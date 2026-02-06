# Phase 2: Slice Validation on Replit

**Status**: Ready to execute
**Date**: 2026-02-07
**Prerequisites**: Phase 1 extraction improvements committed to `main` branch (commit `62affe16`)

---

## Overview

Phase 2 validates extraction improvements on a controlled 5-document slice before full vault re-extraction. This ensures the improved extraction prompt produces clean data without regressions.

**Pre-committed Pass/Fail Criteria (CRITICAL):**
- ✅ ≥3 of 5 documents produce supply-chain edges (SUPPLIES/CUSTOMER_OF/PROCURES_FROM)
- ✅ Boeing typed as ORGANIZATION (not PERSON) in all mentions
- ✅ Co-occurrence WORKS_AT edges reduced >50% compared to baseline
- ✅ No entity with >15 edges (degree anomaly check)
- ✅ No regressions on relationships that currently work

**FAIL → iterate on prompt improvements, do NOT proceed to full re-extraction**

---

## Step 1: Pull Latest Changes on Replit

```bash
# In Replit Shell
cd /home/runner/ContextFoundry_3rdFeb2026
git pull origin main
```

**Verify you have commit `62affe16`:**
```bash
git log --oneline -1
# Should show: 62affe16 feat: Phase 1 extraction improvements - fix upstream data quality
```

**What you just pulled:**
- `config/domain_schema.yaml` - Added 4 supply-chain relationship types
- `src/context_foundry/extraction/relation_extractor.py` - Enhanced prompt with 3 critical rules + entity type validation
- `docs/STATEMENT_OF_OBJECTIVE.md` - Strategic framing document
- `scripts/setup_slice_vault.py` - Slice vault creation script

---

## Step 2: Create Slice Vault (5 Documents)

```bash
python scripts/setup_slice_vault.py
```

**Expected Output:**
```
======================================================================
PHASE 2: Slice Vault Setup (5 Documents)
======================================================================

Testing extraction improvements on controlled slice:
  1. Boeing customer profile (CUSTOMER_OF + entity type)
  2. Nel Hydrogen supplier (SUPPLIES)
  3. GreenHydrogen steering committee (co-occurrence test)
  4. Supplier performance review (supply-chain edges)
  5. Siemens customer profile (CUSTOMER_OF)

[Step 1] Authenticating...
  ✓ Authenticated
[Step 2] Creating fresh slice vault...
  ✓ Created vault: <vault-id>
[Step 3] Uploading 5 test documents...
  Uploading: stakeholders/01_boeing_customer_profile.md
    ✓ Success
  Uploading: stakeholders/09_nel_hydrogen_supplier.md
    ✓ Success
  Uploading: meetings/03_greenhydrogen_steering_committee.md
    ✓ Success
  Uploading: meetings/12_supplier_performance_review.md
    ✓ Success
  Uploading: stakeholders/05_siemens_healthineers_customer.md
    ✓ Success

[Step 4] Upload complete: 5 succeeded, 0 failed

======================================================================
✓ SLICE VAULT READY
======================================================================
Vault ID: <vault-id-will-be-shown-here>
Vault Name: ClaudeCode Nexus Slice (Extraction Validation)
Documents: 5/5

Next step: Run extraction
  python scripts/run_vault_extraction.py --vault-id <vault-id> --use-ontology
```

**IMPORTANT**: Copy the `Vault ID` from the output. You'll need it for Step 3.

---

## Step 3: Run Ontology Extraction on Slice

```bash
# Replace <vault-id> with the ID from Step 2
python scripts/run_vault_extraction.py --vault-id <vault-id> --use-ontology
```

**What this does:**
- Runs improved extraction prompt on all 5 documents
- Applies entity type validation (Boeing must be ORGANIZATION)
- Uses supply-chain relationship types (SUPPLIES, CUSTOMER_OF, etc.)
- Enforces co-occurrence ≠ employment guardrail
- Ingests extracted entities and relationships into KG

**Expected Duration**: 2-5 minutes for 5 documents

---

## Step 4: Run Automated Validation (Phase 2.5)

**CRITICAL**: Run automated validation **BEFORE** looking at any test scores.

### Option 1: Automated Script (Recommended)

```bash
# Run comprehensive automated validation
python scripts/phase2_5_validation.py --vault-id <slice-vault-id>

# With baseline comparison for regression detection
python scripts/phase2_5_validation.py \
  --vault-id <slice-vault-id> \
  --baseline-vault-id <old-vault-id> \
  --output validation_report.json
```

**The script will:**
- ✓ Check type consistency (Boeing as PERSON?)
- ✓ Check schema coverage (supply-chain types missing?)
- ✓ Check degree anomalies (entities with >10 edges?)
- ✓ Check distribution (WORKS_AT >20%?)
- ✓ Check cardinality violations
- ✓ Check regressions vs baseline (relationships disappeared?)

