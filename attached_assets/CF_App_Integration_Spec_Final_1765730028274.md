# Context Foundry: App Integration Architecture
## Final Implementation Specification

**Version**: 1.0  
**Date**: December 14, 2025  
**Status**: Ready for Implementation

---

## Part 1: What is Context Foundry?

### 1.1 The Core Idea

Context Foundry (CF) is a **Partial-Knowledge Intelligence System** that provides "organizational object permanence" for AI. 

The key insight: Most AI systems hallucinate when they don't know something. Context Foundry refuses to hallucinate. It tells you what it knows, what it doesn't know, and how confident it is.

### 1.2 What CF Does

CF ingests organizational documents (strategy decks, governance frameworks, technical specs, org charts, policies) and extracts:

- **Entities**: People, organizations, systems, services, processes, concepts, locations, documents
- **Relationships**: DEPENDS_ON, MANAGES, OWNS, REPORTS_TO, AFFECTS, etc.
- **Facts**: Structured claims with provenance (which document, which page, when extracted)

These are stored in a **knowledge graph** — a structured representation of organizational truth.

### 1.3 How CF Responds to Queries

When you ask CF a question, it returns:

```
GROUNDED: Facts it knows with evidence
GAPS: Things it doesn't know (explicit uncertainty)
INFERRED: Reasonable conclusions with lower confidence
Confidence Score: 0.0 - 1.0
Provenance: Source documents for every claim
```

**Example:**

Query: "What is the blast radius if API Gateway goes down?"

Response:
- GROUNDED: GraphQL Gateway, Mobile Gateway, Partner Gateway depend on API Gateway (confidence: 0.87)
- GAPS: No documented dependents beyond these 3 services
- Evidence: infrastructure-doc.pdf, page 14

### 1.4 CF's Architecture (High Level)

CF has three core capabilities:

1. **Extraction Pipeline**: Ingests documents, extracts entities and relationships using LLM-powered constrained extraction with validation agents (Gardener, RE Agent)

2. **Knowledge Graph**: Stores entities, relationships, and provenance. Entities have confidence scores that decay over time if not revalidated.

3. **Query Engine**: Accepts queries, traverses the graph, returns grounded responses with confidence scores and explicit gaps.

### 1.5 What Makes CF Different

| Typical AI System | Context Foundry |
|-------------------|-----------------|
| Makes up answers when uncertain | Says "I don't know" explicitly |
| No provenance | Every fact traced to source document |
| Confidence is vibes | Confidence is calculated and decays |
| Generic knowledge | Your organization's specific knowledge |
| Stateless | Remembers and learns |

---

## Part 2: The App Ecosystem

### 2.1 CF is Infrastructure, Not a Product

CF is not a user-facing application. It's the **knowledge layer** that other AI applications consume.

Think of it like a database: Users don't interact with PostgreSQL directly. They use applications that query PostgreSQL.

Similarly: Users don't interact with CF directly. They use applications that query CF for organizational context.

### 2.2 Applications That Use CF

