"""Pydantic schemas defining the public API response shapes."""

from typing import Literal

from pydantic import BaseModel, Field


class MovieSuggestion(BaseModel):
    """Represent a recommended movie with a normalized score and reason."""

    movie_id: int = Field(gt=0)
    title: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class MovieRecommendations(BaseModel):
    """Represent movies recommended as similar to a requested movie."""

    movie_id: int
    recommendations: list[MovieSuggestion]
    data_source: Literal["mock", "movielens", "neo4j"] = "mock"


class UserRecommendations(BaseModel):
    """Represent personalized movie recommendations for a user."""

    user_id: int
    recommendations: list[MovieSuggestion]
    data_source: Literal["mock", "movielens", "neo4j"] = "mock"


class TrendingMovies(BaseModel):
    """Represent a ranked list of popular movies."""

    movies: list[MovieSuggestion]
    data_source: Literal["mock", "movielens", "neo4j"] = "mock"
