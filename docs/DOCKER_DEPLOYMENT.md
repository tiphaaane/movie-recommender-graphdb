# Docker Deployment Guide


## 1. Prerequisites


- Docker Desktop installed and running.

- Git installed.

- The MovieLens Small dataset available locally.

- Ollama installed and running on the host machine if AI agent endpoints are required.

- A configured .env file in the project root.


## 2. Environment Configuration


Create a .env file from .env.example and configure the required values.


Keep secrets in .env. Never commit this file or publish it in a Docker image.


Example variables:



- `NEO4J\_PASSWORD`: password used to access Neo4j.

- `OLLAMA\_MODEL`: Ollama model used by the AI agent, for example `qwen2.5:3b`.



Check `docker-compose.yml` for the complete list of supported environment variables.


## 3. Start the Services


From the project root, run:


docker compose up --build -d


Check the container status:


docker compose ps


View logs if needed:


docker compose logs -f api

docker compose logs -f neo4j

docker compose logs -f nginx



## 4. Access the Services



- API through Nginx: http://localhost:8080

- Swagger API documentation: http://localhost:8080/docs

- Neo4j Browser: http://localhost:7474

- Neo4j Bolt connection: `bolt://localhost:7687`



## 5. MovieLens Dataset



Place the MovieLens Small dataset in `data/ml-latest-small/`.



The expected directory contains files such as `movies.csv`, `ratings.csv`, `tags.csv`, and `links.csv`.



Import the dataset into Neo4j:



docker compose exec api python -m scripts.import\_movielens



Verify the imported graph:



docker compose exec api python -m scripts.verify\_graph



The import can be run again to verify that it does not create duplicate graph data.



## 6. Health Checks and API Verification



Check the API health endpoint:





curl http://localhost:8080/health





Open the Swagger documentation at http://localhost:8080/docs to test available API endpoints.



Check container health:



docker compose ps



## 7. Ollama Integration



When using the AI agent endpoints, ensure Ollama is running on the host and that the configured model is available.


The Docker Compose configuration uses `http://host.docker.internal:11434` to reach Ollama from the API container.



Pull the configured model on the host if needed:



ollama pull qwen2.5:3b



## 8. Troubleshooting



- If the API is unavailable, check `docker compose logs api`.

- If Neo4j is unhealthy, check `docker compose logs neo4j` and verify `NEO4J\_PASSWORD`.

- If the AI agent cannot reach Ollama, confirm Ollama is running and accessible on port `11434`.

- If the graph is empty, check the dataset directory and rerun the import and verification scripts.



## 9. Stop the Services



Stop the services without removing persistent data:



docker compose down



To remove containers and the Compose network, including the persistent Neo4j data volume, run:



docker compose down -v



Warning: docker compose down -v deletes the persistent Neo4j volume and its stored graph data.