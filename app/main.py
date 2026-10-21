"""HTTP endpoints for the team's Movie Recommender."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path as ApiPath, Query

from app.agent.api import router as agent_router
from app.recommendations.service import MovieRecommender
from app.schemas import MovieRecommendations, MovieSuggestion, TrendingMovies, UserRecommendations
from app.services import mock_data

app = FastAPI(
    title="Movie Recommender API",
    description="MovieLens recommendation baseline, with mock fallback; Neo4j integration follows.",
    version="0.2.0",
)
app.include_router(agent_router)

Limit = Annotated[int, Query(ge=1, le=20, description="Number of results (1–20)")]
MovieId = Annotated[int, ApiPath(gt=0, description="MovieLens movie ID")]
UserId = Annotated[int, ApiPath(gt=0, description="MovieLens user ID")]

MOVIELENS_DIR = Path(__file__).resolve().parent.parent / "data" / "ml-latest-small"


def using_movielens() -> bool:
    """Keep mock mode as the default for the existing CI tests."""
    return os.getenv("MOVIE_DATA_SOURCE", "mock").lower() == "movielens"


@lru_cache(maxsize=1)
def get_recommender() -> MovieRecommender:
    """Load MovieLens only once instead of for every HTTP request."""
    if not (MOVIELENS_DIR / "movies.csv").is_file() or not (MOVIELENS_DIR / "ratings.csv").is_file():
        raise HTTPException(status_code=503, detail="MovieLens CSV files are missing in data/ml-latest-small")
    return MovieRecommender(MOVIELENS_DIR)


def predicted_rating_suggestion(item: dict, reason_prefix: str) -> MovieSuggestion:
    """Convert a predicted 0–5 star rating into an API score of 0–1."""
    stars = float(item["score"])
    return MovieSuggestion(
        movie_id=int(item["movie_id"]),
        title=str(item["title"]),
        score=round(max(0.0, min(1.0, stars / 5.0)), 4),
        reason=f"{reason_prefix}: predicted rating {stars:.2f}/5 (normalized score, not a probability)",
    )


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    """Confirm that the API is running and identify its chosen source."""
    return {"status": "ok", "data_source": "movielens" if using_movielens() else "mock"}


@app.get("/api/movies/trending", response_model=TrendingMovies, tags=["Movies"])
def trending_movies(limit: Limit = 5) -> TrendingMovies:
    """Rank movies by number of ratings (all-time popularity, not recent trends)."""
    if not using_movielens():
        return TrendingMovies(movies=mock_data.suggestions(mock_data.TRENDING, limit))
    rows = get_recommender().trending(limit)
    max_count = max((item["rating_count"] for item in rows), default=1)
    movies = [MovieSuggestion(
        movie_id=item["movie_id"], title=item["title"],
        score=round(item["rating_count"] / max_count, 4),
        reason=f"{item['rating_count']} ratings; average {item['average_rating']:.2f}/5 (all-time popularity)",
    ) for item in rows]
    return TrendingMovies(movies=movies, data_source="movielens")


@app.get("/api/movies/{movie_id}/similar", response_model=MovieRecommendations, tags=["Movies"])
def similar_movies(movie_id: MovieId, limit: Limit = 5) -> MovieRecommendations:
    """Return movies with positively correlated rating patterns."""
    if not using_movielens():
        if movie_id not in mock_data.MOVIES:
            raise HTTPException(status_code=404, detail="Movie not found")
        return MovieRecommendations(
            movie_id=movie_id,
            recommendations=mock_data.suggestions(mock_data.SIMILARITY[movie_id], limit),
        )
    model = get_recommender()
    if movie_id not in model.movie_title:
        raise HTTPException(status_code=404, detail="Movie not found")
    rows = model.similar_movies(movie_id, limit)
    recommendations = [MovieSuggestion(
        movie_id=item["movie_id"], title=item["title"],
        score=round(min(1.0, float(item["score"])), 4),
        reason=f"Similar rating patterns among {item['common_raters']} shared raters",
    ) for item in rows if float(item["score"]) > 0]
    return MovieRecommendations(movie_id=movie_id, recommendations=recommendations, data_source="movielens")


@app.get("/api/users/{user_id}/recommendations", response_model=UserRecommendations, tags=["Users"])
def user_recommendations(user_id: UserId, limit: Limit = 5) -> UserRecommendations:
    """Personalized recommendations from ratings of similar users."""
    if not using_movielens():
        if user_id not in mock_data.USER_RECOMMENDATIONS:
            raise HTTPException(status_code=404, detail="User not found")
        return UserRecommendations(
            user_id=user_id,
            recommendations=mock_data.suggestions(mock_data.USER_RECOMMENDATIONS[user_id], limit),
        )
    model = get_recommender()
    if user_id not in model.matrix.index:
        raise HTTPException(status_code=404, detail="User not found")
    rows = model.user_recommendations(user_id, limit)
    return UserRecommendations(
        user_id=user_id,
        recommendations=[predicted_rating_suggestion(item, "Similar-user recommendation") for item in rows],
        data_source="movielens",
    )


@app.get("/api/users/{user_id}/discover", response_model=UserRecommendations, tags=["Users"])
def discover_movies(user_id: UserId, limit: Limit = 5) -> UserRecommendations:
    """Prefer less-rated movies from a user's personalized candidate pool."""
    if not using_movielens():
        if user_id not in mock_data.USER_DISCOVERY:
            raise HTTPException(status_code=404, detail="User not found")
        return UserRecommendations(
            user_id=user_id,
            recommendations=mock_data.suggestions(mock_data.USER_DISCOVERY[user_id], limit),
        )
    model = get_recommender()
    if user_id not in model.matrix.index:
        raise HTTPException(status_code=404, detail="User not found")
    candidates = model.user_recommendations(user_id, limit=20)
    popularity = model.ratings["movieId"].value_counts()
    selected = sorted(candidates, key=lambda item: (
        int(popularity.get(item["movie_id"], 0)),
        -float(item["score"]),
        int(item["movie_id"]),
    ))[:limit]
    recommendations = [predicted_rating_suggestion(
        item, f"Less-popular discovery pick ({int(popularity.get(item['movie_id'], 0))} ratings)",
    ) for item in selected]
    return UserRecommendations(user_id=user_id, recommendations=recommendations, data_source="movielens")
