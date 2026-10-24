"""Read-only, parameterized Neo4j recommendation queries for MovieLens."""

from typing import Any

from app.services.neo4j_service import get_driver


def read_cypher(query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute a fixed Cypher query in a read transaction."""
    with get_driver().session() as session:
        return session.execute_read(
            lambda tx: [record.data() for record in tx.run(query, parameters)]
        )


def movie_exists(movie_id: int) -> bool:
    """Return whether a MovieLens movie ID is present in the graph."""
    rows = read_cypher(
        "MATCH (m:Movie {movieId: $movie_id}) RETURN m.movieId AS movie_id LIMIT 1",
        {"movie_id": movie_id},
    )
    return bool(rows)


def user_exists(user_id: int) -> bool:
    """Return whether a MovieLens user ID is present in the graph."""
    rows = read_cypher(
        "MATCH (u:User {userId: $user_id}) RETURN u.userId AS user_id LIMIT 1",
        {"user_id": user_id},
    )
    return bool(rows)


def trending(limit: int) -> list[dict[str, Any]]:
    """Rank movies by all-time number of ratings, not recent activity."""
    return read_cypher(
        """
        MATCH (m:Movie)<-[r:RATED]-(:User)
        WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
        WHERE rating_count >= 3
        RETURN m.movieId AS movie_id, m.title AS title,
               rating_count, round(average_rating, 2) AS average_rating
        ORDER BY rating_count DESC, average_rating DESC, movie_id ASC
        LIMIT $limit
        """,
        {"limit": limit},
    )


def similar_movies(movie_id: int, limit: int) -> list[dict[str, Any]]:
    """Find co-rated movies with strong rating agreement and support shrinkage."""
    return read_cypher(
        """
        MATCH (target:Movie {movieId: $movie_id})<-[r1:RATED]-(u:User)-[r2:RATED]->(other:Movie)
        WHERE other <> target
        WITH other, count(DISTINCT u) AS common_raters,
             avg(1.0 - abs(r1.rating - r2.rating) / 4.5) AS agreement
        WHERE common_raters >= 3
        RETURN other.movieId AS movie_id, other.title AS title,
               round(agreement * (toFloat(common_raters) / (common_raters + 10.0)), 4) AS score,
               common_raters
        ORDER BY score DESC, common_raters DESC, movie_id ASC
        LIMIT $limit
        """,
        {"movie_id": movie_id, "limit": limit},
    )


_CANDIDATES = """
MATCH (u:User {userId: $user_id})-[:RATED]->(seen:Movie)<-[:RATED]-(neighbor:User)
WHERE neighbor <> u
WITH u, neighbor, count(DISTINCT seen) AS shared_movies
WHERE shared_movies >= 3
ORDER BY shared_movies DESC, neighbor.userId ASC
LIMIT 30
MATCH (neighbor)-[r:RATED]->(candidate:Movie)
WHERE NOT EXISTS { MATCH (u)-[:RATED]->(candidate) }
WITH candidate, count(DISTINCT neighbor) AS support,
     sum(shared_movies * r.rating) / toFloat(sum(shared_movies)) AS predicted_rating
WHERE support >= 3
"""


def user_recommendations(user_id: int, limit: int) -> list[dict[str, Any]]:
    """Predict ratings for unseen movies using similar users in the graph."""
    return read_cypher(
        _CANDIDATES + """
        RETURN candidate.movieId AS movie_id, candidate.title AS title,
               round(predicted_rating, 4) AS score, support
        ORDER BY score DESC, support DESC, movie_id ASC
        LIMIT $limit
        """,
        {"user_id": user_id, "limit": limit},
    )


def discover(user_id: int, limit: int) -> list[dict[str, Any]]:
    """Prioritize lesser-rated movies within credible personalized candidates."""
    return read_cypher(
        _CANDIDATES + """
        MATCH (candidate)<-[all_rating:RATED]-(:User)
        WITH candidate, support, predicted_rating, count(all_rating) AS rating_count
        RETURN candidate.movieId AS movie_id, candidate.title AS title,
               round(predicted_rating, 4) AS score, support, rating_count
        ORDER BY rating_count ASC, score DESC, movie_id ASC
        LIMIT $limit
        """,
        {"user_id": user_id, "limit": limit},
    )
