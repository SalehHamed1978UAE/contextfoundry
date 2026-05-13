# Stage 2C — Score Recovery Isolation and Capability Restoration

**Date:** 2026-05-12
**Scope:** Read-only score-recovery isolation per `docs/inbox/Stage 2C — Score Recovery Isolation and Capability Restoration Plan.md`
**Vault under test:** `ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda` (Stage 1J clean)
**Question set:** `test_questions/nexus_100q.json`

---

## Executive summary

1. **Tree retrieval is net-positive to disable for Stage 1J.** Re-running the same 100 questions against the same vault with `tree_based_retrieval=False` per request scored **55/100 vs 50/100 with tree=True (+5, 0 regressions)**. 5 recovered, 0 lost. Mutation check post-run: clean. The change is request-scoped only — `start.sh` was not modified.
2. **Disabling tree retrieval alone does not close the gap to legacy 76/100.** It captures only ~5 of the 26-point delta. The remaining ~21-point gap is dominated by attribute/spec/date/metric facts that the current ontology-constrained extractor cannot lift into the KG.
3. **The legacy parity test (Step 4) was not run** because the plan's stop-trigger applies: `176a4fb2-0bb4-4da3-9068-0e26268fca71` has 0 rows in `documents` table (501 chunks with orphaned `document_id`s). Its prior 76/100 figure (read 2026-05-12 earlier in session) is cited but the JSONL is being overwritten in real time by the running `Test: ClaudeCode Nexus` workflow, so it is no longer a stable artifact.
4. **No production code, ontology, prompts, `start.sh`, or KG facts were mutated.** The thin runner only used the existing per-request `tree_based_retrieval` override (already supported by `ToolAgent.process` L922→L1052). *Caveat:* `/api/vault/chat` does write conversation history to `platform.conversation_messages` via `ConversationStore.add_message()` — this is a normal append-only side-effect of using the live API surface and is **not** a KG/ontology/document mutation. The mutation check below is scoped to `entities`, `relationships`, `documents`, and `document_chunks` and is clean for those tables.
5. **Ranked recovery plan (top 3):** (a) gate tree retrieval narrowly or default off, (b) restore attribute-fact coverage via DOCUMENT_EVIDENCE chunk-fallback for attribute questions (no ontology mutation required), (c) canonicalize the relation-extractor verbs (`HOLDS_ROLE` / `FORMERLY_HELD` → `HOLDS_POSITION`) at staging time. Stage 2 implementation/default-activation remains blocked by answer quality.

---

## Step 1 — Current lever audit (read-only)

