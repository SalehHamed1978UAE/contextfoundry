# Context Foundry — Comprehensive Status Check

> **Purpose**: Get a clear picture of exactly where we are after weeks of changes
> **Date**: January 5, 2026
> **Action**: Replit runs ALL checks below and reports findings

---

## Part 1: Data Health

### 1.1 Entity Counts by Type and State
```sql
SELECT 
    entity_type,
    lifecycle_state,
    COUNT(*) as count
FROM entities 
WHERE tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3'
GROUP BY entity_type, lifecycle_state
ORDER BY entity_type, lifecycle_state;
```

### 1.2 Relationship Counts by Type and State
```sql
SELECT 
    relationship_type,
    lifecycle_state,
    COUNT(*) as count
FROM relationships 
WHERE tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3'
GROUP BY relationship_type, lifecycle_state
ORDER BY count DESC;
```

### 1.3 Document Counts by Status
```sql
SELECT 
    status,
    COUNT(*) as count
FROM documents 
WHERE tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3'
GROUP BY status;
```

### 1.4 Relationship Connectivity
```sql
-- How many entities have relationships vs don't
SELECT 
    CASE 
        WHEN rel_count > 0 THEN 'Has relationships'
        ELSE 'No relationships'
    END as status,
    COUNT(*) as entity_count
FROM (
    SELECT e.id, COUNT(DISTINCT r.id) as rel_count
    FROM entities e
    LEFT JOIN relationships r ON e.id = r.source_entity_id OR e.id = r.target_entity_id
    WHERE e.tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3'
      AND e.lifecycle_state = 'TRUSTED'
    GROUP BY e.id
) sub
GROUP BY status;
```

### 1.5 Top 10 Most Connected Entities
```sql
SELECT 
    e.name,
    e.entity_type,
    COUNT(DISTINCT r.id) as relationship_count
FROM entities e
JOIN relationships r ON e.id = r.source_entity_id OR e.id = r.target_entity_id
WHERE e.tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3'
  AND e.lifecycle_state = 'TRUSTED'
GROUP BY e.id, e.name, e.entity_type
ORDER BY relationship_count DESC
LIMIT 10;
```

### 1.6 Embedding Coverage
```sql
SELECT 
    CASE 
        WHEN name_embedding IS NOT NULL THEN 'Has embedding'
        ELSE 'No embedding'
    END as status,
    COUNT(*) as count
FROM entities
WHERE tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3'
  AND lifecycle_state = 'TRUSTED'
GROUP BY status;
```

---

## Part 2: Schema Configuration

### 2.1 What entity types are defined?
```bash
cat config/domain_schema.yaml | grep -A 100 "entity_types:" | head -50
```

### 2.2 What relationship types are defined?
```bash
cat config/domain_schema.yaml | grep -A 200 "relationship_types:" | head -100
```

### 2.3 Are DEPENDS_ON, SERVICE, DATABASE in schema?
```bash
grep -E "(DEPENDS_ON|SERVICE|DATABASE)" config/domain_schema.yaml
```

---

## Part 3: RLM Implementation Status

### 3.1 Check RLM files exist
```bash
ls -la src/context_foundry/rlm/
```

### 3.2 Run RLM test suite
```bash
pytest tests/rlm/ -v --tb=short 2>&1 | tail -50
```

### 3.3 Check RLM integration in core.py
```bash
grep -n "tier2\|RLM\|force_tier" src/context_foundry/core.py | head -20
```

### 3.4 Test RLM routing
```python
from context_foundry.rlm.router import QueryComplexityRouter

router = QueryComplexityRouter()

test_queries = [
    "What is the Network Monitoring Service?",
    "What services depend on Payment Service?",
    "Which services are affected by incidents triggered by Network Monitoring?",
    "Trace dependencies from Database Cluster to frontend",
]

for q in test_queries:
    result = router.route(q)
    print(f"Query: {q[:50]}...")
    print(f"  → Tier: {result.tier}, Score: {result.complexity_score}, Reason: {result.reason}")
    print()
```

---

## Part 4: API Health

