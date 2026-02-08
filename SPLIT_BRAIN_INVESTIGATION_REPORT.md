# Database Split-Brain Investigation Report

**Generated**: 2026-02-08
**Vault ID**: `b158cd16-810a-484d-99a8-8de786602c35`
**Status**: ⚠️ INVESTIGATION TOOLS PROVIDED - REQUIRES EXECUTION IN REPLIT

---

## Executive Summary

This report documents the split-brain problem in the ContextFoundry database where different parts of the codebase query different document tables:

- **`platform.documents`** - Used by Platform/UI layer (159 occurrences)
- **`public.documents`** - Used by Brain/Knowledge Graph layer (115 occurrences)

### Investigation Tools Provided

Since DATABASE_URL is not available in this local environment, I have created comprehensive investigation scripts that you can run in your Replit environment:

1. **`investigate_split_brain_comprehensive.py`** (NEW - Most comprehensive)
   - Checks table existence for all schemas
   - Shows actual column names from database
   - Counts documents, entities, relationships by schema
   - Analyzes staging vs trusted promotion status
   - Provides detailed recommendations

2. **`check_split_brain.py`** (Existing - Good for quick checks)
   - Compares platform.documents vs public.documents
   - Shows document counts and sample data
   - Checks entity/relationship staging status

3. **`check_split_brain_simple.sh`** (Existing - Simplest)
   - Quick bash script for rapid verification
   - Shows counts only

---

## Codebase Analysis Results

### Query Pattern Distribution

Based on static analysis of the codebase:

| Operation | platform.documents | public.documents |
|-----------|-------------------|------------------|
| SELECT/FROM | 57 occurrences | 8 occurrences |
| UPDATE | 15 occurrences | 0 occurrences |
| **Total** | **72 operations** | **8 operations** |

**Observation**: `platform.documents` is clearly the more actively maintained table.

### Files with Split-Brain Behavior

#### Files Using `platform.documents`:
- `platform_foundation/src/document_service.py` (8 refs)
- `platform_foundation/src/tenant_service.py` (2 refs)
- `web_app.py` (43 refs) - **PRIMARY UI INTERFACE**
- `scripts/run_vault_extraction.py` (18 refs) - **EXTRACTION WORKFLOW**
- `src/context_foundry/extraction/staging_loader.py` (3 refs)
- `src/context_foundry/search/document_searcher.py` (6 refs)
- Many more...

#### Files Using `public.documents`:
- `scripts/run_vault_extraction.py` (also uses public!)
- `verify_system_state.py`
- `brain/app.py`
- `tests/test_rls_security.py`
- `tests/test_platform_integration.py`

### Critical Split-Brain Example

**`scripts/run_vault_extraction.py`** exhibits classic split-brain:

```python
# PREFLIGHT: Checks platform.documents
# Lines 177, 187, 197, 226, 231
FROM platform.documents d
COUNT(*) FROM platform.documents WHERE tenant_id = :vault_id

# EXECUTION: Reads from public.documents
# Lines 301, 434, 498
FROM public.documents WHERE tenant_id = %s

# COMPLETION: Updates platform.documents
# Line 820
UPDATE platform.documents SET extraction_level = 'multi' WHERE id = :doc_id
```

**Impact**: If tables are out of sync, preflight sees different data than execution operates on.

---

## How to Run Investigation

### In Replit Environment

1. **Run the comprehensive investigation**:
   ```bash
   python3 investigate_split_brain_comprehensive.py
   ```

   This will:
   - ✓ Check if both `platform.documents` and `public.documents` exist
   - ✓ Get actual schema (column names) for each table
   - ✓ Count documents for vault `b158cd16-810a-484d-99a8-8de786602c35`
   - ✓ Analyze entities and relationships by stage
   - ✓ Report split-brain status
   - ✓ Provide specific column names to use in code

2. **For quick check**:
   ```bash
   ./check_split_brain_simple.sh
   ```

3. **For detailed comparison**:
   ```bash
   python3 check_split_brain.py
   ```

### Expected Output

The script will tell you:

1. **Table Existence**:
   ```
   ✓ platform.documents: EXISTS
   ✗ public.documents: MISSING    ← Split-brain if both exist
   ✓ platform.entities: EXISTS
   ✓ platform.relationships: EXISTS
   ```

2. **Actual Column Names** (critical for fixing code):
   ```
   platform.documents columns:
   - id
   - tenant_id          ← Use this, not vault_id
   - name
   - status
   - extraction_level
   - single_extracted_at
   - multi_extracted_at
   ```

3. **Document Counts**:
   ```
   platform.documents: 5 documents for vault b158cd16...
   public.documents: 3 documents for vault b158cd16...

   ❌ SPLIT-BRAIN: Count mismatch (5 vs 3)
   ```

4. **Staging Status**:
   ```
   Entities (staging): 150
   Entities (trusted): 0

   ⚠️  WARNING: Entities stuck in STAGING, none promoted to TRUSTED
   ```

---

## Expected Findings

Based on existing documentation (`SPLIT_BRAIN_ROOT_CAUSE.md`), you will likely find:

### Scenario 1: Both Tables Exist
```
❌ SPLIT-BRAIN DETECTED
   platform.documents: 5 documents
   public.documents: 1 document
   Difference: 4 documents
```

**Root Cause**: Different parts of code writing to different tables.

### Scenario 2: Only One Table Exists
```
⚠️  public.documents: TABLE DOES NOT EXIST
✓  platform.documents: 5 documents
```

**Root Cause**: Code querying non-existent table, causing silent failures.

### Scenario 3: Staging Promotion Failure
```
⚠️  Entities: 150 staging, 0 trusted
⚠️  Relationships: 75 staging, 0 trusted
```

