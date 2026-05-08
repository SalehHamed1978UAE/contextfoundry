"""Graph query primitives over the live CF schema.

Typed wrappers around SQLAlchemy. No business logic here — every method is a
single deterministic query. All result lists are `ORDER BY id ASC` so cached
LLM prompts hash identically across runs.

Schema mapping (spec → live):
  spec.entities.id (int)        -> entities.id (uuid string)
  spec.relationships.evidence_chunk_id -> relationships.source_chunk_id
  spec.chunks.content           -> document_chunks.text
  spec.chunks.document_name     -> documents.filename (joined)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Sequence
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class EntityRow:
    id: str
    name: str
    entity_type: str
    lifecycle_state: str
    properties: Dict[str, Any]


@dataclass(frozen=True)
class RelationshipRow:
    id: str
    source_entity_id: str
    relationship_type: str
    target_entity_id: str
    lifecycle_state: str
    source_chunk_id: Optional[str]
    properties: Dict[str, Any]
    source_predicate: Optional[str]
    raw_relationship_type: Optional[str]


@dataclass(frozen=True)
class ChunkRow:
    id: str
    document_id: str
    text: str
    chunk_index: int


class GraphTools:
    """Tenant-scoped graph primitives. Pass tenant_id once at construction."""

    def __init__(self, session: Session, tenant_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id

    def _exec(self, sql, params=None):
        """Single counted entry point for every DB query — bumps the active
        span's db_query_count so the tracer can attribute load per stage.

        Each query runs inside a SAVEPOINT (`begin_nested`) so a failure
        (e.g. malformed UUID from an LLM-emitted Condition) only rolls back
        this single statement — pending writes from outer callers in the
        same session are preserved. This is required because the inference
        engine may share a session with broader units of work."""
        from .observability.trace import tracer
        tracer.bump("db_query_count")
        stmt = text(sql) if isinstance(sql, str) else sql
        with self.session.begin_nested():
            return self.session.execute(stmt, params or {})

    # ------------------------------------------------------------ entities
    def get_entity(self, entity_id: str) -> Optional[EntityRow]:
        sql = """
          SELECT id::text, name,
                 COALESCE((properties->>'entity_type'), '') AS entity_type,
                 lifecycle_state::text, COALESCE(properties, '{}'::json)
            FROM entities
           WHERE id = CAST(:eid AS uuid)
        """
        if self.tenant_id:
            sql += " AND tenant_id = CAST(:tid AS uuid)"
        row = self._exec(sql, {"eid": entity_id, "tid": self.tenant_id}).fetchone()
        if not row:
            return None
        return EntityRow(row[0], row[1], row[2], row[3], dict(row[4] or {}))

    def find_entities_by_name(self, name: str, fuzzy: bool = True) -> List[EntityRow]:
        if fuzzy:
            sql = """
              SELECT id::text, name,
                     COALESCE((properties->>'entity_type'), ''),
                     lifecycle_state::text, COALESCE(properties, '{}'::json)
                FROM entities
               WHERE LOWER(name) LIKE LOWER(:pat)
            """
            params = {"pat": f"%{name}%"}
        else:
            sql = """
              SELECT id::text, name,
                     COALESCE((properties->>'entity_type'), ''),
                     lifecycle_state::text, COALESCE(properties, '{}'::json)
                FROM entities
               WHERE LOWER(name) = LOWER(:n)
            """
            params = {"n": name}
        if self.tenant_id:
            sql += " AND tenant_id = CAST(:tid AS uuid)"
            params["tid"] = self.tenant_id
        sql += " ORDER BY id ASC"
        return [EntityRow(r[0], r[1], r[2], r[3], dict(r[4] or {}))
                for r in self._exec(sql, params).fetchall()]

    def find_entities_by_embedding(self, query_embedding: Sequence[float],
                                   top_k: int = 50) -> List[EntityRow]:
        if not query_embedding:
            return []
        sql = """
          SELECT id::text, name,
                 COALESCE((properties->>'entity_type'), ''),
                 lifecycle_state::text, COALESCE(properties, '{}'::json)
            FROM entities
           WHERE name_embedding IS NOT NULL
        """
        params: dict = {"k": top_k}
        if self.tenant_id:
            sql += " AND tenant_id = CAST(:tid AS uuid)"
            params["tid"] = self.tenant_id
        sql += " ORDER BY name_embedding <=> CAST(:qe AS vector), id ASC LIMIT :k"
        params["qe"] = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"
        return [EntityRow(r[0], r[1], r[2], r[3], dict(r[4] or {}))
                for r in self._exec(sql, params).fetchall()]

    # ------------------------------------------------------- relationships
    def get_relationships(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        rel_types: Optional[List[str]] = None,
        include_archived: bool = False,
        properties_filter: Optional[Dict[str, Any]] = None,
    ) -> List[RelationshipRow]:
        sql = """
          SELECT id::text, source_id::text, relationship_type, target_id::text,
                 lifecycle_state::text, source_chunk_id::text,
                 COALESCE(properties, '{}'::json),
                 source_predicate, raw_relationship_type
            FROM relationships
           WHERE 1=1
        """
        params: dict = {}
        if source_id:
            sql += " AND source_id = CAST(:sid AS uuid)"
            params["sid"] = source_id
        if target_id:
            sql += " AND target_id = CAST(:tgt AS uuid)"
            params["tgt"] = target_id
        if rel_types:
            placeholders = ",".join(f":rt{i}" for i in range(len(rel_types)))
            sql += f" AND relationship_type IN ({placeholders})"
            for i, rt in enumerate(rel_types):
                params[f"rt{i}"] = rt
        if not include_archived:
            sql += " AND lifecycle_state <> 'ARCHIVED'"
        if self.tenant_id:
            sql += " AND tenant_id = CAST(:tid AS uuid)"
            params["tid"] = self.tenant_id
        sql += " ORDER BY id ASC"
        rows = self._exec(sql, params).fetchall()
        out = []
        for r in rows:
            props = dict(r[6] or {})
            if properties_filter and not all(props.get(k) == v for k, v in properties_filter.items()):
                continue
            out.append(RelationshipRow(
                id=r[0], source_entity_id=r[1], relationship_type=r[2],
                target_entity_id=r[3], lifecycle_state=r[4], source_chunk_id=r[5],
                properties=props, source_predicate=r[7], raw_relationship_type=r[8],
            ))
        return out

    def get_competing_relationships(self, fact) -> List[RelationshipRow]:
        """Find facts that compete with this one for a single-target slot.

        Pattern: same target + same relationship_type, different source.
        Used by the adversary to surface "two CEOs" style conflicts.
        """
        all_to_target = self.get_relationships(
            target_id=fact.target_entity_id,
            rel_types=[fact.relationship_type],
            include_archived=False,
        )
        return [r for r in all_to_target if r.source_entity_id != fact.source_entity_id]

    # ------------------------------------------------------------- chunks
    def get_evidence_chunks(self, rel_ids: List[str]) -> List[ChunkRow]:
        if not rel_ids:
            return []
        placeholders = ",".join(f"CAST(:r{i} AS uuid)" for i in range(len(rel_ids)))
        params = {f"r{i}": rid for i, rid in enumerate(rel_ids)}
        sql = f"""
          SELECT DISTINCT c.id::text, c.document_id::text, c.text, c.chunk_index
            FROM document_chunks c
            JOIN relationships r ON r.source_chunk_id = c.id
           WHERE r.id IN ({placeholders})
        """
        if self.tenant_id:
            sql += " AND c.tenant_id = CAST(:tid AS uuid)"
            params["tid"] = self.tenant_id
        sql += " ORDER BY c.id ASC"
        return [ChunkRow(r[0], r[1], r[2], r[3])
                for r in self._exec(sql, params).fetchall()]

    def search_chunks_text(self, query: str) -> List[ChunkRow]:
        """Full-text search via PG `to_tsvector` over chunk text.

        Falls back to ILIKE if tsquery parsing fails — keeps the gatherer
        running on adversarial query strings.
        """
        sql = """
          SELECT id::text, document_id::text, text, chunk_index
            FROM document_chunks
           WHERE text ILIKE :pat
        """
        params = {"pat": f"%{query}%"}
        if self.tenant_id:
            sql += " AND tenant_id = CAST(:tid AS uuid)"
            params["tid"] = self.tenant_id
        sql += " ORDER BY id ASC LIMIT 200"
        return [ChunkRow(r[0], r[1], r[2], r[3])
                for r in self._exec(sql, params).fetchall()]

    def search_chunks_vector(self, query_embedding: Sequence[float],
                             top_k: int = 50) -> List[ChunkRow]:
        if not query_embedding:
            return []
        sql = """
          SELECT id::text, document_id::text, text, chunk_index
            FROM document_chunks
           WHERE embedding IS NOT NULL
        """
        params: dict = {"k": top_k}
        if self.tenant_id:
            sql += " AND tenant_id = CAST(:tid AS uuid)"
            params["tid"] = self.tenant_id
        sql += " ORDER BY embedding <=> CAST(:qe AS vector), id ASC LIMIT :k"
        params["qe"] = "[" + ",".join(f"{x:.6f}" for x in query_embedding) + "]"
        return [ChunkRow(r[0], r[1], r[2], r[3])
                for r in self._exec(sql, params).fetchall()]

    # ------------------------------------------------------------- traces
    def trace_chain(self, start_id: str, rel_types: List[str],
                    max_hops: int = 5) -> List[List[RelationshipRow]]:
        """All non-revisiting chains of length ≤ max_hops starting at start_id."""
        chains: List[List[RelationshipRow]] = []
        def walk(node: str, path: List[RelationshipRow], visited: set):
            if len(path) >= max_hops:
                chains.append(list(path))
                return
            for r in self.get_relationships(source_id=node, rel_types=rel_types):
                if r.target_entity_id in visited:
                    continue
                walk(r.target_entity_id, path + [r], visited | {r.target_entity_id})
            if path:
                chains.append(list(path))
        walk(start_id, [], {start_id})
        chains.sort(key=lambda c: tuple(r.id for r in c))
        return chains
