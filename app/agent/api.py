"""FastAPI endpoints for safe natural-language graph questions and explanations."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agent.database import GraphUnavailableError, Neo4jReader
from app.agent.llm import InvalidPlanError, OllamaPlanner, PlannerUnavailableError
from app.agent.models import AskRequest, AskResponse, ExplanationResponse, QueryPreview
from app.agent.queries import (
    EXPLAIN_RECOMMENDATION,
    UngroundedPlanError,
    UnsafeQueryError,
    build_query,
    check_plan_grounded,
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
        plan = planner.plan(question)
        check_plan_grounded(question, plan)
        return build_query(plan)
    except (UnsafeQueryError, InvalidPlanError, UngroundedPlanError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PlannerUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def summarize(rows: list[dict]) -> str:
    """Describe only what Neo4j returned, naming the resolved seed movie if any."""
    if not rows:
        return "No matching movies were found in Neo4j."
    seed = rows[0].get("source_title")
    if seed:
        return f"Found {len(rows)} movies sharing genres with '{seed}' in Neo4j."
    return f"Found {len(rows)} movie records in Neo4j."


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
    return AskResponse(
        **preview.model_dump(),
        question=request.question,
        answer=summarize(rows),
        records=rows,
        evidence_count=len(rows),
    )


@router.get("/explain", response_model=ExplanationResponse)
def explain_recommendation(
    source_movie_id: int = Query(gt=0),
    recommended_movie_id: int = Query(gt=0),
    reader: Neo4jReader = Depends(get_graph_reader),
) -> ExplanationResponse:
    """Explain a recommendation with observed graph evidence only.

    The collaborative part (users who rated both movies, Jaccard index) is the
    measure behind GDS Node Similarity. Shared genres are reported separately
    as complementary context and are never presented as the cause of a score.
    """
    if source_movie_id == recommended_movie_id:
        raise HTTPException(status_code=422, detail="Use two different movie IDs")
    try:
        rows = reader.run(
            EXPLAIN_RECOMMENDATION,
            {"source_id": source_movie_id, "recommended_id": recommended_movie_id},
        )
    except GraphUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=404, detail="One or both movies were not found in Neo4j")
    return build_explanation(source_movie_id, recommended_movie_id, rows[0])


def build_explanation(source_id: int, recommended_id: int, row: dict) -> ExplanationResponse:
    """Turn raw graph counts into explanations that do not overstate causality."""
    shared = int(row["shared_raters"])
    source_raters = int(row["source_raters"])
    recommended_raters = int(row["recommended_raters"])
    union = source_raters + recommended_raters - shared
    jaccard = round(shared / union, 4) if union else 0.0
    source_title, recommended_title = str(row["source_title"]), str(row["recommended_title"])
    if shared:
        collaborative = (
            f"{shared} users rated both '{source_title}' ({source_raters} raters) and "
            f"'{recommended_title}' ({recommended_raters} raters). Jaccard similarity of their "
            f"audiences: {jaccard}. This is the measure used by GDS Node Similarity."
        )
    else:
        collaborative = "No user rated both movies, so there is no collaborative evidence linking them."
    genres = sorted(str(genre) for genre in row["shared_genres"])
    genre_context = (
        f"Complementary context: both movies are tagged {', '.join(genres)}."
        if genres
        else "Complementary context: the movies share no recorded genre."
    )
    return ExplanationResponse(
        source_movie_id=source_id,
        source_title=source_title,
        recommended_movie_id=recommended_id,
        recommended_title=recommended_title,
        shared_raters=shared,
        source_raters=source_raters,
        recommended_raters=recommended_raters,
        jaccard_similarity=jaccard,
        collaborative_explanation=collaborative,
        shared_genres=genres,
        genre_context=genre_context,
        explanation=f"{collaborative} {genre_context}",
    )