**Root Cause**: Verification/promotion pipeline not executing.

---

## Recommended Fixes (Priority Order)

### P0 - Immediate (Stop the Bleeding)

1. **Determine Which Table Exists**:
   - Run `investigate_split_brain_comprehensive.py`
   - Document findings in a comment on this report

2. **Enforce Single Source of Truth**:

   **Option A: Use ONLY `platform.documents`** (RECOMMENDED)
   - Rationale: 72 operations vs 8 in codebase
   - Platform-managed, more actively maintained
   - Newer schema architecture

   **Option B: Use ONLY `public.documents`**
   - Only if verification confirms this is the authoritative table
   - Requires updating 72 code references

3. **Fix Critical Files**:

   Files to update if choosing `platform.documents`:
   ```python
   # In verify_system_state.py line 87:
   # CHANGE FROM:
   FROM public.documents

   # CHANGE TO:
   FROM platform.documents
   ```

   Files to update if choosing `public.documents`:
   ```python
   # In web_app.py (43 places)
   # In scripts/run_vault_extraction.py (preflight + completion)
   # In platform_foundation/src/document_service.py (8 places)
   # ... etc
   ```

### P1 - System Integrity

4. **Add Pre-Extraction Validation**:
   ```python
   # In scripts/run_vault_extraction.py, before extraction:

   def validate_no_split_brain(vault_id):
       """Verify platform.documents and public.documents are in sync."""
       platform_count = get_count("platform.documents", vault_id)

       public_exists = check_table_exists("public.documents")
       if public_exists:
           public_count = get_count("public.documents", vault_id)
           if platform_count != public_count:
               raise SplitBrainError(
                   f"Split-brain detected: platform={platform_count}, public={public_count}"
               )
   ```

5. **Add Column Name Constants**:
   ```python
   # In src/context_foundry/models/constants.py (new file):

   # Document table configuration
   DOCUMENTS_TABLE = "platform.documents"  # Single source of truth
   DOCUMENTS_TENANT_COL = "tenant_id"      # Use actual column name

   # Entity table configuration
   ENTITIES_TABLE = "platform.entities"
   ENTITIES_STAGE_COL = "stage"            # Not "status"!
   ```

6. **Update All Queries**:
   ```bash
   # Find all hardcoded references:
   grep -r "FROM public.documents" --include="*.py"
   grep -r "FROM platform.documents" --include="*.py"

   # Replace with constant:
   from src.context_foundry.models.constants import DOCUMENTS_TABLE
   cursor.execute(f"SELECT * FROM {DOCUMENTS_TABLE} WHERE ...")
   ```

### P2 - Long-term Architecture

7. **Consolidate Schema**:
   - If both tables exist and migration is needed:
     ```sql
     -- Backup first!
     CREATE TABLE platform.documents_backup AS
     SELECT * FROM platform.documents;

     -- Migrate if needed
     INSERT INTO platform.documents
     SELECT * FROM public.documents
     ON CONFLICT (id) DO UPDATE SET ...;

     -- Drop deprecated table after verification
     DROP TABLE public.documents;
     ```

8. **Add Monitoring**:
   ```python
   # Add to extraction manifest:
   {
     "database_fingerprint": {
       "documents_table": "platform.documents",
       "documents_count": 5,
       "tables_in_sync": true,
       "timestamp": "2026-02-08T..."
     }
   }
   ```

---

## Acceptance Criteria for "Split-Brain Eliminated"

- [ ] Investigation script confirms only ONE documents table exists (or both are in sync)
- [ ] All code queries use the same table name
- [ ] No count mismatches between schemas
- [ ] Entities/relationships promoted from staging → trusted
- [ ] Pre-extraction validation passes
- [ ] Manifest includes database fingerprint

---

## Next Steps

1. **Run Investigation**:
   ```bash
   python3 investigate_split_brain_comprehensive.py > investigation_results.txt
   ```

2. **Analyze Results**:
   - Does `public.documents` exist?
   - If yes, do counts match?
   - What are the actual column names?

3. **Choose Fix Strategy**:
   - Based on investigation results
   - Document decision in this file

4. **Execute Fix**:
   - Update code references
   - Test extraction end-to-end
   - Verify split-brain eliminated

5. **Re-run Investigation**:
   - Confirm fix worked
   - Document final state

---

## Investigation Results (TO BE FILLED IN AFTER RUNNING SCRIPT)

### Run 1: [Date/Time]

```
[Paste output of investigate_split_brain_comprehensive.py here]
```

### Findings:

- [ ] Both tables exist: YES / NO
- [ ] Document counts match: YES / NO / N/A
- [ ] Actual tenant column name: `___________`
- [ ] Actual stage column name: `___________`
- [ ] Entities stuck in staging: YES / NO
- [ ] Split-brain detected: YES / NO

### Decision:

[Document which table to use as single source of truth]

### Fix Applied:

[Document what changes were made]

### Verification Run: [Date/Time]

```
[Paste output after fix to verify split-brain eliminated]
```

---

## Related Documentation

- **`SPLIT_BRAIN_ROOT_CAUSE.md`** - Original analysis of the problem
- **`check_split_brain.py`** - Existing verification script
- **`investigate_split_brain_comprehensive.py`** - New comprehensive investigation tool

---

## Support

If you encounter issues running the investigation script:

1. Verify DATABASE_URL is set:
   ```bash
   echo $DATABASE_URL
   ```

2. Check PostgreSQL is running:
   ```bash
   pg_isready
   ```

3. Install dependencies:
   ```bash
   pip install psycopg2-binary
   ```

4. Run with verbose error output:
   ```bash
   python3 -u investigate_split_brain_comprehensive.py 2>&1 | tee investigation.log
   ```
