# Context Foundry - Complete Codebase Inventory
**Generated:** January 10, 2026

---

## 1. DIRECTORY STRUCTURE

```
src/context_foundry/
├── agents/                          # Core agent implementations
│   ├── tools/                       # Tool definitions for agents
│   │   ├── __init__.py
│   │   ├── definitions.py
│   │   └── wrappers.py
│   ├── __init__.py
│   ├── conversation_store.py        # Conversation history storage
│   ├── directed_retriever.py        # Focused entity/relationship retrieval
│   ├── entity_profile_generator.py  # Stage 4: Entity profile generation
│   ├── entity_resolver.py           # Entity resolution and linking
│   ├── gardener.py                  # Knowledge graph maintenance
│   ├── gardener_learning.py         # Learning ticket processing
│   ├── graph_builder.py             # Document → entity/relationship extraction
│   ├── graph_loader.py              # Bulk graph loading
│   ├── identity_resolver.py         # Identity/alias resolution
│   ├── learning_ticket_agent.py     # Create/manage learning tickets
│   ├── org_chart_loader.py          # Org chart specific loading
│   ├── query_classifier.py          # Query type classification
│   ├── query_interpreter.py         # Natural language → structured query
│   ├── query_pipeline.py            # Full query processing pipeline
│   ├── reasoning.py                 # LLM-based reasoning over context
│   ├── relationship_inference.py    # Infer missing relationships
│   ├── retrieval.py                 # Context bundle retrieval
│   ├── scheduler.py                 # Gardener scheduling
│   ├── semantic_agent.py            # Query-time semantic processing
│   ├── staging_validator.py         # Validate staging → trusted promotion
│   ├── sufficiency.py               # Compute sufficiency signals
│   ├── tier1_resolver.py            # Tier 1 entity resolution
│   ├── tool_agent.py                # Tool-using agent
│   └── validation.py                # Rule-based validation
├── aggregation/                     # Aggregation framework
│   ├── __init__.py
│   ├── crc.py                       # CRC computation
│   ├── executor.py                  # Aggregation execution
│   ├── formatter.py                 # Output formatting
│   ├── hooks.py                     # Aggregation hooks
│   ├── intent.py                    # Intent parsing
│   ├── mentions_indexer.py          # Entity mention indexing
│   ├── models.py                    # Aggregation models
│   ├── planner.py                   # Aggregation planning
│   ├── registry.py                  # Aggregation registry
│   ├── seed_definitions.py          # Seed aggregation definitions
│   ├── service.py                   # Aggregation service
│   └── sufficiency.py               # Aggregation sufficiency
├── api/                             # External API layer
│   ├── __init__.py
│   ├── bundle_builder.py            # Context bundle building
│   ├── context_bundle.py            # Context bundle utilities
│   └── external.py                  # External REST API (Flask Blueprint)
├── config/                          # Configuration
│   ├── __init__.py
│   ├── domain_schema.py             # Domain schema loader
│   └── feature_flags.py             # Feature flag management
├── contracts/                       # Interface contracts
│   ├── __init__.py
│   ├── entity_resolver.py           # Entity resolver contract
│   ├── memory.py                    # Memory interface contract
│   └── query_parser.py              # Query parser contract
├── context_foundry/                 # Nested module (legacy?)
│   ├── __init__.py
│   └── orphan_detector.py           # Detect orphaned entities
├── data/                            # Data generation
│   ├── __init__.py
│   ├── org_chart_generator.py       # Generate org chart data
│   ├── scaled_synthetic_generator.py # Generate scaled test data
│   └── synthetic_generator.py       # Generate synthetic test data
├── dtl/                             # Data Transformation Layer
│   ├── __init__.py
│   ├── core.py                      # DTL core logic
│   ├── dtl_http.py                  # HTTP-based DTL
│   └── dtl_inline.py                # Inline DTL processing
├── evaluation/                      # Evaluation framework
│   ├── __init__.py
│   ├── automated_eval.py            # Automated evaluation
│   ├── evaluator.py                 # Query evaluator
│   ├── graphrag_baseline.py         # GraphRAG baseline comparison
│   ├── query_set.py                 # Query test sets
│   ├── run_100_eval.py              # Run 100-query evaluation
│   └── run_100_eval_fast.py         # Fast 100-query evaluation
├── extraction/                      # Document extraction
│   ├── __init__.py
│   ├── canonical_mapper.py          # Map to canonical types
│   ├── canonicalizer.py             # Entity canonicalization
│   ├── document_classifier.py       # Classify document types
│   ├── duplicate_detector.py        # Detect duplicate entities
│   ├── entity_extractor.py          # Extract entities
│   ├── extraction_pipeline.py       # Full extraction pipeline
│   ├── ontology_centric_pipeline.py # Ontology-driven extraction
│   ├── ontology_manager.py          # Ontology management
│   ├── relation_extractor.py        # Extract relationships
│   ├── staging_loader.py            # Load to staging
│   └── validation.py                # Extraction validation
├── ingestion/                       # Document ingestion
│   ├── __init__.py
│   ├── chunker.py                   # Text chunking
│   ├── document_loader.py           # Load documents
│   └── ingestion_pipeline.py        # Full ingestion pipeline
├── memory/                          # Tri-memory system
│   ├── __init__.py
│   ├── episodic.py                  # Episodic memory
│   ├── inference.py                 # Memory inference
│   ├── semantic.py                  # Semantic memory
│   ├── symbolic.py                  # Symbolic memory (rules)
│   └── temporal.py                  # Temporal reasoning
├── migrations/                      # SQL migrations
│   ├── 001_ontology_tables.sql
│   ├── 002_seed_ontology_types.sql
│   ├── 003_seed_ontology_relations.sql
│   ├── 004_validation_triggers.sql
│   ├── 005_promotion_thresholds.sql
│   ├── 006_infra_ontology.sql
│   ├── 007_rfc_v2_dual_system.sql
│   ├── 008_approval_workflow.sql
│   ├── 009_message_bus.sql
│   ├── 010_pipeline_progress.sql
│   ├── 010_schema_versioning.sql
│   ├── 010_tenant_isolation.sql
│   ├── 011_api_keys.sql
│   ├── 012_entity_embeddings.sql
│   ├── 013_reference_ontologies.sql
│   ├── 014_aggregation_framework.sql
│   ├── 015_entity_dedup_hints.sql
│   └── 020_stage2_context_fields.sql
├── models/                          # Data models
│   ├── __init__.py
│   ├── context_bundle.py            # ContextBundle model
│   └── schema.py                    # SQLAlchemy models (Entity, Relationship, etc.)
├── monitoring/                      # Observability
│   ├── __init__.py
│   └── shadow_metrics.py            # Shadow mode metrics
├── ontology/                        # Ontology management
│   ├── __init__.py
│   ├── constrained_extractor.py     # Constrained extraction
│   ├── models.py                    # Ontology models
│   ├── prompt_generator.py          # Generate extraction prompts
│   ├── repository.py                # Ontology repository
│   └── shadow_adapter.py            # Shadow mode adapter
├── ontology_foundry/                # Ontology evolution
│   ├── __init__.py
│   ├── approval_manager.py          # Type approval workflow
│   ├── collision_detector.py        # Detect type collisions
│   ├── deprecation_manager.py       # Manage type deprecation
│   ├── hierarchy_enforcer.py        # Enforce type hierarchy
│   ├── rule_executor.py             # Execute ontology rules
│   ├── schema_service.py            # Schema service
│   ├── schema_version_manager.py    # Schema versioning
│   ├── type_lifecycle_manager.py    # Type lifecycle management
│   └── type_validator.py            # Type validation
├── pipeline/                        # Pipeline infrastructure
│   ├── __init__.py
│   └── progress.py                  # Pipeline progress tracking
├── rlm/                             # Reasoning Language Model
│   ├── memory_apis/                 # Memory API wrappers
│   │   ├── __init__.py
│   │   ├── episodic.py
│   │   ├── semantic.py
│   │   └── symbolic.py
│   ├── __init__.py
│   ├── executor.py                  # RLM execution
│   ├── router.py                    # RLM routing
│   ├── sandbox.py                   # RLM sandbox
│   ├── schemas.py                   # RLM schemas
│   └── sub_query.py                 # Sub-query handling
├── shared/                          # Shared utilities
│   ├── __init__.py
│   └── message_bus.py               # Event message bus
├── utils/                           # Utilities
│   ├── __init__.py
│   └── logger.py                    # Logging utilities
├── workers/                         # Background workers
│   ├── __init__.py
│   └── extraction_worker.py         # Async extraction worker
├── __init__.py
└── core.py                          # Core ContextFoundry class

src/decision_trace_layer/            # Decision Trace Layer (DTL)
├── __init__.py
├── agent_logger.py                  # Agent action logging
├── api.py                           # DTL API endpoints
├── decision_orchestrator.py         # Decision orchestration
├── models.py                        # DTL data models
├── precedent_middleware.py          # Precedent matching
└── precedent_search.py              # Precedent search
```

