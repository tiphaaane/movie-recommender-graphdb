# Cypher benchmark results: after

- Date (UTC): 2026-10-30 14:33
- Neo4j: Neo4j Kernel 5.26.32 (community)
- Graph: 9742 movies, 100836 ratings
- Timed runs per query: 20 (after 3 warm-up runs)
- Machine: macOS-15.0-arm64-arm-64bit, Python 3.12.6
- Times are wall-clock in ms, client side, all records fetched.

| Query | Source | Rows | DB hits | Median ms | Min ms | Max ms | Index used | Label scan |
|---|---|---|---|---|---|---|---|---|
| api_movie_exists | app/services/neo4j_recommendations.py | 1 | 2 | 1.94 | 1.42 | 4.37 | yes | no |
| api_user_exists | app/services/neo4j_recommendations.py | 1 | 2 | 1.64 | 1.28 | 3.70 | yes | no |
| api_trending | app/services/neo4j_recommendations.py | 10 | 309191 | 37.64 | 31.45 | 70.73 | no | yes |
| api_similar_movies | app/services/neo4j_recommendations.py | 10 | 196394 | 50.75 | 36.03 | 109.01 | yes | no |
| api_user_recommendations | app/services/neo4j_recommendations.py | 10 | 1260318 | 133.79 | 105.91 | 219.26 | yes | no |
| api_discover | app/services/neo4j_recommendations.py | 10 | 1406800 | 155.48 | 122.03 | 339.72 | yes | no |
| agent_movies_by_genre | app/agent/queries.py | 10 | 137782 | 23.28 | 19.93 | 91.08 | no | yes |
| variant_movies_by_genre_exact | variant for comparison (not used by the app) | 10 | 141490 | 26.77 | 18.77 | 219.67 | yes | no |
| agent_movies_like | app/agent/queries.py | 10 | 26314 | 8.92 | 6.94 | 18.06 | yes | no |
| agent_user_favorites | app/agent/queries.py | 10 | 878 | 2.62 | 2.19 | 6.01 | yes | no |
| agent_popular_movies | app/agent/queries.py | 10 | 304222 | 33.48 | 30.95 | 46.73 | no | yes |
| variant_trending_precomputed | variant for comparison (not used by the app) | 10 | 44 | 2.51 | 2.02 | 5.72 | yes | no |
| agent_explain_shared_genres | app/agent/queries.py | 5 | 30 | 3.57 | 2.20 | 17.44 | yes | no |

## api_movie_exists

Source: app/services/neo4j_recommendations.py

Purpose: Check that a movie id exists before answering

```cypher
MATCH (m:Movie {movieId: $movie_id}) RETURN m.movieId AS movie_id LIMIT 1
```

Parameters: `{'movie_id': 1}`

Plan operators: ProduceResults -> Projection -> Limit -> NodeUniqueIndexSeek

## api_user_exists

Source: app/services/neo4j_recommendations.py

Purpose: Check that a user id exists before answering

```cypher
MATCH (u:User {userId: $user_id}) RETURN u.userId AS user_id LIMIT 1
```

Parameters: `{'user_id': 1}`

Plan operators: ProduceResults -> Projection -> Limit -> NodeUniqueIndexSeek

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

## api_similar_movies

Source: app/services/neo4j_recommendations.py

Purpose: Co-rated movies with rating agreement (Toy Story)

```cypher
MATCH (target:Movie {movieId: $movie_id})<-[r1:RATED]-(u:User)-[r2:RATED]->(other:Movie)
WHERE other <> target
WITH other, count(DISTINCT u) AS common_raters,
     avg(1.0 - abs(r1.rating - r2.rating) / 4.5) AS agreement
WHERE common_raters >= 3
RETURN other.movieId AS movie_id, other.title AS title,
       round(agreement * (toFloat(common_raters) / (common_raters + 10.0)), 4) AS score,
       common_raters
ORDER BY score DESC, common_raters DESC, movie_id ASC
LIMIT $limit
```

Parameters: `{'movie_id': 1, 'limit': 10}`

Plan operators: ProduceResults -> Projection -> Top -> Filter -> EagerAggregation -> Expand(All) -> CacheProperties -> NodeUniqueIndexSeek

## api_user_recommendations

Source: app/services/neo4j_recommendations.py

Purpose: Personalized recommendations from the 30 closest users

```cypher
MATCH (u:User {userId: $user_id})-[:RATED]->(seen:Movie)<-[:RATED]-(neighbor:User)
WHERE neighbor <> u
WITH u, neighbor, count(DISTINCT seen) AS shared_movies
WHERE shared_movies >= 3
ORDER BY shared_movies DESC, neighbor.userId ASC
LIMIT 30
MATCH (neighbor)-[r:RATED]->(candidate:Movie)
WHERE NOT EXISTS { MATCH (u)-[:RATED]->(candidate) }
WITH candidate, count(DISTINCT neighbor) AS support,
     sum(shared_movies * r.rating) / toFloat(sum(shared_movies)) AS predicted_rating
WHERE support >= 3

RETURN candidate.movieId AS movie_id, candidate.title AS title,
       round(predicted_rating, 4) AS score, support
ORDER BY score DESC, support DESC, movie_id ASC
LIMIT $limit
```

Parameters: `{'user_id': 1, 'limit': 10}`

Plan operators: ProduceResults -> Projection -> Top -> Filter -> EagerAggregation -> AntiSemiApply -> Expand(All) -> NodeUniqueIndexSeek -> Expand(Into) -> Argument

## api_discover

Source: app/services/neo4j_recommendations.py

Purpose: Personalized recommendations favouring less-rated movies

