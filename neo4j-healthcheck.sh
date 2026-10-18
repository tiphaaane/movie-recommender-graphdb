
#!/bin/sh
set -eu

exec cypher-shell \
  -u neo4j \
  -p "$NEO4J_PASSWORD" \
  -d system \
  "RETURN 1;"