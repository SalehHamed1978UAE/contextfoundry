"""
MCP Server for Context Foundry

Exposes 9 tools for agent consumption via stdio transport.
Run: python -m src.mcp_server
"""

import json
from typing import Optional
from uuid import UUID

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ContextFoundry")

# Lazy-initialized singletons
_db_manager = None
_embedding_service = None
_document_embedder = None


async def _ensure_initialized():
    """Connect to DB and initialize services on first tool call."""
    global _db_manager, _embedding_service, _document_embedder

    if _db_manager is not None:
        return

    from src.db.connection import init_databases, db_manager
    from src.utils.embeddings import EmbeddingService, DocumentEmbedder

    await init_databases()
    _db_manager = db_manager
    _embedding_service = EmbeddingService(use_ollama=False)
    _document_embedder = DocumentEmbedder(_db_manager, _embedding_service)


def _json(data) -> str:
    return json.dumps(data, default=str)


# ─── Tools ────────────────────────────────────────────────────────────


@mcp.tool()
async def query_knowledge_base(query: str, session_id: Optional[str] = None) -> str:
    """Run a full tri-memory query (retrieval + LLM reasoning + validation)."""
    await _ensure_initialized()

    from src.agents.retrieval import RetrievalAgent
    from src.agents.reasoning import ReasoningAgent
    from src.agents.validation import ValidationAgent

    retrieval = RetrievalAgent(_db_manager, _document_embedder)
    reasoning = ReasoningAgent(_db_manager)
    validation = ValidationAgent(_db_manager)

    bundle = await retrieval.build_context_bundle(query=query, session_id=session_id)
    response = await reasoning.reason(bundle)
    await validation.validate(response, bundle)

    return _json(response.model_dump(mode="json"))


@mcp.tool()
async def search_entities(
    type: Optional[str] = None,
    name: Optional[str] = None,
    state: str = "TRUSTED",
    min_confidence: float = 0.0,
    limit: int = 50,
) -> str:
    """Search entities in the knowledge graph."""
    await _ensure_initialized()

    conditions = ["lifecycle_state = $1", "confidence >= $2"]
    params: list = [state, min_confidence]
    idx = 3

    if type:
        conditions.append(f"entity_type = ${idx}")
        params.append(type)
        idx += 1
    if name:
        conditions.append(f"extracted_text ILIKE ${idx}")
        params.append(f"%{name}%")
        idx += 1

    where = " AND ".join(conditions)

    async with _db_manager.get_postgres_connection() as conn:
        rows = await conn.fetch(
            f"""SELECT entity_id, entity_type, lifecycle_state,
                       confidence, extracted_text, source_document_id
                FROM graph_lifecycle WHERE {where}
                ORDER BY confidence DESC LIMIT ${idx}""",
            *params, limit,
        )

    return _json([dict(r) for r in rows])


@mcp.tool()
async def get_entity(entity_id: str) -> str:
    """Get a single entity by UUID, including its relationships."""
    await _ensure_initialized()

    eid = UUID(entity_id)
    async with _db_manager.get_postgres_connection() as conn:
        row = await conn.fetchrow(
            """SELECT entity_id, entity_type, lifecycle_state,
                      confidence, extracted_text, source_document_id
               FROM graph_lifecycle WHERE entity_id = $1""",
            eid,
        )
        if not row:
            return _json({"error": "Entity not found"})

        rels = await conn.fetch(
            """SELECT rm.relationship_id, rm.source_entity_id, rm.target_entity_id,
                      rm.relationship_type, rm.confidence,
                      src.extracted_text AS source_name,
                      tgt.extracted_text AS target_name
               FROM relationship_metadata rm
               JOIN graph_lifecycle src ON rm.source_entity_id = src.entity_id
               JOIN graph_lifecycle tgt ON rm.target_entity_id = tgt.entity_id
               WHERE rm.source_entity_id = $1 OR rm.target_entity_id = $1""",
            eid,
        )

    data = dict(row)
    data["relationships"] = [dict(r) for r in rels]
    return _json(data)


@mcp.tool()
async def search_documents(query: str, top_k: int = 10) -> str:
    """Vector similarity search across documents."""
    await _ensure_initialized()
    results = await _document_embedder.search_similar(query=query, top_k=top_k)
    return _json(results)


@mcp.tool()
async def search_documents_by_text(
    query: Optional[str] = None,
    title: Optional[str] = None,
    doc_type: Optional[str] = None,
    limit: int = 50,
) -> str:
    """Keyword search across document chunks."""
    await _ensure_initialized()

    conditions: list[str] = []
    params: list = []
    idx = 1

    if query:
        conditions.append(f"(chunk_text ILIKE ${idx} OR document_title ILIKE ${idx})")
        params.append(f"%{query}%")
        idx += 1
    if title:
        conditions.append(f"document_title ILIKE ${idx}")
        params.append(f"%{title}%")
        idx += 1
    if doc_type:
        conditions.append(f"document_type = ${idx}")
        params.append(doc_type)
        idx += 1

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    async with _db_manager.get_postgres_connection() as conn:
        rows = await conn.fetch(
            f"""SELECT id, document_id, document_type, document_title,
                       chunk_text, chunk_index
                FROM document_embeddings{where}
                ORDER BY document_id, chunk_index
                LIMIT ${idx}""",
            *params, limit,
        )

    return _json([dict(r) for r in rows])


