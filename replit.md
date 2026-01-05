# Context Foundry - Dual-System Cognitive Architecture

## Overview
Context Foundry implements a dual-system cognitive architecture for enterprise knowledge graph governance. It separates Ontology Foundry (schema governance) from Context Foundry (instance governance) to allow for different governance cadences, confidence thresholds, and agent responsibilities. The project provides a robust framework for managing knowledge graphs, emphasizing structured truth delivery and a cognitive cycle approach to information processing, enabling multi-tenancy and advanced knowledge extraction capabilities with a focus on structured truth delivery and preventing hallucinations.

## Recent Changes (January 2026)

### Week 1 Stabilization - Component Contracts (Completed)
- **Created `src/context_foundry/contracts/`** - Formal component contracts directory
- **QueryParserContract** (`contracts/query_parser.py`)
  - `QueryIntent` dataclass for structured query parsing output
  - `QueryType` enum: IMPACT, DEPENDENCY, OWNERSHIP, ENTITY, RULE, ANALYSIS, etc.
  - `PatternBasedQueryParser` implementation with regex patterns
  - **BUG FIX**: Correctly parses "What was affected by X" - extracts "X" as entity, not "affected by X"
- **EntityResolverContract** (`contracts/entity_resolver.py`)
  - `EntityCandidate` and `ResolveResult` dataclasses with invariant validation
  - Threshold constants: EXACT=0.95, SEMANTIC=0.75, FUZZY=0.70
  - Disambiguation detection when candidates within 0.1 score delta
- **Memory Contracts** (`contracts/memory.py`)
  - `SemanticMemoryContract` - Knowledge graph memory layer interface
  - `SymbolicMemoryAPIContract` - RLM REPL memory interface
  - `verify_relationship_parity()` - Utility to detect RLM parity bugs
  - **CRITICAL**: Parity tests catch when SymbolicMemoryAPI returns 0 relationships while SemanticMemory returns correct data
- **Test Fixtures** (`tests/fixtures/knowledge_graph.py`)
  - Canonical IT service architecture (API Gateway → Payment Service → Auth Database, etc.)
  - 6 entities, 6 relationships, impact chain test cases
  - `get_impact_chain()` helper for expected blast radius results
- **Contract Tests** (`tests/contracts/`)
  - 72 tests total, 100% passing
  - `test_query_parser_contract.py` - 37 tests for query parsing
  - `test_entity_resolver_contract.py` - 17 tests for entity resolution
  - `test_memory_parity.py` - 18 tests for memory parity

### Week 2 Stabilization - E2E Test Suite (Completed)
- **Created `tests/e2e/`** - End-to-end test directory
- **test_dependency_queries.py** (18 tests)
  - Tests "What does X depend on?" query patterns
  - Verifies: query_type classification, ContextBundle structure, confidence levels
  - Skips data-dependent assertions when test entities not in database
- **test_management_queries.py** (14 tests)
  - Tests "Who owns X?" and "Who manages X?" patterns
  - Ownership relationship retrieval verification
- **test_impact_queries.py** (14 tests)
  - Tests blast radius and impact analysis queries
  - **BUG REGRESSION TEST**: Verifies "What was affected by X" fix (Week 1)
  - Confirms target_entity_name does NOT contain "affected by"
- **test_tenant_isolation.py** (13 tests)
  - Tenant data isolation verification
  - Cross-tenant data leakage detection
- **Test Summary**: 59 E2E tests + 72 contract tests = 131 total tests
- **KNOWN LIMITATIONS** (Week 4 backlog):
  - Tests skip when canonical entities (Order Service, etc.) not in database
  - Need deterministic test data seeding for CI/CD reliability
  - Need mock/stub LLM responses for fast, deterministic execution

### Week 3 Stabilization - Schema Consolidation (Completed)
- **Created `src/context_foundry/ontology_foundry/schema_service.py`**
  - `OntologySchemaService` singleton loads schema from ontology.types and ontology.relations tables
  - Auto-loads with database session via `get_ontology_schema_service()`
  - `type_mappings` property provides LLM type correction mappings (APPLICATION→SERVICE, etc.)
  - Fallback to default mappings when database unavailable
  - Compatible with existing `DomainSchema` interface via `to_domain_schema()`
- **Updated `src/context_foundry/config/domain_schema.py`**
  - `DomainSchemaLoader.load()` now tries ontology tables first via `_load_from_ontology()`
  - Falls back to YAML only if ontology tables unavailable
  - `use_ontology=True` parameter (default) enables ontology-first behavior
- **Updated `src/context_foundry/extraction/entity_extractor.py`**
  - Replaced hardcoded `TYPE_MAPPING` with `OntologySchemaService.type_mappings`
  - `_correct_entity_type()` now uses consolidated service
  - Maintains YAML fallback for backward compatibility
- **Updated `src/context_foundry/agents/graph_builder.py`**
  - Same consolidation as entity_extractor
  - `type_mappings` property delegates to OntologySchemaService
