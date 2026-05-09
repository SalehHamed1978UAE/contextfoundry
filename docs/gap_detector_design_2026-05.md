# Gap Detector — Design Document

**Status:** Draft for sign-off
**Author:** Agent
**Date:** 2026-05-09
**Vault under test:** ClaudeCode Nexus Industries (`176a4fb2-0bb4-4da3-9068-0e26268fca71`)
**Baseline run:** `test_results/claudecode_nexus_industries_20260509_073740.json` (74/100 passing, 26 failures)
**Oracle experiment:** `test_results/v2_parallel/oracle.jsonl` (26 records + summary)

---

## 1. Executive Summary

We ran the v2 FactEvaluator under **oracle conditions**: for each of the 26
v1-failing Nexus questions, we fed v2's fact extractor the **expected**
(ground-truth) answer instead of v1's wrong answer. If v2's logical validation
were the missing piece, we should have seen most candidates land in
PROVEN / STRONGLY_SUPPORTED / SUPPORTED. We did not.

| Outcome | Count | Notes |
|---|---:|---|
| Total questions | 26 | All v1 failures from baseline |
| **PROVEN / STRONGLY_SUPPORTED / SUPPORTED** | **0** | The headline number |
| V2_NO_CANDIDATE — extractor rejected | 11 | No representable triple shape |
| V2_NO_CANDIDATE — entity-resolution failed | 8 | Triple extracted, target unresolvable |
| UNDERSPECIFIED — engine ran, NOT_FOUND | 5 | Includes Q17 (false-positive grader, audited) |
| INFRA — engine ignored cancellation, ran past 5min | 2 | Q15 @ 811s, Q18 @ 530s |
| Oracle correct (per FuzzyEvaluator) | 1 | **Q17 audited; reset to 0/26** |

**Audit note (Q17):** The grader (`FuzzyEvaluator._check_semantic_equivalence`)
returned `semantic_match` for `"v2 cannot confirm (NOT_FOUND)"` against the
expected `"Nel Hydrogen"`. Confirmed false-positive; record patched in
`oracle.jsonl` (`v2_correct: false`, `v2_correct_audit` field). True headline
is **0/26** by both metrics.

**Caveat (gatherer):** Throughout the run, the gatherer's vector strategies
errored with `TypeError: object list can't be used in 'await' expression`
(sync embedder being awaited). The gatherer ran on graph_endpoint + fts_chunks
only — **~50% retrieval capacity**. Any UNDERSPECIFIED claim of
"truth-not-retrieved" carries this caveat. The bug is now patched in
`scripts/run_v2_parallel.py` and `scripts/run_v2_oracle.py` (async embedder via
`asyncio.to_thread`); a clean re-run is gated on this design doc's sign-off.

### Top-line thesis

> The v2 FactEvaluator cannot serve as the primary recovery mechanism for
> Nexus failures because the majority of failures cannot be expressed as
> `Fact(subject_entity, relation_type, target_entity)`. Even with oracle
> inputs, **0/26** failures collapsed to PROVEN/SUPPORTED, because **19/26
> never reached the evaluator at all** — they died in extraction or entity
> resolution. The next iteration introduces a **Question-Shape Router** that
> dispatches each question to the right handler (existing FactEvaluator for
> triples; small purpose-built chunk extractors for dates/scalars/ranges;
> ontology fixes for ownership; retrieval fixes for entity-resolution gaps),
> with a **Gap Detector** layered on top that fires when any handler returns
> empty and produces a typed human-completion question.

---

## 2. Why the FactEvaluator Fails as the Recovery Layer

The v2 candidate model is:

```
Fact(source_entity_id: UUID, relationship_type: str, target_entity_id: UUID, …)
```

This shape forces every question through three preconditions:

1. The answer must be **a single entity** (the target).
2. There must be **a single allowed relationship type** that captures the
   semantics linking subject to answer.
3. Both subject and target must be **resolvable to existing graph nodes**.

The oracle data shows that the 26 failures violate at least one of those
preconditions in 100% of cases. Worked examples from the oracle run:

