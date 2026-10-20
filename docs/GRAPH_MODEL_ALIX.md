# Alix — Graph schema and modeling rationale

## Dataset
MovieLens Small (GroupLens). Source: https://grouplens.org/datasets/movielens/latest/ .
Download: https://files.grouplens.org/datasets/movielens/ml-latest-small.zip .
Dataset has ratings, movies, tags and optional external IDs (`links.csv`). Movie IDs are stable across the files and correspond to the IDs used by Tiphaine's API.

## Labels and primary identifiers
- `User`: `userId` (integer, unique, anonymized MovieLens user)
- `Movie`: `movieId` (integer, unique), `title` (string), `year` (integer or null)
- `Genre`: `name` (string, unique)

## Relationships (direction matters)
- `(u:User)-[:RATED {rating: float, timestamp: integer}]->(m:Movie)`
- `(m:Movie)-[:IN_GENRE]->(g:Genre)`
- `(u:User)-[:TAGGED {tagId: string, tag: string, timestamp: integer}]->(m:Movie)`

For tags, MovieLens permits repeated or identically worded tags; tagId is derived from the source row number and fields to avoid collapsing distinct tag events. It is reproducible if source file order remains unchanged.

## Constraints
`User.userId`, `Movie.movieId`, `Genre.name` are unique. These support precise `MERGE` lookups and index-backed equality matching. Two further indexes cover `Movie.title` and `Movie.year` for future browsing/filtering. Verify that indexes are actually used with `PROFILE` before claiming speedup.

## Rationale and deliberate decisions
1. **Genres as nodes, not just a string property**: shared-genre exploration and community-based recommendations are natural graph traversals, and genre entities are reusable. Tradeoff: more relationships than storing a pipe-separated field.
2. **Ratings as relationship properties, not separate nodes**: this dataset provides one rating per user/movie pair; direct edges are efficient for collaborative filtering. If rating history, moderation, or review text becomes an important entity, separate `Rating` nodes may make sense.
3. **Tags as relationship properties, not `Tag` nodes**: we need only 3 labels for now; keeping the text on `TAGGED` preserves all source tag applications. Tradeoff: grouping synonymous tags is harder. A future extension could introduce normalized `Tag` nodes and `USES_TAG` relations.
4. **MovieLens IDs retained**: matches Tiphaine's `movie_id` and `user_id` API path parameters. No independent renumbering, and no fake movie IDs.
5. **Parameterized batch imports**: `UNWIND $rows`, batches of 1000 and `MERGE` make repeated execution predictable and prevent creating duplicate nodes/ratings for the same source.
6. **Separate verified data from recommendation scores**: imported ratings are observed data; Juliette's similarity/ML scores are calculated predictions and must not be labeled as ground truth.

## Anti-genericity appendix (complete as a group)
Prompt an AI assistant with the same project description to create a simple default graph. Paste its diagram and contrast its representation with the above choices. In the oral defense, explain why you intentionally chose these relationships and constraints. Do not invent a comparison or copy a schema uncritically.

## Diagram
See `docs/graph_schema.mmd`. Open it with a Mermaid preview extension or recreate/export the diagram using diagrams.net (draw.io), as required for the report.

## Data privacy and licensing
MovieLens users are anonymized. Respect GroupLens usage terms and attribute GroupLens in README. Avoid committing unnecessary raw data files; keep the downloaded `data/` folder local unless the professor specifically requires raw samples.
