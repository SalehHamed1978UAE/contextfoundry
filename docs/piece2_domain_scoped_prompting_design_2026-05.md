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

### What we measure before setting any threshold

1. **Confidence histogram** across a held-out set of ≥30 docs per domain spanning Nexus + Manus + Ontology Vault (≥240 docs total). Plot Top-1 score and Top-1−Top-2 margin.
2. **Extraction recall by confidence band** on the same set: compute what fraction of ground-truth entities/relations are extracted under Option D scoping, bucketed by classification confidence (e.g., `<0.20`, `0.20–0.30`, `0.30–0.40`, `>0.40`) and by Top-2 margin (`<0.05`, `0.05–0.10`, `>0.10`).
3. **False-domain rate**: for each held-out doc, has the wrapper picked the right domain? (Requires ground-truth domain labels — small effort, ≤30 minutes per corpus).

These three datasets together are sufficient to set a defensible threshold. **Without them, every threshold is a guess.**

### Temporary defaults for initial Piece 2 implementation

| Setting | Initial value | Reasoning |
|---|---|---|
| Prompt scope formula | `core ∪ primary_domain` | Locked by Option D |
| Confidence threshold for governance signal | `< 0.30` | Below 50% of all real-doc observations to date (0.26, 0.26, 0.34, 0.27, 0.27); strictly an interim audit trigger, not a behavior gate |
| Top-2 margin threshold for governance signal | `< 0.05` | All four real-doc cases observed have margins in 0.03–0.08 range; this triggers on the tightest cases |
| Prompt scope behavior at low confidence | **unchanged** | Option D — scope is never widened |

These thresholds are **sentinels for measurement**, not behavior gates. They populate the audit log so Piece 2.1 can revise them with data instead of intuition.

### What confidence affects, by surface

| Surface | Affected by confidence today? | Proposed change in Piece 2 |
|---|---|---|
| Prompt scope | No | **Stays no.** Locked. |
| `classification_status` | Yes (`ok`/`failed`/`unclassified`) | **No new value.** A `needs_review` status would be a schema + CHECK-constraint + contract change; the brief explicitly defers it to a separate sign-off. Use `audit_records` instead (§3.1 below). |
| `audit_records` table emission | N/A (does not exist as a Piece 1 surface) | **NEW:** when confidence < threshold OR Top-2 margin < threshold OR `secondary_domains != []`, append one row tagging the document for review. Schema spec is a Piece 2.1 deliverable. |
| Human review queue UI | Out of scope here | Piece 2.1 — read from `audit_records` |

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

**Piece 0.6 is required before Piece 2 implementation if the system is to extract organizational-structure facts under domain-scoped prompts.** This is not optional. The three Piece-0.6 disposition options from the brief evaluate as:

- **(a) Retroactively bless into `00_shared_ontology.sql`:** Recommended for `HOLDS_POSITION`, `WORKS_AT`, `REPORTS_TO` → `core`; `HAS_COMPENSATION` → `finance`. Keeps existing UUIDs, no remapping, fastest. **Must also dedupe sibling duplicates as part of the same migration.**
- **(b) Re-create under governed `PROPOSED → APPROVED → ACTIVE` flow with new UUIDs:** More principled, but requires migration to remap every referencing row in `relationships` table — not free, and the four verbs are already `ACTIVE`. Justified only if (a) is rejected for governance reasons.
- **(c) Leave unscoped, source from elsewhere in prompt builder:** **Recommend against.** Maintains the NULL-domain pool as a permanent bypass mechanism, undermining the architecture from the inside.

**Recommendation: option (a) + sibling-duplicate cleanup, scoped as Piece 0.6.**

(This section is analysis only. No mutation. No migration is being proposed in this document.)

---

## 5. Proposed Piece 2 target behavior

```
Initial Piece 2 implementation (post Piece 0.6, post sign-off):

  Prompt scope formula:        core_types ∪ primary_domain_types
                               core_relations ∪ primary_domain_relations
  NULL-domain rows:            EXCLUDED (must be enforced by repository)
  Confidence policy:           No effect on scope. Triggers audit_records emission only.
  secondary_domains:           Reserved (always [] today). No-op in scope formula.
  document_type:               Reserved (no overlay). Piece 2.5.
  classification_status:       No new values. No schema change.
  Path coverage:               Both MultiModelExtractor AND OntologyCentricPipeline must use
                               the same SchemaPromptGenerator scoping signature.
```

