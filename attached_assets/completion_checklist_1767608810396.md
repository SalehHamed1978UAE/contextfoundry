# Context Foundry — Completion Checklist

> **Date**: January 5, 2026
> **Goal**: Complete all remaining work, then validate the system provides value
> **Order**: Security hardening → Data fixes → System validation

---

# PHASE 1: Defense-in-Depth (Memory Classes)

RLS is the security boundary. These filters are belt-and-suspenders.

## 1.1 SemanticMemory Tenant Filtering

**File**: `src/context_foundry/memory/semantic.py`

Add `tenant_id` parameter to constructor and filter ALL queries:

```python
class SemanticMemory:
    def __init__(self, session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def find_similar(self, query: str, k: int = 10, **kwargs):
        return self.session.query(Entity).filter(
            Entity.tenant_id == self.tenant_id,  # ADD THIS
            # ... existing filters
        ).limit(k).all()
```

**Methods to update** (from audit):
- `get_entity_by_name()` (line 110)
- `find_by_type()` (line 138)
- `get_outgoing_relationships()` (line 217)
- `get_incoming_relationships()` (line 254)
- `traverse_graph()` (line 297)
- `get_entity_with_neighbors()` (line 322)
- `find_similar_entities()` (line 556)
- `get_entity_by_id()` (line 668)
- `get_neighbors()` (line 748)
- `traverse functions` (lines 804-918)
- `promote_to_trusted()` (line 1029)
- `search_by_property()` (line 1077)
- `get_stats()` (lines 1165-1172)

**Total: 18 entity queries + 5 relationship queries**

---

## 1.2 EpisodicMemory Tenant Filtering

**File**: `src/context_foundry/memory/episodic.py`

```python
class EpisodicMemory:
    def __init__(self, session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def search(self, query: str, k: int = 10):
        return self.session.query(DocumentChunk).filter(
            DocumentChunk.tenant_id == self.tenant_id,  # ADD THIS
            # ... existing filters
        ).limit(k).all()
```

**Methods to update**:
- `get_document()` (line 121)
- `search()` (line 155)
- `search_for_rule_context()` (line 199)
- `various gets` (lines 243-261)
- `count/clear` (lines 276-277)

**Total: 8 document/chunk queries**

---

## 1.3 InferenceAgent Tenant Filtering

**File**: `src/context_foundry/agents/inference.py`

**Methods to update**:
- Path finding (lines 158-195)
- Relationship checks (lines 316-401)
- Traversal (lines 555-692)
- Entity retrieval (lines 853-876)

**Total: 15 entity + 12 relationship + 1 document queries**

---

## 1.4 RLM Memory APIs Tenant Filtering

**Files**:
- `src/context_foundry/rlm/memory_apis/semantic.py`
- `src/context_foundry/rlm/memory_apis/episodic.py`
- `src/context_foundry/rlm/memory_apis/symbolic.py`

Same pattern — add `tenant_id` to constructor, filter all queries.

---

## 1.5 Update All Callers

Wherever these classes are instantiated, pass `tenant_id`:

```python
# Before
sm = SemanticMemory(session)

# After
sm = SemanticMemory(session, tenant_id=tenant_id)
```

**Files to update**:
- `RetrievalAgent`
- `ReasoningAgent`
- `InferenceAgent`
- `RLMExecutor`
- Any other callers

---

## 1.6 Defense-in-Depth Tests

```python
def test_semantic_memory_tenant_filter():
    """Verify SemanticMemory filters by tenant even without RLS."""
    # Create entity in tenant B
    entity_b = Entity(name="SECRET", tenant_id=tenant_b, ...)
    session.add(entity_b)
    session.commit()
    
    # Query as tenant A (RLS disabled for this test)
    sm = SemanticMemory(session, tenant_id=tenant_a)
    results = sm.find_similar("SECRET")
    
    assert len(results) == 0, "Defense-in-depth filter failed!"
```

---

# PHASE 2: Background Worker Audit

## 2.1 Identify All Background Workers

```bash
grep -rn "def process\|def run\|def execute" src/context_foundry/workers/
grep -rn "celery\|background\|worker\|scheduler" src/
```

List all workers:
- Gardener
- Extraction worker
- RE Agent Batch
- Any others?

## 2.2 Verify Each Uses Tenant Session

Each worker should:
```python
def process_tenant_work(tenant_id: str):
    with tenant_session(tenant_id) as session:
        # All DB operations here
        pass
```

## 2.3 Audit Checklist

| Worker | Uses tenant_session? | RLS Active? |
|--------|---------------------|-------------|
| Gardener | ? | ? |
| Extraction | ? | ? |
| RE Agent | ? | ? |
| ... | ? | ? |

Fix any that don't use tenant_session.

---

# PHASE 3: Data Migration (NULL tenant_ids)

## 3.1 Identify Orphaned Data

```sql
-- Documents with NULL tenant_id
SELECT COUNT(*) FROM documents WHERE tenant_id IS NULL;

-- Entities with NULL tenant_id
SELECT COUNT(*) FROM entities WHERE tenant_id IS NULL;

-- Relationships with NULL tenant_id  
SELECT COUNT(*) FROM relationships WHERE tenant_id IS NULL;

-- Chunks with NULL tenant_id
SELECT COUNT(*) FROM document_chunks WHERE tenant_id IS NULL;
```

## 3.2 Decide: Assign or Delete?

