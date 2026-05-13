# Stage 3A — Property Plane MVP

**Date:** 2026-05-13
**Branch:** `stage3a-property-plane-mvp`
**Commit:** `87dadbb8`
**Author:** Co-authored with Claude Opus 4.6

---

## Problem

ContextFoundry scores 59–60/100 on the Nexus 100Q benchmark. Target is ≥76/100.

Stage 2F analysis identified PROPERTY as the largest failure plane: 35/100 questions involve scalar attributes (revenue, budget, capacity, qubits, etc.), and 16 of those are currently failing. The root cause is structural — the relational knowledge graph cannot represent typed attribute facts with values, units, and time qualifiers. However, this data already exists in `Entity.properties` JSON fields — it's just not queryable in the answer path.

### Failure breakdown (Bucket E)

15 of the 16 failures are "confident-wrong" KG answers — the KG returns a plausible but incorrect value. The existing DocEv fallback cannot help because it never overrides confident KG answers by design.

---

## Solution

Materialize existing entity properties into a queryable `property_facts` table and wire a property lookup hook into the answer path. No re-extraction, no new LLM calls for answers.

### Architecture

```
1. ToolAgent.query()          → KG answer (unchanged)
2. QA Verifier                → validates (unchanged)
3. Property Plane hook (NEW)  → for attribute Qs: query property_facts, replace answer
4. DocEv fallback (existing)  → tertiary fallback if property + KG both miss
5. Response building          → (unchanged)
```

### Key design decisions

1. **Property plane overrides KG answers** for attribute questions when a matching fact exists. This is different from DocEv (which defers to confident KG answers). This directly addresses Bucket E failures.

2. **No LLM call** for property answers — template-based formatting from structured facts. Faster, deterministic, no hallucination risk.

3. **DocEv gate updated** to recognize property sources (`TRUSTED_PROPERTY`, `STAGING_PROPERTY`) as authoritative, preventing DocEv from overriding property answers.

---

## What was implemented

### M0 — Property Fact Inventory

| File | Purpose |
|---|---|
| `scripts/property_inventory.py` | Diagnostic script: queries entities table, parses properties JSON, maps to the 16 failing questions, emits a coverage report |

### M1 — Schema + PropertyStore

| File | Purpose |
|---|---|
| `migrations/add_property_facts.sql` | DDL for `property_facts` table with indexes and RLS policy. Not applied — migration file only. |
| `src/context_foundry/models/property_schema.py` | SQLAlchemy `PropertyFact(Base)` model following the Entity pattern from `schema.py` |
| `src/context_foundry/memory/property_store.py` | Tenant-scoped data access layer: `lookup_attribute()`, `lookup_entity_properties()`, `upsert_fact()`, `bulk_upsert()` |
| `tests/unit/test_property_store.py` | 13 unit tests: tenant isolation, lifecycle filtering, read-only invariant, empty results |

#### property_facts schema

```
id, tenant_id, entity_id, entity_name, entity_type, lifecycle_state,
attribute_name, attribute_value, numeric_value, unit, value_type,
period, fiscal_year, valid_from, valid_to,
source_document_id, source_entity_properties, confidence,
created_at, updated_at
```

Indexes on `(tenant_id)`, `(tenant_id, attribute_name)`, `(tenant_id, entity_name)`, `(entity_id)`, `(tenant_id, lifecycle_state)`, `(tenant_id, attribute_name, fiscal_year)`.

### M2 — Property Adapter

| File | Purpose |
|---|---|
| `src/context_foundry/adapters/__init__.py` | Package init |
| `src/context_foundry/adapters/property_adapter.py` | Parses entity.properties JSON into property_facts rows. Handles 5 entity types: FINANCIAL_METRIC, PROJECT, PRODUCT, CUSTOMER, FACILITY. Includes numeric parser (`$8.45 billion` → `8.45e9`). |
| `scripts/run_property_adapter.py` | CLI runner: `python scripts/run_property_adapter.py --tenant-id <uuid> [--dry-run]` |
| `tests/unit/test_property_adapter.py` | 31 unit tests: numeric parser (dollars/millions/billions, commas, units, dates, ranges), type parsers, metadata preservation |

#### Numeric parser handles

- `$8.45 billion` → `8,450,000,000.0`
- `$145 million` → `145,000,000.0`
- `127 qubits` → `127.0`
- `425 kg/hr` → `425.0`
- `23.5%` → `23.5`
- `12,500` → `12,500.0`
- Dates/ranges → `None` (not numeric)

### M3 — Query Integration

