# MANDATORY FIX: Anchor Filter Not Wired Up

**Date:** January 28, 2026
**Priority:** CRITICAL - BLOCKING
**Current Accuracy:** 76%
**Target After Fix:** 80%+

---

## Executive Summary

**The `filter_by_anchor_organization` function exists but is NEVER CALLED.**

This causes:
- Q2: Returns Boeing's CFO (Rahul Ghai) instead of Nexus's CFO (Michael Chang)
- Q40: Returns Boeing's backlog ($11.5B) instead of Nexus's backlog ($12.4B)
- Multiple other cross-organization contamination issues

**Proof:**
```bash
$ grep -r "filter_by_anchor" src/
# Returns ONLY the function definition at line 59 - no calls anywhere
```

---

## PART 1: THE FIX

### File: `src/context_foundry/agents/directed_retriever.py`

---

### Change 1: Modify `__init__` (around line 255)

**FIND:**
```python
def __init__(self, session: Session, tenant_id: str):
    self.session = session
    self.tenant_id = str(tenant_id)
    self.entity_resolver = EntityResolver(session, tenant_id)
```

**REPLACE WITH:**
```python
def __init__(self, session: Session, tenant_id: str, anchor_organization: str = None):
    self.session = session
    self.tenant_id = str(tenant_id)
    self.anchor_organization = anchor_organization
    self.entity_resolver = EntityResolver(session, tenant_id)

    # If no anchor provided, try to get from tenant metadata
    if not self.anchor_organization:
        self.anchor_organization = self._get_anchor_from_tenant()
```

---

### Change 2: Add helper method (after `__init__`, around line 266)

**ADD THIS NEW METHOD:**
```python
def _get_anchor_from_tenant(self) -> Optional[str]:
    """Get anchor organization from tenant metadata."""
    try:
        result = self.session.execute(
            text("""
                SELECT metadata->>'anchor_organization' as anchor
                FROM platform.tenants
                WHERE id = :tid
            """),
            {'tid': self.tenant_id}
        ).fetchone()

        if result and result.anchor:
            logger.info(f"[AnchorFilter] Found anchor organization: {result.anchor}")
            return result.anchor
    except Exception as e:
        logger.warning(f"[AnchorFilter] Could not get anchor organization: {e}")

    return None
```

---

### Change 3: Call the filter in `execute()` (around line 333)

**FIND:**
```python
affected = self._collect_affected_entities(relationships, entity_id)

if intent.target_type:
```

**REPLACE WITH:**
```python
affected = self._collect_affected_entities(relationships, entity_id)

# CRITICAL: Filter by anchor organization to prevent cross-org contamination (e.g., Boeing in Nexus queries)
if self.anchor_organization:
    affected_before = len(affected)
    affected = filter_by_anchor_organization(affected, self.anchor_organization)
    if affected_before != len(affected):
        logger.info(f"[AnchorFilter] Filtered {affected_before} -> {len(affected)} entities (removed {affected_before - len(affected)} cross-org)")

if intent.target_type:
```

---

### Change 4: Set anchor organization for Nexus vault

**RUN THIS SQL:**
```sql
-- Set anchor organization for the Nexus vault
UPDATE platform.tenants
SET metadata = COALESCE(metadata, '{}'::jsonb) || '{"anchor_organization": "Nexus Industries"}'::jsonb
WHERE id = '1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91';

-- Verify it was set
SELECT id, name, metadata->>'anchor_organization' as anchor
FROM platform.tenants
WHERE id = '1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91';
```

---

## PART 2: MANDATORY TESTS

### Test File: `tests/test_anchor_filter_critical.py`

**CREATE THIS FILE AND RUN IT:**

