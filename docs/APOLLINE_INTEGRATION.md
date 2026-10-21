# Apolline — Integration notes for the team

## Files Apolline owns
- `app/agent/models.py`: validated LLM output and responses
- `app/agent/queries.py`: allow-listed, bounded, parameterized Cypher
- `app/agent/llm.py`: Ollama JSON-mode adapter
- `app/agent/database.py`: managed read transaction to Neo4j
- `app/agent/api.py`: router with `/api/agent/preview`, `/api/agent/ask`, `/api/agent/explain`
- `tests/test_agent.py`: guardrail and endpoint tests

## Register endpoints in Tiphaine's `app/main.py`
1. Under other imports, add: `from app.agent.api import router as agent_router`
2. At the very bottom, add: `app.include_router(agent_router)`
Do not replace `app/main.py` or overwrite Tiphaine's existing endpoint functions.

## Local requirements
`python -m pip install -r requirements-agent.txt`
Start Ollama locally and pull `qwen2.5:3b`. If the local machine is weak, use `qwen2.5:1.5b` and set `OLLAMA_MODEL=qwen2.5:1.5b` in `.env`.
`OLLAMA_URL=http://localhost:11434` for native Windows Python execution.
`NEO4J_URI=bolt://localhost:7687`, `NEO4J_USER=neo4j`, `NEO4J_PASSWORD=...` locally.

## Integration with Camille
Camille's Dockerfile installs `requirements.txt` only. Before Docker deployment, add `neo4j` and `python-dotenv` requirements to the shared `requirements.txt` (or modify Dockerfile to install requirements-agent.txt), and set `OLLAMA_URL` for the container's reachable Ollama service. When Ollama runs on the host, container networking may require additional local configuration; the most reproducible final setup is a fourth Compose service for Ollama, configured with a model pull/setup procedure and adequate resources.

## Integration with Alix
The templates target these exact graph labels/properties:
- `(:Movie {movieId, title})`
- `(:User {userId})`
- `(:Genre {name})`
- `(:User)-[:RATED {rating}]->(:Movie)`
- `(:Movie)-[:IN_GENRE]->(:Genre)`
The query response uses `movie_id`, `title` and query-specific facts. Do not pretend results are real until the graph has been populated.

## Limitations and reliability design
- This is **constrained natural-language-to-Cypher**: the LLM selects a structured intent/parameters; Python generates query text from fixed allow-listed templates. It does not accept arbitrary LLM-written Cypher.
- A read transaction alone is *not* an authorization boundary; template allowlisting is the primary restriction. For a stronger production deployment, create a least-privileged Neo4j user (READ-only role) and use separate credentials for the app.
- The LLM can still choose the wrong intent or an ID the user did not intend. Tests and a small manually labeled question set should be used to evaluate accuracy.
- No LLM-generated free-text explanations are trusted as facts; responses return graph paths/records.
- A `source='neo4j'` response indicates that the rows came from a database query, **not** that the underlying movie ratings are independently verified.
- The `movies_like` intent is genre-overlap search, **not** Juliette's final personalized similarity algorithm.
- Genre-based explanations are valid only for a genre-overlap recommendation, not for arbitrary ML prediction.

## Required demo
Successful: `POST /api/agent/ask` with `{"question":"Find movies like movie 1"}` after importing MovieLens (or loading a small demo graph).
Blocked: `POST /api/agent/ask` with `{"question":"Delete all movies"}` should return HTTP 422, with no DB mutation.
Preview: `/api/agent/preview` works when Ollama is running even without Neo4j data.

## Performance and defense
For a demonstration, time the questions and run `EXPLAIN`/`PROFILE` in Neo4j Browser on the selected Cypher. Discuss `LIMIT`, indexes on `Movie.movieId` and `User.userId`, and cardinality when traversing popular genres.
