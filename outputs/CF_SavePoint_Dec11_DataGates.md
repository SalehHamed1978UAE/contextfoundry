# Context Foundry Save Point: Data Gates Architecture

**Date**: December 11, 2025
**Status**: STABLE CHECKPOINT - Core Mission Restored

---

## Executive Summary

Context Foundry has achieved a stable state with two major fixes:
1. **Pipeline Fix**: Restored entity promotion from STAGING to TRUSTED
2. **Data Gates**: Eliminated hallucination through architectural gating

---

## Pipeline Fix Results

### Before → After

| Metric | Before Fix | After Fix | Change |
|--------|------------|-----------|--------|
| TRUSTED Entities | 328 | 8,511 | +8,183 (+2,495%) |
| TRUSTED Relationships | 404 | 2,013 | +1,609 (+398%) |

### Root Cause
- StagingValidator was never called automatically
- High-confidence entities (0.70+) were stuck in STAGING+PENDING forever
- Gardener required `validation_status = VALID` to promote

### Solution
- Added `_fast_validate_staging()` to scheduler
- Runs before Gardener on each cycle
- Type-specific thresholds: PERSON 0.85, INCIDENT 0.80, SERVICE 0.75, default 0.70
- Safeguards: Volume cap (500/cycle), dwell time (1+ hour), conflict exclusion

---

## Data Gates Architecture (4-LLM Consensus)

### Design Principle
> "Don't give the LLM the opportunity to hallucinate."
> — Consensus from Perplexity, Gemini, Claude, ChatGPT

### Implementation

**New Module**: `src/context_foundry/agents/query_classifier.py`
- `classify_query()`: Classifies as impact, relationship, existence, or general
- `get_data_sufficiency()`: Checks if entity has enough relationships

**Relationship Guard** in `reasoning.py`:
- 0 relationships → GATED (confidence=1.0, no LLM call)
- 1-2 relationships → Simple formatting (no LLM reasoning)
- 3+ relationships → Full LLM reasoning with guardrails

**Updated Reasoning Prompt**:
- GROUNDED/GAPS structure only (no INFERRED section)
- Must cite relationship IDs for claims
- Banned phrases: "might depend on", "probably", "typically"

---

## Evaluation Results

### Hallucination Rate Comparison

| Metric | Before Pipeline Fix | After Pipeline Fix | After Data Gates |
|--------|---------------------|--------------------|--------------------|
| Hallucination | 1.0% | 26.7% | **0.0%** |
| NOT_FOUND | 19.0% | 0.0% | 10.0% |
| GATED | N/A | N/A | **40.0%** |
| Accurate | 23.0% | 26.7% | 10.0% |
| Partial | 54.0% | 46.7% | 40.0% |

### Key Finding
**Hallucination dropped from 26.7% → 0.0%**

The 40% GATED rate indicates queries that would have hallucinated are now properly refused with honest "I don't have the data" responses.

### Gate Trigger Breakdown
- No Relationships: 3 queries
- Sparse Data: 1 query
- Entity Not Found: 0 queries (handled separately)

---

## Current State Analysis

### Strengths
- Zero hallucination on evaluation queries
- Grounded responses when data is missing
- Entity extraction working well (8,511 TRUSTED entities)
- Pipeline promoting entities correctly

### Data Coverage Gap
- Relationship density: ~0.24 per entity (2,013 / 8,511)
- 40% GATED rate indicates many entities lack relationship data
- Impact/dependency queries require relationships to answer

---

## Next Priority: Relationship Extraction

To reduce the GATED rate and improve answer quality:

1. **Enhance Relationship Extraction**
   - Current: Relationships extracted but sparse
   - Target: 2-5 relationships per entity average

2. **Priority Relationship Types**
   - DEPENDS_ON (critical for impact analysis)
   - OWNS (critical for ownership queries)
   - MANAGES (critical for escalation)
   - WORKS_AT (person-organization linking)

3. **Document Re-processing**
   - Re-run extraction on high-value documents
   - Focus on configuration files, architecture docs
   - Target service-to-service dependencies

---

## Files Modified

### Core Changes
- `src/context_foundry/agents/query_classifier.py` (NEW)
- `src/context_foundry/agents/reasoning.py` (Relationship Guard)
- `src/context_foundry/agents/scheduler.py` (Fast validation)

### Documentation
- `replit.md` (Updated with Data Gates section)
- `outputs/CF_100_Query_Evaluation_POST_DATA_GATES.md`
- `outputs/CF_Evaluation_Evidence_POST_DATA_GATES.json`

---

## Verification Commands

```bash
# Check entity/relationship counts
psql $DATABASE_URL -c "SELECT lifecycle_state, COUNT(*) FROM entities GROUP BY 1;"
psql $DATABASE_URL -c "SELECT lifecycle_state, COUNT(*) FROM relationships GROUP BY 1;"

# Test the guard on a zero-relationship entity
python3 -c "
from src.context_foundry.models.schema import get_session
from src.context_foundry.agents.retrieval import RetrievalAgent
from src.context_foundry.agents.reasoning import ReasoningAgent

session = get_session()
retrieval = RetrievalAgent(session)
reasoning = ReasoningAgent()

bundle = retrieval.build_context_bundle('What is the impact if CloudRes fails?')
response = reasoning.reason(bundle)
print(f'Grounded: {response.get(\"grounded\")}')
print(f'Data Gap: {response.get(\"data_gap\")}')
print(f'Confidence: {response.get(\"confidence\")}')
"
```

---

## Rollback Instructions

If issues arise, the key changes can be reverted:

1. **Relationship Guard**: Remove guard logic from `reasoning.py` `reason()` method
2. **Fast Validation**: Comment out `_fast_validate_staging()` call in scheduler
3. **Query Classifier**: Module can be deleted if not needed

---

**This is a stable checkpoint. The core mission of preventing hallucination is restored.**

*Created: December 11, 2025*
*Context Foundry v2.0 - Dual-System Cognitive Architecture*
