"""Leakage-aware baseline: classify positive observed ratings from train-only popularity features."""
from pathlib import Path
import argparse
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report


def run(data_dir: Path) -> None:
    ratings = pd.read_csv(data_dir / "ratings.csv")
    ratings = ratings.copy()
    ratings["liked"] = (ratings.rating >= 4).astype(int)
    train, test = train_test_split(ratings, test_size=0.2, random_state=42, stratify=ratings.liked)
    global_mean = float(train.rating.mean())
    u = train.groupby("userId").rating.agg(["mean", "count"])
    m = train.groupby("movieId").rating.agg(["mean", "count"])

    def features(frame: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=frame.index)
        out["user_mean"] = frame.userId.map(u["mean"]).fillna(global_mean)
        out["user_count"] = frame.userId.map(u["count"]).fillna(0)
        out["movie_mean"] = frame.movieId.map(m["mean"]).fillna(global_mean)
        out["movie_count"] = frame.movieId.map(m["count"]).fillna(0)
        return out

    model = LogisticRegression(max_iter=1000)
    model.fit(features(train), train.liked)
    pred = model.predict(features(test))
    prob = model.predict_proba(features(test))[:, 1]
    print("Accuracy:", round(accuracy_score(test.liked, pred), 4))
    print("ROC AUC:", round(roc_auc_score(test.liked, prob), 4))
    print(classification_report(test.liked, pred, zero_division=0))
    print("Only training ratings were used to compute user/movie aggregates.")
    print("This evaluates positive rating prediction among observed ratings, not unseen-watch likelihood.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/ml-latest-small")
    args = parser.parse_args()
    run(Path(args.data_dir))
