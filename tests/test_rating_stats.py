"""Unit tests for the precomputed rating statistics (no Neo4j server needed)."""

from pathlib import Path
from types import SimpleNamespace

from app.services import neo4j_recommendations
from scripts import import_movielens
from scripts.setup_rating_stats import COMPUTE_QUERY, INDEX_QUERY

ROWS = [{"movie_id": 356, "title": "Forrest Gump (1994)", "rating_count": 329,
         "average_rating": 4.16}]


def test_trending_reads_precomputed_statistics(monkeypatch):
    """When the statistics exist, a single fast query is used."""
    calls = []

    def fake_read(query, parameters):
        calls.append((query, parameters))
        return ROWS

    monkeypatch.setattr(neo4j_recommendations, "read_cypher", fake_read)
    assert neo4j_recommendations.trending(5) == ROWS
    assert calls == [(neo4j_recommendations.TRENDING_QUERY, {"limit": 5})]
    assert "m.ratingCount" in calls[0][0]


def test_trending_falls_back_when_statistics_are_missing(monkeypatch):
    """A database imported before the change still gets the same answer."""
    calls = []

    def fake_read(query, parameters):
        calls.append(query)
        return [] if query == neo4j_recommendations.TRENDING_QUERY else ROWS

    monkeypatch.setattr(neo4j_recommendations, "read_cypher", fake_read)
    assert neo4j_recommendations.trending(5) == ROWS
    assert calls == [
        neo4j_recommendations.TRENDING_QUERY,
        neo4j_recommendations.TRENDING_FALLBACK_QUERY,
    ]


def test_trending_queries_keep_the_same_response_columns():
    """Both queries return the columns used by the API response."""
    for query in (neo4j_recommendations.TRENDING_QUERY,
                  neo4j_recommendations.TRENDING_FALLBACK_QUERY):
        for column in ("AS movie_id", "AS title", "rating_count", "AS average_rating"):
            assert column in query
        assert "ORDER BY rating_count DESC, average_rating DESC, movie_id ASC" in query


def test_averages_use_exact_sum_over_count():
    """avg() is order-dependent and once rounded 3.375 to 3.37 instead of 3.38."""
    for query in (COMPUTE_QUERY, neo4j_recommendations.TRENDING_FALLBACK_QUERY):
        assert "avg(" not in query
        assert "sum(r.rating)" in query


class FakeDriver:
    """Records the Cypher statements sent by the importer."""

    def __init__(self):
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def verify_connectivity(self):
        """Pretend the database is reachable."""

    def execute_query(self, query, parameters_=None, database_=None):
        """Store the query and return a minimal result."""
        del parameters_, database_
        self.queries.append(query)
        return SimpleNamespace(records=[{"movies": 3}])


def write_data(folder: Path) -> None:
    """Create minimal MovieLens-format CSV files."""
    (folder / "movies.csv").write_text(
        "movieId,title,genres\n1,Toy Story (1995),Comedy\n2,Unrated (2000),Drama\n",
        encoding="utf-8")
    (folder / "ratings.csv").write_text(
        "userId,movieId,rating,timestamp\n1,1,4.5,111\n", encoding="utf-8")
    (folder / "tags.csv").write_text("userId,movieId,tag,timestamp\n", encoding="utf-8")


def test_import_computes_statistics_automatically(tmp_path, monkeypatch):
    """The normal import ends by storing the statistics and creating their index."""
    write_data(tmp_path)
    driver = FakeDriver()
    monkeypatch.setenv("NEO4J_PASSWORD", "test-password")
    monkeypatch.setattr(import_movielens, "GraphDatabase",
                        SimpleNamespace(driver=lambda *args, **kwargs: driver))
    import_movielens.import_dataset(tmp_path, batch_size=10, limit_ratings=None)
    ratings_position = driver.queries.index(import_movielens.RATINGS_QUERY)
    compute_position = driver.queries.index(COMPUTE_QUERY)
    assert compute_position > ratings_position
    assert INDEX_QUERY in driver.queries[compute_position:]
