# Failure Analysis: 27 Remaining Nexus Failures (post Group D+E)

**Vault:** `176a4fb2-0bb4-4da3-9068-0e26268fca71` (Nexus 2/8/2026)
**Test run:** `test_results/claudecode_nexus_industries_20260507_134642.json`
**Score:** 73/100 (was 72 pre Group D+E)

## Headline finding

**Almost every "missing" entity is already in the KG.** This is overwhelmingly a **query-pipeline / retrieval / role-resolution problem**, not an extraction problem. A full re-extraction would not fix most of these failures.

A second, smaller finding: a **lifecycle bug** in `scripts/reextract_specs.py` was inserting newly-created `SPECIFICATION` entities with `lifecycle_state = NULL`, making them invisible to the retrieval layer. 27 entities (including the new `CAPEX_TOTAL $680 million` and `LONG_TERM_TARGET $15B by 2030`) were affected. **Fixed in this session** with a one-shot UPDATE + script patch.

---

## Bucket A — Lifecycle bug (FIXED, +2 expected on next run)

| Q | Question | Entity in KG | Issue |
|---|----------|--------------|-------|
| Q66 | FY2026 capex plan ($680M) | `CAPEX_TOTAL $680 million` (lifecycle=NULL) | Invisible to retrieval — fixed |
| Q79 | 2030 revenue target ($15B) | `LONG_TERM_TARGET $15B by 2030` (lifecycle=NULL) | Invisible to retrieval — fixed |

Patch applied: 27 entities promoted NULL → STAGING; `reextract_specs.py` INSERT now sets `lifecycle_state='STAGING'` and `status='active'` explicitly.

---

## Bucket B — True extraction gaps (need targeted re-extraction or new patterns)

| Q | Question | Source phrase available? | What's needed |
|---|----------|--------------------------|---------------|
| Q14 | Robert Kim appointed Pres date (Jan 15 2026) | YES (53 chunks mention "January 15") | Date metadata not attached to PERSON entity. Need APPOINTED_AS event with effective_date |
| Q29 | Executive Leadership Team members | YES (chunks list them) | Need ELT entity + MEMBER_OF relationships. No ELT entity exists, only `Executive Leadership` (PROJECT type — wrong) |
| Q40 | Total backlog ($12.4B) | YES ("**Backlog:** Record $12.4 billion") | LLM picks summed division backlogs ($11.5B). Need explicit FINANCIAL_METRIC for "total backlog: $12.4B" |
| Q45 | Chen appointed CEO (2019) | YES (chunks mention "Start Date: June 2019") | Date confusion across roles. Need APPOINTED_AS event with effective_date on Chen→CEO |
| Q60 | Phishing incident detected (Dec 12 2025 02:47 UTC) | YES ("December 12, 2025, 02:47 UTC") | Need INCIDENT entity with detected_at timestamp |
| Q76 | Total patent portfolio (2,412) | **NO** — exact phrase "2,412 patent" not in any chunk | Likely UNFIXABLE — source data missing |

**Bucket B: 5 fixable + 1 unfixable = +5 max via re-extraction with appointment/event/aggregation patterns.**

---

## Bucket C — Query-pipeline / role-resolution / retrieval (entities exist, can't be connected to query)

These are all cases where entities AND the relevant supporting entities both exist in KG, but the retrieval pipeline can't connect them.

### C.1 — Role/title resolution (subject "Who is X of Y?")

| Q | Question | Both entities exist? | What's missing |
|---|----------|----------------------|----------------|
| Q1 | CEO of Nexus Industries (Victoria Chen) | YES | HEADS / CEO_OF rel from Chen → Nexus not surfacing |
| Q2 | CFO (Michael Chang) — picks Robert Kim | YES | Multiple HEADS_FINANCE candidates; needs current-vs-historical disambiguation |
| Q3 | President of Nexus Digital (Robert Kim) | YES | PRESIDENT_OF rel missing or stale |
| Q37 | Project Director GreenHydrogen (Walsh) | YES | LEADS_PROJECT rel missing |
| Q38 | CISO (Walsh, formerly Robert Kim) | YES | HOLDS_ROLE → CISO with recency disambiguation |
| Q61 | Who replaced Anderson as Digital Pres | YES (Anderson + Robert Kim both exist) | SUCCEEDED_BY rel missing |
| Q68 | Chair of Export Control Cmte (Foster) | YES (Foster + Export Controls policy) | CHAIRS rel missing |
| Q75 | VP Engineering Digital (Alan Chen) | YES (Dr. Alan Chen) | HOLDS_ROLE rel missing |
| Q91 | VP Trade Compliance (per POL-009) | YES (VP Trade Compliance is a ROLE) | OWNS_POLICY rel from role → policy missing |

**9 questions. Pattern: PERSON ↔ ROLE ↔ ORGANIZATION/POLICY relationships not being created during extraction even though source text states them.**

