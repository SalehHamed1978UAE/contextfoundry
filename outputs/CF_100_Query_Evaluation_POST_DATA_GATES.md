# Context Foundry Evaluation - POST DATA GATES

**Date**: 2025-12-10 20:02:55
**Queries Evaluated**: 10

## Comparison Results

| Metric | BEFORE PIPELINE FIX | AFTER PIPELINE FIX | AFTER DATA GATES |
|--------|---------------------|--------------------|--------------------|
| Hallucination Rate | 1.0% | 26.7% | **0.0%** |
| NOT_FOUND Rate | 19.0% | 0.0% | **10.0%** |
| GATED (New!) | N/A | N/A | **40.0%** |
| Accurate | 23.0% | 26.7% | **10.0%** |
| Partial | 54.0% | 46.7% | **40.0%** |

## Gate Triggers
- No Relationships: 3
- Entity Not Found: 0
- Sparse Data: 1

## Result Distribution

| Category | Count | Percentage |
|----------|-------|------------|
| ACCURATE | 1 | 10.0% |
| PARTIAL | 4 | 40.0% |
| GATED | 4 | 40.0% |
| NOT_FOUND | 1 | 10.0% |
| HALLUCINATED | 0 | 0.0% |
| ERROR | 0 | 0.0% |

## Individual Results

| Query ID | Result | Confidence | Grounded | Data Gap |
|----------|--------|------------|----------|----------|
| IA-001 | ACCURATE | 0.765 | False | None |
| IA-002 | GATED | 1.0 | True | no_relationships |
| IA-003 | PARTIAL | 0.49500000000000005 | False | None |
| HA-001 | NOT_FOUND | 0.0 | False | None |
| HA-002 | GATED | 1.0 | True | no_relationships |
| DEP-001 | PARTIAL | 0.49500000000000005 | False | None |
| DEP-002 | PARTIAL | 0.49500000000000005 | False | None |
| OWN-001 | GATED | 1.0 | True | no_relationships |
| OWN-002 | GATED | 0.7 | True | sparse_data |
| ESC-001 | PARTIAL | 0.49500000000000005 | False | None |


## Conclusion

The 4-LLM Consensus Data Gates architecture:
- Gates queries BEFORE LLM invocation when insufficient data exists
- Prevents hallucination by architectural design, not post-hoc filtering
- Returns grounded "no data" responses with confidence=1.0 for entities with 0 relationships
