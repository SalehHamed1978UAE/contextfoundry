> Superseded. This document describes design intent as of December 2025. The canonical architecture document is `docs/architecture.md`.

---

# Context Foundry - System Architecture

> Canonical reference for the actual implemented system.
> Last updated: December 2025

## Overview

Context Foundry is a **Partial-Knowledge Intelligence System** that implements a dual-system cognitive architecture for enterprise knowledge graph governance. It separates schema governance (Ontology Foundry) from instance governance (Context Foundry) to enable different governance cadences and confidence thresholds.

**Core Design Principles:**
- Never hallucinate - graduated response modes from FULL_ANSWER to NOT_FOUND
- Explicit uncertainty - confidence scores and evidence chains for every response
- Lifecycle governance - all facts start in STAGING, must earn promotion to TRUSTED
- Domain-agnostic - configurable via `domain_schema.yaml` for any domain

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                               │
│                    (Flask SPA @ port 5000)                          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PLATFORM FOUNDATION                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  Auth    │ │ Tenant   │ │ Document │ │ Metering │ │   MCP    │  │
│  │ Service  │ │ Service  │ │ Service  │ │ Service  │ │  Server  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                        web_app.py @ port 5000                        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                              HTTP/REST
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           BRAIN SERVICE                              │
│                        brain/app.py @ port 3000                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    COGNITIVE AGENTS                          │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐  │    │
│  │  │ Retrieval  │ │ Reasoning  │ │ Validation │ │  Query   │  │    │
│  │  │   Agent    │ │   Agent    │ │   Agent    │ │Classifier│  │    │
│  │  └────────────┘ └────────────┘ └────────────┘ └──────────┘  │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐               │    │
│  │  │  Entity    │ │  Graph     │ │  Staging   │               │    │
│  │  │ Resolver   │ │  Builder   │ │ Validator  │               │    │
│  │  └────────────┘ └────────────┘ └────────────┘               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  GOVERNANCE AGENTS                           │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐               │    │
│  │  │  Gardener  │ │  Identity  │ │ Scheduler  │               │    │
│  │  │   Agent    │ │  Resolver  │ │            │               │    │
│  │  └────────────┘ └────────────┘ └────────────┘               │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       TRI-MEMORY ARCHITECTURE                        │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐     │
│  │  SEMANTIC MEMORY │ │ EPISODIC MEMORY  │ │ SYMBOLIC MEMORY  │     │
│  │    (Entities)    │ │   (Documents)    │ │ (Rules/Relations)│     │
│  │                  │ │                  │ │                  │     │
│  │ - Entity records │ │ - Document chunks│ │ - Relationships  │     │
│  │ - Name embeddings│ │ - Chunk embeddings│ │ - Validation rules│    │
│  │ - Properties     │ │ - Provenance     │ │ - Constraints    │     │
│  │ - Lifecycle state│ │ - Timestamps     │ │ - Type hierarchies│    │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘     │
│                                                                      │
│                     PostgreSQL + pgvector (1536-dim)                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Agent Catalog

### Cognitive Agents

| Agent | File | Responsibility |
|-------|------|----------------|
| **RetrievalAgent** | `agents/retrieval.py` | Queries all 3 memory layers, assembles ContextBundle for reasoning. Integrates EntityResolver for query→entity matching. |
| **ReasoningAgent** | `agents/reasoning.py` | LLM-based reasoning with 3-phase confidence: sufficiency autorater, quadrant scoring, entity density. Uses gpt-4o-mini. |
| **ValidationAgent** | `agents/validation.py` | Post-reasoning validation against symbolic rules. Checks for rule violations. |
| **QueryClassifier** | `agents/query_classifier.py` | Classifies incoming queries, determines retrieval strategy, checks data sufficiency gates. |
| **EntityResolver** | `agents/entity_resolver.py` | 3-stage entity resolution: exact match → semantic search (pgvector) → fuzzy match (rapidfuzz). Returns candidates when ambiguous. |

### Extraction Agents

