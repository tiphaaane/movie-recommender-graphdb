"""Tests for the public FastAPI contract before Neo4j integration."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    """The app responds to its health check."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data_source": "mock"}


def test_similar_movies() -> None:
    """A known movie receives valid mock recommendations."""
    response = client.get("/api/movies/1/similar?limit=2")
    assert response.status_code == 200
    body = response.json()
    assert body["movie_id"] == 1
    assert body["data_source"] == "mock"
    assert len(body["recommendations"]) == 2
    assert all(0 <= item["score"] <= 1 for item in body["recommendations"])


def test_similar_movies_unknown_id() -> None:
    """Unknown movies result in a useful 404."""
    response = client.get("/api/movies/999999/similar")
    assert response.status_code == 404
    assert response.json()["detail"] == "Movie not found"


def test_similar_movies_invalid_limit() -> None:
    """Pydantic rejects an invalid query parameter."""
    response = client.get("/api/movies/1/similar?limit=0")
    assert response.status_code == 422


def test_similar_movies_invalid_movie_id() -> None:
    """Pydantic rejects a non-positive movie ID."""
    response = client.get("/api/movies/0/similar")
    assert response.status_code == 422


def test_user_recommendations() -> None:
    """Personalized recommendation endpoint is available."""
    response = client.get("/api/users/1/recommendations")
    assert response.status_code == 200
    assert response.json()["user_id"] == 1


def test_user_recommendations_unknown_id() -> None:
    """Unknown users result in a useful 404."""
    response = client.get("/api/users/999999/recommendations")
    assert response.status_code == 404


def test_discover_movies() -> None:
    """Discovery endpoint returns a list."""
    response = client.get("/api/users/1/discover?limit=1")
    assert response.status_code == 200
    assert len(response.json()["recommendations"]) == 1


def test_trending_movies() -> None:
    """Trending endpoint respects its limit."""
    response = client.get("/api/movies/trending?limit=2")
    assert response.status_code == 200
    assert len(response.json()["movies"]) == 2
