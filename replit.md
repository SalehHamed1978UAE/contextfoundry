# Context Foundry - Dual-System Cognitive Architecture

## Overview
Context Foundry implements a **dual-system cognitive architecture** for enterprise knowledge graph governance. It separates **Ontology Foundry** (schema governance) from **Context Foundry** (instance governance) to allow for different governance cadences, confidence thresholds, and agent responsibilities. This project aims to provide a robust and resilient framework for managing knowledge graphs, emphasizing structured truth delivery and a cognitive cycle approach to information processing.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture

### Module Separation (RFC v2)
The system is evolving toward a clean separation between **Platform Foundation** and **Brain**:

**Platform Foundation** (`platform_foundation/`):
- Multi-tenancy management (tenants, users, quotas)
- Authentication (magic link, API keys)
- Document management (upload, versioning, folders)
- Usage metering and billing
- MCP server for external AI integrations

**Brain** (`src/context_foundry/`):
- Knowledge extraction pipeline
- Ontology governance
- Entity/relationship management
- Tri-memory architecture (semantic, episodic, symbolic)
- Query and reasoning agents

**Interface Contract** (`packages/interface_types/`):
- Shared Pydantic types for Platform ↔ Brain communication
- ExtractionRequest/ExtractionResult for async extraction
- QueryRequest/QueryResponse for sync queries
- Critical rule: Neither module imports from the other

### Legacy System Separation
- **Ontology Foundry (Schema Governance):** Governs types of entities and relationships, with a weekly/monthly cadence and high confidence (0.90+). It manages schema definitions, validation rules, and lifecycle states. Agents include TypeValidator, HierarchyEnforcer, and CollisionDetector.
- **Context Foundry (Knowledge Governance):** Governs specific instances of entities and relationships, with a continuous cadence (per document) and configurable confidence (0.70+). It manages entities, relationships, documents, and embeddings. Agents include Extractor, Gardener, Resolver, and QueryAgent.

### Database Schema Structure
- `ontology`: For schema governance (meta_ontology, types, relations, rules, versions, type_migration_map).
- `context`: For instance governance (entities, relationships, documents, embeddings, orphan_patterns).
- `shared`: For cross-system components (users, audit_log, message_queue, confidence_thresholds).
- `platform`: NEW - For Platform Foundation (tenants, users, documents, folders, usage_events, api_keys, extraction_requests, extraction_results).

### Core Components & Features
- **Immutable Meta-Ontology (Layer 0):** Defines foundational types: OntologyType, OntologyRelation, ValidationRule, OntologyVersion, LifecycleState.
- **Ontology Lifecycle States:** Entities progress through states like PROPOSED, VALIDATING, CONTESTED, APPROVED, ACTIVE, DEPRECATED. Only ACTIVE types allow extraction.
- **SHACL-Inspired Validation Rules:** Six base rules enforce schema quality, naming conventions, hierarchy, and property validation.
- **Validation Agents:** RuleExecutor, TypeValidator, HierarchyEnforcer, and CollisionDetector ensure data integrity and consistency.
- **Approval Workflow:** Manages type approval with decision matrices, confidence-based routing, SLA deadlines, and auto-escalation.
- **TypeLifecycleManager:** Orchestrates validation agents and routes types to the ApprovalManager based on calculated confidence.
- **Message Bus:** A PostgreSQL-backed publish/subscribe system with exactly-once semantics for agent coordination across 17 event types (including EXTRACTION_REQUESTED), including retry logic and dead-letter queue.
- **OrphanDetector:** Identifies extraction patterns without matching active ontology types, providing a feedback loop from Context Foundry to Ontology Foundry, and supporting promotion to new PROPOSED types.
- **Context Bundle API:** Provides a public API for structured truth delivery, translating internal context bundles into Pydantic models. Supports fuzzy matching and graceful empty-state handling.
- **Schema Versioning & Deprecation:** Manages type versions, migrations, and deprecation processes with an audit trail, supporting multi-hop translation chains.
- **UI/UX:** A web interface with a full Single Page Application (SPA) architecture. All 4 pages (Dashboard, Memory Graph, Command Center, A/B Evaluation) are client-side sections in `templates/index.html` with instant JavaScript-based switching via `switchToPage()`. Features include AJAX polling for real-time updates, SVG-based force-directed graph visualization, and collapsible sidebar with localStorage persistence.
- **Navigation Architecture:** Full SPA - all pages are hidden sections in index.html (`.page-content` divs). Navigation is instant with no page reloads. Legacy Flask routes (`/CommandCenter`, `/evaluation`) redirect to SPA URLs (`/?page=command`, `/?page=evaluation`). API endpoints (`/api/command-center/data`, `/api/evaluation/*`) provide JSON data for client-side rendering. FOUC prevention via inline critical CSS (body opacity 0 until loaded) and HTTP Color-Scheme headers.

