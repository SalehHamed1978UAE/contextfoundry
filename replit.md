# Context Foundry - Dual-System Cognitive Architecture

## Overview
Context Foundry is a project designed to manage and govern enterprise knowledge graphs. It employs a dual-system cognitive architecture, separating schema governance (Ontology Foundry) from instance governance (Context Foundry). This approach allows for distinct governance cadences, confidence thresholds, and agent responsibilities, ensuring structured truth delivery and preventing hallucinations. The project aims to provide a robust, multi-tenant framework for advanced knowledge extraction and processing, focusing on reliable information management.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture
The system is composed of two main services: Platform Foundation (handling multi-tenancy, user management, authentication, document management, usage metering, and external AI integrations) and Brain (managing knowledge extraction, ontology governance, entity/relationship management, tri-memory architecture, and query/reasoning agents). Communication between these services uses HTTP with shared Pydantic types.

**Governance Separation:**
- **Ontology Foundry (Schema Governance):** Manages types of entities and relationships with high confidence and a slower cadence, defining schemas and validation rules.
- **Context Foundry (Knowledge Governance):** Manages instances of entities and relationships with a continuous cadence and configurable confidence, handling entities, relationships, documents, and embeddings.

**Database Schema:** Three logical schemas: `ontology`, `context`, and `platform`, with a `shared` schema for cross-system components.

**Key Features:**
- **Immutable Meta-Ontology (Layer 0):** Defines foundational types and rules.
- **SHACL-Inspired Validation Rules:** Enforce schema quality and consistency.
- **Approval Workflow:** Manages type approval with confidence-based routing.
- **Message Bus:** PostgreSQL-backed for agent coordination.
- **Context Bundle API:** Public API for structured truth delivery.
- **Schema Versioning & Deprecation:** Manages type evolution with audit trails.
- **UI/UX:** Single Page Application (SPA) with Flask/Jinja2, AJAX, and SVG graph visualization.
- **Tenant Isolation:** Multi-layer security via PostgreSQL Row-Level Security (RLS) and application-level filtering.
- **Document Management:** Supports upload, versioning, re-queue, and status tracking.
- **Bulk Ingestion System:** Multi-file/ZIP uploads, S3/Google Drive connectors, and content deduplication.
- **Automatic Domain Detection:** Semantic routing for document classification.
- **Chunked Extraction:** Splits documents into overlapping chunks for LLM processing.
- **Open Capture Extraction:** A 3-phase Canonical Mapping Pipeline for flexible knowledge extraction:
    - **Open Capture:** LLM extracts entities/relationships naturally without predefined types.
    - **Canonical Mapper:** Normalizes raw LLM output to canonical forms using `config/canonical_mappings.yaml`.
    - **Governance Queue:** Tracks unmapped types for human review.
- **Ontology-Centric Pipeline:** Document-aware extraction that learns types from documents.
- **Query/Reasoning System:** Provides GROUNDED, GAP, and INFERRED responses with hallucination guards, using a 4-AI consensus design and a 3-step query pipeline.
- **EntityResolver:** Multi-stage pipeline for robust entity matching and disambiguation.
- **RLM Integration (Recursive Language Model):** For complex multi-hop queries, including a `QueryComplexityRouter`, specialized `Memory APIs`, `REPLSandbox`, `RLMExecutor`, and `SubQueryAPI`.
- **Hybrid Retrieval System:** Combines knowledge graph and RAG for comprehensive answers.
- **Entity-Chunk Provenance:** Links extracted entities/relationships to source document chunks for citation tracing.
- **Decision Trace Layer (DTL):** Extends Context Foundry with precedent-aware decision memory, capturing rationale, precedents, exceptions, and outcomes. Features hybrid retrieval for precedent search.
- **Precedent Middleware:** Library-first architecture for Case-Based Reasoning (CBR) integration, enabling "retrieve before decide" patterns. Includes a core library, HTTP adapter, and inline adapter for efficient integration.
- **Aggregation Framework:** Handles quantitative queries ("How many X?", "What's the average Y?") via a structured pipeline including `AggregationService`, `IntentClassifier`, `SemanticResolver`, `AggregationPlanner`, `AggregationExecutor`, `SufficiencyGate`, `CaptureRecaptureEstimator`, and `AnswerFormatter`. Ensures RLS and deterministic SQL templates.
- **Tool-Calling Agent Architecture:** Replaces regex-based query handling with an LLM-driven tool-calling agent using OpenAI function calling to orchestrate services like `resolve_entities`, `run_aggregation`, `get_knowledge_bundle`, and `search_documents`. Includes guardrails for tool calls and numeric claim validation.
- **Regression Test Suite:** A four-layer test architecture including Smoke, Fast Regression, Component, and Integration tests for comprehensive validation of architectural changes.

## External Dependencies
- **Database:** PostgreSQL (with pgvector for embeddings)
- **LLM:** OpenAI `gpt-4o-mini`
- **Vision LLM:** Anthropic Claude Sonnet 4
- **Vector Embeddings:** `text-embedding-3-small`
- **Web Framework:** Flask
- **Deployment:** Gunicorn
- **Authentication:** Magic Link, API Keys, JWT Sessions, Google OAuth