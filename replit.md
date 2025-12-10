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
- **EntityResolver (NEW)**: 3-stage entity resolution pipeline for robust entity matching:
  1. Exact match (case-insensitive)
  2. Semantic search (OpenAI embeddings with pgvector, similarity > 0.75)
  3. Fuzzy match (rapidfuzz with word-level boost, threshold 0.70)
  - Disambiguation: Returns candidate list when top 2 scores are within 0.1 delta
  - Entity name embeddings stored in `entities.name_embedding` column (Vector 1536)
  - Batch embedding job: `scripts/batch_entity_embeddings.py`

## Recent Changes (December 2025)
- Added `name_embedding` column to entities table via migration 012
- Implemented EntityResolver class in `src/context_foundry/agents/entity_resolver.py`
- Integrated EntityResolver into RetrievalAgent's `_match_known_entity_in_query()`
- Running batch embedding job to populate entity name embeddings (~8.7k entities)

## External Dependencies
- **Database**: PostgreSQL (with pgvector for embeddings)
- **LLM**: OpenAI `gpt-4o-mini`
- **Vision LLM**: Anthropic Claude Sonnet 4
- **Vector Embeddings**: `text-embedding-3-small`
- **Web Framework**: Flask
- **Deployment**: Gunicorn
- **Authentication**: Magic Link, API Keys, JWT Sessions, Google OAuth