### 4.1 Check services running
```bash
curl -s http://localhost:5000/health | python -m json.tool
curl -s http://localhost:3000/health | python -m json.tool
```

### 4.2 Test Tier 1 query
```bash
curl -s -X POST http://localhost:5000/internal/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is Frontend App?"}' | python -m json.tool
```

### 4.3 Test forced Tier 2 (RLM) query
```bash
curl -s -X POST http://localhost:5000/internal/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What services depend on Auth Gateway?", "force_tier": "tier2"}' | python -m json.tool
```

---

## Part 5: Memory Graph UI

### 5.1 Test entity search API
```bash
curl -s "http://localhost:5000/api/graph/search?q=Frontend" | python -m json.tool
```

### 5.2 Test entity relationships API
```bash
# Get an entity ID first
ENTITY_ID=$(curl -s "http://localhost:5000/api/graph/search?q=Frontend" | python -c "import sys,json; print(json.load(sys.stdin)['results'][0]['id'])" 2>/dev/null)
echo "Entity ID: $ENTITY_ID"

# Get relationships
curl -s "http://localhost:5000/api/graph/entity/$ENTITY_ID/relationships" | python -m json.tool
```

---

## Part 6: Background Jobs

### 6.1 Check Gardener status
```bash
grep -i "gardener" logs/*.log 2>/dev/null | tail -10
# Or check scheduler
ps aux | grep -i "scheduler\|gardener"
```

### 6.2 Check extraction worker
```bash
grep -i "extraction\|worker" logs/*.log 2>/dev/null | tail -10
```

### 6.3 Check RE Agent Batch progress
```sql
-- If there's a job tracking table
SELECT * FROM background_jobs ORDER BY created_at DESC LIMIT 5;
```

---

## Part 7: Recent Changes Verification

### 7.1 List recently modified files
```bash
find src/context_foundry -name "*.py" -mtime -1 -exec ls -la {} \;
```

### 7.2 Git status (if using git)
```bash
git log --oneline -20
git diff --stat HEAD~10
```

### 7.3 Check for syntax errors
```bash
python -m py_compile src/context_foundry/core.py
python -m py_compile src/context_foundry/rlm/executor.py
python -m py_compile src/context_foundry/rlm/router.py
echo "No syntax errors if no output above"
```

---

## Part 8: Full Test Suite

### 8.1 Run all tests
```bash
pytest tests/ -v --tb=short 2>&1 | tail -100
```

### 8.2 Summary of test results
```bash
pytest tests/ --tb=no -q 2>&1 | tail -10
```

---

## Report Template

Please fill this out after running all checks:

### Data Health Summary
| Metric | Value |
|--------|-------|
| Total TRUSTED entities | ? |
| Total STAGING entities | ? |
| Total TRUSTED relationships | ? |
| Entity types present | ? |
| Relationship types present | ? |
| % entities with relationships | ? |
| % entities with embeddings | ? |

### Schema Status
| Item | Present? |
|------|----------|
| SERVICE entity type | Yes/No |
| DATABASE entity type | Yes/No |
| DEPENDS_ON relationship | Yes/No |
| MANAGES relationship | Yes/No |
| AFFECTS relationship | Yes/No |

### RLM Status
| Component | Status |
|-----------|--------|
| RLM files exist | Yes/No |
| RLM tests passing | ?/90 |
| RLM integrated in core.py | Yes/No |
| Router threshold | ? |
| Force tier working | Yes/No |

### API Health
| Endpoint | Status |
|----------|--------|
| /health (5000) | OK/Error |
| /health (3000) | OK/Error |
| Tier 1 query | Works/Fails |
| Tier 2 query | Works/Fails |
| Graph search | Works/Fails |

### Test Suite
| Suite | Passing | Failing |
|-------|---------|---------|
| RLM tests | ? | ? |
| Integration tests | ? | ? |
| Total | ? | ? |

### Known Issues
1. ?
2. ?
3. ?

### Things That Are Working
1. ?
2. ?
3. ?

---

## After This Report

Once we have this data, we can:
1. Update the SavePoint with accurate current state
2. Prioritize what actually needs fixing
3. Make informed decisions about next steps
