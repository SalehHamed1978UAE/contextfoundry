# Context Foundry: Foundational Reference

**Version:** 1.0  
**Date:** January 9, 2026  
**Status:** Active Development  
**Current Stage:** Stage 2 (Context-Attached Knowledge)

---

## 1. What Is Context Foundry?

Context Foundry is a **Cognitive Operating System for the Enterprise** — a foundational layer that gives AI systems a coherent, evolving understanding of organizational reality.

### 1.1 The Problem

Today's enterprise AI fails because nothing accumulates:

| Approach | What It Does | Why It Fails |
|----------|--------------|--------------|
| **RAG** | Retrieves text chunks | No memory. No understanding. Rebuilds context every query. |
| **Agents** | Executes tasks | No persistent state. Forgets everything between tasks. |
| **Fine-tuning** | Bakes knowledge in | Static. Can't handle dynamic enterprise reality. |
| **Triple KGs** | Stores entity relationships | Loses context. Can't answer "when" or "which instance." |

Every AI pilot rebuilds from scratch. Every solution is siloed. Nothing compounds.

### 1.2 The Vision

> "Intelligence requires a world model. Context Foundry is that world model."

An organization uploads its documents. Context Foundry:
1. **Extracts** structured knowledge with context
2. **Maintains** a coherent, evolving World Model
3. **Serves** all AI applications from one source of truth
4. **Learns** from every interaction

The result: AI that understands the organization — not just retrieves text about it.

### 1.3 Core Principles

| Principle | Meaning |
|-----------|---------|
| **Compounding** | Every interaction makes the system smarter |
| **Grounded** | Every answer traces to sources — no hallucination |
| **Trustworthy** | Explicit confidence. Admits uncertainty. |
| **Domain-agnostic** | Same architecture works for any knowledge domain |
| **One substrate** | Single World Model serves all AI applications |

---

## 2. Architecture Overview

### 2.1 Tri-Memory System

Context Foundry models cognition with three memory types:

```
┌─────────────────────────────────────────────────────────────┐
│                       WORLD MODEL                           │
├───────────────────┬───────────────────┬────────────────────┤
│  SEMANTIC MEMORY  │  EPISODIC MEMORY  │  SYMBOLIC MEMORY   │
│  "The Subway Map" │ "The Recent Stories"│ "The Traffic Laws" │
├───────────────────┼───────────────────┼────────────────────┤
│ Knowledge graph   │ Event timelines   │ Rules and          │
│ of entities,      │ Incident patterns │ constraints        │
│ relationships,    │ Anomaly detection │ Safety invariants  │
│ and topology      │                   │                    │
├───────────────────┼───────────────────┼────────────────────┤
│ Long-term         │ Pattern           │ Governs reasoning  │
│ structure         │ recognition       │ Prevents unsafe    │
│                   │                   │ conclusions        │
└───────────────────┴───────────────────┴────────────────────┘
```

### 2.2 The Fact Lifecycle

Facts flow through stages to ensure quality:

```
STAGING ──────────▶ TRUSTED ──────────▶ ARCHIVED
   │                   │                   │
New facts            Validated           Superseded
extracted.           facts.              or stale.
Purgatory.           "Truth" for         Historical
                     reasoning.          record.
```

Each fact carries: `_layer`, `_confidence`, `_sources`, `_lifecycle`

### 2.3 The Context Bundle

Output to AI applications — structured truth, not raw text:

```
Context Bundle
├── Focal entities (with attributes, descriptions)
├── Relationships (with temporal, provenance, confidence)
├── Dependency paths
├── Applicable rules
└── Confidence summary
```

**Principle:** "LLMs don't hallucinate when given structured truth."

### 2.4 Context-Attached Knowledge (from Context Graph research)

Relationships carry context, not just triples:

```
BARE TRIPLE (old):
  (Steve Jobs, chairman_of, Apple)

CONTEXT-ATTACHED (new):
  (Steve Jobs, chairman_of, Apple)
  + valid_from: "August 2011"
  + valid_to: "October 2011"
  + event_context: "Post-resignation appointment"
  + provenance: "Press release, Aug 24, 2011"
  + confidence: 0.95
```

