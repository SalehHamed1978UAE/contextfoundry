# Context Foundry — Master Reference Document

> **Version:** 2.0.0  
> **Last Updated:** February 1, 2026  
> **Status:** Active Development (Phase 3 - Ontology Foundry + Corpus Maker 1.5)  
> **Purpose:** Consolidated knowledge base for AI coding agents (Claude Code, Codex, Replit Agent) and human developers

---

## Table of Contents

1. [The Bible — Core Philosophy](#1-the-bible--core-philosophy)
2. [What Context Foundry Is (and Isn't)](#2-what-context-foundry-is-and-isnt)
3. [The Tri-Memory Architecture](#3-the-tri-memory-architecture)
4. [The Full Cognitive Loop](#4-the-full-cognitive-loop)
5. [The Agent Ecosystem](#5-the-agent-ecosystem)
6. [The Query Pipeline & Context Bundle](#6-the-query-pipeline--context-bundle)
7. [The Extraction Pipeline](#7-the-extraction-pipeline)
8. [The Gardener — Entity Lifecycle Management](#8-the-gardener--entity-lifecycle-management)
9. [Data Gates & Response Modes](#9-data-gates--response-modes)
10. [Ontology Foundry (Phase 3)](#10-ontology-foundry-phase-3)
11. [The 6-Phase Roadmap](#11-the-6-phase-roadmap)
12. [Current Work: Corpus Maker 1.5](#12-current-work-corpus-maker-15)
13. [Future: App Integration Phase 2](#13-future-app-integration-phase-2)
14. [Future: RLM Integration](#14-future-rlm-integration)
15. [Evaluation Results & Evidence](#15-evaluation-results--evidence)
16. [Codebase Structure](#16-codebase-structure)
17. [Technology Stack](#17-technology-stack)
18. [Key Design Decisions & Lessons Learned](#18-key-design-decisions--lessons-learned)
19. [Validations — Proven vs. Hypothesized](#19-validations--proven-vs-hypothesized)
20. [Instructions for AI Coding Agents](#20-instructions-for-ai-coding-agents)

---

## 1. The Bible — Core Philosophy

**Context Foundry is the cognitive middleware layer for AI — the way AI software gets context, memory, and understanding.**

**The one-liner:** "Organizational object permanence for AI."

**The core promise:** Ingest knowledge. Create context. Tell the truth. Don't hallucinate.

### What CF Is

1. **Infrastructure, not a product** — Like JDBC, not Salesforce. CF is the layer between raw data and AI applications.
2. **A Cognitive Operating System** with:
   - Tri-memory architecture (semantic, episodic, symbolic)
   - Two-level governance (Ontology Foundry for schema, Context Foundry for instances)
   - Agents that maintain knowledge health
   - Grounded reasoning — refuses to hallucinate, admits uncertainty (Data Gates)

### Core Principles

1. **The abstraction matters more than the implementation** — Prove the idea works. Optimization comes later.
2. **Cognition needs different primitives than computation** — Entities, relationships, memory types — not variables and functions.
3. **The goal is a standard, not a startup** — If CF becomes how AI handles context, the business model is obvious.
4. **"Context Foundry" = where context is forged** — The place AI goes to get understanding.

### The Golden Rule

> **Never hallucinate. Admit uncertainty. Show your work.**

If CF doesn't know something, it says "I don't know" with explicit knowledge boundaries. This is the core differentiator from every other AI system.

**When in doubt, return here.**

---

## 2. What Context Foundry Is (and Isn't)

### What It IS

| Attribute | Description |
|-----------|-------------|
| Cognitive middleware | The layer between raw enterprise data and AI applications |
| Knowledge infrastructure | Any AI app can tap into CF's understanding |
| A truth engine | Returns grounded facts with confidence scores and provenance |
| Domain-agnostic | Configurable for IT Ops, Healthcare, Maritime, Finance, etc. |
| A learning system | Gets smarter over time through feedback loops |

### What It Is NOT

| Anti-Pattern | Why Not |
|-------------|---------|
| A graph database | It uses a graph, but it's not just a database |
| A RAG system | RAG retrieves text. CF builds understanding. |
| A chatbot | CF is infrastructure. Chatbots are built ON TOP of CF. |
| A search engine | CF reasons about connections, not just retrieves documents |
| A product for end users | CF is consumed by AI applications, not by humans directly |

### The Key Differentiator

| Knowledge Graph | RAG System | Context Foundry |
|----------------|------------|-----------------|
| Stores relationships | Retrieves documents | **Builds understanding** |
| Queries return data | LLM generates text | **Agents reason & learn** |
| Static structure | No memory | **Tri-layer memory** |
| No reasoning | Single-shot prompts | **Neuro-symbolic AI** |

> "If your demo doesn't show thinking, you haven't built Context Foundry."

---

## 3. The Tri-Memory Architecture

The architecture is inspired by cognitive science — how human memory works — applied to knowledge management.

### Memory Type 1: Semantic Memory ("The What")

**Factual knowledge about entities and relationships — the knowledge graph.**

- Stores: People, services, databases, teams, processes, and their connections
- Example: "Payment Service depends on User Database. Sarah owns Payment Service."
- Technology: PostgreSQL with pgvector (entities table with embeddings, 1536-dim via text-embedding-3-small)
- Analogy: Like knowing the subway map of a city — the permanent structure

**Table: `entities`**
```sql
entities:
├── id (UUID)
├── name (TEXT)
├── entity_type (TEXT) -- PERSON, SERVICE, DATABASE, SPECIFICATION, etc.
├── properties (JSONB)
├── embedding (vector(1536))
├── lifecycle_state (TEXT) -- STAGING, TRUSTED, ARCHIVED
├── confidence (FLOAT)
├── tenant_id (UUID)
└── created_at / updated_at
```

### Memory Type 2: Episodic Memory ("The When")

**Event-based knowledge with temporal context — timelines and document evidence.**

- Stores: Document chunks, incidents, changes, decisions with timestamps
- Example: "Payment Service went down on Dec 5th. Last time this happened, it took 45 minutes to resolve."
- Technology: Document chunks with embeddings in pgvector
- Analogy: Like remembering stories from your career — what happened, when, how it was resolved

**Table: `document_chunks`**
```sql
document_chunks:
├── id (UUID)
├── document_id (FK)
├── content (TEXT)
├── embedding (vector(1536))
├── chunk_index (INT)
├── tenant_id (UUID)
└── created_at
```

### Memory Type 3: Symbolic Memory ("The Rules")

**Business logic, policies, constraints, and inference patterns.**

- Stores: Escalation paths, business rules, domain constraints, typed relationships
- Example: "SEV1 incidents → escalate to VP Engineering within 15 minutes."
- Technology: PostgreSQL (relationships table, rules)
- Analogy: Like knowing the traffic laws — the rules that govern how things work

**Table: `relationships`**
```sql
relationships:
├── id (UUID)
├── source_entity_id (FK)
├── target_entity_id (FK)
├── relationship_type (TEXT) -- MANAGES, DEPENDS_ON, USES, HAS_SPECIFICATION, etc.
├── properties (JSONB)
├── lifecycle_state (TEXT)
├── confidence (FLOAT)
├── tenant_id (UUID)
└── created_at
```

### Why All Three Matter

Traditional RAG only has semantic memory (embeddings). That's why it gives "confident wrong answers" — it finds similar text but doesn't know:
- Whether entities are actually connected (symbolic)
- How reliable the source was (episodic)

**Precedence order: Symbolic > Semantic > Episodic**

### How All Three Work Together — Example

**Query:** "What happens if User Database fails at 2 AM?"

| Memory | Contribution |
|--------|-------------|
| **Semantic** | "Payment Service and Auth Service depend on User Database" |
| **Episodic** | "Last failure was Oct 15th, took 45 minutes to resolve" |
| **Symbolic** | "After-hours incidents escalate to on-call SRE. SEV1 requires VP notification within 15 minutes." |

**Combined answer:** "User Database failure would affect Payment Service and Auth Service. Based on the October incident, expect ~45 minute recovery. Since it's 2 AM, escalate to the on-call SRE (currently: Mike Chen). Per SEV1 policy, notify VP Engineering within 15 minutes."

---

## 4. The Full Cognitive Loop

Context Foundry implements a continuous cognitive cycle:

```
Ingestion (Sensing) → Documents arrive
       ↓
Perception (Interpreting) → Entities and relationships extracted
       ↓
Memory Formation (Understanding) → Facts added to tri-memory (STAGING)
       ↓
Maintenance (Updating) → Gardener promotes, decays, resolves conflicts
       ↓
Reasoning (Thinking) → Query pipeline builds ContextBundle, LLM reasons
       ↓
Expression (Communicating) → Grounded response with confidence + provenance
       ↓
Learning (Improving) → Feedback refines the graph
       ↓
[back to Ingestion]
```

This is not a pipeline — it's a continuous loop. The system is always sensing, always updating, always learning.

---

## 5. The Agent Ecosystem

### Agent Inventory (11+ Agents Built)

| Agent | File | Purpose | Input | Output |
|-------|------|---------|-------|--------|
| **GraphBuilderAgent** | `graph_builder.py` | Extracts entities/relationships from documents → STAGING | Document | STAGING facts |
| **GraphLoaderAgent** | `graph_loader.py` | Bulk loads structured data into tri-memory | Structured data | Memory entries |
| **StagingValidatorAgent** | `staging_validator.py` | Validates STAGING facts against schema rules | STAGING facts | VALID/INVALID status |
| **RetrievalAgent** | `retrieval.py` | Queries all 3 memory layers, routes queries, builds ContextBundle | Query + Entity | ContextBundle |
| **ReasoningAgent** | `reasoning.py` | LLM reasoning with 3-phase confidence calibration | ContextBundle | Answer + Confidence |
| **ValidationAgent** | `validation.py` | Checks reasoning against symbolic rules | Answer | Validated answer |
| **GardenerAgent** | `gardener.py` | 5-pass lifecycle management | Timer trigger | Promoted/demoted facts |
| **IdentityResolver** | `identity_resolver.py` | Detects and merges duplicate entities | Entity pairs | Merge decisions |
| **EntityResolver** | `entity_resolver.py` | 3-stage query→entity resolution (exact, semantic, fuzzy) | Query text | Resolved entity |
| **QueryClassifier** | `query_classifier.py` | Classifies queries, checks data sufficiency | Query | Query type + sufficiency |
| **ToolAgent** | `tool_agent.py` | Function-calling agent with KG + document tools | Query | Structured response |
| **RoleResolver** | `role_resolver.py` | 3-stage role resolution ("Who is the CEO?") | Role query | Resolved person |
| **SemanticAgent** | `semantic_agent.py` | Query-time semantic retrieval | Query | Semantic matches |
| **PostProcessor** | `post_processor.py` | Regex patterns catch relationships LLM missed | Extracted facts | Enhanced facts |

### Agent Categories (Cognitive Science Mapping)

| Category | Purpose | Agents |
|----------|---------|--------|
| **Sensing Agents** | Ingest and perceive | GraphBuilderAgent, GraphLoaderAgent |
| **Semantic Agents** | Build and maintain world model | StagingValidatorAgent, IdentityResolver |
| **Cognitive Agents** | Think and reason | RetrievalAgent, ReasoningAgent, ValidationAgent, QueryClassifier, EntityResolver, ToolAgent |
| **Maintenance Agents** | Keep knowledge healthy | GardenerAgent, GardenerScheduler |

### Agents Not Yet Built

| Agent | Purpose | Phase |
|-------|---------|-------|
| **Reflection Agent** | Self-critique of reasoning quality | Future |
| **Reinforcement Agent** | Learning loop from feedback | Future |
| **Planner Agent** | Multi-step query decomposition | Future (RLM) |

---

## 6. The Query Pipeline & Context Bundle

### Query Flow

```
User Query
    │
    ▼
EntityResolver (3-stage: exact → semantic → fuzzy)
    │
    ▼
QueryClassifier (classify: impact/ownership/dependency/escalation/expertise/specification)
    │
    ▼
RoleResolver (3-stage: exact title → org hierarchy → semantic)
    │
    ▼
RetrievalRouter (GRAPH_ONLY, DOCS_ONLY, or HYBRID)
    │
    ▼
RetrievalAgent
  ├── Query Semantic Memory (entities + relationships)
  ├── Query Episodic Memory (similar documents, vector search)
  ├── Query Symbolic Memory (matching rules)
  └── Assemble ContextBundle
    │
    ▼
Data Gates (sufficiency check — can we answer this?)
    │
    ├── Sufficient → ReasoningAgent (LLM reasoning with context)
    │                    │
    │                    ▼
    │              ValidationAgent (check against symbolic rules)
    │                    │
    │                    ▼
    │              Response: FULL_ANSWER or PARTIAL_ANSWER
    │
    └── Insufficient → Response: GATED or NOT_FOUND (no LLM call)
```

### The Context Bundle

The ContextBundle is the "product" that CF delivers. It's the contract between retrieval and reasoning.

```python
class ContextBundle:
    target_entity_name: str
    target_entity_found: bool
    query_type: str  # impact, ownership, dependency, escalation, expertise, specification
    
    # From Semantic Memory
    semantic_entities: List[Entity]
    semantic_relationships: List[Relationship]
    blast_radius_entities: List[Entity]  # for impact queries
    
    # From Episodic Memory
    episodic_documents: List[DocumentChunk]  # relevant document chunks
    
    # From Symbolic Memory
    symbolic_rules: List[Rule]  # applicable business rules
    
    # Metadata
    confidence_summary: ConfidenceSummary
    knowledge_boundaries: List[str]  # explicit gaps
```

---

## 7. The Extraction Pipeline

### Pipeline Flow

```
Document Upload
    │
    ▼
Document Loader (document_loader.py) — PDF/DOCX/TXT parsing + OCR
    │
    ▼
Chunker (chunker.py) — 512-token overlapping chunks
    │
    ▼
Extraction Pipeline (extraction_pipeline.py)
  ├── Entity Extractor (entity_extractor.py) — LLM extracts entities
  ├── Relation Extractor (relation_extractor.py) — LLM extracts relationships
  ├── PostProcessor (post_processor.py) — Regex catches missed relationships
  └── Duplicate Detector (duplicate_detector.py) — Prevents duplicate entities
    │
    ▼
Staging Loader (staging_loader.py) — Writes to STAGING state
    │
    ▼
Validation (staging_validator.py) — Schema conformance check
    │
    ▼
Entities land in STAGING (awaiting Gardener promotion)
```

### Defense-in-Depth Extraction

Three layers of validation ensure extraction quality:

1. **LLM Extraction** — Primary extraction via GPT-4o-mini + Claude Sonnet (dual-model consensus)
2. **Post-Processor** — Deterministic regex patterns for specs, relationships
3. **Gap Detector** — Identifies missing expected entities/relationships

### Multi-Model Extraction (Current)

- **GPT-4o-mini**: Primary extraction
- **Claude Sonnet 4**: Vision/complex PDFs and consensus building
- Confidence boosted when both models agree

### Specification Extraction (11 Patterns)

The PostProcessor includes generalizable regex patterns for:
- Energy density (Wh/kg, Wh/L)
- Temperature ranges (°C, °F)
- Production capacity (kg/hr, MW)
- Material compositions (chemical formulas like Li₇La₃Zr₂O₁₂)
- Efficiency percentages
- Cycle life
- Charge time
- Conductivity
- Thickness
- Pressure

---

## 8. The Gardener — Entity Lifecycle Management

### Lifecycle States

```
STAGING → TRUSTED → ARCHIVED
   │         │          │
   │         │          └── Historical, no longer current
   │         └── High confidence, used for reasoning
   └── Newly extracted, unverified
```

### The 5-Pass Gardener Cycle (runs every 5 minutes)

| Pass | Name | What It Does |
|------|------|-------------|
| 1 | **Decay** | Reduce confidence of facts not recently corroborated |
| 2 | **Promotion** | STAGING → TRUSTED based on confidence + corroboration thresholds |
| 3 | **Conflict Resolution** | Detect and resolve contradictory facts |
| 4 | **Demotion** | Archive low-confidence TRUSTED facts |
| 5 | **Cleanup** | Delete stale STAGING facts that never promoted |

### Promotion Thresholds (Type-Weighted)

| Entity Type | Confidence Threshold | Corroborations Required | Min Age |
|-------------|---------------------|------------------------|---------|
| Person | 0.85 | 2 | 4 hours |
| Service | 0.75 | 1 | 1 hour |
| Incident | 0.80 | 3 | 2 hours |
| Default | 0.70 | 1 | 1 hour |

**Key insight:** Different entity types need different promotion criteria. A person's identity matters more than a service name, so it requires higher confidence.

---

## 9. Data Gates & Response Modes

### The Data Gates Principle

> "Don't give the LLM the opportunity to hallucinate."

Data Gates check evidence sufficiency BEFORE calling the LLM. If there's not enough data to answer, return immediately without LLM invocation.

### Three-Level Validation (`src/context_foundry/validation/data_gates.py`)

1. **Entity Not Found Gate**: If query mentions unknown entity → prompt for clarification
2. **No Relevant Chunks Gate**: If semantic search returns no matches → admit no data
3. **Ungrounded Answer Gate**: If LLM answer contains claims not in context → flag uncertainty

### Response Modes

| Mode | Condition | Behavior |
|------|-----------|----------|
| **FULL_ANSWER** | Entity found + sufficient relationships + documents | Full LLM reasoning with provenance |
| **PARTIAL_ANSWER** | Entity found + some data missing | Answer what's known, explicitly state gaps |
| **GUIDANCE** | Entity found but sparse data | Suggest where to find more information |
| **CLARIFY** | Ambiguous entity (multiple matches) | Ask which entity the user means |
| **NOT_FOUND** | Entity doesn't exist in graph | Immediate "entity not found" — no LLM call |

### The General Rule (Critical)

**For ANY query that references a specific entity:**
1. Check if entity exists in graph
2. If not found → "Entity not found" response immediately
3. Do NOT call LLM to fabricate an answer

**This applies to ALL query types**: impact, ownership, dependency, expertise, escalation, specification.

### The Three-Tier Response Structure

Every response should distinguish:
1. **CONFIRMED** — Facts verified in knowledge graph with provenance
2. **INFERRED** — Logical conclusions with confidence scores and reasoning chains
3. **KNOWLEDGE BOUNDARIES** — Explicit statement of what CF doesn't know

---

## 10. Ontology Foundry (Phase 3)

### The Problem Phase 3 Solves

Phase 2 extracts whatever it finds. But enterprises need to know:
- Is the data **complete**? (Does every executive have compensation data?)
- Is it **consistent**? (Can there be two CEOs?)
- Is it **conformant**? (Does the structure match our expected schema?)

**The shift:** From "extract what we find" to "extract what we need."

### Two-Level Governance

| Level | System | Governs | Change Cadence | Confidence |
|-------|--------|---------|----------------|------------|
| Schema | **Ontology Foundry** | What types of things exist | Slow (human-approved) | High |
| Instance | **Context Foundry** | Actual entities and relationships | Continuous (agent-driven) | Variable |

**Key design decision:** Ontology constrains Context, not vice versa.

### The Four-Layer Ontology Model

```
Layer 0: Meta-Core (IMMUTABLE)
├── Entity, Event, Record, Relation
├── Hardcoded into CF — never modified
└── UUID scheme: 00000000-0000-4000-a000-*

Layer 1: Common Core (SHARED)
├── Asset, Agent, Person, Organization
├── Shared across all domains
└── UUID scheme: 00000000-0000-4001-a000-*

Layer 2: Domain Templates (PER-DOMAIN)
├── IT Ops: Service, Database, Incident, Runbook, etc.
├── Maritime: Vessel, Port, Cargo, Route, etc.
├── Healthcare: Patient, Diagnosis, Treatment, etc.
└── UUID scheme: domain-specific

Layer 3: Tenant Extensions (PER-CUSTOMER)
├── Customer-specific entity types
├── Must inherit from Layer 1 or Layer 2
└── UUID scheme: tenant-specific
```

### Ontology Lifecycle States

```
PROPOSED → VALIDATING → CONTESTED → APPROVED → ACTIVE → DEPRECATED
```

### Ontology Foundry Agents

| Agent | Responsibility |
|-------|----------------|
| TypeValidator | Check JSON schema validity, property completeness |
| CollisionDetector | Detect name collisions across domains |
| HierarchyEnforcer | Ensure depth ≥ 3, no Layer 1 direct inheritance |
| NamespaceGuard | Ensure UUID allocation follows conventions |
| SchemaPromoter | Promote APPROVED → ACTIVE when human approves |
| DeprecationAgent | Identify unused types for deprecation |
| OrphanDetector | Surface patterns that don't fit existing types |

### Entity Types (16 current)

```python
ENTITY_TYPES = [
    "PERSON", "ORGANIZATION", "PROJECT", "PRODUCT", "SERVICE", "ROLE",
    "LOCATION", "DEPARTMENT", "TEAM", "INCIDENT", "DOCUMENT", "POLICY",
    "METRIC", "SPECIFICATION", "EVENT", "CONTRACT"
]
```

### Relationship Types (20+)

```python
RELATIONSHIP_TYPES = [
    "WORKS_FOR", "REPORTS_TO", "MANAGES", "LEADS", "MEMBER_OF",
    "SUPPLIES_TO", "SUPPLIER_OF", "PROVIDES", "DEPENDS_ON", "OWNS",
    "CREATED", "AUTHORED", "APPROVED", "TRIGGERED_BY", "RESOLVED_BY",
    "LOCATED_IN", "PART_OF", "MANUFACTURES", "PARTNERS_WITH",
    "CONTRACTS_WITH", "HAS_SPECIFICATION"
]
```

---

## 11. The 6-Phase Roadmap

```
Phase 1          Phase 2          Phase 3          Phase 4          Phase 5          Phase 6
  MVP             MVP+           Ontology         Streaming       Multi-Tenant     Autonomous
   ✅               ✅            Foundry
COMPLETE        COMPLETE        ← CURRENT
   │               │               │                │                │                │
   ▼               ▼               ▼                ▼                ▼                ▼
Validate       Extraction      Define what      Near-real-      Production       CF acts,
tri-memory     + scale +       should exist     time updates    for large        not just
architecture   evaluation                                       orgs             answers
```

### Phase 1: MVP ✅ COMPLETE

**What we proved:**
- Tri-memory architecture: ✅ Working
- Graph lifecycle (STAGING → TRUSTED → ARCHIVED): ✅ Operational
- Uncertainty surfacing: ✅ Data Gates return "insufficient data"
- Multi-hop reasoning: ✅ Working
- Beat GraphRAG: ✅ Won 12-3 in A/B evaluation

### Phase 2: MVP+ ✅ COMPLETE

**What we built:**
- Defense-in-Depth Extraction (LLM + Post-Processor + Gap Detector)
- Entity Lifecycle (Staging → Trusted → Archived)
- Direction-Aware Relationships
- Multi-Tenant Vaults
- E2E Test Suite (5 vaults, 49 queries)
- Data Gates (0% hallucination)
- A/B Evaluation Framework

### Phase 3: Ontology Foundry ← CURRENT

**What's being built:**
- Four-Layer Ontology Model (Layer 0-3)
- Schema validation and gap detection
- Constraint enforcement ("Only one CEO per org")
- Schema-guided extraction
- IT Operations as first domain template

### Phase 4: Streaming (Future)

- Streaming Perception — continuous document ingestion
- Temporal Knowledge — time-versioned facts
- Cross-Domain Reasoning

### Phase 5: Multi-Tenant (Future)

- Federated instances across organizations
- Hardened access control (Row-Level Security)
- Production infrastructure (monitoring, alerting, SLAs)

### Phase 6: Autonomous (Future)

- Action Framework — safe, bounded, audited actions
- Workflow Integration — approval systems, ticketing
- Human-in-the-Loop — escalate when confidence is low
- Learning from Actions — improve based on outcomes

**"The System Comes Alive."**

---

## 12. Current Work: Corpus Maker 1.5

### Goal

Achieve **90% accuracy** on QA tests through systematic improvements.

**Current Status:** 82% accuracy (82/100 on ClaudeCode Nexus Industries)

### Completed Improvements

1. **Technical Specification Extraction** - 11 generalizable regex patterns
2. **152 SPECIFICATION entities** extracted and stored
3. **Post-processor hardening** for energy density, temperature, materials, etc.

### Remaining Work

1. **Add SPECIFICATION retrieval tool** to ToolAgent
   - Query specs by type (energy_density, temp_range, material_composition, etc.)
   - Route spec-related queries to SPECIFICATION entity queries

2. **Improve role resolution** for temporal roles ("former CEO", "current President")

3. **Aggregation query reliability** - Fix counting queries

4. **Date parsing consistency**

### Key Files

- `src/context_foundry/agents/tool_agent.py` - Needs `get_specifications` tool
- `src/context_foundry/agents/retrieval_router.py` - Needs spec query routing
- `src/context_foundry/extraction/post_processor.py` - Spec extraction patterns
- `src/context_foundry/validation/inference_validator.py` - Answer validation

### Test Infrastructure

- **Web UI**: `/test-runner`
- **CLI**: `python -m src.test_runner.runner --corpus "ClaudeCode Nexus Industries"`
- **Corpus Maker**: `/corpus-maker`

---

## 13. Future: App Integration Phase 2

### Memory Endpoints

```python
GET /api/v1/memory/events        # Query interaction logs
POST /api/v1/memory/corrections  # Submit corrections
GET /api/v1/memory/snapshot      # Pre-load entities for sessions
```

### Alias Governance

- **Lifecycle**: PROPOSED → CONFIRMED → TRUSTED
- **Auto-propose** from query patterns
- **Learn** from user corrections
- **Table**: `cf_entity_aliases`

### Background Worker

- Aggregate usage statistics per entity
- Detect alias patterns from query logs
- Auto-propose high-confidence aliases

### Session Snapshots

Pre-load relevant entities for Meeting Assistant app:
- Reduce latency for real-time verification
- Pre-cache EntitySummary + relationships

---

## 14. Future: RLM Integration

### Overview

**Recursive Language Models (RLM)** allow LLMs to write code that queries memory, enabling multi-hop reasoning without stuffing everything into context.

### Phase 1: Memory APIs (Week 1-2)

```python
SemanticMemoryAPI:
  - find_entities(entity_type, limit)
  - find_similar(query, k, entity_type)
  - get_entity(entity_id)
  - find_by_property(property_name, property_value)

EpisodicMemoryAPI:
  - search(query, k, document_type)
  - get_chunk(chunk_id)
  - get_document_chunks(document_id)
  - get_provenance(chunk_id)

SymbolicMemoryAPI:
  - get_relationships(entity_id, direction, relationship_type)
  - find_path(source_id, target_id, max_depth)
  - get_related_entities(entity_id, relationship_type)
  - traverse(start_id, relationship_types, depth)
```

### Phase 2: REPL Executor (Week 3-4)

- Sandboxed Python execution
- Safe builtins only (no imports, no eval, no file access)
- Progress tracker with circuit breaker
- Iteration limits and timeouts

### Phase 3: Sub-Query API (Week 5)

```python
SubQueryAPI:
  - query(prompt, max_tokens) → str
  - verify(claim, evidence) → VerificationResult
  - summarize(content, focus) → str
```

- Budget tracking (tokens, API calls)
- Model presets (Claude Haiku for sub-queries, Sonnet for root)

### Phase 4: Query Router (Week 6)

- Complexity classifier (score ≥3 → RLM pipeline)
- Multi-hop patterns: "which X affected by Y", "trace X through Y"

### Phase 5: Integration & Testing (Week 7-8)

### RLM Success Metrics

| Metric | Target |
|--------|--------|
| Complex query accuracy | +20% vs standard pipeline |
| Evidence citation rate | +15% |
| Cost per complex query | < $0.50 |
| P95 latency (complex) | < 30s |
| Circuit breaker rate | < 10% |

---

## 15. Evaluation Results & Evidence

### A/B Evaluation: CF vs GraphRAG (100 queries)

| Metric | Context Foundry | GraphRAG | Winner |
|--------|----------------|----------|--------|
| Overall Winner | 12 | 3 | **CF** |
| Provenance Score | 2.32/3 | 0.13/3 | **CF (18x better)** |
| Relationship Citations | 32% | 10% | **CF (3x better)** |
| Rule Citations | 100% | 3% | **CF (33x better)** |
| Response Detail | 5,602 chars | 322 chars | **CF (17x more)** |
| Hallucination Rate | 0% | N/A | **CF** |

### Key Finding

GraphRAG returned confident-sounding wrong answers. CF returned honest answers with explicit uncertainty.

---

## 16. Codebase Structure

```
context-foundry/
├── brain/                          # Brain service (port 3000)
│   ├── app.py
│   ├── classifier.py
│   └── routes/
│
├── platform_foundation/            # Platform service components
│   ├── src/
│   │   ├── auth_service.py        # Magic link, API key, JWT, Google OAuth
│   │   ├── tenant_service.py
│   │   ├── document_service.py
│   │   └── connectors/            # S3, GDrive
│   └── migrations/
│
├── src/context_foundry/            # Core library
│   ├── agents/                    # All agents (see Section 5)
│   ├── memory/                    # Tri-memory (semantic, episodic, symbolic)
│   ├── extraction/                # Extraction pipeline + post-processor
│   ├── ingestion/                 # Document ingestion
│   ├── ontology_foundry/          # Schema governance (Phase 3)
│   ├── validation/                # Data gates, coherence checker
│   ├── rlm/                       # RLM integration (TODO)
│   ├── models/                    # Pydantic, SQLAlchemy
│   ├── config/
│   └── migrations/
│
├── src/test_runner/               # Test infrastructure
├── src/corpus_maker/              # Corpus management
│
├── web_app.py                      # Platform entry (port 5000)
├── start.sh                        # Starts both services
├── config/
│   └── domain_schema.yaml
└── docs/
    ├── CF_MASTER_REFERENCE.md     # THIS FILE
    └── ...
```

---

## 17. Technology Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Web Framework | **Flask** | Two services: Platform (5000), Brain (3000) |
| Database | **PostgreSQL** | Single DB with pgvector extension |
| Vector Store | **pgvector** | All embeddings (NOT ChromaDB, NOT Neo4j) |
| Embeddings | **OpenAI text-embedding-3-small** | 1536-dimensional |
| LLM (Primary) | **OpenAI gpt-4o-mini** | Primary reasoning |
| LLM (Vision) | **Anthropic Claude Sonnet 4** | Complex PDF processing |
| LLM (RLM Root) | **Anthropic Claude Sonnet 4.5** | Future |
| LLM (RLM Sub) | **Anthropic Claude Haiku 4.5** | Future |
| Background Jobs | **Python threading + PostgreSQL** | NOT Celery/Redis |
| Fuzzy Matching | **rapidfuzz** | Entity resolution |
| Deployment | **Gunicorn** | |

### What's NOT Used

| Technology | Status | Alternative |
|------------|--------|-------------|
| Neo4j | ❌ | PostgreSQL (relationships table) |
| ChromaDB | ❌ | pgvector |
| FastAPI | ❌ | Flask |
| Celery + Redis | ❌ | PostgreSQL message bus + threads |

**Key design decision:** PostgreSQL-only storage. Unified storage with pgvector eliminates sync issues.

---

## 18. Key Design Decisions & Lessons Learned

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| PostgreSQL-only | Unified storage, no sync issues |
| Two-level governance | Schema changes need different cadence than instance changes |
| One-way constraint (Ontology → Context) | Schema should be stable foundation |
| Entity lifecycle (STAGING→TRUSTED) | Prevents garbage from entering canonical graph |
| Data Gates (pre-LLM check) | Prevent hallucination at architecture level |
| Type-weighted promotion | Different entities need different confidence levels |

### Lessons Learned

1. **Governance must be enforced, not optional.** Application-level validation isn't enough.

2. **Don't give the LLM the opportunity to hallucinate.** Gate queries BEFORE LLM invocation.

3. **Solve problems generally, not specifically.** Every fix should apply to ALL query types.

4. **Latency is not the differentiator.** CF is slightly slower but dramatically better at provenance and honesty.

5. **The learning loop is the gap.** The system ingests and answers, but doesn't yet systematically learn from feedback.

6. **Schema drift is the enemy.** Without ontology governance, aggressive LLM extraction creates type pollution.

---

## 19. Validations — Proven vs. Hypothesized

| # | Validation | Status | Evidence |
|---|------------|--------|----------|
| 1 | Tri-memory outperforms single-memory | **NOT PROVEN** | A/B test compared whole systems |
| 2 | Symbolic precedence matters | **NOT PROVEN** | No isolated test yet |
| 3 | Entity/relationship beats flat retrieval | **PARTIAL (12-3 win)** | A/B evaluation |
| 4 | Shared context across apps | **NOT PROVEN** | No multi-app test yet |
| 5 | Domain-independent | **PARTIAL** | IT Ops works; others not tested |

### What's Proven

- CF's overall architecture works better than GraphRAG (12-3 win)
- Data Gates eliminate hallucination (0% rate)
- Entity lifecycle governance prevents garbage data
- Provenance tracking provides auditability (18x better)

### Honest Assessment

> A hypothesis isn't a weakness. Every important idea starts as a hypothesis. The weakness would be claiming it's proven when it's not.

---

## 20. Instructions for AI Coding Agents

When working on Context Foundry:

1. **Read this document first.** It contains the accumulated design decisions and rationale.

2. **Never bypass Data Gates.** If entity doesn't exist → return NOT_FOUND. Never fabricate.

3. **Respect the lifecycle.** All new facts start in STAGING. Only the Gardener promotes.

4. **Solve generally, not specifically.** Every fix should work for ALL query types.

5. **Ontology constrains Context.** Schema changes go through Ontology Foundry governance.

6. **PostgreSQL is the only database.** No Neo4j, no ChromaDB, no Redis.

7. **Check replit.md and this document before making changes.** Understand current state.

8. **The core job is: Tell the truth. Don't hallucinate.** Everything else serves this.

9. **No band-aids.** Fix the SYSTEM to be capable, not just the specific failing case.

10. **Test thoroughly.** Use the test runner to validate changes don't regress accuracy.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2026-02-01 | Merged master roadmap with RLM specs, Corpus Maker 1.5, App Integration |
| 1.0.0 | 2026-01 | Initial master reference document |

---

*"Intelligence requires a world model. Context Foundry is that world model."*
