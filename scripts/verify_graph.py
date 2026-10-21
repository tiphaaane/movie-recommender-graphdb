"""Check imported graph connectivity and sample recommendations-related traversals."""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

QUERIES = {
    "Movies": "MATCH (m:Movie) RETURN count(m) AS count",
    "Users": "MATCH (u:User) RETURN count(u) AS count",
    "Genres": "MATCH (g:Genre) RETURN count(g) AS count",
    "Ratings": "MATCH ()-[r:RATED]->() RETURN count(r) AS count",
    "Movie-genres": "MATCH ()-[r:IN_GENRE]->() RETURN count(r) AS count",
    "Tags": "MATCH ()-[r:TAGGED]->() RETURN count(r) AS count",
}


def main() -> None:
    """Print actual graph counts and show Toy Story's connected genres."""
    load_dotenv()
    password = os.getenv("NEO4J_PASSWORD")
    if not password or password.startswith("replace"):
        raise RuntimeError("Configure NEO4J_PASSWORD in the local .env file")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        for label, query in QUERIES.items():
            result = driver.execute_query(query, database_="neo4j")
            print(label, result.records[0]["count"])
        result = driver.execute_query("""
            MATCH (m:Movie {movieId: 1})-[:IN_GENRE]->(g:Genre)
            RETURN m.title AS title, collect(g.name) AS genres
            """, database_="neo4j")
        print("Toy Story graph:", [r.data() for r in result.records])


if __name__ == "__main__":
    main()