| Application | Purpose | How It Uses CF |
|-------------|---------|----------------|
| **Premisia** | Strategic consulting (Five Whys, Porter's, SWOT, scenario planning) | Grounds analysis in real org data — "What do we actually know about this system/team/process?" |
| **Meeting Assistant** | Real-time fact verification during meetings | Verifies claims against organizational knowledge — "Is that actually true?" |
| **Board Advisor** | Board pack analysis and preparation | Understands org context when analyzing documents — "What's the history here?" |
| **Future Apps** | Unknown | Any AI app that needs organizational context |

### 2.3 The Integration Pattern (Current State)

Today, apps integrate with CF via REST API:

```
App → POST /api/v1/query → CF → Response
```

Apps must send structured queries with entity names. CF searches the graph and returns results.

**The problem**: Apps don't always know the exact entity names. They have raw user input that needs to be interpreted.

---

## Part 3: The Problem We're Solving

### 3.1 The Failure Case

A user is in Premisia doing a Five Whys analysis. They type:

> "Reduce API Gateway downtime by 50%"

Premisia needs to ask CF: "What do you know about API Gateway?"

**What happened:**

1. Premisia extracted the "entity" from user input
2. Premisia's extraction was naive — it grabbed "Reduce API Gateway"
3. Premisia sent to CF: `focal_entity: "Reduce API Gateway"`
4. CF searched for "Reduce API Gateway" literally
5. CF found nothing
6. Premisia proceeded without organizational context

**The reality:**

- "API Gateway" exists in CF's graph
- It has 3 dependent services: GraphQL Gateway, Mobile Gateway, Partner Gateway
- CF has the data. The query was just malformed.

### 3.2 Root Cause

Premisia is doing entity extraction. Premisia is bad at entity extraction.

CF already has sophisticated entity extraction (Gardener agent, constrained extraction pipeline, EntityResolver for fuzzy matching). We built this. It works. It won 12-3 against GraphRAG in A/B testing.

**Why are we rebuilding entity extraction in every app?**

### 3.3 The Deeper Problem

If we "fix" Premisia's entity extraction, we'll have the same problem in Meeting Assistant, Board Advisor, and every future app.

Each app will:
- Build its own extraction logic
- Have its own bugs
- Be inconsistent with other apps
- Not benefit from CF's sophisticated extraction

This is architectural debt.

---

## Part 4: The Solution Architecture

### 4.1 Design Principle

**Apps should be dumb. CF should be smart.**

Apps send raw text. CF extracts entities, queries the graph, returns grounded results.

```
Before (broken):
  App extracts entities (badly) → Sends to CF → CF searches literally → Fails

After (correct):
  App sends raw text → CF extracts entities → CF queries graph → Returns results
```

### 4.2 Two Query Paths (Critical Design Decision)

Different apps have different latency requirements:

| App | Use Case | Latency Requirement |
|-----|----------|---------------------|
| Premisia | Deep strategic analysis | 5-15 seconds acceptable |
| Board Advisor | Document analysis | 5-15 seconds acceptable |
| Meeting Assistant | Real-time verification | Must be <500ms |

**Solution: Two API endpoints with different latency budgets.**

- `/api/v1/query` — Deep path. Can use LLM. Rich reasoning.
- `/api/v1/verify` — Fast path. No LLM. Bounded traversal. <500ms.

### 4.3 Two-Tier Entity Resolution

To prevent the extraction pipeline from becoming a bottleneck:

**Tier 1: Fast Resolver (default for /verify, first pass for /query)**
- Alias dictionary lookup (confirmed + trusted only)
- Lexical matching (normalized forms)
- Embedding similarity against entity names/aliases
- Deterministic scoring + thresholds
- No LLM calls

**Tier 2: Assisted Resolver (only if Tier 1 is ambiguous, only in /query)**
- LLM-based disambiguation
- Still outputs candidates + evidence
- Never used in /verify

**Hard rule: /verify uses Tier 1 only.**

---

## Part 5: Per-App Context (Phase 2)

### 5.1 The Opportunity

If CF handles extraction for all apps, CF sees how each app queries. This is valuable signal.

Over time, CF can learn:
- "When Premisia says 'API GW', it means 'API Gateway'"
- "Meeting Assistant asks about financial entities more than technical ones"
- "This tenant uses 'Auth Service' but the graph has 'Authentication Service'"

### 5.2 What Per-App Context Is (And Isn't)

**It is NOT a separate knowledge graph per app.**

**It IS structured metadata** that improves extraction and matching:

```python
app_context = {
    "app_id": "premisia",
    "tenant_id": "adq",
    
    # Learned aliases
    "aliases": {
        "API GW": "API Gateway",
        "Auth": "Authentication Service",
        "PG": "Payment Gateway"
    },
    
    # Query patterns
    "frequently_queried_entities": ["API Gateway", "Payment Service", "Auth Service"],
    "common_query_types": ["root_cause", "dependency_analysis"],
    
    # Domain hints
    "primary_domain": "technical_infrastructure",
    
    # Disambiguation preferences
    "when_ambiguous": {
        "Gateway": "prefer SERVICE over LOCATION"
    }
}
```

### 5.3 Memory is NOT Truth

Critical distinction:
- **Graph** = organizational facts (from documents, validated)
- **Memory** = behavioral signals (from usage, statistical)

Memory signals are **biasing hints**, not ground truth. They must not silently override clear textual matches.

### 5.4 Alias Governance (Critical for Trust)

Aliases can be poisoned by confused or malicious users. Lifecycle states prevent this:

| State | Meaning | Auto-Applied? |
|-------|---------|---------------|
| PROPOSED | Inferred from usage/co-occurrence | No — shown as suggestions only |
| CONFIRMED | Explicitly confirmed by user | Yes |
| TRUSTED | Confirmed + stable + no conflicts | Yes |

**Rule: Only CONFIRMED/TRUSTED aliases are applied automatically. PROPOSED aliases are suggestions only.**

### 5.5 Stateless Queries, Stateful Learning

Each individual query is stateless — CF doesn't need prior queries to answer the current one.

But CF accumulates app context over time, making future queries more accurate.

**Write model:**
- Synchronous: Append-only event log (cheap insert), explicit user corrections
- Asynchronous: Aggregate counts, compute usage stats, propose aliases

---

## Part 6: Implementation Plan (Implementation-Ready)

### Guiding Principles

1. **Two query paths, two latency budgets**
   - Deep path for Premisia/Board Advisor: richer reasoning, slower
   - Fast path for Meeting Assistant: strict bounds, no LLM in the loop

2. **Tenant identity comes from auth context**
   - The request body must not be trusted for tenant_id
   - Derive tenant from token claims (or mTLS identity)

3. **Memory writes are event-based**
   - Apps send events and explicit corrections
   - CF computes aggregates asynchronously

4. **Auditability**
   - Every alias resolution and correction must be explainable: who/when/why, confidence, evidence

---

### Phase 1 (MVP): "Apps send raw text; CF resolves entities; CF answers"

**Goal**: Fix integration correctness and remove app-side entity extraction.

#### 6.1 Endpoints (Phase 1)

**A) Deep Query Endpoint (Premisia, Board Advisor)**

