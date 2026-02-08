# Context Foundry — Agent Directive v2

**Date**: 2026-02-08
**Supersedes**: Statement of Objective (2026-02-07)
**Authority**: Saleh (Product Owner)
**Scope**: All LLM agents working on Context Foundry (Codex, Replit, Claude, any others)

---

## Read This First

This document is the single source of truth for what you are allowed to do on Context Foundry. If your planned action contradicts this document, stop and ask before proceeding.

**The SOO (Statement of Objective) from Feb 7 remains in effect.** This document strengthens it with specific implementation instructions, design philosophy, and hard constraints based on what went wrong in the last 72 hours.

---

## Part 1: What Happened and Why We're Here

### The Current State

- **Accuracy**: 67-72% across multiple test runs (target: 88%)
- **Tree ON vs Tree OFF**: 72% vs 70% — the knowledge graph adds +2 points net
- **Root cause**: Extraction produces garbage (Boeing as PERSON, zero supply-chain edges, co-occurrence contamination), and every downstream component amplifies that garbage instead of catching it

### What Was Built (and Why It Didn't Help)

We built 2,500 lines of conflict-aware retrieval across 4 workstreams:
- Workstream A: Conflict detection and resolution
- Workstream B: Entity grounding validation
- Workstream C: Metric normalization and canonicalization
- Workstream D: Aggregation planning and structured compute

All 17 unit tests pass. The architecture is sound. But it moved accuracy by approximately 0 points because **there are no conflicts to resolve** — the knowledge graph either has wrong data (cross-wiring) or missing data (extraction gaps). You cannot arbitrate disputes between witnesses who never showed up.

### What Went Wrong With Agent Execution

1. **Codex** built the conflict pipeline correctly but only wired 3 of 15+ components into the retrieval router, then made unauthorized changes to the tree retriever when the eval ran
2. **Replit** was told to fix extraction but instead modified 8+ retrieval files (entity_resolver, query_classifier, reasoning, tools/wrappers, tree_retriever, role_resolver), violating the SOO. Score went from 68% to 67%
3. **Multiple agents** independently suggested "quick KG fixes" (SQL INSERTs) that would pass the test but not build the system

The pattern: every agent drifts toward retrieval/routing patches because those are easier to find and more satisfying to fix than extraction prompt work. This directive exists to prevent that drift.

---

## Part 2: Design Philosophy

Read this section carefully. These principles govern every decision.

### Principle 1: Fix Upstream Before Compensating Downstream

The pipeline is serial:

```
Documents → Chunk → Extract → Normalize → Stage → Promote → Retrieve → Resolve → Synthesize
```

Errors in stage 2 (Extraction) cascade through every subsequent stage. Fixing stage 7 (Retrieval) or stage 8 (Resolution) cannot compensate for stage 2 being broken.

**Rule**: Do not modify any stage after Promotion (stages 5-9) until Extraction (stage 2) is verified working. No exceptions without explicit authorization.

### Principle 2: The Knowledge Graph Is an Index, Not an Oracle

The KG is a structured acceleration layer derived from documents. The documents are the source of truth. When the KG contradicts the documents, the KG is wrong.

**Rule**: No KG fact should ever be served to a user without the ability to trace it back to a source chunk. If provenance is missing, the fact is unverified and should be treated as such.

### Principle 3: Verify, Don't Trust

The current architecture trusts every upstream stage completely. Extraction says "Boeing is a PERSON" → normalization accepts it → staging stores it → promotion blesses it → retrieval serves it. No stage questions the previous stage.

**Rule**: Every fact entering TRUSTED status must be verified against its source chunk. The verification question is simple: "Does this source text explicitly support this claim?" If yes, promote. If no, flag and hold in STAGING.

### Principle 4: Solve Generally, Not Specifically

A fix that only works for this test corpus is not a fix. A fix that prevents the same class of error on the next corpus is a fix.

**Rule**: Before implementing any change, ask: "If I ingested a completely different corpus tomorrow, would this change still help?" If the answer is no, you're patching, not building.

### Principle 5: One Change, One Measurement

