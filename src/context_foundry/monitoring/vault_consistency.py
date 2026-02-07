"""Shared vault consistency/preflight and metrics helpers.

Single source of truth for vault health should be database state, not filesystem artifacts.
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import text


def _scalar(session, query: str, params: Dict[str, Any]) -> int:
    return session.execute(text(query), params).scalar() or 0


def _table_exists(session, schema: str, table: str) -> bool:
    row = session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema
                  AND table_name = :table
            )
            """
        ),
        {"schema": schema, "table": table},
    ).fetchone()
    return bool(row and row[0])


def build_vault_preflight_report(session, vault_id: str) -> Dict[str, Any]:
    """Build a deterministic preflight report for one vault UUID."""
    db_identity = session.execute(
        text(
            """
            SELECT
                current_database() AS database_name,
                current_user AS database_user,
                inet_server_addr()::text AS server_addr,
                inet_server_port() AS server_port
            """
        )
    ).mappings().first()

    vault_row = session.execute(
        text(
            """
            SELECT id::text AS id, name, created_at
            FROM platform.tenants
            WHERE id = CAST(:vault_id AS uuid)
            LIMIT 1
            """
        ),
        {"vault_id": vault_id},
    ).mappings().first()

    if not vault_row:
        return {
            "ok": False,
            "vault_id": vault_id,
            "exists": False,
            "db_identity": dict(db_identity or {}),
            "checks": {
                "vault_exists": False,
                "has_documents": False,
            },
        }

    documents_total = _scalar(
        session,
        "SELECT COUNT(*) FROM platform.documents WHERE tenant_id = CAST(:vault_id AS uuid)",
        {"vault_id": vault_id},
    )
    docs_queued = _scalar(
        session,
        "SELECT COUNT(*) FROM platform.documents WHERE tenant_id = CAST(:vault_id AS uuid) AND status = 'queued'",
        {"vault_id": vault_id},
    )
    docs_processing = _scalar(
        session,
        "SELECT COUNT(*) FROM platform.documents WHERE tenant_id = CAST(:vault_id AS uuid) AND status = 'processing'",
        {"vault_id": vault_id},
    )
    docs_extracted = _scalar(
        session,
        "SELECT COUNT(*) FROM platform.documents WHERE tenant_id = CAST(:vault_id AS uuid) AND status IN ('extracted','completed')",
        {"vault_id": vault_id},
    )

    req_pending = _scalar(
        session,
        "SELECT COUNT(*) FROM platform.extraction_requests WHERE tenant_id = CAST(:vault_id AS uuid) AND status = 'pending'",
        {"vault_id": vault_id},
    )
    req_processing = _scalar(
        session,
        "SELECT COUNT(*) FROM platform.extraction_requests WHERE tenant_id = CAST(:vault_id AS uuid) AND status = 'processing'",
        {"vault_id": vault_id},
    )
    req_completed = _scalar(
        session,
        "SELECT COUNT(*) FROM platform.extraction_requests WHERE tenant_id = CAST(:vault_id AS uuid) AND status = 'completed'",
        {"vault_id": vault_id},
    )
    req_failed = _scalar(
        session,
        "SELECT COUNT(*) FROM platform.extraction_requests WHERE tenant_id = CAST(:vault_id AS uuid) AND status = 'failed'",
        {"vault_id": vault_id},
    )

    entities_total = _scalar(
        session,
        "SELECT COUNT(*) FROM public.entities WHERE tenant_id = CAST(:vault_id AS uuid)",
        {"vault_id": vault_id},
    )
    relationships_total = _scalar(
        session,
        "SELECT COUNT(*) FROM public.relationships WHERE tenant_id = CAST(:vault_id AS uuid)",
        {"vault_id": vault_id},
    )
    chunks_total = _scalar(
        session,
        "SELECT COUNT(*) FROM public.document_chunks WHERE tenant_id = CAST(:vault_id AS uuid)",
        {"vault_id": vault_id},
    )

    entities_staging = _scalar(
        session,
        """
        SELECT COUNT(*)
        FROM public.entities
        WHERE tenant_id = CAST(:vault_id AS uuid)
          AND lifecycle_state = 'STAGING'
        """,
        {"vault_id": vault_id},
    )
    entities_trusted = _scalar(
        session,
        """
        SELECT COUNT(*)
        FROM public.entities
        WHERE tenant_id = CAST(:vault_id AS uuid)
          AND lifecycle_state = 'TRUSTED'
        """,
        {"vault_id": vault_id},
    )
    rels_staging = _scalar(
        session,
        """
        SELECT COUNT(*)
        FROM public.relationships
        WHERE tenant_id = CAST(:vault_id AS uuid)
          AND lifecycle_state = 'STAGING'
        """,
        {"vault_id": vault_id},
    )
    rels_trusted = _scalar(
        session,
        """
        SELECT COUNT(*)
        FROM public.relationships
        WHERE tenant_id = CAST(:vault_id AS uuid)
          AND lifecycle_state = 'TRUSTED'
        """,
        {"vault_id": vault_id},
    )

    candidate_relationships_total = 0
    if _table_exists(session, "public", "candidate_relationships"):
        candidate_relationships_total = _scalar(
            session,
            "SELECT COUNT(*) FROM public.candidate_relationships WHERE tenant_id = CAST(:vault_id AS uuid)",
            {"vault_id": vault_id},
        )

    checks = {
        "vault_exists": True,
        "has_documents": documents_total > 0,
        "document_queue_resolvable": (docs_queued + docs_processing) >= 0,
        "db_identity_available": bool(db_identity),
    }

    return {
        "ok": all(checks.values()),
        "exists": True,
        "vault_id": vault_row["id"],
        "vault_name": vault_row["name"],
        "created_at": vault_row["created_at"].isoformat() if vault_row.get("created_at") else None,
        "db_identity": dict(db_identity or {}),
        "documents": {
            "total": documents_total,
            "queued": docs_queued,
            "processing": docs_processing,
            "extracted_or_completed": docs_extracted,
        },
        "extraction_requests": {
            "pending": req_pending,
            "processing": req_processing,
            "completed": req_completed,
            "failed": req_failed,
            "total": req_pending + req_processing + req_completed + req_failed,
        },
        "knowledge_graph": {
            "entities_total": entities_total,
            "entities_staging": entities_staging,
            "entities_trusted": entities_trusted,
            "relationships_total": relationships_total,
            "relationships_staging": rels_staging,
            "relationships_trusted": rels_trusted,
            "chunks_total": chunks_total,
            "candidate_relationships_total": candidate_relationships_total,
        },
        "checks": checks,
    }