| Q | Question | Expected | Why FactEvaluator can't represent it |
|---:|---|---|---|
| 14 | When was Robert Kim appointed President of Digital Solutions? | January 2026 | Date is a temporal attribute of a HOLDS_POSITION edge, not a target entity. |
| 24 | Hydrogen production capacity of GreenHydrogen facility? | 425 kg/hour (Phase 1) / 10,200 kg/day | Quantity-with-qualifier; not an entity. |
| 29 | Members of the Executive Leadership Team? | List of 9 named people | Single Fact represents one edge, not a set. |
| 36 | Which division has the highest TRIR? | Nexus Advanced Materials (1.24 TRIR) | Aggregation/argmax over scalar metric on multiple entities. |
| 40 | Total company backlog? | $12.4B | Scalar financial metric; no relationship type. |
| 45 | When was Dr. Victoria Chen appointed CEO? | 2019 | Temporal attribute; same shape as Q14. |
| 67 | Operating temperature range of solid-state battery? | -30°C to 60°C | Range value; not an entity. |
| 79 | 2030 revenue target? | $15B | Scalar strategic-goal metric. |
| 91 | VP Trade Compliance? | Owns the Export Control Policy | Responsibility/ownership semantics; no OWNS_POLICY edge in ontology. |
| 1 | CEO of Nexus Industries? | Dr. Victoria Chen | Subject is correct (CEO role), but target is `ROLE@ORG` composite — not a graph node. |
| 38 | CISO of Nexus Industries? | Jennifer Walsh | Same composite-role shape as Q1; needs role-resolver pre-step. |

Even when extraction succeeded and produced a valid Fact, the engine reached
NOT_FOUND under the **degraded gatherer** (Q25, Q46, Q61, Q83). Whether those
recover with full vector retrieval is unknown — that's the post-fix re-run.

---

## 3. The Question-Shape Router Architecture

### 3.1 The dispatcher

A **QuestionShapeRouter** runs **before** the v2 extractor. It classifies each
incoming question by **expected answer shape** and routes to a handler. The
handler returns either an answer (with provenance) or a typed
`HandlerEmptyResult` that the Gap Detector consumes.

```
       ┌───────────────────────┐
query  │  QuestionShapeRouter   │ ── shape ──┐
──────▶│  classify(question)    │            │
       └───────────────────────┘            ▼
                                  ┌──────────────────────┐
                                  │ Handler (per shape)  │
                                  │  → answer            │
                                  │  → HandlerEmptyResult│
                                  └──────────────────────┘
                                            │
                                            ▼
                                  ┌──────────────────────┐
                                  │ GapDetector          │
                                  │ (only if empty)      │
                                  │  → typed Gap         │
                                  └──────────────────────┘
                                            │
                                            ▼
                                       Human queue
```

### 3.2 Shape taxonomy and handler routing

| Shape | Handler | Behavior |
|---|---|---|
| `triple` | **FactEvaluator (existing v2)** | subject—rel—target. Today's path. |
| `date` | `DateExtractor` (new, small) | Targeted regex + LLM extraction of date phrases from chunks already retrieved by the relevant edge's `source_chunk_id`. Returns ISO date + provenance. |
| `scalar` | `ScalarExtractor` (new, small) | Same shape as DateExtractor for $, count, %, rates. Unit-aware. |
| `range` | `RangeExtractor` (new, small) | Returns `{min, max, unit}` from chunks. |
| `list` | `ListExtractor` (new, small) | Enumerates members via repeated graph queries (e.g., MEMBER_OF target_entity), then synthesizes from chunks. |
| `composite_role` | **EntityResolver enhancement** (extraction-time fix, not runtime) | `"CEO of Nexus Industries"` → resolve to PERSON via `(ORG)-[:HAS_ROLE]->(ROLE)<-[:HOLDS_POSITION]-(PERSON)` traversal. No new evaluator class. |
| `ownership` | **Ontology extension** | Add `OWNS_POLICY`, `OWNS_PROCESS`, `OWNS_CONTROL` relationships. Then routes through FactEvaluator as `triple`. |
| `aggregation` | **Defer to gap** for v1 of this work | Argmax/sum/comparison over a population. Genuinely needs new logic; explicitly deferred to typed-evaluator v3 (out of scope). |

**Key design constraint** (from the user brief): the new shape-handlers are
**not new evaluator classes**. They are **focused extraction passes over
already-retrieved chunks**, triggered by question shape. The implementation
budget is days/weeks, not months. Composite-role handling is a
**resolver/extraction fix**, not a new component. Ownership is an
**ontology fix**, not a new component.

### 3.3 Classification mechanism

