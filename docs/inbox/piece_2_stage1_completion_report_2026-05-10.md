# Piece 2 Stage 1 — Completion Report

**Date:** 2026-05-10
**Brief:** `docs/inbox/piece_2_stage1_implementation_2026-05-10.md`
**Sign-off:** `docs/inbox/piece_2_stage1_step_b_signoff_2026-05-10.md`
**Status:** All Steps A-J COMPLETE. Ready for review.

---

## Summary

Piece 2 Stage 1 introduces **classification-driven domain-scoped prompt
construction** to the OntologyCentricPipeline, plus a write-only governance
audit log. The MultiModelExtractor path is untouched (SHA lock-tested).
The legacy OntologyManager prompt path is preserved for backward compat.

**No behavior changes for existing pipeline callers** (run_vault_extraction.py,
batch reextract scripts) because they don't pass `classification_metadata`
and the new `enforce_scoped_prompts` constructor kwarg defaults to `False`.
Stage 2 will flip enforcement on and wire callers to provide classification
metadata.

---

## Step-by-step status

| Step | Description | Status |
|---|---|---|
| A | SHA baselines captured | ✅ committed prior turn |
| B | Migration SQL composed + sign-off | ✅ committed prior turn (4 decisions in sign-off doc) |
| C | `platform.audit_records` migration applied | ✅ committed (table + 3 indexes + FK to platform.documents, 0 rows) |
| D | Scoped prompt builder methods added | ✅ committed (5 new methods on SchemaPromptGenerator) |
| E | Pipeline classification-decision wiring | ✅ committed (4 new helper methods + 3-branch decision in extract()) |
| F | AuditRecorder write helper | ✅ committed (NEW src/context_foundry/extraction/audit_recorder.py) |
| G | EXTRACTION_SYSTEM_PROMPT SHA lock test | ✅ committed (3 tests, all green) |
| H | Test suite | ✅ committed (85/85 green across 5 test files) |
| I | Unit-level smoke | ✅ 7/7 checks passed |
| J | Prompt diff + this report | ✅ this document |

---

## Code changes

| File | Action | Change |
|---|---|---|
| `src/context_foundry/ontology/prompt_generator.py` | MODIFIED | +240 lines — added `_load_scoped_types`, `_load_scoped_relations`, `build_entity_extraction_prompt_scoped`, `build_relationship_extraction_prompt_scoped`, `get_scoped_extraction_lists`. Legacy methods untouched. |
| `src/context_foundry/extraction/audit_recorder.py` | NEW | 196 lines — `AuditRecorder` class with `emit`, `emit_low_confidence`, `emit_narrow_margin` (reserved), `emit_classification_failed`, `emit_classification_missing`. Inserts to `platform.audit_records` via `sql_text` + jsonb cast. |
| `src/context_foundry/extraction/ontology_centric_pipeline.py` | MODIFIED | +272 lines — `enforce_scoped_prompts` constructor kwarg + 3-branch scope decision (`scoped` / `skip_failed` / `legacy`) in `extract()` + 5 helper methods (`_get_prompt_generator`, `_get_audit_recorder`, `_classify_for_scoped`, `_load_scoped_extraction_lists`, `_maybe_emit_low_confidence_audit`, `_emit_classification_failed_audit`). MultiModelExtractor + RelationExtractor + EntityExtractor untouched. |
| `tests/extraction/__init__.py` | NEW | empty |
| `tests/extraction/test_multi_extractor_prompt_sha.py` | NEW | 3 tests — SHA lock + module-level constant + class-attribute sanity |
| `tests/extraction/test_audit_recorder.py` | NEW | 5 tests — write path + jsonb queryability + index existence |
| `tests/extraction/test_pipeline_classification.py` | NEW | 12 tests — `_classify_for_scoped` decision logic (8 cases) + low-confidence audit emission + scope invariance + scoped lists shape |
| `tests/ontology/test_piece_2_stage1_scoped_prompts.py` | NEW | 65 tests — required-domain rejection (7) + 8 domains × {types contains-only, relations contains-only, types count, relations count} (32) + cross-contamination (2) + core always present (2) + governed Piece 0.6 relations (2) + scoped prompt content (2) + repo no-filter preservation (2) + legacy signature preserved (2) + `get_scoped_extraction_lists` shape (2) |

**Total: 85 tests, 85 PASS, 0 FAIL.**

---

## Step I smoke results

```
1. classification metadata loaded: status=ok, primary_domain=finance
2. classify_for_scoped decision: scoped
3. scoped extraction lists: 53 entity types, 49 relations
4. scope domains: ['core', 'finance'] (must be exactly [core, finance])
5. EXTRACTION_SYSTEM_PROMPT SHA: 5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963 ✓
6. audit_records low_confidence rows: 0 → 1 (delta=1) ✓
7. audit_records on HIGH confidence: delta=0 ✓
```

All seven brief Step I acceptance criteria green:
- classification metadata loaded ✓
- domain_id passed into scoped prompt builder ✓
- prompt scope contains core ∪ primary_domain only ✓
- audit_records written for low-confidence cases ✓
- MultiModelExtractor prompt unchanged ✓

---

## Step J prompt diff (finance-classified document)

