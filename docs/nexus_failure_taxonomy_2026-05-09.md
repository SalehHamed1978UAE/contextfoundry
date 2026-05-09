# Nexus 100 — Failure Taxonomy

**Source run:** `test_results/claudecode_nexus_industries_20260509_065714.json`
**Score:** 77/100 (23 failures)
**Vault:** `176a4fb2-0bb4-4da3-9068-0e26268fca71`
**Vault stats:** 501 chunks, 6624 entities, 1436 relationships
**Config:** `tree_based_retrieval=True`

> **Note (2026-05-09, addendum below):** the v1 baseline used for the Task 2
> v2-parallel run is the freshly-rerun `claudecode_nexus_industries_20260509_073740.json`
> at 74/100 (26 failures). Its failure set is a strict superset of this 23-failure
> set — three additional questions (Q15, Q29, Q73) flipped from PASS to FAIL
> within normal run-to-run variance, all three with classifications and v2-prognoses
> consistent with the buckets already in this table. See "Baseline drift addendum"
> at the bottom for per-question detail. The distribution percentages and read-out
> below still describe the 23-failure source run; the addendum re-states the
> three new rows so cross-referencing between this taxonomy and the 26-row Task 3
> matrix is unambiguous.

## Taxonomy

- `RETRIEVAL_VOID` — no documents retrieved or no entity surfaced
- `RETRIEVAL_WRONG_ENTITY` — wrong entity surfaced (e.g. centrality bias)
- `EXTRACTION_MISSED` — right document retrieved, relationship not in graph
- `DATE_TEMPORAL` — answer requires date arithmetic or temporal scoping
- `CROSS_DOCUMENT` — answer requires reasoning across multiple documents
- `CONFIDENCE_MISCALIBRATED` — right fact present, wrong confidence assigned (v2's target class)
- `SYNTHESIS` — right evidence present, wrong reasoning over it
- `OTHER` — explained inline

## Per-failure classification (23 rows)

| Q  | Expected                                                | Actual (compressed)                                          | Mode                       | Justification                                                                                                          | v2 prognosis              |
|----|---------------------------------------------------------|--------------------------------------------------------------|----------------------------|------------------------------------------------------------------------------------------------------------------------|---------------------------|
| 1  | Dr. Victoria Chen                                       | "Only mentions VP Trade Compliance"                          | `RETRIEVAL_VOID`           | Entity exists in vault (proven by Q45) but CEO_OF/HOLDS_POSITION edge not surfaced for this query.                     | unrecoverable             |
| 14 | January 2026                                            | "Appointment date was not found"                             | `DATE_TEMPORAL`            | Pure date question; dates live in chunks, not graph.                                                                   | unrecoverable             |
| 17 | Nel Hydrogen                                            | Honeywell, Boeing, Lockheed, Northrop                        | `RETRIEVAL_WRONG_ENTITY`   | Surfaced top defense suppliers (most-connected) instead of product-specific electrolyzer supplier — centrality bias.   | unrecoverable             |
| 18 | Shell                                                   | "Does not specify… mentions NexusConnect, Aerospace…"        | `RETRIEVAL_VOID`           | Offtake-agreement relationship/document not retrieved at all.                                                          | unrecoverable             |
| 24 | 425 kg/hr (Phase 1)                                     | 850 kg/hr (full capacity)                                    | `SYNTHESIS`                | Both numbers present in corpus; engine returned the unqualified figure without parsing the "Phase 1" qualifier.        | **conditionally recoverable** |
| 25 | 400 Wh/kg                                               | "Does not specify a target energy density"                   | `EXTRACTION_MISSED`        | Spec value lives in technical doc; SPECIFICATION extraction did not capture it (known weak class).                     | unrecoverable             |
| 36 | Advanced Materials (1.24 TRIR)                          | Energy Division (0.78 TRIR)                                  | `CROSS_DOCUMENT`           | Requires comparing TRIR across all four divisions; Advanced Materials TRIR likely missing so comparison ran short.     | unrecoverable             |
| 37 | Jennifer Walsh                                          | "Does not specify Project Director"                          | `RETRIEVAL_VOID`           | Project-Director-of relationship not surfaced.                                                                         | unrecoverable             |
| 38 | Jennifer Walsh (formerly Robert Kim)                    | "I don't have enough information"                            | `RETRIEVAL_VOID`           | CISO succession chain not retrieved.                                                                                   | unrecoverable             |
| 40 | $12.4 billion                                           | $11.5 billion (sum of 4 divisions)                           | `CROSS_DOCUMENT`           | Wrong total; per-division figures don't reconcile to corpus's stated total.                                            | unrecoverable             |
| 45 | 2019                                                    | March 2018                                                   | `DATE_TEMPORAL`            | Wrong appointment year — date extraction error.                                                                        | unrecoverable             |
| 46 | First Solar                                             | "Does not specify who supplies solar panels"                 | `RETRIEVAL_VOID`           | Supplier relationship for Desert Sun not surfaced.                                                                     | unrecoverable             |
| 48 | Siemens Healthineers ($65M)                             | The Boeing Company                                           | `RETRIEVAL_WRONG_ENTITY`   | Picked most-connected customer (Boeing) instead of HTS-wire-specific customer — centrality bias.                       | unrecoverable             |
| 60 | Dec 12, 2025 02:47 UTC                                  | "No information about phishing incident"                     | `RETRIEVAL_VOID`           | Security incident document/entity not retrieved (date moot if incident itself isn't found).                            | unrecoverable             |
| 61 | Robert Kim                                              | "J. Williams holds the position"                             | `RETRIEVAL_WRONG_ENTITY`   | Returned different President entity instead of following REPLACED edge from Thomas Anderson; succession not traversed. | unrecoverable             |
| 66 | $680 million                                            | $520 million                                                 | `CROSS_DOCUMENT`           | Capex plan requires aggregating across divisional sub-budgets; aggregation produced wrong total.                       | unrecoverable             |
| 67 | -30°C to 60°C                                           | "Does not specify operating temperature range"               | `EXTRACTION_MISSED`        | Spec value not captured during extraction.                                                                             | unrecoverable             |
| 68 | Col. James Foster (Empowered Official)                  | "The Empowered Official" (no name)                           | `RETRIEVAL_VOID`           | Role-to-person dereference is a graph-join traversal failure, not a reasoning gap (reclassified per review).           | unrecoverable             |
| 71 | Caterpillar                                             | Rio Tinto                                                    | `RETRIEVAL_WRONG_ENTITY`   | Surfaced customer (Rio Tinto) when asked about partner (Caterpillar) — entity-role confusion.                          | unrecoverable             |
| 79 | $15 billion (corporate total)                           | Lists divisional targets (~$15B sum), no aggregation         | `SYNTHESIS`                | All component numbers correct and present; engine didn't perform the trivial sum. **v2_unrecoverable_by_architecture** — VerdictSynthesizer performs no arithmetic. | unrecoverable (architecture) |
| 83 | Pacific Power (pilot customer)                          | Nexus Energy Systems (its own parent division)               | `RETRIEVAL_WRONG_ENTITY`   | Returned parent org via centrality instead of traversing PILOT_CUSTOMER edge.                                          | unrecoverable             |
| 91 | "Owns Export Control Policy per POL-009"                | "VP Trade Compliance is Robert Lee"                          | `SYNTHESIS`                | Right entity surfaced but wrong attribute returned. **v2_upstream_of_concern** — wrong fact selected before v2 invoked; fix is in QueryClassifier/fact-selection, not inference. | unrecoverable (upstream)  |
| 93 | LLZO (Li7La3Zr2O12, Al-doped)                           | "Proprietary solid electrolyte" (generic)                    | `EXTRACTION_MISSED`        | Specific material composition not extracted from technical specs.                                                      | unrecoverable             |

## Distribution

| Mode                       | Count | %    |
|----------------------------|-------|------|
| `RETRIEVAL_VOID`           | 7     | 30%  |
| `RETRIEVAL_WRONG_ENTITY`   | 5     | 22%  |
| `EXTRACTION_MISSED`        | 3     | 13%  |
| `CROSS_DOCUMENT`           | 3     | 13%  |
| `SYNTHESIS`                | 3     | 13%  |
| `DATE_TEMPORAL`            | 2     | 9%   |
| `CONFIDENCE_MISCALIBRATED` | **0** | **0%** |
| `OTHER`                    | 0     | 0%   |

## Read-out

- **Zero `CONFIDENCE_MISCALIBRATED` failures.** v2's stated target class is empty in the Nexus failure profile.
- **Retrieval substrate is 52% of failures** (`RETRIEVAL_VOID` 30% + `RETRIEVAL_WRONG_ENTITY` 22%). The substrate is the binding constraint by a wide margin.
- **Realistic v2-recoverable ceiling: +1** (Q24 only, conditionally — depends on whether v2's planner extracts the "Phase 1" qualifier as a Condition and whether the Gatherer surfaces the qualified-vs-unqualified evidence cleanly).
- **Two `SYNTHESIS` cases are architecturally out of scope for v2:**
  - Q79 (`v2_unrecoverable_by_architecture`): VerdictSynthesizer performs no arithmetic; summing four divisional targets requires a compute layer v2 doesn't have.
  - Q91 (`v2_upstream_of_concern`): the wrong fact was selected before v2 would be invoked. v2 evaluates `Fact(s, r, t)` correctly even when `(s, r, t)` is the wrong fact. Fix lives in QueryClassifier/fact-selection.
- **Task 2 motivation:** the taxonomy tells us v2's theoretical maximum contribution is +1. It does **not** tell us whether v2 introduces regressions on the 77 v1 currently passes. Given v2's known behaviors (MetaEvaluator hallucinating falsifiers, 50-minute timeouts, runaway adversarial loops), v2 may be net negative at scale. We need that empirically before parking.

---

## Baseline drift addendum (2026-05-09)

**Diff:** `claudecode_nexus_industries_20260509_065714.json` (77/100, 23 fails)
vs `claudecode_nexus_industries_20260509_073740.json` (74/100, 26 fails) —
same vault, same questions, same git SHA, two consecutive runs ~7 minutes apart
with the test-LLM cache cleared between them.

**Result:** the 23-fail set is a strict subset of the 26-fail set. Three
additional questions flipped PASS → FAIL; zero questions flipped FAIL → PASS.

| Q  | Expected                                                | 74-run actual (compressed)                                                | Mode                       | Justification                                                                                                                                                          | v2 prognosis              |
|----|---------------------------------------------------------|---------------------------------------------------------------------------|----------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------|
| 15 | Dr. Victoria Chen (CEO)                                 | "Does not specify who Michael Chang reports to. Only indicates CFO."      | `RETRIEVAL_VOID`           | The REPORTS_TO edge from Michael Chang → Victoria Chen was surfaced in the 77-run and missed in the 74-run. Same retrieval substrate, different chunk-rank coin flip.   | unrecoverable             |
| 29 | Exec Leadership Team roster                             | Returned wrong CFO ("Robert Martinez") and wrong CTO ("Dr. Aisha Patel")  | `RETRIEVAL_WRONG_ENTITY`   | Surfaced a stale or hallucinated leadership roster instead of the canonical one. Centrality-bias / wrong-entity class — same shape as Q17/Q48/Q71/Q83.                  | unrecoverable             |
| 73 | 1,200 net new positions                                 | "Does not specify the exact number of new employees… provides workforce metrics" | `EXTRACTION_MISSED`        | The "1,200 net new positions" figure lives in a strategy/HR doc; the headcount value isn't in the graph as a property and the chunk wasn't retrieved.                  | unrecoverable             |

**Updated distribution (26 failures, used by Task 3 matrix):**

| Mode                       | Count | %    |
|----------------------------|-------|------|
| `RETRIEVAL_VOID`           | 8     | 31%  |
| `RETRIEVAL_WRONG_ENTITY`   | 6     | 23%  |
| `EXTRACTION_MISSED`        | 4     | 15%  |
| `CROSS_DOCUMENT`           | 3     | 12%  |
| `SYNTHESIS`                | 3     | 12%  |
| `DATE_TEMPORAL`            | 2     | 8%   |
| `CONFIDENCE_MISCALIBRATED` | **0** | **0%** |

**Re-stated read-out (over 26 failures, no qualitative change):**

- `CONFIDENCE_MISCALIBRATED` is still empty. v2's stated target class is unrepresented in either baseline.
- Retrieval substrate now accounts for 54% of failures (`RETRIEVAL_VOID` 31% + `RETRIEVAL_WRONG_ENTITY` 23%) — within rounding of the 23-failure read.
- Realistic v2-recoverable ceiling is unchanged at +1 (Q24 only). None of Q15/Q29/Q73 fall in the v2-conditionally-recoverable bucket: Q15 and Q73 are pure retrieval misses that never reach v2; Q29 is a wrong-entity case where v2 would either endorse the wrong fact or return UNDERSUPPORTED, neither of which scores.
- The drift itself is decision-relevant: a v1 substrate that flips three questions across consecutive identical runs has roughly ±3-question variance independent of any change to v2. Any v2 score within ±3 of v1 must be read as variance, not signal.