---

## 2. COMPONENT INVENTORY

### Agents (`src/context_foundry/agents/`)

| File | Purpose | CF Dependencies | Status |
|------|---------|-----------------|--------|
| `graph_builder.py` (1082 lines) | Extract entities/relationships from documents via LLM | models.schema, ontology, extraction | **Working** |
| `gardener.py` (1244 lines) | Maintain knowledge graph quality (promote, decay, archive) | models.schema | **Working** |
| `gardener_learning.py` (384 lines) | Process learning tickets to improve World Model | models.schema, learning_ticket_agent | **Working** |
| `retrieval.py` (2121 lines) | Build ContextBundle from tri-memory | models.schema, memory | **Working** |
| `reasoning.py` (917 lines) | LLM reasoning over ContextBundle | models.context_bundle | **Working** |
| `entity_resolver.py` (794 lines) | Resolve entity mentions to canonical entities | models.schema | **Working** |
| `identity_resolver.py` (837 lines) | Advanced identity resolution with embeddings | models.schema | **Working** |
| `relationship_inference.py` (905 lines) | Infer missing relationships | models.schema | **Working** |
| `sufficiency.py` (227 lines) | Compute coverage, freshness, source_agreement, relationship_density | None | **Working** |
| `learning_ticket_agent.py` (161 lines) | Create learning tickets from sufficiency gaps | models.schema | **Working** |
| `entity_profile_generator.py` (307 lines) | Stage 4: Generate entity profiles from World Model | models.schema, sufficiency | **Working** |
| `semantic_agent.py` (627 lines) | Query-time semantic processing | models.schema, retrieval | **Working** |
| `staging_validator.py` (663 lines) | Validate facts before promotion to TRUSTED | models.schema, ontology | **Working** |
| `directed_retriever.py` (675 lines) | Focused retrieval for specific entity/relationship sets | models.schema | **Working** |
| `tier1_resolver.py` (528 lines) | Fast tier-1 entity resolution | models.schema | **Working** |
| `query_pipeline.py` (319 lines) | Full query processing pipeline | semantic_agent, retrieval, reasoning | **Working** |
| `query_interpreter.py` (433 lines) | NL query → structured query | None | **Working** |
| `query_classifier.py` (105 lines) | Classify query type | None | **Working** |
| `validation.py` (266 lines) | Rule-based validation against symbolic memory | models.schema, memory.symbolic | **Working** |
| `tool_agent.py` (358 lines) | Tool-using agent for complex queries | tools/ | **Partial** |
| `scheduler.py` (381 lines) | Gardener job scheduling | gardener | **Working** |
| `conversation_store.py` (186 lines) | Store conversation history | models.schema | **Working** |
| `graph_loader.py` (282 lines) | Bulk graph loading utilities | models.schema | **Working** |
| `org_chart_loader.py` (322 lines) | Load org chart data | graph_loader | **Working** |