```
POST /api/v1/query
```

**Purpose**: Grounded answers using CF's best reasoning pipeline (can be slow).

**Latency SLO**: P95 5–15s (tunable), P99 < 30s

**Allowed operations**: LLM-assisted extraction/reranking, deeper traversal, multi-hop reasoning.

**Request:**
```json
{
  "query": "Reduce API Gateway downtime by 50%",
  "analysis_type": "root_cause",
  "context": {
    "app_id": "premisia",
    "user_id": "u-123",
    "session_id": "s-456",
    "trace_id": "t-789"
  }
}
```

**Response:**
```json
{
  "status": "RESOLVED",
  "memory_version": 47,
  "confidence": 0.76,
  "entity_resolution": {
    "candidates": [
      {
        "entity_id": "svc:api-gateway",
        "name": "API Gateway",
        "score": 0.92,
        "evidence": ["alias:the gateway", "lexical", "embedding"]
      }
    ],
    "selected": {
      "entity_id": "svc:api-gateway",
      "name": "API Gateway",
      "selection_reason": "highest score; no ambiguity"
    }
  },
  "answer": {
    "grounded_facts": [
      {
        "fact": "GraphQL Gateway depends on API Gateway",
        "evidence": ["doc:123#p4", "edge:DEPENDS_ON"],
        "confidence": 0.83
      },
      {
        "fact": "Mobile Gateway depends on API Gateway",
        "evidence": ["doc:123#p4", "edge:DEPENDS_ON"],
        "confidence": 0.83
      },
      {
        "fact": "Partner Gateway depends on API Gateway",
        "evidence": ["doc:123#p4", "edge:DEPENDS_ON"],
        "confidence": 0.83
      }
    ],
    "gaps": [
      {
        "gap": "No documented dependents beyond the listed gateways",
        "evidence": ["coverage:dep_graph"],
        "confidence": 0.62
      }
    ]
  },
  "audit": {
    "evidence_chain": ["doc:123#p4", "doc:781#p2"],
    "applied_memory": [
      {
        "type": "alias",
        "input": "gateway",
        "resolved_to": "API Gateway",
        "memory_id": "alias:42",
        "status": "CONFIRMED"
      }
    ]
  }
}
```

