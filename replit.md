# Context Foundry - Dual-System Cognitive Architecture

## Overview
Context Foundry implements a dual-system cognitive architecture for enterprise knowledge graph governance. It separates Ontology Foundry (schema governance) from Context Foundry (instance governance) to allow for different governance cadences, confidence thresholds, and agent responsibilities. The project provides a robust framework for managing knowledge graphs, emphasizing structured truth delivery and a cognitive cycle approach to information processing, enabling multi-tenancy and advanced knowledge extraction capabilities with a focus on structured truth delivery and preventing hallucinations.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture

### Core Architecture
The system is divided into two main services: Platform Foundation (handles multi-tenancy, user management, authentication, document management, usage metering, external AI integrations) and Brain (manages knowledge extraction, ontology governance, entity/relationship management, tri-memory architecture, query/reasoning agents). Communication uses HTTP with shared Pydantic types.

### Governance Separation
- **Ontology Foundry (Schema Governance)**: Manages types of entities and relationships with high confidence and a slower cadence, defining schemas and validation rules.
- **Context Foundry (Knowledge Governance)**: Manages instances of entities and relationships with continuous cadence and configurable confidence, handling entities, relationships, documents, and embeddings.

### Database Schema Structure
Three logical schemas: `ontology` (schema governance), `context` (instance governance), and `platform` (Platform Foundation components). A `shared` schema exists for cross-system components.

### Key Features
- **Immutable Meta-Ontology (Layer 0)**: Defines foundational types and rules.
- **SHACL-Inspired Validation Rules**: Enforce schema quality and consistency.
- **Approval Workflow**: Manages type approval with confidence-based routing.
- **Message Bus**: PostgreSQL-backed for agent coordination with exactly-once semantics.
- **Context Bundle API**: Public API for structured truth delivery.
- **Schema Versioning & Deprecation**: Manages type evolution with audit trails.
- **UI/UX**: Single Page Application (SPA) with Flask/Jinja2, AJAX, SVG graph visualization.
- **Corpus Stats Dashboard**: Displays real-time document processing statistics.
- **OCR Support**: Integrates Tesseract OCR with Claude Vision fallback for visually complex PDFs.
- **Tenant Isolation**: Multi-layer security architecture including PostgreSQL Row-Level Security (RLS) and application-level filtering.
- **Document Management**: Supports upload, versioning, re-queue, and status tracking.
- **Bulk Ingestion System**: Multi-file/ZIP uploads, S3/Google Drive connectors, and content deduplication.
- **Automatic Domain Detection**: Semantic routing classifies documents for domain-specific extraction.
- **Chunked Extraction**: Splits documents into overlapping chunks to prevent LLM output saturation.
- **Ontology-Centric Pipeline** (NEW): Document-aware extraction that learns entity/relationship types from documents rather than forcing pre-defined schemas. Enabled via `USE_ONTOLOGY_CENTRIC_PIPELINE=true` environment variable.
- **Query/Reasoning System**: Provides GROUNDED, GAP, and INFERRED responses with hallucination guards, using a 4-AI consensus design, including a 3-step query pipeline for interpretation, retrieval, and synthesis.
- **EntityResolver**: Multi-stage pipeline (exact, alias, normalized, semantic, fuzzy match) with disambiguation for robust entity matching, intelligent plural/singular normalization, and abbreviation expansion.
- **RLM Integration (Recursive Language Model)**: For complex multi-hop queries, including a `QueryComplexityRouter`, specialized `Memory APIs` for tri-memory, a `REPLSandbox` for secure Python execution, an `RLMExecutor`, and a `SubQueryAPI`.
- **Hybrid Retrieval System**: Combines knowledge graph (structured relationships) with RAG (document chunks) to ensure CF is at least as good as basic RAG while providing superior answers for graph-traversable queries.
- **Entity-Chunk Provenance**: Each entity and relationship has a `source_chunk_id` column linking back to the specific document chunk it was extracted from. This enables full citation tracing from answer → entity → source chunk → document.