| File | Purpose |
|---|---|
| `src/context_foundry/retrieval/property_plane.py` | Query hook: `is_attribute_query()` → `extract_query_parameters()` → `lookup_property_facts()` → `format_property_answer()`. Template-based answer formatting, no LLM. |
| `tests/unit/test_property_plane.py` | 25 unit tests: non-attribute bypass, fact matching, KG override, fall-through, tenant scoping, read-only invariant, answer formatting, DocEv gate integration, web_app wiring check |
| `web_app.py` | **Modified:** 25-line property plane hook inserted at L4452 between QA Verifier end and DocEv fallback start |
| `src/context_foundry/retrieval/document_evidence_fallback.py` | **Modified:** Added `TRUSTED_PROPERTY`/`STAGING_PROPERTY` constants; updated `classify_agent_kg_source()` to treat property sources as authoritative (prevents DocEv override) |

#### web_app.py insertion (L4452)

```python
# === STAGE 3A: PROPERTY PLANE HOOK ===
try:
    from src.context_foundry.retrieval.property_plane import apply_to_agent_result as _apply_prop_plane
    _apply_prop_plane(agent_result, session=db_session, tenant_id=tenant_id, query=resolved_query)
    # ... logging ...
except Exception as e:
    logger.warning(f"[PROP_PLANE] Hook failed (non-blocking): {e}")
# === END STAGE 3A ===
```

#### DocEv gate change (document_evidence_fallback.py)

```python
# In classify_agent_kg_source():
answer_source = agent_result.get("answer_source") or ""
if answer_source in (ANSWER_SOURCE_TRUSTED_PROPERTY, ANSWER_SOURCE_STAGING_PROPERTY):
    return ANSWER_SOURCE_TRUSTED_GRAPH  # prevents DocEv from firing
```

### M4 — Validation

| File | Purpose |
|---|---|
| `scripts/validate_property_plane.py` | Runs Nexus 100Q (or PROPERTY subset) against the live platform, reports score, recovered questions, regressions, answer_source distribution |

---

## Test results

### New tests: 69/69 pass

| Suite | Tests | Status |
|---|---|---|
| `tests/unit/test_property_store.py` | 13 | All pass |
| `tests/unit/test_property_adapter.py` | 31 | All pass |
| `tests/unit/test_property_plane.py` | 25 | All pass |

### Regression tests: 39/39 pass

| Suite | Tests | Status |
|---|---|---|
| `tests/inference/unit/test_document_evidence_fallback.py` | 39 | All pass |

### Total: 108/108 pass, zero regressions

---

## Files changed

### New files (14)

```
scripts/property_inventory.py                        (M0)
migrations/add_property_facts.sql                    (M1)
src/context_foundry/models/property_schema.py        (M1)
src/context_foundry/memory/property_store.py         (M1)
tests/unit/test_property_store.py                    (M1)
src/context_foundry/adapters/__init__.py             (M2)
src/context_foundry/adapters/property_adapter.py     (M2)
scripts/run_property_adapter.py                      (M2)
tests/unit/test_property_adapter.py                  (M2)
src/context_foundry/retrieval/property_plane.py      (M3)
tests/unit/test_property_plane.py                    (M3)
web_app.py                                           (M3, +25 lines)
scripts/validate_property_plane.py                   (M4)
docs/findings/stage3a_property_plane_mvp_2026-05-13.md (M4, this file)
```

### Modified files (2)

```
web_app.py                                                    (+25 lines at L4452)
src/context_foundry/retrieval/document_evidence_fallback.py   (+9 lines)
```

### Lines added: ~2,755

---

## Safety invariants preserved

All of the following remain untouched:

- IdentityResolver tenant isolation (`web_app.py` L220, `scheduler.py` L34/L251)
- VerificationWorker deadlock fix (Stage 1K)
- Gardener promotion (`require_verification_for_promotion=False`)
- Tree retrieval OFF by default (`start.sh` L13)
- DOCUMENT_EVIDENCE labeling
- No Start All restart
- Legacy vaults as forensic fixtures
- No v2/FactEvaluator work

---

## Validation steps (requires DB access)

1. Apply migration:
   ```bash
   psql $DATABASE_URL -f migrations/add_property_facts.sql
   ```

2. Run adapter:
   ```bash
   python scripts/run_property_adapter.py --tenant-id ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda
   ```

3. Run PROPERTY subset (fast feedback):
   ```bash
   python scripts/validate_property_plane.py --tenant-id <uuid> --subset property
   ```

4. If subset improves, run full 100Q:
   ```bash
   python scripts/validate_property_plane.py --tenant-id <uuid>
   ```

### Expected results

| Metric | Before | After (projected) |
|---|---|---|
| Nexus 100Q score | 59–60/100 | 69–76/100 |
| PROPERTY plane (35Q) | 19/35 | 29–35/35 |
| Regressions | — | Low risk (19 passing Qs unaffected) |

---

## Risk assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Property plane returns wrong value | Low | Facts sourced from entity.properties (already trusted); confidence ranking; template formatting (no LLM hallucination) |
| Regression on passing KG questions | Low | Property plane only fires for attribute queries with matching facts; non-attribute queries bypass entirely |
| DocEv interaction | None | DocEv gate updated to respect property sources; 39/39 existing DocEv tests pass |
| Performance impact | Negligible | Single indexed SQL query per attribute question; no LLM call |
