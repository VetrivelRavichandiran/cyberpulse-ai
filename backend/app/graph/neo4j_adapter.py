"""CYBERPULSE AI — Neo4j adapter (optional).

Used automatically when a Neo4j instance is reachable at NEO4J_URI.
Mirrors the PostgreSQL graph service API. If the `neo4j` driver is not
installed or the server is unreachable, the PostgreSQL fallback is used —
the API layer is unchanged (documented in docs/architecture.md).
"""
from __future__ import annotations

import logging

logger = logging.getLogger("cyberpulse.neo4j")


class Neo4jGraphService:
    def __init__(self, uri: str, username: str, password: str):
        try:
            from neo4j import GraphDatabase  # type: ignore
        except ImportError:
            raise RuntimeError("neo4j driver not installed")
        # short timeouts so an unreachable Neo4j fails fast (falls back to the
        # PostgreSQL graph) instead of stalling /health and /graph/stats.
        self.driver = GraphDatabase.driver(
            uri, auth=(username, password),
            connection_timeout=2.0, connection_acquisition_timeout=2.0,
        )
        self.driver.verify_connectivity()
        logger.info("Connected to Neo4j at %s", uri)

    def verify(self) -> bool:
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    def load_entities(self, entities: list[dict], relationships: list[dict]) -> None:
        """Bulk-load entities + relationships (MERGE)."""
        with self.driver.session() as s:
            for e in entities:
                s.run(
                    "MERGE (n:Entity {entity_id: $id}) SET n.type = $type, n.masked = $masked",
                    id=e["entity_id"], type=e["entity_type"], masked=e["masked_identifier"],
                )
            for r in relationships:
                s.run(
                    """
                    MATCH (a:Entity {entity_id: $src}), (b:Entity {entity_id: $tgt})
                    MERGE (a)-[rel:REL {type: $type}]->(b)
                    SET rel.timestamp = $ts
                    """,
                    src=r["source_entity"], tgt=r["target_entity"],
                    type=r["relationship_type"], ts=str(r.get("timestamp", "")),
                )

    def cluster(self, entity_id: str, hops: int = 2) -> dict:
        with self.driver.session() as s:
            res = s.run(
                """
                MATCH path = (c:Entity {entity_id: $id})-[:REL*1..%d]-(n:Entity)
                RETURN c, n, [r IN relationships(path) | r.type] AS rels
                """ % hops,
                id=entity_id,
            )
            nodes, edges = {}, {}
            for rec in res:
                c, n, rels = rec["c"], rec["n"], rec["rels"]
                for node in (c, n):
                    nodes[node["entity_id"]] = {
                        "entity_id": node["entity_id"],
                        "entity_type": node.get("type", "UNKNOWN"),
                        "masked_identifier": node.get("masked", node["entity_id"]),
                    }
                for i, r in enumerate(rels):
                    edges[(i, r)] = r
            return {"center": entity_id, "nodes": list(nodes.values()),
                    "edges": [{"relationship_type": r} for r in edges.values()],
                    "n_nodes": len(nodes), "backend": "neo4j"}

    def close(self):
        self.driver.close()


def try_connect(uri: str, username: str, password: str) -> Neo4jGraphService | None:
    """Return a connected Neo4jGraphService or None (falls back to PostgreSQL)."""
    try:
        svc = Neo4jGraphService(uri, username, password)
        return svc
    except Exception as e:
        logger.info("Neo4j unavailable (%s) — using PostgreSQL graph fallback", e.__class__.__name__)
        return None