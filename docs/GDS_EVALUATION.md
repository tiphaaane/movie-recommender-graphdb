# GDS evaluation: Python recommender vs Neo4j Graph Data Science

## 1. Goal

Check that the GDS endpoints (`/api/gds/...`) are consistent with our original
Cypher queries, and compare three approaches on well-known movies.

| Method | What it measures |
|---|---|
| Python collaborative filtering | Similarity of the ratings given (mean-centered cosine, shrinkage) |
| GDS Node Similarity | Overlap of the users who rated each movie (Jaccard, ignores rating values) |
| GDS PageRank | Structural importance in the user-movie graph |

Data: MovieLens Small (9,742 movies, 610 users, 100,836 ratings) in Juliette's
Neo4j graph, GDS 2.13.14 Community.

## 2. Method

- 10 well-known movies: Toy Story, Pulp Fiction, Forrest Gump, The Lion King,
  The Matrix, Star Wars IV, The Shawshank Redemption, Fight Club, Jurassic Park,
  Back to the Future.
- For each movie, the top 10 similar movies from the Python recommender
  (`scripts/python_similar_films.py`) and from GDS Node Similarity
  (`topK: 10`, `similarityCutoff: 0.1`, `REVERSE` projection).
- PageRank (default parameters, `UNDIRECTED` projection): rank of each of the 10 movies.
- Comparison script: `scripts/compare_gds_python.py`. Raw files and the generated
  tables are in `docs/gds_eval/`.

## 3. Consistency with the original Cypher queries

The API (`app/gds/service.py`) uses the same projections (`REVERSE` for Node
Similarity, `UNDIRECTED` for PageRank), the same `similarityCutoff` (0.1) and the
default PageRank parameters. Three small differences: `topK` equals the requested
`limit`, scores are rounded to 4 decimals, and ties are ordered by `movieId`.

Our manual Cypher runs were reproducible: Toy Story gave the same ten movies and
scores in two separate runs. Endpoint check (run by Juliette on her Neo4j instance, GDS 2.13.14, API on
127.0.0.1:8000): `/api/gds/movies/1/similar?limit=10` returns exactly the same ten
movies, in the same order and with the same scores, as our Cypher run (Independence Day
0.4136, Jurassic Park 0.4112, Star Wars IV 0.4036, ..., Groundhog Day 0.3716).
`/api/gds/movies/important?limit=10` returns the same ten movies in the same order as
our Cypher PageRank query (Forrest Gump 11.1555, Shawshank Redemption 10.6075,
Pulp Fiction 10.3879, ..., Schindler's List 7.5232); the scores equal our raw scores
rounded to 4 decimals. The endpoints are therefore consistent with the original Cypher.

## 4. Results

Overlap between the two similarity methods (top 10 each, 10 movies):

| Figure | Value |
|---|---|
| Mean overlap | 0.4 movies out of 10 |
| Mean Jaccard between the two lists | 0.022 |
| Median number of ratings of recommended movies | Python 40, GDS 200 |
| Distinct movies recommended (100 slots) | Python 87, GDS 52 |

The only movies recommended by both methods: Star Wars V and VI for Star Wars IV,
Aladdin for The Lion King, Back to the Future Part II for Back to the Future.
Seven of the ten movies share nothing.

PageRank rank of each movie compared with its number of ratings:

| Movie | PageRank rank | Ratings |
|---|---:|---:|
| Forrest Gump | 1 | 329 |
| The Shawshank Redemption | 2 | 317 |
| Pulp Fiction | 3 | 307 |
| The Matrix | 4 | 278 |
| Star Wars IV | 6 | 251 |
| Jurassic Park | 7 | 238 |
| Fight Club | 9 | 218 |
| Toy Story | 11 | 215 |
| Back to the Future | 29 | 171 |
| The Lion King | 38 | 172 |

Examples (Toy Story): Python returns Toy Story 2, The Incredibles, Aladdin,
Finding Nemo; GDS returns Independence Day, Jurassic Park, Star Wars IV, Forrest Gump.

## 5. Interpretation

- **Node Similarity measures co-viewing.** Jaccard counts shared raters and ignores
  the rating values, so a movie rated 1 star counts like one rated 5. Very popular
  movies share raters with almost everything, so the same blockbusters come back for
  very different source movies (52 distinct movies in 100 slots, median 200 ratings).
- **The Python method measures taste.** Centering each user's ratings and shrinking
  small overlaps gives movies liked by the same people, even if fewer people saw them
  (median 40 ratings, 87 distinct movies). It finds the animation family for Toy Story.
- **GDS does well on franchises** (Star Wars, Back to the Future), where audiences overlap strongly.
- **PageRank is close to popularity.** On an unweighted graph, a movie is central when
  many active users rated it: the ranking follows the number of ratings almost exactly.
  It is useful for a trending or cold-start list, not for personalisation.

## 6. Rating classifier

Task: predict whether a rating is positive (>= 4) with logistic regression
(`scripts/train_rating_classifier.py`, train-only aggregates).

| Metric | Value |
|---|---|
| Test set | 20,168 ratings (10,452 negative, 9,716 positive) |
| Accuracy | 0.700 |
| ROC AUC | 0.768 |
| Precision / recall (positive class) | 0.68 / 0.70 |
| Majority-class baseline accuracy | 0.518 |

The model beats the majority-class baseline (always predict "not positive") by about
18 points of accuracy, and its ROC AUC of 0.77 is well above the 0.5 of a random
classifier. It is a solid baseline, not a strong predictor: it uses only simple user
and movie aggregates, computed on the training set only. It predicts the sentiment of
ratings that were actually given, not whether a user will watch or like an unseen movie.

## 7. Limitations

- Only 10 well-known movies, so the comparison is biased toward popular items and
  may differ for niche movies.
- We measure how the methods differ, not which one is better: there is no ground
  truth. A proper quality evaluation would hide part of each user's ratings and
  count how many hidden movies each method recovers (precision@k, recall@k).
- GDS Node Similarity and PageRank ignore the `rating` property. Projecting only
  `RATED` relationships with rating >= 4 would bring GDS closer to the Python method.
- MovieLens Small has only 610 users, so Python similarities built on few shared
  raters remain noisy even with shrinkage.
- GDS projections stay in memory and are not refreshed if the graph changes.
- Timings come from a single run on a laptop (projection 4.4 s, Node Similarity
  2.7 s, PageRank 0.4 s) and are indicative only. The Node Similarity endpoint
  recomputes the whole graph on every call.

## 8. Reproduce

    .venv/bin/python -m scripts.python_similar_films
    # run the GDS queries in docs/gds_queries.cypher, export the results to
    # docs/gds_eval/gds_node_similarity.csv and docs/gds_eval/gds_pagerank_rank.csv
    .venv/bin/python -m scripts.compare_gds_python
