from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import uvicorn
import uuid

from src.config import settings
from src.db.connection import init_databases, close_databases, db_manager
from src.models.schemas import (
    QueryRequest, QueryResponse,
    EntityResponse, EntityDetailResponse, EntityListResponse,
    RelationshipResponse, RelationshipListResponse,
    DocumentChunkResponse, DocumentListResponse,
    SimilarDocumentResponse, DocumentSearchResponse,
)
from src.agents.retrieval import RetrievalAgent
from src.agents.reasoning import ReasoningAgent
from src.agents.validation import ValidationAgent
from src.utils.embeddings import EmbeddingService, DocumentEmbedder
from src.utils.llm import LLMClient


# Global agents (initialized on startup)
retrieval_agent = None
reasoning_agent = None
validation_agent = None
document_embedder = None
semantic_cache = None
scheduler = None


async def _scheduled_maintenance():
    """Run gardener maintenance tasks."""
    from src.agents.gardener import GardenerAgent
    from src.agents.extraction import ExtractionAgent

    gardener = GardenerAgent(db_manager)
    extractor = ExtractionAgent(db_manager)

    try:
        conflicts = await gardener.detect_conflicts()
    except Exception:
        conflicts = []

    try:
        stale = await gardener.get_stale_entities(days_threshold=90)
    except Exception:
        stale = []

    evolution = await extractor.rule_evolver()

    # Also run cache and working-memory cleanup
    if semantic_cache:
        await semantic_cache.cleanup_expired()

    try:
        from src.memory.working_memory import WorkingMemory
        wm = WorkingMemory(db_manager)
        await wm.cleanup_expired()
    except Exception:
        pass

    print(
        f"[maintenance] conflicts={len(conflicts)} stale={len(stale)} "
        f"rules_disabled={len(evolution['disabled'])} "
        f"rules_promoted={len(evolution['promoted'])} "
        f"rules_demoted={len(evolution['demoted'])}"
    )
    return {
        "conflicts": conflicts,
        "stale": stale,
        "rule_evolution": evolution,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global retrieval_agent, reasoning_agent, validation_agent, document_embedder, semantic_cache, scheduler

    # Startup
    print("\n" + "="*50)
    print("Context Foundry - Tri-Memory Architecture")
    print("="*50 + "\n")

    try:
        await init_databases()

        # Initialize agents
        print("Initializing agents...")
        embedding_service = EmbeddingService(use_ollama=False)
        document_embedder = DocumentEmbedder(db_manager, embedding_service)
        retrieval_agent = RetrievalAgent(db_manager, document_embedder)
        reasoning_agent = ReasoningAgent(db_manager)
        validation_agent = ValidationAgent(db_manager)

        # Initialize cache
        from src.utils.cache import SemanticCache
        redis_client = await db_manager.get_redis_client()
        semantic_cache = SemanticCache(db_manager, embedding_service, redis_client)
        await semantic_cache.ensure_table()
        print("✓ Semantic cache initialized")

        # Initialize scheduler
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            _scheduled_maintenance, "interval", hours=6, id="maintenance"
        )
        scheduler.start()
        print("✓ Scheduler initialized (maintenance every 6h)")

        print("✓ All agents initialized")
        print("\n✓ All systems operational\n")
    except Exception as e:
        print(f"\n✗ Initialization failed: {e}\n")
        raise

    yield

    # Shutdown
    print("\n" + "="*50)
    print("Shutting down Context Foundry")
    print("="*50 + "\n")
    if scheduler:
        scheduler.shutdown(wait=False)
    await close_databases()


app = FastAPI(
    title="Context Foundry",
    description="Tri-Memory Cognitive Architecture for Enterprise Operations",
    version="0.1.0-mvp",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Context Foundry",
        "version": "0.1.0-mvp",
        "status": "operational",
        "architecture": "tri-memory (semantic + episodic + symbolic)"
    }


