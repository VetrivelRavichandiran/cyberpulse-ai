"""CYBERPULSE AI — graph intelligence service.

Primary backend: PostgreSQL `entities` + `entity_relationships` tables
(a real relational graph, always available).
Optional: Neo4j adapter — when NEO4J_URI is reachable, the same queries are
executed against Neo4j (see neo4j_adapter.py). The public API is identical.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Entity, EntityRelationship

logger = logging.getLogger("cyberpulse.graph")

REL_LABELS = {
    "REPORTED_ON": "reported on",
    "TRANSFERRED_TO": "transferred to",
    "WITHDREW_AT": "withdrew at",
    "FREQ_ATM": "frequent ATM",
    "REGISTERED_PHONE": "registered phone",
}


class GraphService:
    def __init__(self, db: Session):
        self.db = db

    # ── entity lookup ──────────────────────────────────────────────────────
    def get_entity(self, entity_id: str) -> dict | None:
        e = self.db.execute(select(Entity).where(Entity.entity_id == entity_id)).scalar_one_or_none()
        if e is None:
            return None
        return {
            "entity_id": e.entity_id,
            "entity_type": e.entity_type,
            "masked_identifier": e.masked_identifier,
            "degree": self._degree(e.entity_id),
        }

    def _degree(self, entity_id: str) -> int:
        from sqlalchemy import func
        n1 = self.db.execute(
            select(func.count()).select_from(EntityRelationship)
            .where(EntityRelationship.source_entity == entity_id)
        ).scalar_one()
        n2 = self.db.execute(
            select(func.count()).select_from(EntityRelationship)
            .where(EntityRelationship.target_entity == entity_id)
        ).scalar_one()
        return int(n1 + n2)

    # ── neighborhood ───────────────────────────────────────────────────────
    def relationships(self, entity_id: str, limit: int = 100) -> list[dict]:
        """Direct neighbors with edge metadata (1-hop)."""
        src = self.db.execute(
            select(EntityRelationship).where(EntityRelationship.source_entity == entity_id)
        ).scalars().all()
        tgt = self.db.execute(
            select(EntityRelationship).where(EntityRelationship.target_entity == entity_id)
        ).scalars().all()
        out = []
        for r in src:
            out.append(self._edge(entity_id, r, direction="out"))
        for r in tgt:
            out.append(self._edge(entity_id, r, direction="in"))
        out.sort(key=lambda x: (x.get("timestamp") or ""), reverse=True)
        return out[:limit]

    def _edge(self, center: str, r: EntityRelationship, direction: str) -> dict:
        other = r.target_entity if direction == "out" else r.source_entity
        oe = self.db.execute(select(Entity).where(Entity.entity_id == other)).scalar_one_or_none()
        return {
            "source": r.source_entity,
            "target": r.target_entity,
            "relationship_type": r.relationship_type,
            "label": REL_LABELS.get(r.relationship_type, r.relationship_type),
            "direction": direction,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "neighbor": {
                "entity_id": other,
                "entity_type": oe.entity_type if oe else "UNKNOWN",
                "masked_identifier": oe.masked_identifier if oe else other,
            },
        }

    # ── cluster (2-hop ego network) ────────────────────────────────────────
    def cluster(self, entity_id: str, hops: int = 2, limit: int = 200) -> dict:
        """Ego network: nodes + edges up to `hops`."""
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        seen_edges: set[tuple] = set()

        def add_node(eid: str):
            if eid in nodes:
                return
            e = self.db.execute(select(Entity).where(Entity.entity_id == eid)).scalar_one_or_none()
            nodes[eid] = {
                "entity_id": eid,
                "entity_type": e.entity_type if e else "UNKNOWN",
                "masked_identifier": e.masked_identifier if e else eid,
                "degree": self._degree(eid),
            }

        def add_edge(r: EntityRelationship):
            key = (r.source_entity, r.target_entity, r.relationship_type)
            if key in seen_edges:
                return
            seen_edges.add(key)
            edges.append({
                "source": r.source_entity,
                "target": r.target_entity,
                "relationship_type": r.relationship_type,
                "label": REL_LABELS.get(r.relationship_type, r.relationship_type),
            })

        frontier = [entity_id]
        add_node(entity_id)
        for _ in range(hops):
            next_frontier = []
            for eid in frontier:
                rels = self.db.execute(
                    select(EntityRelationship).where(
                        (EntityRelationship.source_entity == eid)
                        | (EntityRelationship.target_entity == eid)
                    )
                ).scalars().all()
                for r in rels:
                    add_edge(r)
                    for other in (r.source_entity, r.target_entity):
                        if other != eid and other not in nodes:
                            add_node(other)
                            next_frontier.append(other)
            frontier = next_frontier
            if not frontier:
                break
        # suspicious flag: HIGH-risk account or mule-inflow pattern
        return {
            "center": entity_id,
            "nodes": list(nodes.values())[:limit],
            "edges": edges[:limit * 2],
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "hops": hops,
            "backend": "postgresql",
        }

    # ── pattern analytics ──────────────────────────────────────────────────
    def suspicious_chains(self, since_hours: int = 72, limit: int = 20) -> list[dict]:
        """Find accounts with many UPI inflows from distinct sources (mule pattern)."""
        from sqlalchemy import func
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        rows = self.db.execute(
            select(
                EntityRelationship.target_entity,
                func.count().label("inflows"),
                func.count(func.distinct(EntityRelationship.source_entity)).label("sources"),
            )
            .where(EntityRelationship.relationship_type == "TRANSFERRED_TO")
            .where(EntityRelationship.timestamp >= cutoff)
            .group_by(EntityRelationship.target_entity)
            .having(func.count() >= 5)
            .order_by(func.count().desc())
            .limit(limit)
        ).all()
        out = []
        for target, inflows, sources in rows:
            e = self.db.execute(select(Entity).where(Entity.entity_id == target)).scalar_one_or_none()
            out.append({
                "entity_id": target,
                "entity_type": e.entity_type if e else "ACCOUNT",
                "masked_identifier": e.masked_identifier if e else target,
                "inflow_count": int(inflows),
                "distinct_sources": int(sources),
            })
        return out

    def shared_phone_accounts(self, limit: int = 20) -> list[dict]:
        """Accounts sharing a registered phone (cross-ring linkage)."""
        from sqlalchemy import func
        rows = self.db.execute(
            select(
                EntityRelationship.target_entity.label("phone"),
                EntityRelationship.source_entity.label("account"),
                func.count().label("n"),
            )
            .where(EntityRelationship.relationship_type == "REGISTERED_PHONE")
            .group_by(EntityRelationship.target_entity, EntityRelationship.source_entity)
            .order_by(func.count().desc())
            .limit(limit)
        ).all()
        # group by phone
        by_phone: dict[str, list[str]] = {}
        for phone, account, _ in rows:
            by_phone.setdefault(phone, []).append(account)
        out = []
        for phone, accs in by_phone.items():
            if len(accs) >= 2:
                pe = self.db.execute(select(Entity).where(Entity.entity_id == phone)).scalar_one_or_none()
                out.append({
                    "phone_entity": phone,
                    "phone_masked": pe.masked_identifier if pe else phone,
                    "accounts": accs,
                    "count": len(accs),
                })
        return out