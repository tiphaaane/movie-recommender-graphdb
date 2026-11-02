"""Top-N similar movies from the Python recommender for a fixed list of films.

The output is compared with GDS Node Similarity in docs/GDS_EVALUATION.md.
"""

import json
from pathlib import Path

from app.recommendations.service import MovieRecommender

DATA_DIR = "data/ml-latest-small"
OUTPUT = Path("docs/gds_eval/python_similar.json")
TOP_N = 10

# MovieLens movie IDs; titles are printed so the IDs can be double-checked.
FILMS = [1, 296, 356, 364, 2571, 260, 318, 2959, 480, 1270]


def _get(item, names, default=None):
    """Read a field from a dict or an object, trying several names."""
    for name in names:
        if isinstance(item, dict) and name in item:
            return item[name]
        if hasattr(item, name):
            return getattr(item, name)
    return default


def main() -> None:
    """Compute and save the top similar movies for each film."""
    model = MovieRecommender(DATA_DIR)
    results = {}
    for movie_id in FILMS:
        try:
            rows = model.similar_movies(movie_id, TOP_N)
        except KeyError:
            print(f"\n{movie_id}: unknown movie, skipped")
            continue
        results[str(movie_id)] = [
            {
                "movie_id": int(_get(row, ["movie_id", "movieId"])),
                "title": str(_get(row, ["title"], "")),
                "score": _get(row, ["score"]),
            }
            for row in rows
        ]
        print(f"\nSimilar to movie {movie_id}:")
        for rank, row in enumerate(results[str(movie_id)], start=1):
            print(f"  {rank:2d}. {row['title']} ({row['score']})")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()