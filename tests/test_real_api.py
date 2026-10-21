"""Real-mode API contract checks using a small synthetic rating dataset."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture()
def real_client(tmp_path, monkeypatch):
    """Enable MovieLens mode without requiring raw MovieLens data in CI."""
    pd.DataFrame(
        {
            "movieId": [1, 2, 3, 4],
            "title": ["Toy Story (1995)", "Movie two", "Movie three", "Movie four"],
            "genres": ["Comedy", "Comedy", "Drama", "Comedy"],
        }
    ).to_csv(tmp_path / "movies.csv", index=False)
    rows = [
        (1, 1, 5), (1, 2, 4), (1, 3, 2),
        (2, 1, 5), (2, 2, 5), (2, 3, 2), (2, 4, 4),
        (3, 1, 4), (3, 2, 4), (3, 3, 1), (3, 4, 5),
        (4, 1, 2), (4, 2, 1), (4, 3, 4), (4, 4, 4),
        (5, 1, 5), (5, 2, 5), (5, 3, 2), (5, 4, 5),
    ]
    pd.DataFrame(rows, columns=["userId", "movieId", "rating"]).to_csv(
        tmp_path / "ratings.csv", index=False
    )
    monkeypatch.setattr(main, "MOVIELENS_DIR", tmp_path)
    monkeypatch.setenv("MOVIE_DATA_SOURCE", "movielens")
    main.get_recommender.cache_clear()
    yield TestClient(main.app)
    main.get_recommender.cache_clear()


def test_real_popularity_has_valid_scores(real_client):
    result = real_client.get("/api/movies/trending?limit=3")
    assert result.status_code == 200
    body = result.json()
    assert body["data_source"] == "movielens"
    assert body["movies"]
    assert all(0 <= movie["score"] <= 1 for movie in body["movies"])


def test_real_similar_excludes_source(real_client):
    result = real_client.get("/api/movies/1/similar?limit=5")
    assert result.status_code == 200
    body = result.json()
    assert body["data_source"] == "movielens"
    assert body["recommendations"]
    assert all(movie["movie_id"] != 1 for movie in body["recommendations"])


def test_personalized_and_discover_use_unseen_movies(real_client):
    for path in ("recommendations", "discover"):
        result = real_client.get(f"/api/users/1/{path}?limit=5")
        assert result.status_code == 200
        body = result.json()
        assert body["data_source"] == "movielens"
        assert body["recommendations"]
        assert all(movie["movie_id"] == 4 for movie in body["recommendations"])
        assert all(0 <= movie["score"] <= 1 for movie in body["recommendations"])


def test_real_unknown_user_is_404(real_client):
    response = real_client.get("/api/users/999/recommendations")
    assert response.status_code == 404
