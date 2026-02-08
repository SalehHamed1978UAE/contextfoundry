# How to Investigate the Database Split-Brain Problem

## Quick Start (In Replit)

### Run the Investigation

```bash
python3 investigate_split_brain_comprehensive.py
```

This single command will:
- ✓ Check if both `platform.documents` and `public.documents` exist
- ✓ Show you the ACTUAL column names in your database
- ✓ Count documents for your vault
- ✓ Analyze entity/relationship staging status
- ✓ Report if split-brain is detected

### Save Results

```bash
python3 investigate_split_brain_comprehensive.py > split_brain_results.txt 2>&1
```

Then you can share the results for further analysis.

---

## What This Investigation Tells You

### 1. Table Existence

The script checks if these tables exist:
- `platform.documents` (Platform/UI layer)
- `public.documents` (Brain/Knowledge Graph layer)
- `platform.entities`
- `public.entities`
- `platform.relationships`
- `public.relationships`

**What to look for**:
- ✓ If only ONE documents table exists → Good
- ⚠️ If BOTH documents tables exist → Potential split-brain
- ❌ If NEITHER exists → Critical problem

### 2. Actual Column Names

The script shows you the REAL columns in your database:

```
platform.documents:
  Column Name                    Data Type                Nullable
  ────────────────────────────────────────────────────────────────
  id                             uuid                     NO
  tenant_id                      uuid                     NO        ← Use this!
  name                           text                     NO
  status                         character varying        NO
  extraction_level               character varying        YES
```

**Why this matters**:
- Code might be using wrong column names
- Some code assumes `vault_id`, others use `tenant_id`
- This tells you which is actually in your database

### 3. Document Counts

The script counts documents for vault `b158cd16-810a-484d-99a8-8de786602c35`:

```
platform.documents: 5 documents
public.documents: 1 document

❌ SPLIT-BRAIN: Count mismatch (5 vs 1)
```

**What this means**:
- Different tables have different data
- Some code sees 5 documents, other code sees 1
- Extraction might operate on wrong documents

### 4. Staging vs Trusted Status

The script checks if entities/relationships are stuck in staging:

```
Entities:
  staging:  150 entities
  trusted:  0 entities

⚠️  WARNING: Entities stuck in STAGING, none promoted to TRUSTED
```

**What this means**:
- Extraction created entities in staging
- Verification/promotion pipeline didn't run
- Brain can't use untrusted data

---

## Common Scenarios

### Scenario 1: Both Tables Exist with Different Counts

```
✓ platform.documents: EXISTS (5 documents)
✓ public.documents: EXISTS (1 document)

❌ SPLIT-BRAIN DETECTED
```

**What happened**: Different parts of code writing to different tables.

**Fix**: Choose ONE table as source of truth and update all code.

### Scenario 2: Only Platform Table Exists

```
✓ platform.documents: EXISTS (5 documents)
✗ public.documents: MISSING
```

**What happened**: Schema migrated to platform, but some code still queries public.

**Fix**: Update code querying `public.documents` to use `platform.documents`.

### Scenario 3: Only Public Table Exists

```
✗ platform.documents: MISSING
✓ public.documents: EXISTS (5 documents)
```

**What happened**: Using older schema or incomplete migration.

**Fix**: Either migrate to platform schema or update code to use public schema consistently.

### Scenario 4: Staging Promotion Failure

```
✓ Only one documents table exists
✓ 5 documents extracted

⚠️  Entities: 150 staging, 0 trusted
⚠️  Relationships: 75 staging, 0 trusted
```

**What happened**: Extraction worked, but promotion pipeline didn't.

**Fix**: Investigate verification/promotion workflow.

---

## After Running Investigation

### 1. Document Your Findings

Fill in the results section of `SPLIT_BRAIN_INVESTIGATION_REPORT.md`:

```markdown
### Run 1: 2026-02-08 08:30

- [x] Both tables exist: YES
- [x] Document counts match: NO (5 vs 1)
- [x] Actual tenant column name: tenant_id
- [x] Actual stage column name: stage
- [x] Entities stuck in staging: YES
- [x] Split-brain detected: YES
```

### 2. Choose Your Fix Strategy

