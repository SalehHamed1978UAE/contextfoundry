# Context Foundry - Setup Guide

## Walking Skeleton Complete! ✓

This guide will walk you through setting up and testing the Context Foundry MVP.

## Prerequisites

- **Docker & Docker Compose** (required)
- **Python 3.11+** (for local development/testing)
- **16GB+ RAM** (recommended)
- **10GB disk space** (for models and data)

## Quick Start (5 Steps)

### Step 1: Initialize Database

```bash
# Start PostgreSQL and create schema
docker-compose up -d postgres redis

# Wait for PostgreSQL to be ready (10-15 seconds)
sleep 15

# Load schema
docker-compose exec -T postgres psql -U cf_user -d context_foundry < schema.sql
```

### Step 2: Pull Ollama Models

```bash
# Start Ollama
docker-compose up -d ollama

# Pull models (this will take 5-10 minutes)
docker-compose exec ollama ollama pull mistral:7b-instruct-q4_K_M
docker-compose exec ollama ollama pull nomic-embed-text
```

### Step 3: Load Walking Skeleton Data

```bash
# Build the app container
docker-compose build app

# Load entities, relationships, and rules
docker-compose run --rm app python3 -m src.cli load-data

# Embed documents
docker-compose run --rm app python3 -m src.cli embed-documents

# Promote all to TRUSTED
docker-compose run --rm app python3 -m src.cli promote-all

# Check stats
docker-compose run --rm app python3 -m src.cli stats
```

Expected output:
```
Entities by Lifecycle State:
  TRUSTED: 12
Relationships: 13
Symbolic Rules: 4
```

### Step 4: Start the API

```bash
# Start the full application
docker-compose up app

# You should see:
# ✓ All agents initialized
# ✓ All systems operational
```

### Step 5: Test a Query!

In another terminal:

```bash
# Test the health endpoint
curl http://localhost:8000/health | jq

# Submit a test query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What database does payment-api use?"
  }' | jq
```

Expected response structure:
```json
{
  "success": true,
  "response": {
    "answer": "...",
    "confidence": 0.85,
    "confidence_level": "high",
    "evidence_chain": [...],
    "caveats": [...],
    "rules_checked": [...]
  }
}
```

## Test Queries

Here are some test queries for the walking skeleton:

### Single-Hop Queries

1. **"What database does payment-api use?"**
   - Expected: PostgreSQL (payments-db)
   - Tests: DEPENDS_ON relationship

2. **"Who owns the user-service?"**
   - Expected: payments-team
   - Tests: OWNS relationship

3. **"What team is Alice Chen on?"**
   - Expected: payments-team
   - Tests: MEMBER_OF relationship

### Multi-Hop Queries

4. **"Which services depend on databases owned by platform-team?"**
   - Expected: payment-api (uses payments-db owned by platform-team)
   - Tests: 2-hop traversal (DEPENDS_ON + OWNS)

5. **"If payments-db goes down, which teams should be notified?"**
   - Expected: platform-team (owns db), payments-team (owns dependent service)
   - Tests: Multi-hop reasoning with ownership chains

6. **"What incidents involved session-cache?"**
   - Expected: INC-2024-002 (Session Cache Eviction Cascade)
   - Tests: Document search with entity matching

7. **"How do I troubleshoot database connection issues?"**
   - Expected: Reference to database troubleshooting runbook
   - Tests: Document similarity search

### Uncertainty Testing

8. **"What is the SLA for notification-service?"**
   - Expected: Low confidence (information not in dataset)
   - Tests: Uncertainty surfacing

9. **"Which database does api-gateway use?"**
   - Expected: Entity not found, insufficient context
   - Tests: Graceful handling of missing data

## Architecture Verification

### Check Tri-Memory Integration

```bash
# Query that should hit all three memory layers:
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Tell me about the payment-api database connection pool exhaustion incident"
  }' | jq '.response | {
    semantic: .evidence_chain[0].source.type,
    episodic: .evidence_chain[1].source.type,
    symbolic: .rules_checked
  }'
```

Expected output showing all three memory types active.

### Verify Confidence Calibration

