# Accuracy Failures Analysis - 87% (87/100)

**Date:** February 2, 2026  
**Test Corpus:** ClaudeCode Nexus Industries  
**Vault ID:** 1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91  
**Baseline:** 84% → **Current:** 87% (+3 points)  
**Hallucination Rate:** 0%

---

## Summary

The system achieved 87% accuracy with zero hallucinations. The remaining 13 failures require architectural improvements, not patches.

## Failing Questions (13)

### Role Resolution Failures (4)

| Q# | Question | Expected | Issue |
|----|----------|----------|-------|
| Q37 | Who is the Director of GreenHydrogen? | David Park | Multi-hop traversal not triggering - role entity not found via blacklist path |
| Q75 | Who is VP of Engineering for Nexus Digital Solutions? | Dr. Alan Chen | Same - role resolution returns position not person |
| Q91 | Who is VP Trade Compliance? | Owns Export Control Policy (POL-009) | Returns multiple VPs instead of following relationship |
| Q68 | Who chairs the Export Control Committee? | VP Trade Compliance | Role → person lookup incomplete |

### Multi-Entity Aggregation Failures (3)

| Q# | Question | Expected | Issue |
|----|----------|----------|-------|
| Q29 | Who are the Executive Team members? | List of executives | Aggregation returns incomplete list |
| Q34 | Which project has the largest budget? | Project with $XXM | Multiple budget values, wrong selection |
| Q100 | What is total value of top 3 customers? | Boeing + DoD + Airbus = $1.975B | Aggregation not summing correctly |

### Financial/Numeric Retrieval Failures (3)

| Q# | Question | Expected | Issue |
|----|----------|----------|-------|
| Q66 | What is FY2026 capex? | $XX million | Wrong fiscal year data retrieved |
| Q79 | What is 2030 revenue target? | $15 billion | Document text preferred over KG |
| Q45 | When did Victoria Chen become CEO? | Date | Temporal relationship not extracted |

### Entity Resolution Failures (3)

| Q# | Question | Expected | Issue |
|----|----------|----------|-------|
| Q14 | When was Robert Kim appointed? | Appointment date | Wrong Robert Kim resolved (multiple entities) |
| Q32 | Who is CEO of Toyota JV? | Person name | JV entity not linked to leadership |
| Q71 | Who is the mining automation partner? | Caterpillar | Partner relationship not retrieved |

---

## Root Causes (Architectural)

### 1. Retrieval Ranking
- Correct data exists in KG but wrong entities get selected
- Document text often preferred over KG relationships
- Semantic similarity scores not discriminating well

### 2. Incomplete Multi-Hop Traversal
- Role → person lookups not completing through all code paths
- Multi-hop code exists but doesn't trigger in Stage 0
- Role entities flow through different resolution path

### 3. Aggregation Reliability
- Multi-entity queries return partial results
- Counting/summing operations inconsistent
- Entity scope not properly bounded

### 4. Ambiguous Entity Resolution
- Multiple entities with same/similar names
- Temporal context not considered
- Organization scope not applied consistently

---

## Assets Created (For Future Use)

1. **Multi-hop Traversal Function**: `_resolve_role_via_multihop()` in `role_resolver.py`
   - Ready to use when role entities flow through correct path

2. **HAS_SPEC Relationships**: 5 new relationships in KG
   - Links products to technical specifications

---

## Recommended Roadmap Items

To reach 90%+, implement these architectural improvements:

### 1. Evidence Layer Verification Loop
- Post-retrieval verification of answer correctness
- Re-query with different strategies if confidence low

### 2. Tree-Based Retrieval
- Hierarchical entity traversal from anchor organization
- Prioritize KG relationships over document text

### 3. Ontology Pipeline Integration
- Enforce ontology constraints during retrieval
- Type-aware entity resolution

### 4. Enhanced Role Resolution
- Unified role → person pipeline
- Multi-hop by default for all role queries

---

## Test Artifacts

- Results: `test_results/claudecode_nexus_industries_20260202_080440.json`
- Traces: `test_results/traces/claudecode_nexus_industries_trace_summary_1f3320cd.json`