@app.get("/health")
async def health():
    """Detailed health check"""

    # Check LLM
    llm_client = LLMClient()
    ollama_status = "connected" if await llm_client.health_check() else "disconnected"

    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected",
        "ollama": ollama_status,
        "graph_name": settings.graph_name,
        "agents": {
            "retrieval": retrieval_agent is not None,
            "reasoning": reasoning_agent is not None,
            "validation": validation_agent is not None
        }
    }


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Execute a query through the full tri-memory pipeline

    Pipeline:
    1. Retrieval Agent builds ContextBundle from tri-memory
    2. Reasoning Agent generates response with LLM
    3. Validation Agent checks symbolic rules
    4. Store results and return
    """

    if not all([retrieval_agent, reasoning_agent, validation_agent]):
        raise HTTPException(
            status_code=503,
            detail="System not fully initialized"
        )

    try:
        # Check cache first
        if semantic_cache:
            cached = await semantic_cache.get(request.query)
            if cached:
                from src.models.schemas import ReasoningResponse as RR
                return QueryResponse(
                    success=True,
                    response=RR(**cached),
                    error=None,
                )

        # Step 1: Build context bundle
        bundle = await retrieval_agent.build_context_bundle(
            query=request.query,
            session_id=str(request.session_id) if request.session_id else None
        )

        # Step 2: Generate reasoning response
        response = await reasoning_agent.reason(bundle)

        # Step 3: Validate against rules
        passed, violations = await validation_agent.validate(response, bundle)

        # Record validation
        await validation_agent.record_validation(response, passed, violations)

        # Step 4: Store bundle and response in database
        await _store_query_results(bundle, response)

        # Step 5: Store session memory for multi-turn conversations
        if request.session_id:
            await _store_session_memory(
                str(request.session_id),
                request.query,
                response.answer
            )

        # Step 5.5: Knowledge file-back
        try:
            from src.agents.knowledge_fileback import KnowledgeFileBack
            fileback = KnowledgeFileBack(db_manager)
            await fileback.process(request.query, response, bundle)
        except Exception:
            pass  # File-back failure must not block query response

        # Step 6: Cache the response
        if semantic_cache:
            await semantic_cache.put(
                request.query,
                response.model_dump(mode="json"),
                response.confidence,
            )

        return QueryResponse(
            success=True,
            response=response,
            error=None
        )

    except Exception as e:
        return QueryResponse(
            success=False,
            response=None,
            error={
                "type": type(e).__name__,
                "message": str(e),
                "details": "Query pipeline failed"
            }
        )


async def _store_query_results(bundle, response):
    """Store query results in database"""
    import json

    async with db_manager.get_postgres_connection() as conn:
        # Store context bundle
        await conn.execute("""
            INSERT INTO context_bundles (
                id,
                query_text,
                session_id,
                semantic_entities,
                semantic_relationships,
                episodic_documents,
                symbolic_rules_applied,
                session_context,
                overall_confidence,
                recommendation,
                high_confidence_facts,
                medium_confidence_facts,
                low_confidence_facts,
                low_confidence_items,
                unresolved_entities,
                missing_relationships,
                stale_facts,
                uncertainty_reasons,
                retrieval_latency_ms
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
        """,
            bundle.id,
            bundle.query_text,
            bundle.session_id,
            json.dumps(bundle.semantic_entities),
            json.dumps(bundle.semantic_relationships),
            json.dumps(bundle.episodic_documents),
            json.dumps(bundle.symbolic_rules_applied),
            json.dumps(bundle.session_context),
            bundle.uncertainty.overall_confidence,
            bundle.uncertainty.recommendation.value,
            bundle.uncertainty.high_confidence_facts,
            bundle.uncertainty.medium_confidence_facts,
            bundle.uncertainty.low_confidence_facts,
            json.dumps([item.dict() for item in bundle.uncertainty.low_confidence_items]),
            bundle.uncertainty.unresolved_entities,
            bundle.uncertainty.missing_relationships,
            json.dumps(bundle.uncertainty.stale_facts),
            bundle.uncertainty.uncertainty_reasons,
            bundle.retrieval_latency_ms
        )

        # Store query response
        await conn.execute("""
            INSERT INTO query_responses (
                id,
                bundle_id,
                answer,
                confidence,
                confidence_level,
                uncertain_facts,
                uncertainty_reasons,
                would_help,
                caveats,
                evidence_chain,
                rules_checked,
                rules_passed,
                validation_failures,
                alternatives,
                total_latency_ms
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        """,
            response.id,
            response.bundle_id,
            response.answer,
            response.confidence,
            response.confidence_level.value,
            response.uncertain_facts,
            response.uncertainty_reasons,
            response.would_help,
            response.caveats,
            json.dumps([item.dict() for item in response.evidence_chain]),
            response.rules_checked,
            response.rules_passed,
            json.dumps(response.validation_failures),
            json.dumps([alt.dict() for alt in response.alternatives]),
            response.total_latency_ms
        )


async def _store_session_memory(session_id: str, query: str, answer: str):
    """Store query/response in session memory for multi-turn context"""
    async with db_manager.get_postgres_connection() as conn:
        await conn.execute("""
            INSERT INTO session_memory (id, session_id, query_text, response_text)
            VALUES (gen_random_uuid(), $1, $2, $3)
        """, uuid.UUID(session_id), query, answer)


@app.post("/feedback")
async def submit_feedback(feedback: dict):
    """
    Submit human feedback on a query response.

    Expected payload:
    {
        "response_id": "uuid of the query response",
        "judgment": "correct" | "incorrect" | "partial" | "uncertain",
        "human_correction": "optional corrected answer",
        "severity": "critical" | "major" | "minor" (for incorrect/partial)
    }
    """
    import json as json_mod
    from src.agents.gardener import GardenerAgent

    response_id = feedback.get("response_id")
    judgment = feedback.get("judgment")
    human_correction = feedback.get("human_correction", "")
    severity = feedback.get("severity")

    valid_judgments = ["correct", "incorrect", "partial", "uncertain"]
    if not response_id or judgment not in valid_judgments:
        raise HTTPException(
            status_code=400,
            detail=f"Required: response_id (uuid) and judgment ({'/'.join(valid_judgments)})"
        )

    try:
        gardener = GardenerAgent(db_manager)
        async with db_manager.get_postgres_connection() as conn:
            # Look up the original query and response
            resp_row = await conn.fetchrow("""
                SELECT qr.answer, qr.bundle_id, cb.query_text, cb.semantic_entities
                FROM query_responses qr
                JOIN context_bundles cb ON qr.bundle_id = cb.id
                WHERE qr.id = $1
            """, uuid.UUID(response_id))

            if not resp_row:
                raise HTTPException(status_code=404, detail="Response not found")

            # Store feedback record
            entities_involved = []
            if resp_row['semantic_entities']:
                entities = json_mod.loads(resp_row['semantic_entities'])
                entities_involved = [uuid.UUID(e['entity_id']) for e in entities if e.get('entity_id')]

            await conn.execute("""
                INSERT INTO feedback_records (
                    id, bundle_id, query_text, response_text, judgment,
                    human_correction, severity, entities_involved
                ) VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7)
            """,
                resp_row['bundle_id'],
                resp_row['query_text'],
                resp_row['answer'],
                judgment,
                human_correction or None,
                severity,
                entities_involved or None
            )

            # Adjust entity confidence based on judgment
            confidence_effect = ""
            if entities_involved:
                if judgment == "correct":
                    delta = 0.03
                    for eid in entities_involved:
                        await gardener.increase_confidence(str(eid), delta, f"correct_feedback:{response_id}")
                    confidence_effect = f"+{delta} to {len(entities_involved)} entities"
                elif judgment in ("incorrect", "partial"):
                    delta = 0.05 if judgment == "incorrect" else 0.02
                    for eid in entities_involved:
                        await gardener.decrease_confidence(str(eid), delta, f"{judgment}_feedback:{response_id}")
                    confidence_effect = f"-{delta} to {len(entities_involved)} entities"

        return {
            "status": "recorded",
            "response_id": response_id,
            "judgment": judgment,
            "confidence_effect": confidence_effect
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get system statistics"""

    async with db_manager.get_postgres_connection() as conn:
        # Entity counts by lifecycle
        entity_stats = await conn.fetch("""
            SELECT lifecycle_state, COUNT(*) as count
            FROM graph_lifecycle
            GROUP BY lifecycle_state
        """)

        entities_by_state = {row["lifecycle_state"]: row["count"] for row in entity_stats}

        # Relationship count
        rel_count = await conn.fetchval("SELECT COUNT(*) FROM relationship_metadata") or 0

        # Query count
        query_count = await conn.fetchval("SELECT COUNT(*) FROM query_responses") or 0

        # Feedback count
        feedback_count = await conn.fetchval("SELECT COUNT(*) FROM feedback_records") or 0

        # Document embeddings count
        doc_count = await conn.fetchval("SELECT COUNT(DISTINCT document_id) FROM document_embeddings") or 0

        return {
            "entities_total": sum(entities_by_state.values()),
            "entities_trusted": entities_by_state.get("TRUSTED", 0),
            "entities_staging": entities_by_state.get("STAGING", 0),
            "entities_archived": entities_by_state.get("ARCHIVED", 0),
            "relationships_total": rel_count,
            "documents_embedded": doc_count,
            "queries_processed": query_count,
            "feedback_records": feedback_count
        }


# ============================================
# STRUCTURED QUERY ENDPOINTS
# ============================================

@app.get("/entities", response_model=EntityListResponse)
async def list_entities(
    type: str = None,
    name: str = None,
    state: str = "TRUSTED",
    min_confidence: float = 0.0,
    limit: int = 50,
    offset: int = 0,
):
    """Search entities in the knowledge graph."""
    conditions = ["lifecycle_state = $1", "confidence >= $2"]
    params = [state, min_confidence]
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

    async with db_manager.get_postgres_connection() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM graph_lifecycle WHERE {where}", *params
        )
        rows = await conn.fetch(
            f"""SELECT entity_id, entity_type, lifecycle_state,
                       confidence, extracted_text, source_document_id,
                       created_at, updated_at
                FROM graph_lifecycle
                WHERE {where}
                ORDER BY confidence DESC
                LIMIT ${idx} OFFSET ${idx + 1}""",
            *params, limit, offset,
        )

    return EntityListResponse(
        entities=[EntityResponse(**dict(r)) for r in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@app.get("/entities/{entity_id}", response_model=EntityDetailResponse)
async def get_entity(entity_id: uuid.UUID):
    """Get a single entity with its relationships."""
    async with db_manager.get_postgres_connection() as conn:
        row = await conn.fetchrow(
            """SELECT entity_id, entity_type, lifecycle_state,
                      confidence, extracted_text, source_document_id,
                      created_at, updated_at
               FROM graph_lifecycle WHERE entity_id = $1""",
            entity_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Entity not found")

        rels = await conn.fetch(
            """SELECT rm.relationship_id, rm.source_entity_id, rm.target_entity_id,
                      rm.relationship_type, rm.confidence, rm.lifecycle_state,
                      src.extracted_text AS source_entity_name,
                      src.entity_type AS source_entity_type,
                      tgt.extracted_text AS target_entity_name,
                      tgt.entity_type AS target_entity_type
               FROM relationship_metadata rm
               JOIN graph_lifecycle src ON rm.source_entity_id = src.entity_id
               JOIN graph_lifecycle tgt ON rm.target_entity_id = tgt.entity_id
               WHERE rm.source_entity_id = $1 OR rm.target_entity_id = $1""",
            entity_id,
        )

    entity_data = dict(row)
    entity_data["relationships"] = [dict(r) for r in rels]
    return EntityDetailResponse(**entity_data)


@app.get("/relationships", response_model=RelationshipListResponse)
async def list_relationships(
    source_type: str = None,
    target_type: str = None,
    relationship_type: str = None,
    min_confidence: float = 0.0,
    limit: int = 50,
    offset: int = 0,
):
    """Search relationships in the knowledge graph."""
    conditions = ["rm.confidence >= $1"]
    params = [min_confidence]
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

    async with db_manager.get_postgres_connection() as conn:
        total = await conn.fetchval(
            f"""SELECT COUNT(*) FROM relationship_metadata rm
                JOIN graph_lifecycle src ON rm.source_entity_id = src.entity_id
                JOIN graph_lifecycle tgt ON rm.target_entity_id = tgt.entity_id
                WHERE {where}""",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT rm.relationship_id, rm.source_entity_id, rm.target_entity_id,
                       rm.relationship_type, rm.confidence, rm.lifecycle_state,
                       src.extracted_text AS source_entity_name,
                       src.entity_type AS source_entity_type,
                       tgt.extracted_text AS target_entity_name,
                       tgt.entity_type AS target_entity_type
                FROM relationship_metadata rm
                JOIN graph_lifecycle src ON rm.source_entity_id = src.entity_id
                JOIN graph_lifecycle tgt ON rm.target_entity_id = tgt.entity_id
                WHERE {where}
                ORDER BY rm.confidence DESC
                LIMIT ${idx} OFFSET ${idx + 1}""",
            *params, limit, offset,
        )

    return RelationshipListResponse(
        relationships=[RelationshipResponse(**dict(r)) for r in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@app.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    query: str = None,
    title: str = None,
    doc_type: str = None,
    limit: int = 50,
    offset: int = 0,
):
    """Search document chunks by keyword."""
    conditions = []
    params = []
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

    async with db_manager.get_postgres_connection() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM document_embeddings{where}", *params
        )
        rows = await conn.fetch(
            f"""SELECT id, document_id, document_type, document_title,
                       chunk_text, chunk_index, created_at
                FROM document_embeddings{where}
                ORDER BY document_id, chunk_index
                LIMIT ${idx} OFFSET ${idx + 1}""",
            *params, limit, offset,
        )

    return DocumentListResponse(
        documents=[DocumentChunkResponse(**dict(r)) for r in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@app.get("/documents/search", response_model=DocumentSearchResponse)
async def search_documents_vector(query: str, top_k: int = 10):
    """Vector similarity search across documents."""
    if document_embedder is None:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    results = await document_embedder.search_similar(query=query, top_k=top_k)
    return DocumentSearchResponse(
        results=[SimilarDocumentResponse(**r) for r in results],
        query=query,
        top_k=top_k,
    )


@app.get("/documents/{document_id}", response_model=DocumentListResponse)
async def get_document(document_id: str):
    """Get all chunks for a specific document."""
    async with db_manager.get_postgres_connection() as conn:
        rows = await conn.fetch(
            """SELECT id, document_id, document_type, document_title,
                      chunk_text, chunk_index, created_at
               FROM document_embeddings
               WHERE document_id = $1
               ORDER BY chunk_index""",
            document_id,
        )

    if not rows:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentListResponse(
        documents=[DocumentChunkResponse(**dict(r)) for r in rows],
        total=len(rows),
        limit=len(rows),
        offset=0,
    )


@app.post("/admin/reset")
async def admin_reset():
    """
    Reset all data tables for fresh corpus ingestion.
    WARNING: Destructive operation - clears everything.
    """
    async with db_manager.get_postgres_connection() as conn:
        await conn.execute("TRUNCATE TABLE feedback_records CASCADE")
        await conn.execute("TRUNCATE TABLE query_responses CASCADE")
        await conn.execute("TRUNCATE TABLE context_bundles CASCADE")
        await conn.execute("TRUNCATE TABLE session_memory CASCADE")
        await conn.execute("TRUNCATE TABLE document_embeddings CASCADE")
        await conn.execute("TRUNCATE TABLE relationship_metadata CASCADE")
        await conn.execute("TRUNCATE TABLE graph_lifecycle CASCADE")
        await conn.execute("TRUNCATE TABLE symbolic_rules CASCADE")

        # Fix embedding column dimension for local model (384-dim BGE)
        try:
            await conn.execute("ALTER TABLE document_embeddings ALTER COLUMN embedding TYPE vector(384)")
        except Exception:
            pass  # Column may already be correct

        # Drop and recreate AGE graph
        await conn.execute("LOAD 'age'")
        await conn.execute("SET search_path = ag_catalog, '$user', public")
        try:
            await conn.execute("SELECT drop_graph('cf_knowledge', true)")
        except Exception:
            pass
        await conn.execute("SELECT create_graph('cf_knowledge')")

    return {"status": "reset_complete", "message": "All data tables cleared"}


@app.post("/admin/maintenance")
async def admin_maintenance():
    """Trigger scheduled maintenance on demand."""
    try:
        result = await _scheduled_maintenance()
        return {
            "status": "maintenance_complete",
            "conflicts": len(result["conflicts"]),
            "stale_entities": len(result["stale"]),
            "rule_evolution": result["rule_evolution"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/ingest")
async def admin_ingest(payload: dict):
    """
    Bulk ingest documents for embedding.

    Expected payload:
    {
        "documents": [
            {"id": "unique-id", "title": "Doc Title", "type": "report", "content": "full text..."},
            ...
        ]
    }
    """
    documents = payload.get("documents", [])
    if not documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    if document_embedder is None:
        raise HTTPException(status_code=503, detail="Embedding service not initialized")

    total_chunks = 0
    total_embeddings = 0
    errors = []

    for doc in documents:
        try:
            result = await document_embedder.embed_document(
                doc_id=doc["id"],
                doc_type=doc.get("type", "document"),
                title=doc.get("title", "Untitled"),
                content=doc["content"],
                chunk_size=512,
                chunk_overlap=50
            )
            total_chunks += result["chunks_created"]
            total_embeddings += result["embeddings_stored"]
        except Exception as e:
            errors.append({"doc_id": doc.get("id"), "error": str(e)})

    return {
        "status": "ingestion_complete",
        "documents_processed": len(documents) - len(errors),
        "total_chunks": total_chunks,
        "total_embeddings": total_embeddings,
        "errors": errors[:10]
    }


@app.post("/admin/extract")
async def admin_extract(payload: dict):
    """
    Run entity extraction on ingested documents.

    Expected payload:
    {
        "documents": [
            {"id": "unique-id", "type": "report", "content": "full text..."},
            ...
        ]
    }
    """
    from src.agents.extraction import ExtractionAgent
    from src.agents.gardener import GardenerAgent

    documents = payload.get("documents", [])
    if not documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    extractor = ExtractionAgent(db_manager)
    gardener = GardenerAgent(db_manager)

    total_entities = 0
    total_relationships = 0
    errors = []

    for doc in documents:
        try:
            # Chunk the document
            chunks = _simple_chunk(doc["content"], 1000, 100)

            for idx, chunk in enumerate(chunks):
                result = await extractor.extract_from_chunk(
                    chunk_text=chunk,
                    document_id=doc["id"],
                    document_type=doc.get("type", "document"),
                    chunk_index=idx
                )
                total_entities += result.get("entities_extracted", 0)
                total_relationships += result.get("relationships_extracted", 0)

        except Exception as e:
            errors.append({"doc_id": doc.get("id"), "error": str(e)})

    # Promote all to TRUSTED
    try:
        promote_result = await gardener.promote_all_staging()
    except Exception:
        promote_result = {"promoted_count": 0}

    return {
        "status": "extraction_complete",
        "documents_processed": len(documents) - len(errors),
        "total_entities": total_entities,
        "total_relationships": total_relationships,
        "promoted": promote_result.get("promoted_count", 0),
        "errors": errors[:10]
    }


def _simple_chunk(text: str, chunk_size: int, overlap: int) -> list:
    """Simple text chunking for extraction"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if end < len(text):
            last_period = chunk.rfind('. ')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            if break_point > chunk_size * 0.5:
                chunk = chunk[:break_point + 1]
                end = start + len(chunk)
        chunks.append(chunk.strip())
        start = end - overlap
    return [c for c in chunks if c]


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