```bash
# High-confidence query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What database does payment-api use?"}' \
  | jq '.response.confidence'

# Low-confidence query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the disaster recovery plan?"}' \
  | jq '.response.confidence'
```

High-confidence should be >0.7, low-confidence should be <0.5.

### Check Rule Validation

```bash
# Query involving services (should trigger ownership rules)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Which team owns payment-api?"}' \
  | jq '.response.rules_checked'
```

Should show rules like "service_must_have_owner" were checked.

## Monitoring & Debugging

### View Logs

```bash
# Application logs
docker-compose logs -f app

# Ollama logs (LLM inference)
docker-compose logs -f ollama

# Database logs
docker-compose logs -f postgres
```

### Check System Stats

```bash
curl http://localhost:8000/stats | jq
```

### Inspect Database

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U cf_user -d context_foundry

# Example queries:
SELECT COUNT(*) FROM graph_lifecycle WHERE lifecycle_state = 'TRUSTED';
SELECT COUNT(*) FROM document_embeddings;
SELECT COUNT(*) FROM query_responses;
```

## Troubleshooting

### Issue: Ollama model not loaded

```bash
# Check available models
docker-compose exec ollama ollama list

# Pull missing model
docker-compose exec ollama ollama pull mistral:7b-instruct-q4_K_M
```

### Issue: Schema not loaded

```bash
# Reload schema
docker-compose exec -T postgres psql -U cf_user -d context_foundry < schema.sql
```

### Issue: No embeddings found

```bash
# Re-run embedding step
docker-compose run --rm app python3 -m src.cli embed-documents
```

### Issue: Low confidence on all queries

**Possible causes:**
1. Data not promoted to TRUSTED
   - Fix: `docker-compose run --rm app python3 -m src.cli promote-all`

2. Embeddings not created
   - Fix: `docker-compose run --rm app python3 -m src.cli embed-documents`

3. LLM timeout or error
   - Check: `docker-compose logs ollama`

## Development Workflow

### Adding New Data

1. Modify `src/utils/synthetic_data.py`
2. Regenerate: `python3 -m src.utils.synthetic_data`
3. Reload: `docker-compose run --rm app python3 -m src.cli load-data`
4. Promote: `docker-compose run --rm app python3 -m src.cli promote-all`

### Modifying Agents

1. Edit agent files in `src/agents/`
2. Rebuild: `docker-compose build app`
3. Restart: `docker-compose restart app`

### Testing Changes

```bash
# Restart with fresh data
docker-compose down -v
docker-compose up -d postgres redis ollama
# ... repeat setup steps
```

## Next Steps

Now that the walking skeleton is working:

1. **Tune Confidence Thresholds** - Adjust in `src/config.py`
2. **Add More Test Queries** - Document edge cases
3. **Implement Feedback Loop** - Build the learning cycle
4. **Scale Up Data** - Generate full synthetic dataset
5. **Benchmark Against GraphRAG** - Implement baseline

## Performance Expectations

On the walking skeleton (12 entities, 13 relationships, 4 documents):

- **Retrieval latency:** <200ms
- **Reasoning latency:** 2-5 seconds (depends on Ollama model size)
- **Total latency p95:** <10 seconds

These will improve with:
- GPU acceleration for Ollama
- Smaller/faster models (e.g., Mistral 7B → Qwen 2.5 3B)
- Vector index optimization

## Success Criteria ✓

You've successfully deployed Context Foundry if:

- [x] All Docker services healthy
- [x] Schema loaded successfully
- [x] Walking skeleton data loaded (12 entities, 13 relationships)
- [x] Documents embedded (4 documents)
- [x] API responds to queries
- [x] Tri-memory architecture active (semantic + episodic + symbolic)
- [x] Uncertainty surfacing works (confidence scores present)
- [x] Rule validation executes

## Support

If you encounter issues:

1. Check logs: `docker-compose logs -f app`
2. Verify stats: `curl http://localhost:8000/stats | jq`
3. Restart services: `docker-compose restart`
4. Full reset: `docker-compose down -v && <re-run setup>`

---

**Walking Skeleton Status: COMPLETE** ✓

You now have a fully functional tri-memory cognitive architecture ready for evaluation!
