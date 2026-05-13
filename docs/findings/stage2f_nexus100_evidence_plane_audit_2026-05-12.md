# Stage 2F — Nexus 100 Evidence-Plane Classification Audit

**Date:** 2026-05-12
**Scope:** Read-only classification of `test_questions/nexus_100q.json` by evidence plane. **No code, no DB, no extraction, no scoring re-run, no ontology change, no replit.md edit.**

---

## 1. Method

Each of the 100 Nexus questions was classified into a **primary** evidence plane (and optional **secondary**) using the spec's taxonomy: IDENTITY / RELATIONAL / PROPERTY / TEMPORAL / SEMANTIC / PROCEDURAL / AGGREGATE / MIXED.

Classification is deterministic regex over the question wording + gold-answer shape (e.g., a numeric+unit gold answer reinforces PROPERTY; a year in the gold answer reinforces TEMPORAL). Priority order when multiple signals match: PROPERTY > TEMPORAL > AGGREGATE > RELATIONAL > PROCEDURAL > SEMANTIC > IDENTITY (most-structured first).

**Inputs cross-referenced:**
- Stage 1J: `test_results/stage1j_questions_only/stage1j_qonly_ecd2f1c2_progress.jsonl` (n=100)
- Stage 2C tree-off: `test_results/stage2c_tree_off/s1j_treeOff_ecd2f1c2_progress.jsonl` (n=100)
- Stage 2D direct: `test_results/stage2d_direct/s2d_treeOff_fbOn_ecd2f1c2_progress.jsonl` (n=100)
- Stage 2E-1 HTTP parity: `test_results/stage2e1_http_parity/s2e1_focused_ecd2f1c2_progress.jsonl` (n=100, latest dedup)
- Legacy 176a4fb2: `test_results/claudecode_nexus_industries_176a4fb2_progress.jsonl` (n=50, partial)

Per-question table: **`test_results/stage2f_evidence_plane/per_question.csv`** (q, question, gold, all 5 pass columns, `s2e1_src`, primary, secondary, why, current_repr, suggested_repr).
Summary stats: **`test_results/stage2f_evidence_plane/SUMMARY.json`**.

---

## 2. Distribution by primary evidence plane

| Plane | Count | Share |
|---|---:|---:|
| **PROPERTY** | **35** | 35% |
| RELATIONAL | 23 | 23% |
| SEMANTIC | 21 | 21% |
| TEMPORAL | 16 | 16% |
| AGGREGATE | 4 | 4% |
| IDENTITY | 1 | 1% |
| PROCEDURAL | 0 | 0% |

**Including secondary plane:**
- PROPERTY (incl. secondary): 35 (no extra — every PROPERTY case is primary)
- TEMPORAL (incl. secondary): 18
- Most common pair: PROPERTY+AGGREGATE = 9 (totals/sums of metrics)
- 23 RELATIONAL, 21 SEMANTIC, 13 TEMPORAL questions are single-plane (no secondary signal)

---

## 3. Pass rates by plane (across runs)

| Plane | n | Stage 1J | Stage 2C | Stage 2D | **Stage 2E-1** | Legacy (n=50) |
|---|---:|---:|---:|---:|---:|---:|
| PROPERTY | 35 | 14/35 (40%) | 16/35 (46%) | 20/35 (57%) | **19/35 (54%)** | 20/24 (83%) |
| RELATIONAL | 23 | 12/23 (52%) | 14/23 (61%) | 14/23 (61%) | **14/23 (61%)** | 7/12 (58%) |
| SEMANTIC | 21 | 15/21 (71%) | 15/21 (71%) | 15/21 (71%) | **15/21 (71%)** | 9/10 (90%) |
| TEMPORAL | 16 | 7/16 (44%) | 7/16 (44%) | 8/16 (50%) | **8/16 (50%)** | 6/9 (67%) |
| AGGREGATE | 4 | 1/4 | 2/4 | 2/4 | **2/4** | 1/2 |
| IDENTITY | 1 | 1/1 | 1/1 | 1/1 | **1/1** | 1/1 |

