# Statement of Objective: Building a System That Works

**Date**: 2026-02-07
**For**: All LLMs working on ContextFoundry
**Purpose**: Shared framing and decision rationale for extraction system improvements

---

## Where We've Been

### The Journey So Far

1. **Starting Point**: 74% accuracy baseline on ontology vault with tree-based retrieval causing performance issues

2. **Research Phase**: Analyzed 60 pages of deep reasoning LLM research on conflict-aware retrieval, discovering techniques like:
   - SOURCE_TRUST hierarchy (4-tier document authority)
   - Evidence-weighted scoring (CRH)
   - 8-case fact classification
   - Metric canonicalization and temporal normalization

3. **Implementation Phase**: Built conflict-aware retrieval pipeline (2,500+ lines across 4 workstreams):
   - Workstream A: Conflict detection/resolution
   - Workstream C: Metric normalization
   - Workstream D: Aggregation planning
   - Workstream B: Entity grounding

4. **Testing Phase**: Ran controlled A/B tests:
   - Tree ON: 72%
   - Tree OFF: 70%
   - Net impact: +2 points (tree retrieval), but conflict resolution impact unclear

5. **Diagnostic Phase**: Conducted comprehensive failure audit of all 24 failing questions:
   - **8 CROSS_WIRING**: Wrong entity returned (Boeing PERSON with 16 edges poisoning queries)
   - **6 CONFLICT**: Multiple competing values (CFO, President mismatches)
   - **5 EXTRACTION_GAP**: Missing relationships (0 supply-chain edges despite ontology support)
   - **3 RETRIEVAL_GAP**: Data in docs but not extracted
   - **2 FORMAT_ISSUE**: Right data, wrong format

6. **Root Cause Analysis**: Found three systemic patterns:
   - **Boeing Mistype**: Extracted as PERSON instead of ORGANIZATION, created high-degree node that absorbs all customer queries
   - **Co-occurrence Contamination**: People mentioned in same chunk get WORKS_AT relationships when they shouldn't
   - **Zero Supply-Chain Relationships**: Extraction prompt heavily biased toward HR relationships (492 WORKS_AT = 25.6% of all relationships), completely ignores SUPPLIES, CUSTOMER_OF, PROCURES_FROM despite ontology defining them

---

## The Decision Point

After the RCA, we received **9 different opinions** on what to do next:

### What We're NOT Doing (And Why)

**NOT doing Opinions 1-8: "Fix the KG first, then improve extraction"**

