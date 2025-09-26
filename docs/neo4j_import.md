# Neo4j Knowledge Graph Import

This guide explains how to reproduce the handwerker-app knowledge graph in a
local Neo4j instance.  You can either run Neo4j via Docker or use an existing
installation on your workstation.

## 1. Start Neo4j locally

### Option A – Docker (recommended)
```bash
docker run \
  --rm \
  --name handwerker-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/test \
  neo4j:5.15.0
```
This command starts a disposable Neo4j 5.x container with the default password
`test`.  Wait until the logs show that Bolt is listening on port `7687`.

### Option B – Local installation
1. Install Neo4j Desktop or the Neo4j Community Edition.
2. Create (or reuse) a database and ensure that the Bolt connector is exposed on
   `bolt://localhost:7687`.
3. Note the username and password for later use.

## 2. Install Python dependencies

The import script uses the official Neo4j Python driver.  Install it into your
virtual environment:

```bash
pip install neo4j
```

If you prefer to keep dependencies isolated, create a dedicated virtual
environment first.

## 3. Load the knowledge graph

Run the helper script that lives in this repository:

```bash
python scripts/neo4j/load_knowledge_graph.py \
  bolt://localhost:7687 \
  neo4j \
  test
```

Replace `neo4j` and `test` with the credentials of your database.  The script
performs `MERGE` operations, so running it multiple times is idempotent.

## 4. Inspect the graph in Neo4j Browser

1. Open <http://localhost:7474> in your browser.
2. Log in using the same credentials as above.
3. Run the following Cypher query to inspect the imported nodes and
   relationships:

```cypher
MATCH (n)
OPTIONAL MATCH (n)-[r]->(m)
RETURN n, r, m
```

You can also filter by labels, for example:

```cypher
MATCH (c:Component)-[r]->(s:Service)
RETURN c, r, s
```

## 5. Extend or update the model

The script encodes the nodes and relationships that were identified during the
architecture analysis.  To adapt it to future findings:

1. Update the `NODES` and `RELATIONSHIPS` lists in
   [`scripts/neo4j/load_knowledge_graph.py`](../scripts/neo4j/load_knowledge_graph.py).
2. Re-run the import command.
3. Use `DETACH DELETE` in Cypher if you need to remove outdated nodes:

```cypher
MATCH (n {key: "DeprecatedNode"})
DETACH DELETE n;
```

With these steps you can reproduce and evolve the project knowledge graph in a
self-hosted Neo4j database.
