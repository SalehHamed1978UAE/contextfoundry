# Context Foundry - Dual-System Cognitive Architecture

> **Detailed architecture documentation:** See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for complete system reference including all agents, memory layers, pipelines, and data flows.

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
The system is divided into two main services: Platform Foundation and Brain.
- **Platform Foundation**: Handles multi-tenancy, user management, authentication, document management, usage metering, and acts as an MCP server for external AI integrations.
- **Brain**: Manages the knowledge extraction pipeline, ontology governance, entity/relationship management, a tri-memory architecture (semantic, episodic, symbolic), and query/reasoning agents.
Communication between services uses HTTP with shared Pydantic types for contracts.

### Governance Separation
- **Ontology Foundry (Schema Governance)**: Manages types of entities and relationships with high confidence and a slower cadence, defining schemas, validation rules, and lifecycle states.
- **Context Foundry (Knowledge Governance)**: Manages instances of entities and relationships with continuous cadence and configurable confidence, handling entities, relationships, documents, and embeddings.

### Database Schema Structure
Three logical schemas: `ontology` (schema governance), `context` (instance governance), and `platform` (Platform Foundation components). A `shared` schema exists for cross-system components.

### Key Features
- **Immutable Meta-Ontology (Layer 0)**: Defines foundational types and rules.
- **SHACL-Inspired Validation Rules**: Enforce schema quality and consistency.
- **Approval Workflow**: Manages type approval with confidence-based routing and escalation.
- **Message Bus**: PostgreSQL-backed for agent coordination with exactly-once semantics.
- **OrphanDetector**: Identifies unmapped extraction patterns.
- **Context Bundle API**: Public API for structured truth delivery.
- **Schema Versioning & Deprecation**: Manages type evolution with audit trails.
- **UI/UX**: Single Page Application (SPA) with Flask/Jinja2, AJAX polling, SVG-based graph visualization, and a retractable sidebar.
- **Corpus Stats Dashboard**: Displays real-time document processing statistics.
- **OCR Support**: Integrates Tesseract OCR for scanned PDFs, falling back to Claude Vision for visually designed PDFs (e.g., presentations) to extract entities from images.
- **Tenant Isolation**: Multi-layer security via application-level filtering, database RLS policies, and session management.
- **Document Management**: Supports upload, versioning, re-queue for extraction, and status tracking.
- **Bulk Ingestion System**: Multi-file/ZIP uploads, S3/Google Drive connectors, and content deduplication.
- **Automatic Domain Detection**: Semantic routing classifies documents into domains using embedding similarity, combining Core Foundation types with domain-specific types for extraction.
- **Chunked Extraction**: Splits documents into overlapping chunks to prevent LLM "output saturation," significantly improving entity extraction recall.
- **Query/Reasoning System**: Provides GROUNDED, GAP, and INFERRED responses, with guards to prevent hallucination when entities or sufficient data are not found. Implements a 4-AI consensus design principle by architecturally gating LLM calls based on data sufficiency.
- **EntityResolver**: 3-stage entity resolution pipeline for robust entity matching:
  1. Exact match (case-insensitive)
  2. Semantic search (OpenAI embeddings with pgvector, similarity > 0.75)
  3. Fuzzy match (rapidfuzz with word-level boost, threshold 0.70)
  - Disambiguation: Returns candidate list when top 2 scores are within 0.1 delta
  - Entity name embeddings stored in `entities.name_embedding` column (Vector 1536)
  - Batch embedding job: `scripts/batch_entity_embeddings.py`
- **RLM Integration (January 2026)**: Recursive Language Model system for complex multi-hop queries:
  - **QueryComplexityRouter**: Routes between Tier 1 (simple) and Tier 2 (RLM) based on complexity analysis
    - Threshold: 0.10 complexity score for Tier 2 routing
    - Force patterns: `affected by.*triggered`, `services.*connected`, `impact.*of.*on`, etc.
  - **Memory APIs**: Wrappers for tri-memory (Semantic, Episodic, Symbolic) with discovery tracking and text fallback when embeddings unavailable
  - **REPLSandbox**: Secure Python execution with restricted patterns, timeout enforcement, and retry hints
  - **RLMExecutor**: Orchestrates multi-turn LLM loop with:
    - Circuit breaker (3 iterations without progress)
    - Iteration warnings at 2 and 4 iterations remaining
    - Answer synthesis from discoveries when LLM doesn't finalize
  - **SubQueryAPI**: Sub-queries to Tier 1 resolver with token budget (max 8000 tokens)
  - **Design decisions**:
    - STAGING entities visible to RLM with lifecycle_state field
    - StaleEntityError raised if Gardener archives entity mid-execution
    - Synthesized answers include entity names and relationship types from database
  - **Test coverage**: 90 passing tests (Memory API + Sandbox + Router + Integration)

## Recent Changes (January 2026)
- **Entity Type Correction Fix (Jan 5)**: Fixed TYPE_MAPPING not being called in extraction pipeline
  - Root cause: TYPE_MAPPING existed in `graph_builder.py` but extraction uses `entity_extractor.py`
  - Added TYPE_MAPPING and SPECIFIC_TYPE_PATTERNS to EntityExtractor class
  - Changed SPECIFIC_TYPE_PATTERNS from dict to ordered list for priority control (TEAM > DATABASE)
  - Pattern priority: TEAM first (catches "Database Administration Team"), then INCIDENT, SERVICE, DATABASE
  - Verified: Payment Gateway → SERVICE, Platform Engineering Team → TEAM, Inventory Database → DATABASE, INC-* → INCIDENT