This enables questions like:
- "When was Jobs chairman?" → "August-October 2011"
- "Was this his first time as chairman?" → "No, second tenure"
- "Source?" → "Press release, Aug 24, 2011"

---

## 3. Development Roadmap

### Stage 1: Structured Beats Unstructured ✓ COMPLETE

**Hypothesis:** Extracting knowledge into a graph and reasoning over it produces better answers than RAG over raw documents.

**Test:** Same questions, same documents — CF vs GraphRAG

**Outcome:** CF won 12-3 in blind A/B evaluation
- 18x better provenance scores
- 33x better rule citations  
- Faster on hard multi-hop queries

**What we proved:** The tri-memory architecture works. Structured knowledge with provenance beats chunk retrieval.

---

### Stage 2: Context-Attached Beats Bare Triples ← CURRENT

**Hypothesis:** Relationships with context (temporal, provenance, confidence, event) answer questions that bare triples cannot.

**Test:** Questions requiring contextual reasoning:
- "When did X happen?"
- "Which instance of X?"
- "How confident are you?"
- "What's the source?"
- Questions where the same triple appears in different contexts

**Success Criteria:**
1. Relationships carry context fields (temporal, provenance, confidence, event)
2. Extraction populates context at ingestion time
3. Query retrieves relationships WITH context
4. System answers contextual questions correctly
5. System distinguishes same-triple-different-context scenarios

**Testable Goal:**
```
Given 5 documents with temporal/contextual complexity:
- 20 questions requiring contextual reasoning
- 16/20 correct answers (80%)
- System uses context fields, not document fallback
- System reports appropriate confidence
```

**What This Proves:** Context attached to structure enables reasoning that bare triples cannot support.

---

### Stage 3: The System Learns from Interaction

**Hypothesis:** Queries that reveal gaps improve the World Model. The same question asked later gets a better answer.

**Test:**
1. Ask a question the system answers incompletely
2. System detects the gap
3. System learns (extracts missing knowledge)
4. Ask the same question again
5. Answer is now more complete

**Success Criteria:**
1. Gap detection works (system knows when knowledge may be incomplete)
2. Query-triggered learning extracts new facts
3. New facts flow through staging → trusted
4. Repeated query shows improvement
5. Learning doesn't introduce noise

**Testable Goal:**
```
Given documents with knowledge the initial extraction missed:
- 10 questions that expose gaps
- System detects gap in 8/10 cases
- System learns and improves answer in 6/10 cases
- No false learning (noise introduced) in >1 case
```

**What This Proves:** The cognitive loop works. Understanding compounds over time.

---

### Stage 4: One Substrate, Many Applications

**Hypothesis:** A single CF instance can power multiple AI applications without rebuilding context.

**Test:** 
- Deploy Chat Interface, Meeting Assistant, Board Advisor
- All query the same World Model
- Each gets accurate, grounded answers
- Knowledge learned in one application benefits others

**Success Criteria:**
1. Three applications share one CF instance
2. Each application retrieves appropriate Context Bundles
3. Knowledge added via one application is available to others
4. No per-application context rebuilding

**Testable Goal:**
```
Given one CF instance with organizational knowledge:
- Chat asks about Project Phoenix → correct answer
- Meeting Assistant verifies claim about Phoenix → uses same knowledge
- Board Advisor analyzes Phoenix risks → uses same knowledge
- New fact added via Chat → available to other apps within 5 minutes
```

**What This Proves:** CF is a platform, not a point solution. "Create once, use everywhere."

---

### Stage 5: Domain-Agnostic

**Hypothesis:** Load a new domain's documents, answer questions with zero code changes.

**Test:**
- Load completely different domain (legal contracts, medical records, manufacturing specs)
- No schema changes, no code changes
- System extracts knowledge and answers questions

**Success Criteria:**
1. New domain loaded via standard ingestion
2. Ontology emerges from data (open extraction)
3. Queries work without domain-specific code
4. Accuracy comparable to domain-specific systems