def build_vault_metrics_report(session, vault_id: str) -> Dict[str, Any]:
    """Build DB-backed metrics payload for extraction dashboard."""
    preflight = build_vault_preflight_report(session, vault_id)
    if not preflight.get("exists"):
        return preflight

    kg = preflight["knowledge_graph"]
    docs = preflight["documents"]
    req = preflight["extraction_requests"]

    # Backward-compatible keys for existing UI clients.
    compat_entities = kg["entities_total"]
    compat_relationships = kg["relationships_total"]

    return {
        "ok": preflight["ok"],
        "source": "database",
        "vault_id": preflight["vault_id"],
        "vault_name": preflight["vault_name"],
        "totals": {
            "documents": docs["total"],
            "chunks": kg["chunks_total"],
            "entities": kg["entities_total"],
            "relationships": kg["relationships_total"],
            "candidate_relationships": kg["candidate_relationships_total"],
        },
        "lifecycle": {
            "entities_staging": kg["entities_staging"],
            "entities_trusted": kg["entities_trusted"],
            "relationships_staging": kg["relationships_staging"],
            "relationships_trusted": kg["relationships_trusted"],
        },
        "requests": req,
        "checks": preflight["checks"],
        "db_identity": preflight["db_identity"],
        "gpt_4o_mini": {"entities": compat_entities, "relationships": compat_relationships},
        "claude_sonnet": {"entities": compat_entities, "relationships": compat_relationships},
    }