| Agent | File | Responsibility |
|-------|------|----------------|
| **GraphBuilderAgent** | `agents/graph_builder.py` | Ingests documents, extracts entities/relationships via LLM, writes to STAGING state. Chunked extraction for large documents. |
| **GraphLoaderAgent** | `agents/graph_loader.py` | Bulk loads structured data (JSON/YAML) into tri-memory. For bootstrapping or migrations. |
| **StagingValidatorAgent** | `agents/staging_validator.py` | Validates STAGING entities against schema rules before promotion. Checks cardinality, type compatibility, required fields. |

### Governance Agents

| Agent | File | Responsibility |
|-------|------|----------------|
| **GardenerAgent** | `agents/gardener.py` | 5-pass lifecycle maintenance: decay, promotion, conflict resolution, demotion, cleanup. Runs every 5 minutes. |
| **IdentityResolver** | `agents/identity_resolver.py` | Detects duplicate entities using name match, alias overlap, relationship overlap. Auto-merges at ≥0.95 confidence. |
| **GardenerScheduler** | `agents/scheduler.py` | Background scheduler for Gardener and IdentityResolver cycles. Also runs fast-validation pass. |

---

## Memory Layer Details

### Semantic Memory (`memory/semantic.py`)

Stores entities with embeddings for similarity search.

```
entities table:
├── id (UUID)
├── name (text)
├── entity_type (PERSON, SERVICE, INCIDENT, etc.)
├── properties (JSONB)
├── lifecycle_state (STAGING, TRUSTED, ARCHIVED)
├── confidence (0.0-1.0)
├── name_embedding (vector[1536])  -- for entity resolution
├── tenant_id (UUID)
└── created_at, updated_at
```

**Key operations:**
- `find_similar(embedding, k=10)` - Vector similarity search
- `find_by_type(entity_type)` - Type-filtered retrieval
- `update_lifecycle(entity_id, state)` - State transitions

### Episodic Memory (`memory/episodic.py`)

Stores document chunks with embeddings and provenance.

```
document_chunks table:
├── id (UUID)
├── document_id (FK)
├── chunk_index (int)
├── content (text)
├── embedding (vector[1536])
├── token_count (int)
├── tenant_id (UUID)
└── created_at
```

**Key operations:**
- `retrieve_relevant(query_embedding, k=5)` - Semantic retrieval
- `get_by_document(document_id)` - Full document chunks
- `get_provenance(chunk_id)` - Source tracking

### Symbolic Memory (`memory/symbolic.py`)

Stores relationships, rules, and constraints.

```
relationships table:
├── id (UUID)
├── source_entity_id (FK)
├── target_entity_id (FK)
├── relationship_type (MANAGES, USES, TRIGGERED_BY, etc.)
├── properties (JSONB)
├── lifecycle_state (STAGING, TRUSTED, ARCHIVED)
├── confidence (0.0-1.0)
├── tenant_id (UUID)
└── created_at
```

**Key operations:**
- `get_relationships(entity_id)` - All relationships for entity
- `find_path(source, target, max_depth)` - Graph traversal
- `get_rules_for_type(entity_type)` - Validation rules

### Inference Engine (`memory/inference.py`)

Path-based reasoning over the relationship graph.

- Shortest path finding
- Multi-hop relationship traversal
- Transitive closure computation

---

## Extraction Pipeline

```
Document Upload
      │
      ▼
┌─────────────────┐
│ Document Loader │  PDF, DOCX, TXT, OCR (Tesseract + Claude Vision)
│ ingestion/      │
│ document_loader │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Chunker      │  512-token overlapping chunks
│ ingestion/      │
│ chunker.py      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Domain Detector │  Semantic routing to domain types
│ brain/          │
│ classifier.py   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ GraphBuilder    │  LLM extraction (gpt-4o-mini)
│ agents/         │  Per-chunk extraction prevents saturation
│ graph_builder   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Duplicate       │  Prevents duplicate entity creation
│ Detector        │
│ extraction/     │
│ duplicate_det.  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Staging Loader  │  Writes to STAGING state
│ extraction/     │  All facts start unverified
│ staging_loader  │
└────────┬────────┘
         │
         ▼
    STAGING STATE
```

---

## Governance Lifecycle

### Entity Lifecycle States

