# Context Foundry Save Point - December 10, 2025

## Overview
This save point documents all major improvements completed on December 9-10, 2025.

---

## Query/Reasoning System Hardening

### 1. Blast Radius Direction Fix
**Problem:** DEPENDS_ON traversal was showing upstream dependencies instead of downstream dependents.

**Fix:** Corrected traversal direction to show what breaks if X fails (downstream entities that depend on X).

**Status:** ✅ FIXED - Shows DOWNSTREAM correctly

### 2. GROUNDED/GAP/INFERRED Response Structure
All query responses now clearly label facts:
- **GROUNDED**: Facts verified in the knowledge graph
- **GAP**: Missing documentation identified
- **INFERRED**: Derived conclusions (not directly documented)

**Status:** ✅ IMPLEMENTED

### 3. Query Verification
**23/23 query types passing** - Full test suite verified

### 4. Edge Case Handling (5/5 Passing)
| Query | Expected Behavior | Result |
|-------|------------------|--------|
| "Blast radius of FakeService" | Refuse to hallucinate | ✅ PASS |
| "Who owns XYZ123 Service" | Refuse to hallucinate | ✅ PASS |
| "What does User Database depend on?" | Return real data | ✅ PASS |
| "" (empty query) | Return 400 error | ✅ PASS |
| "Capital of France" | Stay in-domain | ✅ PASS |

---

## Pipeline Progress Module (Anthropic Long-Running Agent Harness)

### Implementation
- **Location:** `src/context_foundry/pipeline/`
- **Pattern:** Anthropic's long-running agent harness with checkpoint/resume

### Features
- **Step-based tracking:** 11 discrete steps
  - queued → reading → classifying → chunking → extracting → relating → staging → verifying → promoting → completed/failed
- **Checkpoint/Resume:** Database-backed progress survives crashes
- **Stale detection:** `get_stalled()` finds documents stuck for N minutes
- **Clean retry:** `reset_for_retry()` clears stale steps/metadata

### Database Migration
- **Migration:** `010_pipeline_progress.sql` applied
- **Table:** `pipeline_progress` with 11 columns
- **Enum:** `ingestion_step` with 11 values
- **Indexes:** 7 indexes for query performance

### Test Suite
**13 tests passing:**
- Checkpoint flow (start → update → complete)
- Resume after crash/interrupt
- Fail and retry logic with stale data cleanup
- Stalled document detection
- Summary statistics

---

## Production Fixes

### Google OAuth Fix
- **Issue:** Hardcoded redirect URI broke contextfoundry.app deployment
- **Fix:** Dynamic redirect URI construction from request host
- **Status:** ✅ FIXED

### SQLAlchemy JSON Mutation
- **Issue:** JSON fields not persisting properly
- **Fix:** Added `flag_modified()` calls for proper mutation tracking
- **Status:** ✅ FIXED

---

## Stress Test Results

### Test Duration
- Started: December 9, 2025 ~20:39
- Auto-recovered from overnight hibernation at 04:16

### Corpus Statistics
| Metric | Count |
|--------|-------|
| Documents | 7,694 |
| Entities | 8,314 |
| Relationships | 2,327 |
| Documents with Extractions | 176 |

### Per-Document Averages
| Metric | Value |
|--------|-------|
| Avg Entities/Doc | 47.1 |
| Avg Relationships/Doc | 14.8 |
| Max Relationships | 526 |

### Domain Classification
Automatic detection working:
- Construction (0.529 confidence)
- Manufacturing (0.423 confidence)
- Finance (0.340 confidence)
- IT Infrastructure (0.299 confidence)

### Relationship State Distribution
| State | Count | % |
|-------|-------|---|
| STAGING | 1,466 | 60% |
| TRUSTED | 404 | 17% |
| ARCHIVED | 553 | 23% |

**Note:** High-confidence STAGING relationships (0.9-1.0) may need promotion to TRUSTED for blast radius queries to return results.

---

## System Recovery

### Overnight Hibernation
- **Issue:** Replit workspace hibernated at 21:49
- **Recovery:** Stress Test Monitor auto-restarted at 04:16
- **Impact:** Minimal - no data loss, processing resumed normally

### Current System Health
- Memory: 27GB / 62GB used (healthy)
- All services running
- No OOM events detected

---

## Files Changed

### New Files
- `src/context_foundry/pipeline/__init__.py`
- `src/context_foundry/pipeline/progress.py`
- `src/context_foundry/migrations/010_pipeline_progress.sql`
- `tests/test_progress.py`

### Modified Files
- `src/context_foundry/agents/reasoning.py` (blast radius fix)
- `src/context_foundry/models/schema.py` (PipelineProgress model)
- `web_app.py` (Google OAuth fix)
- `replit.md` (documentation update)

---

## Next Steps
1. Build Context Bundle API for external apps
2. Integrate progress module with feature flag
3. Decide on STAGING → TRUSTED promotion strategy
4. Continue overnight stress testing
