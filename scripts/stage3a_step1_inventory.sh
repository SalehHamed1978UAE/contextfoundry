#!/usr/bin/env bash
# Stage 3A Step 1 — Property Inventory (read-only, safe)
# Run this on Replit: bash scripts/stage3a_step1_inventory.sh
set -e
cd "$(dirname "$0")/.."
git fetch origin stage3a-property-plane-mvp
git checkout stage3a-property-plane-mvp
python scripts/property_inventory.py \
  --tenant-id ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda \
  --output test_results/stage3a_property_inventory.json
echo ""
echo "=== DONE === Report saved to test_results/stage3a_property_inventory.json"
echo "Review the coverage ratio. If below 12/16, STOP — do not run step 2."