`QuestionShapeRouter.classify` is an LLM-backed classifier with a small,
deterministic feature pre-pass:

- Regex pre-filters (cheap):
  - `\bwhen\b|\bdate\b|\bappointed\b` → `date`
  - `\bhow much\b|\bhow many\b|\b\$\d|backlog|target|revenue|capex|TRIR\b` → `scalar`
  - `\brange\b|temperature|operating|between .* and\b` → `range`
  - `\bmembers of\b|list .* of\b|\bwho are\b` → `list`
  - `\b(CEO|CFO|CTO|CISO|President|Chair|Director|VP)\s+of\s+\w+` → `composite_role`
  - `\bowns\b|\bresponsible for\b|\bowner of\b` → `ownership`
  - `\bhighest\b|\blargest\b|\btotal\b|\bsum\b|\bcompare\b` → `aggregation`
- LLM tiebreak when regex matches multiple, or none.
- Default: `triple`.

Classifier output goes into the trace; the trace is used to score routing
correctness during demo prep.

---

## 4. The Gap Detector

The Gap Detector is **a layer on top of the router**. It does not classify
questions in isolation; it classifies **the failure** when a handler returns
`HandlerEmptyResult`. This means every gap has full provenance: the chosen
handler, what it tried, what it found, and why it gave up.

### 4.1 Gap taxonomy (4 classes)

Per reviewer-1's split (adopted), gaps separate by **what subsystem owns the
fix**:

#### A. Representational gaps (ontology/extraction owns the fix)

| Code | Meaning |
|---|---|
| `GAP_TEMPORAL_ATTRIBUTE` | Question wants a date/time qualifier on an existing fact |
| `GAP_SCALAR_METRIC` | Question wants a numeric measurement not modeled as a relationship |
| `GAP_LIST_AGGREGATION` | Single triple cannot represent a set/list answer |
| `GAP_COMPOSITE_ROLE_TARGET` | Target is `ROLE @ ORG`, not a single graph node |
| `GAP_QUANTITY_RANGE_TARGET` | Target is a `{min, max, unit}` range |
| `GAP_MATERIAL_SPEC_TARGET` | Target is a material/spec literal, not a node |
| `GAP_OWNERSHIP_RESPONSIBILITY` | No `OWNS_*` relationship exists in ontology |
| `GAP_AMBIGUOUS_SUBJECT` | Question's subject cannot be uniquely resolved |

#### B. Retrieval gaps (retrieval/resolver owns the fix)

| Code | Meaning |
|---|---|
| `GAP_EVIDENCE_NOT_RETRIEVED` | Truth exists in corpus but retrieval missed it |
| `GAP_ENTITY_RESOLUTION_FAILED` | Named entity in question/answer not in graph or wrong fingerprint |
| `GAP_RELATION_NOT_IN_GRAPH` | Edge missing despite source chunk present |

#### C. Synthesis gaps (reasoning owns the fix — deferred to v3)

| Code | Meaning |
|---|---|
| `GAP_ROLE_DEREFERENCE` | Need to chase ROLE → PERSON via multi-hop |
| `GAP_QUALIFIER_BINDING` | Need to bind a qualifier (date, $, location) to an edge |
| `GAP_ATTRIBUTE_SELECTION` | Multiple matching edges; need to pick the right one |
| `GAP_TOTAL_OR_COMPARISON_OPERATION` | Need to sum/argmax/compare across multiple facts |

#### D. Runtime/infrastructure (not product gaps)

| Code | Meaning |
|---|---|
| `INFRA_TIMEOUT_CANCELLATION_FAILURE` | `asyncio.wait_for` did not cut off engine work |
| `INFRA_VECTOR_GATHERER_AWAIT_BUG` | Gatherer awaited sync embedder (now patched) |
| `INFRA_LLM_CACHE_VERSIONING_RISK` | Cache key did not include prompt/schema/engine version (now patched) |
| `INFRA_API_CREDIT_BLOCKER` | Provider quota/credit prevents calls |

These are **not counted in product reasoning gap totals**. They are reliability
issues. The Gap Detector emits them so they're auditable, but routing rules
exclude them from the human queue.

### 4.2 Gap object schema