---

**B) Fast Verify Endpoint (Meeting Assistant)**

```
POST /api/v1/verify
```

**Purpose**: Real-time claim verification / entity lookup with strict bounds.

**Latency SLO**: P95 < 300ms, P99 < 500ms

**Rules**: No LLM in loop, bounded traversal depth (max 1–2 hops), use precomputed indexes.

**Request:**
```json
{
  "utterance": "If API Gateway goes down, mobile will be down too.",
  "verification_type": "dependency_check",
  "context": {
    "app_id": "meeting_assistant",
    "user_id": "u-777",
    "session_id": "meeting-2025-12-14-0900",
    "trace_id": "t-abc"
  }
}
```

**Response:**
```json
{
  "verdict": "SUPPORTED",
  "memory_version": 47,
  "confidence": 0.81,
  "entity_resolution": {
    "selected": {"entity_id": "svc:api-gateway", "name": "API Gateway"},
    "secondary": [{"entity_id": "svc:mobile-gateway", "name": "Mobile Gateway"}]
  },
  "support": [
    {
      "claim": "Mobile Gateway depends on API Gateway",
      "evidence": ["edge:DEPENDS_ON", "doc:123#p4"],
      "confidence": 0.84
    }
  ],
  "limits": {"max_hops": 2, "llm_used": false}
}
```

---

**C) Entity Resolver Endpoint (Optional)**

```
POST /api/v1/resolve
```

**Purpose**: Standalone resolution of entity mentions → canonical entities (helps apps preflight UI, autocomplete).

**Latency SLO**: P95 < 150ms (no LLM), P99 < 250ms

---

#### 6.2 Ambiguous / Low-Confidence Behavior

**Critical rule**: If CF cannot confidently resolve entities, it must not fabricate an answer.

| Scenario | Behavior |
|----------|----------|
| Top match confidence ≥ 0.7 | Return `status: RESOLVED` with selected entity |
| Top match confidence < 0.7, but candidates exist | Return `status: AMBIGUOUS` with `candidate_entities: [...]` |
| No entities extracted | Return `status: NO_ENTITIES_FOUND` |
| Entities extracted but none match graph | Return `status: NO_MATCHES` with extracted terms |

For `/verify` endpoint specifically, low-confidence returns `verdict: NEEDS_CLARIFICATION` with top candidates.

---

#### 6.3 Security and Tenancy

**Non-negotiable rules:**

1. **CF derives tenant from auth context (JWT claims or mTLS identity), NOT from request body.**
   - If `tenant_id` appears in request body, CF ignores it or rejects the request.

2. **All graph queries are tenant-scoped.**
   - Every query predicate includes tenant filter.
   - Cross-tenant data access is impossible by design.

3. **App identity is validated server-side.**
   - `app_id` in request is verified against token claims.

---

#### 6.4 Phase 1 Logging Requirements

To support Phase 2 learning, CF must log the following on every request (append-only):

| Field | Purpose |
|-------|---------|
| `raw_text` / `query` / `utterance` | What the app sent |
| `extracted_entities` | What CF extracted |
| `matched_entity` | What CF resolved to |
| `confidence` | Resolution confidence |
| `app_id` | Which app |
| `tenant_id` | Which tenant (from auth) |
| `user_id` | Which user (if available) |
| `session_id` | Session context |
| `trace_id` | For debugging |
| `result_status` | RESOLVED / AMBIGUOUS / NO_MATCHES / etc. |
| `helpfulness` | User feedback if provided |
| `corrections` | If user corrected the resolution |

This logging happens in Phase 1 but is not used to change behavior until Phase 2.

---

#### 6.5 Writes and Asynchrony

For performance and correctness, CF should NOT synchronously update aggregates in the request thread.

**Synchronous writes (request thread):**
- Append-only interaction event (cheap insert)
- Explicit user correction (alias mapping confirmation)

**Async writes (worker):**
- Aggregate entity usage counts
- Build/update "hot entity" lists
- Compute per-app/per-session summaries
- Bump memory_version

---

