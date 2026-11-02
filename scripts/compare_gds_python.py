"""Compare the Python recommender with GDS Node Similarity and PageRank.

Inputs, all in docs/gds_eval/:
  python_similar.json      written by scripts/python_similar_films.py
  gds_node_similarity.csv  GDS Node Similarity top 10 for the same movies
  gds_pagerank_rank.csv    PageRank rank of the same movies
The number of ratings per movie comes from data/ml-latest-small/ratings.csv.

Output: docs/gds_eval/comparison.md (also printed).
"""

import json
from pathlib import Path
from statistics import mean, median

import pandas as pd

EVAL_DIR = Path("docs/gds_eval")
RATINGS = Path("data/ml-latest-small/ratings.csv")
OUTPUT = EVAL_DIR / "comparison.md"
TOP_N = 10


def load_inputs():
    """Load the comparison files and the number of ratings per movie."""
    python_lists = json.loads((EVAL_DIR / "python_similar.json").read_text(encoding="utf-8"))
    gds = pd.read_csv(EVAL_DIR / "gds_node_similarity.csv")
    pagerank = pd.read_csv(EVAL_DIR / "gds_pagerank_rank.csv")
    counts = pd.read_csv(RATINGS, usecols=["movieId"])["movieId"].value_counts()
    return python_lists, gds, pagerank, counts


def median_ratings(movie_ids, counts):
    """Median number of ratings of a list of movies."""
    if not movie_ids:
        return 0
    return median(int(counts.get(movie_id, 0)) for movie_id in movie_ids)


def compare_film(movie_id, python_lists, gds, counts):
    """Return the overlap statistics for one source movie."""
    py_rows = python_lists[str(movie_id)][:TOP_N]
    py_ids = [row["movie_id"] for row in py_rows]
    gds_rows = (
        gds[gds["movie_id"] == movie_id]
        .sort_values(["score", "similar_id"], ascending=[False, True])
        .head(TOP_N)
    )
    gds_ids = gds_rows["similar_id"].tolist()
    common = set(py_ids) & set(gds_ids)
    union = set(py_ids) | set(gds_ids)
    py_titles = {row["movie_id"]: row["title"] for row in py_rows}
    return {
        "movie_id": movie_id,
        "py_ids": py_ids,
        "gds_ids": gds_ids,
        "common": sorted(py_titles[i] for i in common),
        "overlap": len(common),
        "jaccard": len(common) / len(union) if union else 0.0,
        "py_median": median_ratings(py_ids, counts),
        "gds_median": median_ratings(gds_ids, counts),
    }


def film_table(results, names, ranks, counts):
    """Markdown table with one row per source movie."""
    lines = [
        "| Movie | Ratings | PageRank rank | Common (top 10) | Jaccard "
        "| Median ratings, Python recs | Median ratings, GDS recs |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for res in results:
        movie_id = res["movie_id"]
        lines.append(
            f"| {names.get(movie_id, movie_id)} | {int(counts.get(movie_id, 0))} "
            f"| {ranks.get(movie_id, '-')} | {res['overlap']} | {res['jaccard']:.3f} "
            f"| {res['py_median']:.0f} | {res['gds_median']:.0f} |"
        )
    return lines


def summary(results, counts):
    """Markdown bullet points with the global figures."""
    py_all = [i for res in results for i in res["py_ids"]]
    gds_all = [i for res in results for i in res["gds_ids"]]
    return [
        f"- Source movies compared: {len(results)} (top {TOP_N} each)",
        f"- Mean overlap: {mean(r['overlap'] for r in results):.2f} movies out of {TOP_N}",
        f"- Mean Jaccard between the two lists: {mean(r['jaccard'] for r in results):.3f}",
        f"- Median ratings of recommended movies: Python {median_ratings(py_all, counts):.0f}, "
        f"GDS {median_ratings(gds_all, counts):.0f}",
        f"- Distinct movies recommended: Python {len(set(py_all))}, GDS {len(set(gds_all))}",
    ]


def main() -> None:
    """Build the comparison and save it as markdown."""
    python_lists, gds, pagerank, counts = load_inputs()
    names = gds.drop_duplicates("movie_id").set_index("movie_id")["movie"].to_dict()
    ranks = pagerank.set_index("movie_id")["rank"].to_dict()
    results = [compare_film(int(mid), python_lists, gds, counts) for mid in python_lists]

    lines = ["# Python vs GDS: comparison output", "", "## Summary", ""]
    lines += summary(results, counts)
    lines += ["", "## Per movie", ""]
    lines += film_table(results, names, ranks, counts)
    lines += ["", "## Movies recommended by both methods", ""]
    for res in results:
        if res["common"]:
            lines.append(f"- {names.get(res['movie_id'], res['movie_id'])}: "
                         + "; ".join(res["common"]))

    text = "\n".join(lines) + "\n"
    OUTPUT.write_text(text, encoding="utf-8")
    print(text)
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    main()