# Piece 2.0 — Domain-Scoped Prompting Design (Design Only)

**Status:** Design proposal — awaiting sign-off. No code, no DB mutations, no prompt changes.
**Date:** 2026-05
**Builds on:** Piece 0 (canonical domain registry), Piece 0.5 (repository filter fix), Piece 1 (classification in multi-model path), Piece 1.5 (classification parity in ontology path).
**Locked architectural principle:** Domain-scoped prompts are the architecture. **There is no full-union fallback.** Low confidence is a governance signal, not a license to widen scope.

---

## 1. Inputs available after Piece 1.5

For every document that flows through either extraction path, `platform.documents` now carries:

| Column | Source | Today's behavior |
|---|---|---|
| `primary_domain` | wrapper Top-1 from cosine score across 8 domain prototypes | populated for `status='ok'`; one of 8 canonical domain_ids |
| `secondary_domains` | wrapper Top-N (N≥2) | always `[]` today (wrapper does not yet emit) |
| `document_type` | filename heuristic OR LLM classifier | populated when `status='ok'` |
| `classification_confidence` | Top-1 cosine score | numeric, real-doc range observed 0.20–0.40 |
| `classifier_version` | wrapper version literal | currently `'v1.0.0-2026-05'` |
| `classification_evidence` | sorted per-domain score string | always populated when `status='ok'` |
| `classification_status` | `'ok' | 'failed' | 'unclassified'` | CHECK-constrained |

**Piece 1.5 added metadata parity for both extraction paths and changed no prompts** (verified by 7-file SHA-256 byte-identity check).

Current ontology distribution (measured 2026-05):

| domain_id | layer-2 types | active relations |
|---|---:|---:|
| `core` | 25 | 17 |
| `aviation` | 27 | 30 |
| `construction` | 26 | 28 |
| `finance` | 28 | 27 |
| `healthcare` | 26 | 34 |
| `it_infrastructure` | 34 | 25 |
| `manufacturing` | 18 | 24 |
| `supply_chain` | 19 | 27 |
| `(NULL)` | 805 layer-2 types | 42 relations |
| **8 named domains total** | **203** | **212** |

The 805 NULL-domain types and 42 NULL-domain relations are precisely the flat-union pool the architecture is escaping. **Any Piece 2 implementation must exclude NULL-domain rows from scoped prompts by default.**

---

## 2. Recommended scope construction: **Option D**

```
scope = core_types ∪ primary_domain_types
scope = core_relations ∪ primary_domain_relations
```

Always the same shape. Confidence does not widen scope. Confidence drives a **governance signal**.

**Rejected:** Option C (primary + close runner-up) and any "low-confidence → full union" fallback. Both silently undo the architecture and reintroduce the flat-union problem under a different name. The locked architectural principle in this brief explicitly forbids them.

**Deferred:** Option B (primary + secondary + core) is identical to Option D today because `secondary_domains` is always `[]`. Reserve the column for when the wrapper emits Top-N and re-evaluate then — do not pre-build the union path before the data exists.

**Deferred:** Option E (document_type overlay) requires a `document_type → ontology overlay` mapping that does not exist. Recommend Piece 2.5.

**Why not Option A:** Option A and Option D have identical scope formulas. The difference is what the system does on low confidence: Option A is silent, Option D emits a governance signal. **The signal is the whole point.**

---

## 3. Confidence and margin policy (measurement-driven)

**The architecture does not use confidence to alter prompt scope.** Confidence only drives governance signals.

### Threshold revision plan (staged, NOT audit-only calibration)