Every eval run must isolate exactly one variable. If you change extraction AND retrieval AND run the eval, the result tells you nothing about which change helped or hurt.

**Rule**: Make one category of change → run eval → record result → decide next step. Never bundle unrelated changes into a single eval cycle.

### Principle 6: Fail Loudly, Don't Compensate Silently

When the system encounters bad data, it should flag it — not silently work around it. The staging loader silently sending relationships to the candidate store (instead of erroring on unrecognized types) is exactly how bugs hide for months.

**Rule**: When a component receives unexpected input, log a clear warning. Do not silently drop, remap, or work around data without a trace.

---

## Part 3: The Architecture You're Building

### Current Architecture (Broken)

```
Documents → Extraction → Staging → [Gardener never runs] → Retrieval (queries STAGING noise)
                                                              ↓
                                                          Synthesis (confidently wrong)
```

Problems:
- Extraction produces noise (Boeing PERSON, zero supply-chain edges, co-occurrence WORKS_AT)
- Gardener/Promotion doesn't run → everything sits in STAGING
- Retrieval either finds nothing (TRUSTED-only) or finds everything including garbage (STAGING-inclusive)
- No verification anywhere in the pipeline

### Target Architecture

```
Documents → Extraction → Staging → Batch Verification → Promotion → TRUSTED KG
                                         |                              |
                                    Source chunks                       v
                                    (verify each              Query-time retrieval
                                     fact against                      |
                                     its source)                       v
                                                              [If fact from STAGING
                                                               or low confidence:
                                                               verify against source
                                                               chunk before serving]
                                                                       |
                                                                       v
                                                                  Synthesis
```

Two additions:
1. **Batch verification after extraction** (replaces the broken Gardener): For each extracted fact, check it against its source chunk using a cheap model. Verified facts → TRUSTED. Unverified facts → stay STAGING with a flag.
2. **Query-time verification** (fallback only): When retrieval is about to serve a STAGING fact or a low-confidence fact, verify it against the source chunk before synthesis. This is the safety net, not the main path.

---

## Part 4: The Build Plan

### What Is Already Done
- [x] Staging loader bug fix (`_is_known_relationship_type` now checks mapped type)
- [x] 48 LLM-to-ontology type mappings added
- [x] Extraction prompt: supply-chain relationship examples added
- [x] Extraction prompt: co-occurrence guardrail added
- [x] Extraction prompt: entity type validation added
- [x] Conflict-aware retrieval pipeline (Workstreams A-D) — built, tested, parked

### Phase 1: Complete Extraction Validation (CURRENT PRIORITY)

**Objective**: Confirm extraction fixes actually work on a properly selected document slice.

**Step 1.1: Re-select the 5-document slice**

The previous slice had 3 meeting/steering committee documents that don't contain supply-chain language. That's a document selection error, not an extraction failure.

Select 5 documents matching these criteria:
1. A document that describes Boeing as a **customer** (not an employee, not a meeting attendee)
2. A document that describes a company **supplying** materials or components to another
3. A document where a person is **mentioned alongside** an organization they do NOT work for (tests co-occurrence guardrail)
4. A document containing a **well-known company name** that should be typed as ORGANIZATION
5. A document with an explicit **supplier-customer relationship** described in prose

**How to select**: Query the chunks table for documents containing keywords like "supplier", "customer", "contract with", "procures from", "vendor". Pick documents where the supply-chain relationship is explicit in the text.

```sql
SELECT DISTINCT document_name, chunk_text
FROM chunks
WHERE tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce'
AND (
  chunk_text ILIKE '%supplier%'
  OR chunk_text ILIKE '%customer%'
  OR chunk_text ILIKE '%procures from%'
  OR chunk_text ILIKE '%vendor%'
  OR chunk_text ILIKE '%contract with%'
)
LIMIT 20;
```

Review the results. Pick 5 documents where the relationship is clearly stated in the text.

**Step 1.2: Clear and re-extract the slice**

Extract only the 5 selected documents with the improved extraction pipeline. Do NOT extract the full vault yet.

**Step 1.3: Evaluate against pre-committed criteria**

