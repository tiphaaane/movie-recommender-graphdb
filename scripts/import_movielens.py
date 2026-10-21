"""Idempotent, parameterized bulk import from MovieLens Small into Neo4j 5.

Run from the repository root:
python -m scripts.import_movielens --data-dir data/ml-latest-small --limit-ratings 1000
python -m scripts.import_movielens --data-dir data/ml-latest-small
"""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

from scripts.movielens_io import batches, movie_rows, rating_rows, tag_rows

SCHEMA_QUERIES = [
    "CREATE CONSTRAINT movie_id_unique IF NOT EXISTS FOR (m:Movie) REQUIRE m.movieId IS UNIQUE",
    "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.userId IS UNIQUE",
    "CREATE CONSTRAINT genre_name_unique IF NOT EXISTS FOR (g:Genre) REQUIRE g.name IS UNIQUE",
    "CREATE INDEX movie_title_index IF NOT EXISTS FOR (m:Movie) ON (m.title)",
    "CREATE INDEX movie_year_index IF NOT EXISTS FOR (m:Movie) ON (m.year)",
]

MOVIES_QUERY = """
UNWIND $rows AS row
MERGE (m:Movie {movieId: row.movieId})
SET m.title = row.title, m.year = row.year
"""

GENRES_QUERY = """
UNWIND $rows AS row
MATCH (m:Movie {movieId: row.movieId})
MERGE (g:Genre {name: row.genre})
MERGE (m)-[:IN_GENRE]->(g)
"""

RATINGS_QUERY = """
UNWIND $rows AS row
MATCH (m:Movie {movieId: row.movieId})
MERGE (u:User {userId: row.userId})
MERGE (u)-[r:RATED]->(m)
SET r.rating = row.rating, r.timestamp = row.timestamp
"""

TAGS_QUERY = """
UNWIND $rows AS row
MATCH (m:Movie {movieId: row.movieId})
MERGE (u:User {userId: row.userId})
MERGE (u)-[t:TAGGED {tagId: row.tagId}]->(m)
SET t.tag = row.tag, t.timestamp = row.timestamp
"""


def import_dataset(data_dir: Path, batch_size: int, limit_ratings: int | None) -> dict:
    """Create schema and import full or sample rows, safely on reruns."""
    if limit_ratings is not None and limit_ratings <= 0:
        raise ValueError("--limit-ratings must be positive")
    movies, genres = movie_rows(data_dir)
    ratings = rating_rows(data_dir, limit=limit_ratings)
    tags = tag_rows(data_dir)
    print(f"Prepared {len(movies)} movies, {len(genres)} movie-genres, "
          f"{len(ratings)} ratings, {len(tags)} tags")
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    if not password or password.startswith("replace"):
        raise RuntimeError("Set your own NEO4J_PASSWORD in the local .env file")

    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        driver.verify_connectivity()
        for query in SCHEMA_QUERIES:
            driver.execute_query(query, database_="neo4j")
        for label, rows, query in [
            ("movies", movies, MOVIES_QUERY),
            ("genres", genres, GENRES_QUERY),
            ("ratings", ratings, RATINGS_QUERY),
            ("tags", tags, TAGS_QUERY),
        ]:
            for group in batches(rows, batch_size):
                driver.execute_query(query, parameters_={"rows": group}, database_="neo4j")
            print(f"Imported {len(rows)} {label} source rows")
    return {"movies": len(movies), "genres": len(genres), "ratings": len(ratings), "tags": len(tags)}


def main() -> None:
    """Parse user options and execute import."""
    parser = argparse.ArgumentParser(description="Import MovieLens Small into Neo4j")
    parser.add_argument("--data-dir", type=Path, default=Path("data/ml-latest-small"))
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--limit-ratings", type=int, default=None)
    arguments = parser.parse_args()
    import_dataset(arguments.data_dir, arguments.batch_size, arguments.limit_ratings)


if __name__ == "__main__":
    main()
