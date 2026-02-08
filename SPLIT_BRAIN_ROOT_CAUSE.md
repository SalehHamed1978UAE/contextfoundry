# Split-Brain Root Cause Analysis

**Date**: 2026-02-08
**Severity**: CRITICAL - System Integrity Failure

---

## Root Cause Identified

The system has **TWO separate `documents` tables** in different schemas:

1. **`platform.documents`** ← Platform/UI layer
2. **`public.documents`** ← Brain/Knowledge Graph layer

**Different parts of the codebase query different tables**, creating operational split-brain where actors see different realities.

---

## Evidence

### Code Querying `platform.documents` (159 occurrences)

**Files:**
- `platform_foundation/src/document_service.py`
- `platform_foundation/src/tenant_service.py`
- `web_app.py` (Web UI)
- `scripts/run_vault_extraction.py` (Preflight + Updates)

**Example Queries:**
```sql
FROM platform.documents WHERE tenant_id = %s
UPDATE platform.documents SET extraction_level = 'multi' WHERE id = %s
SELECT COUNT(*) FROM platform.documents WHERE tenant_id = %s
```

### Code Querying `public.documents` (115 occurrences)

**Files:**
- `scripts/run_vault_extraction.py` (Extraction execution)
- `verify_system_state.py`
- `tests/*`

**Example Queries:**
```sql
FROM public.documents WHERE tenant_id = %s
SELECT status, COUNT(*) FROM public.documents GROUP BY status
```

---

## Split-Brain in `run_vault_extraction.py`

The extraction script itself exhibits split-brain behavior:

```python
# PREFLIGHT: Read from platform.documents
# Line 177, 187, 197, 226, 231
FROM platform.documents d
COUNT(*) FROM platform.documents WHERE tenant_id = :vault_id

# EXECUTION: Read from public.documents
# Line 301, 434, 498
FROM public.documents WHERE tenant_id = %s

# COMPLETION: Update platform.documents
# Line 820
UPDATE platform.documents SET extraction_level = 'multi' WHERE id = :doc_id
```

**Flow:**
1. Preflight checks `platform.documents` → sees 5 docs
2. Extraction reads `public.documents` → **sees different data?**
3. Updates `platform.documents` status

**If the tables are out of sync**, extraction operates on different data than preflight checked.

---

## Manifest Evidence of Split-Brain

From `run_manifest_20260208T005946Z.json`:

```json
"preflight": {
  "documents": {
    "total": 5,          // ← From platform.documents?
    "queued": 4,
    "extracted_or_completed": 0
  }
},
"extraction_summary": {
  "total_documents": 1,  // ← From public.documents?
  "errors": [
    "01_boeing_customer_profile.md: 'StagingResult' object has no attribute 'entities_staged'"
  ]
}
```

**Expected**: 5 documents
**Preflight**: 5 docs in platform.documents
**Execution**: Only 1 doc processed from public.documents
**Result**: Split-brain - different tables showed different realities

---

## Why This Causes Failures

### 1. Data Inconsistency
If `platform.documents` and `public.documents` don't stay in sync:
- UI shows one reality (from platform.documents)
- Extraction operates in different reality (from public.documents)
- Updates go to platform.documents, leaving public.documents stale

### 2. Race Conditions
Multiple processes updating different tables:
- Test Runner → might update platform.documents
- Extraction Worker → might read public.documents
- Web UI → reads platform.documents
- Brain API → reads public.documents

### 3. No Single Source of Truth
When debugging:
- "How many docs are queued?" → Different answer depending on which table you query
- "What's the extraction status?" → Different answer depending on which table you query

---

## Additional Split-Brain Vectors

### Competing Execution Paths (from .replit)

```toml
[[workflows.workflow]]
name = "Project"
mode = "parallel"  # ← Multiple workflows run simultaneously!

# These all run in parallel:
- "Run Extraction"
- "Ontology Extraction: Nexus"
- "Test: Manus Healthtec"
- "Test: ClaudeCode Medsync"
- "Test: Manus Medsync"
```

**Result**: Multiple extraction processes contending for the same vault, writing to same/different tables.

---

## Schema Architecture Questions

###Need to Verify:

1. **Are platform.documents and public.documents synchronized?**
   - Via trigger?
   - Via sync worker?
   - Manually?
   - Not at all?

2. **Which is the source of truth?**
   - platform.documents = Platform-managed documents
   - public.documents = Brain-managed documents
   - Should they mirror each other?

3. **Why two tables?**
   - Architectural separation? (Platform vs Brain)
   - Row-Level Security? (RLS policies)
   - Multi-tenancy isolation?

4. **What data differs between them?**
   - Same schema?
   - Same rows?
   - Same tenant_ids?

---

