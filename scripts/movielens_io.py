"""Read and validate the MovieLens Small CSV files using the standard library."""

import csv
import hashlib
import re
from pathlib import Path
from typing import Iterator

YEAR_PATTERN = re.compile(r"\((\d{4})\)$")


def read_csv(path: Path) -> Iterator[dict[str, str]]:
    """Read a MovieLens CSV file with correct UTF-8 decoding and CSV quoting."""
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Download and extract ml-latest-small first.")
    with path.open(newline="", encoding="utf-8-sig") as source:
        yield from csv.DictReader(source)


def movie_rows(folder: Path) -> tuple[list[dict], list[dict]]:
    """Return movies and distinct movie-to-genre connections."""
    movies, movie_genres = [], []
    for raw in read_csv(folder / "movies.csv"):
        movie_id = int(raw["movieId"])
        title = raw["title"].strip()
        match = YEAR_PATTERN.search(title)
        movies.append({
            "movieId": movie_id,
            "title": title,
            "year": int(match.group(1)) if match else None,
        })
        for genre in set(raw["genres"].split("|")):
            if genre and genre != "(no genres listed)":
                movie_genres.append({"movieId": movie_id, "genre": genre})
    return movies, movie_genres


def rating_rows(folder: Path, limit: int | None = None) -> list[dict]:
    """Return validated user ratings; limit is useful for an initial trial."""
    ratings = []
    for raw in read_csv(folder / "ratings.csv"):
        rating = float(raw["rating"])
        if not (0.5 <= rating <= 5 and (rating * 2).is_integer()):
            raise ValueError(f"Invalid MovieLens rating: {rating}")
        ratings.append({
            "userId": int(raw["userId"]),
            "movieId": int(raw["movieId"]),
            "rating": rating,
            "timestamp": int(raw["timestamp"]),
        })
        if limit is not None and len(ratings) >= limit:
            break
    return ratings


def tag_rows(folder: Path) -> list[dict]:
    """Return tags with stable row-based IDs to keep re-imports idempotent."""
    tags = []
    for row_number, raw in enumerate(read_csv(folder / "tags.csv"), start=1):
        text = raw["tag"].strip()
        if not text:
            continue
        key = f'{row_number}|{raw["userId"]}|{raw["movieId"]}|{text}|{raw["timestamp"]}'
        tags.append({
            "tagId": hashlib.sha256(key.encode("utf-8")).hexdigest(),
            "userId": int(raw["userId"]),
            "movieId": int(raw["movieId"]),
            "tag": text,
            "timestamp": int(raw["timestamp"]),
        })
    return tags


def batches(rows: list[dict], batch_size: int) -> Iterator[list[dict]]:
    """Split data into small pieces to avoid one very large graph transaction."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    for first in range(0, len(rows), batch_size):
        yield rows[first:first + batch_size]
