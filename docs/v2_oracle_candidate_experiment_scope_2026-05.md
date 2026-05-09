# v2 Oracle-Candidate Validation — Experiment Scope

**Date:** 2026-05-09
**Status:** SCOPED, not run. Decision-relevant for Task 4 ("park v2?").
**Estimated runtime:** ~1 hour wall clock, ~$15-25 in Anthropic spend.
**Prerequisite:** Anthropic API credit balance restored (the 2026-05-09 v2 parallel run was blocked by an empty balance — see "Hard prerequisite" below).

---

## Question this experiment answers

> Does v2's `FactEvaluator` correctly evaluate facts when given the *correct*
> candidate `Fact(s, r, t)` — separating "evaluator logic works" from
> "candidate generation works"?

The Task 2 v2 parallel run fed v2 the *fact derived from v1's answer*. When v1 was wrong, that's a wrong candidate, and v2's verdict tells us nothing about the evaluator's competence. This experiment isolates the evaluator by feeding it the verifiable correct candidate for each of the 26 failures and measuring how often v2 returns a verdict consistent with that candidate being true.

If v2 reaches the correct verdict on, say, 20+/26 oracle candidates, then v2's evaluator logic is working and the v2 chapter's failure mode is candidate-generation/integration, not evaluator design. If v2 reaches the correct verdict on 5-10/26, the evaluator itself has correctness gaps — relevant context for any future "rebuild" decision.

This is **the only experiment that lets us evaluate v2's validator on its own terms.** Without it, "park v2" is defensible on cost-and-marginal-recovery grounds but not on "the validator is broken" grounds.

---

## Method

### 1. Build the oracle candidate set (deterministic, no LLM)

For each of the 26 questions in the 74-baseline failure set
(`test_results/claudecode_nexus_industries_20260509_073740.json`), build a
`Fact(subject_entity_id, relationship_type, target_entity_id)` from the **expected** answer:

| Question kind | Oracle candidate construction |
|---|---|
| Person-role lookup ("Who is the X of Y?") | `Fact(person_id, HOLDS_POSITION, role_label)` resolved from `expected` |
| Person-affiliation ("Who reports to X?") | `Fact(reporter_id, REPORTS_TO, manager_id)` |
| Customer/supplier ("Who supplies X to Y?") | `Fact(supplier_id, SUPPLIES, product_id)` (and SUPPLIES_TO/CUSTOMER_OF variants) |
| Numeric/spec value | `Fact(entity_id, HAS_PROPERTY, value)` — falls back to `V2_NO_CANDIDATE` for the architecturally-unsupported aggregation cases (Q40, Q66, Q79) |
| Date/temporal | `Fact(entity_id, HAS_DATE, date_value)` — similarly unsupported for Q14, Q45 (date arithmetic) |
| Cross-document aggregation | Marked `V2_NO_CANDIDATE` upfront; v2 has no compute layer (Q40, Q66, Q79) |

Entity resolution uses the same name-lookup the runner already uses
(`scripts/run_v2_parallel.py:resolve_entity`). Where a target value isn't an
entity (numeric, date, string), the candidate is marked `V2_NO_CANDIDATE` and
recorded as architecturally out of scope rather than fed to v2.

Expected count breakdown (from the failure taxonomy):
- 8 RETRIEVAL_VOID + 6 RETRIEVAL_WRONG_ENTITY + 1 of EXTRACTION_MISSED that has a name target = ~15 oracle candidates v2 *should* handle
- 4 EXTRACTION_MISSED (numeric/spec) = candidates only if HAS_PROPERTY-style fact is supported; we'll try and tag UNDERSPECIFIED if not
- 3 SYNTHESIS + 3 CROSS_DOCUMENT + 2 DATE_TEMPORAL = ~8 architecturally out-of-scope, marked V2_NO_CANDIDATE without invocation

So the meaningful test surface is ~15 oracle candidates for which v2 should
return a `PROVEN`/`STRONGLY_SUPPORTED`/`SUPPORTED` verdict (the candidate is the
correct fact, by construction).

### 2. Run

A new script `scripts/run_v2_oracle.py` (one fork of `scripts/run_v2_parallel.py`):