These opinions (including Codex's initial recommendation and my Opinion 8) all suggested:
1. Execute 10 Tier-1 KG fixes manually (delete Boeing PERSON, add missing relationships)
2. Get to 88% accuracy immediately
3. Then improve extraction to prevent recurrence

**Why we're rejecting this:**
- **Violates "solve generally" principle**: Manual KG fixes are band-aids that only work for this specific test corpus
- **Creates technical debt**: Next corpus will have the exact same problems (Boeing mistyped again, supply-chain relationships missing again)
- **Optimizes for passing the test, not building a system**: We'd prove we can patch around a broken extraction system, not that we fixed it
- **Doesn't compound**: Effort spent on Tier-1 fixes provides zero value for future vaults

**NOT doing Opinion 6: "Heavy architecture changes (Relink/SHACL/Bayesian/QUEST)"**
- Over-engineered for current stage
- Introduces massive complexity before validating basics work
- R&D track, not operational priority

---

## What We're Doing (Opinion 9: Fix the Extraction System)

### The Core Insight

> "The Tier 1 SQL fixes I proposed — manually inserting 10 relationships — that's passing the test. The next corpus you ingest would have the exact same problems." - Opinion 9

The 24 failures aren't random data errors. They're **symptoms of a broken extraction system**:
- The prompt doesn't know supply-chain relationships exist
- The prompt treats every co-occurrence as employment
- Entity type validation doesn't happen at extraction time

**If we fix the extraction system**, these patterns won't recur on future corpora. **If we patch the KG**, we're just covering up the system's inability to extract correctly.

### The Most Important Learning

> "You gave yourself one page that correctly identifies the actual problem. The extraction system doesn't know what a supply chain is. Everything downstream — the conflict resolver, the entity grounding, the aggregation planner — was sophisticated machinery compensating for that one upstream failure."

We built 2,500 lines of conflict-aware retrieval (SOURCE_TRUST hierarchy, evidence-weighted scoring, metric normalization, aggregation planning) to work around an extraction system that didn't know SUPPLIES existed as a relationship type.

**The sophisticated downstream machinery was compensating for upstream failure.**

This is why we must fix extraction first. Once the KG contains clean entities, correct types, and supply-chain edges, the conflict-aware pipeline becomes the right tool for handling **legitimate conflicts** (dual revenue figures, role succession, temporal aggregation). The work wasn't wasted — it was **correctly sequenced**.

### Our Plan

**Phase 1: Extraction System Fixes (1-2 days)**

1. **Add Supply-Chain Relationship Examples to Prompt**
   - Current: 492 WORKS_AT (25.6%), 0 SUPPLIES/CUSTOMER_OF/PROCURES_FROM
   - Fix: Add few-shot examples showing what supply-chain relationships look like
   - Expected: Distribution shifts toward commercial relationships

2. **Add "Co-occurrence ≠ Employment" Guardrail**
   - Current: Person mentioned alongside organization → WORKS_AT created
   - Fix: Add explicit instruction: "Person mentioned in meeting/report/project context does NOT mean they work there"
   - Expected: Eliminates false WORKS_AT edges (James Foster, Jennifer Walsh, etc.)

3. **Add Entity Type Validation at Extraction Time**
   - Current: Boeing extracted as PERSON, nothing stops it
   - Fix: Validate entity types against ontology before entering KG
   - Expected: Catches structural errors before they poison the graph

**Phase 2: Validation on Small Slice (1 day)**

### Pre-Committed Pass/Fail Criteria (CRITICAL - Define BEFORE Running Slice)

**Test Set**: Select 5 specific documents containing known patterns:
1. Document with Boeing as customer (should extract CUSTOMER_OF, not just WORKS_AT)
2. Document with Siemens as supplier (should extract SUPPLIES)
3. Document with Nel Hydrogen co-occurrence (should NOT create false WORKS_AT)
4. Document with major company mention (should type as ORGANIZATION, not PERSON)
5. Document with supply-chain relationship (any type: SUPPLIES/CUSTOMER_OF/PROCURES_FROM)

**PASS Criteria (ALL must be true to proceed to Phase 3):**
- ✅ ≥3 of 5 documents produce correct supply-chain edges (SUPPLIES/CUSTOMER_OF/PROCURES_FROM)
- ✅ Boeing typed as ORGANIZATION (not PERSON) in all mentions
- ✅ Co-occurrence WORKS_AT edges reduced by >50% compared to current KG slice
- ✅ No new degree anomalies (no entity with >15 edges in the slice)
- ✅ No regressions on relationships that currently work correctly

**FAIL → Iterate on prompt improvements, do NOT proceed to full re-extraction**

**Why pre-commitment matters**: Without defined criteria before testing, there's temptation to rationalize partial results as "good enough to proceed." The system should **work** — define what working looks like before you test it.

---

4. **Re-extract 5 selected documents** with improved prompt
   - Apply Phase 1 improvements to extraction system
   - Run extraction on the 5-document test set
   - Evaluate against pre-committed pass/fail criteria above

**Phase 2.5: Automated Validation Pass (CRITICAL)**

5. **Run automated validation on slice output BEFORE looking at test scores**
   - **Type consistency checks**: Any suspicious entity types? (e.g., major companies typed as PERSON)
   - **Schema coverage**: Which ontology relationship types still have zero instances?
   - **Degree anomalies**: Any single entity with suspiciously high degree (>10 edges)?
   - **Distribution analysis**: Does relationship type distribution look reasonable? (Not 25% WORKS_AT)
   - **Cardinality violations**: Any 1-to-1 relationships with multiple values?
   - **Regression detection (Category 0 Gate)**: Diff old KG vs new KG for the slice
     - Track what improved (new supply-chain edges, correct entity types)
     - Track what regressed (relationships that disappeared, entities that changed incorrectly)
     - If improvements come with regressions, understand WHY before proceeding
     - Example: If 3 documents improve but 2 regress on relationships that currently work, iterate on prompt

**Why this matters**:
- The three bugs we found (Boeing PERSON, zero supply-chain, co-occurrence contamination) are the three bugs **the test surfaced**. This validation pass finds the bugs **the test didn't surface** before they cost us another debugging cycle.
- **Re-extraction may introduce NEW errors**: Changing the prompt fixes known patterns but can regress things that currently work. Don't just look at test scores — diff the KGs to understand the full impact.

**Phase 3: Full Vault Re-Extraction (conditional)**

6. **If slice validates**, re-extract entire 197-document vault
7. **Run automated validation on full output** (same checks as Phase 2.5, including regression detection)
8. **Run 100-question test** to measure system capability
9. **Expected outcome**: 82-85% accuracy from clean extraction

**Phase 4: When Conflict-Aware Pipeline Becomes Priority**

After extraction fixes land and the KG contains clean entities/types/relationships:

- **Expected initial lift**: 82-85% accuracy (clean extraction eliminates cross-wiring, extraction gaps)
- **Remaining gap to 88-90%**: Legitimate conflicts that clean extraction can't resolve:
  - Dual revenue figures from different sources (both valid, different reporting periods)
  - Role succession (Jennifer Walsh → Michael Chang as CFO, temporal supersession needed)
  - Aggregation classification (Q1 revenue + FY revenue = subsumption, not complement)
  - Metric conflicts ($2.3B vs $1.8B for same metric, SOURCE_TRUST needed to resolve)

**This is when the conflict-aware pipeline becomes the right tool**:
- SOURCE_TRUST hierarchy resolves document authority conflicts
- Evidence-weighted scoring handles contested values
- Temporal normalization enables supersession logic
- 8-case fact classifier prevents aggregation double-counting

**The 2,500-line pipeline wasn't wasted — it was correctly sequenced.** We needed clean extraction first to know which conflicts are **legitimate** (dual sources) vs **artificial** (Boeing PERSON poisoning queries).

**Phase 5: Fallback Only If Needed**

10. **Only if extraction improvements don't fix specific high-impact failures**, apply targeted Tier-1 KG patches
    - This becomes the exception, not the rule
    - Documents which failures are extraction-resistant

---

## Our Goal

### What Success Looks Like

**Primary Goal**: Build an extraction system that produces clean knowledge graphs without manual intervention.

**Success Criteria**:

1. **Systematic Improvement**: Next vault ingested should NOT have Boeing PERSON, zero supply-chain relationships, or co-occurrence contamination

2. **Generalization Test (CRITICAL)**: Take a **different document corpus** (10-20 docs about a different company with different people, products, and supply chains), run it through the improved extraction pipeline, and validate:
   - Does relationship type distribution look reasonable?
   - Do supply-chain edges appear?
   - Are entity types correct?
   - No single entity has >10 edges (degree anomaly)?

   **Why this matters**: If we only validate on the same 197 Nexus documents, we're still implicitly teaching to the test — just at the extraction level instead of the KG level. The generalization test proves the system learned **generally**, not just "learned to extract from these specific documents better."

3. **Accuracy Target**: 86-89% on current test (validates extraction fixes work on known corpus)

4. **Compounding**: Effort invested carries forward to every future vault

### What We're NOT Optimizing For

- ❌ **Passing this specific test**: We're not tuning to the 100 questions
- ❌ **Short-term accuracy gains**: We're not taking the fastest path to 88%
- ❌ **Manual intervention**: We're not building a system that requires KG surgery every time
- ❌ **Code complexity**: We're not adding more retrieval layers when extraction is the bottleneck

---

## Remember: We're Building a System, Not Passing a Test

The 100-question test is a **diagnostic tool**, not a target. It surfaces where the system fails so we can identify and fix root causes.

If we optimize for test performance, we get:
- Manual KG fixes that don't generalize
- Overfitted prompts tuned to these specific questions
- Technical debt that bites us on the next corpus

If we optimize for system capability, we get:
- Extraction that produces clean graphs automatically
- Patterns that transfer to new domains
- Compounding improvements that make each vault better than the last

**The test will tell us when the system works.** But the system working means it extracts correctly, not that we patched around its failures.

---

## Instructions for All LLMs

When working on ContextFoundry:

1. **Do NOT implement Tier-1 KG fixes** (manual relationship insertions) unless explicitly instructed
2. **Do focus on extraction prompt improvements** - this is the current priority
3. **Do validate changes on small slices** before committing to full re-extraction
4. **Do run automated validation** on extraction output before looking at test scores
5. **Do test generalization** on a different corpus to prove system learned generally
6. **Do ask "does this generalize?"** before implementing any fix
7. **Do remember: solve generally, no band-aids, build systems that work**

If you find yourself writing SQL INSERT statements to fix specific test failures, **stop and reconsider**. That's passing the test, not building the system.

---

## Next Immediate Actions

**Phase 1: Extraction Improvements**
1. Read current extraction prompt
2. Implement supply-chain relationship examples (SUPPLIES, CUSTOMER_OF, PROCURES_FROM)
3. Implement co-occurrence guardrail ("co-occurrence ≠ employment")
4. Implement entity type validation against ontology

**Phase 2: Slice Validation (MOST CRITICAL GATE)**
5. **Select 5 test documents** matching pre-committed criteria (Boeing customer, Siemens supplier, Nel co-occurrence, entity typing, supply-chain)
6. **Re-extract 5 documents** with improved prompt
7. **Evaluate against pass/fail criteria** BEFORE looking at full test:
   - ≥3 supply-chain edges extracted correctly?
   - Boeing typed as ORGANIZATION?
   - Co-occurrence WORKS_AT reduced >50%?
   - No new degree anomalies?
   - No regressions on currently-working relationships?
8. **Decision**: PASS → proceed to Phase 2.5 | FAIL → iterate on prompt

**Phase 2.5: Automated Validation**
9. **Run automated validation on slice output** BEFORE test scores:
   - Type consistency, schema coverage, degree anomalies, distribution analysis
   - **Diff old KG vs new KG**: What improved? What regressed? Why?
10. **Understand regressions** before proceeding to full re-extraction

**Phase 3: Full Re-Extraction (Conditional)**
11. If slice validates cleanly, re-extract full 197-document vault
12. Run automated validation on full output (including regression detection)
13. Run 100-question test

**Phase 4: Generalization Test**
14. **Prepare different corpus** (different company, 10-20 docs)
15. **Run extraction** on generalization corpus
16. **Validate**: Does system extract correctly on unseen domain?

---

**Constraints for All Work:**

**No code changes** to retrieval, routing, or conflict resolution unless data quality improvements reveal new bottlenecks.

**No manual KG edits** unless extraction improvements prove insufficient for specific cases after full validation.

**The goal is a system that extracts correctly, not one that compensates for bad extraction.**

**If you find yourself writing SQL INSERT statements to fix specific test failures, STOP.** That's passing the test, not building the system.

---

**Approved by**: User (2026-02-07)
**Strengthened with**:
- Claude's validation pass and generalization test requirements
- Concrete pre-committed pass/fail criteria for Phase 2 decision gate
- Regression detection (Category 0 Gate) in Phase 2.5
- Acknowledgment that conflict pipeline is correctly sequenced, not discarded

**Effective immediately for all agents working on ContextFoundry**