### Models (`src/context_foundry/models/`)

| File | Purpose | Status |
|------|---------|--------|
| `schema.py` (1331 lines) | SQLAlchemy models: Entity, Relationship, Rule, Document, etc. | **Working** |
| `context_bundle.py` (188 lines) | ContextBundle dataclass with uncertainty signals | **Working** |

### Memory (`src/context_foundry/memory/`)

| File | Purpose | Status |
|------|---------|--------|
| `semantic.py` | Entity/relationship graph queries | **Working** |
| `episodic.py` | Vector-based document retrieval | **Working** |
| `symbolic.py` | Rule evaluation | **Working** |
| `temporal.py` | Temporal reasoning (valid_from/valid_to) | **Working** |
| `inference.py` | Memory inference utilities | **Working** |

### Extraction (`src/context_foundry/extraction/`)

| File | Purpose | Status |
|------|---------|--------|
| `ontology_centric_pipeline.py` | Schema-guided extraction | **Working** |
| `entity_extractor.py` | Entity extraction from text | **Working** |
| `relation_extractor.py` | Relationship extraction | **Working** |
| `canonical_mapper.py` | Map raw types to canonical | **Working** |
| `canonicalizer.py` | Entity name canonicalization | **Working** |
| `duplicate_detector.py` | Detect duplicate entities | **Working** |
| `staging_loader.py` | Load extracted facts to STAGING | **Working** |
| `validation.py` | Validate extracted facts | **Partial** |