ALL of these must pass to proceed:

| # | Criterion | Pass Condition |
|---|-----------|---------------|
| 1 | Supply-chain edges extracted | ≥3 of 5 documents produce SUPPLIES, CUSTOMER_OF, or PROCURES_FROM edges |
| 2 | Boeing typed correctly | "Boeing" / "The Boeing Company" typed as ORGANIZATION in all mentions |
| 3 | Co-occurrence reduction | WORKS_AT edges reduced by >50% compared to equivalent slice from old extraction |
| 4 | No degree anomalies | No single entity with >15 edges in the slice |
| 5 | No regressions | Relationships that worked correctly in the old extraction still work |

**If ANY criterion fails**: Iterate on extraction prompt. Do NOT proceed to Phase 2. Do NOT modify retrieval, routing, or any downstream component.

**If ALL criteria pass**: Proceed to Phase 2.

---

### Phase 2: Build Promotion-Time Verification

**Objective**: Replace the broken Gardener with automated, evidence-based fact verification.

**What this does**: For each STAGING fact (entity or relationship), fetch the source chunk that produced it. Ask a cheap, fast model: "Does this text explicitly support this claim?" Promote verified facts to TRUSTED. Flag unverified facts.

**Design specification**:

```
Module: src/context_foundry/verification/fact_verifier.py

Function: verify_fact(fact, source_chunk_text) -> VerificationResult

Input:
  - fact: A STAGING entity or relationship with its metadata
  - source_chunk_text: The text chunk that produced this fact

Output:
  - VerificationResult:
      - verified: bool (does the source support the claim?)
      - confidence: float (model's confidence in the verification)
      - reasoning: str (one-line explanation)
      - action: "PROMOTE" | "FLAG" | "REJECT"

Logic:
  1. Construct a verification prompt:
     "Given this text: [source_chunk_text]
      Does it explicitly support the claim that [entity/relationship description]?
      Answer YES or NO with a one-line reason."
  2. Call a cheap model (Claude Haiku or GPT-4o-mini)
  3. If YES with high confidence → action = PROMOTE
  4. If NO or low confidence → action = FLAG
  5. Never auto-REJECT (human review for flagged items)

Function: batch_verify(staging_facts, source_chunks) -> List[VerificationResult]

  - Iterates over all STAGING facts
  - Groups by source chunk to minimize redundant chunk fetches
  - Returns verification results for each fact
  - Logs summary: X promoted, Y flagged, Z had no source chunk

Function: promote_verified(session, tenant_id, verification_results)

  - For each result where action == PROMOTE:
      UPDATE entities SET lifecycle_state = 'TRUSTED' WHERE id = fact.id
  - For each result where action == FLAG:
      UPDATE entities SET lifecycle_state = 'STAGING',
             metadata = metadata || '{"verification_flag": "source_mismatch"}'
  - Log: "Promoted X facts, flagged Y facts"
```

**Verification prompt template**:

```
You are a fact verification system. Given a source text and a claimed fact,
determine whether the source text EXPLICITLY supports the claim.

SOURCE TEXT:
{chunk_text}

CLAIMED FACT:
{fact_description}

Does the source text explicitly support this claim?
Answer with exactly one of:
- YES: The source text directly states or clearly implies this fact
- NO: The source text does not support this fact, or contradicts it
- PARTIAL: The source text partially supports this but with important differences

Then provide a one-line reason.

Format: [YES/NO/PARTIAL] - [reason]
```

**Entity type verification** (additional check):

```
For entity facts, also verify type plausibility:
- If entity name matches a known company (Fortune 500, major corporations):
    expected_type = ORGANIZATION
    If extracted_type == PERSON → auto-FLAG with reason "Company name extracted as PERSON"
- If entity has REVENUE, CUSTOMER_OF, or SUPPLIES relationships:
    expected_type = ORGANIZATION
    If extracted_type == PERSON → auto-FLAG
```

**Cardinality verification** (additional check):

