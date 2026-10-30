"""Reproducible Cypher benchmarks for the MovieLens graph (Neo4j 5).

For every query in QUERIES, the script:
1. runs PROFILE once to read the execution plan, operators and database hits;
2. runs the plain query a few times to warm up the page cache;
3. times N runs (wall clock, all records fetched) and reports median, min and max.

Full workflow, from the repository root (see docs/QUERY_BENCHMARKS_JULIETTE.md):
    docker compose up -d neo4j                      # standard project Neo4j service
    python -m scripts.import_movielens              # fresh MovieLens import
    python -m scripts.benchmark_queries --label before
    python -m scripts.setup_rating_stats            # applies the tested optimization
    python -m scripts.benchmark_queries --label after

--label only names the report (docs/benchmarks/results_<label>.md). The optimization
itself is created by scripts/setup_rating_stats.py. Queries marked with "requires" are
skipped, and listed as skipped in the report, until that setup has been run.
"""

import argparse
import os
import platform
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Queries copied from the application code (app/services/neo4j_recommendations.py
# and app/agent/queries.py). If the application queries change, update them here.
_API_CANDIDATES = """
MATCH (u:User {userId: $user_id})-[:RATED]->(seen:Movie)<-[:RATED]-(neighbor:User)
WHERE neighbor <> u
WITH u, neighbor, count(DISTINCT seen) AS shared_movies
WHERE shared_movies >= 3
ORDER BY shared_movies DESC, neighbor.userId ASC
LIMIT 30
MATCH (neighbor)-[r:RATED]->(candidate:Movie)
WHERE NOT EXISTS { MATCH (u)-[:RATED]->(candidate) }
WITH candidate, count(DISTINCT neighbor) AS support,
     sum(shared_movies * r.rating) / toFloat(sum(shared_movies)) AS predicted_rating
WHERE support >= 3
"""

API = "app/services/neo4j_recommendations.py"
AGENT = "app/agent/queries.py"
VARIANT = "variant for comparison (not used by the app)"

QUERIES = [
    {
        "name": "api_movie_exists",
        "source": API,
        "purpose": "Check that a movie id exists before answering",
        "cypher": "MATCH (m:Movie {movieId: $movie_id}) RETURN m.movieId AS movie_id LIMIT 1",
        "params": {"movie_id": 1},
    },
    {
        "name": "api_user_exists",
        "source": API,
        "purpose": "Check that a user id exists before answering",
        "cypher": "MATCH (u:User {userId: $user_id}) RETURN u.userId AS user_id LIMIT 1",
        "params": {"user_id": 1},
    },
    {
        "name": "api_trending",
        "source": API,
        "purpose": "Most rated movies (aggregation over all ratings)",
        "cypher": """
MATCH (m:Movie)<-[r:RATED]-(:User)
WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
WHERE rating_count >= 3
RETURN m.movieId AS movie_id, m.title AS title,
       rating_count, round(average_rating, 2) AS average_rating
ORDER BY rating_count DESC, average_rating DESC, movie_id ASC
LIMIT $limit
""",
        "params": {"limit": 10},
    },
    {
        "name": "api_similar_movies",
        "source": API,
        "purpose": "Co-rated movies with rating agreement (Toy Story)",
        "cypher": """
MATCH (target:Movie {movieId: $movie_id})<-[r1:RATED]-(u:User)-[r2:RATED]->(other:Movie)
WHERE other <> target
WITH other, count(DISTINCT u) AS common_raters,
     avg(1.0 - abs(r1.rating - r2.rating) / 4.5) AS agreement
WHERE common_raters >= 3
RETURN other.movieId AS movie_id, other.title AS title,
       round(agreement * (toFloat(common_raters) / (common_raters + 10.0)), 4) AS score,
       common_raters
ORDER BY score DESC, common_raters DESC, movie_id ASC
LIMIT $limit
""",
        "params": {"movie_id": 1, "limit": 10},
    },
    {
        "name": "api_user_recommendations",
        "source": API,
        "purpose": "Personalized recommendations from the 30 closest users",
        "cypher": _API_CANDIDATES + """
RETURN candidate.movieId AS movie_id, candidate.title AS title,
       round(predicted_rating, 4) AS score, support
ORDER BY score DESC, support DESC, movie_id ASC
LIMIT $limit
""",
        "params": {"user_id": 1, "limit": 10},
    },
    {
        "name": "api_discover",
        "source": API,
        "purpose": "Personalized recommendations favouring less-rated movies",
        "cypher": _API_CANDIDATES + """
MATCH (candidate)<-[all_rating:RATED]-(:User)
WITH candidate, support, predicted_rating, count(all_rating) AS rating_count
RETURN candidate.movieId AS movie_id, candidate.title AS title,
       round(predicted_rating, 4) AS score, support, rating_count
ORDER BY rating_count ASC, score DESC, movie_id ASC
LIMIT $limit
""",
        "params": {"user_id": 1, "limit": 10},
    },
    {
        "name": "agent_movies_by_genre",
        "source": AGENT,
        "purpose": "Most rated movies of a genre, case-insensitive genre name",
        "cypher": """
MATCH (m:Movie)-[:IN_GENRE]->(g:Genre)
WHERE toLower(g.name) = toLower($genre)
OPTIONAL MATCH (:User)-[r:RATED]->(m)
WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
RETURN m.movieId AS movie_id, m.title AS title,
       rating_count, round(average_rating * 100) / 100 AS average_rating
ORDER BY rating_count DESC, average_rating DESC, movie_id
LIMIT $limit
""",
        "params": {"genre": "comedy", "limit": 10},
    },
    {
        "name": "variant_movies_by_genre_exact",
        "source": VARIANT,
        "purpose": "Same as agent_movies_by_genre, exact genre name (index lookup)",
        "cypher": """
MATCH (g:Genre {name: $genre})<-[:IN_GENRE]-(m:Movie)
OPTIONAL MATCH (:User)-[r:RATED]->(m)
WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
RETURN m.movieId AS movie_id, m.title AS title,
       rating_count, round(average_rating * 100) / 100 AS average_rating
ORDER BY rating_count DESC, average_rating DESC, movie_id
LIMIT $limit
""",
        "params": {"genre": "Comedy", "limit": 10},
    },
    {
        "name": "agent_movies_like",
        "source": AGENT,
        "purpose": "Movies sharing the most genres with a seed movie",
        "cypher": """
MATCH (seed:Movie {movieId: $movie_id})-[:IN_GENRE]->(g:Genre)
      <-[:IN_GENRE]-(m:Movie)
WHERE m.movieId <> $movie_id
WITH m, count(DISTINCT g) AS shared_genres
RETURN m.movieId AS movie_id, m.title AS title, shared_genres
ORDER BY shared_genres DESC, movie_id
LIMIT $limit
""",
        "params": {"movie_id": 1, "limit": 10},
    },
    {
        "name": "agent_user_favorites",
        "source": AGENT,
        "purpose": "Movies a user rated 4 or more",
        "cypher": """
MATCH (u:User {userId: $user_id})-[r:RATED]->(m:Movie)
WHERE r.rating >= 4
RETURN m.movieId AS movie_id, m.title AS title, r.rating AS rating
ORDER BY rating DESC, movie_id
LIMIT $limit
""",
        "params": {"user_id": 1, "limit": 10},
    },
    {
        "name": "agent_popular_movies",
        "source": AGENT,
        "purpose": "Most rated movies overall (aggregation over all ratings)",
        "cypher": """
MATCH (:User)-[r:RATED]->(m:Movie)
WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
RETURN m.movieId AS movie_id, m.title AS title,
       rating_count, round(average_rating * 100) / 100 AS average_rating
ORDER BY rating_count DESC, average_rating DESC, movie_id
LIMIT $limit
""",
        "params": {"limit": 10},
    },
    {
        "name": "variant_trending_precomputed",
        "source": VARIANT,
        "purpose": "Same ranking as api_trending, read from precomputed Movie properties",
        "requires": "rating_stats",
        "cypher": """
MATCH (m:Movie)
WHERE m.ratingCount >= 3
RETURN m.movieId AS movie_id, m.title AS title,
       m.ratingCount AS rating_count, round(m.averageRating, 2) AS average_rating
ORDER BY rating_count DESC, average_rating DESC, movie_id ASC
LIMIT $limit
""",
        "params": {"limit": 10},
    },
    {
        "name": "agent_explain_shared_genres",
        "source": AGENT,
        "purpose": "Genres shared by two movies (explains a recommendation)",
        "cypher": """
MATCH (a:Movie {movieId: $source_id})-[:IN_GENRE]->(g:Genre)
      <-[:IN_GENRE]-(b:Movie {movieId: $recommended_id})
RETURN g.name AS genre
ORDER BY genre
LIMIT 20
""",
        "params": {"source_id": 1, "recommended_id": 3114},
    },
]

FULL_SCAN_OPERATORS = {"AllNodesScan", "NodeByLabelScan"}


def plan_stats(plan: dict) -> tuple[int, list[str]]:
    """Return the total database hits and the operator names of a PROFILE plan tree."""
    hits = int(plan.get("dbHits", plan.get("db_hits", 0)) or 0)
    operators = [str(plan.get("operatorType", "?")).split("@", maxsplit=1)[0]]
    for child in plan.get("children", []):
        child_hits, child_operators = plan_stats(child)
        hits += child_hits
        operators.extend(child_operators)
    return hits, operators


def safe_label(label: str) -> str:
    """Keep only characters that are safe in a file name."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", label).strip("_")
    return cleaned or "run"


def connect():
    """Open a Neo4j driver from the local .env file."""
    load_dotenv()
    password = os.getenv("NEO4J_PASSWORD")
    if not password or password.startswith("replace"):
        raise RuntimeError("Configure NEO4J_PASSWORD in the local .env file")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    return driver


def environment_info(driver, database: str) -> dict:
    """Collect the Neo4j version and graph size, so results can be compared."""
    version = driver.execute_query(
        "CALL dbms.components() YIELD name, versions, edition "
        "RETURN name + ' ' + versions[0] + ' (' + edition + ')' AS version",
        database_=database,
    ).records[0]["version"]
    movies = driver.execute_query(
        "MATCH (m:Movie) RETURN count(m) AS n", database_=database
    ).records[0]["n"]
    ratings = driver.execute_query(
        "MATCH ()-[r:RATED]->() RETURN count(r) AS n", database_=database
    ).records[0]["n"]
    return {"version": version, "movies": movies, "ratings": ratings}


def rating_stats_ready(driver, database: str) -> bool:
    """Return True when every movie has the precomputed rating statistics."""
    record = driver.execute_query(
        "MATCH (m:Movie) RETURN count(m) AS movies, count(m.ratingCount) AS with_stats",
        database_=database,
    ).records[0]
    return record["movies"] > 0 and record["with_stats"] == record["movies"]


def benchmark(driver, database: str, query: dict, runs: int, warmup: int) -> dict:
    """PROFILE a query once, then time repeated plain executions."""
    records, summary, _ = driver.execute_query(
        "PROFILE " + query["cypher"], parameters_=query["params"], database_=database
    )
    hits, operators = plan_stats(summary.profile or {})
    for _ in range(warmup):
        driver.execute_query(query["cypher"], parameters_=query["params"], database_=database)
    timings = []
    for _ in range(runs):
        start = time.perf_counter()
        driver.execute_query(query["cypher"], parameters_=query["params"], database_=database)
        timings.append((time.perf_counter() - start) * 1000)
    unique_operators = list(dict.fromkeys(operators))
    return {
        **query,
        "rows": len(records),
        "db_hits": hits,
        "operators": unique_operators,
        "uses_index": any("Index" in name for name in unique_operators),
        "full_scan": any(name in FULL_SCAN_OPERATORS for name in unique_operators),
        "median_ms": statistics.median(timings),
        "min_ms": min(timings),
        "max_ms": max(timings),
    }


def render_report(
    label: str, info: dict, settings: dict, results: list[dict], skipped: list[str]
) -> str:
    """Build the Markdown report with a summary table and one section per query."""
    lines = [
        f"# Cypher benchmark results: {label}",
        "",
        f"- Date (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        f"- Neo4j: {info['version']}",
        f"- Graph: {info['movies']} movies, {info['ratings']} ratings",
        f"- Timed runs per query: {settings['runs']} (after {settings['warmup']} warm-up runs)",
        f"- Machine: {platform.platform()}, Python {platform.python_version()}",
        "- Times are wall-clock in ms, client side, all records fetched.",
        "",
        "| Query | Source | Rows | DB hits | Median ms | Min ms | Max ms "
        "| Index used | Label scan |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for res in results:
        lines.append(
            f"| {res['name']} | {res['source']} | {res['rows']} | {res['db_hits']} "
            f"| {res['median_ms']:.2f} "
            f"| {res['min_ms']:.2f} | {res['max_ms']:.2f} "
            f"| {'yes' if res['uses_index'] else 'no'} | {'yes' if res['full_scan'] else 'no'} |"
        )
    if skipped:
        lines += [
            "",
            f"Skipped (run `python -m scripts.setup_rating_stats` first): {', '.join(skipped)}",
        ]
    for res in results:
        lines += [
            "",
            f"## {res['name']}",
            "",
            f"Source: {res['source']}",
            "",
            f"Purpose: {res['purpose']}",
            "",
            "```cypher",
            res["cypher"].strip(),
            "```",
            "",
            f"Parameters: `{res['params']}`",
            "",
            f"Plan operators: {' -> '.join(res['operators'])}",
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    """Parse options, run every selected benchmark and write the report."""
    parser = argparse.ArgumentParser(description="Benchmark Cypher queries with PROFILE")
    parser.add_argument("--label", default="run", help="e.g. before / after")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--output-dir", type=Path, default=Path("docs/benchmarks"))
    parser.add_argument("--only", nargs="*", help="names of the queries to run")
    args = parser.parse_args()
    if args.runs <= 0 or args.warmup < 0:
        raise ValueError("--runs must be positive and --warmup non-negative")

    selected = [q for q in QUERIES if not args.only or q["name"] in args.only]
    if not selected:
        raise ValueError("No query matches --only")

    with connect() as driver:
        info = environment_info(driver, args.database)
        stats_ready = rating_stats_ready(driver, args.database)
        results, skipped = [], []
        for query in selected:
            if query.get("requires") == "rating_stats" and not stats_ready:
                print(f"{query['name']:<30} skipped: run python -m scripts.setup_rating_stats")
                skipped.append(query["name"])
                continue
            result = benchmark(driver, args.database, query, args.runs, args.warmup)
            results.append(result)
            print(
                f"{result['name']:<30} rows={result['rows']:<4} "
                f"db_hits={result['db_hits']:<9} median={result['median_ms']:.2f} ms"
            )

    label = safe_label(args.label)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"results_{label}.md"
    settings = {"runs": args.runs, "warmup": args.warmup}
    output.write_text(render_report(label, info, settings, results, skipped), encoding="utf-8")
    print(f"Report written to {output}")


if __name__ == "__main__":
    main()
