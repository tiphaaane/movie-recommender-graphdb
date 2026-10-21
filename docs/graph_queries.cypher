// Run ONE query at a time in Neo4j Browser.
// Node counts
MATCH (m:Movie) RETURN count(m) AS movies;

// Relationship counts
MATCH (u:User)-[r:RATED]->(m:Movie)
RETURN count(r) AS ratings;

// Preview 25 connections around a known movie ID
MATCH path=(m:Movie {movieId: 1})-[:IN_GENRE]->(g:Genre)
RETURN path LIMIT 25;

// Shared-genre candidate movies (NOT Juliette's final similarity score)
MATCH (m:Movie {movieId: 1})-[:IN_GENRE]->(g:Genre)<-[:IN_GENRE]-(other:Movie)
WHERE other <> m
RETURN other.movieId AS movieId, other.title AS title,
       count(DISTINCT g) AS sharedGenres
ORDER BY sharedGenres DESC, movieId ASC LIMIT 10;

// Explore user/movie rating connections
MATCH path=(u:User {userId: 1})-[r:RATED]->(m:Movie)
RETURN path LIMIT 10;

// List constraints and indexes
SHOW CONSTRAINTS;
SHOW INDEXES;

// Performance inspection (run separately)
EXPLAIN MATCH (m:Movie {movieId: 1}) RETURN m.title;
PROFILE MATCH (m:Movie {movieId: 1}) RETURN m.title;
