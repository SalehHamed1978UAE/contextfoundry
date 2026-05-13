#!/usr/bin/env bash
# Stage 3A Step 2 — Migrate, adapt, validate (requires Step 1 coverage >= 12/16)
# Run this on Replit: bash scripts/stage3a_step2_migrate_and_validate.sh
set -e
cd /home/runner/ContextFoundry
TENANT_ID="ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda"

echo "=== 2a: Applying migration ==="
psql "$DATABASE_URL" -f migrations/add_property_facts.sql

echo ""
echo "=== 2b: Adapter dry-run (no writes) ==="
python scripts/run_property_adapter.py --tenant-id "$TENANT_ID" --dry-run

echo ""
echo "=== 2c: Adapter real run (writes to property_facts) ==="
python scripts/run_property_adapter.py --tenant-id "$TENANT_ID"

echo ""
echo "=== 2d: Row counts ==="
psql "$DATABASE_URL" -c "
SELECT entity_type, lifecycle_state, COUNT(*) as fact_count
FROM property_facts
WHERE tenant_id = '${TENANT_ID}'::uuid
GROUP BY entity_type, lifecycle_state
ORDER BY entity_type, lifecycle_state;
"
psql "$DATABASE_URL" -c "
SELECT COUNT(*) as total_facts FROM property_facts
WHERE tenant_id = '${TENANT_ID}'::uuid;
"

echo ""
echo "=== 2e: PROPERTY subset validation (35 questions) ==="
echo "Using run_qonly_http_parity.py with --qids for PROPERTY-35 subset"
echo "This uses the in-process harness (same code path as /api/vault/chat)"

# PROPERTY-35 question IDs from Stage 2F analysis
PROPERTY_QIDS="1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35"

# Find the questions file
QUESTIONS_FILE=""
for f in data/nexus_industries_100q.json \
         data/test-runner/nexus_industries_100q.json \
         src/test_runner/data/nexus_industries_100q.json; do
    if [ -f "$f" ]; then
        QUESTIONS_FILE="$f"
        break
    fi
done

if [ -z "$QUESTIONS_FILE" ]; then
    echo "ERROR: Cannot find questions file. Listing data dirs:"
    ls data/ 2>/dev/null || true
    ls data/test-runner/ 2>/dev/null || true
    ls src/test_runner/data/ 2>/dev/null || true
    exit 1
fi

echo "Questions file: $QUESTIONS_FILE"

python scripts/run_qonly_http_parity.py \
  --vault-id "$TENANT_ID" \
  --questions-file "$QUESTIONS_FILE" \
  --out-dir test_results/stage3a \
  --corpus-name stage3a_property \
  --qids "$PROPERTY_QIDS" \
  --batch 35 \
  --per-q-timeout 60 \
  --enable-fallback true

echo ""
echo "=== DONE ==="
echo "Results saved to test_results/stage3a/"
