# movie-recommender-graphdb
Graph-based movie recommendation system using Neo4j, FastAPI, Graph Data Science and AI.

# Camille - DevOps, Testing & Deployment

## Overview

This document describes the infrastructure and quality checks
for the Movie Recommender GraphDB project.

## Docker


Build and start the services:

```powershell
docker compose up --build -d
```


Check their status:

```bash
docker compose ps
```

The stack includes the FastAPI application, Neo4j and Nginx.

## Development environment

Install development dependencies:

```bash
make install
```

Run the application locally:

```bash
make run
```

## Quality checks

Run tests with coverage:

```bash
make test
```

Run Pylint:

```bash
make lint
```

The test coverage target is at least 60%, and the Pylint
score target is at least 9.5/10.

## Continuous Integration

GitHub Actions runs the test and lint commands for relevant
pushes and pull requests.

## Environment variables

Configure local environment variables using `.env.example`.
Never commit the actual `.env` file or expose credentials.

## Docker Quickstart

### Prerequisites

- Docker Desktop installed and running.
- A configured `.env` file based on `.env.example`.
- The MovieLens Small dataset available in `data/ml-latest-small/`.

### Start the application

Build and start the services:

docker compose up --build -d


Check service status:

docker compose ps


### Access the services

- API health check: http://localhost:8080/health
- Swagger documentation: http://localhost:8080/docs
- Neo4j Browser: http://localhost:7474

### Import and verify MovieLens data

docker compose exec api python -m scripts.import_movielens
docker compose exec api python -m scripts.verify_graph


For the complete setup, configuration, Ollama integration, health checks, and troubleshooting instructions, see [Docker Deployment Guide](docs/DOCKER_DEPLOYMENT.md).

## Public Docker Image

The FastAPI application is published as a public Docker image on Docker Hub.

**Docker Hub repository:**  
[Movie Recommender API](https://hub.docker.com/r/cammetz/movie-recommender-api)

### Pull the image

docker pull TON_IDENTIFIANT_DOCKER/movie-recommender-api:1.0

The image includes the Python API and its dependencies.

Neo4j, Ollama, credentials, and the MovieLens dataset are managed separately. See the [Docker Deployment Guide](docs/DOCKER_DEPLOYMENT.md) for instructions on starting the complete application with Docker Compose.