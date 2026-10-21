"""MovieLens recommendation baselines. No Docker/Neo4j required."""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

MIN_NEIGHBORS = 3

class MovieRecommender:
    """Train-rating-only collaborative recommender for development and testing."""

    def __init__(self, data_dir: str | Path):
        folder = Path(data_dir)
        self.movies = pd.read_csv(folder / "movies.csv")
        self.ratings = pd.read_csv(folder / "ratings.csv")
        self.ratings["rating"] = pd.to_numeric(self.ratings["rating"])
        self.movie_title = dict(zip(self.movies.movieId, self.movies.title))
        self.matrix = self.ratings.pivot_table(index="userId", columns="movieId", values="rating")

    def similar_movies(self, movie_id: int, limit: int = 5) -> list[dict]:
        """Rank movies by adjusted cosine of ratings from shared users."""
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        if movie_id not in self.matrix.columns:
            return []
        target = self.matrix[movie_id]
        rows = []
        for other in self.matrix.columns:
            if other == movie_id:
                continue
            overlap = target.notna() & self.matrix[other].notna()
            common = int(overlap.sum())
            if common < 3:
                continue
            a = target[overlap].to_numpy(dtype=float)
            b = self.matrix.loc[overlap, other].to_numpy(dtype=float)
            # Mean-centered ratings of the shared users; a zero-norm vector is skipped.
            a, b = a - a.mean(), b - b.mean()
            denom = np.linalg.norm(a) * np.linalg.norm(b)
            if denom == 0:
                continue
            similarity = float(np.dot(a, b) / denom)
            # Shrink tiny co-rating samples so incidental 3-user agreement is less dominant.
            score = similarity * (common / (common + 10))
            rows.append({"movie_id": int(other), "title": self.movie_title.get(other, str(other)),
                         "score": round(score, 4), "common_raters": common})
        return sorted(rows, key=lambda x: (-x["score"], -x["common_raters"]))[:limit]

    def trending(self, limit: int = 5) -> list[dict]:
        """Rating-count ranking with a minimum rating threshold."""
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        stats = self.ratings.groupby("movieId").rating.agg(["count", "mean"])
        stats = stats[stats["count"] >= 3].sort_values(["count", "mean"], ascending=False).head(limit)
        return [{"movie_id": int(i), "title": self.movie_title.get(i, str(i)),
                 "rating_count": int(row["count"]), "average_rating": round(float(row["mean"]), 2)}
                for i, row in stats.iterrows()]

    def user_recommendations(self, user_id: int, limit: int = 5) -> list[dict]:
        """Recommend unseen items scored positively by similar users."""
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        if user_id not in self.matrix.index:
            return []
        matrix = self.matrix.fillna(0.0)
        target = matrix.loc[[user_id]]
        similarities = cosine_similarity(target, matrix)[0]
        neighbor_scores = pd.Series(similarities, index=matrix.index).drop(user_id)
        neighbors = neighbor_scores[neighbor_scores > 0].nlargest(30)
        if neighbors.empty:
            return []
        unseen = self.matrix.loc[user_id].isna()
        ratings = self.matrix.loc[neighbors.index, unseen.index[unseen]]
        neighbor_counts = ratings.notna().sum(axis=0)
        weighted = ratings.mul(neighbors, axis=0)
        support = ratings.notna().mul(neighbors, axis=0).sum(axis=0)
        scores = (weighted.sum(axis=0) / support.replace(0, np.nan)).dropna()
        scores = scores[neighbor_counts.reindex(scores.index) >= MIN_NEIGHBORS]
        scores = scores.sort_values(ascending=False).head(limit)
        return [{"movie_id": int(i), "title": self.movie_title.get(i, str(i)),
                 "score": round(float(score), 4)} for i, score in scores.items()]
