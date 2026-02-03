# Phase 3 Ontology Integration - Replit Work Plan

**Mission:** Create fresh vault, run ontology extraction, validate against 88% baseline

**Critical Rules:**
1. ❌ **NO SHORTCUTS** - Every step must complete fully
2. ❌ **NO ASSUMPTIONS** - Verify every claim with database queries
3. ❌ **NO EARLY EXITS** - All 9 validation gates must pass
4. ✅ **DETERMINISTIC ONLY** - Use counts, queries, file checks (no LLM judgment)

---

## PRE-FLIGHT CHECKLIST

Before you start, verify these exist:

```bash
# 1. Check scripts exist
ls -la scripts/phase3_ontology_validator.py
ls -la scripts/phase3_ontology_execution.py

# 2. Check corpus exists
ls -la "test documents/ClaudeCode_NExus_Industries_corpus/"

# 3. Check database connection
python -c "import os; print('DB:', os.environ.get('DATABASE_URL', 'NOT SET'))"

# 4. Check platform services running
curl -s http://localhost:5000/api/health || echo "Platform NOT running"
```

**ALL FOUR MUST PASS** before proceeding. If any fail, STOP and report.

---

## EXECUTION STEPS

### STEP 1: Pull Latest Code from GitHub

```bash
git fetch origin
git pull origin main
git status  # Must show "up to date"
```

**Verification:** `git log -1` shows latest commit from GitHub

---

### STEP 2: Start Platform Services

```bash
# Start platform (if not running)
python web_app.py &
sleep 10

# Verify running
curl -s http://localhost:5000/api/health | grep -q "ok" || exit 1
```

**Verification:** Platform health check returns "ok"

---

### STEP 3: Execute Phase 3 Workflow

```bash
python scripts/phase3_ontology_execution.py 2>&1 | tee phase3_execution.log
```

**This script will:**
1. Create fresh vault: "ClaudeCode Nexus Industries (Ontology)"
2. Upload 100+ documents
3. Run ONTOLOGY extraction (`--use-ontology` flag)
4. Run 100-question test
5. Run 9-gate validation

**Time Estimate:** 60-90 minutes total

**Verification:** Script exits with code 0 (success)

---

### STEP 4: Verify All 9 Gates Passed

```bash
# Check validation results
cat data/phase3_validation_results.json

# Extract overall pass status
python -c "import json; print('PASS' if json.load(open('data/phase3_validation_results.json'))['overall_pass'] else 'FAIL')"
```

**Must show:** `PASS`

**If FAIL:** Check which gates failed in the JSON file and fix them. DO NOT PROCEED.

---

### STEP 5: Extract Key Metrics

```bash
# Get accuracy from test results
python -c "import json; d=json.load(open('data/test-runner/status.json')); print(f\"Accuracy: {d['qa_progress']['accuracy_percent']}%\")"

# Get entity/relationship counts
python -c "
import os, json
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
vault_id = json.load(open('data/phase3_validation_results.json'))['vault_id']
with engine.connect() as conn:
    entities = conn.execute(text('SELECT COUNT(*) FROM entities WHERE tenant_id = :v'), {'v': vault_id}).scalar()
    rels = conn.execute(text('SELECT COUNT(*) FROM relationships WHERE tenant_id = :v'), {'v': vault_id}).scalar()
    print(f'Entities: {entities}')
    print(f'Relationships: {rels}')
"
```

**Expected Output:**
```
Accuracy: 88.0% or higher
Entities: 500+
Relationships: 1000+
```

---

### STEP 6: Generate Summary Report

