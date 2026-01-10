# Context Foundry - Cognitive Operating System for the Enterprise

**Version:** 1.0 | **Date:** January 9, 2026 | **Current Stage:** Stage 2 (Context-Attached Knowledge)

---

## What Is Context Foundry?

Context Foundry is a **Cognitive Operating System for the Enterprise** — a foundational layer that gives AI systems a coherent, evolving understanding of organizational reality.

> "Intelligence requires a world model. Context Foundry is that world model."

### The Problem It Solves

| Approach | What It Does | Why It Fails |
|----------|--------------|--------------|
| **RAG** | Retrieves text chunks | No memory. No understanding. Rebuilds context every query. |
| **Agents** | Executes tasks | No persistent state. Forgets everything between tasks. |
| **Fine-tuning** | Bakes knowledge in | Static. Can't handle dynamic enterprise reality. |
| **Triple KGs** | Stores entity relationships | Loses context. Can't answer "when" or "which instance." |

### Core Principles

| Principle | Meaning |
|-----------|---------|
| **Compounding** | Every interaction makes the system smarter |
| **Grounded** | Every answer traces to sources — no hallucination |
| **Trustworthy** | Explicit confidence. Admits uncertainty. |
| **Domain-agnostic** | Same architecture works for any knowledge domain |
| **One substrate** | Single World Model serves all AI applications |

---

## Architecture Overview

### Tri-Memory System

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

### The Fact Lifecycle

```
STAGING ──────────▶ TRUSTED ──────────▶ ARCHIVED
   │                   │                   │
New facts            Validated           Superseded
extracted.           facts.              or stale.
Purgatory.           "Truth" for         Historical
                     reasoning.          record.
```

Each fact carries: `_layer`, `_confidence`, `_sources`, `_lifecycle`

### Context-Attached Knowledge

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

### The Context Bundle

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

---

## Development Roadmap

### Stage 1: Structured Beats Unstructured ✓ COMPLETE
**Proven:** CF won 12-3 in blind A/B vs GraphRAG. 18x better provenance, 33x better rule citations.

### Stage 2: Context-Attached Beats Bare Triples ✓ COMPLETE
**Hypothesis:** Relationships with context (temporal, provenance, confidence, event) answer questions that bare triples cannot.

**Success Criteria:**
1. ✓ Relationships carry context fields (valid_from, valid_to, provenance_text, event_context, qualifiers)
2. ✓ Extraction populates context at ingestion time via GraphBuilderAgent
3. ✓ Query retrieves relationships WITH context via temporal functions
4. ✓ System answers contextual questions correctly (18/20 = 90%)
5. ✓ System distinguishes same-triple-different-context scenarios

**Testable Goal:** 20 contextual questions → 90% correct using context fields (exceeds 80% target)

### Stage 3: The System Learns from Interaction
**Hypothesis:** Queries that reveal gaps improve the World Model.

### Stage 4: One Substrate, Many Applications
**Hypothesis:** Single CF instance powers Chat, Meeting Assistant, Board Advisor.

### Stage 5: Domain-Agnostic
**Hypothesis:** Load new domain, answer questions with zero code changes.
**Note:** Partially validated with 15-minute org chart test (95% confidence).

### Stage 6: Enterprise-Ready
**Hypothesis:** Works at scale with governance, security, multi-tenancy.

---

## Current State

### What's Built

| Component | Status |
|-----------|--------|
| Tri-memory schema | ✓ Implemented |
| Entity extraction | ✓ Working |
| Relationship extraction | ✓ Working (context-attached) |
| Fact lifecycle (staging/trusted) | ✓ Implemented |
| Multi-tenant RLS | ✓ Implemented |
| Query-time semantic mapping | ✓ Working (temporal queries) |
| Context Bundle assembly | ✓ Working (includes relationship context) |
| Temporal query functions | ✓ Implemented (get_relationships_at_time, get_entity_history) |
| Chat interface | ⚠ Partial (working but limited) |
| Learning loop | ✗ Not started |

### Stage 2 Implementation Details

**Context Fields Added:**
- `valid_from` / `valid_to`: Temporal validity dates
- `provenance_text`: Source sentence evidence
- `event_context`: Situational context ("Early career at ENEC", "Series A investment")
- `qualifiers`: Additional metadata list

**Temporal Query Functions:**
- `get_relationships_at_time(entity_id, at_time)`: Find relationships active at a specific date
- `get_relationship_timeline(entity_id)`: Get chronological list of relationships
- `get_entity_history(entity_id)`: Full history of entity changes

**Test Documents:**
- `test_docs/career_history.md`: Career progression with temporal positions
- `test_docs/investment_portfolio.md`: Investment portfolio with entry/exit dates

**Validation Results:**
- 18/20 contextual questions passed (90%)
- Successfully answers "What position did Saleh hold in 2005?" → Systems Engineer
- Successfully extracts event_context like "Early career at ENEC"
- Successfully calculates durations from valid_from/valid_to

### Next Steps (Stage 3)

1. **Learning from interaction** — Queries that reveal gaps improve the World Model
2. **Sufficiency check** — System detects when it has enough information
3. **Gap logging** — Record questions system couldn't answer for re-extraction

---

## Key Agents

| Agent | Responsibility |
|-------|----------------|
| **GraphBuilderAgent** | Extract entities + relationships from documents |
| **RetrievalAgent** | Assemble Context Bundle from tri-memory |
| **ReasoningAgent** | LLM reasoning over Context Bundle |
| **ValidationAgent** | Apply symbolic rules, adjust confidence |
| **GardenerAgent** | Maintain KG quality (dedup, promotion, pruning) |
| **QueryTimeSemanticAgent** | Parse query, resolve entities, orchestrate retrieval + reasoning |

---

## Query Flow

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

## Key Definitions

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

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

---

## External Dependencies
- **Database:** PostgreSQL (with pgvector for embeddings)
- **LLM:** OpenAI `gpt-4o-mini`
- **Vision LLM:** Anthropic Claude Sonnet 4
- **Vector Embeddings:** `text-embedding-3-small`
- **Web Framework:** Flask
- **Deployment:** Gunicorn
- **Authentication:** Magic Link, API Keys, JWT Sessions, Google OAuth

---

## References
- Context Foundry Vision Document (internal)
- Context Graph paper: arXiv:2406.11160 (Xu et al., 2024)
- CF vs GraphRAG A/B Evaluation (Dec 8, 2025)
- Frank's World: "Context Graphs: AI's Next Big Idea" (Jan 6, 2026)
- Full Reference: `attached_assets/CF_Foundational_Reference_v1.2_1768030556025.md`

---

*This document is the canonical reference for Context Foundry development. All coding work, architecture decisions, and strategic reviews should align with this document.*