### Phase 2: Tenant Memory Layer

**Goal**: Improve resolution and usability over time, without turning usage into "facts."

#### 6.6 Memory MVP Scope

**In scope:**
1. Aliases (with governance states)
2. Resolver hints (e.g., "GW usually means API Gateway in this tenant")
3. Preferences (per app and/or per user, explicitly set)
4. Usage stats (decayed counts, not treated as truth)

**Deferred until proven necessary:**
- "Decision patterns"
- "Frameworks used"
- "Speaker models"

These tend to explode scope and are hard to audit.

---

#### 6.7 Memory APIs (Phase 2)

**A) Submit Interaction Event**

```
POST /api/v1/memory/events
```

Apps send events; CF stores them and aggregates later.

```json
{
  "event_type": "QUERY",
  "payload": {
    "raw_text": "Reduce API Gateway downtime by 50%",
    "analysis_type": "root_cause",
    "resolved_entities": [{"entity_id": "svc:api-gateway"}],
    "result_status": "RESOLVED",
    "helpfulness": "UP"
  },
  "context": {
    "app_id": "premisia",
    "user_id": "u-123",
    "session_id": "s-456",
    "trace_id": "t-789"
  }
}
```

**B) Submit Explicit Correction**

```
POST /api/v1/memory/corrections
```

```json
{
  "correction_type": "ALIAS",
  "input_text": "AG",
  "resolved_entity_id": "svc:api-gateway",
  "confirmation": "USER_CONFIRMED",
  "context": {
    "app_id": "meeting_assistant",
    "user_id": "u-777",
    "session_id": "meeting-...",
    "trace_id": "t-abc"
  }
}
```

**C) Read Memory Snapshot**

```
GET /api/v1/memory/snapshot?scope=resolver&since_version=42
```

Returns incremental changes since version 42. If no `since_version`, returns full snapshot.

---

#### 6.8 Caching & Sync Model

**Default model: CF is authoritative. Apps maintain read-through caches only.**

- CF returns `memory_version` on every response
- Apps store cached snapshot with a version
- Apps refresh snapshot:
  - On startup
  - Periodically (every 5–15 minutes)
  - Immediately if CF returns a higher `memory_version` than cache

**Conflict resolution rule:**
- App cache never "wins"
- App sends events/corrections; CF stores truth; app refreshes

---

### Phase 3: Meeting Session Snapshot

**Goal**: Eliminate network dependency for high-frequency verifications.

```
POST /api/v1/sessions
GET /api/v1/sessions/{id}/snapshot
```

Snapshot contains:
- Top N entities relevant to the meeting scope
- Confirmed aliases
- Precomputed adjacency for critical relations (DEPENDS_ON, OWNS, etc.)

Meeting Assistant loads this into memory and verifies locally, falling back to CF only on misses.

---

#### 6.9 Postgres Data Model

**Core event store (append-only)**

```sql
CREATE TABLE cf_interaction_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  app_id TEXT NOT NULL,
  user_id TEXT,
  session_id TEXT,
  trace_id TEXT,
  event_type TEXT NOT NULL,  -- QUERY, VERIFY, FEEDBACK, CORRECTION
  raw_text TEXT,
  analysis_type TEXT,
  resolved_entities JSONB,
  result_status TEXT,
  helpfulness TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_tenant_time ON cf_interaction_events(tenant_id, created_at);
CREATE INDEX idx_events_tenant_app ON cf_interaction_events(tenant_id, app_id, created_at);
CREATE INDEX idx_events_entities ON cf_interaction_events USING GIN(resolved_entities);
```

**Alias dictionary with governance**

```sql
CREATE TABLE cf_entity_aliases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  alias_text TEXT NOT NULL,  -- normalized
  entity_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PROPOSED',  -- PROPOSED, CONFIRMED, TRUSTED
  confidence FLOAT,
  source TEXT,  -- USER_CONFIRMED, ADMIN_SET, INFERRED
  evidence JSONB,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ,
  UNIQUE(tenant_id, alias_text, entity_id)
);

CREATE INDEX idx_aliases_lookup ON cf_entity_aliases(tenant_id, alias_text);
```

