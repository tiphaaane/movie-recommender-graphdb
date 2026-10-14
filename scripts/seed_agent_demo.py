"""Seed a disposable local Neo4j graph for Apolline's independent demo only.

Use only on an EMPTY, throwaway development database. This script creates
illustrative ratings; never present those as genuine MovieLens observations.
"""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

DEMO_QUERY = """
UNWIND [
    {id: 1, title: 'Toy Story (1995)', genres: ['Adventure', 'Comedy', 'Fantasy']},
    {id: 2, title: 'Jumanji (1995)', genres: ['Adventure', 'Fantasy']},
    {id: 3, title: 'Grumpier Old Men (1995)', genres: ['Comedy']}
] AS row
MERGE (m:Movie {movieId: row.id})
SET m.title = row.title, m.sample_only = true
WITH m, row
UNWIND row.genres AS genre
MERGE (g:Genre {name: genre})
MERGE (m)-[:IN_GENRE]->(g)
"""
RATING_QUERY = """
MERGE (u:User {userId: 1})
MERGE (m:Movie {movieId: 1})
MERGE (u)-[r:RATED]->(m)
SET r.rating = 5.0, r.sample_only = true
"""


def main() -> None:
    """Populate three movie nodes and a synthetic sample rating."""
    load_dotenv()
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("Set local NEO4J_PASSWORD in .env first")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    with GraphDatabase.driver(uri, auth=(os.getenv("NEO4J_USER", "neo4j"), password)) as driver:
        driver.verify_connectivity()
        records, _, _ = driver.execute_query(
            "MATCH (n) RETURN count(n) AS total", database_="neo4j"
        )
        if records[0]["total"]:
            raise RuntimeError("Demo seeding requires a completely empty Neo4j database")
        driver.execute_query(DEMO_QUERY, database_="neo4j")
        driver.execute_query(RATING_QUERY, database_="neo4j")
    print("Seeded DEMO-ONLY graph; data is illustrative, NOT sourced from MovieLens")


if __name__ == "__main__":
    main()
