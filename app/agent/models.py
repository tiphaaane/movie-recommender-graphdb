"""Strictly validated question, intent, and evidence response formats."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Intent = Literal["movies_by_genre", "movies_like", "user_favorites", "popular_movies"]


class AskRequest(BaseModel):
    """A user's natural-language question to the movie assistant."""

    question: str = Field(min_length=4, max_length=300)


class QueryPlan(BaseModel):
    """The only format accepted from the LLM, never arbitrary Cypher."""

    model_config = ConfigDict(extra="forbid")

    intent: Intent
    genre: str | None = Field(default=None, min_length=2, max_length=40, pattern=r"^[A-Za-z][A-Za-z0-9 -]*$")
    movie_id: int | None = Field(default=None, gt=0)
    user_id: int | None = Field(default=None, gt=0)
    limit: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_required_fields(self) -> "QueryPlan":
        """Reject incomplete and contradictory instructions from the LLM."""
        required = {
            "movies_by_genre": "genre",
            "movies_like": "movie_id",
            "user_favorites": "user_id",
        }
        relevant = required.get(self.intent)
        if relevant and getattr(self, relevant) is None:
            raise ValueError(f"The intent '{self.intent}' requires '{relevant}'")
        for field in ("genre", "movie_id", "user_id"):
            if field != relevant and getattr(self, field) is not None:
                raise ValueError(f"Field '{field}' is not supported for '{self.intent}'")
        return self


class QueryPreview(BaseModel):
    """The constrained query that will be submitted to Neo4j."""

    intent: Intent
    cypher: str
    parameters: dict[str, Any]
    validated: bool = True
    note: str = "Allow-listed read-only template; parameters are bound separately"


class AskResponse(QueryPreview):
    """A database-grounded answer with traceable evidence."""

    question: str
    answer: str
    records: list[dict[str, Any]]
    source: Literal["neo4j"] = "neo4j"
    evidence_count: int = Field(ge=0)


class ExplanationResponse(BaseModel):
    """Actual genre edges connecting two movies, not an AI hypothesis."""

    source_movie_id: int
    recommended_movie_id: int
    shared_genres: list[str]
    explanation: str
    source: Literal["neo4j"] = "neo4j"
