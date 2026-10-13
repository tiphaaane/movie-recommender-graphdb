"""Pydantic schemas defining the public API response shapes."""

from typing import Literal

from pydantic import BaseModel, Field


class MovieSuggestion(BaseModel):
    """A movie plus a score between zero and one."""

    movie_id: int = Field(gt=0)
    title: str = Field(min_length=1)
    score: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class MovieRecommendations(BaseModel):
    """A list of movies similar to a requested movie."""

    movie_id: int
    recommendations: list[MovieSuggestion]
    data_source: Literal["mock", "neo4j"] = "mock"


class UserRecommendations(BaseModel):
    """A list of recommended movies for a user."""

    user_id: int
    recommendations: list[MovieSuggestion]
    data_source: Literal["mock", "neo4j"] = "mock"


class TrendingMovies(BaseModel):
    """A list of popular movies."""

    movies: list[MovieSuggestion]
    data_source: Literal["mock", "neo4j"] = "mock"