**Testable Goal:**
```
Given 3 different domains (org chart, legal contracts, financial reports):
- Load each domain (documents only, no schema)
- 10 questions per domain
- 7/10 correct per domain (70%)
- Zero domain-specific code
```

**What This Proves:** The architecture generalizes. Not just IT ops or portfolios — any enterprise domain.

**Note:** Partially validated with 15-minute org chart test (95% confidence answer with zero code changes).

---

### Stage 6: Enterprise-Ready

**Hypothesis:** CF works at scale with governance, security, multi-tenancy for real enterprise deployment.

**Test:** Production deployment with:
- Multiple tenants (isolated data)
- Thousands of documents
- Concurrent users
- Audit trails
- Role-based access

**Success Criteria:**
1. Multi-tenant isolation (RLS enforced)
2. Sub-3-second query latency at p95
3. Scales to 10,000+ documents per tenant
4. Full audit trail of reasoning
5. Governance controls (human approval for high-stakes)

**Testable Goal:**
```
Given production-like load:
- 5 tenants, 2000 documents each
- 100 concurrent queries
- p95 latency < 3 seconds
- Zero data leakage between tenants
- Full audit trail for compliance review
```

**What This Proves:** CF is production-ready for enterprise deployment.

---

## 4. Current State

### 4.1 What's Built

| Component | Status |
|-----------|--------|
| Tri-memory schema | ✓ Implemented |
| Entity extraction | ✓ Working |
| Relationship extraction | ✓ Working (open extraction) |
| Fact lifecycle (staging/trusted) | ✓ Implemented |
| Multi-tenant RLS | ✓ Implemented |
| Query-time semantic mapping | ⚠ Partial (agent exists, context not attached) |
| Context Bundle assembly | ⚠ Partial (missing relationship context) |
| Chat interface | ⚠ Partial (working but limited) |
| Learning loop | ✗ Not started |
| Meeting Assistant | ✗ Spec only |
| Board Advisor | ✗ Spec only |

### 4.2 What's Proven

- ✓ Structured beats unstructured (Stage 1)
- ✓ Architecture is domain-agnostic (Stage 5 partial)
- ⚠ Context-attached beats bare triples (Stage 2 — in progress)

### 4.3 Current Blockers

1. **Relationships lack context** — No temporal, provenance, confidence fields populated
2. **Extraction doesn't capture context** — Extracts triples, not quadruples
3. **Query retrieves triples only** — Context Bundle missing relationship context
4. **No sufficiency check** — System doesn't know when it has enough information

---

## 5. Technical Reference

### 5.1 Key Tables

```sql
entities (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  name TEXT NOT NULL,
  entity_type TEXT,
  attributes JSONB,
  description TEXT,
  aliases TEXT[],
  lifecycle_state TEXT DEFAULT 'STAGING',
  confidence FLOAT,
  source_chunk_ids UUID[],
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

relationships (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  source_entity_id UUID REFERENCES entities(id),
  target_entity_id UUID REFERENCES entities(id),
  relationship_type TEXT NOT NULL,
  attributes JSONB,
  lifecycle_state TEXT DEFAULT 'STAGING',
  confidence FLOAT,
  source_chunk_ids UUID[],
  -- CONTEXT FIELDS (Stage 2 additions):
  valid_from TIMESTAMPTZ,
  valid_to TIMESTAMPTZ,
  provenance_chunk_id UUID,
  event_context TEXT,
  qualifiers JSONB,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

document_chunks (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  document_id UUID,
  content TEXT,
  embedding VECTOR(1536),
  chunk_index INT,
  metadata JSONB,
  created_at TIMESTAMPTZ
)

rules (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  rule_type TEXT,
  condition JSONB,
  action JSONB,
  priority INT,
  enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ
)
```

### 5.2 Key Agents

