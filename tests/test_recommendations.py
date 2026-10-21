"""Unit tests use synthetic ratings, and do not pretend to validate real MovieLens quality."""
import pandas as pd
import pytest
from app.recommendations.service import MovieRecommender


@pytest.fixture()
def model(tmp_path):
    pd.DataFrame({"movieId": [1, 2, 3, 4], "title": ["One", "Two", "Three", "Four"],
                  "genres": ["Comedy"] * 4}).to_csv(tmp_path / "movies.csv", index=False)
    data = [(1,1,5),(1,2,5),(1,3,2),(2,1,4),(2,2,4),(2,3,2),
            (3,1,5),(3,2,5),(3,3,1),(4,1,2),(4,2,2),(4,3,5),(4,4,4),(2,4,4),(3,4,5)]
    pd.DataFrame(data, columns=["userId", "movieId", "rating"]).to_csv(tmp_path / "ratings.csv", index=False)
    return MovieRecommender(tmp_path)


def test_similar_omits_source(model):
    similar = model.similar_movies(1)
    assert similar
    assert all(x["movie_id"] != 1 for x in similar)


def test_trending_has_real_counts(model):
    assert model.trending(2)[0]["rating_count"] == 4


def test_recommendations_exclude_watched(model):
    already = set(model.ratings[model.ratings.userId == 1].movieId)
    recs = model.user_recommendations(1)
    assert recs
    assert all(x["movie_id"] not in already for x in recs)


def test_bad_limit(model):
    with pytest.raises(ValueError):
        model.trending(0)


def test_recommendations_need_enough_neighbors(model):
    one_rater = model.ratings[~((model.ratings.movieId == 4) & model.ratings.userId.isin([2, 3]))]
    model.ratings = one_rater
    model.matrix = one_rater.pivot_table(index="userId", columns="movieId", values="rating")
    assert model.user_recommendations(1) == []