### Brain Internal Endpoints
- `/internal/v1/health` - Component-level health check for Platform Foundation
- `/internal/v1/query` - QueryRequest/QueryResponse contract endpoint for Platform

### Extraction Worker
- `src/context_foundry/workers/extraction_worker.py` - Queue consumer that:
  - Claims requests from `platform.extraction_requests`
  - Invokes extraction pipeline
  - Writes ExtractionResult with tokens_consumed to `platform.extraction_results`
  - Returns {input_tokens, output_tokens, total_tokens} for billing

## Directory Structure
```
context-foundry/
├── packages/
│   └── interface_types/        # Shared types (Platform ↔ Brain contract)
│       └── src/
│           ├── extraction.py   # ExtractionRequest, ExtractionResult
│           └── query.py        # QueryRequest, QueryResponse
├── platform_foundation/        # NEW - Platform module
│   ├── migrations/             # SQL migrations for platform schema
│   └── src/
│       ├── tenant_service.py   # Multi-tenancy management
│       ├── document_service.py # Document upload, versioning
│       └── metering_service.py # Usage tracking, quotas
├── src/context_foundry/        # Brain module
│   ├── workers/                # Queue consumers
│   │   └── extraction_worker.py
│   ├── agents/                 # Cognitive agents
│   ├── memory/                 # Tri-memory architecture
│   └── shared/                 # Message bus, shared utilities
└── web_app.py                  # Flask web application
```

## External Dependencies
- **Database**: PostgreSQL (Neon for Replit)
- **LLM**: OpenAI gpt-4o-mini
- **Vector Embeddings**: pgvector with text-embedding-3-small
- **Web Framework**: Flask
- **Deployment**: Gunicorn

### Authentication (Phase 2 Complete)
- **Magic Link Flow**: /auth/magic-link generates 15-minute tokens, /auth/verify validates and returns JWT
- **API Keys**: cf_live_/cf_test_ prefixes with bcrypt hashing, /api/keys CRUD endpoints
- **JWT Sessions**: Access tokens (15min) and refresh tokens (7 days) with tenant_id, role, user_id
- **Tenant Context**: before_request extracts auth, stores in Flask g; set_tenant_on_session() for RLS
- **RLS Integration**: platform.set_current_tenant() and platform.set_current_user_role() session variables

### Tenant Isolation (Track B Complete)
- Migration 010 adds tenant_id to context.entities, context.relationships, context.documents
- SQLAlchemy models include tenant_id columns
- GraphBuilder stamps tenant_id on all Entity, Relationship, Document records during extraction
- RLS policies exist but not enabled until backfill of existing records

### Document Management (Phase 3 Complete)
- **POST /documents**: Upload with multipart/form-data, validates MIME/size, checks quota, stores to tenant-isolated path
- **GET /documents**: List tenant documents with pagination and filters
- **GET /documents/{id}**: Get document details (status, version, metadata)
- **POST /documents/{id}/extraction**: Re-queue document for extraction
- **GET /documents/{id}/status**: Get current extraction status
- **Storage Path**: ./storage/tenants/{tenant_id}/documents/{doc_id}/v{version}/content
- **Usage Logging**: Tracks upload and extraction events in platform.usage_events
- **Result Processing**: process_extraction_results() updates document status and logs token usage

### MCP Server (Phase 4 Complete)
- **Endpoints**: POST /mcp/v1/tools/{tool_name}, GET /mcp/v1/resources?uri=...
- **Discovery**: GET /mcp/v1/tools (list tools), GET /mcp/v1/resources/list (list resources)
- **Authentication**: API key via Authorization header (ApiKey cf_live_xxx or cf_live_xxx)
- **Scope Validation**: read/write/admin hierarchy (admin > write > read)
- **Quota Enforcement**: Pre-flight check_quota() before Brain calls, prevents wasted compute
- **Usage Logging**: log_usage() after each query_context/verify_statement with tokens_consumed
- **Tools**: query_context, verify_statement, ingest_document, get_document_status, list_entity_types
- **Resources**: context://schema/{domain}, context://usage

## Recent Changes (December 2025)
- Completed Phase 4: MCP server with 5 tools, 2 resources, API key auth, quota enforcement, usage logging
- Completed Phase 3: Document upload, storage, queue submission, status tracking, usage logging
- Completed Phase 2: Authentication with magic links, API keys, JWT sessions
- Completed Track B: Tenant isolation with tenant_id columns and extraction stamping
- Added set_tenant_on_session() helper for handlers needing RLS
- Added Platform Foundation module with multi-tenancy support
- Created interface types package for Platform ↔ Brain contract
- Added EXTRACTION_REQUESTED event type to MessageBus
- Created extraction worker for queue consumption
- Added /internal/v1/health and /internal/v1/query Brain endpoints
- Created RLS policies for tenant isolation (pending enablement after backfill)
