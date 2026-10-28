"""Test GDS routes and projection logic without needing a live Neo4j server."""

from fastapi.testclient import TestClient

from app.gds import api, service
from app.main import app

client = TestClient(app)


def test_node_similarity_response(monkeypatch):
    """A known movie returns its graph similarities with the right score."""
    monkeypatch.setattr(api.neo4j_recommendations, "movie_exists", lambda movie_id: movie_id == 1)
    monkeypatch.setattr(service, "node_similarity", lambda movie_id, limit: [
        {"movie_id": 3114, "title": "Toy Story 2 (1999)", "score": 0.42}
    ])
    response = client.get("/api/gds/movies/1/similar?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["source_movie_id"] == 1
    assert data["algorithm"] == "node_similarity"
    assert data["data_source"] == "neo4j_gds"
    assert data["movies"][0]["movie_id"] == 3114


def test_node_similarity_missing_movie(monkeypatch):
    """A missing movie returns HTTP 404 rather than a made-up recommendation."""
    monkeypatch.setattr(api.neo4j_recommendations, "movie_exists", lambda _movie_id: False)
    response = client.get("/api/gds/movies/999999/similar")
    assert response.status_code == 404


def test_node_similarity_rejects_invalid_limit():
    """FastAPI rejects limits outside the allowed interval."""
    assert client.get("/api/gds/movies/1/similar?limit=0").status_code == 422
    assert client.get("/api/gds/movies/1/similar?limit=21").status_code == 422
    assert client.get("/api/gds/movies/0/similar").status_code == 422


def test_pagerank_preserves_raw_score(monkeypatch):
    """A raw PageRank score may exceed 1 and must not be clipped."""
    monkeypatch.setattr(service, "page_rank", lambda limit: [
        {"movie_id": 356, "title": "Forrest Gump (1994)", "score": 11.155}
    ])
    response = client.get("/api/gds/movies/important?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["algorithm"] == "pagerank"
    assert data["movies"][0]["score"] == 11.155


def test_pagerank_rejects_invalid_limit():
    """FastAPI validates the PageRank result count."""
    assert client.get("/api/gds/movies/important?limit=21").status_code == 422


def test_database_unavailable_returns_503(monkeypatch):
    """Database failures are handled without leaking connection credentials."""
    def unavailable(_limit):
        raise RuntimeError("credential or network detail")

    monkeypatch.setattr(service, "page_rank", unavailable)
    response = client.get("/api/gds/movies/important")
    assert response.status_code == 503
    assert "credential" not in response.json()["detail"]


def test_existing_projection_is_reused(monkeypatch):
    """Avoid projecting the same graph repeatedly on every request."""
    calls = []

    def fake_query(query, params, *, write=False):
        calls.append((query, params, write))
        return [{"exists": True}]

    monkeypatch.setattr(service, "_query", fake_query)
    service._ensure_projection(service.SIMILARITY_GRAPH)
    assert len(calls) == 1
    assert calls[0][2] is False


def test_missing_projection_uses_alix_orientation(monkeypatch):
    """Build the correct Movie -> User projection from Alix's Cypher design."""
    calls = []

    def fake_query(query, params, *, write=False):
        calls.append((query, params, write))
        return [{"exists": False}] if not write else [{"graphName": params["graph_name"]}]

    monkeypatch.setattr(service, "_query", fake_query)
    service._ensure_projection(service.SIMILARITY_GRAPH)
    assert len(calls) == 2
    assert "REVERSE" in calls[1][0]
    assert calls[1][2] is True


def test_pagerank_projection_undirected(monkeypatch):
    """Preserve Alix's undirected PageRank projection."""
    calls = []

    def fake_query(query, params, *, write=False):
        calls.append((query, params, write))
        return [{"exists": False}] if not write else [{"graphName": params["graph_name"]}]

    monkeypatch.setattr(service, "_query", fake_query)
    service._ensure_projection(service.PAGERANK_GRAPH)
    assert "UNDIRECTED" in calls[1][0]