**Observations:**
1. **PROPERTY is both the largest plane AND the worst-performing** (54% pass on Stage 2E-1). Stage 2D's DocEv fallback added +6 vs Stage 2C — most of the recent gain came from PROPERTY questions where the KG had a gap.
2. **TEMPORAL is the most under-served plane relative to legacy** (50% vs legacy 67%). The 176a4fb2 vault clearly had something — likely TEMPORAL_ASSERTIONS or date-bearing chunks the current vault is missing.
3. **SEMANTIC is already strong (71%)** — DocEv chunk grounding handles narrative/strategic claims well; legacy's 90% suggests there's still ~4 points of headroom.
4. **RELATIONAL plateau at 61%** — relational graph extraction is mature but missing edges (per Stage 2E-1 audit, several confident-wrong-CEO/CFO cases live here).
5. **AGGREGATE is tiny (n=4)** — 50% pass rate; not worth its own pipeline.
6. **PROCEDURAL is empty** — Nexus benchmark does not test workflow/policy questions. Building a procedural graph is **not** justified by this benchmark.

---

## 4. Where the 50/100 gap lives

Stage 1J failed 50 questions (50/100 baseline). Their plane distribution:

| Plane | Stage 1J failures | Share of 50-question gap |
|---|---:|---:|
| **PROPERTY** | **21** | **42%** |
| RELATIONAL | 11 | 22% |
| TEMPORAL | 9 | 18% |
| SEMANTIC | 6 | 12% |
| AGGREGATE | 3 | 6% |
| IDENTITY | 0 | 0% |

**42% of the original gap is PROPERTY.** Stages 2C → 2E-1 closed +9 of those. Of the remaining 41 failures (Stage 2E-1):

| Plane | Stage 2E-1 failures | % of remaining gap |
|---|---:|---:|
| PROPERTY | 16 | 39% |
| RELATIONAL | 9 | 22% |
| TEMPORAL | 8 | 20% |
| SEMANTIC | 6 | 15% |
| AGGREGATE | 2 | 5% |

**PROPERTY (39%) + TEMPORAL (20%) = 59% of remaining gap = 24 questions = +24 score ceiling if both were solved.**

Cross-check with Stage 2E-1 attribute-failure audit (`ATTRIBUTE_FAILURES.csv`, n=19): 17 of those 19 are confident-wrong PROPERTY/TEMPORAL scalars where the agent returned a wrong KG fact (Bucket E). This is consistent.

---

## 5. Specific questions answered

| # | Question | Answer |
|---|---|---|
| 1 | Property/spec/metric/value questions | **35** primary; 35 incl. secondary |
| 2 | Relational | **23** primary |
| 3 | Temporal | **16** primary; 18 incl. secondary |
| 4 | Semantic | **21** primary |
| 5 | Require aggregation | **4** primary |
| 6 | Solved by DOCUMENT_EVIDENCE alone (Stage 2E-1 evidence) | **7 passed via DocEv** out of 9 attempted; estimated **15-22 plausible** if Bucket E gate didn't short-circuit |
| 7 | Require structured property or temporal extraction | **51** (35 PROPERTY + 16 TEMPORAL) |
| 8 | Does five-evidence-plane architecture fit this benchmark? | **Partially.** PROPERTY + TEMPORAL + RELATIONAL + SEMANTIC = 95% of questions. PROCEDURAL (0) and IDENTITY (1) and AGGREGATE (4) do not justify dedicated planes for this benchmark. |

---

## 6. Current vs suggested representation

Per per_question.csv (`current_repr` column derived from latest answer_source):

| Current representation | Count |
|---|---:|
| TRUSTED relational graph (any-stage pass) | ~73 |
| document chunks only (passed via DocEv) | 7 |
| missing (no run passed) | ~20 |

**The gap** = the ~24 questions in PROPERTY (16) + TEMPORAL (8) buckets that the system either gets wrong from the relational graph or cannot ground from chunks.

