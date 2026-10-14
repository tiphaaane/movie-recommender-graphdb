"""HTTP endpoints for the team's graph-backed Movie Recommender."""

from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query
from app.agent.api import router as agent_router
from app.schemas import MovieRecommendations, TrendingMovies, UserRecommendations
from app.services import mock_data

app = FastAPI(
    title="Movie Recommender API",
    description="Week 1 prototype using mock data; Neo4j integration follows.",
    version="0.1.0",
)
app.include_router(agent_router)

Limit = Annotated[int, Query(ge=1, le=20, description="Number of results (1–20)")]
MovieId = Annotated[int, Path(gt=0, description="MovieLens movie ID")]
UserId = Annotated[int, Path(gt=0, description="MovieLens user ID")]


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    """Confirm that the API is running."""
    return {"status": "ok", "data_source": "mock"}


@app.get("/api/movies/trending", response_model=TrendingMovies, tags=["Movies"])
def trending_movies(limit: Limit = 5) -> TrendingMovies:
    """Return a sample popularity ranking, later replaced by Neo4j."""
    return TrendingMovies(movies=mock_data.suggestions(mock_data.TRENDING, limit))


@app.get(
    "/api/movies/{movie_id}/similar",
    response_model=MovieRecommendations,
    tags=["Movies"],
)
def similar_movies(movie_id: MovieId, limit: Limit = 5) -> MovieRecommendations:
    """Return sample movies ranked by their similarity to the given movie."""
    if movie_id not in mock_data.MOVIES:
        raise HTTPException(status_code=404, detail="Movie not found")
    return MovieRecommendations(
        movie_id=movie_id,
        recommendations=mock_data.suggestions(mock_data.SIMILARITY[movie_id], limit),
    )


@app.get(
    "/api/users/{user_id}/recommendations",
    response_model=UserRecommendations,
    tags=["Users"],
)
def user_recommendations(user_id: UserId, limit: Limit = 5) -> UserRecommendations:
    """Return an illustrative personalized recommendation list."""
    if user_id not in mock_data.USER_RECOMMENDATIONS:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRecommendations(
        user_id=user_id,
        recommendations=mock_data.suggestions(mock_data.USER_RECOMMENDATIONS[user_id], limit),
    )


@app.get(
    "/api/users/{user_id}/discover",
    response_model=UserRecommendations,
    tags=["Users"],
)
def discover_movies(user_id: UserId, limit: Limit = 5) -> UserRecommendations:
    """Return illustrative less-obvious movie suggestions."""
    if user_id not in mock_data.USER_DISCOVERY:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRecommendations(
        user_id=user_id,
        recommendations=mock_data.suggestions(mock_data.USER_DISCOVERY[user_id], limit),
    )
