"""Infrastructure tests for the Movie Recommender API."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_health_endpoint_exists():
    """Check that the health endpoint responds successfully."""
    response = client.get("/health")
    assert response.status_code == 200


def test_trending_movies_endpoint_exists():
    """Check that the trending movies endpoint is available."""
    response = client.get("/api/movies/trending")
    assert response.status_code == 200


def test_similar_movies_endpoint_exists():
    """Check that the similar movies endpoint is available."""
    response = client.get("/api/movies/1/similar")
    assert response.status_code == 200


def test_user_recommendations_endpoint_exists():
    """Check that the user recommendations endpoint is available."""
    response = client.get("/api/users/1/recommendations")
    assert response.status_code == 200


def test_user_discover_endpoint_exists():
    """Check that the user discover endpoint is available."""
    response = client.get("/api/users/1/discover")
    assert response.status_code == 200


def test_dockerfile_exists():
    """Check that the Dockerfile exists."""
    assert (PROJECT_ROOT / "Dockerfile").is_file()


def test_docker_compose_exists():
    """Check that the Docker Compose configuration exists."""
    assert (PROJECT_ROOT / "docker-compose.yml").is_file()


def test_makefile_exists():
    """Check that the Makefile exists."""
    assert (PROJECT_ROOT / "Makefile").is_file()


def test_nginx_configuration_exists():
    """Check that the Nginx configuration directory exists."""
    assert (PROJECT_ROOT / "nginx").is_dir()