```
For relationship facts:
- If relationship type is in the 1-to-1 cardinality registry (CEO_OF, CFO_OF, etc.):
    Count existing TRUSTED relationships of same type for same entity + same time period
    If count >= 1 → FLAG new relationship with reason "Cardinality violation: multiple values"
```

**Implementation constraints**:
- This module has NO dependencies on retrieval, routing, or conflict resolution
- It reads from the staging tables and source chunks only
- It writes only lifecycle_state updates and metadata flags
- It uses a cheap model (Haiku-class) — not the main synthesis model
- It runs as a batch job after extraction, NOT at query time (query-time verification is Phase 4)

**Cost estimate**: ~3,500 relationships × ~500 tokens per verification × cheap model pricing = a few dollars per full vault verification

**Tests to write**:

```
tests/test_fact_verifier.py

test_verify_supported_fact:
  Input: chunk="Boeing announced $5B quarterly revenue", fact="Boeing EARNS $5B"
  Expected: YES - PROMOTE

test_verify_unsupported_fact:
  Input: chunk="Meeting attended by James Foster and Nel Hydrogen team",
         fact="James Foster WORKS_AT Nel Hydrogen"
  Expected: NO - FLAG (co-occurrence, not employment)

test_verify_type_mismatch:
  Input: entity={name: "Boeing", type: "PERSON"}
  Expected: FLAG - "Company name extracted as PERSON"

test_verify_cardinality_violation:
  Input: relationship={type: "HOLDS_POSITION", target: "CEO", source: "Jennifer Lee"},
         existing=[{type: "HOLDS_POSITION", target: "CEO", source: "Victoria Chen", status: "TRUSTED"}]
  Expected: FLAG - "Cardinality violation: multiple CEO values"

test_batch_verify_logs_summary:
  Input: 10 staging facts (6 supported, 3 unsupported, 1 no source chunk)
  Expected: 6 promoted, 3 flagged, 1 flagged (no source)
```

---

### Phase 3: Full Vault Re-Extraction + Verification

**Only proceed here if Phase 1 slice validation passed ALL criteria.**

**Step 3.1**: Re-extract the full 197-document vault with improved extraction pipeline

**Step 3.2**: Run batch verification on all STAGING facts
- Log: how many promoted vs flagged
- Log: distribution of flag reasons (type mismatch, source mismatch, cardinality violation, no source chunk)

**Step 3.3**: Run automated validation (Phase 2.5 from SOO)
- Entity type distribution (no single type > 30%)
- Relationship type distribution (WORKS_AT < 20%, supply-chain edges > 0)
- Degree anomalies (no entity with > 15 edges)
- Schema coverage (which ontology types have zero instances?)
- Diff vs old KG: what improved, what regressed, why

**Step 3.4**: Run 100-question evaluation

**Expected outcome**: 82-85% accuracy

**Decision gate**:
- If ≥82%: Proceed to Phase 4 (query-time verification) and then Phase 5 (conflict resolution)
- If 75-82%: Analyze failures — are they extraction errors the verifier should have caught, or genuine retrieval issues? Iterate on verifier or extraction before moving downstream.
- If <75%: Something regressed. Diff the KG. Do NOT modify retrieval. Find the regression source.

---

### Phase 4: Query-Time Verification (Fallback Path)

**Only proceed here after Phase 3 eval shows ≥82%.**

This is the safety net for facts that batch verification missed or for STAGING facts that need to be served.

**Design**: When retrieval returns a fact for synthesis:
- If fact is TRUSTED → serve directly (already batch-verified)
- If fact is STAGING or low-confidence → verify against source chunk before serving
- If verification fails → fall back to document retrieval for that claim

**Implementation**: ~50 lines added to the retrieval router. One LLM call for STAGING facts only. TRUSTED facts pass through without extra cost.

---

### Phase 5: Conflict Resolution Activation

**Only proceed here after Phase 4 is deployed and measured.**

This is when the 2,500-line conflict-aware pipeline earns its place. After extraction is clean and verification catches errors, the remaining failures should be genuine conflicts:
- Dual revenue figures from different sources (both valid, different reporting periods)
- Role succession (Jennifer Walsh → Michael Chang as CFO)
- Aggregation classification (Q1 + FY = subsumption, not complement)