## How to Verify Split-Brain

Run these queries **simultaneously** when extraction is running:

```sql
-- Platform view
SELECT id, name, status, extraction_level
FROM platform.documents
WHERE tenant_id = 'b158cd16-810a-484d-99a8-8de786602c35'
ORDER BY name;

-- Public/Brain view
SELECT id, name, status, extraction_level
FROM public.documents
WHERE tenant_id = 'b158cd16-810a-484d-99a8-8de786602c35'
ORDER BY name;

-- Compare counts
SELECT
  (SELECT COUNT(*) FROM platform.documents WHERE tenant_id = 'b158cd16-810a-484d-99a8-8de786602c35') as platform_count,
  (SELECT COUNT(*) FROM public.documents WHERE tenant_id = 'b158cd16-810a-484d-99a8-8de786602c35') as public_count;
```

**If counts/data differ → Split-brain confirmed**

---

## Recommended Fixes (Priority Order)

### P0 - Immediate (Stop the Bleeding)

1. **Enforce Single Table as Source of Truth**

   Option A: Use ONLY `platform.documents`
   - Modify all Brain queries to use `platform.documents`
   - Drop or deprecate `public.documents`

   Option B: Use ONLY `public.documents`
   - Modify all Platform queries to use `public.documents`
   - Drop or deprecate `platform.documents`

   Option C: Synchronize via Database View
   ```sql
   CREATE OR REPLACE VIEW documents AS
   SELECT * FROM platform.documents;  -- Or vice versa
   ```

2. **Add Database Fingerprint to All Queries**
   Log which table is being queried:
   ```python
   logger.info(f"Querying platform.documents for vault {vault_id}")
   # vs
   logger.info(f"Querying public.documents for vault {vault_id}")
   ```

### P1 - System Integrity

3. **Add Cross-Table Consistency Checks**
   Before any extraction run:
   ```sql
   -- Verify tables are in sync
   SELECT
     pd.id,
     pd.name AS platform_name,
     pubd.name AS public_name,
     pd.status AS platform_status,
     pubd.status AS public_status
   FROM platform.documents pd
   FULL OUTER JOIN public.documents pubd ON pd.id = pubd.id
   WHERE pd.tenant_id = %s
     AND (pd.id IS NULL OR pubd.id IS NULL OR pd.status != pubd.status);
   ```

   If ANY rows returned → Abort run as invalid, tables out of sync

4. **Add Runtime Fingerprinting**
   Include in manifest:
   ```json
   {
     "database_fingerprint": {
       "documents_table_used": "platform.documents",
       "platform_doc_count": 5,
       "public_doc_count": 5,
       "tables_in_sync": true
     }
   }
   ```

5. **Disable Parallel Extraction Workflows**
   In `.replit`:
   ```toml
   [[workflows.workflow]]
   name = "Project"
   mode = "sequential"  # ← Prevent race conditions
   ```

### P2 - Long-term Architecture

6. **Consolidate to Single Schema**
   - Decide: Is this Platform-managed or Brain-managed data?
   - Move all queries to single table
   - Add migration to merge data if needed

7. **Add Advisory Locks**
   Prevent concurrent extraction on same vault:
   ```sql
   SELECT pg_try_advisory_lock(hashtext('vault_' || %s));
   ```

---

## Acceptance Criteria for "Split-Brain Eliminated"

- [ ] All document queries use same table (platform.documents OR public.documents, not both)
- [ ] Preflight and execution see same data
- [ ] Manifest includes database fingerprint showing single source
- [ ] Cross-table consistency check passes (if keeping both tables)
- [ ] No parallel workflows contending for same vault
- [ ] UI, Test Runner, Extraction, and Replit all query same table

---

## Test Plan

1. Add logging to show which table is queried:
   ```python
   logger.info(f"[SPLIT-BRAIN-DEBUG] Querying platform.documents: {query}")
   logger.info(f"[SPLIT-BRAIN-DEBUG] Querying public.documents: {query}")
   ```

2. Run extraction and grep logs:
   ```bash
   grep "SPLIT-BRAIN-DEBUG" /tmp/extraction.log
   ```

3. If BOTH tables appear in logs → Split-brain confirmed

4. Modify to use single table, re-run

5. Verify only ONE table appears in logs

---

## Related Issues

- Parallel workflow execution (`.replit` mode=parallel)
- No advisory locking on vaults
- AttributeError causing 4/5 doc failures
- Missing verification/promotion pipeline
- No run validity tracking

All of these are **symptoms** of the underlying split-brain architecture.

---

**Next Steps**:
1. Run cross-table consistency check
2. Decide which table is source of truth
3. Modify all queries to use single table
4. Add fingerprinting to verify fix
5. Re-run extraction and verify single-table usage
