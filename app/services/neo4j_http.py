"""Shared Neo4j error handling for FastAPI endpoints."""

from typing import Any, Callable

from fastapi import HTTPException
from neo4j.exceptions import AuthError, Neo4jError, ServiceUnavailable, SessionExpired


def graph_call(handler: Callable[..., Any], *args: Any) -> Any:
    """Convert Neo4j failures into HTTP errors without exposing credentials."""
    try:
        return handler(*args)
    except (AuthError, ServiceUnavailable, SessionExpired, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="Neo4j service is unavailable") from exc
    except Neo4jError as exc:
        raise HTTPException(status_code=502, detail="Neo4j query failed") from exc
