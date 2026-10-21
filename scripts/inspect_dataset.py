"""Quick data inspection before importing MovieLens Small."""

import argparse
from pathlib import Path

from scripts.movielens_io import movie_rows, rating_rows, tag_rows


def main() -> None:
    """Print source sizes and sample records."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/ml-latest-small"))
    folder = parser.parse_args().data_dir
    movies, genres = movie_rows(folder)
    ratings = rating_rows(folder)
    tags = tag_rows(folder)
    print(f"Movies: {len(movies)} | Movie-genre pairs: {len(genres)}")
    print(f"Ratings: {len(ratings)} | Tags: {len(tags)}")
    print(f"Distinct users with ratings: {len({row['userId'] for row in ratings})}")
    print(f"Distinct genres: {len({row['genre'] for row in genres})}")
    print("First movie:", movies[0] if movies else "none")
    print("First rating:", ratings[0] if ratings else "none")


if __name__ == "__main__":
    main()