```python
"""
CRITICAL: These tests MUST pass before deployment.
Tests the anchor organization filter that prevents Boeing data in Nexus queries.
"""
import pytest
from context_foundry.agents.directed_retriever import filter_by_anchor_organization


class TestAnchorFilterCritical:
    """Tests that MUST pass to fix Q2 and Q40."""

    def test_boeing_excluded_when_anchor_is_nexus(self):
        """CRITICAL: Boeing entities must be filtered out when querying Nexus."""
        entities = [
            {'name': 'Total Backlog', 'organization': 'Nexus Industries', 'value': '12.4B'},
            {'name': 'Total Backlog', 'organization': 'The Boeing Company', 'value': '11.5B'},
        ]

        filtered = filter_by_anchor_organization(entities, 'Nexus Industries')

        assert len(filtered) == 1, f"Expected 1 entity, got {len(filtered)}"
        assert filtered[0]['organization'] == 'Nexus Industries'
        assert filtered[0]['value'] == '12.4B'

    def test_boeing_cfo_excluded(self):
        """CRITICAL: Boeing's CFO must not appear in Nexus queries."""
        entities = [
            {'name': 'Michael Chang', 'organization': 'Nexus Industries', 'role': 'CFO'},
            {'name': 'Rahul Ghai', 'organization': 'Boeing', 'role': 'CFO'},
            {'name': 'Rahul Ghai', 'organization': 'The Boeing Company', 'role': 'CFO'},
        ]

        filtered = filter_by_anchor_organization(entities, 'Nexus Industries')

        assert len(filtered) == 1, f"Expected 1 CFO, got {len(filtered)}"
        assert filtered[0]['name'] == 'Michael Chang'

        # Verify NO Boeing entities leaked through
        for entity in filtered:
            org = entity.get('organization', '').lower()
            assert 'boeing' not in org, f"Boeing leaked through: {entity}"

    def test_generic_entities_kept(self):
        """Entities without organization should be kept."""
        entities = [
            {'name': 'Generic Metric', 'value': '100'},  # No org - keep
            {'name': 'Nexus Metric', 'organization': 'Nexus Industries', 'value': '200'},
            {'name': 'Boeing Metric', 'organization': 'Boeing', 'value': '300'},  # Filter out
        ]

        filtered = filter_by_anchor_organization(entities, 'Nexus Industries')

        assert len(filtered) == 2, "Should keep generic + Nexus, filter Boeing"

    def test_partial_org_match(self):
        """Should match partial organization names."""
        entities = [
            {'name': 'A', 'organization': 'Nexus Industries Inc.'},
            {'name': 'B', 'organization': 'Nexus'},
            {'name': 'C', 'organization': 'Boeing Corporation'},
        ]

        filtered = filter_by_anchor_organization(entities, 'Nexus')

        assert len(filtered) == 2, "Should match 'Nexus' in both Nexus orgs"

    def test_empty_anchor_returns_all(self):
        """Empty anchor should not filter anything."""
        entities = [
            {'name': 'A', 'organization': 'Nexus'},
            {'name': 'B', 'organization': 'Boeing'},
        ]

        filtered = filter_by_anchor_organization(entities, '')
        assert len(filtered) == 2

        filtered = filter_by_anchor_organization(entities, None)
        assert len(filtered) == 2


# Run with: pytest tests/test_anchor_filter_critical.py -v
```

---

## PART 3: VERIFICATION COMMANDS

### Step 1: Run unit tests
```bash
pytest tests/test_anchor_filter_critical.py -v
```
**Must show: 5 passed**

---

### Step 2: Run existing smoke tests
```bash
pytest tests/smoke/test_anchor_filter.py -v
```
**Must show: All passed**

---

### Step 3: Verify SQL update worked
```sql
SELECT id, name, metadata->>'anchor_organization' as anchor
FROM platform.tenants
WHERE name ILIKE '%nexus%';
```
**Must show: anchor = "Nexus Industries"**

---

### Step 4: Run integration tests
```bash
python cf_integration_tests.py --all
```
**Must show: Exit code 0**

---

### Step 5: Run Q40 and Q2 manually
```python
from context_foundry.core import ContextFoundry

cf = ContextFoundry(vault_id='1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91')

# Test Q40
response = cf.query("What is the total company backlog?")
print(f"Q40: {response['answer']}")
# MUST contain "12.4" and NOT contain "Boeing"

# Test Q2
response = cf.query("What is the name of the CFO?")
print(f"Q2: {response['answer']}")
# MUST contain "Michael Chang" and NOT contain "Rahul Ghai"
```

---

### Step 6: Run full 100-question regression
```bash
python -m src.test_runner.runner --vault-id "1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91" --questions "test_questions/nexus_100q.json"
```
**Must show: Accuracy > 76% (expecting 79%+)**

---

## PART 4: EXPECTED RESULTS

| Question | Before Fix | After Fix |
|----------|------------|-----------|
| Q2 (CFO) | Rahul Ghai ❌ | Michael Chang ✅ |
| Q40 (Backlog) | $11.5B Boeing ❌ | $12.4B Nexus ✅ |
| Q19 (Largest customer) | Airbus ❌ | Boeing $730M ✅ |
| **Accuracy** | **76%** | **79%+** |

---

## PART 5: SUPPLIES_TO VERIFICATION

After fixing the anchor filter, verify SUPPLIES_TO relationships exist:

```sql
-- Check for SUPPLIES_TO relationships
SELECT COUNT(*) as count
FROM relationships
WHERE tenant_id = '1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91'
AND relationship_type = 'SUPPLIES_TO';

-- If count = 0, re-extraction is needed
-- If count > 0, the patterns are working
```

**If SUPPLIES_TO count = 0:**
1. Force re-extraction of key documents
2. Check pattern matching in `post_processor.py`
3. See separate document: `CF_Replit_Verify_SUPPLIES_TO.md`

---

## DO NOT DEPLOY CHECKLIST

- [ ] All 5 unit tests pass
- [ ] Smoke tests pass
- [ ] SQL shows anchor_organization set
- [ ] Q40 returns Nexus's $12.4B (not Boeing's $11.5B)
- [ ] Q2 returns Michael Chang (not Rahul Ghai)
- [ ] Integration tests pass
- [ ] Full regression shows > 76% accuracy

---

## Summary of Code Changes

| File | Line | Change |
|------|------|--------|
| `directed_retriever.py` | ~255 | Add `anchor_organization` parameter to `__init__` |
| `directed_retriever.py` | ~266 | Add `_get_anchor_from_tenant()` method |
| `directed_retriever.py` | ~333 | Call `filter_by_anchor_organization()` in `execute()` |
| Database | - | Set metadata.anchor_organization on tenant |

**Total: 3 code changes + 1 SQL update**
