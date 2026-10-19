# movie-recommender-graphdb
Graph-based movie recommendation system using Neo4j, FastAPI, Graph Data Science and AI.

# Camille - DevOps, Testing & Deployment

## Overview

This document describes the infrastructure and quality checks
for the Movie Recommender GraphDB project.

## Docker

Build the services:

```bash
docker compose build
```

Start the services:

```bash
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
