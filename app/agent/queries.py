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
        WITH seed, m, count(DISTINCT g) AS shared_genres
        WITH seed, m, shared_genres, COUNT { (m)<-[:RATED]-(:User) } AS rating_count
        RETURN seed.movieId AS source_movie_id, seed.title AS source_title,
               m.movieId AS movie_id, m.title AS title, shared_genres, rating_count
        ORDER BY shared_genres DESC, rating_count DESC, movie_id
        LIMIT $limit
    """,
    # Title lookup happens inside Neo4j: the LLM never converts a title to an ID.
    # If several movies match (remakes), the most-rated one is used as the seed.
    "movies_like_title": """
        MATCH (seed:Movie)
        WHERE any(t IN $titles WHERE toLower(seed.title) = t
                  OR toLower(seed.title) STARTS WITH t + ' (')
        WITH seed, COUNT { (seed)<-[:RATED]-(:User) } AS seed_ratings
        ORDER BY seed_ratings DESC, seed.movieId
        LIMIT 1
        MATCH (seed)-[:IN_GENRE]->(g:Genre)<-[:IN_GENRE]-(m:Movie)
        WHERE m <> seed
        WITH seed, m, count(DISTINCT g) AS shared_genres
        WITH seed, m, shared_genres, COUNT { (m)<-[:RATED]-(:User) } AS rating_count
        RETURN seed.movieId AS source_movie_id, seed.title AS source_title,
               m.movieId AS movie_id, m.title AS title, shared_genres, rating_count
        ORDER BY shared_genres DESC, rating_count DESC, movie_id
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


ARTICLES = ("the", "a", "an")


def title_variants(title: str) -> list[str]:
    """Return lower-case spellings matching MovieLens titles such as 'Matrix, The (1999)'."""
    cleaned = " ".join(title.strip().lower().split())
    variants = [cleaned]
    first, _, rest = cleaned.partition(" ")
    if first in ARTICLES and rest:
        variants.append(f"{rest}, {first}")
    return variants


def build_query(plan: QueryPlan) -> QueryPreview:
    """Produce validated Cypher from a fixed template and bound parameters."""
    template = "movies_like_title" if plan.movie_title is not None else plan.intent
    cypher = TEMPLATES[template].strip()
    if DISALLOWED_WORDS.search(cypher):
        raise UnsafeQueryError("Query template failed safety validation")
    params: dict[str, Any] = {"limit": plan.limit}
    if plan.intent == "movies_by_genre":
        params["genre"] = plan.genre
    elif plan.intent == "movies_like" and plan.movie_title is not None:
        params["titles"] = title_variants(plan.movie_title)
    elif plan.intent == "movies_like":
        params["movie_id"] = plan.movie_id
    elif plan.intent == "user_favorites":
        params["user_id"] = plan.user_id
    # Validate all parameter placeholders are supplied without interpolation.
    placeholders = set(re.findall(r"\$([a-z_]+)", cypher))
    if placeholders != set(params):
        raise UnsafeQueryError("Unexpected query parameter")
    return QueryPreview(intent=plan.intent, cypher=cypher, parameters=params)


# Returns no row when either movie is missing, so the API can answer 404.
# shared_raters / (source_raters + recommended_raters - shared_raters) is the
# unweighted Jaccard index that GDS Node Similarity computes on the same graph.
EXPLAIN_RECOMMENDATION = """
    MATCH (a:Movie {movieId: $source_id}), (b:Movie {movieId: $recommended_id})
    OPTIONAL MATCH (a)-[:IN_GENRE]->(g:Genre)<-[:IN_GENRE]-(b)
    WITH a, b, collect(DISTINCT g.name) AS shared_genres
    RETURN a.title AS source_title, b.title AS recommended_title, shared_genres,
           COUNT { (a)<-[:RATED]-(:User) } AS source_raters,
           COUNT { (b)<-[:RATED]-(:User) } AS recommended_raters,
           COUNT { (a)<-[:RATED]-(:User)-[:RATED]->(b) } AS shared_raters
""".strip()
