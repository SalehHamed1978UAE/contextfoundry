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
- **Precedent Middleware & Decision Orchestrator**: Case-Based Reasoning (CBR) integration implementing "retrieve before decide" pattern. Key components:
  - `PrecedentMiddleware`: Low-level API for precedent retrieval with 300ms timeout and no-block fallback
  - `DecisionOrchestrator`: Single unified hook for all CF agent decision points (query routing, entity resolution, tier selection)
  - Metrics tracking: call rate, mean/p95 latency, citation vs deviation rates
  - Integration in `ContextFoundry.query()` via `_route_with_precedents()` method

## External Dependencies
- **Database**: PostgreSQL (with pgvector for embeddings)
- **LLM**: OpenAI `gpt-4o-mini`
- **Vision LLM**: Anthropic Claude Sonnet 4
- **Vector Embeddings**: `text-embedding-3-small`
- **Web Framework**: Flask
- **Deployment**: Gunicorn
- **Authentication**: Magic Link, API Keys, JWT Sessions, Google OAuth