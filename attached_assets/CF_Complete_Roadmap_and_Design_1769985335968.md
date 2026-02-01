# Context Foundry — Complete Roadmap, Architecture & Design Reference

> **Purpose:** This is the consolidated knowledge base for Context Foundry. It contains the full roadmap, architecture, design decisions, research findings, and implementation details accumulated across months of development. Use this document to onboard new AI coding agents (Claude Code, Codex, Replit) or humans to the project.
>
> **Last Updated:** February 2026
>
> **Author:** Saleh (Creator & Lead), compiled from collaborative design sessions

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
10. [Ontology Foundry (Phase 3) — Full Specification](#10-ontology-foundry-phase-3--full-specification)
11. [The 6-Phase Roadmap](#11-the-6-phase-roadmap)
12. [Evaluation Results & Evidence](#12-evaluation-results--evidence)
13. [Codebase Structure (What's Actually Built)](#13-codebase-structure-whats-actually-built)
14. [Technology Stack](#14-technology-stack)
15. [Key Design Decisions & Lessons Learned](#15-key-design-decisions--lessons-learned)
16. [Validations — What's Proven vs. Hypothesized](#16-validations--whats-proven-vs-hypothesized)
17. [SavePoint & Current State](#17-savepoint--current-state)

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
├── entity_type (TEXT) -- PERSON, SERVICE, DATABASE, etc.
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
├── relationship_type (TEXT) -- MANAGES, DEPENDS_ON, USES, etc.
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

### Why Separate Memories?

1. **Different update cadences** — Entities change occasionally; documents arrive continuously; rules change with policy
2. **Different confidence models** — Entity existence is high-confidence; document freshness decays; relationship confidence varies
3. **Different query patterns** — "Does X exist?" vs "What documents mention X?" vs "What depends on X?"
4. **Explainability** — Can show which entities, documents, and rules contributed to each answer

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

### Agent Inventory (11 Agents Built)

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
| **GardenerScheduler** | `scheduler.py` | Runs Gardener/IdentityResolver on 5-min cycles | Timer | Cycle completion |

### Agent Categories (Cognitive Science Mapping)

| Category | Purpose | Agents |
|----------|---------|--------|
| **Sensing Agents** | Ingest and perceive | GraphBuilderAgent, GraphLoaderAgent |
| **Semantic Agents** | Build and maintain world model | StagingValidatorAgent, IdentityResolver |
| **Cognitive Agents** | Think and reason | RetrievalAgent, ReasoningAgent, ValidationAgent, QueryClassifier, EntityResolver |
| **Maintenance Agents** | Keep knowledge healthy | GardenerAgent, GardenerScheduler |

### Agents Not Yet Built

| Agent | Purpose | Phase |
|-------|---------|-------|
| **Reflection Agent** | Self-critique of reasoning quality | Future |
| **Reinforcement Agent** | Learning loop from feedback | Future |
| **Planner Agent** | Multi-step query decomposition | Partial |

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
QueryClassifier (classify: impact/ownership/dependency/escalation/expertise)
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
    # What the query is about
    target_entity_name: str
    target_entity_found: bool
    query_type: str  # impact, ownership, dependency, escalation, expertise
    
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

### Context Bundle API (External Interface)

```
POST /api/v1/context
{
    "query": "What services are affected if Payment Database goes down?",
    "focal_entity": "Payment Database",
    "max_hops": 2,
    "include_episodic": true,
    "include_symbolic": true
}

Response:
{
    "bundle": { ... },
    "confidence": 0.87,
    "knowledge_boundaries": ["No visibility into downstream consumers of..."],
    "provenance": { ... }
}
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

1. **LLM Extraction** — Primary extraction via GPT-4o-mini
2. **Post-Processor** — Deterministic validation of extracted facts
3. **Gap Detector** — Identifies missing expected entities/relationships

### Ontology-Constrained Extraction (Phase 3)

In Phase 3, extraction becomes schema-guided:
- Dynamic prompts generated from the ontology (no more static YAML)
- Pydantic models constrained to valid types
- Uses Instructor for structured LLM output
- Tracks skipped entities with reasons

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

**Key insight:** Different entity types need different promotion criteria. A person's identity matters more than a service name, so it requires higher confidence.

---

## 9. Data Gates & Response Modes

### The Data Gates Principle

> "Don't give the LLM the opportunity to hallucinate."

Data Gates check evidence sufficiency BEFORE calling the LLM. If there's not enough data to answer, return immediately without LLM invocation.

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

**This applies to ALL query types**, not just blast radius:
- Impact: "What is affected if X fails?"
- Ownership: "Who owns X?"
- Dependencies: "What does X depend on?"
- Expertise: "Who is the expert on X?"
- Escalation: "Who to contact for X issues?"

### The Three-Tier Response Structure

Every response should distinguish:
1. **CONFIRMED** — Facts verified in knowledge graph with provenance
2. **INFERRED** — Logical conclusions with confidence scores and reasoning chains
3. **KNOWLEDGE BOUNDARIES** — Explicit statement of what CF doesn't know

Example:
```
Confirmed Impact:
- Payment Service (93%): Core payment processing
- Fraud Detection Service (90%): Real-time fraud detection

Inferred Impact:
- Checkout Service (75%): Inferred via Payment Service dependency

Knowledge Boundaries:
- No visibility into downstream consumers of Checkout Service
- No visibility into downstream consumers of API Gateway
```

---

## 10. Ontology Foundry (Phase 3) — Full Specification

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

**Key design decision:** Ontology constrains Context, not vice versa. Schema should be a stable foundation, not reactive to noise.

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

### Ontology Database Schema

```sql
-- Type definitions
CREATE TABLE ontology_types (
    id UUID PRIMARY KEY,
    layer INT NOT NULL CHECK (layer BETWEEN 0 AND 3),
    name TEXT NOT NULL,
    parent_type_id UUID REFERENCES ontology_types(id),
    domain TEXT,
    json_schema JSONB,  -- Pydantic-compatible schema for properties
    lifecycle_state TEXT DEFAULT 'PROPOSED',
    tenant_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Relationship definitions  
CREATE TABLE ontology_relations (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    source_type_id UUID REFERENCES ontology_types(id),
    target_type_id UUID REFERENCES ontology_types(id),
    cardinality TEXT,  -- 1:1, 1:N, N:M
    semantics TEXT,  -- Human-readable meaning
    extraction_hints TEXT[],  -- Guide LLM extraction
    constraints JSONB,
    tenant_id UUID
);
```

### Ontology Lifecycle States

```
PROPOSED → VALIDATING → CONTESTED → APPROVED → ACTIVE → DEPRECATED
```

| State | Meaning | Transition Criteria |
|-------|---------|---------------------|
| PROPOSED | LLM-generated draft | Initial creation |
| VALIDATING | Under rule evaluation | Passes syntax check |
| CONTESTED | Conflicts with existing types | Collision detected |
| APPROVED | Human/agent approved | Passes all rules + review |
| ACTIVE | In production use | Loaded into Context Foundry |
| DEPRECATED | Marked for removal | Superseded or unused |

### Ontology Foundry Agents

| Agent | Responsibility |
|-------|----------------|
| TypeValidator | Check JSON schema validity, property completeness |
| CollisionDetector | Detect name collisions across domains |
| HierarchyEnforcer | Ensure depth ≥ 3, no Layer 1 direct inheritance |
| NamespaceGuard | Ensure UUID allocation follows conventions |
| SchemaPromoter | Promote APPROVED → ACTIVE when human approves |
| DeprecationAgent | Identify unused types for deprecation |
| OrphanDetector | Surface patterns that don't fit existing types → feed back to ontology |

### IT Operations Domain Template (First Implemented)

**Entity Types:**
- SERVICE, DATABASE, SERVER, LOAD_BALANCER, API_GATEWAY
- INCIDENT, CHANGE_REQUEST, RUNBOOK, MAINTENANCE_WINDOW
- TEAM, PERSON (inherited from Layer 1)

**Relationship Types:**
- DEPENDS_ON, USES, MANAGES, OWNS
- TRIGGERED_BY, RESOLVED_BY, ESCALATED_TO
- HOSTED_ON, ROUTES_TO, BACKED_BY

### Constrained Extraction Pipeline (Phase 3)

```
Document Chunk
    ↓
Ontology Plug-in (loads valid types for domain)
    ↓
Dynamic Prompt Generation (from ontology, not static YAML)
    ↓
LLM Extraction (with Instructor for structured output)
    ↓
Pydantic Validation (constrained to valid types)
    ↓
Evidence Validator
    ↓
STAGING (with ontology type tags) or REJECTED (logged)
    ↓
Gardener Promotion (type-weighted thresholds)
```

### Ontology Foundry Implementation Spec Grade

The full specification was reviewed by Perplexity and scored **A- (9/10 — Ready for Execution)**. Key strengths:
- 4-Layer Ontology with Immutable Foundation
- Production-Grade SQL with Constraints
- Complete implementation sequence
- All components concrete, sequenced, and testable

---

## 11. The 6-Phase Roadmap

```
Phase 1          Phase 2          Phase 3          Phase 4          Phase 5          Phase 6
  MVP             MVP+           Ontology         Streaming       Multi-Tenant     Autonomous
   ✅               ✅            Foundry
COMPLETE        COMPLETE          NEXT
   │               │               │                │                │                │
   ▼               ▼               ▼                ▼                ▼                ▼
Validate       Extraction      Define what      Near-real-      Production       CF acts,
tri-memory     + scale +       should exist     time updates    for large        not just
architecture   evaluation                                       orgs             answers
                                                                                    │
                                                                                    ▼
                                                                            "The System
                                                                             Comes Alive"
```

### Phase 1: MVP ✅ COMPLETE

**Objective:** Validate the tri-memory architecture works.

**What we proved:**
- Semantic + Episodic + Symbolic memory can work together
- The cognitive loop concept is viable
- Multi-hop reasoning outperforms standard RAG

**Success criteria met:**
- Tri-memory architecture: ✅ Working
- Graph lifecycle (STAGING → TRUSTED → ARCHIVED): ✅ Operational
- Uncertainty surfacing: ✅ Data Gates return "insufficient data"
- Zero rule violations: ✅ Rules checked before answers
- Multi-hop reasoning: ✅ Working
- Provenance tracking: ✅ Implemented
- Beat GraphRAG: ✅ Won 12-3 in A/B evaluation

### Phase 2: MVP+ ✅ COMPLETE

**Objective:** Add extraction, scale, and rigorous evaluation.

**What we built:**

| Component | What It Does |
|-----------|-------------|
| Defense-in-Depth Extraction | LLM + Post-Processor + Gap Detector |
| Entity Lifecycle | Staging → Trusted → Archived with confidence scoring |
| Query Pipeline | Intent detection → Role resolution → Query chaining |
| Direction-Aware Relationships | "Who reports to X" vs "Who does X report to" |
| Multi-Tenant Vaults | Complete isolation between organizations |
| E2E Test Suite | 5 vaults, 49 queries, proven stability across 3 runs |
| Data Gates | Pre-LLM evidence sufficiency check (0% hallucination) |
| A/B Evaluation Framework | Automated comparison vs GraphRAG baseline |

**Key results:**
- CF beat GraphRAG 12-3 in blind A/B evaluation
- 18x better provenance scoring (2.32/3 vs 0.13/3)
- 33x better rule citations (100% vs 3%)
- 0% hallucination rate with Data Gates
- 89% query consistency across stability runs

### Phase 3: Ontology Foundry ← CURRENT

**Objective:** Define what *should* exist, not just what *does* exist.

**What's being built:**
- Four-Layer Ontology Model (Layer 0-3)
- Schema validation and gap detection
- Constraint enforcement ("Only one CEO per org")
- Schema-guided extraction
- Ontology lifecycle governance (PROPOSED → ACTIVE → DEPRECATED)
- IT Operations as first domain template

**Success criteria:**
- Schema language defined and implemented
- Validation engine running against extracted graphs
- Gap detection surfacing missing entities/relationships
- Constraint enforcement rejecting invalid extractions
- Schema-guided extraction improving accuracy

**Full specification:** See Section 10 above.

### Phase 4: Streaming (Future)

**Objective:** Near-real-time cognitive updates.

**What we'll build:**
- Streaming Perception — continuous document ingestion
- Temporal Knowledge — time-versioned facts
- Cross-Domain Reasoning — connecting patterns across domains
- Continuous sensing agents

**The shift:** From batch processing to always-on cognition.

### Phase 5: Multi-Tenant (Future)

**Objective:** Production-ready for large organizations.

**What we'll build:**
- Federated instances across organizations
- Hardened access control (Row-Level Security)
- Production infrastructure (monitoring, alerting, SLAs)
- Maintenance agents at scale

### Phase 6: Autonomous (Future)

**Objective:** CF acts, not just answers.

**What we'll build:**
- Action Framework — safe, bounded, audited actions
- Workflow Integration — approval systems, ticketing, orchestration
- Autonomous Reasoning — decisions within defined guardrails
- Human-in-the-Loop — escalate when confidence is low
- Learning from Actions — improve based on outcomes

**The shift:**
```
Phase 5: "Ask me anything about the organization"
Phase 6: "I'll handle that for you"
```

**"The System Comes Alive."**

### The Full Picture

| Phase | Focus | Memory Systems | Agents Active |
|-------|-------|----------------|---------------|
| 1 MVP | Architecture | Semantic (basic) | Core reasoning |
| 2 MVP+ | Extraction & Query | Semantic (full) | Sensing, Semantic, Cognitive |
| **3 Ontology** | **Schema & Validation** | **Semantic + Symbolic** | **+ Validation agents** |
| 4 Streaming | Real-time | + Episodic (full) | + Continuous sensing |
| 5 Multi-Tenant | Scale & Security | All three (hardened) | + Maintenance at scale |
| 6 Autonomous | Action | All three (acting) | Full ecosystem |

---

## 12. Evaluation Results & Evidence

### A/B Evaluation: CF vs GraphRAG (100 queries)

| Metric | Context Foundry | GraphRAG | Winner |
|--------|----------------|----------|--------|
| Overall Winner | 12 | 3 | **CF** |
| Provenance Score | 2.32/3 | 0.13/3 | **CF (18x better)** |
| Relationship Citations | 32% | 10% | **CF (3x better)** |
| Rule Citations | 100% | 3% | **CF (33x better)** |
| Response Detail | 5,602 chars | 322 chars | **CF (17x more)** |
| Avg Latency | 2,677ms | 2,266ms | GraphRAG (not significant, d=0.17) |
| Hallucination Rate (with Data Gates) | 0% | N/A | **CF** |

### Key Example

**Query:** "What's the blast radius if Payment Database goes down?"

| | Context Foundry | GraphRAG |
|--|----------------|----------|
| **Structure** | Confirmed → Inferred → Boundaries | Flat list |
| **Reasoning** | Shows inference chains with confidence % | None |
| **Uncertainty** | Explicit knowledge boundaries | None |
| **Failure mode** | Correctly refused to connect unrelated entities | Conflated "Core API" with "API Gateway" based on word similarity |

### What the A/B Test Proves

- **Validation 3:** Entity/relationship structure beats flat retrieval ✅
- **CF's core value proposition:** Refuses to hallucinate, admits what it doesn't know ✅
- GraphRAG returned confident-sounding wrong answers. CF returned honest answers with explicit uncertainty.

### What It Doesn't Prove

- The test didn't isolate tri-memory specifically (it compared whole systems)
- Doesn't prove which component of CF is responsible for the win
- Doesn't prove symbolic precedence matters (Validation 2)

---

## 13. Codebase Structure (What's Actually Built)

### Services (2 Flask apps)

| Service | Port | Entry Point | Purpose |
|---------|------|-------------|---------|
| Brain | 3000 | `brain/app.py` | Knowledge processing API |
| Platform | 5000 | `web_app.py` | User-facing SPA + auth |

### File Structure

```
context-foundry/
├── brain/                          # Brain service (port 3000)
│   ├── app.py                     # Flask app entry
│   ├── classifier.py              # Domain classification
│   └── routes/                    # API routes
│
├── platform_foundation/            # Platform service components
│   ├── src/
│   │   ├── auth_service.py        # Magic link, API key, JWT, Google OAuth
│   │   ├── tenant_service.py      # Multi-tenancy isolation
│   │   ├── document_service.py    # Upload, versioning, status tracking
│   │   ├── metering_service.py    # Usage tracking per tenant
│   │   ├── mcp_server.py         # Model Context Protocol for external AI
│   │   ├── s3_connector.py       # AWS S3 bulk ingestion
│   │   └── gdrive_connector.py   # Google Drive connector
│   └── migrations/
│
├── src/context_foundry/            # Core library
│   ├── agents/                    # All 11 agents (see Section 5)
│   │   ├── graph_builder.py
│   │   ├── graph_loader.py
│   │   ├── staging_validator.py
│   │   ├── retrieval.py           # Query routing + Data Gates
│   │   ├── reasoning.py           # LLM reasoning
│   │   ├── validation.py
│   │   ├── gardener.py            # 5-pass lifecycle
│   │   ├── identity_resolver.py
│   │   ├── entity_resolver.py     # 3-stage resolution
│   │   ├── query_classifier.py
│   │   ├── scheduler.py
│   │   └── org_chart_loader.py
│   │
│   ├── memory/                    # Tri-memory implementation
│   │   ├── semantic.py            # Entities with embeddings (pgvector)
│   │   ├── episodic.py            # Document chunks with embeddings
│   │   ├── symbolic.py            # Rules, relationships, constraints
│   │   └── inference.py           # Path-based reasoning over relationships
│   │
│   ├── extraction/                # Extraction pipeline
│   │   ├── extraction_pipeline.py # Main orchestrator
│   │   ├── entity_extractor.py    # LLM entity extraction
│   │   ├── relation_extractor.py  # LLM relationship extraction
│   │   ├── duplicate_detector.py  # Prevents duplicate entities
│   │   ├── staging_loader.py      # Writes to STAGING state
│   │   └── validation.py          # Pre-load validation
│   │
│   ├── ingestion/                 # Document ingestion
│   │   ├── ingestion_pipeline.py  # Document → chunks → extraction
│   │   ├── document_loader.py     # PDF/DOCX/TXT parsing + OCR
│   │   └── chunker.py            # 512-token overlapping chunks
│   │
│   ├── ontology_foundry/          # Schema governance (Phase 3)
│   │   ├── type_lifecycle.py
│   │   ├── collision_detector.py
│   │   ├── hierarchy_enforcer.py
│   │   └── schema_promoter.py
│   │
│   ├── models/                    # Pydantic models, SQLAlchemy
│   │   ├── schema.py             # Database schema + session management
│   │   └── context_bundle.py     # ContextBundle data class
│   │
│   ├── config/                    # Domain schema, feature flags
│   │   └── domain_schema.yaml
│   │
│   ├── migrations/                # Core DB migrations
│   └── workers/                   # Background workers
│       └── extraction_worker.py   # Process document queue
│
├── web_app.py                      # Platform service entry (port 5000)
├── start.sh                        # Starts both services
└── config/
    └── domain_schema.yaml
```

### Background Jobs

| Job | Schedule | Purpose |
|-----|----------|---------|
| Gardener Cycle | Every 5 min | Lifecycle governance (5-pass) |
| Fast Validation | Every 5 min | Quick STAGING→TRUSTED for high-confidence facts |
| Extraction Worker | Every 30 sec | Process document queue |
| Identity Resolution | Every 5 min | Merge duplicate entities |

---

## 14. Technology Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Web Framework | **Flask** | Two services: Platform (5000), Brain (3000) |
| Database | **PostgreSQL** | Single DB with pgvector extension |
| Vector Store | **pgvector** | All embeddings (NOT ChromaDB, NOT Neo4j) |
| Embeddings | **OpenAI text-embedding-3-small** | 1536-dimensional |
| LLM | **OpenAI gpt-4o-mini** | Primary reasoning |
| Vision LLM | **Anthropic Claude Sonnet** | Complex PDF processing |
| Background Jobs | **Python threading + PostgreSQL message bus** | NOT Celery/Redis |
| Authentication | **Magic Link, API Keys, JWT, Google OAuth** | |
| Fuzzy Matching | **rapidfuzz** | Entity resolution stage 3 |
| Deployment | **Gunicorn** | |
| Development | **Replit** | Primary development environment |

### What's NOT Used

| Technology | Status | Alternative |
|------------|--------|-------------|
| FastAPI | ❌ | Flask |
| Celery + Redis | ❌ | PostgreSQL message bus + threads |
| Neo4j | ❌ | PostgreSQL (relationships table) |
| ChromaDB | ❌ | pgvector |

**Key design decision:** PostgreSQL-only storage. Unified storage with pgvector eliminates sync issues between separate vector stores. One database for everything.

---

## 15. Key Design Decisions & Lessons Learned

### Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| PostgreSQL-only | Unified storage, no sync issues | Neo4j + ChromaDB + Postgres (rejected: too complex) |
| Two-level governance | Schema changes need different cadence than instance changes | Single system with configurable governance (rejected: allows schema drift) |
| One-way constraint (Ontology → Context) | Schema should be stable foundation | Bidirectional coupling (rejected: noise causes schema drift) |
| Entity lifecycle (STAGING→TRUSTED) | Prevents garbage from entering canonical graph | Direct insertion (rejected: "cat" got into graph) |
| Data Gates (pre-LLM check) | Prevent hallucination at architecture level | Post-hoc filtering (rejected: LLM already fabricated answer) |
| Type-weighted promotion | Different entities need different confidence levels | Uniform threshold (rejected: person identity matters more than service name) |

### Lessons Learned

1. **Governance must be enforced, not optional.** Application-level validation isn't enough. "cat" got into the graph because nothing stopped it. Database triggers provide the last line of defense.

2. **Don't give the LLM the opportunity to hallucinate.** Gate queries BEFORE LLM invocation. If evidence is insufficient, return immediately.

3. **Solve problems generally, not specifically.** Every fix should apply to ALL query types, not just the one that's currently broken. (e.g., entity existence validation applies to impact, ownership, dependency, expertise, and escalation queries.)

4. **Latency is not the differentiator.** CF is slightly slower than GraphRAG but dramatically better at provenance, rule citations, and honesty. Speed can be optimized; trust cannot be retrofitted.

5. **The learning loop is the gap.** The system ingests and answers, but doesn't yet systematically learn from feedback. This is the biggest missing piece.

6. **Schema drift is the enemy.** Without ontology governance, aggressive LLM extraction creates type pollution. Phase 3 (Ontology Foundry) exists to solve this.

---

## 16. Validations — What's Proven vs. Hypothesized

| # | Validation | Status | Evidence |
|---|------------|--------|----------|
| 1 | Tri-memory outperforms single-memory | **NOT PROVEN** | A/B test compared whole systems, not isolated components |
| 2 | Symbolic precedence matters | **NOT PROVEN** | No test where rules override retrieved facts |
| 3 | Entity/relationship beats flat retrieval | **PARTIAL (12-3 win)** | A/B evaluation showed CF beats GraphRAG |
| 4 | Shared context across apps | **NOT PROVEN** | No multi-app test yet |
| 5 | Domain-independent | **PARTIAL** | IT Ops works; other domains not yet tested |

### What's Proven

- CF's overall architecture works better than GraphRAG (12-3 A/B win)
- Data Gates eliminate hallucination (0% rate)
- Entity lifecycle governance prevents garbage data
- Provenance tracking provides auditability (18x better than baseline)

### What's Not Proven

- Whether tri-memory specifically is responsible for the win
- Whether symbolic precedence changes answers in practice
- Whether the architecture works across domains (only IT Ops tested)
- Whether shared context across applications works

### Honest Assessment

> A hypothesis isn't a weakness. Every important idea starts as a hypothesis. The weakness would be claiming it's proven when it's not.

---

## 17. SavePoint & Current State

### System Metrics (as of last checkpoint)

| Metric | Value |
|--------|-------|
| Ontology types | 226 ACTIVE |
| Entities | 447 valid |
| Relationships | 679 |
| Documents indexed | 7,670 |
| Invalid entities | 0 |
| Orphan patterns | 10 pending review |
| Agents implemented | 11 of ~14 planned |

### Components Operational

- ✅ Command Center (live dashboard, auto-refresh 30s)
- ✅ A/B Evaluation framework
- ✅ Memory Graph visualization
- ✅ Learning Loop tracking (partial)
- ✅ Message Bus (16 event types, 0 dead letters)
- ✅ Database enforcement trigger
- ✅ Multi-tenant vault system
- ✅ MCP Server for external AI integration

### Key SavePoint Notes

- **A/B eval COMPLETE** (CF won 12-3 vs GraphRAG). DO NOT re-run.
- IT Ops test data preserved (80 SERVICE entities)
- Core system validated
- Two schemas coexist: IT Ops (eval) + Core Foundation (real docs)
- Chunking fix applied: 12→55 entities
- Relationship wiring bug fixed

### What Comes Next

1. Complete Ontology Foundry implementation (Phase 3)
2. Build the learning loop (biggest gap)
3. Test with real enterprise documents
4. Validate across domains beyond IT Ops
5. Build Context Bundle API for external consumption

---

## Appendix A: Key Chat References

| Topic | Chat Link |
|-------|-----------|
| Full 6-phase roadmap with all details | https://claude.ai/chat/e9cc8ff2-adfb-4286-a377-9f01f95c311b |
| Ontology Foundry spec + Replit handoff | https://claude.ai/chat/8788831a-1aed-4a9d-a5c0-d03d06cd83af |
| Implementation spec (A- grade from Perplexity) | https://claude.ai/chat/4dd91e31-a5cd-467e-8e0c-fc61e4043bb0 |
| Jan 17 roadmap revisit + validation framework | https://claude.ai/chat/217f70d9-4a10-41e1-b081-82faffe5a040 |
| Architecture review + tri-memory deep dive | https://claude.ai/chat/dc84726f-00a5-4734-980c-b8f142ce863b |
| CF Bible creation + honest assessment | https://claude.ai/chat/e9cc8ff2-adfb-4286-a377-9f01f95c311b |
| Vision vs Reality audit (Dec 2025) | https://claude.ai/chat/8788831a-1aed-4a9d-a5c0-d03d06cd83af |
| Hybrid MVP synthesis | https://claude.ai/chat/b45bc9be-aa57-4c42-8195-2895f3d61f21 |
| Core innovation refocus | https://claude.ai/chat/e8c619d1-21b5-46dd-bc98-5b716ea8eed1 |

---

## Appendix B: Instructions for AI Coding Agents

When working on Context Foundry:

1. **Read this document first.** It contains the accumulated design decisions and rationale.
2. **Never bypass Data Gates.** If entity doesn't exist → return NOT_FOUND. Never fabricate.
3. **Respect the lifecycle.** All new facts start in STAGING. Only the Gardener promotes.
4. **Solve generally, not specifically.** Every fix should work for ALL query types.
5. **Ontology constrains Context.** Schema changes go through Ontology Foundry governance.
6. **PostgreSQL is the only database.** No Neo4j, no ChromaDB, no Redis.
7. **Check SavePoints before making changes.** Read CF_SavePoint files to understand current state.
8. **The core job is: Tell the truth. Don't hallucinate.** Everything else is in service of this.

---

*"Intelligence requires a world model. Context Foundry is that world model."*
