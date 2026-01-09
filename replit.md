# Context Foundry - Dual-System Cognitive Architecture

## Overview
Context Foundry implements a dual-system cognitive architecture for enterprise knowledge graph governance. It separates Ontology Foundry (schema governance) from Context Foundry (instance governance) to allow for different governance cadences, confidence thresholds, and agent responsibilities. The project provides a robust framework for managing knowledge graphs, emphasizing structured truth delivery and a cognitive cycle approach to information processing, enabling multi-tenancy and advanced knowledge extraction capabilities with a focus on structured truth delivery and preventing hallucinations. The project's vision is to provide a robust framework for managing knowledge graphs, emphasizing structured truth delivery and a cognitive cycle approach to information processing, enabling multi-tenancy and advanced knowledge extraction capabilities with a focus on structured truth delivery and preventing hallucinations.

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
- **Tenant Isolation**: Multi-layer security architecture including PostgreSQL Row-Level Security (RLS) and application-level filtering.
- **Document Management**: Supports upload, versioning, re-queue, and status tracking.
- **Bulk Ingestion System**: Multi-file/ZIP uploads, S3/Google Drive connectors, and content deduplication.
- **Automatic Domain Detection**: Semantic routing classifies documents for domain-specific extraction.
- **Chunked Extraction**: Splits documents into overlapping chunks to prevent LLM output saturation.
- **Ontology-Centric Pipeline**: Document-aware extraction that learns entity/relationship types from documents rather than forcing pre-defined schemas.
- **Query/Reasoning System**: Provides GROUNDED, GAP, and INFERRED responses with hallucination guards, using a 4-AI consensus design, including a 3-step query pipeline for interpretation, retrieval, and synthesis.
- **EntityResolver**: Multi-stage pipeline (exact, alias, normalized, semantic, fuzzy match) with disambiguation for robust entity matching.
- **RLM Integration (Recursive Language Model)**: For complex multi-hop queries, including a `QueryComplexityRouter`, specialized `Memory APIs` for tri-memory, a `REPLSandbox` for secure Python execution, an `RLMExecutor`, and a `SubQueryAPI`.
- **Hybrid Retrieval System**: Combines knowledge graph (structured relationships) with RAG (document chunks) to ensure CF is at least as good as basic RAG while providing superior answers for graph-traversable queries.
- **Entity-Chunk Provenance**: Each entity and relationship has a `source_chunk_id` column linking back to the specific document chunk it was extracted from, enabling full citation tracing.
- **Decision Trace Layer (DTL)**: Extends Context Foundry with precedent-aware decision memory, capturing rationale, precedents, exceptions, and outcomes. DTL includes 13 tables, 6 enums, and 30 indexes, with 14 RLS policies for tenant isolation. It features hybrid retrieval for precedent search, combining semantic search, full-text search, and entity overlap.
- **Precedent Middleware - Library-First Architecture (Refactored Jan 2026)**: Case-Based Reasoning (CBR) integration implementing "retrieve before decide" pattern. Refactored to library-first architecture:
  - **Core Library** (`src/context_foundry/dtl/core.py`): Single source of truth for all precedent retrieval logic. Accepts only `AuthContext` (no raw tenant_id/user_id). Sets DB session vars for RLS enforcement.
  - **HTTP Adapter** (`src/context_foundry/dtl/dtl_http.py`): Thin adapter for external API access. Derives `AuthContext` from API key auth.
  - **Inline Adapter** (`src/context_foundry/dtl/dtl_inline.py`): In-process adapter for agents/orchestrator. Bypasses HTTP transport (~490ms overhead eliminated).
  - `PrecedentMiddleware`: Now uses inline adapter. Features client-side embedding computation with MD5-keyed caching (1-hour TTL, 1k entry cap).
  - `DecisionOrchestrator`: Single unified hook for all CF agent decision points (query routing, entity resolution, tier selection)
  - Performance: **Mean: 112ms, P95: 123ms** (inline path with pre-computed embeddings, 100 searches)
  - Security: AuthContext enforces tenant isolation. Cross-tenant queries return 0 results.
  - Tests: Parity (inline vs HTTP), Security (cross-tenant isolation), Performance (p95 ≤ 250ms with 10k decisions)
  - Integration in `ContextFoundry.query()` via `_route_with_precedents()` method
  - **CI Integration (Jan 2026)**:
    - Normal CI (`.github/workflows/ci.yml`): Runs `TestSmoke` class with `@pytest.mark.smoke` marker - inline-only tests using fixed embeddings (no API keys/HTTP server required)
    - Nightly CI (`.github/workflows/nightly.yml`): Full parity test (HTTP + inline), security tests, performance tests (requires OPENAI_API_KEY, running Brain service)

## Aggregation Framework (Jan 2026)
Quantitative query handling ("How many X?", "What's the average Y?") without hallucinating numbers. Implements v1.3 spec for safe counting and aggregation over KG, DTL, and document data.

### Architecture
- **AggregationService** (`src/context_foundry/aggregation/service.py`): Main orchestrator - call `try_aggregation_query()`
- **IntentClassifier** (`intent.py`): DSPy classifier with rules fallback for aggregation intent detection
- **SemanticResolver** → **CAT** (Canonical Aggregation Target): Semantic contract defining "what exactly are we counting?"
- **AggregationPlanner** (`planner.py`): Maps CAT to deterministic SQL templates (no LLM-generated SQL)
- **AggregationExecutor** (`executor.py`): Runs SQL with RLS via existing session
- **SufficiencyGate** (`sufficiency.py`): Decides EXACT vs LOWER_BOUND vs RANGE vs INSUFFICIENT
- **CaptureRecaptureEstimator** (`crc.py`): Lincoln-Petersen estimation for multi-source RANGE
- **AnswerFormatter** (`formatter.py`): Composes user-visible answers