```bash
cat > phase3_summary.md <<'EOF'
# Phase 3 Ontology Integration - Validation Results

## Vault Information
- **Vault ID:** [COPY from phase3_validation_results.json]
- **Vault Name:** ClaudeCode Nexus Industries (Ontology)
- **Extraction Method:** Ontology-centric pipeline (--use-ontology)

## Validation Gates (9/9 must pass)
[COPY gate results from phase3_validation_results.json]

## Test Results
- **Accuracy:** [COPY from status.json]
- **Questions Passed:** [COPY from status.json]
- **Questions Failed:** [COPY from status.json]
- **Baseline Comparison:** 88% (multi-model) vs XX% (ontology)

## Extraction Statistics
- **Documents:** [COUNT from database]
- **Entities:** [COUNT from database]
- **Relationships:** [COUNT from database]
- **Ontology Types Used:** [COUNT from gate 6]

## Conclusion
[✅ PASS / ❌ FAIL] - Ontology pipeline [MATCHES/EXCEEDS/FALLS SHORT OF] baseline

## Recommendation
[YES/NO] - Make ontology pipeline the default extraction method

---
Generated: [TIMESTAMP]
EOF
```

Manually fill in the bracketed values from the validation and test results files.

---

## SUCCESS CRITERIA - ALL MUST BE TRUE

Check these manually before declaring success:

```bash
# ✅ Gate 1: Vault exists in database
# ✅ Gate 2: 100+ documents uploaded
# ✅ Gate 3: All documents extracted with ontology pipeline
# ✅ Gate 4: 500+ entities extracted
# ✅ Gate 5: 1000+ relationships extracted
# ✅ Gate 6: 10+ ontology types used
# ✅ Gate 7: Test results file exists
# ✅ Gate 8: All 100 questions answered
# ✅ Gate 9: Accuracy ≥ 88%
```

**If ANY gate fails:** DO NOT declare success. Report the failure.

---

## FAILURE HANDLING

If the script fails at any step:

1. **DO NOT SKIP AHEAD**
2. **Capture the error:**
   ```bash
   tail -100 phase3_execution.log > error_report.txt
   ```
3. **Report to user:**
   - Which step failed
   - Error message
   - Relevant log lines
4. **DO NOT attempt to fix it yourself** - wait for instructions

---

## COMPLETION CHECKLIST

Before declaring "Phase 3 Complete":

- [ ] `phase3_validation_results.json` shows `"overall_pass": true`
- [ ] `data/test-runner/status.json` shows accuracy ≥ 88%
- [ ] All 9 validation gates passed
- [ ] Vault ID recorded in results file
- [ ] Summary report generated
- [ ] Execution log saved

**ONLY IF ALL CHECKBOXES ARE CHECKED:** Reply with "✅ Phase 3 Complete - All Gates Passed"

---

## VALIDATION GATES EXPLAINED

### Gate 1: Vault Exists
- Checks database for vault record
- Query: `SELECT id, name FROM platform.tenants WHERE id = :vault_id`

### Gate 2: Documents Uploaded
- Minimum 100 documents required
- Query: `SELECT COUNT(*) FROM platform.documents WHERE tenant_id = :vault_id`

### Gate 3: Extraction Completed
- ALL documents must have `status = 'extracted'`
- ALL documents must have `extraction_level = 'ontology'`
- Query: Check extraction_level column

### Gate 4: Entities Created
- Minimum 500 entities required
- Query: `SELECT COUNT(*) FROM entities WHERE tenant_id = :vault_id`

### Gate 5: Relationships Created
- Minimum 1000 relationships required
- Query: `SELECT COUNT(*) FROM relationships WHERE tenant_id = :vault_id`

### Gate 6: Ontology Types Used
- Minimum 10 distinct entity types required
- Query: `SELECT COUNT(DISTINCT entity_type) FROM entities WHERE tenant_id = :vault_id`

### Gate 7: Test Results Exist
- File check: `data/test-runner/status.json` must exist
- Must be valid JSON

### Gate 8: All Questions Answered
- Must have answered all 100 questions
- Check: `qa_progress.answered == 100`

### Gate 9: Accuracy Threshold
- Must achieve ≥ 88% accuracy
- Check: `qa_progress.accuracy_percent >= 88.0`

---

## IMPORTANT NOTES FOR REPLIT

1. **DO NOT use LLM judgment calls** - All validation is algorithmic
2. **DO NOT skip steps** - Each step builds on the previous one
3. **DO NOT fake validation** - Every gate checks the database
4. **DO capture all errors** - Save logs if anything fails
5. **DO verify before claiming success** - Run the validation script

**The validation script is your friend - it tells you exactly what's wrong if anything fails.**
