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