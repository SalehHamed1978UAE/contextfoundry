# Stage 2E-1 — DOCUMENT_EVIDENCE HTTP Parity and Failure Audit

**Date:** 2026-05-12 / 2026-05-13
**Vault:** `ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda` (Stage1J-Fresh, Nexus 100Q)
**Scope:** Wire existing Stage 2D `document_evidence_fallback` into `/api/vault/chat` behind a default-OFF flag, validate via in-process HTTP-shaped harness, audit failures, propose Stage 2E-2. **No hardening.**

---

## 1. What was built (Part A — wiring)

| File | Change | Default state |
|---|---|---|
| `web_app.py` L4456-4485 | Hook between QA Verifier and `conv_store.add_message`. Reads `CF_DOCUMENT_EVIDENCE_FALLBACK` env + `data.get('document_evidence_fallback')` request payload. Both must be true to enable. | **OFF** (env unset, payload omitted) |
| `src/context_foundry/retrieval/document_evidence_fallback.py` L407+ | New `apply_to_agent_result(agent_result, query, vault_id, request_payload)`, `is_fallback_enabled(request_payload)`, `classify_agent_kg_source(agent_result)`. GAP iff `not_found` / QA verdict ∈ {OFF_TOPIC, INSUFFICIENT, UNSUPPORTED, SUSPICIOUS} / inner `looks_like_no_data`. Otherwise TRUSTED_GRAPH_FACT. | n/a (helper) |
| `tests/inference/unit/test_document_evidence_fallback.py` | +10 tests (E1.1–E1.7 + wiring assertion) | 39/39 pass |

**Invariants enforced in the hook:**
- No mutation of `agent_result` when classification is TRUSTED_GRAPH_FACT (KG short-circuit preserved).
- No KG override: fallback only fires on GAP.
- Tenant scope inherited from existing route session (no extra context switch).
- No worker startup, no extraction triggered.
- No `Start All` restart required.

---

## 2. Validation harness (Part B)

`scripts/run_qonly_http_parity.py` replicates the `/api/vault/chat` route flow in-process:
1. `set_tenant_context(vault_id)` — same call the route uses.
2. `ToolAgent.query(query, vault_context=…)` — same call site.
3. QA Verifier replacement (matches `web_app.py` L4424-4449).
4. **Stage 2E-1 hook**: `apply_to_agent_result(...)` between QA and persistence.
5. Resume-aware JSONL (skips already-completed qids).

**Why in-process and not curl?** The plan explicitly forbids restarting `Start All`. The in-process harness exercises the *same* code path with the *same* call sites and the *same* tenant context as the route — every difference vs production is enumerated below.