At this point:
- Wire the conflict pipeline into the retrieval router (the wiring code from the earlier commit)
- Run eval
- Measure which conflicts are actually resolved

---

## Part 5: Hard Constraints

These are non-negotiable. Violation of any constraint requires stopping and asking for authorization.

### Files You May Edit (Phases 1-2)

```
ALLOWED:
  src/context_foundry/extraction/          (extraction prompts, extraction pipeline)
  src/context_foundry/staging/             (staging loader, type mappings)
  src/context_foundry/verification/        (NEW — fact verifier module)
  src/context_foundry/metrics/             (if needed for verification)
  tests/test_fact_verifier.py              (NEW)
  tests/test_metric_normalization.py       (existing, don't break)

FORBIDDEN (until Phase 4+):
  src/context_foundry/agents/retrieval_router.py
  src/context_foundry/agents/retrieval.py
  src/context_foundry/agents/entity_resolver.py
  src/context_foundry/agents/query_classifier.py
  src/context_foundry/agents/reasoning.py
  src/context_foundry/agents/role_resolver.py
  src/context_foundry/retrieval/tree_retriever.py
  src/context_foundry/tools/
  src/context_foundry/conflict/            (already built, don't touch)
  src/context_foundry/aggregation/         (already built, don't touch)
  src/context_foundry/grounding/           (already built, don't touch)
```

### Actions You May NOT Take

1. **No SQL INSERT/UPDATE/DELETE on entity or relationship tables** to fix specific test failures
2. **No modifications to retrieval, routing, or synthesis** until Phase 4
3. **No "quick fixes"** to role resolution, supplier lookup, or lifecycle filters
4. **No unauthorized code changes** — if you discover a bug outside the ALLOWED files, report it. Do not fix it.
5. **No bundling multiple changes into one eval run** — one category of change per measurement cycle
6. **No reinterpreting pass/fail criteria after seeing results** — criteria are pre-committed

### When To Stop And Ask

- You discover a bug in a FORBIDDEN file that blocks your work
- Extraction improvements require a schema change
- The 5-document slice fails criteria and you're unsure whether it's a doc selection issue or extraction issue
- You want to add a dependency or install a package
- Anything feels like it's "working around" a problem rather than fixing it

---

## Part 6: How To Report Results

After every significant action, report using this format:

```
## Action Taken
[What you did, in 1-2 sentences]

## Files Changed
[List of files modified, with line counts]

## Test Results
[Unit tests: X/Y passed]
[Eval score: X/100 if applicable]

## Before/After Comparison
[What changed in the output — specific questions that flipped, distribution changes, etc.]

## Unexpected Findings
[Anything you discovered that wasn't part of the plan]

## Next Step
[What you plan to do next, with reference to which Phase/Step in this directive]

## Asking Permission For
[If you need to do something outside the ALLOWED scope, state it here]
```

---

## Part 7: The Philosophy (Read This Last)

Context Foundry's purpose is **organizational object permanence for AI** — it refuses to hallucinate and admits uncertainty.

Right now, the system hallucinate at extraction time and then confidently serves those hallucinations as facts. Boeing is not a person. James Foster does not work at Nel Hydrogen. The system says they do because no component in the pipeline questions what extraction produced.

We are building a system where:

1. **Extraction is good but not perfect** — improved prompts reduce systemic errors
2. **Verification catches what extraction misses** — every fact is checked against evidence before it becomes trusted
3. **The system admits what it doesn't know** — unverified facts are flagged, not served confidently
4. **Conflicts are resolved with evidence** — when verified facts genuinely disagree, the conflict pipeline arbitrates with source trust, temporal supersession, and evidence weighting

This is the order. Not 4 before 1. Not 3 before 2. The sequence matters because each layer depends on the one before it.

**The test tells us when the system works. But the system working means it extracts correctly and verifies honestly — not that we patched around its failures.**

---

**Effective immediately. Supersedes all prior instructions except where the SOO is explicitly referenced and consistent.**

**Approved by**: Saleh (2026-02-08)