- **Schema Architecture**:
  - **Source of Truth**: `ontology.types` and `ontology.relations` tables (225 types, 208 relations)
  - **YAML Fallback**: `config/domain_schema.yaml` kept for domains not in ontology tables
  - **Type Mappings**: Default mappings in service (type_translation view requires deprecated types)
- **Verification**: All 72 contract tests + E2E tests still pass

### Week 4 Stabilization - Bug Fixes (In Progress)
- **RLM Parity Bug (FIXED)**: `SymbolicMemoryAPI.get_relationships()` returned 0 relationships while `SemanticMemory.get_entity_relationships()` returned correct data.
  - **Root Cause**: tenant_id type mismatch - SymbolicMemoryAPI compared string tenant_id directly to UUID column
  - **Fix**: Added UUID conversion in `SymbolicMemoryAPI.__init__()`: `self._tenant_id = PyUUID(tenant_id) if isinstance(tenant_id, str) else tenant_id`
  - **File**: `src/context_foundry/rlm/memory_apis/symbolic.py`
  - **Verification**: 18 parity contract tests pass, 2 integration unit tests pass
- **Integration Tests Added**: `tests/integration/test_rlm_parity.py`
  - Tests tenant_id UUID conversion
  - Parity tests (skip when RLS prevents seeding)
- **Test Data Seeding Fixtures (CREATED)**:
  - `tests/fixtures/seed_test_data.py` - TestDataSeeder class with canonical IT service architecture
  - `tests/e2e/conftest.py` - Pytest fixtures for test data (seeded_test_data, api_gateway, payment_service, etc.)
  - RLS-aware: gracefully skips seeding when Row-Level Security prevents inserts
- **E2E Test Attribute Bug (FIXED)**: Fixed incorrect attribute names in E2E tests
  - Changed `bundle.entities` → `bundle.semantic_entities`
  - Changed `bundle.relationships` → `bundle.semantic_relationships`
  - Changed `bundle.documents` → `bundle.episodic_documents`
- **Test Summary (as of Week 4)**:
  - 74 contract + integration tests passing
  - 12 tenant isolation E2E tests passing
  - 4 skipped (RLS prevents seeding)
  - **86+ total tests verified**

### Known Bugs (Remaining)
1. **Query Parser Bug (FIXED in Week 1)**: "What was affected by X" was incorrectly parsed. Fixed in `PatternBasedQueryParser`.
2. **'rely on' Query Classification**: Maps to 'impact' instead of 'dependency' - needs query parser pattern update.

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
- **Tenant Isolation**: Multi-layer security architecture:
  - **RLS (Authoritative)**: PostgreSQL fail-closed policies on 9 tables via `app_user` role (NOBYPASSRLS)
  - **Defense-in-Depth**: Application-level tenant_id filtering in all memory classes
  - **Propagation Chain**: ContextFoundry → RetrievalAgent → SemanticMemory/EpisodicMemory → _apply_tenant_filter()
  - **UUID Conversion**: _apply_tenant_filter() converts string tenant_ids to UUID for proper SQLAlchemy filtering
  - **TenantSession Wrapper**: Auto-restores tenant context after commit/rollback (PostgreSQL resets SET variables on transaction boundaries)
  - **Test Coverage**: 16 RLS tests (11 RLS + 5 defense-in-depth) verify tenant isolation
- **Document Management**: Supports upload, versioning, re-queue, and status tracking.
- **Bulk Ingestion System**: Multi-file/ZIP uploads, S3/Google Drive connectors, and content deduplication.
- **Automatic Domain Detection**: Semantic routing classifies documents for domain-specific extraction.
- **Chunked Extraction**: Splits documents into overlapping chunks to prevent LLM output saturation.
- **Query/Reasoning System**: Provides GROUNDED, GAP, and INFERRED responses with hallucination guards, using a 4-AI consensus design.
- **EntityResolver**: 3-stage pipeline (exact, semantic, fuzzy match) with disambiguation for robust entity matching. Entity name embeddings are stored in `entities.name_embedding`.
- **RLM Integration (Recursive Language Model)**: For complex multi-hop queries.
  - **QueryComplexityRouter**: Routes queries to Tier 1 (simple) or Tier 2 (RLM) based on complexity analysis.
  - **Memory APIs**: Wrappers for tri-memory (Semantic, Episodic, Symbolic).
  - **REPLSandbox**: Secure Python execution for RLM.
  - **RLMExecutor**: Orchestrates multi-turn LLM loop with circuit breakers and answer synthesis.
  - **SubQueryAPI**: Sub-queries to Tier 1 resolver with token budget.

## External Dependencies
- **Database**: PostgreSQL (with pgvector for embeddings)
- **LLM**: OpenAI `gpt-4o-mini`
- **Vision LLM**: Anthropic Claude Sonnet 4
- **Vector Embeddings**: `text-embedding-3-small`
- **Web Framework**: Flask
- **Deployment**: Gunicorn
- **Authentication**: Magic Link, API Keys, JWT Sessions, Google OAuth