# Juliette — macOS database setup

This starter was adapted from the team's original Neo4j ETL files; use them only once per shared repo (do not merge duplicate scripts from an old Alix branch).

1. macOS: `python3 -m venv .venv`; `./.venv/bin/python -m pip install -r requirements-neo4j.txt`.
2. Get `ml-latest-small.zip` from https://grouplens.org/datasets/movielens/latest/ and extract to `data/ml-latest-small/`. Do not commit raw CSV or `.env`.
3. Local Docker test: `docker run -d --name juliette-neo4j -p 127.0.0.1:7474:7474 -p 127.0.0.1:7687:7687 -e "NEO4J_AUTH=neo4j/$NEO4J_PASSWORD" neo4j:5.26-community` after setting `export NEO4J_PASSWORD='your-private-password'`. Or use a Neo4j Aura instance and its provided URI / credentials.
4. Add `.env` in repository root with `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
5. `./.venv/bin/python -m scripts.inspect_dataset`
6. `./.venv/bin/python -m pytest tests/test_movielens_etl.py -q`
7. `./.venv/bin/python -m scripts.import_movielens --limit-ratings 1000`
8. `./.venv/bin/python -m scripts.import_movielens`
9. `./.venv/bin/python -m scripts.verify_graph`

Schema: `User(userId)`, `Movie(movieId,title,year)`, `Genre(name)`; `RATED`, `TAGGED`, `IN_GENRE`. Refer to documentation and test on the actual graph.