**Suggested representation** (per spec's mapping):

| Plane | Count | Suggested representation |
|---|---:|---|
| PROPERTY | 35 | property graph (typed attribute facts with values, units, time qualifiers) |
| RELATIONAL | 23 | relational graph (already exists, mostly works) |
| SEMANTIC | 21 | semantic evidence (DocEv chunk-grounded claims) |
| TEMPORAL | 16 | temporal graph (event facts with dates, before/after) |
| AGGREGATE | 4 | aggregate/composite handler (lightweight; could stack on property graph) |
| IDENTITY | 1 | identity layer (trivial) |
| PROCEDURAL | 0 | not needed for this benchmark |

---

## 7. Decision

**Recommendation: F — Mixed plan with sequence.**

The benchmark cleanly justifies investment in **two** new planes (property + temporal) but not all five. The sequence:

### Step 1 (highest leverage): **Property Graph MVP** — option A
- Targets **35 questions, 16 of which currently fail** in Stage 2E-1.
- Direct addressable upside: **+10 to +14 questions** (the Bucket E confident-wrong scalars: revenue, qubits, capacity, density, backlog, etc.).
- Implementation cost: medium. Schema = `(entity_id, attribute_type, value, unit, time_qualifier, evidence_chunk_id, confidence)`. Most data already extracted as relationships of type `HAS_*` — just needs typing + value parsing + a property-aware ContextBundle.
- Reuses existing extraction pipeline (Sonnet relation extractor already emits HAS_REVENUE / HAS_CAPACITY / etc.). The plane is a **reorganization + value parser**, not a new ontology.

### Step 2: **Temporal Graph MVP** — option B
- Targets **16 questions, 8 of which currently fail.**
- Direct addressable upside: **+5 to +7 questions** (when X was appointed/launched/achieved/planned).
- Implementation cost: medium-high. Needs date normalization, before/after queries, validity intervals.
- **Defer behind Step 1.** Smaller absolute upside; partly covered by DocEv when chunks contain the date.

### Step 3 (deferred — calibrate first): **Cross-graph ContextBundle synthesis** — option E
- Required only once Steps 1 + 2 ship. Until then, the existing ContextBundle handles the bulk of single-plane lookups well enough.

### Why NOT the other options first
- **C (improve relational extraction)** — RELATIONAL is at 61%, gap of 9 questions. Most are confident-wrong (Bucket E) not missing-edge. Re-extraction won't fix; would need a different correctness mechanism (e.g., the Stage 2E-2 KG-Conflict Shadow Mode already in proposal).
- **D (improve DocEv / semantic)** — SEMANTIC is at 71%, gap of 6 questions. Diminishing returns; Stage 2E-1 already wired DocEv.
- **B alone (temporal first)** — smaller upside than property and partly already grounded by chunks.
- **A alone, no sequence** — leaves 5-7 temporal questions stranded.

### Score model
- Stage 2E-1 today: **59/100**
- After Step 1 (Property Graph MVP): **~69-73/100**
- After Step 2 (Temporal Graph MVP): **~74-80/100**
- Practical ceiling without architectural change to relational confidence: ~80/100. Closing the remaining ~20 requires the Stage 2E-2 KG-Conflict Shadow Mode (separate workstream) to address Bucket E in the RELATIONAL plane.

---

## 8. Caveats

- **Heuristic classifier**, not LLM-validated. Spot-checked ~15 questions; saw 1-2 plausible alternative classifications (e.g., Q40 "total company backlog" → PROPERTY/AGGREGATE coin flip; classified PROPERTY+AGGREGATE here, gold answer is a single scalar so PROPERTY is defensible). Total category counts robust to ±2 per plane.
- **Legacy 176a4fb2 only covered 50 questions** — pass rates for that column are partial; comparisons should be qualitative.
- **PROCEDURAL = 0** is real for Nexus, not a classifier blind spot. Manus Orion or other corpora may differ; do not generalize this finding to other benchmarks.
- This audit **does not** quantify how many of the 16 failing PROPERTY questions are "fixable by a property graph" vs "fixable only with re-extraction." Stage 2E-2 shadow-mode data would settle this; recommend running 2E-2 in parallel with Property Graph MVP design.

---

## 9. Stop condition met

Per spec: "Stop after the evidence-plane classification report. Wait for sign-off before any implementation plan."

**No code edits, no DB mutations, no extraction, no scoring re-run, no ontology changes, no prompt changes, no v2/T01-T14 work, no replit.md edits.** Awaiting sign-off on Decision F (Step 1 = Property Graph MVP, Step 2 = Temporal Graph MVP) before any implementation begins.

## 10. Artifacts

- `test_results/stage2f_evidence_plane/per_question.csv` — 100-row classification table (q, question, gold, s1j/s2c/s2d/s2e1/legacy pass, s2e1_src, primary, secondary, why, current_repr, suggested_repr).
- `test_results/stage2f_evidence_plane/SUMMARY.json` — counts, plane pass rates, pair counts, specific-answer numerics, Stage 1J/2E-1 failure breakdown.
