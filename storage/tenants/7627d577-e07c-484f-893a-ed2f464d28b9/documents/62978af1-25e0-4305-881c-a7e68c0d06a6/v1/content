# Relationship Health Verification — Instructions for Replit

> **Goal**: Verify actual state of relationships before concluding there's a systemic problem
> **Context**: "Payments DB" has 0 relationships, but we need to check if this is isolated or widespread
> **Priority**: Do this BEFORE any fixes

---

## Step 1: Run These SQL Queries

### Query A: Top 20 Entities by Relationship Count
```sql
SELECT 
    e.name, 
    e.entity_type,
    COUNT(DISTINCT r.id) as rel_count
FROM entities e
LEFT JOIN relationships r ON e.id = r.source_entity_id OR e.id = r.target_entity_id
WHERE e.tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3'
  AND e.lifecycle_state = 'TRUSTED'
GROUP BY e.id, e.name, e.entity_type
HAVING COUNT(DISTINCT r.id) > 0
ORDER BY rel_count DESC
LIMIT 20;
```

**What we're looking for**: Which entities actually have relationships? Are they SERVICE, INCIDENT, DOCUMENT, or other types?

---

### Query B: Relationship Type Distribution
```sql
SELECT 
    relationship_type, 
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM relationships 
WHERE tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3'
  AND lifecycle_state = 'TRUSTED'
GROUP BY relationship_type
ORDER BY count DESC;
```

**What we're looking for**: Are relationships typed as DEPENDS_ON, MANAGES, AFFECTS? Or mostly POTENTIALLY_RELATES_TO / MENTIONS?

---

### Query C: SERVICE Entities Relationship Count
```sql
SELECT 
    e.name, 
    COUNT(r.id) as rel_count
FROM entities e
LEFT JOIN relationships r ON e.id = r.source_entity_id OR e.id = r.target_entity_id
WHERE e.entity_type = 'SERVICE'
  AND e.tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3'
  AND e.lifecycle_state = 'TRUSTED'
GROUP BY e.id, e.name
ORDER BY rel_count DESC
LIMIT 10;
```

**What we're looking for**: Do SERVICE entities have relationships? Or only DOCUMENTs?

---

### Query D: Entities with DEPENDS_ON Relationships
```sql
SELECT 
    source.name as source_name,
    source.entity_type as source_type,
    target.name as target_name,
    target.entity_type as target_type,
    r.confidence
FROM relationships r
JOIN entities source ON r.source_entity_id = source.id
JOIN entities target ON r.target_entity_id = target.id
WHERE r.relationship_type = 'DEPENDS_ON'
  AND r.tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3'
LIMIT 20;
```

**What we're looking for**: Do DEPENDS_ON relationships exist? What entities are connected?

---

### Query E: Overall Relationship Health
```sql
SELECT 
    'Total Entities' as metric, COUNT(*) as value 
FROM entities WHERE tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3' AND lifecycle_state = 'TRUSTED'
UNION ALL
SELECT 
    'Total Relationships', COUNT(*) 
FROM relationships WHERE tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3' AND lifecycle_state = 'TRUSTED'
UNION ALL
SELECT 
    'Entities WITH relationships', COUNT(DISTINCT e.id)
FROM entities e
JOIN relationships r ON e.id = r.source_entity_id OR e.id = r.target_entity_id
WHERE e.tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3' AND e.lifecycle_state = 'TRUSTED'
UNION ALL
SELECT 
    'Entities WITHOUT relationships', COUNT(*)
FROM entities e
WHERE e.tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3' 
  AND e.lifecycle_state = 'TRUSTED'
  AND NOT EXISTS (
    SELECT 1 FROM relationships r 
    WHERE r.source_entity_id = e.id OR r.target_entity_id = e.id
  );
```

**What we're looking for**: What percentage of entities have ANY relationships?

---

## Step 2: Test Graph UI with Connected Entity

1. Open Memory Graph UI
2. Search for an entity from Query A that has 10+ relationships (e.g., "Incident Report: Checkout Service SEV2")
3. Click on it
4. Check:
   - Does the graph show real edges (not just the speculative spiral)?
   - Do relationships display proper types (DEPENDS_ON, AFFECTS, etc.)?
   - Do entity names resolve correctly (not "Unknown")?

**Screenshot the result** — compare to the Payments DB spiral.

---

## Step 3: Test RLM with Connected Entity

```python
from context_foundry.core import ContextFoundry

cf = ContextFoundry(tenant_id="f3dd3201-7225-4a55-9264-445f99d0eba3")

# Find an entity name from Query A that has relationships
# Replace with actual entity name from your results
result = cf.query(
    "What is related to Incident Report: Checkout Service SEV2?",
    force_tier="tier2"
)

print(f"Entities discovered: {len(result.get('entities_discovered', []))}")
print(f"Relationships discovered: {len(result.get('relationships_discovered', []))}")
print(f"Answer: {result.get('answer', 'No answer')[:500]}")
```

---

## Step 4: Report Findings

Please report back with:

### A. Query Results Summary
| Query | Key Finding |
|-------|-------------|
| A (Top entities) | Which entity types have most relationships? |
| B (Type distribution) | What % are DEPENDS_ON vs POTENTIALLY_RELATES_TO? |
| C (SERVICE entities) | Do services have relationships? |
| D (DEPENDS_ON sample) | Do semantic dependencies exist? |
| E (Health metrics) | What % of entities are connected? |

### B. Graph UI Test
- Did connected entity render properly?
- Screenshot comparison: connected entity vs Payments DB

### C. RLM Test
- Did RLM find relationships for connected entity?
- What was the answer quality?

---

## Possible Conclusions

| Finding | Conclusion | Action |
|---------|------------|--------|
| Many entities have real relationships, Payments DB is just unconnected | No systemic problem | Test RLM with connected entities |
| Only DOCUMENT entities have relationships | Extraction creating doc links, not service dependencies | Fix extraction prompt |
| Most relationships are POTENTIALLY_RELATES_TO | Type classification failing | Fix extraction to use schema types |
| SERVICE entities have DEPENDS_ON | System works | Payments DB is just an outlier |
| <5% entities have relationships | Sparse graph problem | Need relationship enrichment |

---

## Do NOT Proceed With Fixes Until This Verification Is Complete

We need data before conclusions.
