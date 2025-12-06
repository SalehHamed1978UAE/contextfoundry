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

### Session 5 Progress ✅

**Phase 1 (P0) - Foundation:**
- ✅ Created 3 database schemas (ontology, context, shared)
- ✅ Seeded Layer 0 meta-ontology (5 immutable meta-types)
- ⏳ Awaiting 8 validated ontology SQL files (200 types)

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
| `src/context_foundry/migrations/007_rfc_v2_dual_system.sql` | RFC v2 database migration |
| `src/context_foundry/ontology_foundry/rule_executor.py` | SHACL-inspired rule execution |
| `src/context_foundry/ontology_foundry/type_validator.py` | Type validation agent |
| `src/context_foundry/ontology_foundry/hierarchy_enforcer.py` | Hierarchy enforcement agent |
| `src/context_foundry/ontology_foundry/collision_detector.py` | Collision detection agent |

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

### Remaining Session 5 Work
1. Load 8 validated ontology SQL files (200 types with status='ACTIVE')
2. Test full validation pipeline with proposed types

### Session 6 (Future)
- OrphanDetector agent for feedback channel
- Approval workflow with human-in-the-loop
- Schema versioning with query translation
- Production rollout with RLS