- Same per-question 5-min ceiling.
- Same 6-h total budget (overestimate; ~26 × ~3 min average = ~80 min expected).
- Skip the LLM-based fact extractor entirely. Use the oracle-built `Fact` directly.
- Record verdict status, derived answer, wall-time, LLM call counts (from tracer
  `evaluate_summary`), timeout flag, error.

Output: `test_results/v2_parallel/oracle.jsonl`, one record per question.

### 3. Grade

Per-question outcome (no fuzzy LLM grader needed — the oracle candidate is true
by construction, so the v2 verdict either agrees or doesn't):

| v2 verdict | Interpretation | Counts as |
|---|---|---|
| PROVEN, STRONGLY_SUPPORTED, SUPPORTED | v2 correctly endorsed the true fact | **CORRECT** |
| CONTESTED | v2 surfaced competing facts; check if true fact is one of them | partial — log for inspection |
| UNDERSUPPORTED, UNKNOWN, UNDERSPECIFIED | v2 couldn't confirm the true fact | **WRONG** (evaluator gap or retrieval failure inside v2) |
| DISPROVEN | v2 actively rejected the true fact | **WRONG** (evaluator hallucination — most concerning) |
| V2_TIMEOUT | hit 5-min ceiling | **WRONG** (perf gap) |
| V2_ERROR | crashed | **WRONG** (correctness gap) |

Decision matrix:

- **≥ 12/15 CORRECT (≥ 80%):** v2's evaluator works on its own merits. The
  failure mode is candidate generation / system integration. "Park v2 the
  validator" decision should explicitly note this.
- **6-11/15 CORRECT (40-73%):** evaluator has meaningful gaps but isn't broken.
  Candidate-generation issues compound; both layers need work.
- **≤ 5/15 CORRECT (≤ 33%):** evaluator itself is unreliable. "Park v2" is the
  right call regardless of candidate-generation question.

### 4. Cross-reference with the gatherer salvage decision

If oracle accuracy is high (≥ 80%) but real-world parallel-run accuracy is low
(measured: ~0%, blocked by API credits), the bottleneck is *getting v2 the right
candidate to evaluate* — and that's the v1 → v2 boundary, which is exactly
what the gatherer salvage recon (`docs/v2_gatherer_salvage_recon_2026-05.md`)
addresses from the other direction. The two pieces compose: v1 + lifted gatherer
gets the right entities surfaced → fact extraction yields the right candidate →
v2 endorses it.

If oracle accuracy is low, the gatherer salvage is still independently valuable
but it doesn't rescue v2 the validator.

---

## What this experiment does **not** answer

- Whether v2 finds the correct fact when only the question is given. (That's the
  Task 2 parallel run, which we attempted and was blocked by the credit issue.)
- Whether v2 catches *false* candidates. (Symmetric experiment: feed v2 a
  deliberately-wrong candidate per question and verify it returns DISPROVEN/
  CONTESTED. Worth running as a follow-up if oracle accuracy is high.)
- Whether v2 is cost-effective at scale. (Even if oracle accuracy is 100%, the
  per-fact cost is the parallel-run cost, ~$0.50-2/question. That's the
  parking decision's economic axis, not a correctness one.)

---

## Hard prerequisite

The Anthropic API credit balance must be restored before this experiment can
run. The 2026-05-09 v2 parallel run terminated in 58 seconds with 78
EXTRACTION_ERROR results because every API call returned HTTP 400:

```
Your credit balance is too low to access the Anthropic API.
Please go to Plans & Billing to upgrade or purchase credits.
```

This script uses the same Anthropic Sonnet 4.6 model via the same `LLMClient`
and will fail in exactly the same way until the balance is topped up. Estimated
spend for the oracle run: 15 candidates × ~5-10 LLM calls each (planner + 2-4
gatherer polarity + 2 prover + 1 meta + 0-2 adversary rounds) × ~$0.05/call =
**~$15-25 total**, well within a small credit purchase.

---

## When to run

After: (a) Anthropic balance restored, (b) Task 4 decision committed (so the
oracle experiment is informational rather than blocking the decision). The
experiment's value is in informing the *next* iteration if v2 is parked, or in
characterizing the validator's actual ceiling if v2 stays.

Estimated wall-clock: 60-90 minutes including setup. Single-shot, no iteration
needed.
