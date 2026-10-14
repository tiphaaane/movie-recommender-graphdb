"""A small, auditable allow-list of parameterized Cypher graph queries."""

import re
from typing import Any

from app.agent.models import QueryPlan, QueryPreview


TEMPLATES = {
    "movies_by_genre": """
        MATCH (m:Movie)-[:IN_GENRE]->(g:Genre)
        WHERE toLower(g.name) = toLower($genre)
        OPTIONAL MATCH (:User)-[r:RATED]->(m)
        WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
        RETURN m.movieId AS movie_id, m.title AS title,
               rating_count, round(average_rating * 100) / 100 AS average_rating
        ORDER BY rating_count DESC, average_rating DESC, movie_id
        LIMIT $limit
    """,
    "movies_like": """
        MATCH (seed:Movie {movieId: $movie_id})-[:IN_GENRE]->(g:Genre)
              <-[:IN_GENRE]-(m:Movie)
        WHERE m.movieId <> $movie_id
        WITH m, count(DISTINCT g) AS shared_genres
        RETURN m.movieId AS movie_id, m.title AS title, shared_genres
        ORDER BY shared_genres DESC, movie_id
        LIMIT $limit
    """,
    "user_favorites": """
        MATCH (u:User {userId: $user_id})-[r:RATED]->(m:Movie)
        WHERE r.rating >= 4
        RETURN m.movieId AS movie_id, m.title AS title, r.rating AS rating
        ORDER BY rating DESC, movie_id
        LIMIT $limit
    """,
    "popular_movies": """
        MATCH (:User)-[r:RATED]->(m:Movie)
        WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
        RETURN m.movieId AS movie_id, m.title AS title,
               rating_count, round(average_rating * 100) / 100 AS average_rating
        ORDER BY rating_count DESC, average_rating DESC, movie_id
        LIMIT $limit
    """,
}

# A deliberately conservative, additional sanity check. The *primary* control
# is choosing only source-owned query templates and never evaluating LLM code.
DISALLOWED_WORDS = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|LOAD|CALL|"
    r"APOC|GRANT|DENY|REVOKE|ALTER|TERMINATE|FOREACH)\b",
    flags=re.IGNORECASE,
)


class UnsafeQueryError(ValueError):
    """The user or LLM attempted an operation outside the read-only scope."""


def check_question(question: str) -> None:
    """Fail closed on obvious mutation or administrative instructions."""
    if DISALLOWED_WORDS.search(question):
        raise UnsafeQueryError("The assistant only answers read-only movie questions")


def build_query(plan: QueryPlan) -> QueryPreview:
    """Produce validated Cypher from a fixed template and bound parameters."""
    cypher = TEMPLATES[plan.intent].strip()
    if DISALLOWED_WORDS.search(cypher):
        raise UnsafeQueryError("Query template failed safety validation")
    params: dict[str, Any] = {"limit": plan.limit}
    if plan.intent == "movies_by_genre":
        params["genre"] = plan.genre
    elif plan.intent == "movies_like":
        params["movie_id"] = plan.movie_id
    elif plan.intent == "user_favorites":
        params["user_id"] = plan.user_id
    # Validate all parameter placeholders are supplied without interpolation.
    placeholders = set(re.findall(r"\$([a-z_]+)", cypher))
    if placeholders != set(params):
        raise UnsafeQueryError("Unexpected query parameter")
    return QueryPreview(intent=plan.intent, cypher=cypher, parameters=params)


EXPLAIN_SHARED_GENRES = """
    MATCH (a:Movie {movieId: $source_id})-[:IN_GENRE]->(g:Genre)
          <-[:IN_GENRE]-(b:Movie {movieId: $recommended_id})
    RETURN g.name AS genre
    ORDER BY genre
    LIMIT 20
""".strip()