@mcp.tool()
async def get_document(document_id: str) -> str:
    """Get all chunks for a specific document, ordered by chunk_index."""
    await _ensure_initialized()

    async with _db_manager.get_postgres_connection() as conn:
        rows = await conn.fetch(
            """SELECT id, document_id, document_type, document_title,
                      chunk_text, chunk_index
               FROM document_embeddings
               WHERE document_id = $1
               ORDER BY chunk_index""",
            document_id,
        )

    if not rows:
        return _json({"error": "Document not found"})

    return _json([dict(r) for r in rows])


@mcp.tool()
async def search_relationships(
    source_type: Optional[str] = None,
    target_type: Optional[str] = None,
    relationship_type: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 50,
) -> str:
    """Search relationships in the knowledge graph."""
    await _ensure_initialized()

    conditions = ["rm.confidence >= $1"]
    params: list = [min_confidence]
    idx = 2

    if source_type:
        conditions.append(f"src.entity_type = ${idx}")
        params.append(source_type)
        idx += 1
    if target_type:
        conditions.append(f"tgt.entity_type = ${idx}")
        params.append(target_type)
        idx += 1
    if relationship_type:
        conditions.append(f"rm.relationship_type = ${idx}")
        params.append(relationship_type)
        idx += 1

    where = " AND ".join(conditions)

    async with _db_manager.get_postgres_connection() as conn:
        rows = await conn.fetch(
            f"""SELECT rm.relationship_id, rm.source_entity_id, rm.target_entity_id,
                       rm.relationship_type, rm.confidence,
                       src.extracted_text AS source_name, src.entity_type AS source_type,
                       tgt.extracted_text AS target_name, tgt.entity_type AS target_type
                FROM relationship_metadata rm
                JOIN graph_lifecycle src ON rm.source_entity_id = src.entity_id
                JOIN graph_lifecycle tgt ON rm.target_entity_id = tgt.entity_id
                WHERE {where}
                ORDER BY rm.confidence DESC LIMIT ${idx}""",
            *params, limit,
        )

    return _json([dict(r) for r in rows])


@mcp.tool()
async def get_system_stats() -> str:
    """Get system statistics (entity/relationship/document/query counts)."""
    await _ensure_initialized()

    async with _db_manager.get_postgres_connection() as conn:
        entity_stats = await conn.fetch(
            "SELECT lifecycle_state, COUNT(*) as count FROM graph_lifecycle GROUP BY lifecycle_state"
        )
        entities_by_state = {row["lifecycle_state"]: row["count"] for row in entity_stats}

        rel_count = await conn.fetchval("SELECT COUNT(*) FROM relationship_metadata") or 0
        query_count = await conn.fetchval("SELECT COUNT(*) FROM query_responses") or 0
        feedback_count = await conn.fetchval("SELECT COUNT(*) FROM feedback_records") or 0
        doc_count = await conn.fetchval("SELECT COUNT(DISTINCT document_id) FROM document_embeddings") or 0

    return _json({
        "entities_total": sum(entities_by_state.values()),
        "entities_trusted": entities_by_state.get("TRUSTED", 0),
        "entities_staging": entities_by_state.get("STAGING", 0),
        "entities_archived": entities_by_state.get("ARCHIVED", 0),
        "relationships_total": rel_count,
        "documents_embedded": doc_count,
        "queries_processed": query_count,
        "feedback_records": feedback_count,
    })


@mcp.tool()
async def submit_feedback(
    response_id: str,
    judgment: str,
    human_correction: Optional[str] = None,
    severity: Optional[str] = None,
) -> str:
    """Submit human feedback on a query response."""
    await _ensure_initialized()
    import uuid as _uuid
    from src.agents.gardener import GardenerAgent

    valid = {"correct", "incorrect", "partial", "uncertain"}
    if judgment not in valid:
        return _json({"error": f"judgment must be one of {valid}"})

    gardener = GardenerAgent(_db_manager)
    async with _db_manager.get_postgres_connection() as conn:
        resp_row = await conn.fetchrow(
            """SELECT qr.answer, qr.bundle_id, cb.query_text, cb.semantic_entities
               FROM query_responses qr
               JOIN context_bundles cb ON qr.bundle_id = cb.id
               WHERE qr.id = $1""",
            _uuid.UUID(response_id),
        )
        if not resp_row:
            return _json({"error": "Response not found"})

        entities_involved = []
        if resp_row["semantic_entities"]:
            entities = json.loads(resp_row["semantic_entities"])
            entities_involved = [
                _uuid.UUID(e["entity_id"]) for e in entities if e.get("entity_id")
            ]

        await conn.execute(
            """INSERT INTO feedback_records
               (id, bundle_id, query_text, response_text, judgment,
                human_correction, severity, entities_involved)
               VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7)""",
            resp_row["bundle_id"],
            resp_row["query_text"],
            resp_row["answer"],
            judgment,
            human_correction,
            severity,
            entities_involved or None,
        )

        confidence_effect = ""
        if entities_involved:
            if judgment == "correct":
                for eid in entities_involved:
                    await gardener.increase_confidence(str(eid), 0.03, f"correct_feedback:{response_id}")
                confidence_effect = f"+0.03 to {len(entities_involved)} entities"
            elif judgment in ("incorrect", "partial"):
                delta = 0.05 if judgment == "incorrect" else 0.02
                for eid in entities_involved:
                    await gardener.decrease_confidence(str(eid), delta, f"{judgment}_feedback:{response_id}")
                confidence_effect = f"-{delta} to {len(entities_involved)} entities"

    return _json({
        "status": "recorded",
        "response_id": response_id,
        "judgment": judgment,
        "confidence_effect": confidence_effect,
    })


# ─── Entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