### Hybrid Retrieval Architecture
1. **Graph Query**: Searches knowledge graph for entities and relationships matching query
2. **Chunk Search**: Keyword-ranked document chunk retrieval with phrase/title matching
3. **Entity-Chunk Citations**: Retrieves entities matching query with their source chunk provenance
4. **LLM Synthesis**: Combines graph data, entity citations, and chunk text in unified prompt

### Provenance Schema
- `entities.source_chunk_id` (UUID): Links to document_chunks.id for extraction provenance
- `relationships.source_chunk_id` (UUID): Links to document_chunks.id for extraction provenance
- Pipeline: OntologyCentricPipeline processes each chunk individually, storing source_chunk_id for every extracted entity/relationship

### Current Extraction Status (Jan 2026)
- 467 entities with chunk provenance
- 285 relationships with chunk provenance
- 10 documents fully extracted with graph data
- Embedding endpoint fixed: Uses direct OpenAI API for embeddings (Replit proxy only supports chat completions)
- All document_chunks now have embeddings for pgvector semantic search
- Similarity threshold: 0.35 (optimized for text-embedding-3-small cosine similarity)

### Confidence Calibration System
- **Q1 (entity + docs)**: Base 0.90 when entity found AND top chunk similarity > 0.35
- **Q2 (entity only)**: Base 0.70 when entity found but no strong doc matches
- **Q3 (docs only)**: Base 0.65 when docs found but no entity match
- **Q4 (neither)**: Base 0.10 for unknown queries
- Sufficiency modifiers: SUFFICIENT +0.10, PARTIAL ×0.85, INSUFFICIENT ×0.55
- Target confidence for grounded answers: 77-95%

## External Dependencies
- **Database**: PostgreSQL (with pgvector for embeddings)
- **LLM**: OpenAI `gpt-4o-mini`
- **Vision LLM**: Anthropic Claude Sonnet 4
- **Vector Embeddings**: `text-embedding-3-small`
- **Web Framework**: Flask
- **Deployment**: Gunicorn
- **Authentication**: Magic Link, API Keys, JWT Sessions, Google OAuth

## Database Security (RLS)

### Role-Based Access
- **`app_user`**: Application role with RLS enforced - used by running application
- **`neondb_owner`**: Database owner - used only for migrations, bypasses RLS

### Vault Isolation
All tenant data is protected by PostgreSQL Row-Level Security (RLS):
- RLS policies filter data by `tenant_id` using `app.current_tenant_id` session variable
- Application connects as `app_user` (non-owner) so RLS is enforced
- 14 tables have RLS policies: entities, relationships, documents, etc.

### Connection Setup
- `get_session(use_rls_role=True)`: Default, uses `app_user` for tenant isolation
- `get_session(use_rls_role=False)`: Admin/migration mode, bypasses RLS
- RLS URL constructed from `PGHOST`, `PGPORT`, `PGDATABASE` + `app_user` credentials

## Vault Interface (User-Facing)

### Routes
- `/app` - Vault list (all vaults user has access to)
- `/app/new` - Create new vault
- `/app/<vault_id>` - Vault view (file tree + chat interface)
- `/app/<vault_id>/settings` - Vault settings (API keys, configuration)
- `/app/<vault_id>/dashboard` - Knowledge dashboard
- `/app/<vault_id>/memory-graph` - Memory graph visualization
- `/app/<vault_id>/command-center` - Query interface
- `/app/<vault_id>/evaluation` - A/B evaluation

### Multi-Vault Access
- Users can access multiple vaults via `platform.user_tenants` join table
- `user_tenants` table stores user_id, tenant_id, and role (e.g., 'owner')
- All vault routes check authorization via `user_has_vault_access()` before setting session tenant
- Creating a vault adds entry to `user_tenants`, preserving existing vault access

