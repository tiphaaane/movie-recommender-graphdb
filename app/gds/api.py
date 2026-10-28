"""HTTP endpoints exposing the team's Neo4j Graph Data Science algorithms."""

from typing import Annotated, Any, Callable, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable, SessionExpired
from pydantic import BaseModel, Field

from app.gds import service
from app.services import neo4j_recommendations

router = APIRouter(prefix="/api/gds", tags=["Graph Data Science"])

MovieId = Annotated[int, Path(gt=0, description="MovieLens movie ID")]
Limit = Annotated[int, Query(ge=1, le=20, description="Number of results (1-20)")]


class GDSMovie(BaseModel):
    """Movie with a raw score produced by a named GDS algorithm."""

    movie_id: int = Field(gt=0)
    title: str = Field(min_length=1)
    score: float = Field(ge=0)


class SimilarMoviesGDS(BaseModel):
    """Movie matches based on Jaccard similarity of shared raters."""

    source_movie_id: int
    algorithm: Literal["node_similarity"] = "node_similarity"
    data_source: Literal["neo4j_gds"] = "neo4j_gds"
    movies: list[GDSMovie]


class ImportantMoviesGDS(BaseModel):
    """Movies ranked by PageRank centrality (raw, not normalized scores)."""

    algorithm: Literal["pagerank"] = "pagerank"
    data_source: Literal["neo4j_gds"] = "neo4j_gds"
    movies: list[GDSMovie]


def _db_call(handler: Callable[..., Any], *args: Any) -> Any:
    """Return stable HTTP errors without exposing connection details or secrets."""
    try:
        return handler(*args)
    except (AuthError, ServiceUnavailable, SessionExpired, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="Neo4j service is unavailable") from exc
    except Neo4jError as exc:
        raise HTTPException(status_code=502, detail="Neo4j GDS query failed") from exc


@router.get("/movies/{movie_id}/similar", response_model=SimilarMoviesGDS)
def similar_movies_gds(movie_id: MovieId, limit: Limit = 5) -> SimilarMoviesGDS:
    """Find movies with an overlapping audience using GDS Node Similarity."""
    if not _db_call(neo4j_recommendations.movie_exists, movie_id):
        raise HTTPException(status_code=404, detail="Movie not found")
    rows = _db_call(service.node_similarity, movie_id, limit)
    return SimilarMoviesGDS(source_movie_id=movie_id, movies=[GDSMovie(**row) for row in rows])


@router.get("/movies/important", response_model=ImportantMoviesGDS)
def important_movies_gds(limit: Limit = 5) -> ImportantMoviesGDS:
    """Return the most structurally important movies using GDS PageRank."""
    rows = _db_call(service.page_rank, limit)
    return ImportantMoviesGDS(movies=[GDSMovie(**row) for row in rows])