### Result Kinds (User-Truthfulness Contract)
- **EXACT**: Closed-world + deterministic; safe point value
- **LOWER_BOUND**: Open-world or incomplete; "at least N"
- **RANGE**: Conflicts or multi-source; "between N and M"
- **INSUFFICIENT**: Cannot compute safe bounds

### Database Tables (with RLS)
- `agg_definitions`: Semantic contract registry
- `aggregation_metadata`: Result cache
- `doc_entity_mentions`: Document mention index

### Integration Hook
Aggregation check runs BEFORE tri-memory pipeline in `RetrievalAgent.build_context_bundle()`. If aggregation query detected, returns early with structured result.

### Feature Flags
```python
{
    "aggregation.enabled": True,        # Enable aggregation framework
    "aggregation.crc_estimation.enabled": True,  # Enable Lincoln-Petersen CRC
}
```

### Critical Rules
1. **NO COUNTING FROM RETRIEVAL** - Never use top-K retrieval results as complete sets
2. **RLS ALWAYS** - All queries use existing SQLAlchemy session (tenant isolation automatic)
3. **DETERMINISTIC ONLY** - SQL templates are pre-approved; never generate SQL from LLM

### Recent Fixes (Jan 2026)
- **EntityResolver RLS Context Preservation**: Fixed issue where session rollback cleared tenant RLS context. Now re-sets `SET LOCAL app.current_tenant_id` at the start of each resolve() call.
- **Rich Response Composition**: Aggregation results now include entity details (company names, etc.) in the answer, not just bare numbers.
- **Response Metadata**: Added `is_aggregation`, `aggregation_result`, and `counted_entities` to API responses for both `/api/query` and `/api/vault/chat` endpoints.
- **Conversation Context & Pronoun Resolution**: Follow-up queries now work properly. Frontend tracks chat history with mentioned entities; backend resolves pronouns (he, she, him, etc.) to actual entity names from previous messages. Example: After asking "How many jobs has Saleh done?", the follow-up "What roles did he do?" is resolved to "What roles did Saleh Hamed do?" for accurate retrieval.
- **Entity Phrase Extraction Fix (Jan 2026)**: Added missing regex pattern for "did X do/work/have/hold" queries in `_extract_entity_phrase_from_query()`. This fixes entity resolution for queries like "What roles did Saleh Hamed do?" which previously failed with 10% confidence due to the entity not being extracted from the query text.

## Tool-Calling Agent Architecture (Jan 2026)
Replaces regex/pattern matching with LLM-driven tool calling for query handling. Uses OpenAI function calling to orchestrate existing services.

### Components
- **ToolAgent** (`src/context_foundry/agents/tool_agent.py`): ReAct-style agent with max 5 tool calls, 800 token limit
- **Tool Definitions** (`src/context_foundry/agents/tools/definitions.py`): OpenAI function calling schema
- **Tool Wrappers** (`src/context_foundry/agents/tools/wrappers.py`): ToolExecutor wrapping existing services
- **Conversation Store** (`src/context_foundry/agents/conversation_store.py`): Session history for pronoun resolution

### Available Tools
1. **resolve_entities**: Maps names to canonical entity IDs via EntityResolver
2. **run_aggregation**: Deterministic counts/sums via AggregationService (returns EXACT/LOWER_BOUND/RANGE)
3. **get_knowledge_bundle**: Fetches KG relationships for entities via direct SQL
4. **search_documents**: Vector search over document chunks via EpisodicMemory

### Integration
- Feature flag: Add `?agent=true` to `/api/vault/chat` endpoint
- Fallback: If agent fails, gracefully falls back to existing hybrid answer pipeline
- Conversation context: Stores session history in `platform.conversation_messages` table for pronoun resolution

### Agent Workflow
1. LLM reasons about which tools to call
2. Calls `resolve_entities` to map names to IDs
3. Calls `run_aggregation` for counting queries (enforced by system prompt)
4. Calls `get_knowledge_bundle` for relationship enumeration
5. Composes rich response with citations and result_kind

### Guardrails
- Max 5 tool calls per query
- Numeric claim validator warns if numbers appear without aggregation evidence
- All SQL is parameterized with tenant RLS

## Regression Test Suite (Jan 2026)
Comprehensive regression testing for safe architectural changes. Four-layer test architecture:
- **Smoke Tests** (`@pytest.mark.smoke`): <30 seconds, no external APIs. Imports, DB connectivity, core class instantiation.
- **Fast Regression** (`@pytest.mark.fast_regression`): <3 minutes. Query classification, entity resolution, quadrant confidence, DTL adapter, tenant isolation.
- **Component Tests** (`@pytest.mark.component`): <5 minutes. API endpoints, service integration.
- **Integration Tests** (`@pytest.mark.integration`): Nightly. Full E2E pipeline.

**Files:**
- `tests/test_regression_suite.py`: Main regression test module (47 tests pass, 5 skip)
- `scripts/run_regression.py`: Convenience runner script

**Usage:**
```bash
python scripts/run_regression.py --smoke    # Fastest (30s)
python scripts/run_regression.py --fast     # Recommended during dev (4s)
python scripts/run_regression.py --full     # Complete validation
```

## External Dependencies
- **Database**: PostgreSQL (with pgvector for embeddings)
- **LLM**: OpenAI `gpt-4o-mini`
- **Vision LLM**: Anthropic Claude Sonnet 4
- **Vector Embeddings**: `text-embedding-3-small`
- **Web Framework**: Flask
- **Deployment**: Gunicorn
- **Authentication**: Magic Link, API Keys, JWT Sessions, Google OAuth