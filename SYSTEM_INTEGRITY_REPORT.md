# System Integrity Verification Report
**Date**: 2026-02-08
**Vault**: b158cd16-810a-484d-99a8-8de786602c35 (ClaudeCode Nexus Slice)
**Run**: run_manifest_20260208T005946Z.json

## Executive Summary
❌ **SYSTEM INTEGRITY FAILURE CONFIRMED**

The last extraction run exhibits all symptoms of the split-brain failure described in the problem assessment.

---

## Critical Findings

### 1. ❌ Incomplete Execution Marked as "Complete"
**Severity**: CRITICAL

- **Expected**: 5 documents
- **Preflight**: 4 docs queued, 0 extracted
- **Actual**: Only 1 document processed
- **Status**: Marked "completed" (INVALID)

**Evidence**:
```json
"preflight": {
  "documents": {
    "total": 5,
    "queued": 4,
    "extracted_or_completed": 0
  }
},
"extraction_summary": {
  "total_documents": 1,  // Only 1 out of 5!
  "errors": [
    "01_boeing_customer_profile.md: 'StagingResult' object has no attribute 'entities_staged'"
  ]
},
"status": "completed"  // FALSE - this run is INVALID
```

**Impact**: Invalid run pollutes accuracy metrics.

---

### 2. ❌ Missing Verification/Promotion Pipeline
**Severity**: CRITICAL

The manifest shows **NO** verification or promotion statistics.

**Expected** (from ontology mode):
- Extraction stats ✓ (present)
- Verification stats ❌ (missing)
- Promotion stats ❌ (missing)
- TRUSTED entity/relationship counts ❌ (missing)

**Evidence**:
```json
"extraction_summary": {
  "total_entities": 77,
  "total_relationships": 14,
  // No verification_stats
  // No promotion_stats
  // No trusted_entities count
  // No trusted_relationships count
}
```

**Impact**: Extraction → STAGING only. No TRUSTED facts = retrieval failures.

---

### 3. ❌ Silent Failure Mode
**Severity**: HIGH

4 out of 5 documents failed silently with AttributeError.

**Root Cause**:
Line 699 in run_vault_extraction.py used incorrect attribute:
```python
# BEFORE (wrong):
entities_staged = result.staging_result.entities_staged

# AFTER (fixed in commit 1c7d5b4d):
entities_created = result.staging_result.entities_created
```

**Impact**: Partial extractions appear complete, creating data inconsistency.

---

### 4. ❌ No Run Validity Tracking
**Severity**: HIGH

The manifest has:
- `"status": "completed"` ❌ Should be `"invalid"`
- No `"is_valid"` field
- No `"invalid_reason"` field
- No phase completion tracking

**Expected Fields** (missing):
```json
{
  "is_valid": false,
  "invalid_reason": "Only 1/5 documents processed; AttributeError prevented completion",
  "phases_completed": ["extraction"],
  "phases_failed": ["verification", "promotion"],
  "verification_stats": null,
  "promotion_stats": null
}
```

---

### 5. ⚠️ STAGING vs TRUSTED Unknown
**Severity**: HIGH

The manifest shows 77 entities and 14 relationships extracted, but doesn't indicate their stage.

**Questions**:
- Are they in `staging` or `trusted`?
- Did promotion execute at all?
- Are they queryable for Q&A?

**Expected**:
```json
"knowledge_graph": {
  "entities_staging": 77,
  "entities_trusted": 0,    // ← Critical: Are these populated?
  "relationships_staging": 14,
  "relationships_trusted": 0  // ← Critical: Are these populated?
}
```

**From preflight** (before extraction):
```json
"knowledge_graph": {
  "entities_total": 0,
  "entities_staging": 0,
  "entities_trusted": 0,
  "relationships_total": 0,
  "relationships_staging": 0,
  "relationships_trusted": 0
}
```

**Impact**: If TRUSTED = 0 after extraction, Q&A will fail despite "completed" status.

---

### 6. ❌ Execution Path Inconsistency
**Severity**: MEDIUM

The run used `mode: "ontology"` but the pipeline didn't complete the ontology-specific flow.

**Expected Ontology Flow**:
1. ✓ Extraction
2. ❌ Verification
3. ❌ Promotion
4. ❌ Manifest update with verification/promotion stats

**Actual Flow**:
1. ✓ Extraction (partial: 1/5 docs)
2. ❌ Stopped (AttributeError)
3. Status: "completed" (invalid)

---

## Split-Brain Evidence

