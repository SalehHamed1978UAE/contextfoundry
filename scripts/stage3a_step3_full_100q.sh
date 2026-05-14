#!/usr/bin/env bash
# Stage 3A Step 3 — Full 100Q validation
# Property facts already loaded from Step 2. This just runs all 100 questions.
# Run on Replit: bash scripts/stage3a_step3_full_100q.sh
set -e
cd "$(dirname "$0")/.."
TENANT_ID="ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda"

echo "=== Verifying property_facts are loaded ==="
psql "$DATABASE_URL" -c "
SELECT COUNT(*) as total_facts FROM property_facts
WHERE tenant_id = '${TENANT_ID}'::uuid;
"

# Find the questions file
QUESTIONS_FILE=""
for f in test_questions/nexus_100q.json \
         data/nexus_industries_100q.json \
         data/test-runner/nexus_industries_100q.json \
         src/test_runner/data/nexus_industries_100q.json; do
    if [ -f "$f" ]; then
        QUESTIONS_FILE="$f"
        break
    fi
done

if [ -z "$QUESTIONS_FILE" ]; then
    echo "ERROR: Cannot find questions file."
    ls data/ 2>/dev/null || true
    ls test_questions/ 2>/dev/null || true
    exit 1
fi

echo "Questions file: $QUESTIONS_FILE"

echo ""
echo "=== Running full 100Q validation ==="
echo "This will take a while (~5-10 min for 100 questions)"

# Clear old full-run results
rm -f test_results/stage3a/stage3a_full100q_*.jsonl

python scripts/run_qonly_http_parity.py \
  --vault-id "$TENANT_ID" \
  --questions-file "$QUESTIONS_FILE" \
  --out-dir test_results/stage3a \
  --corpus-name stage3a_full100q \
  --batch 100 \
  --per-q-timeout 60 \
  --enable-fallback true

echo ""
echo "=== DONE ==="
echo "Results saved to test_results/stage3a/"
