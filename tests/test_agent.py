"""Tests for safety, structured planning, and API behavior without live services."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from app.agent.api import get_graph_reader, get_planner, router
from app.agent.models import QueryPlan
from app.agent.queries import UnsafeQueryError, build_query, check_question


class FakePlanner:
    """Return a deterministic plan for fully reproducible unit tests."""

    def plan(self, question: str) -> QueryPlan:
        """Honor only supported movie questions in these controlled tests."""
        del question
        return QueryPlan(intent="movies_like", movie_id=1, limit=3)


class FakeReader:
    """Return facts with the shape the real Cypher query would use."""

    def run(self, cypher: str, params: dict) -> list[dict]:
        """Emulate a minimal Neo4j response, while checking bound parameters."""
        assert "MATCH" in cypher
        if "recommended_id" in params:
            return [{"genre": "Adventure"}, {"genre": "Fantasy"}]
        assert params == {"movie_id": 1, "limit": 3}
        return [{"movie_id": 2, "title": "Jumanji (1995)", "shared_genres": 3}]


@pytest.fixture()
def client() -> TestClient:
    """Mount only Apolline's router to avoid depending on Tiphaine's code."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_planner] = FakePlanner
    app.dependency_overrides[get_graph_reader] = FakeReader
    with TestClient(app) as test_client:
        yield test_client


def test_parameterized_movie_query() -> None:
    """No user-controlled literal is inserted into the Cypher string."""
    preview = build_query(QueryPlan(intent="movies_like", movie_id=1, limit=3))
    assert "$movie_id" in preview.cypher
    assert preview.parameters == {"movie_id": 1, "limit": 3}
    assert preview.validated is True


def test_disallow_mutation_question() -> None:
    """Requests to delete graph data must be refused."""
    with pytest.raises(UnsafeQueryError):
        check_question("Delete all movie nodes from Neo4j")


def test_unknown_intent_rejected() -> None:
    """Reject fabricated intents from a hallucinating LLM."""
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({"intent": "delete_database", "limit": 3})


def test_invalid_large_limit_rejected() -> None:
    """Bound the size of user-visible query results."""
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({"intent": "popular_movies", "limit": 100000})


def test_missing_movie_id_rejected() -> None:
    """A similar-movie query needs an actual MovieLens identifier."""
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({"intent": "movies_like", "limit": 5})


def test_reject_extra_llm_field() -> None:
    """LLM outputs must not introduce executable code or unknown parameters."""
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({"intent": "popular_movies", "cypher": "MATCH (n) DETACH DELETE n"})


def test_query_preview(client: TestClient) -> None:
    """The first endpoint works before Neo4j data is available."""
    result = client.post("/api/agent/preview", json={"question": "Movies like movie 1?"})
    assert result.status_code == 200
    assert result.json()["parameters"] == {"movie_id": 1, "limit": 3}


def test_query_ask(client: TestClient) -> None:
    """A full answer includes Neo4j evidence and the actual query trace."""
    result = client.post("/api/agent/ask", json={"question": "Find movies like movie 1"})
    assert result.status_code == 200
    assert result.json()["source"] == "neo4j"
    assert result.json()["evidence_count"] == 1
    assert result.json()["records"][0]["movie_id"] == 2


def test_reject_delete_over_http(client: TestClient) -> None:
    """Reject a malicious request before the LLM or the graph is invoked."""
    result = client.post("/api/agent/ask", json={"question": "Delete everything in the graph"})
    assert result.status_code == 422
    assert "read-only" in result.json()["detail"]


def test_explain_with_real_edge_pattern(client: TestClient) -> None:
    """Genre explanations use rows that a shared-genre graph traversal returned."""
    result = client.get("/api/agent/explain?source_movie_id=1&recommended_movie_id=2")
    assert result.status_code == 200
    assert result.json()["shared_genres"] == ["Adventure", "Fantasy"]


def test_reject_same_movie_for_explanation(client: TestClient) -> None:
    """Do not manufacture a self-recommendation explanation."""
    result = client.get("/api/agent/explain?source_movie_id=1&recommended_movie_id=1")
    assert result.status_code == 422