```python
@dataclass
class Gap:
    gap_id: str                 # deterministic SHA256 (see 4.3)
    gap_type: str               # one of the codes above
    question_id: int            # source question
    question_text: str
    expected_answer_shape: str  # router's classification
    handler_used: str           # "FactEvaluator" | "DateExtractor" | …
    handler_attempt: dict       # what the handler tried (Fact, query, etc.)
    handler_empty_reason: str   # the HandlerEmptyResult.reason
    suggested_remediation: str  # one of: extractor_pass | ontology_extend |
                                #         resolver_fix | retrieval_fix |
                                #         human_completion | infra_fix
    routing_destination: str    # "human" | "automation" | "deferred"
    created_at: datetime
    tenant_id: UUID
```

### 4.3 `gap_id` determinism

```
gap_id = sha256(f"{tenant_id}|{gap_type}|{normalized_question}|{handler_used}").hexdigest()[:16]
```

This makes gaps idempotent: re-running the same question against the same
vault produces the same `gap_id`. Human answers can be cached against
`gap_id` and replayed across re-runs.

### 4.4 `NoApplicableGap` distinction

When a handler returns an answer (success), no Gap is created. When a handler
returns `HandlerEmptyResult` but the failure does not match any known
classification rule, the Detector emits `Gap(gap_type="NoApplicableGap", …)`
with the full handler trace. This is **not** the same as `GAP_UNKNOWN` —
`NoApplicableGap` means the Detector itself needs improvement, and triggers
an analyst-level review rather than a human-completion question.

### 4.5 YAML routing table

Routing rules live in `config/gap_routing.yaml`, hot-reloadable:

```yaml
# Gap-type → routing destination + remediation channel
GAP_TEMPORAL_ATTRIBUTE:
  routing_destination: automation
  suggested_remediation: extractor_pass
  handler_to_invoke: DateExtractor

GAP_SCALAR_METRIC:
  routing_destination: automation
  suggested_remediation: extractor_pass
  handler_to_invoke: ScalarExtractor

GAP_QUANTITY_RANGE_TARGET:
  routing_destination: automation
  suggested_remediation: extractor_pass
  handler_to_invoke: RangeExtractor

GAP_COMPOSITE_ROLE_TARGET:
  routing_destination: automation
  suggested_remediation: resolver_fix
  handler_to_invoke: CompositeRoleResolver

GAP_OWNERSHIP_RESPONSIBILITY:
  routing_destination: automation
  suggested_remediation: ontology_extend
  ontology_change_required: [OWNS_POLICY, OWNS_PROCESS, OWNS_CONTROL]

GAP_LIST_AGGREGATION:
  routing_destination: human         # v1: human; v3: ListExtractor
  suggested_remediation: human_completion

GAP_AMBIGUOUS_SUBJECT:
  routing_destination: human
  suggested_remediation: human_completion

GAP_EVIDENCE_NOT_RETRIEVED:
  routing_destination: automation     # if vector fix sufficient
  suggested_remediation: retrieval_fix
  fallback_destination: human         # if still empty after fix

GAP_ENTITY_RESOLUTION_FAILED:
  routing_destination: automation
  suggested_remediation: resolver_fix
  fallback_destination: human

INFRA_TIMEOUT_CANCELLATION_FAILURE:
  routing_destination: deferred       # not human-facing
  suggested_remediation: infra_fix

INFRA_VECTOR_GATHERER_AWAIT_BUG:
  routing_destination: deferred
  suggested_remediation: infra_fix
  status: PATCHED_2026-05-09         # already fixed, gated re-run pending

INFRA_LLM_CACHE_VERSIONING_RISK:
  routing_destination: deferred
  suggested_remediation: infra_fix
  status: PATCHED_2026-05-09
```

---

## 5. Human-Completion Interface

Three Views, served from the existing Flask app under `/gaps`.

### 5.1 View A — Queue

`GET /gaps/queue?tenant_id=…`

Lists all `Gap` rows where `routing_destination == "human"` and no human
answer recorded yet. Sorted by question_id ascending. Each row shows:
gap_id (short), question_text (truncated), gap_type, handler_used,
created_at, **Skip** + **Answer** + **Reroute** buttons.

### 5.2 View B — Typed answer form (with Skip + Reroute)

`GET /gaps/<gap_id>` and `POST /gaps/<gap_id>/answer`

The form is **shape-typed** — fields are rendered per the gap's expected shape:

- `triple` — three text inputs (subject, rel-type dropdown from schema, target)
- `date` — ISO date picker + free-text qualifier
- `scalar` — numeric input + unit dropdown
- `range` — min, max, unit
- `list` — repeating row of typed entries
- `composite_role` — person picker + role/org pickers
- `ownership` — person/org picker + policy/process/control picker

Every form includes:
- `evidence_text`: free-text "where did this come from"
- `evidence_source_url`: optional link
- `confidence`: low / medium / high
- **Skip button** → records `skipped_by`, `skipped_at`, `skip_reason`. Gap
  stays in the queue with status `skipped` (re-orderable).
- **Reroute button** → opens a small modal with `reroute_destination`
  (`automation` | `another_human` | `defer_to_v3`) and
  `reroute_reason`. Updates the Gap row, removes it from the current human's
  queue.

Submission writes a `HumanConfirmationEvidence` row (see 5.4) and triggers
the writeback worker.

### 5.3 View C — Audit trail

`GET /gaps/<gap_id>/audit`

Read-only view showing:
- Original question + expected_answer_shape (router output)
- Handler used + full handler trace (HandlerEmptyResult.reason, evidence
  considered, why it gave up)
- Gap classification reasoning (which rule fired in the Detector)
- All human interactions: who saw it, who skipped, who rerouted, who answered,
  with timestamps
- Final accepted answer + evidence
- Writeback result: which entities/relationships were created/updated, with
  ids and STAGING→TRUSTED status

This is the artifact that proves to the user "the system did not silently
fabricate; here's exactly how this answer entered the graph."

### 5.4 `HumanConfirmationEvidence` data model

```python
class HumanConfirmationEvidence(Base):
    __tablename__ = "human_confirmation_evidence"
    id = Column(UUID, primary_key=True, default=uuid4)
    gap_id = Column(String(16), nullable=False, index=True)
    tenant_id = Column(UUID, nullable=False, index=True)
    answered_by = Column(String, nullable=False)        # user id
    answered_at = Column(DateTime, nullable=False, default=utcnow)
    answer_payload = Column(JSONB, nullable=False)      # shape-typed
    evidence_text = Column(Text, nullable=False)        # required
    evidence_source_url = Column(String, nullable=True)
    confidence = Column(Enum("low","medium","high"), nullable=False)
    skipped_by = Column(String, nullable=True)
    skipped_at = Column(DateTime, nullable=True)
    skip_reason = Column(Text, nullable=True)
    reroute_destination = Column(String, nullable=True)  # see View B
    reroute_reason = Column(Text, nullable=True)
    writeback_status = Column(Enum("pending","applied","failed"), default="pending")
    writeback_result = Column(JSONB, nullable=True)      # ids of created/updated facts
```

Writeback creates entities/relationships in **STAGING** with provenance
pointing back to `gap_id` and `human_confirmation_evidence.id`. The Gardener
promotes to TRUSTED on the next pass per existing policy. Verification status
is set to `verified=true` since human confirmation is treated as authoritative
evidence at the same level as LLM verification.

---

## 6. Per-Question Remediation Plan (the demo plan)

Mapping every one of the 26 v1 failures to a handler and the path to "answered
by demo time." This is the concrete plan for the **100% comprehension demo**.