```cypher
MATCH (u:User {userId: $user_id})-[:RATED]->(seen:Movie)<-[:RATED]-(neighbor:User)
WHERE neighbor <> u
WITH u, neighbor, count(DISTINCT seen) AS shared_movies
WHERE shared_movies >= 3
ORDER BY shared_movies DESC, neighbor.userId ASC
LIMIT 30
MATCH (neighbor)-[r:RATED]->(candidate:Movie)
WHERE NOT EXISTS { MATCH (u)-[:RATED]->(candidate) }
WITH candidate, count(DISTINCT neighbor) AS support,
     sum(shared_movies * r.rating) / toFloat(sum(shared_movies)) AS predicted_rating
WHERE support >= 3

MATCH (candidate)<-[all_rating:RATED]-(:User)
WITH candidate, support, predicted_rating, count(all_rating) AS rating_count
RETURN candidate.movieId AS movie_id, candidate.title AS title,
       round(predicted_rating, 4) AS score, support, rating_count
ORDER BY rating_count ASC, score DESC, movie_id ASC
LIMIT $limit
```

Parameters: `{'user_id': 1, 'limit': 10}`

Plan operators: ProduceResults -> Projection -> Top -> EagerAggregation -> Filter -> Expand(All) -> AntiSemiApply -> NodeUniqueIndexSeek -> Expand(Into) -> Argument

## agent_movies_by_genre

Source: app/agent/queries.py

Purpose: Most rated movies of a genre, case-insensitive genre name

```cypher
MATCH (m:Movie)-[:IN_GENRE]->(g:Genre)
WHERE toLower(g.name) = toLower($genre)
OPTIONAL MATCH (:User)-[r:RATED]->(m)
WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
RETURN m.movieId AS movie_id, m.title AS title,
       rating_count, round(average_rating * 100) / 100 AS average_rating
ORDER BY rating_count DESC, average_rating DESC, movie_id
LIMIT $limit
```

Parameters: `{'genre': 'comedy', 'limit': 10}`

Plan operators: ProduceResults -> Projection -> PartialTop -> Sort -> EagerAggregation -> OptionalExpand(All) -> Filter -> Expand(All) -> NodeByLabelScan

## variant_movies_by_genre_exact

Source: variant for comparison (not used by the app)

Purpose: Same as agent_movies_by_genre, exact genre name (index lookup)

```cypher
MATCH (g:Genre {name: $genre})<-[:IN_GENRE]-(m:Movie)
OPTIONAL MATCH (:User)-[r:RATED]->(m)
WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
RETURN m.movieId AS movie_id, m.title AS title,
       rating_count, round(average_rating * 100) / 100 AS average_rating
ORDER BY rating_count DESC, average_rating DESC, movie_id
LIMIT $limit
```

Parameters: `{'genre': 'Comedy', 'limit': 10}`

Plan operators: ProduceResults -> Projection -> Top -> EagerAggregation -> OptionalExpand(All) -> Filter -> Expand(All) -> NodeUniqueIndexSeek

## agent_movies_like

Source: app/agent/queries.py

Purpose: Movies sharing the most genres with a seed movie

```cypher
MATCH (seed:Movie {movieId: $movie_id})-[:IN_GENRE]->(g:Genre)
      <-[:IN_GENRE]-(m:Movie)
WHERE m.movieId <> $movie_id
WITH m, count(DISTINCT g) AS shared_genres
RETURN m.movieId AS movie_id, m.title AS title, shared_genres
ORDER BY shared_genres DESC, movie_id
LIMIT $limit
```

Parameters: `{'movie_id': 1, 'limit': 10}`

Plan operators: ProduceResults -> Projection -> Top -> EagerAggregation -> Filter -> Expand(All) -> NodeUniqueIndexSeek

## agent_user_favorites

Source: app/agent/queries.py

Purpose: Movies a user rated 4 or more

```cypher
MATCH (u:User {userId: $user_id})-[r:RATED]->(m:Movie)
WHERE r.rating >= 4
RETURN m.movieId AS movie_id, m.title AS title, r.rating AS rating
ORDER BY rating DESC, movie_id
LIMIT $limit
```

Parameters: `{'user_id': 1, 'limit': 10}`

Plan operators: ProduceResults -> Projection -> Top -> Filter -> Expand(All) -> NodeUniqueIndexSeek

## agent_popular_movies

Source: app/agent/queries.py

Purpose: Most rated movies overall (aggregation over all ratings)

```cypher
MATCH (:User)-[r:RATED]->(m:Movie)
WITH m, count(r) AS rating_count, avg(r.rating) AS average_rating
RETURN m.movieId AS movie_id, m.title AS title,
       rating_count, round(average_rating * 100) / 100 AS average_rating
ORDER BY rating_count DESC, average_rating DESC, movie_id
LIMIT $limit
```

Parameters: `{'limit': 10}`

Plan operators: ProduceResults -> Projection -> PartialTop -> Sort -> EagerAggregation -> Filter -> Expand(All) -> NodeByLabelScan

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

## agent_explain_shared_genres

Source: app/agent/queries.py

Purpose: Genres shared by two movies (explains a recommendation)

```cypher
MATCH (a:Movie {movieId: $source_id})-[:IN_GENRE]->(g:Genre)
      <-[:IN_GENRE]-(b:Movie {movieId: $recommended_id})
RETURN g.name AS genre
ORDER BY genre
LIMIT 20
```

Parameters: `{'source_id': 1, 'recommended_id': 3114}`

Plan operators: ProduceResults -> Top -> Projection -> Filter -> NodeHashJoin -> Expand(All) -> NodeUniqueIndexSeek
