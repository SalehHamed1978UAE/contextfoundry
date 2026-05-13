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
python scripts/validate_property_plane.py \
  --tenant-id "$TENANT_ID" \
  --subset property \
  --output test_results/stage3a_property_subset_results.json

echo ""
echo "=== DONE ==="
echo "Results saved to:"
echo "  test_results/stage3a_property_inventory.json (step 1)"
echo "  test_results/stage3a_property_subset_results.json (step 2)"
