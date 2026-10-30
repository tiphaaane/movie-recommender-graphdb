# Cypher query benchmarks (Juliette)

Goal: measure the real cost of the Cypher queries used by the application, check which
ones use the indexes, find the expensive operations, and test improvements without
inventing gains.

## 1. Method

- Environment of the published measurements: Neo4j 5.26 Community in Docker on a MacBook Air (Apple M1). GDS is not needed for these benchmarks.
- Data: MovieLens Small (9,742 movies, 610 users, 100,836 ratings), imported with `scripts/import_movielens.py`.
- Queries: copied from `app/services/neo4j_recommendations.py` (API) and `app/agent/queries.py` (AI assistant), plus clearly labelled variants used only for comparison.
- Parameters: movie 1 (Toy Story), user 1, genre Comedy, limit 10.
- Measurement (`scripts/benchmark_queries.py`):
  - `PROFILE` once per query to read the plan operators and the total database hits;
  - 3 warm-up runs, then 20 timed runs; median, min and max wall-clock time on the client side (Python driver, all records fetched).
- Database hits are deterministic and are the main metric. Times are indicative only (see Limitations).

Reproduce from a fresh database, from the repository root, with the standard project setup:

```bash
# 1. Start the project's Neo4j service and import MovieLens (data in data/ml-latest-small/)
docker compose up -d neo4j
python -m scripts.import_movielens
python -m scripts.verify_graph

# 2. Baseline: the current application queries
#    (the optimized variant is skipped because its properties do not exist yet)
python -m scripts.benchmark_queries --label before

# 3. Apply the tested optimization (section 4), then measure again
python -m scripts.setup_rating_stats
python -m scripts.benchmark_queries --label after

# Optional: remove the optimization to return to the baseline graph
python -m scripts.setup_rating_stats --drop
```

`--label` only names the report. The optimization is created by
`scripts/setup_rating_stats.py`, which is idempotent and checks that the optimized query
returns exactly the same rows as the current API query before the "after" run.

Raw reports: `docs/benchmarks/results_before.md` and `docs/benchmarks/results_after.md`.

## 2. Results (baseline)

| Query | Source | DB hits | Median (ms) |
|---|---|---|---|
| api_movie_exists | API | 2 | 2.13 |
| api_user_exists | API | 2 | 2.08 |
| api_trending | API | 309,191 | 31.94 |
| api_similar_movies | API | 196,394 | 35.30 |
| api_user_recommendations | API | 1,260,318 | 130.21 |
| api_discover | API | 1,406,800 | 140.62 |
| agent_movies_by_genre | AI assistant | 137,782 | 22.16 |
| agent_movies_like | AI assistant | 26,314 | 7.36 |
| agent_user_favorites | AI assistant | 878 | 2.68 |
| agent_popular_movies | AI assistant | 304,222 | 32.02 |
| agent_explain_shared_genres | AI assistant | 30 | 2.26 |

## 3. Analysis

### Already optimal

`api_movie_exists`, `api_user_exists`, `agent_user_favorites` and `agent_explain_shared_genres`
start from a node found through the unique constraints on `Movie.movieId` or `User.userId`
(index seek), then read only a few relationships. With 2 to 878 database hits and about
2 to 3 ms, they are at the cost of a single driver round trip: no change is needed.

### Aggregations over all ratings

`api_trending` and `agent_popular_movies` read all 100,836 `RATED` relationships at every
call to count and average them (about 305,000 database hits, about 32 ms). No index can help
here, because the work is the aggregation itself. This is the best optimization target
(section 4).

### Collaborative traversals

`api_similar_movies` (196,394 hits) goes from Toy Story to every user who rated it, then to
every movie those users rated. `api_user_recommendations` and `api_discover`
(1.26 and 1.41 million hits, 130 to 141 ms) compare user 1 with every user who rated the same
movies before keeping the 30 closest. These are the most expensive queries of the application.
Their cost comes from the number of paths, not from a missing index.

## 4. Optimization tested: precomputed rating statistics

Idea: store `ratingCount` and `averageRating` on each `Movie` once, and index `ratingCount`,
instead of recomputing them from all ratings at every request (denormalization).

The setup is scripted in `scripts/setup_rating_stats.py` (`--drop` removes it). It runs:

```cypher
MATCH (m:Movie)
OPTIONAL MATCH (m)<-[r:RATED]-(:User)
WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
SET m.ratingCount = rating_count, m.averageRating = average_rating;

CREATE INDEX movie_rating_count_index IF NOT EXISTS FOR (m:Movie) ON (m.ratingCount);
```

Same run (`results_after.md`):

| Query | DB hits | Median (ms) |
|---|---|---|
| api_trending (current) | 309,191 | 37.64 |
| variant_trending_precomputed | 44 | 2.51 |

- Database hits divided by about 7,000; median time divided by about 15.
- Correctness: both queries return the same rows in the same order with the same values. This is checked automatically by `scripts/setup_rating_stats.py` (first 50 rows) and shown in `docs/screenshots/trending_current.png` and `trending_precomputed.png`.
- Trade-off: the two properties must be recomputed when ratings change. MovieLens Small is static here, so recomputing them at import time is enough.
- Status: proposal. Adopting it in production needs the precomputation in the import pipeline and a query change in the API (`trending`) and the AI templates (`popular_movies`), to be agreed with Tiphaine and Apolline.

## 5. Variant tested without gain: exact genre name

`agent_movies_by_genre` uses `toLower(g.name) = toLower($genre)`, which cannot use the unique
index on `Genre.name`. The variant with an exact name (`{name: $genre}`) can use it, but the
measurement shows no gain: 137,782 database hits for the current query and 141,490 for the
variant, with similar times. There are only 19 genres, so finding the genre is negligible;
the cost comes from reading the ratings of the movies in the genre. We keep `toLower`, which is
more tolerant for the AI assistant.

## 6. Next candidate (not measured yet)

For the collaborative queries, the similar users or similar movies could be precomputed with
GDS Node Similarity (Alix's work) and written as relationships, so that the API reads a few
relationships instead of exploring all co-ratings. This must be measured before any gain is
claimed.

## 7. Index usage evidence

`SHOW INDEXES` after the import showed 601,216 reads of `movie_id_unique` and 110,288 reads of
`genre_name_unique`: the constraint indexes are used by every `MERGE` and `MATCH` on these keys.
`movie_title_index` and `movie_year_index` are almost never read by the current application;
they were created for future browsing and no speed-up is claimed for them.

## 8. Limitations

- Times vary between runs on the same laptop: `api_similar_movies` measured 35.30 ms in one run and 50.75 ms in the next, with identical database hits. Conclusions rely on database hits.
- One parameter set per query (movie 1, user 1). Users or movies with more ratings cost more.
- Warm cache, single client, no concurrent load.
- Client-side times include the driver round trip (about 2 ms floor).
- Reproduced on a fresh database with docker compose (image neo4j:5): database hits identical for all queries except api_user_recommendations and api_discover (1,617 fewer each, about 0.1%), possibly because of a different Neo4j version; conclusions unchanged.
- On a fresh database, benchmark_queries.py prints an UnknownPropertyKeyWarning for ratingCount: this is expected, the property is created by setup_rating_stats.py.
