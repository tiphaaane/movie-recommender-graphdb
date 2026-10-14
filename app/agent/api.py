"""FastAPI endpoints for safe natural-language graph questions and explanations."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agent.database import GraphUnavailableError, Neo4jReader
from app.agent.llm import OllamaPlanner, PlannerUnavailableError
from app.agent.models import AskRequest, AskResponse, ExplanationResponse, QueryPreview
from app.agent.queries import (
    EXPLAIN_SHARED_GENRES,
    UnsafeQueryError,
    build_query,
    check_question,
)

router = APIRouter(prefix="/api/agent", tags=["AI / Graph"])


def get_planner() -> OllamaPlanner:
    """Provide an injectable LLM adapter for API tests."""
    return OllamaPlanner()


def get_graph_reader() -> Neo4jReader:
    """Provide an injectable graph adapter for API tests."""
    return Neo4jReader()


def plan_question(question: str, planner: OllamaPlanner) -> QueryPreview:
    """Filter the input, validate the model response, and build allow-listed Cypher."""
    try:
        check_question(question)
        return build_query(planner.plan(question))
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PlannerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/preview", response_model=QueryPreview)
def preview_query(
    request: AskRequest,
    planner: OllamaPlanner = Depends(get_planner),
) -> QueryPreview:
    """Generate and validate Cypher without requiring any Neo4j database."""
    return plan_question(request.question, planner)


@router.post("/ask", response_model=AskResponse)
def ask_graph(
    request: AskRequest,
    planner: OllamaPlanner = Depends(get_planner),
    reader: Neo4jReader = Depends(get_graph_reader),
) -> AskResponse:
    """Turn user language into validated Cypher, then return graph-backed facts."""
    preview = plan_question(request.question, planner)
    try:
        rows = reader.run(preview.cypher, preview.parameters)
    except GraphUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    summary = f"Found {len(rows)} movie records in Neo4j." if rows else "No matching movies were found in Neo4j."
    return AskResponse(
        **preview.model_dump(),
        question=request.question,
        answer=summary,
        records=rows,
        evidence_count=len(rows),
    )


@router.get("/explain", response_model=ExplanationResponse)
def explain_recommendation(
    source_movie_id: int = Query(gt=0),
    recommended_movie_id: int = Query(gt=0),
    reader: Neo4jReader = Depends(get_graph_reader),
) -> ExplanationResponse:
    """Explain a genre-based recommendation using observed graph paths."""
    if source_movie_id == recommended_movie_id:
        raise HTTPException(status_code=422, detail="Use two different movie IDs")
    try:
        rows = reader.run(
            EXPLAIN_SHARED_GENRES,
            {"source_id": source_movie_id, "recommended_id": recommended_movie_id},
        )
    except GraphUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    genres = [str(row["genre"]) for row in rows]
    explanation = (
        f"These movies share {len(genres)} recorded genre(s): {', '.join(genres)}."
        if genres
        else "No shared genre connection was found in Neo4j; no genre-based explanation is supported."
    )
    return ExplanationResponse(
        source_movie_id=source_movie_id,
        recommended_movie_id=recommended_movie_id,
        shared_genres=genres,
        explanation=explanation,
    )
