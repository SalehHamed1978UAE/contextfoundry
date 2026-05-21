#!/bin/bash

# Context Foundry - Test Queries
# Run this script after setup to verify the walking skeleton

set -e

API_URL="http://localhost:8000"

echo "=============================================="
echo "Context Foundry - Walking Skeleton Tests"
echo "=============================================="
echo ""

# Check if API is running
echo "Checking API health..."
curl -s "${API_URL}/health" | jq -r '
  "Status: \(.status)",
  "Database: \(.database)",
  "Ollama: \(.ollama)",
  "Agents: Retrieval=\(.agents.retrieval) Reasoning=\(.agents.reasoning) Validation=\(.agents.validation)"
'
echo ""

# Check system stats
echo "System Statistics:"
curl -s "${API_URL}/stats" | jq -r '
  "Entities (TRUSTED): \(.entities_trusted)",
  "Relationships: \(.relationships_total)",
  "Documents Embedded: \(.documents_embedded)",
  "Queries Processed: \(.queries_processed)"
'
echo ""

# Function to run query and extract key info
run_query() {
    local query="$1"
    local description="$2"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "TEST: $description"
    echo "QUERY: $query"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    response=$(curl -s -X POST "${API_URL}/query" \
        -H "Content-Type: application/json" \
        -d "{\"query\": \"$query\"}")

    echo "$response" | jq -r '
        if .success then
            "✓ SUCCESS",
            "",
            "Answer:",
            "  \(.response.answer)",
            "",
            "Confidence: \(.response.confidence) (\(.response.confidence_level))",
            "",
            "Evidence Chain:",
            (.response.evidence_chain[] | "  - \(.fact) [confidence: \(.confidence)]"),
            "",
            (if (.response.caveats | length) > 0 then
                "Caveats:",
                (.response.caveats[] | "  - \(.)"),
                ""
            else "" end),
            (if (.response.rules_checked | length) > 0 then
                "Rules Checked: \(.response.rules_checked | join(", "))",
                ""
            else "" end),
            "Latency: \(.response.total_latency_ms)ms"
        else
            "✗ FAILED",
            "Error: \(.error.message)"
        end
    '

    echo ""
    sleep 2  # Rate limiting
}

# Single-hop queries
echo "========================================"
echo "SINGLE-HOP QUERIES"
echo "========================================"
echo ""

run_query \
    "What database does payment-api use?" \
    "Single-hop: Service → Database dependency"

run_query \
    "Who owns the user-service?" \
    "Single-hop: Service → Team ownership"

run_query \
    "What team is Alice Chen on?" \
    "Single-hop: Person → Team membership"

# Multi-hop queries
echo "========================================"
echo "MULTI-HOP QUERIES"
echo "========================================"
echo ""

run_query \
    "Which services depend on databases owned by platform-team?" \
    "Multi-hop: Service → Database → Team"

run_query \
    "If payments-db goes down, which teams should be notified?" \
    "Multi-hop: Database → Services → Teams"

# Document search
echo "========================================"
echo "DOCUMENT SEARCH (EPISODIC MEMORY)"
echo "========================================"
echo ""

run_query \
    "What incidents involved session-cache?" \
    "Episodic: Document similarity search"

run_query \
    "How do I troubleshoot database connection issues?" \
    "Episodic: Runbook retrieval"

# Uncertainty testing
echo "========================================"
echo "UNCERTAINTY SURFACING"
echo "========================================"
echo ""

run_query \
    "What is the SLA for notification-service?" \
    "Uncertainty: Information not in dataset"

run_query \
    "Which database does api-gateway use?" \
    "Uncertainty: Entity not found"

echo "=============================================="
echo "Tests Complete!"
echo "=============================================="
echo ""
echo "Summary: Check that..."
echo "  - Single-hop queries have high confidence (>0.7)"
echo "  - Multi-hop queries work correctly"
echo "  - Document search retrieves relevant incidents"
echo "  - Uncertainty is surfaced for unknown information"
echo "  - Rules are being checked and validated"
echo ""
