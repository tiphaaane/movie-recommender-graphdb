"""Read-only Neo4j access with short server-side query timeouts."""

import os
from typing import Any


class GraphUnavailableError(RuntimeError):
    """Graph database configuration or connectivity failed."""


class Neo4jReader:
    """Execute only query templates supplied by the application's allow-list."""

    def run(self, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Run the bounded query within a managed read transaction."""
        # Lazy dependency import lets API route previews work before Neo4j is installed.
        try:
            from dotenv import load_dotenv  # pylint: disable=import-outside-toplevel
            from neo4j import GraphDatabase, unit_of_work  # pylint: disable=import-outside-toplevel
        except ImportError as exc:
            raise GraphUnavailableError("Install requirements-agent.txt to query Neo4j") from exc

        load_dotenv()
        password = os.getenv("NEO4J_PASSWORD", "")
        if not password:
            raise GraphUnavailableError("Missing NEO4J_PASSWORD in .env")
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")

        @unit_of_work(timeout=5)
        def read_rows(tx):
            """Execute one fixed read query and materialize at most 20 records."""
            return [record.data() for record in tx.run(cypher, parameters=params).fetch(20)]

        try:
            with GraphDatabase.driver(uri, auth=(user, password), connection_timeout=5) as driver:
                with driver.session(database="neo4j") as session:
                    return session.execute_read(read_rows)
        except Exception as exc:
            # Neo4j driver exceptions vary between auth, connectivity and Cypher failure.
            raise GraphUnavailableError("Neo4j query failed. Check the database, schema and logs") from exc