| Agent | Responsibility |
|-------|----------------|
| **GraphBuilderAgent** | Extract entities + relationships from documents |
| **RetrievalAgent** | Assemble Context Bundle from tri-memory |
| **ReasoningAgent** | LLM reasoning over Context Bundle |
| **ValidationAgent** | Apply symbolic rules, adjust confidence |
| **GardenerAgent** | Maintain KG quality (dedup, promotion, pruning) |
| **QueryTimeSemanticAgent** | Parse query, resolve entities, orchestrate retrieval + reasoning |

### 5.3 Query Flow

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│ 1. PARSE                            │
│    Understand intent, entities,     │
│    relationships from natural lang  │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 2. RESOLVE                          │
│    Map to canonical entities in KG  │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 3. RETRIEVE                         │
│    Assemble Context Bundle:         │
│    - Entities + attributes          │
│    - Relationships + context        │
│    - Applicable rules               │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 4. SUFFICIENCY CHECK                │
│    Is there enough context to       │
│    answer confidently?              │
│                                     │
│    YES → Continue                   │
│    NO  → Iterate (retrieve more)    │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 5. REASON                           │
│    LLM reasons over Context Bundle  │
│    Produces answer + confidence     │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 6. VALIDATE                         │
│    Apply symbolic rules             │
│    Check constraints                │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 7. RESPOND                          │
│    Return answer with:              │
│    - Confidence score               │
│    - Provenance citations           │
│    - Uncertainty acknowledgment     │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 8. LEARN (async)                    │
│    If gaps detected:                │
│    - Log for review                 │
│    - Trigger re-extraction          │
│    - Update World Model             │
└─────────────────────────────────────┘
```

---

## 6. Working with This Document

### 6.1 For Coding LLMs (Codex, Claude Code, Replit)

**When starting work:**
1. Read this document first
2. Check "Current State" for what's built
3. Check "Current Stage" for what we're proving
4. Work toward the testable goal for that stage

**When making decisions:**
- Does this support the current stage's hypothesis?
- Does this maintain the core principles?
- Can we test if this works?

**When stuck:**
- Re-read the stage definition
- Focus on the testable goal
- Ask: "What's the minimum change to prove/disprove this hypothesis?"

### 6.2 For Architecture Review (Codex)

**Before approving changes:**
1. Does it align with current stage goals?
2. Does it maintain tri-memory architecture?
3. Does it preserve fact lifecycle integrity?
4. Is it testable?

**Red flags:**
- "Document fallback" that bypasses World Model
- Per-query hacks instead of general solutions
- Skipping stages (e.g., Stage 3 before Stage 2 complete)

### 6.3 For Strategic Review

**Key questions at each stage:**
- Stage 1: Does structured beat unstructured? → **YES (proven)**
- Stage 2: Does context-attached beat bare triples? → **Testing**
- Stage 3: Does the system learn? → **Not started**
- Stage 4: Does one substrate serve many apps? → **Not started**
- Stage 5: Is it domain-agnostic? → **Partially proven**
- Stage 6: Is it enterprise-ready? → **Not started**

---

## 7. Key Definitions

| Term | Definition |
|------|------------|
| **World Model** | CF's coherent representation of organizational reality |
| **Context Bundle** | Structured package of knowledge delivered to AI applications |
| **Fact Lifecycle** | STAGING → TRUSTED → ARCHIVED flow with validation |
| **Context-Attached** | Relationships carrying temporal, provenance, confidence, event data |
| **Sufficiency Check** | System evaluating if it has enough information to answer confidently |
| **Grounded** | Answer that traces to sources, not hallucinated |
| **Compounding** | System getting smarter from interactions over time |

---

## 8. References

- Context Foundry Vision Document (internal)
- Context Graph paper: arXiv:2406.11160 (Xu et al., 2024)
- CF vs GraphRAG A/B Evaluation (Dec 8, 2025)
- Frank's World: "Context Graphs: AI's Next Big Idea" (Jan 6, 2026)

---

## 9. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 9, 2026 | Initial foundational reference |

---

*This document is the canonical reference for Context Foundry development. All coding work, architecture decisions, and strategic reviews should align with this document.*