| Q | Question (truncated) | Expected | Oracle outcome | Gap class | Handler / remediation |
|---:|---|---|---|---|---|
| 1 | CEO of Nexus Industries? | Dr. Victoria Chen | NO_CANDIDATE (resolve fail) | GAP_COMPOSITE_ROLE_TARGET | `CompositeRoleResolver` (resolver fix) |
| 14 | When was Robert Kim appointed President? | January 2026 | NO_CANDIDATE (extractor) | GAP_TEMPORAL_ATTRIBUTE | `DateExtractor` |
| 15 | Who does Michael Chang report to? | Dr. Victoria Chen | TIMEOUT 811s | INFRA_TIMEOUT_CANCELLATION_FAILURE + GAP_EVIDENCE_NOT_RETRIEVED | Infra fix; expect resolution under fixed gatherer |
| 17 | Who supplied the electrolyzers for GreenHydrogen? | Nel Hydrogen | UNDERSPECIFIED (NOT_FOUND, false-positive grader) | GAP_EVIDENCE_NOT_RETRIEVED | Re-run after vector fix; if still empty → human |
| 18 | Green hydrogen offtake partner? | Shell | TIMEOUT 530s | INFRA_TIMEOUT + GAP_EVIDENCE_NOT_RETRIEVED | Infra fix; expect resolution under fixed gatherer |
| 24 | Hydrogen production capacity? | 425 kg/hour, 10,200 kg/day | NO_CANDIDATE (resolve) | GAP_QUANTITY_RANGE_TARGET | `ScalarExtractor` (with multi-unit support) |
| 25 | Target energy density of solid-state battery? | 400 Wh/kg | UNDERSPECIFIED (NOT_FOUND) | GAP_SCALAR_METRIC + GAP_EVIDENCE_NOT_RETRIEVED | `ScalarExtractor` after vector fix |
| 29 | ELT members? | List of 9 people | NO_CANDIDATE (extractor) | GAP_LIST_AGGREGATION | **Human** (v1); ListExtractor v3 |
| 36 | Highest-TRIR division? | Nexus Advanced Materials (1.24) | NO_CANDIDATE (extractor) | GAP_TOTAL_OR_COMPARISON_OPERATION | **Human** (v1); AggregationEvaluator v3 |
| 37 | Project Director for GreenHydrogen? | Jennifer Walsh | NO_CANDIDATE (resolve) | GAP_COMPOSITE_ROLE_TARGET | `CompositeRoleResolver` |
| 38 | CISO of Nexus Industries? | Jennifer Walsh | NO_CANDIDATE (resolve) | GAP_COMPOSITE_ROLE_TARGET | `CompositeRoleResolver` |
| 40 | Total company backlog? | $12.4B | NO_CANDIDATE (extractor) | GAP_SCALAR_METRIC | `ScalarExtractor` (financial unit) |
| 45 | When was Dr. Victoria Chen appointed CEO? | 2019 | NO_CANDIDATE (extractor) | GAP_TEMPORAL_ATTRIBUTE | `DateExtractor` |
| 46 | Solar panel supplier for Desert Sun? | First Solar | UNDERSPECIFIED | GAP_EVIDENCE_NOT_RETRIEVED | Re-run after vector fix |
| 48 | Primary HTS wire customer? | Siemens Healthineers ($65M) | NO_CANDIDATE (resolve) | GAP_MATERIAL_SPEC_TARGET + GAP_SCALAR_METRIC | `CompositeRoleResolver` (target=PRODUCT then customer) + `ScalarExtractor` |
| 60 | When was the phishing incident detected? | Dec 12, 2025 02:47 UTC | NO_CANDIDATE (extractor) | GAP_TEMPORAL_ATTRIBUTE | `DateExtractor` (timestamp variant) |
| 61 | Who replaced Thomas Anderson as Digital President? | Robert Kim | UNDERSPECIFIED | GAP_EVIDENCE_NOT_RETRIEVED | Re-run after vector fix |
| 66 | FY2026 capex plan? | $680M | NO_CANDIDATE (extractor) | GAP_SCALAR_METRIC | `ScalarExtractor` |
| 67 | Solid-state battery operating temp range? | -30°C to 60°C | NO_CANDIDATE (resolve) | GAP_QUANTITY_RANGE_TARGET | `RangeExtractor` |
| 68 | Chair of Export Control Committee? | Col. James Foster | NO_CANDIDATE (resolve) | GAP_COMPOSITE_ROLE_TARGET | `CompositeRoleResolver` |
| 71 | Mining automation partner? | Caterpillar | NO_CANDIDATE (extractor) | GAP_AMBIGUOUS_SUBJECT | **Human** (subject not specified in question) |
| 73 | New employees in FY2026? | 1,200 net new | NO_CANDIDATE (extractor) | GAP_SCALAR_METRIC | `ScalarExtractor` (count) |
| 79 | 2030 revenue target? | $15B | NO_CANDIDATE (extractor) | GAP_SCALAR_METRIC | `ScalarExtractor` (forward-looking metric) |
| 83 | Primary SmartGrid Controller customer? | Pacific Power (pilot) | UNDERSPECIFIED | GAP_EVIDENCE_NOT_RETRIEVED | Re-run after vector fix |
| 91 | VP Trade Compliance owns what? | Export Control Policy | NO_CANDIDATE (extractor) | GAP_OWNERSHIP_RESPONSIBILITY | Ontology extension (`OWNS_POLICY`) → FactEvaluator |
| 93 | Solid-state battery electrolyte material? | LLZO (Li7La3Zr2O12, Al-doped) | NO_CANDIDATE (resolve) | GAP_MATERIAL_SPEC_TARGET | `MaterialSpecResolver` (one-shot extractor pass over the SPEC chunk) |

