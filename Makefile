
PYTHON ?= python

.PHONY: help install run docker-build docker-run test lint clean

help:
	@echo "Available commands:"
	@echo "  make install       - Install development dependencies"
	@echo "  make run           - Run FastAPI locally"
	@echo "  make docker-build  - Build the Docker image"
	@echo "  make docker-run    - Start Docker services"
	@echo "  make test          - Run tests with coverage"
	@echo "  make lint          - Run Pylint"
	@echo "  make clean         - Remove Python cache files"

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

run:
	$(PYTHON) -m uvicorn app.main:app --reload

docker-build:
	docker compose build

docker-run:
	docker compose up --build -d

test:
	$(PYTHON) -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=60

lint:
	$(PYTHON) -m pylint app

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__') if p.is_dir()]"
