"""Create or remove the precomputed rating statistics used by the optimized trending query.

Run from the repository root, after importing MovieLens:
    python -m scripts.setup_rating_stats          # create properties and index, then check
    python -m scripts.setup_rating_stats --drop   # remove them (back to the baseline graph)

The setup is idempotent: running it twice gives the same graph. After creating the
statistics, the script checks that the optimized query returns exactly the same rows
as the current API query (api_trending) and fails otherwise.
"""

import argparse

from scripts.benchmark_queries import QUERIES, connect

INDEX_NAME = "movie_rating_count_index"

COMPUTE_QUERY = """
MATCH (m:Movie)
OPTIONAL MATCH (m)<-[r:RATED]-(:User)
WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
SET m.ratingCount = rating_count, m.averageRating = average_rating
RETURN count(m) AS movies
"""

INDEX_QUERY = (
    f"CREATE INDEX {INDEX_NAME} IF NOT EXISTS FOR (m:Movie) ON (m.ratingCount)"
)

DROP_QUERIES = [
    "MATCH (m:Movie) REMOVE m.ratingCount, m.averageRating",
    f"DROP INDEX {INDEX_NAME} IF EXISTS",
]


def check_graph(driver, database: str) -> None:
    """Fail clearly when MovieLens has not been imported yet."""
    record = driver.execute_query(
        "CALL () { MATCH (m:Movie) RETURN count(m) AS movies } "
        "CALL () { MATCH ()-[r:RATED]->() RETURN count(r) AS ratings } "
        "RETURN movies, ratings",
        database_=database,
    ).records[0]
    if record["movies"] == 0 or record["ratings"] == 0:
        raise RuntimeError("Empty graph: run python -m scripts.import_movielens first")


def create_stats(driver, database: str) -> None:
    """Store ratingCount and averageRating on every movie and index ratingCount."""
    movies = driver.execute_query(COMPUTE_QUERY, database_=database).records[0]["movies"]
    driver.execute_query(INDEX_QUERY, database_=database)
    driver.execute_query("CALL db.awaitIndexes(300)", database_=database)
    print(f"Rating statistics stored on {movies} movies; index {INDEX_NAME} is online")


def check_same_results(driver, database: str, limit: int) -> None:
    """Fail if the optimized query does not return the same rows as the API query."""
    by_name = {query["name"]: query for query in QUERIES}
    rows = []
    for name in ("api_trending", "variant_trending_precomputed"):
        query = by_name[name]
        records = driver.execute_query(
            query["cypher"],
            parameters_={**query["params"], "limit": limit},
            database_=database,
        ).records
        rows.append([record.data() for record in records])
    if rows[0] != rows[1]:
        raise RuntimeError("The optimized query does not return the same rows as api_trending")
    print(f"Check passed: both queries return the same {len(rows[0])} rows (limit {limit})")


def drop_stats(driver, database: str) -> None:
    """Remove the precomputed properties and their index."""
    for query in DROP_QUERIES:
        driver.execute_query(query, database_=database)
    print(f"Rating statistics and index {INDEX_NAME} removed")


def main() -> None:
    """Parse options and create, check or remove the rating statistics."""
    parser = argparse.ArgumentParser(description="Set up precomputed rating statistics")
    parser.add_argument("--drop", action="store_true", help="remove the statistics")
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--check-limit", type=int, default=50)
    args = parser.parse_args()
    if args.check_limit <= 0:
        raise ValueError("--check-limit must be positive")

    with connect() as driver:
        if args.drop:
            drop_stats(driver, args.database)
            return
        check_graph(driver, args.database)
        create_stats(driver, args.database)
        check_same_results(driver, args.database, args.check_limit)


if __name__ == "__main__":
    main()
