# Cypher benchmark results: optimized_2026_11_02

- Date (UTC): 2026-11-02 18:12
- Neo4j: Neo4j Kernel 5.26.32 (community)
- Graph: 9742 movies, 100836 ratings
- Timed runs per query: 20 (after 3 warm-up runs)
- Machine: Windows-11-10.0.26300-SP0, Python 3.12.6
- Times are wall-clock in ms, client side, all records fetched.

| Query | Source | Rows | DB hits | Median ms | Min ms | Max ms | Index used | Label scan |
|---|---|---|---|---|---|---|---|---|
| api_trending | app/services/neo4j_recommendations.py | 10 | 309191 | 187.33 | 131.51 | 292.89 | no | yes |
| variant_trending_precomputed | variant for comparison (not used by the app) | 10 | 44 | 13.83 | 11.84 | 37.11 | yes | no |

## api_trending

Source: app/services/neo4j_recommendations.py

Purpose: Most rated movies (aggregation over all ratings)

```cypher
MATCH (m:Movie)<-[r:RATED]-(:User)
WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
WHERE rating_count >= 3
RETURN m.movieId AS movie_id, m.title AS title,
       rating_count, round(average_rating, 2) AS average_rating
ORDER BY rating_count DESC, average_rating DESC, movie_id ASC
LIMIT $limit
```

Parameters: `{'limit': 10}`

Plan operators: ProduceResults -> Projection -> Top -> Filter -> EagerAggregation -> Expand(All) -> NodeByLabelScan

## variant_trending_precomputed

Source: variant for comparison (not used by the app)

Purpose: Same ranking as api_trending, read from precomputed Movie properties

```cypher
MATCH (m:Movie)
WHERE m.ratingCount >= 3
RETURN m.movieId AS movie_id, m.title AS title,
       m.ratingCount AS rating_count, round(m.averageRating, 2) AS average_rating
ORDER BY rating_count DESC, average_rating DESC, movie_id ASC
LIMIT $limit
```

Parameters: `{'limit': 10}`

Plan operators: ProduceResults -> Projection -> PartialTop -> CacheProperties -> NodeIndexSeekByRange
