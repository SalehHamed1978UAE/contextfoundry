#!/usr/bin/env bash
# Stage 3A — Empirical Validation Commands
# Run these on Replit where DB access and platform server are available.
# Execute each step sequentially and capture the output.

set -e

TENANT_ID="ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda"

echo "=============================================="
echo "STEP 1: Property Inventory (read-only, safe)"
echo "=============================================="
echo ""
echo "This queries entities table, parses properties JSON,"
echo "and reports which of the 16 failing questions have"
echo "matching data in entity.properties."
echo ""

python scripts/property_inventory.py \
  --tenant-id "$TENANT_ID" \
  --output test_results/stage3a_property_inventory.json

echo ""
echo "Report written to test_results/stage3a_property_inventory.json"
echo ""
echo "=============================================="
echo "STEP 1 COMPLETE — Review the report above."
echo "If coverage is low, STOP HERE. The adapter"
echo "path won't help and we need a different approach."
echo "=============================================="

# --- ONLY proceed to Step 2 if Step 1 shows good coverage ---

echo ""
echo "=============================================="
echo "STEP 2a: Apply migration (dev/staging only)"
echo "=============================================="

psql "$DATABASE_URL" -f migrations/add_property_facts.sql

echo ""
echo "=============================================="
echo "STEP 2b: Run adapter (dry-run first)"
echo "=============================================="

python scripts/run_property_adapter.py \
  --tenant-id "$TENANT_ID" \
  --dry-run

echo ""
echo "=============================================="
echo "STEP 2c: Run adapter (actual upsert)"
echo "=============================================="

python scripts/run_property_adapter.py \
  --tenant-id "$TENANT_ID"

echo ""
echo "=============================================="
echo "STEP 2d: Verify row counts"
echo "=============================================="

psql "$DATABASE_URL" -c "
SELECT entity_type, lifecycle_state, COUNT(*) as fact_count
FROM property_facts
WHERE tenant_id = '$TENANT_ID'::uuid
GROUP BY entity_type, lifecycle_state
ORDER BY entity_type, lifecycle_state;
"

psql "$DATABASE_URL" -c "
SELECT COUNT(*) as total_facts
FROM property_facts
WHERE tenant_id = '$TENANT_ID'::uuid;
"

echo ""
echo "=============================================="
echo "STEP 2e: Validate — PROPERTY subset (35Q)"
echo "=============================================="

python scripts/validate_property_plane.py \
  --tenant-id "$TENANT_ID" \
  --subset property \
  --output test_results/stage3a_property_subset_results.json

echo ""
echo "=============================================="
echo "STEP 2 COMPLETE"
echo "=============================================="
echo ""
echo "Results written to:"
echo "  test_results/stage3a_property_inventory.json"
echo "  test_results/stage3a_property_subset_results.json"
