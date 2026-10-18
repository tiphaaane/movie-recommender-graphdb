"""Neo4j connection and query helpers."""

import os
from functools import lru_cache
from typing import Any

from neo4j import Driver, GraphDatabase


@lru_cache(maxsize=1)
def get_driver() -> Driver:
    """Create and cache the Neo4j driver."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise RuntimeError("The NEO4J_PASSWORD environment variable is not set.")

    return GraphDatabase.driver(
        uri,
        auth=(username, password),
    )


def verify_connection() -> bool:
    """Verify that Neo4j is reachable and credentials are valid."""
    get_driver().verify_connectivity()
    return True


def run_query(
    query: str,
    parameters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute a read query and return its records as dictionaries."""
    with get_driver().session() as session:
        result = session.run(query, parameters or {})
        return [record.data() for record in result]


def close_driver() -> None:
    """Close the driver and clear the cached instance."""
    if get_driver.cache_info().currsize:  # pylint: disable=too-many-function-args
        get_driver().close()
        get_driver.cache_clear()