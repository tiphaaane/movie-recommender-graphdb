// 0. Vérifier GDS
RETURN gds.version() AS version;

// 1. Projections en mémoire (à lancer une fois chacune)
CALL gds.graph.project('movieSimGraph', ['User', 'Movie'], {RATED: {orientation: 'REVERSE'}})
YIELD graphName, nodeCount, relationshipCount;

CALL gds.graph.project('movieRankGraph', ['User', 'Movie'], {RATED: {orientation: 'UNDIRECTED'}})
YIELD graphName, nodeCount, relationshipCount;

// 2. Node Similarity : films similaires à Toy Story (movieId 1)
CALL gds.nodeSimilarity.stream('movieSimGraph', {topK: 10, similarityCutoff: 0.1})
YIELD node1, node2, similarity
WITH gds.util.asNode(node1) AS a, gds.util.asNode(node2) AS b, similarity
WHERE a.movieId = 1
RETURN a.title AS movie, b.title AS similar_movie, similarity
ORDER BY similarity DESC LIMIT 10;

// 3. PageRank : films les plus importants du graphe
CALL gds.pageRank.stream('movieRankGraph')
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS movie, score
WHERE movie:Movie
RETURN movie.title AS movie, score
ORDER BY score DESC LIMIT 10;

// 4. Nettoyage
CALL gds.graph.drop('movieSimGraph', false);
CALL gds.graph.drop('movieRankGraph', false);