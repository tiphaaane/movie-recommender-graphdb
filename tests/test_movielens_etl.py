"""Unit tests for the CSV-to-graph transformation (no Neo4j server needed)."""

from pathlib import Path

import pytest

from scripts.movielens_io import batches, movie_rows, rating_rows, tag_rows


def write_data(folder: Path) -> None:
    """Create minimal MovieLens-format test CSV files."""
    (folder / "movies.csv").write_text(
        'movieId,title,genres\n1,Toy Story (1995),Adventure|Animation|Children\n'
        '2,Untitled,Comedy|Comedy\n3,Unknown,(no genres listed)\n', encoding="utf-8")
    (folder / "ratings.csv").write_text(
        'userId,movieId,rating,timestamp\n1,1,4.5,111\n2,2,3.0,222\n', encoding="utf-8")
    (folder / "tags.csv").write_text(
        'userId,movieId,tag,timestamp\n1,1,fun,333\n1,1,fun,333\n', encoding="utf-8")


def test_movie_parser_creates_genre_pairs(tmp_path: Path) -> None:
    """Duplicate genre values and missing genres are handled."""
    write_data(tmp_path)
    movies, links = movie_rows(tmp_path)
    assert movies[0] == {"movieId": 1, "title": "Toy Story (1995)", "year": 1995}
    assert len(links) == 4
    assert {x["genre"] for x in links if x["movieId"] == 2} == {"Comedy"}


def test_ratings_and_limit(tmp_path: Path) -> None:
    """Rating values are parsed and development subsets are supported."""
    write_data(tmp_path)
    assert rating_rows(tmp_path, limit=1)[0]["rating"] == 4.5
    assert len(rating_rows(tmp_path)) == 2


def test_tags_are_distinct_and_reproducible(tmp_path: Path) -> None:
    """Repeated identical source rows have distinct stable tag identifiers."""
    write_data(tmp_path)
    first = tag_rows(tmp_path)
    assert len(first) == 2
    assert first[0]["tagId"] != first[1]["tagId"]
    assert tag_rows(tmp_path) == first


def test_batches() -> None:
    """Chunks are split predictably to bound transaction size."""
    assert list(batches([{"n": i} for i in range(5)], 2)) == [
        [{"n": 0}, {"n": 1}], [{"n": 2}, {"n": 3}], [{"n": 4}]
    ]
    with pytest.raises(ValueError):
        list(batches([{}], 0))


def test_invalid_rating(tmp_path: Path) -> None:
    """Out-of-range source ratings are rejected explicitly."""
    write_data(tmp_path)
    (tmp_path / "ratings.csv").write_text(
        "userId,movieId,rating,timestamp\n1,1,8.0,111\n", encoding="utf-8")
    with pytest.raises(ValueError):
        rating_rows(tmp_path)


def test_missing_dataset_file(tmp_path: Path) -> None:
    """Data ingestion fails clearly when the dataset wasn't downloaded."""
    with pytest.raises(FileNotFoundError):
        movie_rows(tmp_path)