### API (`src/context_foundry/api/`)

| File | Purpose | Status |
|------|---------|--------|
| `external.py` (971 lines) | REST API Blueprint for external apps | **Working** |
| `bundle_builder.py` | Build ContextBundle for API responses | **Working** |
| `context_bundle.py` | API context bundle utilities | **Working** |

### Decision Trace Layer (`src/decision_trace_layer/`)

| File | Purpose | Status |
|------|---------|--------|
| `api.py` | DTL REST endpoints | **Working** |
| `models.py` | DTL data models | **Working** |
| `agent_logger.py` | Log agent decisions | **Working** |
| `decision_orchestrator.py` | Orchestrate decisions | **Working** |
| `precedent_middleware.py` | Match precedent decisions | **Working** |
| `precedent_search.py` | Search precedent database | **Working** |

---

## 3. DATABASE SCHEMA

### Core Tables

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `entities` | id (UUID), tenant_id, name, entity_type, lifecycle_state, confidence, valid_from, valid_to | Semantic memory nodes |
| `relationships` | id (UUID), tenant_id, source_id, target_id, relationship_type, lifecycle_state, provenance_text, qualifiers | Semantic memory edges |
| `documents` | id (UUID), tenant_id, title, doc_type, content | Source documents |
| `document_chunks` | id (UUID), document_id, tenant_id, text, embedding (vector) | Chunked text with embeddings |
| `rules` | id (UUID), name, rule_type, condition, action, priority | Symbolic memory rules |
| `learning_tickets` | id (UUID), tenant_id, gap_type, focal_entity_name, priority, status | Knowledge gaps to address |
| `query_logs` | id (UUID), tenant_id, query_text, response_text, confidence, context_bundle | Query audit log |
| `gardener_runs` | id (UUID), tenant_id, status, entities_promoted, conflicts_detected | Gardener run history |
| `api_keys` | id, name, key_hash, tenant_id, is_active, scopes | External API authentication |

### Lifecycle States

- `STAGING` → Newly extracted, unvalidated
- `TRUSTED` → Validated, used for reasoning
- `ARCHIVED` → Superseded or stale

### Current Data Counts

| Table | Count |
|-------|-------|
| Entities (TRUSTED) | 20,888 |
| Relationships (TRUSTED) | 3,890 |
| Documents | 7,760 |
| Document Chunks | 1,628 |
| Learning Tickets | 12 |
| Rules | 13 |

---

## 4. AGENTS LIST

| Agent Class | Purpose | Has Tests |
|-------------|---------|-----------|
| `GraphBuilderAgent` | Document → entity/relationship extraction | Partial (constrained_extraction) |
| `GardenerAgent` | Knowledge graph maintenance | Yes (test_gardener_thresholds) |
| `GardenerLearningProcessor` | Process learning tickets | No |
| `RetrievalAgent` | Build ContextBundle | Partial (regression) |
| `ReasoningAgent` | LLM reasoning over context | Partial (regression) |
| `ValidationAgent` | Rule-based validation | No |
| `QueryTimeSemanticAgent` | Query-time processing | Yes (test_query_pipeline) |
| `StagingValidatorAgent` | Validate STAGING facts | No |
| `RelationshipInferenceAgent` | Infer missing relationships | No |
| `ToolAgent` | Tool-using capabilities | No |
| `LearningTicketAgent` | Create learning tickets | No |
| `EntityProfileGenerator` | Generate entity profiles | No |
| `GraphLoaderAgent` | Bulk graph loading | No |

---

## 5. API ENDPOINTS