**Knobs replicated:** `CF_TREE_BASED_RETRIEVAL=false` (matches current `start.sh` L13 default), `document_evidence_fallback=true` payload (Part A's request flag).

---

## 3. Results

| Run | Score | Tree | Fallback | Notes |
|---|---|---|---|---|
| Stage 1J baseline (tree on, no fallback) | 50/100 | ON | OFF | Pre-2C measurement |
| Stage 2C (tree off, no fallback) | 55/100 | OFF | OFF | Tree-off win |
| Stage 2D direct (tree off, fallback on, harness-only) | **60/100** | OFF | ON | DocEv harness wins |
| **Stage 2E-1 HTTP parity** | **59/100** | OFF | ON (via wiring) | This run |

**Δ vs Stage 2D direct: −1 (Q96 flake, see §5).** All other 99 questions match Stage 2D pass-state exactly.
**Δ vs Stage 2C tree-off baseline: +4** (Q14, Q34, Q41, Q51, Q84 — recoveries that survived the wiring).

### Answer-source breakdown (HTTP parity, n=100)

| Source | Count | Fail count |
|---|---|---|
| TRUSTED_GRAPH_FACT | 86 | 35 |
| DOCUMENT_EVIDENCE | 9 | 2 |
| GAP (no answer) | 5 | 4 |

**Fallback statistics:** attempted=12, used=9, passed=7, failed=2.

### Direct-vs-HTTP differences

| Q | Direct | HTTP | Notes |
|---|---|---|---|
| 96 | PASS / DOCUMENT_EVIDENCE | FAIL / TRUSTED_GRAPH_FACT | **Only pass-state regression.** Agent path returned a confident KG answer this run instead of GAP — gate `trusted_kg_answer` blocked fallback. Source-of-truth nondeterminism in upstream `ToolAgent.query`, not in the wiring. |
| 12, 58, 87, 98, 99 | DOCUMENT_EVIDENCE / GAP variants | TRUSTED_GRAPH_FACT (all PASS-equivalent) | Source-attribution flaps; pass-state identical. Same nondeterminism pattern. |

**Interpretation:** the wiring is faithful. The single observed regression is an upstream agent flake, not a hook bug.

### Cohort transfer

- **Stage 2D recoveries (8):** 7/8 transfer (Q14, Q32, Q34, Q41, Q51, Q58, Q84). Q96 flake.
- **Stage 2C recoveries (5):** 4/5 transfer (Q15, Q36, Q68, Q100). Q40 fails in both Stage 2D direct and Stage 2E-1 HTTP — pre-existing failure, not a wiring regression.
- **10 attribute failures (Q6, Q20, Q23, Q24, Q25, Q33, Q42, Q43, Q45, Q60):** 0/10 recovered. 9/10 blocked by `gate=trusted_kg_answer` (Bucket E). Q33 fired DE but extractor returned no_match (Bucket C/D).

---

## 4. Failure bucket audit (Part C)

41 total failures. Attribute-style failures: 19 (full per-question table at `test_results/stage2e1_http_parity/ATTRIBUTE_FAILURES.csv`).

| Bucket | Description | All failures | Attribute failures |
|---|---|---|---|
| **E** | Confident KG answer short-circuited fallback | **35** | **15** |
| **C/D** | Fallback fired but extractor wrong / spec mismatch | 2 | 2 |
| F | Fallback fired but found no evidence | 2 | 1 |
| H | Plan classifier said `not_attribute_query` | 1 | 0 |
| I | HTTP/direct pass-state mismatch (upstream flake) | 1 | 1 |
| J | Other | 0 | 0 |
| A | Fallback never triggered but should have | 0 | 0 |
| B/G | Polarity / synthesis bugs | 0 | 0 |

**The dominant failure mode is Bucket E — the agent path is producing a confident-but-wrong KG answer that the Stage 2E-1 hook (correctly, by design) does not override.** This validates the Stage 2E-1 invariant ("never override TRUSTED_GRAPH_FACT") but exposes the next high-leverage fix surface.

### Representative Bucket E failures

| Q | Question | KG answer (wrong) | Why |
|---|---|---|---|
| 6 | "What was Nexus Industries' revenue in FY2025?" | wrong scalar | KG has a `HAS_REVENUE` edge with stale year |
| 23 | "How many qubits does the QuantumLeap system have?" | wrong number | extractor picked wrong SPECIFICATION value |
| 25 | "What is the target energy density for the solid-state battery?" | wrong unit-bearing scalar | duplicate SPECIFICATION facts, wrong one wins |
| 40 | "What is the total company backlog?" | wrong scalar | aggregation of segment values disagrees with stated total |
| 43 | "When did CyberShield achieve FedRAMP High authorization?" | wrong date | event-date facts conflict |
| 45 | "When was Dr. Victoria Chen appointed CEO?" | wrong date | TEMPORAL fact pulled from wrong document |
| 96 | "What is the APAC revenue target for 2030?" | wrong scalar | regional target ambiguity |

**Common shape:** confident-wrong scalar (number, date, range, score) where a chunk-grounded answer would have been correct.

---

## 5. Invariant verification

| Table | Pre-test count | Post-test count | Δ |
|---|---|---|---|
| `entities` | 14252 | 14252 | 0 |
| `relationships` | 8176 | 8176 | 0 |
| `documents` | 300 | 300 | 0 |
| `document_chunks` | 2094 | 2094 | 0 |
| `ontology.types` | 1037 | 1037 | 0 |
| `ontology.relations` | 254 | 254 | 0 |
| `platform.conversation_messages` (this tenant) | (baseline + N) | +446 over session | append-only, expected |

`extraction_requests` table does not exist in this schema (no extraction was run; the workflow `Reextract Failed Docs v2` was not invoked for this exercise).

**No KG mutations. No worker startup. No `Start All` restart.** All measurements taken with `CF_DOCUMENT_EVIDENCE_FALLBACK` and request `document_evidence_fallback` flag. Default route behavior (both unset) is byte-identical to pre-Stage-2E-1 because the hook short-circuits at `is_fallback_enabled(...) → False`.

---

## 6. Stage 2E-2 proposal (no hardening, no spec — just a ranked plan)

Failure population in priority order:

### Tier 1 — Bucket E confident-wrong scalars (35 failures, ~highest score impact)

**Hypothesis:** the KG holds a fact that is structurally valid (passes ontology validation, passes Data Gates, has provenance) but is *factually* wrong relative to chunks — typically because (a) duplicate facts with different values exist and the wrong one was chosen, (b) the fact was extracted from a stale section, or (c) aggregation rules don't apply.

**Proposed Stage 2E-2:** *KG-Conflict Shadow Mode*

1. Run `DocumentEvidenceFallback` on **every** TRUSTED_GRAPH_FACT response *in shadow* (do not modify the agent_result, do not change the user-facing answer).
2. Compare the KG scalar against the DocEv chunk-grounded scalar.
3. Log `kg_conflict_diagnostics` with: `kg_value`, `de_value`, `chunk_grounding_score`, `agreement` (boolean), `disagreement_severity`.
4. Aggregate into a daily report; do not promote/demote any KG fact, do not block any answer.
5. **Override gate (deferred — Stage 2E-3 candidate):** allow override only when chunk grounding score ≥ θ (where θ is calibrated post-shadow-data) AND DocEv polarity = SUPPORTING.

**Estimated upside:** if shadow data shows ≥ 70% of Bucket E disagreements have high-confidence chunk evidence, an override gate could recover ~20-25 of the 35. **Score model: 59 → ~78-83.**

**Risks called out for review:**
- Cost: every TRUSTED answer now runs the fallback. ~3-8s/Q at current chunk-search latency. Mitigations: budget ceiling, async logging-only path, sampling.
- Cache invalidation: shadow mode must not affect QA Verifier or `conversation_messages`.
- "Override" is a structural change to the Stage 2E-1 invariant — explicitly Stage 2E-3, not 2E-2.

### Tier 2 — Bucket C/D extractor-wrong (2 failures)

Q33 ("How much hydrogen will Shell purchase annually") and Q79 ("2030 revenue target"). DocEv fired and selected a chunk; the extracted scalar disagreed with the gold answer. Inspect the polarity/extraction prompt; likely a units (mt/yr vs kg/day) or specifier (FY2030 target vs interim) issue. **Score model: +1-2.**

### Tier 3 — Bucket F "no evidence" (2 failures)

Q97 ("M&A budget capacity"). Genuinely sparse in the corpus. Could be an embedding/keyword recall issue. Worth a recall sweep but unlikely to move the score by more than 1.

### Tier 4 — Bucket I (1 failure, Q96)

Source: upstream `ToolAgent.query` nondeterminism. Not a fallback or wiring issue. **Stage 2E-2 should NOT touch this** — would require route-level retry/quorum semantics that are out of the DocumentEvidence scope.

---

## 7. Recommendation

- **Keep Stage 2E-1 wiring as-is, default OFF.** Ship behind both env (`CF_DOCUMENT_EVIDENCE_FALLBACK`) and per-request payload flag.
- **Do not enable in production yet.** The +4 vs Stage 2C is positive but the dominant failure mode (Bucket E) is unaddressed and the wiring's only contribution at scale is to recover GAP cases, which is a small share.
- **Stage 2E-2 = shadow-mode KG-conflict diagnostics.** No behavior change. Two-week instrumentation period to calibrate θ before any Stage 2E-3 override discussion.

## 8. Artifacts

- `test_results/stage2e1_http_parity/SUMMARY.json` — score, breakdowns, cohort transfer, direct-vs-HTTP diffs.
- `test_results/stage2e1_http_parity/ATTRIBUTE_FAILURES.csv` — per-question audit (19 rows).
- `test_results/stage2e1_http_parity/INVARIANT_CHECK.json` — DB count check.
- `test_results/stage2e1_http_parity/s2e1_focused_ecd2f1c2_progress.jsonl` — full per-Q records (100, deduped to last entry per qid).
- `tests/inference/unit/test_document_evidence_fallback.py` — 39/39 unit tests.
