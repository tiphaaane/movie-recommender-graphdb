"""Temporary deterministic data, replaced later by real graph services.

All similarity scores and recommendations here are invented for API testing.
Do not present them as results from MovieLens or a trained model.
"""

from app.schemas import MovieSuggestion

MOVIES = {
    1: "Toy Story (1995)",
    2: "Jumanji (1995)",
    3: "Grumpier Old Men (1995)",
    5: "Father of the Bride Part II (1995)",
}

SIMILARITY = {
    1: [(2, 0.85), (5, 0.67)],
    2: [(1, 0.85), (3, 0.54)],
    3: [(5, 0.79), (2, 0.54)],
    5: [(3, 0.79), (1, 0.67)],
}

USER_RECOMMENDATIONS = {
    1: [(1, 0.92), (2, 0.83), (5, 0.75)],
    2: [(3, 0.90), (5, 0.84), (1, 0.65)],
}

USER_DISCOVERY = {
    1: [(3, 0.81), (5, 0.70)],
    2: [(2, 0.82), (1, 0.72)],
}

TRENDING = [(1, 0.95), (2, 0.86), (3, 0.75), (5, 0.62)]


def suggestions(pairs: list[tuple[int, float]], limit: int) -> list[MovieSuggestion]:
    """Convert a mock movie ranking to validated API results."""
    return [
        MovieSuggestion(
            movie_id=movie_id,
            title=MOVIES[movie_id],
            score=score,
            reason="Illustrative mock score, not a real recommendation",
        )
        for movie_id, score in pairs[:limit]
    ]
