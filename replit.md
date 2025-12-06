# Context Foundry - Dual-System Cognitive Architecture

## Overview
Context Foundry implements a **dual-system cognitive architecture** for enterprise knowledge graph governance, separating **Ontology Foundry** (schema governance) from **Context Foundry** (instance governance). This separation enables different governance cadences, confidence thresholds, and agent responsibilities for schema vs. instance management.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

---

## RFC v2: Dual-System Architecture

### System Separation

```
┌─────────────────────────────────────────────────────────────────┐
│                     ONTOLOGY FOUNDRY                            │
│                   (Schema Governance)                           │
│                                                                 │
│  Governs: What TYPES of things can exist                        │
│  Cadence: Weekly/Monthly                                        │
│  Confidence: 0.90+ (calibrated)                                 │
│  Storage: ontology.* schema                                     │
│                                                                 │
│  Agents: TypeValidator, HierarchyEnforcer, CollisionDetector    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ CONSTRAINS (types must be ACTIVE)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CONTEXT FOUNDRY                             │
│                   (Knowledge Governance)                        │
│                                                                 │
│  Governs: What SPECIFIC things we know                          │
│  Cadence: Continuous (per document)                             │
│  Confidence: 0.70+ (configurable per type)                      │
│  Storage: context.* schema                                      │
│                                                                 │
│  Agents: Extractor, Gardener, Resolver, QueryAgent              │
└─────────────────────────────────────────────────────────────────┘
```

### Database Schema Structure

| Schema | Purpose | Tables |
|--------|---------|--------|
| `ontology` | Schema governance | meta_ontology, types, relations, rules, versions, type_migration_map |
| `context` | Instance governance | entities, relationships, documents, embeddings, orphan_patterns |
| `shared` | Cross-system | users, audit_log, message_queue, confidence_thresholds |

### Layer 0: Immutable Meta-Ontology

Five immutable meta-types define the governance substrate:
1. **OntologyType** - Definition of entity types
2. **OntologyRelation** - Definition of relationship types
3. **ValidationRule** - Constraint rules for validation
4. **OntologyVersion** - Versioned snapshots
5. **LifecycleState** - Valid states for governed entities

### Ontology Lifecycle States

| State | Meaning | Extraction Allowed |
|-------|---------|-------------------|
| PROPOSED | LLM-generated or human-submitted | No |
| VALIDATING | Under rule evaluation | No |
| CONTESTED | Conflicts detected | No |
| APPROVED | Passed validation | No |
| ACTIVE | In production | **Yes** |
| DEPRECATED | Marked for removal | No |

### SHACL-Inspired Validation Rules

Six base validation rules (stored in `ontology.rules`):
1. `hierarchy_minimum_depth` - Types must have depth >= 3
2. `type_naming_convention` - PascalCase naming required
3. `uuid_namespace_allocation` - UUIDs follow layer conventions
4. `no_orphan_types` - Types should have relationships (WARNING)
5. `extraction_hints_required` - NLP hints required (WARNING)
6. `valid_properties_schema` - Valid JSON Schema required

### Validation Agents

| Agent | Responsibility |
|-------|---------------|
| **RuleExecutor** | Executes SHACL-inspired rules with ERROR/WARNING/INFO severity |
| **TypeValidator** | Validates JSON schema, required fields, naming conventions |
| **HierarchyEnforcer** | Ensures depth >= 3, no circular refs, valid layer progression |
| **CollisionDetector** | Detects name/UUID collisions, semantic duplicates |

---

## Implementation Status

### Session 6 Progress ✅

**Approval Workflow (RFC v2 §10-§11):**
- ✅ Migration 008: shared.users, shared.audit_log, ontology.approval_requests tables
- ✅ ApprovalManager with decision matrix routing:
  - Concrete type: ≥0.98 auto-approve, 0.90-0.98 Domain Lead, <0.90 reject
  - Abstract type: ≥0.98 Domain Lead, 0.90-0.98 Architecture Team, <0.90 reject
  - Deprecation: Always Architecture Team