### C.2 — Supplier/customer routing (entity exists, wrong selection)

| Q | Question | Entity in KG | What goes wrong |
|---|----------|--------------|-----------------|
| Q17 | Electrolyzer supplier for GreenHydrogen (Nel) | YES (`Nel Hydrogen --SUPPLIES--> Nexus`) | Supplier-of-product query returns Honeywell/Boeing/etc. — needs project-scoped supplier filter |
| Q46 | Solar panel supplier for Desert Sun (First Solar) | YES (`First Solar --SUPPLIES--> Nexus`) | Same — no project-scoped supplier resolver |
| Q48 | Primary customer HTS wire (Healthineers) | YES (`Siemens Healthineers` ORG) | Returns Boeing — needs product-scoped customer resolver |
| Q83 | Primary customer SmartGrid (Pacific Power) | YES (`Pacific Power` CUSTOMER) | Returns "Nexus Energy Systems" (its own division) — needs product-scoped customer filter excluding internal orgs |
| Q71 | Mining automation partner (Caterpillar) | YES (Caterpillar SUPPLIER) | Returns "Siemens" — needs domain-scoped partner resolver |
| Q18 | Hydrogen offtake partner (Shell) | YES (Shell ORG) | OFFTAKE_AGREEMENT_WITH rel not surfacing |

**6 questions. Pattern: need project/product-scoped supplier/customer routing instead of generic "highest-confidence supplier" selection.**

### C.3 — Specification ↔ subject linkage

| Q | Question | Entity in KG | What's missing |
|---|----------|--------------|----------------|
| Q24 | GreenHydrogen production capacity (425 kg/hr Phase 1) | YES (425 kg/hr SPEC + 850 kg/hr SPEC) | LLM picks 850 (full capacity) instead of 425 (Phase 1). Need Phase-1 disambiguation/preference |
| Q67 | Solid-state battery operating temp (-30 to 60°C) | YES (`Operating Temperature -30 to 60°C` SPEC) | Spec exists but no `HAS_SPEC` rel from "solid-state battery" → spec |
| Q93 | Solid-state battery electrolyte (LLZO) | YES (LLZO MATERIAL) | No `USES_MATERIAL` rel from solid-state battery → LLZO |

**3 questions. Pattern: standalone SPECIFICATION/MATERIAL entities created with no relationship to their parent product. The reextract script doesn't create relationships.**

### C.4 — Aggregation/ranking

| Q | Question | What's needed |
|---|----------|---------------|
| Q36 | Highest-TRIR division (Materials 1.24) | Returns Energy Systems — need MAX-aggregation over division→TRIR values |

**1 question. Existing AggregationEngine code path not being triggered for "highest X" queries.**

---

## Summary

| Bucket | Count | Action |
|--------|-------|--------|
| A — Lifecycle bug | 2 | **FIXED in-session** (+2 expected next run) |
| B — Extraction gaps (fixable) | 5 | Targeted re-extraction with new patterns: APPOINTED_AS event, INCIDENT entity, ELT roster, total-backlog metric |
| B — Extraction gaps (unfixable) | 1 | Q76 source data not present |
| C.1 — Role resolution | 9 | Query-pipeline: HOLDS_ROLE/HEADS rel creation during extraction + pipeline routing |
| C.2 — Supplier/customer routing | 6 | Query-pipeline: project/product-scoped supplier resolver |
| C.3 — Spec ↔ subject linkage | 3 | **Hybrid:** post-process to create HAS_SPEC/USES_MATERIAL rels |
| C.4 — Aggregation | 1 | Wire existing AggregationEngine into "highest X" query routing |

### Re-extraction would help (max +8): Bucket B fixable (5) + Bucket C.3 spec-linkage (3 — best done at extraction time)

### Code-only fixes would help (max +16): Bucket A (already done, +2) + C.1 role resolution (9) + C.2 supplier routing (6) + C.4 aggregation (1) — minus role-resolution items that need extraction-time relationship creation

### Recommendation

A **fresh-vault re-extraction is NOT the highest-leverage move.** Most failures are query-pipeline issues that will reproduce in a new vault unless we also fix the pipeline. Suggested order:

1. ✅ **Bucket A done** (+2 expected on next test run)
2. **Bucket C.3 hybrid script** — create HAS_SPEC/USES_MATERIAL rels for the standalone specs we already extracted (+3, no LLM cost)
3. **Bucket C.4 aggregation wiring** — small router change (+1)
4. **Bucket C.2 supplier/customer scoping** — query-pipeline change (+~3-6)
5. **Bucket C.1 role resolution** — needs extraction-time changes; only here do we want a fresh-vault re-extraction
6. **Bucket B targeted patterns** — APPOINTED_AS, INCIDENT, ELT, BACKLOG_TOTAL refinement