**Option A**: Assign to default tenant
```sql
UPDATE documents SET tenant_id = 'f3dd3201-7225-4a55-9264-445f99d0eba3' 
WHERE tenant_id IS NULL;
```

**Option B**: Delete orphaned data
```sql
DELETE FROM entities WHERE tenant_id IS NULL;
DELETE FROM relationships WHERE tenant_id IS NULL;
DELETE FROM documents WHERE tenant_id IS NULL;
```

**Recommendation**: Assign to default tenant (preserve data for testing)

## 3.3 Add NOT NULL Constraint (After Migration)

```sql
-- Only after all NULLs are fixed
ALTER TABLE documents ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE entities ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE relationships ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE document_chunks ALTER COLUMN tenant_id SET NOT NULL;
```

## 3.4 Update RLS Policies for NOT NULL

Once tenant_id is NOT NULL, simplify policies:
```sql
-- Can remove the NULL check
CREATE OR REPLACE POLICY tenant_isolation ON entities
    FOR ALL 
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

---

# PHASE 4: System Validation

**This is the real test — does the system provide value?**

## 4.1 Test Document Already Uploaded

The health check test document has:
- 7 SERVICE entities
- 6 TEAM entities
- 2 DATABASE entities
- 2 INCIDENT entities
- 8 DEPENDS_ON relationships
- 7 MANAGES relationships
- 2 TRIGGERED_BY relationships
- 3 AFFECTS relationships

## 4.2 Tier 1 Query Tests

```python
from context_foundry.core import ContextFoundry

# Use the tenant that has the test data
cf = ContextFoundry(tenant_id="???")  # Which tenant has the health check doc?

# Test 1: Dependency query
result = cf.query("What does Order Processing Service depend on?")
print(f"Answer: {result.get('answer')}")
# EXPECTED: Mentions Payment Gateway AND Inventory Database

# Test 2: Management query
result = cf.query("Who manages the Payment Gateway?")
print(f"Answer: {result.get('answer')}")
# EXPECTED: Mentions Platform Engineering Team

# Test 3: Impact query
result = cf.query("What was affected by incident INC-2026-0105-A?")
print(f"Answer: {result.get('answer')}")
# EXPECTED: Mentions Order Processing Service

# Test 4: Reverse lookup
result = cf.query("What incidents were triggered by Payment Gateway?")
print(f"Answer: {result.get('answer')}")
# EXPECTED: Mentions INC-2026-0105-A
```

## 4.3 Tier 2 (RLM) Query Tests

```python
# Test 5: Multi-hop (RLM)
result = cf.query(
    "Trace the full dependency chain from Customer Portal to databases",
    force_tier="tier2"
)
print(f"Entities discovered: {len(result.get('entities_discovered', []))}")
print(f"Relationships discovered: {len(result.get('relationships_discovered', []))}")
print(f"Answer: {result.get('answer')}")
# EXPECTED: Customer Portal → Order Processing Service → Inventory Database
#           Customer Portal → Authentication Service → User Database

# Test 6: Impact analysis (RLM)
result = cf.query(
    "If Payment Gateway goes down, what's the full blast radius?",
    force_tier="tier2"
)
print(f"Blast radius: {result.get('blast_radius_entities', [])}")
print(f"Answer: {result.get('answer')}")
# EXPECTED: Order Processing Service, potentially Customer Portal
```

## 4.4 Comparison: Graph vs No Graph

**The real value test** — is the graph helping?

```python
# Ask something that requires relationship traversal
query = "What teams are responsible for services that had incidents this month?"

# With graph (should use relationships)
result_with_graph = cf.query(query)

# What would simple RAG return? (just text search)
# Compare manually - does the graph answer show relationships
# that wouldn't be obvious from just searching text?
```

## 4.5 Validation Report

| Test | Query | Expected Answer | Actual Answer | Pass? |
|------|-------|-----------------|---------------|-------|
| 1 | Dependency | Payment Gateway, Inventory DB | ? | ? |
| 2 | Management | Platform Engineering Team | ? | ? |
| 3 | Impact | Order Processing Service | ? | ? |
| 4 | Reverse | INC-2026-0105-A | ? | ? |
| 5 | Multi-hop | Full chain | ? | ? |
| 6 | Blast radius | Affected services | ? | ? |

---

# PHASE 5: Report Back

After completing all phases, provide:

## Summary Report

### Security Status
| Item | Status |
|------|--------|
| RLS policies active | ✅/❌ |
| Defense-in-depth filters | ✅/❌ |
| Background workers audited | ✅/❌ |
| NULL tenant_ids fixed | ✅/❌ |
| NOT NULL constraints added | ✅/❌ |

### Validation Results
| Query Type | Pass Rate |
|------------|-----------|
| Tier 1 dependency | X/Y |
| Tier 1 management | X/Y |
| Tier 1 impact | X/Y |
| Tier 2 multi-hop | X/Y |
| Tier 2 blast radius | X/Y |

### Issues Found
1. ...
2. ...
3. ...

### System Ready for Demo?
- [ ] Yes, all tests pass
- [ ] No, issues remain (list them)

---

# Execution Order

1. **Phase 1**: Defense-in-depth filters (~2 hours)
2. **Phase 2**: Background worker audit (~30 min)
3. **Phase 3**: Data migration (~30 min)
4. **Phase 4**: System validation (~1 hour)
5. **Phase 5**: Report back

**Total estimated time: 4-5 hours**

Do each phase completely before moving to the next. Report progress after each phase.
