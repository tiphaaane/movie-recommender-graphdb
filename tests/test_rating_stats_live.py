"""Live non-regression checks on a real MovieLens Neo4j database.

These tests need a running, imported database configured in .env. They are skipped
automatically when no database is available, for example in GitHub Actions.
"""

import os

import pytest
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

from app.services import neo4j_recommendations
from scripts.setup_rating_stats import create_stats


@pytest.fixture(scope="module", name="driver")
def fixture_driver():
    """Connect to the local database, or skip when none is available."""
    load_dotenv()
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        pytest.skip("No NEO4J_PASSWORD configured: live Neo4j tests skipped")
    graph = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), password),
    )
    try:
        graph.verify_connectivity()
    except (ServiceUnavailable, AuthError, OSError):
        graph.close()
        pytest.skip("Neo4j is not reachable: live Neo4j tests skipped")
    yield graph
    graph.close()


def run(driver, query, **parameters):
    """Return the rows of a query as plain dictionaries."""
    return [record.data() for record in
            driver.execute_query(query, parameters_=parameters, database_="neo4j").records]


def test_optimized_trending_matches_the_previous_query(driver):
    """Same movies, same order, same values as before the optimization."""
    for limit in (10, 100):
        optimized = run(driver, neo4j_recommendations.TRENDING_QUERY, limit=limit)
        previous = run(driver, neo4j_recommendations.TRENDING_FALLBACK_QUERY, limit=limit)
        assert optimized, "No statistics: re-import MovieLens first"
        assert optimized == previous


def test_rating_count_matches_the_ratings(driver):
    """Every stored ratingCount equals the real number of RATED relationships."""
    mismatches = run(driver, """
        MATCH (m:Movie)
        OPTIONAL MATCH (m)<-[r:RATED]-(:User)
        WITH m, count(r) AS real_count
        WHERE m.ratingCount IS NULL OR m.ratingCount <> real_count
        RETURN count(m) AS movies
        """)[0]["movies"]
    assert mismatches == 0


def test_movies_without_ratings_have_zero_count(driver):
    """Unrated movies get ratingCount = 0 and no average."""
    row = run(driver, """
        MATCH (m:Movie)
        WHERE NOT EXISTS { (m)<-[:RATED]-(:User) }
        RETURN count(m) AS movies, collect(DISTINCT m.ratingCount) AS counts,
               count(m.averageRating) AS averages
        """)[0]
    if row["movies"] == 0:
        pytest.skip("Every movie has at least one rating in this database")
    assert row["counts"] == [0]
    assert row["averages"] == 0


def test_statistics_are_reproducible(driver):
    """Recomputing the statistics leaves the graph unchanged."""
    snapshot = """
        MATCH (m:Movie)
        RETURN sum(m.ratingCount) AS total, count(m.averageRating) AS averages,
               round(sum(m.averageRating), 6) AS average_sum
        """
    before = run(driver, snapshot)
    create_stats(driver, "neo4j")
    assert run(driver, snapshot) == before
