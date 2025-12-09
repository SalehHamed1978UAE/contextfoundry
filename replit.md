# Context Foundry - Dual-System Cognitive Architecture

## Overview
Context Foundry implements a **dual-system cognitive architecture** for enterprise knowledge graph governance. It separates **Ontology Foundry** (schema governance) from **Context Foundry** (instance governance) to allow for different governance cadences, confidence thresholds, and agent responsibilities. The project aims to provide a robust framework for managing knowledge graphs, emphasizing structured truth delivery and a cognitive cycle approach to information processing, enabling multi-tenancy and advanced knowledge extraction capabilities.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture

### Core Architecture
The system is divided into two main services:
- **Platform Foundation**: Handles multi-tenancy, user management, authentication, document management, usage metering, and acts as an MCP server for external AI integrations.
- **Brain**: Manages the knowledge extraction pipeline, ontology governance, entity/relationship management, a tri-memory architecture (semantic, episodic, symbolic), and query/reasoning agents.
Communication between these services is strictly via HTTP, using shared Pydantic types defined in `packages/interface_types/` for contracts (e.g., `ExtractionRequest`/`ExtractionResult`, `QueryRequest`/`QueryResponse`).

### Governance Separation
- **Ontology Foundry (Schema Governance)**: Manages types of entities and relationships with high confidence and a slower cadence. It defines schemas, validation rules, and lifecycle states (PROPOSED, VALIDATING, CONTESTED, APPROVED, ACTIVE, DEPRECATED).
- **Context Foundry (Knowledge Governance)**: Manages instances of entities and relationships with continuous cadence and configurable confidence. It handles entities, relationships, documents, and embeddings.

### Database Schema Structure
Three logical schemas exist:
- `ontology`: For schema governance.
- `context`: For instance governance.
- `platform`: For Platform Foundation components (tenants, documents, usage).
- `shared`: For cross-system components (users, audit_log, message_queue).

### Key Features
- **Immutable Meta-Ontology (Layer 0)**: Defines foundational types and rules.
- **SHACL-Inspired Validation Rules**: Enforce schema quality and consistency.
- **Approval Workflow**: Manages type approval with confidence-based routing and escalation.
- **Message Bus**: PostgreSQL-backed for agent coordination with exactly-once semantics.
- **OrphanDetector**: Identifies unmapped extraction patterns, feeding back to Ontology Foundry.
- **Context Bundle API**: Public API for structured truth delivery.
- **Schema Versioning & Deprecation**: Manages type evolution with audit trails.
- **UI/UX**: Single Page Application (SPA) with Flask/Jinja2 for client-side rendering, AJAX polling, and SVG-based graph visualization. Navigation is instant, and critical CSS prevents Flash of Unstyled Content.
- **Navigation Architecture**: Retractable sidebar with two modules:
  - **Sources** (Platform): Where users PUT data in. Pages: Documents (combined upload + status with real-time polling), Connectors, API Keys
  - **Knowledge** (Brain): Where users GET insights out. Links to Dashboard, Memory Graph, Command Center, A/B Evaluation
  - **Collapse/Expand**: Sidebar can collapse to 60px showing only icons with tooltips; state persists in localStorage
- **Corpus Stats Dashboard**: Documents page displays real-time stats (Documents, Entities, Relationships, Processing) via `/api/corpus-stats` endpoint with 5-second polling
- **OCR Support**: Scanned PDFs automatically processed with Tesseract OCR when pypdf/pdfplumber return no text (dependencies: tesseract, poppler, pytesseract, pdf2image)
- **Claude Vision Fallback**: When OCR produces insufficient text (< 800 chars/page), the system automatically falls back to Claude Vision (Sonnet 4) for designed PDFs. Vision renders pages as JPEG images and extracts entities directly from visual content, achieving 4x+ better extraction on strategy documents, presentations, and designed materials. Connection handling is optimized to reconnect after long Vision API calls.
- **Tenant Isolation**: Multi-layer security:
  1. Application-level: All queries filter by `tenant_id` via StagingLoader and DuplicateDetector
  2. Database-level: RLS policies enabled on `entities` and `relationships` tables
  3. Session management: `tenant_session()` context manager sets/resets `app.current_tenant_id`
  - Note: Neon PostgreSQL's `neondb_owner` role has `rolbypassrls=t`, requiring a non-bypass application role for full RLS enforcement
