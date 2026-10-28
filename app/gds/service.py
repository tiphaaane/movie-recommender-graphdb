"""Neo4j GDS projections and read-only graph algorithm queries.

The projections reproduce Alix's experiments on Juliette's MovieLens graph.
Projection names are specific to this API, so Alix's manual graphs are untouched.
"""

from threading import Lock
from typing import Any

from app.services.neo4j_service import get_driver

SIMILARITY_GRAPH = "apiMovieSimGraph"
PAGERANK_GRAPH = "apiMovieRankGraph"
_PROJECTION_LOCK = Lock()

_PROJECTIONS = {
    SIMILARITY_GRAPH: "REVERSE",      # Movie -> User: compare movies by shared raters
    PAGERANK_GRAPH: "UNDIRECTED",    # Both directions: centrality on user/movie graph
}


def _query(query: str, parameters: dict[str, Any], *, write: bool = False) -> list[dict[str, Any]]:
    """Execute a fixed, parameterized Cypher query in a managed transaction."""
    with get_driver().session() as session:
        executor = session.execute_write if write else session.execute_read
        return executor(lambda tx: [record.data() for record in tx.run(query, parameters)])


def _ensure_projection(graph_name: str) -> None:
    """Create our named GDS projection once, reusing it on later requests."""
    with _PROJECTION_LOCK:
        rows = _query(
            "CALL gds.graph.exists($graph_name) YIELD exists RETURN exists",
            {"graph_name": graph_name},
        )
        if rows and rows[0]["exists"]:
            return

        # The orientation is an internal allow-listed constant, not user input.
        orientation = _PROJECTIONS[graph_name]
        cypher = (
            "CALL gds.graph.project($graph_name, ['User', 'Movie'], "
            f"{{RATED: {{orientation: '{orientation}'}}}}) "
            "YIELD graphName RETURN graphName"
        )
        _query(cypher, {"graph_name": graph_name}, write=True)


def node_similarity(movie_id: int, limit: int) -> list[dict[str, Any]]:
    """Compute unweighted Jaccard similarities from overlapping movie raters."""
    _ensure_projection(SIMILARITY_GRAPH)
    return _query(
        """
        CALL gds.nodeSimilarity.stream($graph_name, {
            topK: $limit, similarityCutoff: 0.1
        })
        YIELD node1, node2, similarity
        WITH gds.util.asNode(node1) AS source_movie,
             gds.util.asNode(node2) AS other_movie, similarity
        WHERE source_movie:Movie AND other_movie:Movie
          AND source_movie.movieId = $movie_id
        RETURN other_movie.movieId AS movie_id,
               other_movie.title AS title,
               round(similarity, 4) AS score
        ORDER BY score DESC, movie_id ASC
        LIMIT $limit
        """,
        {"graph_name": SIMILARITY_GRAPH, "movie_id": movie_id, "limit": limit},
    )


def page_rank(limit: int) -> list[dict[str, Any]]:
    """Rank movie importance by PageRank on the unweighted rating graph."""
    _ensure_projection(PAGERANK_GRAPH)
    return _query(
        """
        CALL gds.pageRank.stream($graph_name)
        YIELD nodeId, score
        WITH gds.util.asNode(nodeId) AS movie, score
        WHERE movie:Movie
        RETURN movie.movieId AS movie_id,
               movie.title AS title,
               round(score, 4) AS score
        ORDER BY score DESC, movie_id ASC
        LIMIT $limit
        """,
        {"graph_name": PAGERANK_GRAPH, "limit": limit},
    )
