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
- **Query/Reasoning System**: Provides GROUNDED, GAP, and INFERRED responses with hallucination guards, using a 4-AI consensus design.
- **EntityResolver**: 3-stage pipeline (exact, semantic, fuzzy match) with disambiguation for robust entity matching. Entity name embeddings are stored in `entities.name_embedding`.
- **RLM Integration (Recursive Language Model)**: For complex multi-hop queries, including a `QueryComplexityRouter`, specialized `Memory APIs` for tri-memory, a `REPLSandbox` for secure Python execution, an `RLMExecutor`, and a `SubQueryAPI`.

## External Dependencies
- **Database**: PostgreSQL (with pgvector for embeddings)
- **LLM**: OpenAI `gpt-4o-mini`
- **Vision LLM**: Anthropic Claude Sonnet 4
- **Vector Embeddings**: `text-embedding-3-small`
- **Web Framework**: Flask
- **Deployment**: Gunicorn
- **Authentication**: Magic Link, API Keys, JWT Sessions, Google OAuth

## Recent Changes (January 2026)

### Value Demo (6/6 queries working)
- **Demo Script**: `scripts/value_demo.py`
- **Demo Tenant**: 8eee325b-ba3b-447e-9ee7-6d66085ead5f
- **Query Results**:
  1. Blast Radius (0.77) - "If Auth Service goes down, what services are affected?"
  2. Dependency Chain (0.95) - "What does Order Service depend on?"
  3. Ownership (0.50) - "Who manages the Payment Service?"
  4. Incident Impact (0.59) - "What was affected by incident INC-2025-1201?"
  5. Cross-Document Reasoning (0.77) - "Which team should be paged if Orders Database fails?"
  6. Gap Identification (0.50) - "What services have no documented disaster recovery?"
- **Verdict**: CONTEXT FOUNDRY PROVIDES SIGNIFICANT VALUE

### Alias Intelligence System (January 2026)
- **entity_aliases Table**: Stores acronym/synonym mappings with RLS (alias_text, alias_type, source, entity_id)
- **EntityResolver._alias_match()**: Checks entity_aliases before semantic/fuzzy search
- **GraphBuilder Integration**: Extracts aliases from patterns like "Full Name (ABBR)" during ingestion
- **Retrieval Agent Integration**: _verify_target_entity_exists() uses alias resolution
- **Backfill Script**: scripts/backfill_aliases.py extracts aliases from existing entity names
- **Result**: EHR → "Electronic Health Record (EHR)" resolved at 0.77 confidence

### Test 2 Results - Al Shifa Healthcare (6/6 queries working)
- **Demo Tenant**: 7031800f-06ef-4858-b9e8-a22174bfbdae
- **Query Results**:
  1. Blast Radius (0.77) - "If Patient Identity Service goes down..."
  2. Dependency Chain (0.77) - "What does the EHR depend on?" (uses alias)
  3. Ownership (0.95) - "Who manages the Lab System?"
  4. Incident Impact (0.45) - "What was affected by incident INC-2025-0892?"
  5. Cross-Document (0.50) - "Which team should be paged if Master Patient Index fails?"
  6. Gap Identification (0.50) - "What systems have no documented disaster recovery?"

### Bug Fixes (Demo Debugging)
- **RLS Tenant Context Reset**: Fixed `session.commit()` resetting PostgreSQL `SET app.current_tenant_id`
- **EntityResolver UUID Conversion**: Added UUID conversion in `EntityResolver.__init__()`
- **RLM Memory APIs UUID Conversion**: Fixed SemanticMemoryAPI and EpisodicMemoryAPI
- **Query Parser Incident ID Handling**: Fixed extraction of incident IDs like "INC-2025-1201"
- **Retrieval Agent "affected by" Pattern**: Added patterns for incident impact queries