**Aggregated usage (decayed)**

```sql
CREATE TABLE cf_entity_usage_daily (
  tenant_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  day DATE NOT NULL,
  query_count INT DEFAULT 0,
  verify_count INT DEFAULT 0,
  PRIMARY KEY (tenant_id, entity_id, day)
);
```

**Preferences**

```sql
CREATE TABLE cf_preferences (
  tenant_id TEXT NOT NULL,
  scope_type TEXT NOT NULL,  -- TENANT, APP, USER
  scope_id TEXT,  -- app_id or user_id or null
  key TEXT NOT NULL,
  value JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, scope_type, scope_id, key)
);
```

**Memory versioning**

```sql
CREATE TABLE cf_memory_versions (
  tenant_id TEXT PRIMARY KEY,
  current_version BIGINT DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Part 7: What Each Replit Needs To Do

### CF Replit (Context Foundry)

#### Phase 1 (Must-have)

1. **Implement `/api/v1/query`**
   - Accept raw query text
   - Resolve entities (Tier 1 resolver first, Tier 2 if ambiguous)
   - Traverse graph and return grounded response + evidence chain
   - Include `memory_version` in response metadata
   - Handle ambiguous/no-match cases per spec

2. **Implement `/api/v1/verify`**
   - Strict fast path: no LLM, bounded traversal
   - Uses only Tier 1 resolver
   - Returns `SUPPORTED | REFUTED | INSUFFICIENT_EVIDENCE | NEEDS_CLARIFICATION`
   - **Performance target: P95 < 300ms, P99 < 500ms**

3. **Implement Tier 1 Resolver**
   - Normalization + alias lookup + lexical matching + embedding similarity
   - Return top candidates always (for auditability)
   - Apply only CONFIRMED/TRUSTED aliases automatically

4. **Add append-only event logging**
   - Insert into `cf_interaction_events` on each request
   - Log all fields per spec (Section 6.4)
   - Do NOT update aggregates inline

5. **Auth-bound tenant routing**
   - Tenant comes from token claim or mTLS identity
   - Ignore any `tenant_id` in the body (or reject it)
   - All queries are tenant-scoped

#### Phase 2 (Memory MVP)

6. **Implement memory endpoints**
   - `/api/v1/memory/events`
   - `/api/v1/memory/corrections`
   - `/api/v1/memory/snapshot`

7. **Implement alias governance**
   - PROPOSED vs CONFIRMED vs TRUSTED states
   - Store evidence trail for alias creation/updates
   - Ability to disable/delete aliases (admin action)

8. **Background worker**
   - Aggregate usage stats into `cf_entity_usage_daily`
   - Update `cf_memory_versions.current_version`
   - Optionally propose aliases (PROPOSED only)

#### Phase 3 (Meeting Session Snapshot)

9. **Implement session snapshot endpoints**
   - `/api/v1/sessions`
   - `/api/v1/sessions/{id}/snapshot`

---

### Premisia Replit

#### Phase 1

1. **Remove app-side entity extraction entirely**

2. **Call `/api/v1/query` with raw user input**
   ```json
   {
     "query": "Reduce API Gateway downtime by 50%",
     "analysis_type": "root_cause",
     "context": {"app_id": "premisia", ...}
   }
   ```

3. **Handle all response statuses**
   - RESOLVED: Use the grounded facts
   - AMBIGUOUS: Show candidates to user, let them pick
   - NO_MATCHES: Proceed without org context, flag to user

4. **Display CF's entity resolution for transparency**
   - Show what CF extracted and matched
   - Show confidence scores

#### Phase 2

5. **Send explicit corrections when user clarifies meaning**
   - Call `/api/v1/memory/corrections`

6. **Optionally cache resolver snapshot for autocomplete**

---

### Board Advisor Replit

#### Phase 1

1. **Use `/api/v1/query` for document-grounded analysis**

2. **Display evidence chains in UI** (trust-critical for board context)

#### Phase 2

3. **Send feedback events** (helpful/not helpful)

---

### Meeting Assistant Replit

#### Phase 1 (Critical)

1. **Use `/api/v1/verify` for real-time checks**
   - NOT `/api/v1/query` — too slow

2. **Handle `NEEDS_CLARIFICATION` quickly**
   - Show candidates in UI
   - Let user pick or dismiss

3. **Only call `/api/v1/query` if user explicitly requests deep dive**

#### Phase 2

4. **Send corrections immediately when users clarify terms live**
   - "AG means API Gateway" → `/api/v1/memory/corrections`

#### Phase 3 (Recommended)

5. **At meeting start, request snapshot**
   - `/api/v1/sessions/{id}/snapshot`

6. **Verify locally using snapshot**
   - Fall back to `/verify` on misses

---

## Part 8: Testing & Validation Checklist

### Required Before Ship

| Test | Criteria |
|------|----------|
| **Regression: Original failure** | "Reduce API Gateway downtime by 50%" must resolve to "API Gateway" and return 3 dependents |
| **Latency: /verify** | P95 < 300ms, P99 < 500ms under realistic load |
| **Latency: /query** | P95 < 15s, P99 < 30s |
| **Audit trail** | Every alias applied must appear in `audit.applied_memory` |
| **Tenant isolation** | Tenant cannot be switched via request payload |
| **Alias poisoning** | PROPOSED aliases must NOT be auto-applied |
| **Ambiguous handling** | Low-confidence matches return AMBIGUOUS with candidates, not fabricated answer |

### Golden Query Set (Build This)

Create 50-100 test queries covering:
- Simple entity lookups ("What is API Gateway?")
- Entity + action ("Reduce API Gateway downtime")
- Ambiguous terms ("Check the gateway" — which one?)
- Typos and aliases ("API GW", "AG", "api-gateway")
- Multi-entity queries ("API Gateway and Auth Service")
- No-match cases (entities not in graph)

Run against old pipeline (baseline) and new pipeline (improvement).

---

## Part 9: Success Metrics

### Phase 1 Success

- [ ] Premisia sends raw text, gets grounded results
- [ ] "Reduce API Gateway downtime by 50%" returns API Gateway + 3 dependents
- [ ] Zero entity extraction code in Premisia
- [ ] Meeting Assistant achieves <500ms P99
- [ ] Response includes entity resolution details (transparency)
- [ ] All requests logged with full context

### Phase 2 Success

- [ ] CF maintains per-app context
- [ ] Aliases learned from corrections persist
- [ ] Frequently queried entities prioritized in fuzzy matching
- [ ] Context improves match accuracy over time (measurable)
- [ ] No alias poisoning incidents

---

## Appendix A: Existing CF Capabilities

CF already has these capabilities (do not rebuild):

- **Gardener Agent**: Validates extracted entities, manages confidence scores
- **RE Agent**: Relationship extraction and validation
- **EntityResolver**: Fuzzy matching against graph
- **Constrained Extraction Pipeline**: LLM-powered extraction with validation
- **Confidence Decay**: Entity confidence decreases over time if not revalidated

Phase 1 should USE these capabilities, not duplicate them.

## Appendix B: Test Data

CF's graph currently contains (from IT Ops test data):

- "API Gateway" (SERVICE) with 3 dependents
- "GraphQL Gateway" (SERVICE) - depends on API Gateway
- "Mobile Gateway" (SERVICE) - depends on API Gateway
- "Partner Gateway" (SERVICE) - depends on API Gateway
- ~80 SERVICE entities total

Use "API Gateway" as the test case for Phase 1.

## Appendix C: Decision Log

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Two API paths (/query, /verify) | Different latency needs | Single endpoint with hints — rejected, too easy to misuse |
| Two-tier resolver | Fast path must be <500ms | LLM on every query — rejected, too slow |
| Tenant from auth, not body | Security requirement | Trust body — rejected, trivially exploitable |
| Alias governance states | Prevent poisoning | Auto-learn all aliases — rejected, too risky |
| Log now, learn later | Safer, 90% of value | Real-time learning — rejected, too complex |
| Memory in Postgres, not graph | Different data types | Put everything in graph — rejected, pollutes facts with behavior |

---

**End of Specification**

*Version 1.0 — December 14, 2025*