### Folder Organization
- Documents can be organized into folders within each vault
- `platform.folders` table stores folder hierarchy with `path` and `parent_path`
- `platform.documents` has `folder_path` column (defaults to '/')
- Drag-drop to move documents between folders
- Folder tree UI with expand/collapse functionality

### API Endpoints
- `GET /api/vaults` - List user's vaults
- `POST /api/vaults` - Create new vault (body: `{name: string}`)
- `GET /api/vaults/<vault_id>` - Get vault details with stats
- `GET /api/folders` - List folders in current vault
- `POST /api/folders` - Create folder (body: `{name: string, parent_path: string}`)
- `GET /api/documents/tree` - Get folder tree with documents
- `POST /api/documents/<id>/move` - Move document to folder (body: `{folder_path: string}`)

## Decision Trace Layer (DTL) - Added Jan 2026

### Overview
DTL extends Context Foundry with precedent-aware decision memory. While CF captures *what exists* (entities, relationships), DTL captures *why decisions were made* (rationale, precedents, exceptions, outcomes).

### Database Schema
- **13 Tables**: decision_traces, decision_evidence, decision_entity_links, decision_precedent_links, decision_exceptions, decision_confidence_scores, decision_executions, decision_results, decision_assessments, decision_categories, schema_evolution_proposals, decision_access_grants, decision_access_audit
- **6 Enums**: decision_lifecycle, result_status, evidence_type, sensitivity_level, decision_entity_role, category_lifecycle
- **30 Indexes**: Optimized for precedent search, temporal queries, and RRF ranking
- **14 RLS Policies**: All tables protected by tenant isolation via `app.current_tenant_id`
- **4 SQL Functions**: search_precedents, search_precedents_api, dtl_enforce_evidence_for_enacted, dtl_prevent_evidence_deletion_when_enacted
- **3 Triggers**: Evidence enforcement for enacted decisions

### Evidence Enforcement
- Enacted decisions REQUIRE evidence (enforced via deferrable constraint trigger)
- Evidence cannot be deleted if it's the last evidence for an enacted decision
- Evidence must have substance: source_uri, source_id, or excerpt >= 10 chars

### Precedent Search (Hybrid Retrieval)
Combines multiple signals with Reciprocal Rank Fusion (RRF):
1. **Semantic Search** (40% weight): Vector similarity on rationale embeddings
2. **Full-Text Search** (35% weight): PostgreSQL ts_rank_cd on summary + rationale
3. **Entity Overlap** (25% weight): Shared entities between decisions
4. **Recency Decay**: Exponential decay favoring recent decisions
5. **Outcome Weighting**: Positive outcomes boosted, negative outcomes optionally filtered
6. **Category Bonus**: Matching decision_type gets ranking boost

### DTL API Endpoints (Blueprint: /api/v1/dtl)
- `GET /api/v1/dtl/health` - Health check
- `POST /api/v1/dtl/decisions` - Create decision with evidence (required)
- `GET /api/v1/dtl/decisions/<id>` - Get decision with all related data
- `POST /api/v1/dtl/decisions/<id>/outcome` - Record decision outcome
- `POST /api/v1/dtl/precedents/search` - Search for relevant precedents

### Python Module Structure
- `src/decision_trace_layer/__init__.py` - Module exports
- `src/decision_trace_layer/models.py` - SQLAlchemy ORM + Pydantic models
- `src/decision_trace_layer/precedent_search.py` - PrecedentSearchClient
- `src/decision_trace_layer/api.py` - Flask Blueprint (registered in brain/app.py)

### DTL Security Notes
- SQL functions use SECURITY DEFINER to bypass RLS recursion (tenant_id filtering in function logic)
- API endpoints use application-level tenant isolation (explicit WHERE tenant_id = :tenant_id clauses)
- All UUID inputs validated before use
- JSON payloads serialized with json.dumps() for safety
- Cross-tenant access blocked: requests with wrong tenant_id return 404