```
     STAGING ────────────────────────────────────────┐
        │                                            │
        │ (validation passes,                        │
        │  confidence ≥ threshold,                   │
        │  time requirements met)                    │
        ▼                                            │
     TRUSTED ◄───────────────────────────────────────┘
        │                                      (reactivation)
        │ (confidence decay,
        │  superseded by newer fact,
        │  manual demotion)
        ▼
     ARCHIVED
```

### Gardener 5-Pass Cycle

Every 5 minutes, the Gardener runs:

1. **Decay Pass** - Apply type-specific confidence decay to stale facts
2. **Promotion Pass** - Move qualified STAGING → TRUSTED based on:
   - Confidence threshold (type-specific: Person=0.85, Service=0.75, etc.)
   - Corroboration count (how many sources confirm)
   - Time-in-staging requirement
3. **Conflict Pass** - Resolve conflicts using strategies:
   - `higher_confidence_wins` for attribute mismatches
   - `newer_wins` for temporal overlaps
   - `escalate_to_human` when margin < 0.15
4. **Demotion Pass** - Archive low-confidence or superseded facts
5. **Cleanup Pass** - Delete old resolved conflicts, orphaned STAGING data

### Promotion Thresholds (from database)

| Entity Type | Confidence | Corroborations | Time Required |
|-------------|------------|----------------|---------------|
| PERSON | 0.85 | 2 | 4 hours |
| INCIDENT | 0.80 | 3 | 2 hours |
| SERVICE | 0.75 | 1 | 1 hour |
| Default | 0.70 | 1 | 1 hour |

---

## Ontology Foundry (Schema Governance)

Located in `src/context_foundry/ontology_foundry/`

Manages schema types with their own lifecycle:

```
DRAFT → PROPOSED → APPROVED → DEPRECATED → RETIRED
```

| Component | Purpose |
|-----------|---------|
| `type_lifecycle_manager.py` | State transitions for types |
| `approval_manager.py` | Approval workflow with escalation |
| `schema_version_manager.py` | Version history and rollback |
| `collision_detector.py` | Prevents conflicting type definitions |
| `deprecation_manager.py` | Graceful type deprecation |
| `rule_executor.py` | SHACL-inspired validation rule execution |

---

## Platform Foundation

Located in `platform_foundation/src/`

| Service | File | Purpose |
|---------|------|---------|
| **AuthService** | `auth_service.py` | Magic link, API key, JWT, Google OAuth authentication |
| **TenantService** | `tenant_service.py` | Multi-tenancy with RLS policies |
| **DocumentService** | `document_service.py` | Upload, versioning, status tracking, re-queue |
| **MeteringService** | `metering_service.py` | Usage tracking for billing |
| **MCPServer** | `mcp_server.py` | Model Context Protocol for external AI integrations |
| **S3Connector** | `connectors/s3_connector.py` | AWS S3 bulk ingestion |
| **GDriveConnector** | `connectors/gdrive_connector.py` | Google Drive connector |

---

## Query/Reasoning Flow

```
User Query
    │
    ▼
┌─────────────────┐
│ QueryClassifier │  Classify intent, check data sufficiency
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ EntityResolver  │  3-stage: exact → semantic → fuzzy
│                 │  Returns entity or disambiguation candidates
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ RetrievalAgent  │  Query all 3 memory layers
│                 │  Build ContextBundle
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ReasoningAgent  │  LLM reasoning with context
│                 │  3-phase confidence calibration:
│                 │  1. Sufficiency autorater
│                 │  2. Quadrant scoring (entity+docs)
│                 │  3. Entity density grounding
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ValidationAgent │  Check against symbolic rules
└────────┬────────┘
         │
         ▼
    Response with:
    - answer_text
    - response_mode (FULL/PARTIAL/GUIDANCE/CLARIFY/NOT_FOUND)
    - confidence (0.0-1.0)
    - evidence_chain (source citations)
    - rule_violations (if any)
```

---

## Background Jobs

