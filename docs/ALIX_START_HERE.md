# Alix — exact first run (Windows, VS Code)

This package is **additional files only**. Do not overwrite Tiphaine's `app/`, Camille's `docker-compose.yml`, `Makefile`, `.env.example` or their tests.

1. Clone group repo and use branch `feature/neo4j-alix`.
2. Copy `scripts/`, `docs/`, `requirements-neo4j.txt` and `tests/test_movielens_etl.py` into repository root; merge `tests/` folder.
3. Download https://files.grouplens.org/datasets/movielens/ml-latest-small.zip ; extract to `data/ml-latest-small/` (the path should contain `movies.csv`, `ratings.csv`, `tags.csv`). Do not commit the `data/` folder.
4. If Camille's `.env` and `docker-compose.yml` are available: edit local `.env`, then `docker compose up -d neo4j`. **If only Tiphaine's files are available**, run Neo4j locally with Docker instead:

```powershell
$env:NEO4J_AUTH='neo4j/YourStrongPrivatePassword123'
docker run -d --name alix-neo4j -p 127.0.0.1:7474:7474 -p 127.0.0.1:7687:7687 -e NEO4J_AUTH=$env:NEO4J_AUTH neo4j:5.26.32-community
```

5. For standalone Docker, create your private `.env` manually in repository root with `NEO4J_PASSWORD=YourStrongPrivatePassword123` (same password; don't commit), and `NEO4J_URI=bolt://localhost:7687`. Check `.gitignore` includes `.env`, `.venv/`, and `data/`.
6. Create venv: `py -3 -m venv .venv`
7. Install requirements: `.\.venv\Scripts\python.exe -m pip install -r requirements-neo4j.txt`
8. Inspect: `.\.venv\Scripts\python.exe -m scripts.inspect_dataset`
9. Small import: `.\.venv\Scripts\python.exe -m scripts.import_movielens --limit-ratings 1000`
10. Full import: `.\.venv\Scripts\python.exe -m scripts.import_movielens`
11. Verify: `.\.venv\Scripts\python.exe -m scripts.verify_graph`
12. Tests: `.\.venv\Scripts\python.exe -m pytest tests/test_movielens_etl.py -q`
13. Open Neo4j Browser at http://localhost:7474 ; connect as `neo4j` using the private password, run one query at a time from `docs/graph_queries.cypher`.
14. `git add scripts docs requirements-neo4j.txt tests/test_movielens_etl.py`; `git commit -m "feat: add MovieLens Neo4j schema and importer"`; `git push -u origin feature/neo4j-alix` ; open a PR and request review from Tiphaine.

### Integration notes
- Tiphaine and Juliette expect `Movie.movieId`, `Movie.title`, `User.userId`, and integer IDs.
- API output uses `movie_id` but database properties use `movieId`. Translate at the API/service layer.
- The API's mock data stays unchanged until the team integrates real services.
- Python scripts are run **on your Windows host** and connect over `bolt://localhost:7687`. Inside Docker containers, the API should use `bolt://neo4j:7687` (configured by Camille).
- `requirements-neo4j.txt` is standalone and for local ETL use. When the API begins querying Neo4j, coordinate with Camille and Tiphaine to add the `neo4j` Python driver to the application's `requirements.txt` for the Docker image.
- Neo4j Graph Data Science is **not installed** by these files. Juliette will coordinate the GDS plugin/version with Camille.
- Do not run `docker compose down -v` unless deleting local graph data is intentional.
