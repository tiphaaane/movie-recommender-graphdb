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
    movie_title: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[\w .,:;'!?&()\-]+$")
    user_id: int | None = Field(default=None, gt=0)
    limit: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def validate_required_fields(self) -> "QueryPlan":
        """Reject incomplete and contradictory instructions from the LLM."""
        allowed = {
            "movies_by_genre": {"genre"},
            "movies_like": {"movie_id", "movie_title"},
            "user_favorites": {"user_id"},
            "popular_movies": set(),
        }[self.intent]
        provided = {field for field in ("genre", "movie_id", "movie_title", "user_id") if getattr(self, field) is not None}
        unsupported = provided - allowed
        if unsupported:
            raise ValueError(f"Field '{sorted(unsupported)[0]}' is not supported for '{self.intent}'")
        if allowed and len(provided) != 1:
            expected = " or ".join(sorted(allowed))
            raise ValueError(f"The intent '{self.intent}' requires exactly one of: {expected}")
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
    """Observed graph evidence linking two movies, never an AI hypothesis.

    Collaborative evidence (users who rated both movies) is what GDS Node
    Similarity measures. Shared genres are complementary context only.
    """

    source_movie_id: int
    source_title: str
    recommended_movie_id: int
    recommended_title: str
    shared_raters: int = Field(ge=0)
    source_raters: int = Field(ge=0)
    recommended_raters: int = Field(ge=0)
    jaccard_similarity: float = Field(ge=0, le=1)
    collaborative_explanation: str
    shared_genres: list[str]
    genre_context: str
    explanation: str
    note: str = (
        "Shared genres are descriptive context only: they do not explain collaborative "
        "or GDS Node Similarity scores, which depend only on users who rated both movies. "
        "The Python recommender uses rating-weighted cosine similarity, so its scores differ "
        "from this Jaccard value."
    )
    source: Literal["neo4j"] = "neo4j"