- **Document Management**: Supports upload, versioning, re-queue for extraction, and status tracking with tenant-isolated storage.
- **Bulk Ingestion System**: Supports multi-file/ZIP uploads, S3/Google Drive connectors with credential encryption, junk file filtering, and content deduplication.
- **Automatic Domain Detection**: Semantic routing using embedding similarity classifies documents into domains (IT, healthcare, finance, aviation, etc.) and combines Core Foundation types with domain-specific types for comprehensive extraction. See `brain/classifier.py`.

## Extraction Architecture

### Domain-Agnostic Extraction
The extraction pipeline uses **semantic routing** for automatic domain detection:

1. **Core Foundation Types** (always included): PERSON, ORGANIZATION, DOCUMENT, LOCATION, EVENT, CONCEPT, PROCESS, DATE
2. **Domain-Specific Types** (auto-detected): Added when document matches a domain with confidence >= 0.30

### Semantic Router (`brain/classifier.py`)
- Pre-computed embeddings for 7 domains: it_infrastructure, healthcare, finance, aviation, supply_chain, manufacturing, construction
- Cosine similarity compares document embedding against domain embeddings
- Threshold: 0.30 confidence for domain detection
- Fallback: Core Foundation types only if no domain matches

### Extraction Flow
1. Embed first 2000 chars of document
2. Compare against cached domain embeddings
3. If domain detected → use Core + Domain types
4. If no domain → use Core types only
5. **Chunk document** into ~2000 char segments with 400 char overlap
6. Extract entities from each chunk separately (avoids LLM output saturation)
7. Deduplicate entities across all chunks
8. Load to staging with duplicate detection

### Chunked Extraction (Output Saturation Fix)
**Problem**: LLMs exhibit "output saturation" (lazy list effect) due to RLHF training - they stop extracting after ~12-15 entities regardless of document length.

**Solution**: Split documents into overlapping chunks (~2000 chars each) and extract from each chunk separately.

**Results**: 
- Single chunk: ~12 entities
- Chunked (5 chunks): 55-60 entities
- **Improvement: +358%**

Implementation: `src/context_foundry/extraction/entity_extractor.py` - `_chunk_text()` and `extract_with_types()`

## Query & Reasoning System

### Conversational Response Style
The reasoning agent produces **natural, conversational responses** that:
- Explain WHY services are affected (causal chains)
- Mention team/owner names when available in entity properties
- Acknowledge knowledge gaps naturally ("I don't have contact info for X, check Slack")
- Answer the SPECIFIC question asked (notification vs impact vs escalation)

### Impact Query Optimization
For blast radius/impact queries, the system:
1. Uses deterministic graph traversal (BFS) to find all affected entities
2. Skips the sufficiency LLM call when traversal results exist (saves ~3-5 seconds)
3. Filters start entity from results (it's the CAUSE, not an effect)
4. Deduplicates blast radius entity list

### Notification Query Cross-Memory Synthesis
When queries contain "notify", "contact", "escalate", or "owner":
- Pulls ownership info from entity properties (owner, team, owner_team)
- Checks ESCALATES_TO relationships
- Includes escalation rules from symbolic memory

### Response Time Target
- Impact queries with traversal: ~12 seconds (reduced from 22s)
- Non-impact queries: ~16-18 seconds

### Performance Optimization (Dec 2025)
**Episodic Memory pgvector Optimization**: Replaced Python-based full table scan with in-database pgvector cosine distance search.
- Before: 6400ms (loading all 7700+ documents into Python)
- After: 540ms (in-database vector similarity)
- **Improvement: 12x speedup**

Implementation: `src/context_foundry/memory/episodic.py` - `search_similar()` uses `Document.embedding.cosine_distance()` for efficient in-database search.

## External Dependencies
- **Database**: PostgreSQL (with pgvector for embeddings)
- **LLM**: OpenAI `gpt-4o-mini`
- **Vision LLM**: Anthropic Claude Sonnet 4 (for designed PDFs where OCR yields < 800 chars/page)
- **Vector Embeddings**: `text-embedding-3-small`
- **Web Framework**: Flask
- **Deployment**: Gunicorn
- **Authentication**: Magic Link, API Keys, JWT Sessions