### Database vs Manifest Discrepancy
**Preflight** reported:
- 5 total documents
- 4 queued
- 0 extracted
- 0 entities
- 24 chunks (documents WERE chunked!)

**Post-Extraction** shows:
- Only 1 document processed
- 77 entities created (stage unknown)
- 14 relationships created (stage unknown)
- 4 documents lost to AttributeError

**Conclusion**: Documents were chunked but extraction failed silently for 4/5 docs.

---

## Validation Criteria (from System Fix Plan)

| Criteria | Status | Evidence |
|----------|--------|----------|
| All docs chunked or run aborted invalid | ❌ FAIL | Docs chunked but run marked "completed" despite 4/5 failures |
| Completed run guarantees all phases executed | ❌ FAIL | Verification/promotion missing |
| TRUSTED facts appear after run | ⚠️ UNKNOWN | Manifest doesn't report TRUSTED counts |
| Invalid runs excluded from score reporting | ❌ FAIL | This invalid run would pollute metrics |
| Pipeline: chunk → extract → verify → promote | ❌ FAIL | Stopped after partial extraction |

---

## Recommended Actions (Priority Order)

### P0 - Immediate
1. **Mark this run as INVALID**
   - Add `is_valid: false`
   - Add `invalid_reason: "AttributeError prevented 4/5 documents from processing"`
   - Exclude from accuracy metrics

2. **Verify TRUSTED count in database**
   - If `trusted_entities = 0` and `trusted_relationships = 0`, this confirms promotion didn't execute
   - Run Q&A test to verify retrieval fails

3. **Fix remaining AttributeError instances**
   - Scan for all `entities_staged` → should be `entities_created`
   - Scan for all `relations_staged` → should be `relations_created`

### P1 - System Integrity
4. **Add run validity semantics to manifest**
   ```json
   {
     "is_valid": boolean,
     "invalid_reason": string | null,
     "phases_completed": ["extraction", "verification", "promotion"],
     "phases_failed": [...]
   }
   ```

5. **Enforce pipeline atomicity**
   - If extraction fails, mark run invalid
   - If verification fails, mark run invalid
   - If promotion fails, mark run invalid
   - No partial "completed" states

6. **Add TRUSTED counts to extraction_summary**
   ```json
   "extraction_summary": {
     "entities_staging": 77,
     "entities_trusted": 0,
     "relationships_staging": 14,
     "relationships_trusted": 0,
     "verification_passed": false,
     "promotion_passed": false
   }
   ```

### P2 - Observability
7. **Add runtime fingerprinting**
   - git SHA
   - database identity
   - run mode
   - tree_based_retrieval setting

8. **Add phase-level logging**
   - Track each phase completion
   - Record phase duration
   - Log failure reasons per phase

---

## Test Plan

Before declaring system fixed:

1. ✓ Run extraction with fixed AttributeError code
2. ☐ Verify all 5 documents process
3. ☐ Verify verification phase executes
4. ☐ Verify promotion phase executes
5. ☐ Verify TRUSTED entities > 0
6. ☐ Verify TRUSTED relationships > 0
7. ☐ Verify manifest includes all phases
8. ☐ Verify Q&A retrieval succeeds
9. ☐ Re-run accuracy test with valid run

---

## Appendix: Full Manifest

```json
{
  "run_started_at": "2026-02-08T00:58:17.000666",
  "vault_id": "b158cd16-810a-484d-99a8-8de786602c35",
  "vault_name": "ClaudeCode Nexus Slice (Extraction Validation)",
  "mode": "ontology",
  "tree_based_retrieval": "false",
  "models": ["gpt-4o-mini", "claude-sonnet"],
  "preflight": {
    "ok": true,
    "exists": true,
    "documents": {
      "total": 5,
      "queued": 4,
      "processing": 0,
      "extracted_or_completed": 0
    },
    "knowledge_graph": {
      "entities_total": 0,
      "entities_staging": 0,
      "entities_trusted": 0,
      "relationships_total": 0,
      "relationships_staging": 0,
      "relationships_trusted": 0,
      "chunks_total": 24
    }
  },
  "extraction_summary": {
    "total_documents": 1,
    "total_entities": 77,
    "total_relationships": 14,
    "total_chunks": 4,
    "errors": [
      "01_boeing_customer_profile.md: 'StagingResult' object has no attribute 'entities_staged'"
    ]
  },
  "run_completed_at": "2026-02-08T00:59:46.914300",
  "status": "completed"
}
```

---

**Report Generated**: 2026-02-08
**Conclusion**: System integrity failure confirmed. Run should be marked INVALID and excluded from metrics.