- **Entity Persistence FK Fix (Jan 5)**: Fixed critical silent failure where entities weren't being persisted
  - Root cause: `entity_mentions.document_id` has FK to `public.documents`, but extraction documents only exist in `platform.documents`
  - FK violation caused transaction rollback, but error was caught and appended to `result.errors` without re-raising
  - Fix: Added `_document_exists_in_public()` check in StagingLoader before creating EntityMention records
  - EntityMention creation now skipped when document doesn't exist in public.documents (entity still persists)
  - Verified fix: test entities now persist correctly (2/2 created, 0 errors)
- **OntologyRepository Refactor (Jan 5)**: Fixed repository to use correct ontology schema
  - Repository now queries `ontology.types` and `ontology.relations` instead of legacy `public` schema
  - Updated OntologyType and OntologyRelation models to match actual database columns
  - Added `get_keywords()` helper to handle both list and dict extraction_hints formats
  - Added 10 IT-specific relations to ontology.relations: DEPENDS_ON, MANAGES, OWNS, AFFECTS, TRIGGERED_BY
  - Ontology snapshot now loads 229 types and 222 relations from correct schema
  - Next: Refactor GraphBuilderAgent to use OntologyRepository (pending approval)
- **Entity Type Extraction Fix (Jan 5)**: Fixed critical issue where extractor used generic types (ORGANIZATION, PROCESS) instead of IT-specific types (SERVICE, DATABASE, TEAM, INCIDENT)
  - Added TEAM and INCIDENT entity types to domain_schema.yaml
  - Added OWNS, AFFECTS, TRIGGERED_BY relationship types for IT infrastructure
  - Updated extraction prompt with TYPE PRIORITY section to prefer specific types
  - Added post-extraction type correction with TYPE_MAPPING and SPECIFIC_TYPE_PATTERNS
  - Added deduplication to prevent duplicate entities with different types
  - Updated MANAGES relationship to include TEAM as source and SERVICE/DATABASE as targets
- **RLM Answer Generation Improvements**: Enhanced RLM to produce grounded answers instead of exploration-only responses
  - Updated system prompt to emphasize early finalization (after 3 iterations)
  - Added iteration warnings at 2 and 4 remaining iterations
  - Added circuit breaker synthesis: when LLM doesn't finalize, answers synthesized from discovered entities/relationships
  - Added FORCE_RLM_PATTERNS for pattern-based routing (bypasses complexity scoring)
  - Lowered complexity threshold from 0.19 to 0.10 for broader RLM coverage
  - Fixed entity name lookup to use correct schema (public vs context)
  - 90 passing tests across all components

## Previous Changes (December 2025)
- Added `name_embedding` column to entities table via migration 012
- Implemented EntityResolver class in `src/context_foundry/agents/entity_resolver.py`
- Integrated EntityResolver into RetrievalAgent's `_match_known_entity_in_query()`
- Running batch embedding job to populate entity name embeddings (~8.7k entities)
- Fixed Gardener scheduler conflict query (UNION of fact_a_id/fact_b_id)
- Created Day 4 test suite: 100% resolution rate (0% NOT_FOUND failures)

## Week 2.5 Governance Blocker

**CRITICAL: Gardener must be healthy before ANY enrichment work begins.**

Before implementing relationship enrichment, entity merging, or data quality improvements:

1. **Verify Gardener cycles complete without errors** - Check scheduler logs for successful promotion/decay/conflict passes
2. **Confirm STAGING → TRUSTED promotion is working** - Entities should flow through lifecycle states
3. **Validate conflict resolution** - Pending conflicts should be resolved or escalated
4. **Check demotion pass** - Low-confidence entities should be archived

**Rationale:** Enrichment work will generate new STAGING entities and relationships. If the Gardener isn't promoting/demoting correctly, the knowledge graph will either:
- Accumulate low-quality STAGING data indefinitely
- Miss conflicts between new and existing facts
- Fail to maintain confidence scores over time

**Validation command:** Check `/tmp/logs/Start_All_*.log` for `[Scheduler] Cycle #N complete` with non-zero promotion counts.

## Future Optimization: Document Chunk Embeddings

**Current state:** Both entity names and document chunks use `text-embedding-3-small` (1536-dim)

**Why this is fine for now:**
- Entity resolution via tri-stage resolver compensates for embedding quality
- Cost-efficient during development (~10x cheaper than large)
- Relationship sparsity (0.24 rel/entity) is the current bottleneck, not retrieval quality

**Review triggers - revisit embedding model choice when ANY of these occur:**

1. **Useful answer rate plateaus** after relationship density improves past 1.0 rel/entity
2. **Document retrieval misses** become a pattern in query logs (user asks about incident X, system retrieves incident Y)
3. **Long-form queries underperform** - questions requiring synthesis across multiple 512-token chunks return poor results
4. **A/B benchmark shows >15% retrieval quality gap** between small and large on document chunks specifically

**Upgrade path if triggered:**
- Keep `text-embedding-3-small` for entity names (short strings, cost-sensitive, high volume)
- Upgrade to `text-embedding-3-large` for document chunks only (3072-dim)
- Update pgvector columns to handle mixed dimensions OR maintain separate tables

**Benchmark task:** Create evaluation set of 50 document retrieval queries, measure recall@5 for small vs large, log results before deciding.

## External Dependencies
- **Database**: PostgreSQL (with pgvector for embeddings)
- **LLM**: OpenAI `gpt-4o-mini`
- **Vision LLM**: Anthropic Claude Sonnet 4
- **Vector Embeddings**: `text-embedding-3-small`
- **Web Framework**: Flask
- **Deployment**: Gunicorn
- **Authentication**: Magic Link, API Keys, JWT Sessions, Google OAuth