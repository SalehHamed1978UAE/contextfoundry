# Fix: Incident Impact Query

## The Bug

Query: "What was affected by incident INC-2025-1201?"
Result: Entity not found, confidence 0.00

## Debug Steps

### Step 1: Find what incident entities actually exist

```python
from sqlalchemy import text
from context_foundry.models.database import get_session

session = get_session()

# Set tenant context
session.execute(text("SET app.current_tenant_id = :tid"), {"tid": DEMO_TENANT_ID})

# Find ALL incident entities
incidents = session.execute(text("""
    SELECT id, name, entity_type 
    FROM entities 
    WHERE tenant_id = :tid 
    AND (entity_type = 'INCIDENT' OR name ILIKE '%inc%' OR name ILIKE '%2025%')
"""), {"tid": DEMO_TENANT_ID}).fetchall()

print("Incident-like entities found:")
for inc in incidents:
    print(f"  ID: {inc.id}")
    print(f"  Name: '{inc.name}'")
    print(f"  Type: {inc.entity_type}")
    print()
```

### Step 2: Find AFFECTS relationships

```python
# Find all AFFECTS relationships
affects = session.execute(text("""
    SELECT r.id, 
           s.name as source_name, 
           t.name as target_name,
           r.confidence
    FROM relationships r
    JOIN entities s ON r.source_entity_id = s.id
    JOIN entities t ON r.target_entity_id = t.id
    WHERE r.tenant_id = :tid 
    AND r.relationship_type = 'AFFECTS'
"""), {"tid": DEMO_TENANT_ID}).fetchall()

print(f"AFFECTS relationships: {len(affects)}")
for a in affects:
    print(f"  {a.source_name} -[AFFECTS]-> {a.target_name} (conf: {a.confidence})")
```

### Step 3: Fix based on findings

**If incident entity exists but with different name:**
- Update entity resolution to handle the actual name format

**If incident entity doesn't exist:**
- Check extraction logs
- Manually create if needed for demo

**If AFFECTS relationships are missing:**
- The postmortems clearly list affected services
- Add the relationships manually

### Step 4: Add missing AFFECTS relationships (if needed)

From the postmortem, INC-2025-1201 affected:
- API Gateway
- Order Service  
- Payment Service
- Inventory Service
- Notification Service

```python
from uuid import uuid4, UUID

# Find the incident entity (use actual name from Step 1)
incident = session.execute(text("""
    SELECT id, name FROM entities 
    WHERE tenant_id = :tid 
    AND (name ILIKE '%1201%' OR name ILIKE '%auth%outage%')
    LIMIT 1
"""), {"tid": DEMO_TENANT_ID}).fetchone()

if not incident:
    print("ERROR: No incident entity found. Need to create one.")
else:
    print(f"Found incident: {incident.name} (id: {incident.id})")
    
    # Services that were affected
    affected_service_patterns = [
        '%api%gateway%',
        '%order%service%',
        '%payment%service%',
        '%inventory%service%',
        '%notification%service%'
    ]
    
    for pattern in affected_service_patterns:
        service = session.execute(text("""
            SELECT id, name FROM entities 
            WHERE tenant_id = :tid 
            AND name ILIKE :pattern
            AND entity_type = 'SERVICE'
            LIMIT 1
        """), {"tid": DEMO_TENANT_ID, "pattern": pattern}).fetchone()
        
        if service:
            # Check if relationship exists
            existing = session.execute(text("""
                SELECT id FROM relationships 
                WHERE source_entity_id = :src 
                AND target_entity_id = :tgt
                AND relationship_type = 'AFFECTS'
            """), {"src": incident.id, "tgt": service.id}).fetchone()
            
            if not existing:
                rel_id = str(uuid4())
                session.execute(text("""
                    INSERT INTO relationships 
                    (id, source_entity_id, target_entity_id, relationship_type, 
                     tenant_id, lifecycle_state, confidence)
                    VALUES (:id, :src, :tgt, 'AFFECTS', :tid, 'TRUSTED', 0.90)
                """), {
                    "id": rel_id,
                    "src": incident.id,
                    "tgt": service.id,
                    "tid": DEMO_TENANT_ID
                })
                print(f"Added: {incident.name} -[AFFECTS]-> {service.name}")
            else:
                print(f"Already exists: {incident.name} -[AFFECTS]-> {service.name}")
        else:
            print(f"Service not found for pattern: {pattern}")
    
    session.commit()
    # Restore tenant context after commit
    session.execute(text("SET app.current_tenant_id = :tid"), {"tid": DEMO_TENANT_ID})
```

### Step 5: Test the query

```python
from context_foundry.core import ContextFoundry

cf = ContextFoundry(tenant_id=DEMO_TENANT_ID)

# Use the actual incident name found in Step 1
result = cf.query("What was affected by incident INC-2025-1201?")
print(f"Answer: {result.get('answer')}")
print(f"Confidence: {result.get('confidence')}")

# Also try with the actual extracted name if different
# result = cf.query("What was affected by [ACTUAL_NAME]?")
```

### Step 6: If entity resolution is the issue

The query might be failing because "INC-2025-1201" doesn't match the extracted entity name exactly.

Fix in entity resolution:

```python
# In entity_resolver.py or retrieval logic

# Add incident ID pattern matching
incident_patterns = [
    r'INC-?\d{4}-?\d+',  # INC-2025-1201 or INC20251201
    r'incident\s*#?\s*\d+',  # incident #1201
]

def normalize_incident_reference(query: str) -> str:
    """Extract incident ID from various formats."""
    import re
    for pattern in incident_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(0)
    return query
```

## Report Back

After debugging, tell me:
1. What incident entities exist (exact names)
2. How many AFFECTS relationships exist
3. Whether the query works after fixes
4. The confidence score