**Exit codes:**
- `0` = PASS (all checks passed)
- `1` = FAIL (critical failures - DO NOT proceed)
- `2` = WARN (warnings - review before proceeding)

### Option 2: Manual SQL Validation

If you prefer manual validation, run the SQL queries below.

### A) Check Supply-Chain Edges Appear

```sql
-- Connect to database (Replit provides psql)
-- Or use database admin panel if available

-- Count supply-chain relationship types
SELECT
  relation_type,
  COUNT(*) as count
FROM cf_relationships
WHERE tenant_id = '<vault-id>'
  AND relation_type IN ('SUPPLIES', 'CUSTOMER_OF', 'PROCURES_FROM', 'VENDOR_OF', 'SUPPLIES_TO')
GROUP BY relation_type
ORDER BY count DESC;
```

**PASS CRITERIA**: At least 3 different relationship types appear
**FAIL CRITERIA**: 0 or 1-2 relationship types

---

### B) Check Boeing Entity Type

```sql
-- Find Boeing entity and check type
SELECT
  canonical_name,
  entity_type,
  degree
FROM cf_entities
WHERE tenant_id = '<vault-id>'
  AND LOWER(canonical_name) LIKE '%boeing%';
```

**PASS CRITERIA**: Boeing typed as `ORGANIZATION`
**FAIL CRITERIA**: Boeing typed as `PERSON` or not found

---

### C) Check Co-Occurrence WORKS_AT Reduction

```sql
-- Count WORKS_AT edges in slice
SELECT
  COUNT(*) as works_at_count
FROM cf_relationships
WHERE tenant_id = '<vault-id>'
  AND relation_type = 'WORKS_AT';

-- Compare to baseline (you'll need baseline vault ID from previous run)
-- Expected: Should be significantly lower than before
```

**PASS CRITERIA**: WORKS_AT count reduced by >50% compared to old baseline slice
**FAIL CRITERIA**: Similar or higher WORKS_AT count

**Note**: You may need to extract the same 5 docs with the OLD prompt first to get baseline, or compare against proportion in full vault.

---

### D) Check for Degree Anomalies

```sql
-- Find entities with high degree (potential cross-wiring)
SELECT
  canonical_name,
  entity_type,
  degree
FROM cf_entities
WHERE tenant_id = '<vault-id>'
ORDER BY degree DESC
LIMIT 10;
```

**PASS CRITERIA**: No entity has >15 edges
**FAIL CRITERIA**: Boeing PERSON or any entity with >15 edges exists

---

### E) Check for Regressions (Category 0 Gate)

```sql
-- Relationship type distribution
SELECT
  relation_type,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM cf_relationships
WHERE tenant_id = '<vault-id>'
GROUP BY relation_type
ORDER BY count DESC;
```

**PASS CRITERIA**:
- Distribution looks reasonable (not 25% WORKS_AT)
- Mix of HR relationships (WORKS_AT, HOLDS_POSITION) AND supply-chain (SUPPLIES, CUSTOMER_OF)
- No obvious missing relationship types that should appear

**FAIL CRITERIA**:
- WORKS_AT dominates (>20%)
- Zero supply-chain edges
- Missing relationship types that were in old KG

---

## Step 5: Generate Validation Report

Create a summary with these metrics and send back:

```markdown
# Phase 2 Slice Validation Report

**Vault ID**: <vault-id>
**Vault Name**: ClaudeCode Nexus Slice (Extraction Validation)
**Documents Extracted**: 5/5
**Extraction Date**: <timestamp>

---

## Pre-Committed Pass/Fail Results

### A) Supply-Chain Edges
- SUPPLIES: X edges
- CUSTOMER_OF: X edges
- PROCURES_FROM: X edges
- VENDOR_OF: X edges
- **RESULT**: ✅ PASS / ❌ FAIL

### B) Boeing Entity Type
- Entity: Boeing / The Boeing Company
- Type: ORGANIZATION / PERSON
- Degree: X edges
- **RESULT**: ✅ PASS / ❌ FAIL

### C) Co-Occurrence WORKS_AT
- WORKS_AT edges in slice: X
- Baseline comparison: X% reduction
- **RESULT**: ✅ PASS / ❌ FAIL

### D) Degree Anomalies
- Highest degree entity: <name> (<type>) - X edges
- Entities with >15 edges: X
- **RESULT**: ✅ PASS / ❌ FAIL

### E) Relationship Distribution
```
| Relationship Type | Count | Percentage |
|-------------------|-------|------------|
| ...               | ...   | ...        |
```
- **RESULT**: ✅ PASS / ❌ FAIL

---

## Overall Phase 2 Decision

**PASS (all 5 criteria met)**: ✅ Proceed to Phase 3 (full vault re-extraction)
**FAIL (any criteria failed)**: ❌ Iterate on prompt improvements, do NOT proceed

---

## Observations

[Note any interesting patterns, unexpected results, or insights]
```

---

## Decision Gate

### IF PASS (All 5 Criteria Met)

**Proceed to Phase 2.5: Automated Validation**

