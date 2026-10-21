# Alix — recommendation algorithms and ML

## Scope
Local baseline using official MovieLens Small CSV: `data/ml-latest-small/movies.csv` and `ratings.csv`.
No Docker and no live Neo4j connection needed for the first milestone.

## Commands (from repository root, macOS)

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-recommendations.txt
./.venv/bin/python -m pytest tests/test_recommendations.py -q
./.venv/bin/python -m scripts.demo_recommendations
./.venv/bin/python -m scripts.train_rating_classifier
```

## Limitations and improvements
- Similarity: mean-centered cosine on at least three co-ratings, with shrinkage. Sparse co-ratings may yield no matches. A development baseline; not appropriate for big datasets without indexing.
- Personalized suggestions: positive-neighbor cosine with zeros representing unrated movies. Needs evaluation on holdout ratings, and implementation may be slow at scale.
- Trending: all-time rating counts, not true recent-trending signals.
- ML classifier: predicts positive ratings among observed interactions, not whether a user will choose to watch an unseen title. Train-only features prevent target leakage from per-item aggregates.
- The final project also needs two GDS algorithms; coordinate with Juliette once Neo4j is populated and GDS plugin configured, and implement GDS projections with recorded results and benchmarks.
- The FastAPI endpoint shapes must be agreed with Tiphaine before integration.


## Results (MovieLens Small)

### Popularity baseline (top 5 by number of ratings)
| Movie | Ratings | Average |
|---|---|---|
| Forrest Gump (1994) | 329 | 4.16 |
| Shawshank Redemption, The (1994) | 317 | 4.43 |
| Pulp Fiction (1994) | 307 | 4.20 |
| Silence of the Lambs, The (1991) | 279 | 4.16 |
| Matrix, The (1999) | 278 | 4.19 |

### Similar movies to Toy Story (movie 1)
| Movie | Score | Common raters |
|---|---|---|
| Toy Story 2 (1999) | 0.6224 | 81 |
| Incredibles, The (2004) | 0.5694 | 77 |
| Aladdin (1992) | 0.5596 | 107 |
| Finding Nemo (2003) | 0.5549 | 87 |
| Darjeeling Limited, The (2007) | 0.5068 | 14 |

The top results are family/animation films, which is plausible. The last result rests on only 14 common raters, so it is less reliable.

### Personalized recommendations for user 1
Detroit Rock City (1999), Angels and Insects (1995), Glengarry Glen Ross (1992),
Benji the Hunted (1987), Reform School Girls (1986). All have a predicted score of 5.0.

Limitation: scores are tied at the top of the scale and the films are obscure,
so they are probably supported by few similar users. Ranking could be improved
by requiring more supporting users or breaking ties by popularity.

### Rating classifier (logistic regression, positive = rating >= 4)
| Metric | Value |
|---|---|
| Test set size | 20,168 ratings |
| Majority-class baseline accuracy | about 0.52 |
| Accuracy | 0.6999 |
| Precision (positive class) | 0.68 |
| Recall (positive class) | 0.70 |
| F1 (positive class) | 0.69 |
| ROC AUC | 0.7678 |

Aggregates (user/movie averages) were computed on training data only.
The model predicts whether an observed rating is positive, not whether
someone will watch an unseen movie.

## Neo4j Graph Data Science (GDS) experiments

Queries: `docs/gds_queries.cypher`. Run on the shared Neo4j graph (Juliette's
local Docker instance, GDS 2.13.14 Community): 9,742 movies, 610 users,
100,836 `RATED` relationships.

### Projections

| Projection | Orientation | Nodes | Relationships | Time |
|---|---|---|---|---|
| `movieSimGraph` | `REVERSE` (Movie -> User) | 10,352 | 100,836 | 4,367 ms |
| `movieRankGraph` | `UNDIRECTED` | 10,352 | 201,672 | 175 ms |

### Node Similarity (similar movies to Toy Story, movieId 1)

`topK: 10`, `similarityCutoff: 0.1`. Run time: 2,689 ms.

| # | Similar movie | Similarity |
|---|---|---|
| 1 | Independence Day (1996) | 0.4136 |
| 2 | Jurassic Park (1993) | 0.4112 |
| 3 | Star Wars: Episode IV - A New Hope (1977) | 0.4036 |
| 4 | Forrest Gump (1994) | 0.3949 |
| 5 | Star Wars: Episode VI - Return of the Jedi (1983) | 0.3932 |
| 6 | Mission: Impossible (1996) | 0.3911 |
| 7 | Lion King, The (1994) | 0.3821 |
| 8 | Back to the Future (1985) | 0.3786 |
| 9 | Men in Black (1997) | 0.3718 |
| 10 | Groundhog Day (1993) | 0.3716 |

### PageRank (most central movies)

Run time: 437 ms.

| # | Movie | Score |
|---|---|---|
| 1 | Forrest Gump (1994) | 11.155 |
| 2 | Shawshank Redemption, The (1994) | 10.608 |
| 3 | Pulp Fiction (1994) | 10.388 |
| 4 | Matrix, The (1999) | 9.742 |
| 5 | Silence of the Lambs, The (1991) | 9.545 |
| 6 | Star Wars: Episode IV - A New Hope (1977) | 8.742 |
| 7 | Jurassic Park (1993) | 7.963 |
| 8 | Braveheart (1995) | 7.813 |
| 9 | Fight Club (1999) | 7.723 |
| 10 | Schindler's List (1993) | 7.523 |

### Comparison with the Python recommender

For Toy Story, the Python item-item similarity returns Toy Story 2, The
Incredibles, Aladdin and Finding Nemo. GDS Node Similarity returns popular
blockbusters (Independence Day, Jurassic Park, Star Wars).

The difference comes from the method. Node Similarity computes the Jaccard
index on the set of users who rated each movie: it measures co-viewing and
ignores the rating values, so very popular movies score high with almost
everything. The Python version uses mean-centered cosine similarity with
shrinkage, so it uses the actual ratings and penalises small overlaps, which
gives movies closer in taste (animation/family for Toy Story).

PageRank on the user-movie graph ranks movies by structural importance. It is
close to the popularity ranking (`trending`) because the graph is unweighted:
a movie is important when many (active) users rated it. It says nothing about
whether people liked the movie.

### Limitations

- Both GDS algorithms ignore the `rating` property. Using rating-weighted
  projections or filtering `RATED` relationships with `rating >= 4` would
  make the results closer to the Python recommender.
- Timings come from a single run on Juliette's laptop (Docker), so they are
  indicative only.
- GDS Community edition limits concurrency; this is not a problem at
  MovieLens Small size.