- ✅ SLA deadlines: Level 1 (3 days), Level 2 (5 days), Level 3 (7 days)
- ✅ Auto-escalation with user reassignment on SLA expiry
- ✅ Complete audit trail for all approval decisions

**TypeLifecycleManager (Validation Orchestration):**
- ✅ Orchestrates TypeValidator → HierarchyEnforcer → CollisionDetector
- ✅ Calculates confidence: 1.0 - (0.1 × errors + 0.05 × warnings)
- ✅ Routes to ApprovalManager based on confidence thresholds
- ✅ Handles auto-approve, human review, and rejection workflows

**Message Bus (Agent Coordination):**
- ✅ Migration 009: message_queue, processed_events, event_subscriptions, dead_letter_queue
- ✅ PostgreSQL-backed publish/subscribe with exactly-once semantics
- ✅ 16 event types for governance coordination (TYPE_*, ENTITY_*, ORPHAN_*, etc.)
- ✅ Dead letter queue with retry logic and exponential backoff
- ✅ Targeted message support with correct completion semantics

**OrphanDetector (Feedback Channel):**
- ✅ Detects extraction patterns without matching ACTIVE ontology types
- ✅ Aggregates frequency with source documents and sample contexts
- ✅ Publishes ORPHAN_PATTERN_DETECTED events at threshold crossings (10/25/50)
- ✅ Creates feedback loop from Context Foundry to Ontology Foundry
- ✅ Supports resolve/dismiss workflow for human review
- ✅ **promote_to_type()**: Converts orphan patterns to PROPOSED types
- ✅ **finalize_promotion()**: Marks orphans RESOLVED on success, reverts to ACTIVE on failure

### Session 8 Progress ✅

**Context Bundle API (Pillar 4: Deliver Structured Truth):**
- ✅ Created Pydantic models: APIContextBundle, APIEntity, APIRelationship, FrontierNode, RetrievalMeta
- ✅ BundleBuilder class translates internal ContextBundle to public API schema with timing instrumentation
- ✅ POST /api/v1/context endpoint with request validation (query, focal_entity, max_hops, include_episodic)
- ✅ GET /api/v1/context/schema returns OpenAPI 3.0 documentation
- ✅ Fuzzy focal entity matching handles pluralization ("Payment Database" → "Payments Database")
- ✅ Graceful empty-state handling with explicit knowledge_gaps and low confidence (0.1)

**Schema Versioning & Deprecation (RFC v2 §7-§8):**
- ✅ Migration 010: ontology.type_versions, type_migrations tables, type_translation view
- ✅ SchemaVersionManager with recursive CTE for query translation (handles A→B→C chains)
- ✅ DeprecationManager with deprecate_type(), execute_migration(), get_deprecation_impact()
- ✅ Proper JSON deserialization for mapping_rules
- ✅ Type status transitions: ACTIVE → DEPRECATED → ARCHIVED
- ✅ Audit trail via shared.audit_log for all deprecation events
- ✅ type_translation view includes DEPRECATED and ARCHIVED (translations persist post-migration)
- ✅ All deprecation actions (MIGRATE/ARCHIVE/DELETE) create migration records
- ✅ Dependent type discovery uses proper array unnesting with ANY() operator
- ✅ Relationship migration tracks history via properties metadata

**Stress Test Results:**
| Metric | Value | Status |
|--------|-------|--------|
| Staging entities | 35 | All valid types |
| Garbage entities (conf < 0.5) | 0 | PASS |
| Invalid types in staging | 0 | PASS |
| Legacy invalid types | 14 | From pre-constrained era |

**API Test Results:**
| Query | Focal | Related | Confidence | Knowledge Gaps |
|-------|-------|---------|------------|----------------|
| Payment Database | 1 (fuzzy matched) | 13 | 90% | None |
| XYZ (unknown) | 0 | 1 | 10% | "Entity 'XYZ' not found in knowledge graph" |

### Session 7 Progress ✅

**End-to-End Governance Tests:**
- ✅ Test 1: Type proposal lifecycle (PROPOSED → Validated → Auto-Approved → ACTIVE)
- ✅ Test 2: Orphan pattern detection from document processing (5 events published)
- ✅ Test 3: Complete learning cycle - Orphan → Promote → Validate → Approve → Activate → Resolve