Audit-only feedback alone is **not** a substitute for formal calibration — `audit_records` rows are biased toward uncertain documents (that's their selection criterion), so they cannot stand in for a labeled, randomly-sampled set. Calibration is staged across three horizons:

1. **Initial Piece 2 (provisional sentinels).**
   - `classification_confidence < 0.30` → emit one `audit_records` row.
   - `top_two_margin < 0.05` → emit one `audit_records` row.
   - These produce `audit_records` only. **They do not change prompt scope.**

2. **Piece 2.5 first sentinel review.**
   - Trigger: ≥50 `audit_records` accumulated **OR** two weeks of real extraction activity, whichever comes first.
   - Output: revised sentinel thresholds based on the observed distribution + qualitative review of flagged docs.
   - Still audit-only — still no scope change.

3. **Longer-term calibration (separate epic, NOT deleted).**
   - A labeled held-out document set remains the gold standard for real threshold work because `audit_records` are biased toward uncertain cases.
   - Earlier ≥240-doc target may be **reduced or staged** (e.g., start with ≥10 ground-truth-labeled docs per domain = ~80 total, expand iteratively), but the requirement for labeled calibration is **not deleted**.
   - Plot confidence histograms, extraction recall by confidence band, false-domain rate. Use these to set defensible thresholds.

### Temporary defaults for initial Piece 2 implementation

| Setting | Initial value | Reasoning |
|---|---|---|
| Prompt scope formula | `core ∪ primary_domain` | Locked by Option D |
| Confidence threshold for `audit_records` emission | `< 0.30` | Below 50% of all real-doc observations to date (0.26, 0.26, 0.34, 0.27, 0.27); strictly an interim audit trigger, not a behavior gate |
| Top-2 margin threshold for `audit_records` emission | `< 0.05` | All four real-doc cases observed have margins in 0.03–0.08 range; this triggers on the tightest cases |
| Prompt scope behavior at low confidence | **unchanged** | Option D — scope is never widened |

These thresholds are **provisional sentinels**, not behavior gates. Revised at the Piece 2.5 review and again after labeled-set calibration.

### What confidence affects, by surface

| Surface | Affected by confidence today? | Proposed change in Piece 2 |
|---|---|---|
| Prompt scope | No | **Stays no.** Locked. |
| `classification_status` | Yes (`ok`/`failed`/`unclassified`) | **No new value.** A `needs_review` status would be a schema + CHECK-constraint + contract change; the brief explicitly defers it to a separate sign-off. Use `audit_records` instead. |
| `audit_records` table emission | N/A (does not exist as a Piece 1 surface) | **NEW in Piece 2 (minimal write-only path):** when confidence < threshold OR Top-2 margin < threshold OR `secondary_domains != []`, append one row tagging the document for review. Schema below in §6. |
| Human review queue / consumption UI | Out of scope here | Piece 2.1 or later — read from `audit_records` |

**No `classification_status` value is added.** Avoiding the schema change keeps Piece 2 narrow.

---

## 4. Relation-scope dependency analysis (the four NULL-domain verbs)

Confirmed in DB at 2026-05:

| Relation | Rows in `ontology.relations` | All ACTIVE? | domain_id | Duplicate rows? |
|---|---:|---|---|---|
| `HOLDS_POSITION` | 2 | Yes | NULL | **Yes — 2 distinct UUIDs** |
| `WORKS_AT` | 1 | Yes | NULL | No |
| `REPORTS_TO` | 1 | Yes | NULL | No |
| `HAS_COMPENSATION` | 2 | Yes | NULL | **Yes — 2 distinct UUIDs** |

(Sibling duplicates also exist: `HELD_POSITION ×2`, `DEPENDS_ON ×2`, `TRIGGERED_BY ×2`, `LOCATED_IN ×2`, `MANAGES ×3`, `OWNS ×4`. **Piece 0.6 must address these, not just the four named.**)

### Per-relation needed-in-Piece-2 analysis

| Relation | Needed in Piece 2 prompts? | Why | Piece 0.6 prerequisite? | Notes |
|---|---|---|---|---|
| `HOLDS_POSITION` | **Yes** | Org-structure facts (CEO/CFO/VP/etc.) appear in every domain corpus we test (Nexus, Manus, Ontology Vault). Without it, scoped prompts cannot extract person-role assignments — the most common KG question class. | **Yes** | Should resolve to a single canonical row in `core`. The duplicate row is a governance defect. |
| `WORKS_AT` | **Yes** | Person→organization affiliation is universal across enterprise corpora. | **Yes** | Single canonical row in `core`. |
| `REPORTS_TO` | **Yes** | Reporting-chain queries (Nexus Q15, Q61 — already documented failure modes in `replit.md`) require this verb. | **Yes** | Single canonical row in `core`. |
| `HAS_COMPENSATION` | **Probably yes for finance docs; conditionally yes for HR docs** | HR/finance bridge. Less universal than the other three. | **Yes, but assignment is debatable** | Two canonical placements possible: (a) `core` (universal HR fact) or (b) `finance` (instrument-of-value). Recommend `finance` since compensation surfaces predominantly in 10-Ks, proxy statements, comp committee minutes — all finance documents. Document for review. |

### Piece 0.6 dependency conclusion

**Piece 0.6 is required before Piece 2 implementation if the system is to extract organizational-structure facts under domain-scoped prompts.** This is not optional.

**Piece 0.6 is itself audit-and-sign-off gated.** The three Piece-0.6 disposition options from the brief are evaluated below, but **no relation mutation is approved by the Piece 2 design alone.** The Piece 2 design's role is to record the recommendation; the disposition is decided by Piece 0.6's own audit and a separate sign-off.

- **(a) Retroactively bless into `00_shared_ontology.sql`:** **Design recommendation** for `HOLDS_POSITION`, `WORKS_AT`, `REPORTS_TO` likely → `core`; `HAS_COMPENSATION` likely → `finance` (open question — see §9 #4 and architecture.md Gap 6). Keeps existing UUIDs, no remapping, fastest. **Sibling duplicates should also be deduped in the same migration window.**
- **(b) Re-create under governed `PROPOSED → APPROVED → ACTIVE` flow with new UUIDs:** More principled, but requires migration to remap every referencing row in `relationships` table — not free, and the four verbs are already `ACTIVE`. Justified only if (a) is rejected for governance reasons.
- **(c) Leave unscoped, source from elsewhere in prompt builder:** **Recommend against.** Maintains the NULL-domain pool as a permanent bypass mechanism, undermining the architecture from the inside.

**Design recommendation: option (a) + sibling-duplicate cleanup, scoped as Piece 0.6 — pending Piece 0.6 audit and a separate sign-off, not approved by Piece 2.**

(This section is analysis only. No mutation. No migration is being proposed in this document.)

---

## 5. Proposed Piece 2 target behavior

```
Initial Piece 2 implementation (post Piece 0.6, post sign-off):

  Prompt scope formula:        core_types ∪ primary_domain_types
                               core_relations ∪ primary_domain_relations
  NULL-domain rows:            EXCLUDED from scoped prompt construction via explicit
                               domain-scoped repository calls. Repository no-filter
                               behavior remains unchanged for legacy/full-snapshot callers.
  Confidence policy:           No effect on scope. Triggers audit_records emission only.
  secondary_domains:           Reserved (always [] today). No-op in scope formula.
  document_type:               Reserved (no overlay). Piece 2.5.
  classification_status:       No new values. No schema change.
  Stage 1 path coverage:       OntologyCentricPipeline uses scoped prompts.
                               MultiModelExtractor remains on its existing prompt in Stage 1.
                               MultiModelExtractor adapter and prompt replacement are staged
                               behind separate sign-off, prompt diff review, and SHA verification.
```

The two prompts that change (entity extraction prompt, relationship extraction prompt) must both narrow to the scope above. System prompt unchanged.

---

## 6. Implementation boundaries

### Repository vs scoped prompt-builder behavior — load-bearing distinction

The "no full-union fallback" rule applies to **scoped prompt construction**, not to the underlying `OntologyRepository`. Globally breaking no-filter repository callers would break legacy/full-snapshot consumers (Gardener, validators, analytics, the existing `get_snapshot()` path). The enforcement lives at the prompt-builder layer:

- **Scoped prompt builder APIs require explicit scope:**
  - `build_entity_extraction_prompt(domain_id=None)` **must raise.**
  - `build_relationship_extraction_prompt(domain_id=None)` **must raise.**
  - Any new scoped prompt API must require an explicit `domain_id`.
- **Repository no-filter behavior is unchanged for legacy callers:**
  - `OntologyRepository.get_all_types()` (no domain filter) continues returning the full active set.
  - `OntologyRepository.get_all_relations()` (no domain filter) continues returning the full active set.
  - **Piece 2 must not globally break no-filter repository callers.**

Equivalently: scoping is a *prompt-construction* concern, not a *data-access* concern. The repository remains a neutral data layer; scope is a contract enforced at the prompt boundary.

### What Piece 2 implementation will change after sign-off

- `SchemaPromptGenerator.build_entity_extraction_prompt(...)` — gain a required `domain_id: str` parameter. No default. No `None` fallback (raises on `None`).
- `SchemaPromptGenerator.build_relationship_extraction_prompt(...)` — same.
- `OntologyRepository.get_all_types(domain_id=...)` — gain an **optional** `domain_id` filter. Calling without it continues to return the full active set (legacy contract preserved).
- `OntologyRepository.get_all_relations(domain_id=...)` — same.
- `OntologyCentricPipeline.extract(...)` — read `classification_metadata['primary_domain']` and pass to the scoped prompt builder. (The kwarg already exists from Piece 1.5; Piece 2 is the first piece that reads it.)
- `MultiModelExtractor` prompt assembly — staged change (see "MultiModelExtractor staging" below); not a silent replacement.
- **`audit_records` table (new — minimal Piece 2 deliverable, write-only).** Schema below.

### `audit_records` minimal schema (Piece 2 deliverable, NOT Piece 2.1)

```sql
CREATE TABLE platform.audit_records (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id   uuid REFERENCES platform.documents(id),
  signal_type   varchar(64) NOT NULL,   -- 'low_confidence' | 'narrow_margin' | 'multi_domain' | ...
  severity      varchar(16) NOT NULL,   -- 'info' | 'warn' | 'error'
  payload       jsonb NOT NULL,         -- e.g. {"confidence": 0.27, "primary_domain": "construction", "top_2_margin": 0.04}
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_records_document_id_idx ON platform.audit_records(document_id);
CREATE INDEX audit_records_signal_type_idx ON platform.audit_records(signal_type);
```

**Piece 2 boundaries on `audit_records`:**

- Piece 2 creates the minimal table and writes `low_confidence` / `narrow_margin` signals.
- Piece 2 **does not** build UI, review queue, routing, notifications, or any human workflow.
- Consumer logic (read paths, dashboards, queue routing, notification rules) is **Piece 2.1 or later**.
- Write-only. The signal must be persisted, not just logged — otherwise it disappears.

### MultiModelExtractor staging (load-bearing)

`MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT` is a hardcoded string that Piece 1.5 SHA-tracked specifically because it is load-bearing for the multi-model path. Piece 2 may intentionally change prompt behavior after sign-off, **but the rollout must be staged**:

1. **Stage 1 (in-scope for Piece 2 merge):** Implement scoped prompt generation in `SchemaPromptGenerator` and use it on the `OntologyCentricPipeline` path. The multi-model path continues to use its existing prompts unchanged.
2. **Stage 2 (later in Piece 2, separate sign-off):** Build a reviewed adapter that lets `MultiModelExtractor` consume the scoped prompt builder's output.
3. **Stage 3 (separate sign-off, prompt diff in PR):** Replace or bypass the hardcoded `EXTRACTION_SYSTEM_PROMPT`. Reviewer must see the literal old-vs-new prompt diff before merge.

**Piece 2 must not silently replace the multi-model prompt without reviewed prompt output.** SHA-tracking discipline from Piece 1.5 carries forward.

### What it must not change

- Gardener (no validation logic shift).
- Data Gates.
- v2 FactEvaluator (parked).
- Nexus benchmark hardcoding.
- `classification_wrapper` thresholds.
- `classification_status` CHECK constraint (no new value).
- Relation governance beyond Piece 0.6's narrow scope.
- Legacy no-filter `OntologyRepository` callers.

---

## 7. Test plan

Required tests before any Nexus re-run:

1. **Prompt scope contract.** For each of the 8 domains, build the entity prompt and assert: (a) every type listed is in `core ∪ that_domain`; (b) zero types from any other named domain; (c) zero NULL-domain types.
2. **NULL-domain exclusion.** Insert a sentinel NULL-domain type into the snapshot at test setup; assert it does not appear in any built prompt.
3. **Core-inclusion check.** Each scoped prompt must contain all 25 core types and all 17 (post-0.6: 20+) core relations.
4. **No full-union fallback at the prompt-builder layer.** Call `SchemaPromptGenerator.build_entity_extraction_prompt(domain_id=None)` and `build_relationship_extraction_prompt(domain_id=None)` — both must raise. **Test enforcement is at the scoped prompt-builder API layer, NOT by globally breaking `OntologyRepository` no-filter calls** — legacy `get_all_types()` / `get_all_relations()` no-filter callers must continue returning the full active set (separate test asserting this contract is preserved).
5. **Token-count regression budget.** Snapshot prompt token count per domain and fail CI if any domain's prompt exceeds 1.5× its post-Piece-2 baseline.
6. **Snapshot tests.** Capture the exact prompt string for one canonical (domain, document_type) pair per domain and diff on every change. Reviewer must approve the diff.
7. **`audit_records` minimal-write tests.** (a) Mock a doc with confidence 0.25; assert one `audit_records` row inserted with `signal_type='low_confidence'`, payload containing the confidence value, scope unchanged. (b) Mock a doc with Top-2 margin 0.03; assert one row with `signal_type='narrow_margin'`. (c) Verify the table exists with the §6 schema. (d) Confirm Piece 2 ships **no** consumer/UI/queue code reading from this table.
8. **Both paths covered (staged, per §6 staging).** Stage 1: assert `OntologyCentricPipeline` uses scoped prompts. Multi-model path remains on its existing prompt — assert this explicitly (no silent replacement). Stage 2/3 multi-model adapter + prompt replacement land under separate sign-off with a literal old-vs-new prompt diff in the PR.
9. **3–5 doc end-to-end smoke.** On a small Nexus subset, before/after Piece 2: report (a) prompt size delta per doc, (b) extracted entity count delta, (c) extracted relation count delta. Acceptance: extraction still runs to completion with `errors=0` and no domain-misclassification regressions.
10. **Prompt-SHA discipline.** Same SHA-tracking style as Piece 1 / Piece 1.5 — capture pre-Piece-2 SHAs of all prompt-bearing files; any diff is expected for the ontology-path prompts and must be reviewed line-by-line. The `MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT` SHA must remain unchanged in Stage 1.

---

## 8. Required sign-off points before Piece 2 implementation

| # | Gate | Recommendation |
|---|---|---|
| 1 | Prompt-scope policy | **Option D**: `core ∪ primary_domain`. No widening. |
| 2 | Confidence/margin policy | Provisional sentinels `< 0.30` confidence, `< 0.05` Top-2 margin → `audit_records` emission only. **No effect on scope.** Staged revision per §3 threshold revision plan (Piece 2.5 first review, longer-term labeled-set calibration). |
| 3 | Whether Piece 0.6 is required | **Yes** — Piece 0.6 is required before Piece 2 implementation. Piece 0.6 is itself audit-and-sign-off gated. **Design recommendation** (not approved by Piece 2): `HOLDS_POSITION` / `WORKS_AT` / `REPORTS_TO` likely → `core`; `HAS_COMPENSATION` likely → `finance`. Disposition decided by Piece 0.6 audit + a separate sign-off, not by this design. |
| 4 | Whether core inclusion is automatic | **Yes.** Always included unconditionally. Tested by §7 #3. |
| 5 | Confirmation no full-union fallback **at the prompt-builder layer** | **Confirmed.** §7 #4 enforces this at the scoped prompt-builder API only. Repository no-filter callers preserved (legacy contract — see §6 "Repository vs scoped prompt-builder behavior"). |
| 6 | Schema/contract change for `needs_review` | **None proposed.** Use new `audit_records` table instead. |
| 7 | `audit_records` minimal write-only path is in Piece 2 | **Yes — Piece 2 deliverable** (§6 schema). Piece 2 creates the table and writes signals. UI / consumer / review queue / routing / notifications are explicitly **not** in Piece 2 — Piece 2.1 or later. |
| 8 | MultiModelExtractor staging | **3-stage rollout** per §6: Stage 1 (Piece 2 merge) ontology path only; Stage 2 reviewed adapter; Stage 3 explicit prompt diff review before any `EXTRACTION_SYSTEM_PROMPT` replacement. No silent multi-model prompt replacement. |

---

## 9. Open questions

These cannot be resolved in this design without separate input or measurement:

1. **Should `core` be implicitly always-included, or always-included-but-explicit?** Recommend explicit (`core ∪ primary`) so the union is auditable in code and tests, not implicit in repository behavior.
2. **What does the system do when classification fails (`status='failed'`)?** Currently the document just doesn't get classified — extraction still runs via `OntologyCentricPipeline`'s internal `classify_with_fallback`. Under Piece 2, when `primary_domain` is NULL, what scope is used? **Recommend: skip extraction and emit `audit_records` row.** Decision required.
3. **Where does `classify_with_fallback` (the pipeline-internal fallback) live in this picture?** It returns `document_type` only, not `primary_domain`. After Piece 2, both paths read `primary_domain` from the persisted classification metadata. The internal fallback becomes dead code OR is repurposed to populate `secondary_domains` on disagreement with the wrapper. Decision required.
4. **`HAS_COMPENSATION` placement.** §4 recommends `finance`; reasonable alternative is `core`. Sign-off needed.
5. **Audit-records consumption.** Is there a UI commitment in Piece 2.1, or do `audit_records` write-only into the void until a separate epic? Decision required so we don't ship governance theater.
6. **Held-out measurement set.** Who labels the ground-truth domains for ~240 docs? This is the biggest open dependency to setting real thresholds.

---

**No code changed. No prompts changed. No DB mutated. Design proposal only.**