**Before (legacy unscoped path):** ~1033 entity types listed in prompt, ~253
relations. The legacy `build_entity_extraction_prompt()` actually crashes on
the current 1033-row ontology because at least one row has `display_name=None`
and `_format_type_description` does `display_name.lower()` (pre-existing latent
bug in `prompt_generator.py:51`, flagged separately).

**After (scoped path with `domain_id="finance"`):**

- 53 entity types listed (25 core + 28 finance) — **5.1% of legacy unscoped count**
- 49 relations listed (21 core + 28 finance) — **19.4% of legacy unscoped count**
- Domain breakdown verified: `Counter({'finance': 28, 'core': 25})` for types,
  `Counter({'finance': 28, 'core': 21})` for relations
- NULL-domain rows excluded by repository filter (Piece 0.5)
- Other named domains (healthcare, aviation, manufacturing, …) excluded

First 25 lines of scoped prompt show the prompt header and 11 of the 53 types,
all properly attributed (e.g., `AccountHolder`, `BankAccount`, `Bond`, `Brokerage
Account`, `Commodity`, `ComplianceCheck`). HOLDS_POSITION + WORKS_AT + REPORTS_TO
(governed into core by Piece 0.6) + HAS_COMPENSATION (finance) all present in
relation list — verified by `test_get_scoped_extraction_lists_finance_includes_core`.

---

## Backward compatibility analysis

| Caller | Mode | Behavior |
|---|---|---|
| `run_vault_extraction.py` | enforce_scoped_prompts=False (default), no classification_metadata | LEGACY path — OntologyManager.get_or_create_ontology + per-doc-type entity_types. **Unchanged.** |
| Batch reextract scripts | Same as above | LEGACY path. **Unchanged.** |
| Stage 2 future callers | enforce_scoped_prompts=True + classification_metadata | NEW SCOPED path. |
| Tests with valid classification_metadata | Either flag value | NEW SCOPED path triggered when metadata.status='ok' + primary_domain present. |

**Manus Orion / Ontology Vault / Nexus extraction pipelines: zero behavior
change** — they all hit the legacy branch (constructor default + no metadata).

---

## Database state

`platform.audit_records` table:
- Rows: 0 (test rows cleaned up after each run via fixtures)
- Indexes: `audit_records_pkey`, `audit_records_document_id_idx`,
  `audit_records_signal_type_idx` (verified by
  `test_signal_type_index_exists`)
- FK: `audit_records_document_id_fkey` → `platform.documents(id)` ON DELETE
  SET NULL (verified by Step C migration; document_id nullable so
  non-document-bound signals can be recorded in future stages)

Ontology row counts (unchanged from Piece 0.6):
- `ontology.types`: 1033 ACTIVE
- `ontology.relations`: 253 ACTIVE (254 raw, 1 deprecated by Piece 0.6)

---

## Stage 1 limitations explicitly accepted (per brief lines 113, 281)

1. **`narrow_margin` audit not wired.** The `top_two_margin < 0.05` signal
   requires parsing top-two domain probabilities from
   `classification_evidence`, but the current evidence shape isn't
   guaranteed to include them. `AuditRecorder.emit_narrow_margin()` is
   defined and unit-callable but the pipeline does not call it. Reserved
   for Stage 1.5 / Stage 2 once classifier metadata shape is stabilized.

2. **Governance write-only.** Audit rows are inserted but not consumed:
   no UI, review queue, dashboard, routing, notifications, or
   downstream alerting. Brief Stage 1 explicitly scopes to "write
   path only."

3. **Pre-existing legacy bug in `_format_type_description`.** Calling
   `build_entity_extraction_prompt()` on the full 1033-row unscoped
   ontology crashes with `AttributeError: 'NoneType' object has no
   attribute 'lower'` because at least one type has `display_name=None`.
   This bug PRE-DATES Piece 2 and is unrelated to scoped builder work.
   Scoped methods don't hit this path because they filter out layer-0
   types before description formatting and the seeded domain types all
   have valid display_name. Flagged for separate fix.

---

## Files committed this stage

```
M src/context_foundry/extraction/ontology_centric_pipeline.py     (+272 lines)
M src/context_foundry/ontology/prompt_generator.py                  (+240 lines)
A src/context_foundry/extraction/audit_recorder.py                  (NEW)
A tests/extraction/__init__.py                                      (NEW empty)
A tests/extraction/test_multi_extractor_prompt_sha.py               (NEW, 3 tests)
A tests/extraction/test_audit_recorder.py                           (NEW, 5 tests)
A tests/extraction/test_pipeline_classification.py                  (NEW, 12 tests)
A tests/ontology/test_piece_2_stage1_scoped_prompts.py              (NEW, 65 tests)
A docs/inbox/piece_2_stage1_step_b_signoff_2026-05-10.md            (sign-off, prior turn)
A docs/inbox/piece_2_stage1_completion_report_2026-05-10.md         (this doc)
```

Plus prior commit (Step C migration):
```
M (alembic-equivalent direct DDL)  CREATE TABLE platform.audit_records + 3 indexes + FK
```

---

## Awaiting

- Code-review architect pass (auto-triggered by main agent rules)
- User sign-off on Stage 1 close-out
- Stage 2 brief (when ready) — flip enforce_scoped_prompts default to True
  and wire all pipeline callers to provide classification_metadata