The two prompts that change (entity extraction prompt, relationship extraction prompt) must both narrow to the scope above. System prompt unchanged.

---

## 6. Implementation boundaries

### What Piece 2 implementation will change after sign-off

- `SchemaPromptGenerator.build_entity_extraction_prompt(...)` — gain a required `domain_id: str` parameter. No default. No `None` fallback.
- `SchemaPromptGenerator.build_relationship_extraction_prompt(...)` — same.
- `OntologyRepository.get_all_types(domain_id=...)` — gain `domain_id` filter; must reject `None` (no silent "all").
- `OntologyRepository.get_all_relations(domain_id=...)` — same.
- `OntologyCentricPipeline.extract(...)` — read `classification_metadata['primary_domain']` and pass to repository/prompt-builder. (The kwarg already exists from Piece 1.5; Piece 2 is the first piece that reads it.)
- `MultiModelExtractor` prompt assembly — same wiring at its prompt-construction site.
- `audit_records` table (new) — minimal schema for governance signal emission. Spec is a Piece 2.1 deliverable.

### What it must not change

- Gardener (no validation logic shift).
- Data Gates.
- v2 FactEvaluator (parked).
- Nexus benchmark hardcoding.
- `classification_wrapper` thresholds.
- `classification_status` CHECK constraint (no new value).
- Relation governance beyond Piece 0.6's narrow scope.

---

## 7. Test plan

Required tests before any Nexus re-run:

1. **Prompt scope contract.** For each of the 8 domains, build the entity prompt and assert: (a) every type listed is in `core ∪ that_domain`; (b) zero types from any other named domain; (c) zero NULL-domain types.
2. **NULL-domain exclusion.** Insert a sentinel NULL-domain type into the snapshot at test setup; assert it does not appear in any built prompt.
3. **Core-inclusion check.** Each scoped prompt must contain all 25 core types and all 17 (post-0.6: 20+) core relations.
4. **No full-union fallback.** Call `build_entity_extraction_prompt(domain_id=None)` — must raise, not return the union.
5. **Token-count regression budget.** Snapshot prompt token count per domain and fail CI if any domain's prompt exceeds 1.5× its post-Piece-2 baseline.
6. **Snapshot tests.** Capture the exact prompt string for one canonical (domain, document_type) pair per domain and diff on every change. Reviewer must approve the diff.
7. **Confidence-policy emission.** Mock a doc with confidence 0.25; assert one `audit_records` row written with reason='low_confidence'. Mock a doc with margin 0.03; assert one row with reason='narrow_margin'. Both: scope unchanged.
8. **Both paths covered.** Run the test in (1) once via `MultiModelExtractor` and once via `OntologyCentricPipeline` — same scope formula must apply to both.
9. **3–5 doc end-to-end smoke.** On a small Nexus subset, before/after Piece 2: report (a) prompt size delta per doc, (b) extracted entity count delta, (c) extracted relation count delta. Acceptance: extraction still runs to completion with `errors=0` and no domain-misclassification regressions.
10. **Prompt-SHA discipline.** Same SHA-tracking style as Piece 1 / Piece 1.5 — capture pre-Piece-2 SHAs of all prompt-bearing files; the diff is expected and must be reviewed line-by-line.

---

## 8. Required sign-off points before Piece 2 implementation

| # | Gate | Recommendation |
|---|---|---|
| 1 | Prompt-scope policy | **Option D**: `core ∪ primary_domain`. No widening. |
| 2 | Confidence/margin policy | Sentinels `< 0.30` confidence, `< 0.05` Top-2 margin → `audit_records` emission only. **No effect on scope.** Pending measurement on held-out set per §3. |
| 3 | Whether Piece 0.6 is required | **Yes.** Bless `HOLDS_POSITION`, `WORKS_AT`, `REPORTS_TO` to `core`; `HAS_COMPENSATION` to `finance`. Dedupe sibling duplicates. |
| 4 | Whether core inclusion is automatic | **Yes.** Always included unconditionally. Tested by §7 #3. |
| 5 | Confirmation no full-union fallback | **Confirmed.** §7 #4 enforces this in code. |
| 6 | Schema/contract change for `needs_review` | **None proposed.** Use new `audit_records` table instead. |
| 7 | New `audit_records` table schema | Deferred to Piece 2.1 design — not in Piece 2 critical path. |

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