| Job | Location | Schedule | Purpose |
|-----|----------|----------|---------|
| Gardener Cycle | `agents/scheduler.py` | Every 5 min | Lifecycle governance |
| Fast Validation | `agents/scheduler.py` | Every 5 min | Quick STAGING→TRUSTED for high-confidence facts |
| Extraction Worker | `workers/extraction_worker.py` | Every 30 sec | Process document queue |
| Identity Resolution | `agents/scheduler.py` | Every 5 min | Merge duplicate entities |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Web Framework** | Flask (NOT FastAPI) |
| **Database** | PostgreSQL with pgvector extension |
| **Vector Store** | pgvector (NOT ChromaDB, NOT Neo4j) |
| **Embeddings** | OpenAI text-embedding-3-small (1536-dim) |
| **LLM** | OpenAI gpt-4o-mini |
| **Vision LLM** | Anthropic Claude Sonnet (for complex PDFs) |
| **Background Jobs** | Python threading + PostgreSQL message bus (NOT Celery/Redis) |
| **Authentication** | Magic Link, API Keys, JWT, Google OAuth |
| **Deployment** | Gunicorn |

---

## File Structure

```
context-foundry/
├── brain/                      # Brain service (port 3000)
│   ├── app.py                 # Flask app entry
│   ├── classifier.py          # Domain classification
│   └── routes/                # API routes
│
├── platform_foundation/        # Platform service components
│   ├── src/
│   │   ├── auth_service.py
│   │   ├── tenant_service.py
│   │   ├── document_service.py
│   │   └── connectors/        # S3, GDrive
│   └── migrations/            # Platform DB migrations
│
├── src/context_foundry/        # Core library
│   ├── agents/                # All agents
│   ├── memory/                # Tri-memory implementation
│   ├── extraction/            # Extraction pipeline
│   ├── ingestion/             # Document ingestion
│   ├── ontology_foundry/      # Schema governance
│   ├── models/                # Pydantic models, SQLAlchemy
│   ├── config/                # Domain schema, feature flags
│   ├── migrations/            # Core DB migrations
│   └── workers/               # Background workers
│
├── web_app.py                  # Platform service entry (port 5000)
├── start.sh                    # Starts both services
└── config/
    └── domain_schema.yaml      # Domain configuration
```

---

## Key Design Decisions

1. **PostgreSQL-only storage** - Unified storage with pgvector eliminates sync issues between separate vector stores

2. **STAGING-first ingestion** - All extracted facts must earn promotion, preventing garbage from polluting TRUSTED data

3. **3-stage entity resolution** - Exact → semantic → fuzzy matching with disambiguation prevents silent mismatches

4. **Type-specific thresholds** - Different entity types have different promotion requirements (Person needs higher confidence than Service)

5. **Graduated response modes** - FULL_ANSWER, PARTIAL_ANSWER, GUIDANCE, CLARIFY, NOT_FOUND - never forces hallucination

6. **Domain-agnostic schema** - All entity/relationship types defined in `domain_schema.yaml`, not hardcoded

---

## EntityResolver (3-Stage Pipeline)

Critical for query accuracy. Resolves ambiguous entity mentions:

**Stage 1: Exact Match**
- Case-insensitive name lookup
- If unique match → return immediately

**Stage 2: Semantic Search**
- OpenAI embeddings via pgvector
- Similarity threshold > 0.75
- If clear winner → return

**Stage 3: Fuzzy Match**
- rapidfuzz with word-level boost
- Threshold > 0.70
- Handles typos and word reordering

**Disambiguation**
- If top 2 candidates within 0.1 delta → return candidate list
- User/system must choose

**Current Performance (Day 4 Validation):**
- Pass rate: 55% (direct entity match)
- Resolution rate: 100% (found or disambiguated)
- NOT_FOUND rate: 0%

---

## Confidence Calibration (ReasoningAgent)

3-phase calibration prevents overconfident wrong answers:

1. **Sufficiency Autorater** - LLM evaluates if context can answer query
2. **Quadrant Scoring** - 4-quadrant based on entity presence + document presence
3. **Entity Density** - Counts known entity mentions in response as grounding proxy

Response modes based on calibrated confidence:
- ≥ 0.80 → FULL_ANSWER
- 0.60-0.80 → PARTIAL_ANSWER
- 0.40-0.60 → GUIDANCE
- < 0.40 with entities → CLARIFY
- < 0.40 no entities → NOT_FOUND