### Demo automation budget

| Path | Count | Effort |
|---|---:|---|
| **Automation: existing FactEvaluator** (after ontology extension) | 1 | 1 day (Q91 + OWNS_POLICY ontology row) |
| **Automation: new chunk extractors** (Date/Scalar/Range/MaterialSpec) | 12 | 3-5 days |
| **Automation: CompositeRoleResolver** | 5 | 2-3 days |
| **Automation: vector-fix re-run only** | 4 | re-run is free, validates infra patch |
| **Automation: infra fix (timeout cancellation)** | 2 | 1-2 days, testing-heavy |
| **Human-completion gaps** | 2 | UI + 2 curator turns |
| **Total automation candidates** | 24 / 26 | ~92% automation ratio |

The two genuinely human-completion cases are **Q29 (list aggregation)** and
**Q71 (ambiguous subject)** — both are correctly classified as needing
clarification rather than extraction.

---

## 7. Out-of-Scope Deferrals

Reviewer 1 proposed a typed candidate/evaluator class expansion:

```
Candidate := Fact | Date | Scalar | Range | List | Aggregation | …
Evaluator := FactEvaluator | DateEvaluator | MetricEvaluator | …
```

**This is the right v3 direction and is explicitly out of scope for this
work.** The reasons:

1. The current system handles **triples plus targeted chunk extraction**, and
   that is sufficient to reach the 92% automation ratio for the demo.
2. New evaluator classes are 6-8 components × full evaluator pipeline (Plan,
   Gather, Prove, Adversary, Synthesize, Meta) each. That's 2-3 months.
3. The chunk-extractor approach reuses the gatherer's already-retrieved
   chunks, so each new shape adds days, not weeks.
4. We can validate the automation path on the Nexus 26 with the chunk-extractor
   approach, then graduate the patterns into typed evaluators in v3 if
   warranted.

What this means concretely:
- **No new `*_Candidate` ADT branches in `contracts.py`** for this work.
- **No new `*_Evaluator` classes in the inference engine** for this work.
- The 4 Synthesis gaps (`GAP_ROLE_DEREFERENCE`, `GAP_QUALIFIER_BINDING`,
  `GAP_ATTRIBUTE_SELECTION`, `GAP_TOTAL_OR_COMPARISON_OPERATION`) are
  **emitted by the Detector but routed to `human` or `deferred`** in v1.

---

## 8. Implementation Plan & Sequencing

After sign-off:

1. **Re-run the oracle with the vector fix** to validate INFRA fixes don't
   change the gap distribution (expect Q15/18/25/46/61/83 to behave
   differently).
2. **Schema + dispatcher scaffolding** — `Gap` table, `HumanConfirmationEvidence`
   table, `QuestionShapeRouter` skeleton, `gap_routing.yaml`.
3. **DateExtractor + ScalarExtractor** — covers 9 questions.
4. **CompositeRoleResolver** — covers 5 questions.
5. **RangeExtractor + MaterialSpecResolver** — covers 3 questions.
6. **OWNS_POLICY ontology extension + re-extraction of POL-009** — covers Q91.
7. **Human-completion UI Views A/B/C** — for Q29, Q71, and any handler-empty
   fallbacks.
8. **Demo run + audit-trail review** — establish the 100% comprehension claim
   with full provenance.

---

## 9. Open Questions for Sign-Off

1. Are we comfortable shipping `GAP_LIST_AGGREGATION` (Q29) as human-only in
   v1, or should we attempt a `ListExtractor` chunk-pass given the ELT
   list is in a single document?
2. Should the routing table support **per-tenant** overrides, or is a single
   global YAML sufficient for the demo?
3. For the writeback worker: is human-confirmed evidence promoted directly to
   TRUSTED, or does it pass through STAGING and wait for the Gardener? Default
   in this draft is **STAGING → Gardener-promoted**, treating it the same as
   LLM verification. Confirm.
4. What's the latency budget for the QuestionShapeRouter? Current proposal is
   regex pre-pass + optional LLM tiebreak; 90th-percentile target ≤ 50ms
   without LLM, ≤ 1.5s with.

Awaiting sign-off before any implementation.