Based on the investigation results:

#### If `platform.documents` is more populated:
→ Use `platform.documents` as single source of truth

#### If `public.documents` is more populated:
→ Use `public.documents` as single source of truth

#### If counts are the same:
→ Compare codebase usage (platform has more references)

### 3. Update Code

See `SPLIT_BRAIN_INVESTIGATION_REPORT.md` for detailed fix instructions.

Key files to update:
- `verify_system_state.py`
- `scripts/run_vault_extraction.py`
- `brain/app.py`
- Any file that queries the wrong schema

### 4. Re-run Investigation

After applying fixes:

```bash
python3 investigate_split_brain_comprehensive.py
```

You should see:
```
✓ Only one documents table exists
✓ Document counts consistent
✓ No split-brain detected
```

---

## Troubleshooting

### "DATABASE_URL not set"

In Replit:
1. Check that PostgreSQL is enabled in your .replit file
2. Restart the Repl
3. Verify: `echo $DATABASE_URL`

### "Could not connect to database"

1. Check PostgreSQL is running: `pg_isready`
2. Check .replit configuration includes PostgreSQL
3. Try restarting the database service

### "psycopg2 not installed"

```bash
pip install psycopg2-binary
```

---

## Alternative Investigation Scripts

If the comprehensive script doesn't work, try these alternatives:

### Quick Check (Bash)
```bash
./check_split_brain_simple.sh
```

### Detailed Comparison (Python)
```bash
python3 check_split_brain.py
```

### Manual SQL Queries

If scripts fail, run these SQL queries directly:

```sql
-- Check table existence
SELECT EXISTS (
  SELECT FROM information_schema.tables
  WHERE table_schema = 'platform' AND table_name = 'documents'
) AS platform_exists,
EXISTS (
  SELECT FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name = 'documents'
) AS public_exists;

-- Count documents
SELECT
  (SELECT COUNT(*) FROM platform.documents
   WHERE tenant_id = 'b158cd16-810a-484d-99a8-8de786602c35') AS platform_count,
  (SELECT COUNT(*) FROM public.documents
   WHERE tenant_id = 'b158cd16-810a-484d-99a8-8de786602c35') AS public_count;

-- Check entity staging
SELECT stage, COUNT(*)
FROM entities
WHERE tenant_id = 'b158cd16-810a-484d-99a8-8de786602c35'
GROUP BY stage;
```

---

## What the Codebase Analysis Revealed

Even without database access, static analysis of the code shows:

### Document Table Usage
- **platform.documents**: 57 SELECT statements, 15 UPDATE statements
- **public.documents**: 8 SELECT statements, 0 UPDATE statements

**Conclusion**: `platform.documents` is the primary table in active use.

### Critical Split-Brain Location

**File**: `scripts/run_vault_extraction.py`

This file queries BOTH tables:
- Preflight checks: `platform.documents`
- Execution reads: `public.documents`
- Completion updates: `platform.documents`

This is a textbook split-brain scenario.

---

## Expected Timeline

1. **Run investigation**: 1 minute
2. **Analyze results**: 5 minutes
3. **Choose fix strategy**: 10 minutes
4. **Update code**: 30-60 minutes
5. **Test extraction**: 15 minutes
6. **Verify fix**: 5 minutes

**Total**: ~1-2 hours to completely resolve split-brain

---

## Success Criteria

You know split-brain is eliminated when:

- [ ] Investigation shows only ONE documents table exists (or both are in sync)
- [ ] All code queries use the same schema
- [ ] No document count mismatches
- [ ] Entities/relationships promoted from staging to trusted
- [ ] Extraction runs end-to-end without errors
- [ ] Re-running investigation shows: "✓ No split-brain detected"

---

## Need Help?

If you get stuck:

1. Save the investigation output:
   ```bash
   python3 investigate_split_brain_comprehensive.py > results.txt 2>&1
   ```

2. Check the detailed report: `SPLIT_BRAIN_INVESTIGATION_REPORT.md`

3. Review the root cause analysis: `SPLIT_BRAIN_ROOT_CAUSE.md`

4. Look at existing scripts: `check_split_brain.py`, `check_split_brain_simple.sh`