**Learning Cycle Implementation:**
- ✅ OrphanDetector.promote_to_type() creates PROPOSED types from orphan patterns
- ✅ Auto-generates properties_schema, extraction_hints, and description
- ✅ Sets orphan status to PROMOTING during validation
- ✅ Publishes TYPE_PROPOSED event for TypeLifecycleManager
- ✅ finalize_promotion() resolves or reverts orphan based on outcome
- ✅ Ontology grew from 212 to 215+ types through learning

### Session 5 Progress ✅

**Phase 1 (P0) - Foundation:**
- ✅ Created 3 database schemas (ontology, context, shared)
- ✅ Seeded Layer 0 meta-ontology (5 immutable meta-types)
- ✅ Loaded 212 types (9 Layer 1 + 203 Layer 2) across 8 domains

**Phase 2 (P1) - Rules Engine:**
- ✅ Created ontology.rules table with SHACL-inspired schema
- ✅ Seeded 6 base validation rules
- ✅ Built RuleExecutor class (tested and working)

**Phase 3 (P2) - Validation Agents:**
- ✅ Built TypeValidator agent
- ✅ Built HierarchyEnforcer agent
- ✅ Built CollisionDetector agent

### Key Files

| File | Purpose |
|------|---------|
| `src/context_foundry/api/context_bundle.py` | Public API Pydantic models for Context Bundle |
| `src/context_foundry/api/bundle_builder.py` | BundleBuilder class with timing instrumentation |
| `src/context_foundry/migrations/007_rfc_v2_dual_system.sql` | RFC v2 database migration |
| `src/context_foundry/migrations/008_approval_workflow.sql` | Approval workflow tables |
| `src/context_foundry/migrations/009_message_bus.sql` | Message bus infrastructure |
| `src/context_foundry/ontology_foundry/approval_manager.py` | Decision matrix routing & SLA |
| `src/context_foundry/ontology_foundry/type_lifecycle_manager.py` | Validation orchestration |
| `src/context_foundry/ontology_foundry/rule_executor.py` | SHACL-inspired rule execution |
| `src/context_foundry/ontology_foundry/type_validator.py` | Type validation agent |
| `src/context_foundry/ontology_foundry/hierarchy_enforcer.py` | Hierarchy enforcement agent |
| `src/context_foundry/ontology_foundry/collision_detector.py` | Collision detection agent |
| `src/context_foundry/shared/message_bus.py` | Event-driven agent coordination |
| `src/context_foundry/context_foundry/orphan_detector.py` | Orphan pattern detection |

---

## Previous Architecture (Sessions 1-4)

### Tri-Memory System
1. **Semantic Memory**: Entities and relationships with lifecycle states
2. **Episodic Memory**: Document embeddings with pgvector
3. **Symbolic Memory**: Business rules with priority ordering

### Gardener Agent
Four-pass maintenance system:
1. Corroboration Pass
2. Conflict Resolution Pass
3. Promotion Pass (type-specific thresholds)
4. Decay Pass

### Infrastructure Domain Template
- 28 entity types for asset-intensive infrastructure
- 15 relationship types
- Risk-based promotion thresholds (CRITICAL/HIGH/MEDIUM/LOW)

---

## External Dependencies

- **Database**: PostgreSQL (Neon for Replit)
- **LLM**: OpenAI gpt-4o-mini
- **Vector Embeddings**: pgvector with text-embedding-3-small
- **Web Framework**: Flask
- **Deployment**: Gunicorn

---

## Next Steps

### Session 9 (Future)
- Add regression tests for multi-hop queries and pluralization fuzziness
- Monitor retrieval timing metrics via logging/metrics dashboards
- Document error-handling conventions (400 vs 500) in API docs
- Schema versioning with query translation
- Production rollout with Row-Level Security (RLS)
- Web UI for approval workflows
- Integrate finalize_promotion() into TypeLifecycleManager callbacks
- /api/v1/context/stream endpoint for SSE streaming on large graphs
