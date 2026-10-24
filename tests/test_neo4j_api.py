"""Test Neo4j API response contracts without needing a live database."""

from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_neo4j_trending(monkeypatch):
    """Graph popularity results retain the public score and source contract."""
    monkeypatch.setenv("MOVIE_DATA_SOURCE", "neo4j")
    monkeypatch.setattr(main.neo4j_recommendations, "trending", lambda limit: [
        {"movie_id": 356, "title": "Forrest Gump", "rating_count": 329, "average_rating": 4.16}
    ][:limit])
    response = client.get("/api/movies/trending?limit=5")
    assert response.status_code == 200
    assert response.json()["data_source"] == "neo4j"
    assert response.json()["movies"][0]["score"] == 1.0


def test_neo4j_similar_and_unknown_movie(monkeypatch):
    """Graph similarity rejects missing movie IDs and returns valid scores."""
    monkeypatch.setenv("MOVIE_DATA_SOURCE", "neo4j")
    monkeypatch.setattr(main.neo4j_recommendations, "movie_exists", lambda movie_id: movie_id == 1)
    monkeypatch.setattr(main.neo4j_recommendations, "similar_movies", lambda movie_id, limit: [
        {"movie_id": 3114, "title": "Toy Story 2", "score": 0.6, "common_raters": 81}
    ][:limit])
    assert client.get("/api/movies/99999/similar").status_code == 404
    response = client.get("/api/movies/1/similar?limit=5")
    assert response.status_code == 200
    assert response.json()["recommendations"][0]["movie_id"] == 3114
    assert response.json()["data_source"] == "neo4j"


def test_neo4j_user_and_discovery(monkeypatch):
    """Graph-based personalized and discovery results are normalized."""
    monkeypatch.setenv("MOVIE_DATA_SOURCE", "neo4j")
    monkeypatch.setattr(main.neo4j_recommendations, "user_exists", lambda user_id: user_id == 1)
    monkeypatch.setattr(main.neo4j_recommendations, "user_recommendations", lambda user_id, limit: [
        {"movie_id": 1203, "title": "12 Angry Men", "score": 4.5, "support": 8}
    ][:limit])
    monkeypatch.setattr(main.neo4j_recommendations, "discover", lambda user_id, limit: [
        {"movie_id": 1244, "title": "Manhattan", "score": 4.0, "support": 3, "rating_count": 45}
    ][:limit])
    response = client.get("/api/users/1/recommendations")
    assert response.status_code == 200
    assert response.json()["recommendations"][0]["score"] == 0.9
    assert response.json()["data_source"] == "neo4j"
    discovery = client.get("/api/users/1/discover")
    assert discovery.status_code == 200
    assert discovery.json()["recommendations"][0]["score"] == 0.8
    assert client.get("/api/users/9999/recommendations").status_code == 404


def test_neo4j_errors_become_service_unavailable(monkeypatch):
    """Missing database configuration gives a clear HTTP error."""
    monkeypatch.setenv("MOVIE_DATA_SOURCE", "neo4j")
    def error(_limit):
        raise RuntimeError("NEO4J_PASSWORD is missing")
    monkeypatch.setattr(main.neo4j_recommendations, "trending", error)
    response = client.get("/api/movies/trending")
    assert response.status_code == 503
    assert response.json()["detail"] == "Neo4j service is unavailable"