### Web App (`web_app.py`) - Internal Platform

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/magic-link` | POST | Request magic link login |
| `/auth/verify` | GET | Verify magic link token |
| `/auth/refresh` | POST | Refresh JWT |
| `/auth/me` | GET | Get current user |
| `/api/dev/auth` | POST | Dev-only auth bypass |
| `/api/keys` | GET/POST | Manage API keys |
| `/api/keys/<key_id>` | DELETE | Revoke API key |
| `/documents` | GET/POST | List/upload documents |
| `/documents/<id>` | GET | Get document details |
| `/documents/<id>/extraction` | POST | Re-queue extraction |
| `/api/vaults` | GET/POST | Manage vaults (tenants) |
| `/api/vaults/<id>` | GET/DELETE | Get/delete vault |
| `/dashboard/*` | GET | Dashboard views |

### External API (`src/context_foundry/api/external.py`)

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/v1/query` | POST | Natural language query | API Key |
| `/api/v1/context` | POST | Get structured context bundle | API Key |
| `/api/v1/entities/{name}` | GET | Get entity details + relationships | API Key |
| `/api/v1/health` | GET | Health check | None |

### DTL API (`src/decision_trace_layer/api.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/dtl/decisions` | GET/POST | List/create decisions |
| `/api/dtl/decisions/<id>` | GET | Get decision details |
| `/api/dtl/precedents/search` | POST | Search for precedents |

---

## 6. CONFIGURATION

### Environment Variables (Secrets)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` | DB connection parts |
| `SESSION_SECRET` | Flask session secret |
| `AI_INTEGRATIONS_OPENAI_API_KEY` | OpenAI API key |
| `AI_INTEGRATIONS_OPENAI_BASE_URL` | OpenAI base URL |
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth secret |
| `GEMINI_API_KEY` | Google Gemini API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |

### Environment Variables (Non-Secret)

| Variable | Value | Purpose |
|----------|-------|---------|
| `BRAIN_INTERNAL_URL` | `http://localhost:3000` | Internal service URL |
| `USE_ONTOLOGY_CENTRIC_PIPELINE` | `true` | Enable ontology-based extraction |

### Config Files

| File | Purpose |
|------|---------|
| `config/domain_schema.yaml` | Entity types (41), relationship types, validation rules |
| `config/canonical_mappings.yaml` | Raw type → canonical type mappings |
| `config/fiction_schema.yaml` | Schema for fiction domain |
| `config/investment_schema.yaml` | Schema for investment domain |

### Domain Schema Summary

- **Entity Types:** 41 (PERSON, ORGANIZATION, DOCUMENT, LOCATION, EVENT, CONCEPT, PROCESS, SERVICE, DATABASE, TEAM, INCIDENT, DATE, ...)
- **Relationship Types:** 28+ (WORKS_AT, MEMBER_OF, REPORTS_TO, PART_OF, OWNS, MANAGES, GOVERNS, IMPLEMENTS, ENABLES, DESCRIBES, REFERENCES, AUTHORED_BY, LOCATED_IN, OPERATES_IN, OCCURRED_ON, AFFECTS, TRIGGERED_BY, DEPENDS_ON, HELD_POSITION, INVESTED_IN, LEADS, COLLABORATED_WITH, AFFILIATED_WITH, RELATED_TO, ...)

---

## 7. TEST COVERAGE

### Tests with Unit/Integration Tests

| Test File | Component Covered |
|-----------|-------------------|
| `tests/test_cognitive_loop.py` | End-to-end cognitive loop |
| `tests/test_constrained_extraction.py` | Ontology-constrained extraction |
| `tests/test_decision_orchestrator.py` | DTL decision orchestration |
| `tests/test_dtl_core.py` | DTL core functionality |
| `tests/test_dtl_e2e.py` | DTL end-to-end |
| `tests/test_entity_resolver.py` | Entity resolution |
| `tests/test_gardener_thresholds.py` | Gardener promotion/decay thresholds |
| `tests/test_p0_fixes.py` | Priority 0 bug fixes |
| `tests/test_platform_integration.py` | Platform integration |
| `tests/test_precedent_middleware.py` | Precedent matching |
| `tests/test_progress.py` | Pipeline progress tracking |
| `tests/test_regression.py` | Regression tests |
| `tests/test_regression_suite.py` | Full regression suite |
| `tests/test_rlm_*.py` (4 files) | RLM subsystem |
| `tests/test_rls_security.py` | Row-level security |
| `tests/contracts/test_*.py` (4 files) | Interface contracts |
| `tests/e2e/test_*.py` (4 files) | End-to-end query tests |
| `tests/integration/test_rlm_parity.py` | RLM parity checks |

### Components WITHOUT Tests

| Component | Notes |
|-----------|-------|
| `EntityProfileGenerator` | New in Stage 4 |
| `GardenerLearningProcessor` | New in Stage 3 |
| `LearningTicketAgent` | New in Stage 3 |
| `sufficiency.py` | New in Stage 3 |
| `ValidationAgent` | Needs tests |
| `StagingValidatorAgent` | Needs tests |
| `RelationshipInferenceAgent` | Needs tests |
| `ToolAgent` | Needs tests |
| `conversation_store.py` | Needs tests |
| Most of `aggregation/` | Needs tests |
| Most of `ontology_foundry/` | Needs tests |

---

## 8. KNOWN ISSUES

### Code Quality Issues (from LSP)

1. **`src/context_foundry/api/external.py`** - 42 diagnostics (mostly type issues)
2. **`src/context_foundry/models/schema.py`** - 47 diagnostics (mostly type issues)
3. **`src/context_foundry/agents/entity_profile_generator.py`** - 23 diagnostics
4. **`src/context_foundry/agents/sufficiency.py`** - 1 diagnostic

### Extraction Quality Issues

1. **Missing HAS_COMPENSATION relationship type** - Salary data captured as qualifier on wrong relationship
2. **HELD_POSITION targets ORGANIZATION instead of JOB_TITLE** - Schema constraint not enforced during extraction
3. **Relationship type → target type validation missing** - Extraction doesn't validate that relationship targets are appropriate entity types

### Architecture Issues

1. **Nested context_foundry/ directory** - `src/context_foundry/context_foundry/` contains orphan_detector.py - should be moved
2. **Large files** - `retrieval.py` (2121 lines), `gardener.py` (1244 lines), `graph_builder.py` (1082 lines) could be refactored
3. **web_app.py** (262,073 bytes / ~7000+ lines) - Monolithic, should be split into blueprints

### Functional Issues

1. **RLS tenant context** - Must call `SET app.current_tenant_id` before every operation
2. **Session management** - Some agents don't properly rollback on errors
3. **Learning ticket deduplication** - Works but hit_count increments slowly

### TODO Items (from code comments)

1. `src/context_foundry/aggregation/service.py` - "TODO: Integrate with QueryLogger and DTL trace"

### Test Coverage Gaps

- Stage 3 (Learning) components lack unit tests
- Stage 4 (EntityProfileGenerator) lacks unit tests
- Many agents lack dedicated test files

---

## 9. SCRIPTS

| Script | Purpose |
|--------|---------|
| `scripts/stage4_demo.py` | Stage 4 demo (Q&A + Profile Generator) |
| `scripts/stage3_test_runner.py` | Stage 3 validation |
| `scripts/stage2_test_runner.py` | Stage 2 validation |
| `scripts/backfill_aliases.py` | Backfill entity aliases |
| `scripts/backfill_chunks.py` | Backfill document chunks |
| `scripts/batch_entity_embeddings.py` | Generate entity embeddings |
| `scripts/cleanup_*.py` | Various cleanup scripts |
| `scripts/dtl_*.py` | DTL validation scripts |
| `scripts/seed_*.py` | Seed data scripts |
| `scripts/value_demo.py` | Value demonstration |

---

## 10. WORKFLOWS

| Workflow | Command | Status |
|----------|---------|--------|
| Start All | `bash start.sh` | Running |
| RE Agent Batch | `python scripts/re_agent_batch.py` | Finished |
| Re-extraction | `python scripts/full_reextraction.py` | Finished |
| Stress Test Monitor | `python3 -u stress_test/monitor.py` | Running |

---

## 11. DEVELOPMENT STAGES

| Stage | Status | Key Components |
|-------|--------|----------------|
| Stage 1: Core Infrastructure | Complete | Entity, Relationship, Tri-Memory, Gardener |
| Stage 2: Context-Attached Knowledge | Complete | provenance_text, event_context, qualifiers, valid_from/valid_to |
| Stage 3: Learning from Interaction | Complete | sufficiency.py, learning_ticket_agent.py, gardener_learning.py |
| Stage 4: One Substrate, Many Apps | Complete | entity_profile_generator.py, stage4_demo.py |

---

*End of Inventory*
