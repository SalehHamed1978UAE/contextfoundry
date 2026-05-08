"""CrossDocumentValidator — Component 3 of the Intelligent Auto-Discovery System.

Validates an extracted fact by checking whether other documents in the same
tenant corroborate it, contradict it, or leave it as a single-source orphan.

Per spec, four outcomes:

  - CORROBORATED  — same fact from ≥2 distinct sources → AUTO_PROMOTE
  - SINGLE_SOURCE — exactly 1 corroborating source     → STAGING
  - ORPHAN        — no corroboration                   → STAGING
  - CONTRADICTED  — conflicting fact found             → HUMAN_REVIEW

Contradiction patterns (extensible):
  1. Active-role conflict: two PERSONs hold the same ROLE entity at the same
     time (relationship_type ∈ HOLDS_POSITION/LEADS/MANAGES/HEADS/CHAIRS).
  2. Temporal contradiction: valid_from > valid_to.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, List, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFact:
    """A fact (relationship) being validated."""
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    evidence_chunk_id: Optional[str] = None      # chunk this fact was extracted from
    source_document_id: Optional[str] = None
    valid_from: Optional[Any] = None
    valid_to: Optional[Any] = None
    confidence: float = 0.0


@dataclass
class ValidationResult:
    status: str                                  # CORROBORATED | SINGLE_SOURCE | ORPHAN | CONTRADICTED
    confidence: float
    reasoning: str
    action_required: str                         # AUTO_PROMOTE | STAGING | HUMAN_REVIEW
    corroborating_count: int = 0
    contradicting_count: int = 0
    contradicting_examples: List[dict] = field(default_factory=list)


# Roles that are typically singular per organisation/role-entity.
_SINGULAR_ROLE_RELATIONS = {
    "HOLDS_POSITION", "LEADS", "MANAGES", "HEADS", "CHAIRS",
}


class CrossDocumentValidator:
    """Validate facts against the knowledge graph.

    Args:
        session: SQLAlchemy session bound to the same tenant DB.
        tenant_id: tenant UUID string. When provided, all queries are scoped
            to this tenant so cross-tenant data can't bleed into validation.
        ignore_archived: skip ARCHIVED relationships (defaults True per spec).
    """

    def __init__(
        self,
        session: Any,
        tenant_id: Optional[str] = None,
        ignore_archived: bool = True,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.ignore_archived = ignore_archived

    # ------------------------------------------------------------- public
    def validate_fact(self, fact: ExtractedFact) -> ValidationResult:
        """Check corroboration / contradiction for a single fact."""
        corroborating = self._find_corroborating_edges(fact)
        contradicting = self._find_contradicting_edges(fact)

        # Temporal self-contradiction (no DB lookup needed)
        if fact.valid_from and fact.valid_to and fact.valid_from > fact.valid_to:
            contradicting = list(contradicting) + [{
                "kind": "temporal",
                "reason": f"valid_from {fact.valid_from} after valid_to {fact.valid_to}",
            }]

        if contradicting:
            confidence = self._resolve_contradiction(fact, corroborating, contradicting)
            return ValidationResult(
                status="CONTRADICTED",
                confidence=confidence,
                reasoning=(
                    f"Contradicted by {len(contradicting)} source(s). "
                    f"Corroborated by {len(corroborating)}."
                ),
                action_required="HUMAN_REVIEW",
                corroborating_count=len(corroborating),
                contradicting_count=len(contradicting),
                contradicting_examples=[
                    c if isinstance(c, dict) else {
                        "source_id": str(c.get("source_id")),
                        "target_id": str(c.get("target_id")),
                        "relationship_type": c.get("relationship_type"),
                        "source_document_id": str(c.get("source_document_id"))
                        if c.get("source_document_id") else None,
                    } for c in contradicting[:5]
                ],
            )

        n = len(corroborating)
        if n >= 2:
            return ValidationResult(
                status="CORROBORATED",
                confidence=round(0.7 + min(n, 5) * 0.05, 3),
                reasoning=f"Corroborated by {n} independent source(s).",
                action_required="AUTO_PROMOTE",
                corroborating_count=n,
            )
        if n == 1:
            return ValidationResult(
                status="SINGLE_SOURCE",
                confidence=0.5,
                reasoning="Only one other source found. Needs corroboration.",
                action_required="STAGING",
                corroborating_count=1,
            )
        return ValidationResult(
            status="ORPHAN",
            confidence=0.3,
            reasoning="No corroborating or contradicting evidence found.",
            action_required="STAGING",
        )

    # --------------------------------------------------------- corroboration
    def _find_corroborating_edges(self, fact: ExtractedFact) -> List[dict]:
        """Edges with the same source/target/rel_type from a *different
        source document*.

        Counting by document (not chunk) means many chunks within one
        document don't inflate the corroboration count — true corroboration
        requires independent sources, per the spec.
        """
        params: dict = {
            "src": fact.source_entity_id,
            "tgt": fact.target_entity_id,
            "rt": fact.relationship_type,
        }
        # Branch in Python (not SQL) — psycopg casts a bare-NULL bind to
        # text, which then can't be compared against a uuid column.
        if fact.evidence_chunk_id:
            distinctness_clause = (
                "AND source_chunk_id IS DISTINCT FROM CAST(:chunk AS uuid)"
            )
            params["chunk"] = fact.evidence_chunk_id
        elif fact.source_document_id:
            distinctness_clause = (
                "AND source_document_id IS DISTINCT FROM CAST(:doc AS uuid)"
            )
            params["doc"] = fact.source_document_id
        else:
            # No anchor → can't tell self from other; skip the distinctness
            # filter (the validator will be conservative and overcount).
            distinctness_clause = ""

        sql = f"""
            SELECT id, source_id, target_id, relationship_type,
                   source_chunk_id, source_document_id, lifecycle_state, confidence
            FROM relationships
            WHERE source_id = CAST(:src AS uuid)
              AND target_id = CAST(:tgt AS uuid)
              AND relationship_type = :rt
              {distinctness_clause}
        """
        if self.ignore_archived:
            sql += " AND lifecycle_state <> 'ARCHIVED'"
        if self.tenant_id:
            sql += " AND tenant_id = CAST(:tid AS uuid)"
            params["tid"] = self.tenant_id
        rows = self.session.execute(text(sql), params).mappings().fetchall()
        edges = [dict(r) for r in rows]
        # De-duplicate by source_document_id so multiple chunks of the same
        # document only count as one corroborating source. Edges without a
        # source_document_id fall back to their own id (treated as distinct).
        seen_docs: set = set()
        if fact.source_document_id:
            seen_docs.add(str(fact.source_document_id))
        deduped: List[dict] = []
        for e in edges:
            key = str(e.get("source_document_id") or e.get("id"))
            if key in seen_docs:
                continue
            seen_docs.add(key)
            deduped.append(e)
        return deduped

    # --------------------------------------------------------- contradictions
    def _find_contradicting_edges(self, fact: ExtractedFact) -> List[dict]:
        """Find edges that contradict this fact.

        Pattern 1 — Singular-role conflict: another PERSON holds the same ROLE
        entity (target) via a singular-role relation, and is not the same person
        as the fact's source.
        """
        contradictions: List[dict] = []

        if fact.relationship_type in _SINGULAR_ROLE_RELATIONS:
            params: dict = {
                "tgt": fact.target_entity_id,
                "src": fact.source_entity_id,
                "rels": list(_SINGULAR_ROLE_RELATIONS),
            }
            sql = """
                SELECT id, source_id, target_id, relationship_type,
                       source_document_id, source_chunk_id, lifecycle_state
                FROM relationships
                WHERE target_id = CAST(:tgt AS uuid)
                  AND relationship_type = ANY(:rels)
                  AND source_id <> CAST(:src AS uuid)
            """
            if self.ignore_archived:
                sql += " AND lifecycle_state <> 'ARCHIVED'"
            if self.tenant_id:
                sql += " AND tenant_id = CAST(:tid AS uuid)"
                params["tid"] = self.tenant_id
            rows = self.session.execute(text(sql), params).mappings().fetchall()
            contradictions.extend({**dict(r), "kind": "singular_role_conflict"} for r in rows)

        return contradictions

    def _resolve_contradiction(
        self,
        fact: ExtractedFact,
        corroborating: List[dict],
        contradicting: List[Any],
    ) -> float:
        """Confidence after a contradiction:

        - More corroborating evidence than contradicting → tilts above 0.5
        - More contradicting evidence than corroborating → tilts below 0.5
        - Even → 0.4 (slightly pessimistic; review still required)
        """
        c_n = len(corroborating)
        x_n = len(contradicting)
        if c_n + x_n == 0:
            return 0.4
        score = 0.4 + 0.4 * (c_n - x_n) / (c_n + x_n)
        return round(max(0.05, min(score, 0.85)), 3)
