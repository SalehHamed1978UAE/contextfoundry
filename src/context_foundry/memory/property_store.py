"""PropertyStore — data access layer for property_facts (Stage 3A).

Follows the SemanticMemory pattern from memory/semantic.py:
  - Tenant-scoped via set_tenant_context() + application-level tenant_id filter
  - Lifecycle-aware (trusted_only=True by default)
  - Read-only lookups (never writes for query path)
  - Upsert for adapter path (M2)

Pure SQL via sqlalchemy.text — no ORM queries for the read path to match
the document_evidence_fallback.py pattern.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class PropertyFactRow:
    """Lightweight row object returned by lookups (no ORM dependency)."""
    id: str
    tenant_id: str
    entity_id: str
    entity_name: str
    entity_type: str
    lifecycle_state: str
    attribute_name: str
    attribute_value: str
    numeric_value: Optional[float]
    unit: Optional[str]
    value_type: Optional[str]
    period: Optional[str]
    fiscal_year: Optional[str]
    source_document_id: Optional[str]
    confidence: float


class PropertyStore:
    """Tenant-scoped data access layer for property_facts.

    Read path: lookup_attribute(), lookup_entity_properties()
    Write path: upsert_fact(), bulk_upsert() (adapter only)
    """

    def __init__(self, session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        # Set RLS context (same pattern as SemanticMemory)
        try:
            self.session.execute(
                text("SELECT platform.set_current_tenant(:tid)"),
                {"tid": tenant_id},
            )
        except Exception:
            # Fallback for environments without the platform schema
            try:
                self.session.execute(
                    text(f"SET app.current_tenant_id = '{tenant_id}'")
                )
            except Exception as e:
                logger.warning(f"[PROP_STORE] Failed to set tenant context: {e}")

    def _row_to_fact(self, row) -> PropertyFactRow:
        """Convert a raw SQL row to a PropertyFactRow."""
        return PropertyFactRow(
            id=row.id,
            tenant_id=row.tenant_id,
            entity_id=row.entity_id,
            entity_name=row.entity_name,
            entity_type=row.entity_type,
            lifecycle_state=row.lifecycle_state,
            attribute_name=row.attribute_name,
            attribute_value=row.attribute_value,
            numeric_value=row.numeric_value,
            unit=row.unit,
            value_type=row.value_type,
            period=row.period,
            fiscal_year=row.fiscal_year,
            source_document_id=row.source_document_id,
            confidence=row.confidence,
        )

    def lookup_attribute(
        self,
        attribute_name: str,
        *,
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        fiscal_year: Optional[str] = None,
        trusted_only: bool = True,
    ) -> List[PropertyFactRow]:
        """Look up property facts by attribute name.

        Tenant-scoped. Returns facts ordered by confidence DESC, entity_name ASC.
        """
        clauses = ["tenant_id = :tid", "LOWER(attribute_name) = LOWER(:attr)"]
        params: Dict[str, Any] = {"tid": self.tenant_id, "attr": attribute_name}

        if trusted_only:
            clauses.append("lifecycle_state = 'TRUSTED'")

        if entity_name:
            clauses.append("LOWER(entity_name) = LOWER(:ename)")
            params["ename"] = entity_name

        if entity_type:
            clauses.append("LOWER(entity_type) = LOWER(:etype)")
            params["etype"] = entity_type

        if fiscal_year:
            clauses.append("fiscal_year = :fy")
            params["fy"] = fiscal_year

        where = " AND ".join(clauses)
        sql = f"""
            SELECT id::text, tenant_id::text, entity_id::text, entity_name,
                   entity_type, lifecycle_state, attribute_name, attribute_value,
                   numeric_value, unit, value_type, period, fiscal_year,
                   source_document_id, confidence
            FROM property_facts
            WHERE {where}
            ORDER BY confidence DESC, entity_name ASC
        """
        rows = self.session.execute(text(sql), params).fetchall()
        return [self._row_to_fact(r) for r in rows]

    def lookup_entity_properties(
        self,
        entity_name: str,
        *,
        trusted_only: bool = True,
    ) -> List[PropertyFactRow]:
        """Look up all property facts for a given entity.

        Tenant-scoped. Returns facts ordered by attribute_name ASC.
        """
        clauses = ["tenant_id = :tid", "LOWER(entity_name) = LOWER(:ename)"]
        params: Dict[str, Any] = {"tid": self.tenant_id, "ename": entity_name}

        if trusted_only:
            clauses.append("lifecycle_state = 'TRUSTED'")

        where = " AND ".join(clauses)
        sql = f"""
            SELECT id::text, tenant_id::text, entity_id::text, entity_name,
                   entity_type, lifecycle_state, attribute_name, attribute_value,
                   numeric_value, unit, value_type, period, fiscal_year,
                   source_document_id, confidence
            FROM property_facts
            WHERE {where}
            ORDER BY attribute_name ASC
        """
        rows = self.session.execute(text(sql), params).fetchall()
        return [self._row_to_fact(r) for r in rows]

    def upsert_fact(self, fact: Dict[str, Any]) -> str:
        """Insert or update a single property fact. Returns the fact ID.

        Upsert key: (tenant_id, entity_id, attribute_name, fiscal_year).
        Used by the adapter (M2), not the query path.
        """
        fact_id = fact.get("id") or str(uuid.uuid4())
        fiscal_year = fact.get("fiscal_year") or ""

        sql = """
            INSERT INTO property_facts (
                id, tenant_id, entity_id, entity_name, entity_type,
                lifecycle_state, attribute_name, attribute_value,
                numeric_value, unit, value_type, period, fiscal_year,
                source_document_id, source_entity_properties, confidence,
                created_at, updated_at
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:eid AS uuid), :ename, :etype,
                :lstate, :attr, :aval,
                :nval, :unit, :vtype, :period, :fy,
                :sdoc, CAST(:sprops AS jsonb), :conf,
                now(), now()
            )
            ON CONFLICT (id) DO UPDATE SET
                attribute_value = EXCLUDED.attribute_value,
                numeric_value = EXCLUDED.numeric_value,
                unit = EXCLUDED.unit,
                value_type = EXCLUDED.value_type,
                period = EXCLUDED.period,
                fiscal_year = EXCLUDED.fiscal_year,
                lifecycle_state = EXCLUDED.lifecycle_state,
                confidence = EXCLUDED.confidence,
                updated_at = now()
            RETURNING CAST(id AS text) AS id
        """
        import json as _json

        params = {
            "id": fact_id,
            "tid": self.tenant_id,
            "eid": fact["entity_id"],
            "ename": fact["entity_name"],
            "etype": fact["entity_type"],
            "lstate": fact.get("lifecycle_state", "STAGING"),
            "attr": fact["attribute_name"],
            "aval": fact["attribute_value"],
            "nval": fact.get("numeric_value"),
            "unit": fact.get("unit"),
            "vtype": fact.get("value_type"),
            "period": fact.get("period"),
            "fy": fact.get("fiscal_year"),
            "sdoc": fact.get("source_document_id"),
            "sprops": _json.dumps(fact.get("source_entity_properties") or {}),
            "conf": fact.get("confidence", 0.8),
        }
        result = self.session.execute(text(sql), params)
        row = result.fetchone()
        self.session.commit()
        return row.id if row else fact_id

    def bulk_upsert(self, facts: List[Dict[str, Any]]) -> int:
        """Batch upsert property facts. Returns the number of facts upserted."""
        count = 0
        for fact in facts:
            try:
                self.upsert_fact(fact)
                count += 1
            except Exception as e:
                logger.warning(f"[PROP_STORE] Failed to upsert fact: {e}")
        return count
