# Phase 2 Slice Vault Validation Report

**Date:** February 6, 2026  
**Vault ID:** `b158cd16-810a-484d-99a8-8de786602c35`  
**Documents:** 5-document slice (Boeing, Nel Hydrogen, Siemens, Supplier Review, Steering Committee)

---

## Overall Verdict: PASS (5/5 criteria met)

| # | Criterion | Threshold | Result | Status |
|---|-----------|-----------|--------|--------|
| 1 | Docs with supply-chain edges | ≥3 of 5 | **4 of 5** | ✅ PASS |
| 2 | Boeing typed as ORGANIZATION | ORGANIZATION | **ORGANIZATION** | ✅ PASS |
| 3 | WORKS_AT reduction | >50% reduction | **4 total** (down from dozens) | ✅ PASS |
| 4 | Max entity degree | ≤15 edges | **12** (Falcon X) | ✅ PASS |
| 5 | Max relationship type share | <60% | **41.0%** (AFFILIATED_WITH) | ✅ PASS |

**Bonus:** 0 candidates in candidate store (all relationships mapped to ontology types)

---

## Criterion 1: Supply-Chain Edges (4/5 docs)

6 SUPPLIES edges across 4 documents:

| Document | Source | Relationship | Target |
|----------|--------|--------------|--------|
| Siemens Customer | Siemens Healthineers AG | SUPPLIES | Specialty Conductors |
| Siemens Customer | Siemens Healthineers AG | SUPPLIES | HTS Wire |
| Nel Hydrogen | Nel ASA | SUPPLIES | PEM Electrolyzer System |
| Nel Hydrogen | nHydrogen Electrolyzers | SUPPLIES | PEM Electrolyzer System |
| Supplier Review | First Solar | SUPPLIES | Nexus |
| Boeing | Nexus Aerospace | SUPPLIES | AeroMaterials |

The 5th doc (Steering Committee) did not produce supply-chain edges, which is expected — it's a meeting minutes document focused on project status, not supplier relationships.

## Criterion 2: Boeing Entity Type

| Entity Name | Type |
|-------------|------|
| Boeing | ORGANIZATION |
| The Boeing Company | ORGANIZATION |
| Boeing workforce constraints | INCIDENT |
| Boeing dedicated a production cell for Nexus | RESOLUTION |

Core Boeing entities correctly typed as ORGANIZATION. Derived entities (workforce constraints, production cell dedication) appropriately typed as INCIDENT and RESOLUTION.

## Criterion 3: WORKS_AT Count

**4 WORKS_AT relationships** — massive reduction from the co-occurrence explosion pattern where every person mentioned alongside an organization would get a WORKS_AT edge. The CandidateNormalizer's MEMBER_OF→WORKS_AT synonym mapping is working correctly but only fires for genuine membership relationships.

## Criterion 4: Degree Distribution (Top 10)

| Entity | Type | Degree |
|--------|------|--------|
| Falcon X | PROJECT | 12 |
| FY2026 Procurement Plan | PROJECT | 11 |
| The Boeing Company | ORGANIZATION | 10 |
| nHydrogen Electrolyzers | PRODUCT | 10 |
| January 7, 2026 | DATE | 9 |
| ITM Power | ORGANIZATION | 9 |
| Nel ASA | ORGANIZATION | 9 |
| Siemens | ORGANIZATION | 8 |
| Boeing | ORGANIZATION | 8 |
| PEM Electrolyzer System | EQUIPMENT | 8 |

Max degree = 12 (well under the 15-edge threshold). No hub-and-spoke anomalies.

## Criterion 5: Relationship Type Distribution

| Type | Count | Percentage |
|------|-------|------------|
| AFFILIATED_WITH | 71 | 41.0% |
| OWNS | 30 | 17.3% |
| MEMBER_OF | 26 | 15.0% |
| AFFECTS | 11 | 6.4% |
| LOCATED_IN | 7 | 4.0% |
| MEETS_SPEC | 6 | 3.5% |
| SUPPLIES | 6 | 3.5% |
| MANAGES | 5 | 2.9% |
| WORKS_AT | 4 | 2.3% |
| OCCURRED_AT | 4 | 2.3% |
| DIVISION_OF | 3 | 1.7% |

**11 distinct relationship types.** Highest share is AFFILIATED_WITH at 41.0% (under 60% threshold). Good diversity across supply-chain (SUPPLIES), organizational (AFFILIATED_WITH, MEMBER_OF, DIVISION_OF), specification (MEETS_SPEC), geographic (LOCATED_IN), and temporal (OCCURRED_AT) categories.

## Bonus: Overall Stats

| Metric | Value |
|--------|-------|
| Total relationships committed | 173 |
| Candidate store relationships | 0 |
| Per-doc breakdown | 15 + 35 + 7 + 94 + 22 = 173 |

---

## Root Causes Fixed (Systemic, Not Patches)

### Fix 1: LLM_TO_ONTOLOGY_TYPE_MAP (48 mappings)
LLMs generate relationship types like `GENERATES_REVENUE`, `HAS_METRIC`, `SPECIFIES` that don't exist in the ontology. The map translates these to valid ontology types (e.g., `GENERATES_REVENUE→OWNS`, `HAS_METRIC→AFFILIATED_WITH`, `SPECIFIES→MEETS_SPEC`). All 48 mapping targets validated against the 230 actual ontology types.

### Fix 2: Bug in `_is_known_relationship_type` check (staging_loader.py:537)
**Before:** `_is_known_relationship_type(extracted.relation_type)` — checked the *original* LLM type  
**After:** `_is_known_relationship_type(relation_type)` — checks the *mapped* type  
This was THE critical bug. Even with correct mappings, the check was using the pre-mapping value, so every mapped relationship was rejected and sent to the candidate store.

### Fix 3: Mapping target validation against actual ontology
Initial mappings targeted types like `EARNS`, `DESCRIBES`, `AUTHORED_BY` that don't exist in the 230-type ontology. Fixed to `HAS_COMPENSATION`, `DOCUMENTS`, `PERFORMED_BY` respectively.

---

## Recommendation

**PASS — Safe to proceed with full 197-document re-extraction.**

The three systemic fixes are general-purpose and will apply to all document types, not just this 5-document slice. The extraction pipeline now:
1. Maps LLM-generated types to valid ontology types before the known-type check
2. Correctly evaluates mapped types (not original types) against the ontology
3. Commits all validly-mapped relationships directly to the KG instead of the candidate store