Run these additional checks:
- Type consistency: Any suspicious entity types beyond Boeing?
- Schema coverage: Which ontology relationship types have zero instances?
- Distribution analysis: Does it look reasonable overall?
- Cardinality violations: Any 1-to-1 relationships with multiple values?

Then proceed to **Phase 3: Full Vault Re-Extraction** (197 documents)

### IF FAIL (Any Criteria Failed)

**DO NOT proceed to full re-extraction**

1. Analyze which criteria failed and why
2. Iterate on extraction prompt improvements
3. Re-run Phase 2 with new prompt
4. Repeat until all 5 criteria pass

Remember: **"We're building a system that works, not passing a test"**

---

## SQL Queries Reference

### Alternative: Get All Validation Data in One Query

```sql
-- Comprehensive validation query
WITH supply_chain AS (
  SELECT relation_type, COUNT(*) as count
  FROM cf_relationships
  WHERE tenant_id = '<vault-id>'
    AND relation_type IN ('SUPPLIES', 'CUSTOMER_OF', 'PROCURES_FROM', 'VENDOR_OF')
  GROUP BY relation_type
),
boeing_check AS (
  SELECT canonical_name, entity_type, degree
  FROM cf_entities
  WHERE tenant_id = '<vault-id>'
    AND LOWER(canonical_name) LIKE '%boeing%'
),
works_at_count AS (
  SELECT COUNT(*) as count
  FROM cf_relationships
  WHERE tenant_id = '<vault-id>'
    AND relation_type = 'WORKS_AT'
),
degree_check AS (
  SELECT canonical_name, entity_type, degree
  FROM cf_entities
  WHERE tenant_id = '<vault-id>'
    AND degree > 15
),
rel_distribution AS (
  SELECT
    relation_type,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
  FROM cf_relationships
  WHERE tenant_id = '<vault-id>'
  GROUP BY relation_type
  ORDER BY count DESC
)
SELECT
  'Supply Chain Edges' as check_type,
  (SELECT json_agg(json_build_object('type', relation_type, 'count', count))
   FROM supply_chain) as result
UNION ALL
SELECT
  'Boeing Entity',
  (SELECT row_to_json(boeing_check.*) FROM boeing_check)
UNION ALL
SELECT
  'WORKS_AT Count',
  (SELECT row_to_json(works_at_count.*) FROM works_at_count)
UNION ALL
SELECT
  'Degree Anomalies',
  (SELECT json_agg(row_to_json(degree_check.*)) FROM degree_check)
UNION ALL
SELECT
  'Distribution',
  (SELECT json_agg(json_build_object('type', relation_type, 'count', count, 'pct', percentage))
   FROM rel_distribution LIMIT 10);
```

---

## Troubleshooting

### "Vault creation failed"
- Check API server is running on Replit
- Verify DATABASE_URL is set in environment
- Check authentication credentials

### "Documents not uploading"
- Verify corpus path exists: `test documents/ClaudeCode_NExus_Industries_corpus/`
- Check document paths in `SLICE_DOCUMENTS` list
- Ensure Replit has file access permissions

### "Extraction failed"
- Check OPENAI_API_KEY is set
- Verify sufficient API credits
- Check extraction logs for errors

### "Can't connect to database"
- Ensure PostgreSQL is running on Replit
- Verify DATABASE_URL format
- Check database credentials

---

## What Changed in Phase 1 (Reminder)

**1. Ontology Schema** (`config/domain_schema.yaml`)
```yaml
# Supply Chain & Commercial Relationships
- name: SUPPLIES
  description: "Organization supplies products, components, or services to another Organization"
  examples:
    - "Siemens supplies turbine components to Nexus Industries"

- name: CUSTOMER_OF
  description: "Organization is a customer of another Organization"
  examples:
    - "Nexus Industries is a customer of Siemens for turbine equipment"
```

**2. Extraction Prompt** (`relation_extractor.py:470-516`)
```python
CRITICAL EXTRACTION RULES:

1. CO-OCCURRENCE IS NOT EMPLOYMENT
   ❌ WRONG: Person mentioned in meeting → DO NOT create WORKS_AT
   ✅ CORRECT: Only create WORKS_AT when text explicitly states employment

2. PRIORITIZE SUPPLY-CHAIN RELATIONSHIPS
   ✅ Look for: supplier, vendor, customer, purchases from, procures

3. VALIDATE ENTITY TYPES
   - Major companies must be ORGANIZATION, never PERSON
```

**3. Entity Type Validation** (`relation_extractor.py:231-269`)
```python
# Known companies that should NEVER be PERSON
known_organizations = ["boeing", "siemens", "nexus industries", "nel hydrogen"]

# Validate WORKS_AT: source must be PERSON, target must be ORGANIZATION
# Validate supply-chain: both must be ORGANIZATION
```

---

**Good luck with Phase 2 validation!**
**Remember: All 5 criteria must pass to proceed to Phase 3.**
