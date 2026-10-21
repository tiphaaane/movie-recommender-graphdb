# Quick start for Apolline (Windows PowerShell)

1. Clone the team repository and create `feature/agent-apolline` from the latest `main`.
2. Copy this package’s `app/agent/`, `tests/test_agent.py`, `requirements-agent.txt`, `docs/`, and optionally `scripts/seed_agent_demo.py` into the repository without deleting other files.
3. Add `from app.agent.api import router as agent_router` to `app/main.py` imports and `app.include_router(agent_router)` at the bottom. Coordinate the two-line change with Tiphaine.
4. `py -3 -m venv .venv` (skip if it already exists).
5. `.\.venv\Scripts\python.exe -m pip install -r requirements-agent.txt`
6. `.\.venv\Scripts\python.exe -m pytest tests/test_agent.py -q`
7. Install Ollama, pull a small model with `ollama pull qwen2.5:3b`, check `ollama list`. Ollama usually runs automatically on Windows.
8. `py -3 -m uvicorn app.main:app --reload` (or use `.venv\Scripts\python.exe -m uvicorn ...`).
9. Open `http://127.0.0.1:8000/docs`; use POST `/api/agent/preview` to see validated Cypher and POST `/api/agent/ask` after connecting Neo4j.
10. For an empty disposable database, optionally run `python -m scripts.seed_agent_demo` after setting up Neo4j and `.env`.
11. Test a safe question and `Delete all movies` to demonstrate guardrails.
12. Commit ONLY agent files, tests, docs and requirements; do NOT commit `.env` or downloaded models.

Complete modeling, security, integration and troubleshooting guidance is in `docs/APOLLINE_INTEGRATION.md`.