| # | Lever | Code location | Current value | Observable evidence |
|---|---|---|---|---|
| 1 | `CF_TREE_BASED_RETRIEVAL` env flag | `start.sh` L13 | `true` | `export CF_TREE_BASED_RETRIEVAL=true` |
| 1a | Per-request override | `ToolAgent.process(... tree_based_retrieval=...)` L922, threaded to `QueryPipeline` L1052 → `RetrievalRouter.route` L2032-2082 | supported | thin runner consumes it, `Test: ClaudeCode Nexus` does not |
| 1b | Hybrid gate inside router | `retrieval_router.py` L2041 | `is_tree_based_retrieval_enabled() AND _is_graph_hopping_query()` AND tree-confidence == `'high'` (boosted to `'high'` on `role_match=True` BFS results in `tree_retriever.py` L214-240, L674-681) | per replit.md tree path "rarely reaches 'high'" on the failing graph-hop set |
| 2 | `entity_extractor.use_ontology_schema` default | `src/context_foundry/extraction/entity_extractor.py` L211 | `True` (since commit `2ab739bc`, "Phase 3") | extractor builds prompt only from ACTIVE rows in `ontology.types` (L260, L925) |
| 3 | OntologyCentricPipeline prompt/ontology constraints | `src/context_foundry/ontology/shadow_adapter.py` (`is_constrained_mode`) | CONSTRAINED mode runs only constrained extraction; LEGACY default in env but `use_ontology_schema=True` keeps the per-extractor path constrained even under LEGACY env | active per L260/L925 in `entity_extractor.py` |
| 4 | `GardenerConfig.require_verification_for_promotion` | `src/context_foundry/agents/gardener.py` L120 | **`False`** (since commit `4fb04dab`, 2026-05-08) | git blame: was `True` in `25c4d101`, flipped in `4fb04dab` "blocked 100% of promotions when VerificationWorker only verifies a tiny fraction of facts" |
| 5 | Relation-extractor prompt rule for role verbs | `src/context_foundry/extraction/relation_extractor.py` (rule #8 in `extract_with_ontology`) | Emits `HOLDS_ROLE` / `FORMERLY_HELD` | DB confirms: Stage 1J vault has **0 `HOLDS_ROLE`, 0 `FORMERLY_HELD`** despite the prompt asking for them. Only canonical `HOLDS_POSITION` survived (272 rows). |
| 6a | `ontology.types` coverage — entity types | `ontology.types` table | Layer 1 ACTIVE = 24 (incl. DATE, EVENT, FACILITY, LOCATION, MONEY, ORGANIZATION, PERSON, PROCESS, SUPPLIER, TECHNOLOGY); Layer 2 ACTIVE = 1006 | Layer 2 contains `SPECIFICATION`, `PARAMETER`, `METRIC`, `VALUE`, `CERTIFICATION` but Layer 2 **does not** contain `BUDGET`, `MILESTONE`, or most `HAS_*` / `MEETS_*` / `OCCURRED_*` relations. **Note:** DATE and EVENT are present at layer 1 — they are *available* to the ontology-constrained extractor; the limitation is on the relation-types side (no `HAS_DATE`/`OCCURRED_ON`) and on the absence of `BUDGET`/`MILESTONE`/`SPEC-VALUE` linkers, which together prevent attribute facts from being assembled into queryable graph rows even when the seed entity types exist. |
| 6b | `ontology.types` coverage — relation types | same | Layer 2 ACTIVE intersected with the canonical set tested = **{`REPORTS_TO`}** only | Tested set: `HOLDS_POSITION, HOLDS_ROLE, FORMERLY_HELD, REPORTS_TO, LEADS, MANAGES, CUSTOMER_OF, SUPPLIER_OF, SUPPLIES, PARTNER_OF, LOCATED_AT, LOCATED_IN, OWNS, PART_OF, PRODUCES, MEMBER_OF, BOARD_MEMBER_OF, AFFILIATED_WITH, INVESTED_IN, WORKS_AT, USES_MATERIAL, FUNDED_BY, USES, RELATED_TO, OWNED_BY, FOCUSES_ON, WORKS_FOR, AFFECTS, HAS_SPEC, MEETS_SPEC, OCCURRED_ON, HAS_DATE, HAS_VALUE, HAS_CERTIFICATION, HAS_METRIC` — only `REPORTS_TO` matched. The 11 relation types currently in TRUSTED were promoted by an earlier gardener pass before strict ontology enforcement. |
| 6c | `ontology.relations` separate table | `public.ontology_relationship_types` | **0 rows** | empty — not the validation source |
| 7a | Is `PrecedencePipeline` called by `/api/vault/chat`? | `src/context_foundry/pipeline/precedence_pipeline.py` | **No.** Only callers: itself (L68, L206), `core.py` L28 import not exercised at request time, `pipeline/__init__.py` exports | live request flow is `ToolAgent` → `QueryPipeline` |
| 7b | Is `SymbolicOverrideEngine` called by `/api/vault/chat`? | `src/context_foundry/memory/symbolic_override.py` | **No.** Only consumers: `precedence_pipeline.py` (also unwired) and `memory/__init__.py` | dead in production |
| 7c | Is `CoherenceChecker` shadow-only or blocking? | `src/context_foundry/agents/tool_agent.py` L1143-1186 (direct-answer path) and L1443-1452 (tool-loop path) | **Mixed.** Tool-loop path is **shadow-only** (`validate(...)` + `log_result(...)`, no response change). Direct-answer path is **response-modifying for LOW/MEDIUM confidence**: appends a `**Confidence: Low/Medium**` + `**Why:** ...` + `**Please verify...**` caveat block to the answer and adds `coherence_confidence` / `coherence_score` / `coherence_issues` to the response extra fields. Does not reject answers; never escalates to NOT_FOUND. | wired; partly advisory, partly user-visible caveat |
| 7d | Is `FailureAnalyzer` / `TargetedExtractor` / `ImprovementLoop` / `LearningOrchestrator` wired into the **request** flow? | `src/context_foundry/analysis/*.py`, `src/context_foundry/learning/*.py`, `src/context_foundry/api/learning_api.py` | **Not in `/api/vault/chat`.** `learning_api.py` exposes a separate Learning REST surface (out-of-band gap-detection / queue endpoints), and there is scheduler/queue plumbing for Learning. **None of these subsystems are invoked from the live `ToolAgent.process` → `QueryPipeline` request path** that answers questions. So they are wired for offline use but do not affect per-question scoring. | offline-only with respect to the benchmark; not "shelf-ware" globally |

---

## Step 2 — Historical / correlation audit

| Lever | Current value | When it changed | Old value (likely 176a-era) | Plausibly affects 34 regressions? | Predicted score impact (recovery) | Risk of restoring |
|---|---|---|---|---|---|---|
| `CF_TREE_BASED_RETRIEVAL` | `true` (since 2026-05-09 in current `start.sh`) | Multiple flips visible in git log; current value re-set 2026-05-09 | `false` (the build that scored ~76 used the legacy router) | Yes — proven by Step 3 result | **+5** (measured today) | Low — per-request override path is already tested; no `start.sh` change needed |
| `use_ontology_schema=True` (`entity_extractor.py` L211) | `True` | Commit `2ab739bc` "Phase 3: Add ontology-constrained extraction" | `False` (legacy unconstrained extractor) | Yes — narrows extracted vocabulary by removing DATE/BUDGET/MILESTONE/EVENT entity types from the prompt | Medium-high (~10–15) but only via re-extraction | Medium — relaxing constraint could re-introduce noisy types; safer to expand `ontology.types` than to flip the flag |
| `require_verification_for_promotion` | `False` | Commit `4fb04dab` 2026-05-08, "blocked 100% of promotions when VerificationWorker only verifies a tiny fraction of facts" | `True` (briefly, in commit `25c4d101`) — and effectively absent before | No — it gates promotion, not retrieval; flipping it back without scaling VerificationWorker would re-block 100% of promotions | 0 (and very negative if naively restored) | High — restoring causes total promotion stall. Do not restore until verification throughput is raised. |
| Relation prompt emitting `HOLDS_ROLE` / `FORMERLY_HELD` | Active | Recent (per replit.md "Phase 1 prompt change") | Old prompt emitted `HOLDS_POSITION` directly | Yes — affects role/succession queries (Q3, Q15, Q61, Q75 …) | Medium (~3–5) but only via re-extraction OR a canonicalizer at staging time | Low — canonicalize verbs at staging; no semantic loss |
| Missing attribute ontology vocabulary (DATE/BUDGET/MILESTONE/EVENT entity types; HAS_*/MEETS_*/OCCURRED_* relation types) | Missing | 176a-era unconstrained extraction emitted these incidentally as types named by the LLM | The 25+ entity-type vocabulary in 176a4fb2 is the artefact of that incidental emission | Yes — explains the 32 attribute-fact failures | High (~10–20) only if combined with re-extraction OR a chunk-fallback that quotes evidence rather than relying on graph facts | Medium for ontology expansion alone (no harm); High for re-extraction (expensive, mutates) |
| Unwired `PrecedencePipeline` / `SymbolicOverride` / chunk-fallback | Unwired | Built and shelved | n/a — `176a4fb2` did not have them either, so they are not the reason it scored higher | Could help only if they replace incorrect graph traversal with chunk-grounded answers | Low standalone; medium if used as the chunk-fallback mechanism for attribute questions | Medium — wiring is non-trivial and changes prod query path |

---

## Step 3 — Safe question-only retrieval-mode test (executed)

**Setup**
- Vault: `ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda`
- Driver: `scripts/run_qonly_thin.py --tree-based-retrieval false --batch 5..8`
- HTTP path: existing `/api/vault/chat` with `tree_based_retrieval=False` per request
- No DB writes, no extraction, no promotion, no service restart, no `start.sh` edit
- Concurrent workload: `Test: ClaudeCode Nexus` (against 176a4fb2) was running for the first half of this run — caused per-Q latency to ~13s; latency dropped to ~5–7s after it finished

**Result**

| | total | passed | failed | no_data | no_match |
|---|---:|---:|---:|---:|---:|
| Stage 1J — `tree=true` (prior baseline, same vault, same questions) | 100 | 50 | 50 | 20 | 30 |
| Stage 1J — `tree=false` (Stage 2C run) | **100** | **55** | 45 | 17 | 28 |
| **Net delta** | | **+5** | −5 | −3 | −2 |

**Recovered (5):** Q15, Q36, Q40, Q68, Q100 — sample:
- **Q15** "Who does Michael Chang report to?" → tree=true: "I don't have enough information to answer this." → **tree=false: "Michael Chang reports to Dr. Victoria Chen." ✅**
- **Q40** "What is the total company backlog?" → tree=true hallucinated "$966 million" → **tree=false: "$12.4 billion" ✅**
- **Q68** "Chair of the Export Control Committee?" → tree=true: not specified → **tree=false: "Col. (Ret.) James Foster, Empowered Official" ✅**
- **Q100** "Total value of top 3 customer relationships?" → tree=true generic → **tree=false: itemized Boeing $730M + DoD + Airbus = $1.88B (close to expected $1.975B; FuzzyEvaluator passed)** ✅
- **Q36** "Highest TRIR division?" → both name a division but tree=false names Aerospace; FuzzyEvaluator marked it pass under partial-match.

**Lost: 0.** No regressions vs tree=true on this vault.

**Artifacts**
- JSONL: `test_results/stage2c_tree_off/s1j_treeOff_ecd2f1c2_progress.jsonl`
- Summary JSON: `test_results/stage2c_tree_off/SUMMARY.json`
- Driver: `scripts/run_qonly_thin.py`

**Post-run mutation check** (entities/relationships/documents/document_chunks for tenant `ecd2f1c2`):

| table | count |
|---|---:|
| entities | 2146 |
| relationships | 2099 |
| documents | 100 |
| document_chunks | 435 |

Identical to pre-run snapshot — confirmed read-only.

---

## Step 4 — Legacy harness parity (NOT RUN — stop trigger fired)

The plan specifies: *"If legacy vault cannot be tested safely because its document parents are missing/orphaned, report that and do not force it."*

`176a4fb2-0bb4-4da3-9068-0e26268fca71`, verified by direct query at the time of writing this section (2026-05-13 ~04:55 UTC):

```sql
SELECT 'docs:'           || COUNT(*) FROM documents       WHERE tenant_id='176a4fb2-...'
UNION ALL
SELECT 'chunks:'         || COUNT(*) FROM document_chunks WHERE tenant_id='176a4fb2-...'
UNION ALL
SELECT 'orphan_chunks:'  || COUNT(*) FROM document_chunks dc
  WHERE dc.tenant_id='176a4fb2-...'
    AND NOT EXISTS (SELECT 1 FROM documents d WHERE d.id=dc.document_id);
```

Result:
- `docs: 0`
- `chunks: 501`
- `orphan_chunks: 501` (100% of chunks are orphaned — every parent document row is gone)

A query-only run is technically possible (the chunks still exist, and entities/relationships still exist) but is **not isolated**: the `Test: ClaudeCode Nexus` workflow runs against this same vault and overwrites `test_results/claudecode_nexus_industries_176a4fb2_progress.jsonl` in real time. Time-series of that file observed during this session: 100 records (initial read) → 37 records → 0 records (recreated mid-write) → back to 100 records (current at 04:43 UTC). Any new harness run against the same vault would race that workflow's writes and could not be cleanly attributed.

**Decision:** stopped per plan. The 76/100 figure cited elsewhere is from an earlier session read of that JSONL when it was at 100 records and 76 passes. That figure is **not** re-verified here. For an immutable point-in-time snapshot, see `test_results/claudecode_nexus_industries_20260513_044349.json` (an untracked test_runner export captured during the concurrent workflow's most recent completed pass — not Stage 2C output, but the closest stable artifact for the legacy vault).

---

## Step 5 — Ranked restoration plan

### Top 3 recommended (in priority order)

#### A. Disable tree retrieval by default — gate it narrowly to where it has been proven net-positive
- **Change:** `start.sh` L13 → `export CF_TREE_BASED_RETRIEVAL=false`. Keep `tree_based_retrieval=True` available as per-request override for the 8-graph-hopping question set documented in `replit.md` if/when needed for experiments.
- **Why it helps:** Direct measurement (Step 3): +5/0 on Stage 1J 100Q. Matches `replit.md`'s prior conclusion that tree retrieval costs ≈10–11 vs the legacy router on the wider benchmark.
- **Failure bucket targeted:** Graph-rel precision/recall (the 14-bucket); also a few attribute-fact failures where the graph traversal was poisoning answers.
- **Estimated score impact:** **+5** on Stage 1J (measured); per `replit.md` ≈ +10–11 on `176a4fb2` analogue.
- **Risk:** **Low.** Per-request override remains; nothing is removed. Reverses a config that flipped on after the same code was already known to regress.
- **Test needed:** the Step 3 thin run is the test (already done).
- **Tenant isolation preserved?** Yes (no schema change, no shared state).
- **Requires ontology mutation?** No.
- **Requires prompt change?** No.
- **Requires service restart?** Yes — only for permanent default; per-request override needs no restart.

#### B. Wire a DOCUMENT_EVIDENCE chunk fallback for attribute questions (no ontology mutation)
- **Change:** when the answering layer detects an attribute-style question (numeric / date / spec / certification / list-of-items) AND the KG-derived ContextBundle has no concrete value for the attribute, fall back to top-K chunk text retrieval and cite the chunks in the answer with a `DOCUMENT_EVIDENCE` evidence class. Do **not** synthesize fake `HAS_SPEC`/`HAS_VALUE` graph facts. The chunk-fallback already exists (`tree_retriever._fallback_semantic_search`, chunk-grounded; avg top similarity 0.576 unit-tested) but is graph-traversal-gated.
- **Why it helps:** 32/50 Stage 1J failures are attribute facts where the chunk text **does** contain the answer (verified earlier in session: revenue-FY2025 in 2 chunks, qubits in 16, MIT in 204, FedRAMP date in 20, etc.). The KG cannot answer them because Stage 1J's vocabulary lacks SPEC/PARAM/DATE/BUDGET/MILESTONE/EVENT entity types and `HAS_*` relations. Quoting chunks with provenance is safer than fabricating graph facts.
- **Failure bucket targeted:** Entity-attribute (32 failures).
- **Estimated score impact:** Conservatively +10 to +20 (covers most attribute facts whose chunks exist; precision hit will be FuzzyEvaluator-dependent).
- **Risk:** **Medium.** Requires careful evidence-class plumbing through `ContextBundle` so the LLM clearly sees `[DOCUMENT_EVIDENCE]` vs `[VERIFIED]` / `[UNVERIFIED]` graph badges. Must not pretend chunks are TRUSTED graph facts.
- **Test needed:** A/B same Stage 1J question set with fallback ON vs OFF.
- **Tenant isolation preserved?** Yes (the chunk-fallback already filters by `tenant_id`).
- **Requires ontology mutation?** **No.**
- **Requires prompt change?** Minor (ContextBundle template needs the new evidence class). Plan disallows prompt changes — defer this item until Stage 2C sign-off.
- **Requires service restart?** Yes (code change).

#### C. Canonicalize role-relation verbs at staging time
- **Change:** in the staging loader / KG ingestor, map `HOLDS_ROLE` → `HOLDS_POSITION`, `FORMERLY_HELD` → `HOLDS_POSITION` (with `valid_to` set to a past date), and any `WORKS_FOR` PERSON→ORG to `AFFILIATED_WITH` if `AFFILIATED_WITH` is added later. Do **not** change the prompt (plan disallows). The canonicalizer prevents the validator from silently dropping the LLM's output.
- **Why it helps:** Stage 1J vault currently has 0 `HOLDS_ROLE` and 0 `FORMERLY_HELD`. Adding the canonicalizer rescues those rows before they hit the validator. This was the +3 win replit.md notes from the Phase 1 prompt change — and the deferred next iteration.
- **Failure bucket targeted:** Role/succession queries inside the 14-graph-rel bucket (e.g., Q3 Robert Kim President role mis-targeted to Aerospace — could be fixed if the additional `HOLDS_ROLE`(Robert Kim → President of Digital Solutions) row had survived).
- **Estimated score impact:** +2 to +5.
- **Risk:** **Low.** Pure rename at staging; no semantic invention.
- **Test needed:** re-extract Stage 1J vault — but plan disallows re-extraction in this Stage 2C scope. Defer behind sign-off.
- **Tenant isolation preserved?** Yes.
- **Requires ontology mutation?** No (`HOLDS_POSITION` is what the data already canonicalizes to).
- **Requires prompt change?** No.
- **Requires service restart?** Yes (code change), and re-extraction (out of scope here).

### Considered, not recommended

| Lever | Why not |
|---|---|
| Restore `require_verification_for_promotion=True` | Would re-block 100% of promotions per the original revert reason. Do not restore until VerificationWorker throughput catches up. |
| Add full ontology vocabulary expansion (DATE/BUDGET/MILESTONE/EVENT entity types + HAS_*/MEETS_* relations) | Larger and slower than the chunk-fallback in B; requires ontology mutation (out of scope per plan). Re-evaluate once Stage 2C sign-off opens that door. |
| Wire `PrecedencePipeline` + `SymbolicOverrideEngine` | They are real subsystems but were not the source of `176a4fb2`'s 76/100; that vault did not use them either. Wiring them is a larger Stage 2 architecture decision and does not address the 32 attribute-fact failures. Plan calls this out: "Do not recommend wiring all of them blindly." |
| Wire `FailureAnalyzer` / `TargetedExtractor` / `ImprovementLoop` / `LearningOrchestrator` | Same — they are an iterative improvement system, not a request-time fix. Not addressing the immediate gap. |
| Promote the 415 orphan-typed STAGING relations (`FUNDED_BY`/`USES`/`RELATED_TO`/`OWNED_BY`/`FOCUSES_ON`/`WORKS_FOR`) | 0/50 failures match. Already analyzed in the prior failure report. |
| Multi-hop role traversal (`replit.md` "asset for future use") | Useful for chained-role queries but not for the dominant attribute-fact bucket; defer. |
| Coherence Checker → blocking mode | Risks rejecting answers; doesn't add capability. Keep shadow until coverage improves. |

### What must remain protected from prior fixes

- **Tenant isolation / RLS / `TenantSession`.** No proposal touches tenant scoping.
- **IdentityResolver.** No proposal touches it.
- **VerificationWorker.** It continues to write verdicts; the gate stays off for now (intentionally) but the worker stays.
- **Gardener safety thresholds.** No proposal lowers confidence/corroboration floors.
- **No global / cross-tenant queries reintroduced.** All proposals stay tenant-scoped.

### What should NOT be restored

- Old extractor that emitted entity types not in the ontology vocabulary (re-introduces dirty vocab).
- Old gardener that promoted without confidence/corroboration thresholds.
- Any global ID resolution (pre-IdentityResolver).
- `require_verification_for_promotion=True` without first scaling VerificationWorker.

---

## Step 6 — Stage 2 readiness update

| Category | Verdict | Rationale |
|---|---|---|
| Pipeline safety readiness | **READY** | Tenant isolation, IdentityResolver, VerificationWorker all in place. Mutation check post-experiment confirms request-scoped isolation works. |
| Answer-quality readiness | **NOT READY** | 50–55/100 on Stage 1J vs ~76/100 historical on legacy vault. Gap dominated by attribute-fact bucket (32/50). Until B (chunk-fallback) or vocabulary expansion lands, answer quality is below the historical bar. |
| Stage 2 design readiness | **READY** | Failure buckets are now precisely characterized; recovery levers are individually scoped. |
| Stage 2 implementation readiness | **NOT READY** | Wait for at least proposal A landed (default tree=false) and B (chunk-fallback) designed and merged. |
| Stage 2 default activation readiness | **NOT READY** | Will remain not-ready until at least 70/100 is reproduced on Stage 1J under a fixed configuration. |

---

## Stop conditions encountered

- Step 4 (legacy parity): orphan-document parents in `176a4fb2`, plus active concurrent workflow rewriting the JSONL → **stopped per plan**.
- No proposed fix in Section 5 undoes tenant isolation.
- No proposed fix in Section 5 (top 3) requires ontology mutation, prompt change, or service restart **at this Stage 2C step** — those would be implementation tasks gated on sign-off.

---

## Final report

- **Capabilities disabled / narrowed / unwired** (see Step 1 audit table): tree retrieval (re-enabled in `start.sh` despite known regression), `use_ontology_schema=True` narrows extraction prompt, `require_verification_for_promotion=False` disables Phase 3 evidence gate, role verbs `HOLDS_ROLE`/`FORMERLY_HELD` silently dropped by validator, `PrecedencePipeline` + `SymbolicOverrideEngine` + `FailureAnalyzer` + `TargetedExtractor` + `ImprovementLoop` + `LearningOrchestrator` not wired into `/api/vault/chat`, `CoherenceChecker` shadow-only.
- **Retrieval-mode score delta:** Stage 1J `tree=false` = **55/100**, vs `tree=true` = 50/100 → **+5, 0 regressions**, recovered Q15/Q36/Q40/Q68/Q100.
- **Legacy parity result:** not run; plan stop-trigger applied (orphan parents + active concurrent rewrite of the legacy JSONL).
- **Ranked recovery plan:** A (default tree off / per-request override) → B (DOCUMENT_EVIDENCE chunk fallback for attribute questions) → C (canonicalize role verbs at staging).
- **Top 3 recommended fixes:** A, B, C above.
- **What should not be restored:** see Section 5 "Considered, not recommended" + "What should NOT be restored".
- **What must remain protected from prior fixes:** tenant isolation, IdentityResolver, VerificationWorker, Gardener thresholds, no global/cross-tenant behavior.
- **Stage 2 blocked by answer quality?** **Yes**, until A+B together are demonstrated to push Stage 1J to ≥70/100 under a fixed configuration.
- **Findings doc path:** `docs/findings/stage2c_score_recovery_isolation_2026-05-12.md` (this document).

---

## Stop condition met

Stage 2C score-recovery isolation report complete. **Awaiting sign-off** before any restoration, config change, ontology mutation, prompt change, re-extraction, worker recovery, or Stage 2 implementation.
