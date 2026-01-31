# Context Foundry: Phase 1 Implementation (76% → 82%+)

## Scope

**In scope (this phase)**:
- SUPPLIES_TO extraction with targets + canonical mapping
- Anchor organization filtering with edge_rank preference
- Sync extraction with worker health check
- Deterministic smoke tests for each fix

**Deferred to Phase 2**:
- REPORTS_TO inference engine
- Temporal data handling
- Role assignment fixes (Q5, Q68)

---

# Part A: SUPPLIES_TO Relationship Extraction

**Target questions**: Q17, Q18, Q78, Q95

## A1. Add Supplier Patterns

**File**: `src/context_foundry/extraction/post_processor.py`

```python
import re
from typing import List, Dict, Optional

# Supplier relationship patterns
# Format: (pattern, relationship_type, confidence)
# Patterns capture: group(1)=supplier, group(2)=product/service, group(3)=recipient (if present)
SUPPLIER_PATTERNS = [
    # Active: "X supplies/provides Y to/for Z"
    (
        r"(\b[A-Z][a-zA-Z\s]{2,30}?)\s+(?:supplies?|provides?|delivers?|furnishes?)\s+(.+?)\s+(?:to|for)\s+([A-Z][a-zA-Z\s]+?)(?:\.|,|$)",
        "SUPPLIES_TO",
        0.85
    ),
    # Active without recipient: "X supplies/provides Y"
    (
        r"(\b[A-Z][a-zA-Z\s]{2,30}?)\s+(?:supplies?|provides?|delivers?)\s+([a-zA-Z\s]+?)(?:\.|,|$)",
        "SUPPLIES_TO",
        0.80
    ),
    # Passive: "Y supplied/provided by X"
    (
        r"([a-zA-Z\s]+?)\s+(?:supplied|provided|delivered|furnished)\s+by\s+(\b[A-Z][a-zA-Z\s]{2,30}?)(?:\.|,|$)",
        "SUPPLIES_TO",
        0.80
    ),
    # Role: "X as supplier/vendor of Y"
    (
        r"(\b[A-Z][a-zA-Z\s]{2,30}?)\s+as\s+(?:the\s+)?(?:primary\s+)?(?:supplier|vendor|provider)\s+(?:of|for)\s+(.+?)(?:\.|,|$)",
        "SUPPLIES_TO",
        0.75
    ),
    # Contract: "X contracted to supply Y"
    (
        r"(\b[A-Z][a-zA-Z\s]{2,30}?)\s+(?:contracted|engaged|selected)\s+to\s+(?:supply|provide|deliver)\s+(.+?)(?:\.|,|$)",
        "SUPPLIES_TO",
        0.80
    ),
]

# Blocklist for false positive sources
SUPPLIER_BLOCKLIST = {'the', 'a', 'an', 'this', 'that', 'these', 'their', 'our', 'its'}


def extract_supplier_relationships(text: str) -> List[Dict]:
    """
    Extract supplier relationships from text using regex patterns.

    Returns list of dicts with keys:
        - source: supplier name
        - target: recipient/project (if captured)
        - product: what is being supplied
        - relationship_type: always SUPPLIES_TO
        - confidence: pattern confidence
        - evidence: matched text
    """
    results = []
    seen = set()  # Dedupe by (source, product)

    for pattern, rel_type, confidence in SUPPLIER_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            groups = match.groups()

            # Handle passive voice (product first, then supplier)
            if 'by' in pattern:
                product = groups[0].strip() if len(groups) > 0 else ""
                source = groups[1].strip() if len(groups) > 1 else ""
                target = None
            else:
                source = groups[0].strip() if len(groups) > 0 else ""
                product = groups[1].strip() if len(groups) > 1 else ""
                target = groups[2].strip() if len(groups) > 2 else None

            # Validate source
            if len(source) < 3:
                continue
            if source.lower() in SUPPLIER_BLOCKLIST:
                continue
            if not source[0].isupper():
                continue

            # Dedupe
            key = (source.lower(), product.lower()[:30])
            if key in seen:
                continue
            seen.add(key)

            results.append({
                'source': source,
                'target': target,
                'product': product,
                'relationship_type': rel_type,
                'confidence': confidence,
                'evidence': match.group(0)[:100],
            })

    return results
```

## A2. Add Canonical Relationship Mapping

**File**: `src/context_foundry/extraction/relation_extractor.py`

Find the existing canonical mapping (or create if missing) and add:

```python
CANONICAL_RELATIONSHIP_TYPES = {
    # ... existing mappings ...

    # Supplier relationships
    'SUPPLIES_TO': 'SUPPLIES_TO',
    'SUPPLIES': 'SUPPLIES_TO',
    'PROVIDES_TO': 'SUPPLIES_TO',
    'DELIVERS_TO': 'SUPPLIES_TO',
    'VENDOR_FOR': 'SUPPLIES_TO',
    'VENDOR_OF': 'SUPPLIES_TO',
    'SUPPLIER_OF': 'SUPPLIES_TO',
    'SUPPLIER_FOR': 'SUPPLIES_TO',
    'CONTRACTED_TO_SUPPLY': 'SUPPLIES_TO',
}

def canonicalize_relationship_type(rel_type: str) -> str:
    """Map relationship type to canonical form."""
    normalized = rel_type.upper().replace(' ', '_')
    return CANONICAL_RELATIONSHIP_TYPES.get(normalized, normalized)
```

## A3. Integrate into Extraction Pipeline

**File**: `src/context_foundry/extraction/relation_extractor.py`

In the `extract()` method, after LLM-based extraction:

```python
from .post_processor import extract_supplier_relationships

def extract(self, text: str, entities: list) -> list:
    """Extract relationships from text."""
    relationships = []

    # Existing LLM extraction
    llm_relationships = self._extract_with_llm(text, entities)
    relationships.extend(llm_relationships)

    # Pattern-based supplier extraction (deterministic)
    supplier_rels = extract_supplier_relationships(text)

    for rel in supplier_rels:
        # Find source entity
        source_entity = self._find_entity(rel['source'], entities)
        if not source_entity:
            continue

        # Find target entity if specified
        target_entity = None
        if rel['target']:
            target_entity = self._find_entity(rel['target'], entities)

        relationships.append({
            'source_id': source_entity['id'],
            'source_name': rel['source'],
            'target_id': target_entity['id'] if target_entity else None,
            'target_name': rel['target'] or rel['product'],
            'relationship_type': canonicalize_relationship_type(rel['relationship_type']),
            'confidence': rel['confidence'],
            'provenance': 'pattern_match',
            'evidence': rel['evidence'],
            'properties': {
                'product': rel['product'],
            }
        })

    return relationships
```

## A4. Smoke Test for SUPPLIES_TO

**File**: `tests/smoke/test_supplies_to.py`

```python
"""
Deterministic smoke test for SUPPLIES_TO extraction.
Run: python -m pytest tests/smoke/test_supplies_to.py -v
"""
import pytest
from src.context_foundry.extraction.post_processor import extract_supplier_relationships


class TestSupplierPatterns:
    """Test supplier pattern matching - no LLM, pure regex."""

    # Q17: Nel Hydrogen
    def test_q17_nel_hydrogen(self):
        text = "Nel Hydrogen supplies electrolyzers for the GreenHydrogen facility"
        result = extract_supplier_relationships(text)
        assert len(result) >= 1, "Should extract Nel Hydrogen"
        assert any(r['source'] == 'Nel Hydrogen' for r in result)
        assert any('electrolyzer' in r['product'].lower() for r in result)

    # Q18: Shell
    def test_q18_shell_offtake(self):
        text = "Shell provides hydrogen offtake services to Nexus Industries"
        result = extract_supplier_relationships(text)
        assert len(result) >= 1, "Should extract Shell"
        assert any(r['source'] == 'Shell' for r in result)

    # Q78: Honeywell
    def test_q78_honeywell(self):
        text = "Honeywell delivers flight computers for the Falcon X program"
        result = extract_supplier_relationships(text)
        assert len(result) >= 1, "Should extract Honeywell"
        assert any(r['source'] == 'Honeywell' for r in result)
        assert any('flight computer' in r['product'].lower() for r in result)

    # Q95: Raytheon
    def test_q95_raytheon(self):
        text = "The SAR radar system is supplied by Raytheon"
        result = extract_supplier_relationships(text)
        assert len(result) >= 1, "Should extract Raytheon"
        assert any('Raytheon' in r['source'] for r in result)

    # Negative case
    def test_no_false_positives(self):
        text = "The company reported quarterly earnings of $8.45 billion"
        result = extract_supplier_relationships(text)
        assert len(result) == 0, "Should not match non-supplier text"

    # Edge case: passive voice
    def test_passive_voice(self):
        text = "Components are furnished by Lockheed Martin"
        result = extract_supplier_relationships(text)
        assert len(result) >= 1
        assert any('Lockheed Martin' in r['source'] for r in result)


class TestCanonicalMapping:
    """Test relationship type canonicalization."""

    def test_supplies_variants(self):
        from src.context_foundry.extraction.relation_extractor import canonicalize_relationship_type

        variants = ['SUPPLIES', 'PROVIDES_TO', 'VENDOR_FOR', 'SUPPLIER_OF']
        for v in variants:
            assert canonicalize_relationship_type(v) == 'SUPPLIES_TO'
```

**Run command**:
```bash
python -m pytest tests/smoke/test_supplies_to.py -v
```

**Expected**: All 7 tests pass

---

# Part B: Anchor Organization Filtering

**Target question**: Q40 (Boeing contamination)

## B1. Add Filter with Edge Rank

**File**: `src/context_foundry/agents/directed_retriever.py`

```python
# Edge rank for relationship preference
EDGE_RANK = {
    'HOLDS_POSITION': 100,
    'LEADS': 90,
    'MANAGES': 85,
    'REPORTS_TO': 80,
    'WORKS_FOR': 50,
    'MEMBER_OF': 40,
    'ASSOCIATED_WITH': 20,
}

def get_edge_rank(relationship_type: str) -> int:
    """Get priority rank for relationship type. Higher = more authoritative."""
    return EDGE_RANK.get(relationship_type.upper(), 10)


def filter_by_anchor_organization(
    self,
    entities: list,
    anchor_org: str,
    prefer_higher_rank: bool = True
) -> list:
    """
    Filter entities to anchor organization and rank by edge authority.

    Args:
        entities: List of entity dicts with 'properties' containing 'organization'
        anchor_org: Organization to filter by (e.g., "Nexus Industries")
        prefer_higher_rank: If True, sort by edge_rank descending

    Returns:
        Filtered and optionally ranked entities
    """
    if not anchor_org:
        return entities

    anchor_lower = anchor_org.lower().strip()
    filtered = []

    for entity in entities:
        props = entity.get('properties') or {}
        entity_org = (props.get('organization') or '').lower().strip()

        # Include if: same org, or no org specified (generic/shared entity)
        if not entity_org or entity_org == anchor_lower:
            filtered.append(entity)

    # Rank by edge type if relationships are present
    if prefer_higher_rank:
        filtered.sort(
            key=lambda e: get_edge_rank(e.get('relationship_type', '')),
            reverse=True
        )

    return filtered
```

## B2. Update Call Sites

**File**: `src/context_foundry/agents/directed_retriever.py`

Update `_get_direct_relationships`:

```python
def _get_direct_relationships(
    self,
    entity_id: str,
    direction: str = "both",
    relationship_types: list = None,
    anchor_organization: str = None,  # NEW PARAMETER
) -> list:
    """Get direct relationships for an entity."""

    # ... existing query logic ...

    results = self.db.execute(query, params).fetchall()

    # Convert to dicts
    results = [dict(r) for r in results]

    # Apply anchor filter and edge ranking
    if anchor_organization:
        results = self.filter_by_anchor_organization(
            results,
            anchor_organization,
            prefer_higher_rank=True
        )

    return results
```

Update `execute()`:

```python
def execute(self, intent: QueryIntent, context: dict = None) -> RetrievalResult:
    """Execute directed graph retrieval."""

    # Get anchor organization from context
    anchor_org = None
    if context:
        anchor_org = context.get('anchor_organization')
    if not anchor_org and hasattr(intent, 'context') and intent.context:
        anchor_org = intent.context.get('organization')

    # ... existing entity resolution ...

    # Pass anchor to relationship queries
    relationships = self._get_direct_relationships(
        entity_id=resolved_entity.id,
        direction=intent.direction,
        relationship_types=intent.relationship_types,
        anchor_organization=anchor_org,  # PASS IT THROUGH
    )

    # ... rest of method ...
```

## B3. Set Anchor via Tenant Metadata

**File**: `src/context_foundry/agents/query_pipeline.py`

```python
def _get_anchor_organization(self, tenant_id: str) -> str:
    """
    Get anchor organization from tenant metadata.
    Falls back to vault-based lookup if metadata not set.
    """
    # Try tenant metadata first
    try:
        tenant = self.tenant_service.get_tenant(tenant_id)
        if tenant and tenant.get('metadata', {}).get('anchor_organization'):
            return tenant['metadata']['anchor_organization']
    except Exception:
        pass

    # Fallback: vault-based mapping (for backwards compatibility)
    VAULT_ANCHOR_FALLBACK = {
        "e7c8b55c": "Nexus Industries",
        "07b831b8": "Manus Medsync",
        "d023e091": "Manus Healthtec",
    }

    vault_prefix = tenant_id[:8] if tenant_id else ""
    return VAULT_ANCHOR_FALLBACK.get(vault_prefix)
```

In query processing, set the anchor:

```python
def process_query(self, query: str, tenant_id: str, vault_id: str = None) -> dict:
    """Process a query through the pipeline."""

    # Determine anchor organization
    anchor_org = self._get_anchor_organization(vault_id or tenant_id)

    context = {
        'tenant_id': tenant_id,
        'vault_id': vault_id,
        'anchor_organization': anchor_org,  # SET IT HERE
    }

    # ... rest of pipeline ...
```

## B4. Smoke Test for Anchor Filtering

**File**: `tests/smoke/test_anchor_filter.py`

```python
"""
Deterministic smoke test for anchor organization filtering.
Run: python -m pytest tests/smoke/test_anchor_filter.py -v
"""
import pytest


class TestAnchorFilter:
    """Test anchor organization filtering - no LLM."""

    @pytest.fixture
    def sample_entities(self):
        return [
            {'name': 'Backlog', 'value': '12.4B',
             'properties': {'organization': 'Nexus Industries'},
             'relationship_type': 'HAS_METRIC'},
            {'name': 'Backlog', 'value': '11.5B',
             'properties': {'organization': 'Boeing'},
             'relationship_type': 'HAS_METRIC'},
            {'name': 'Revenue', 'value': '8.45B',
             'properties': {},  # No org = generic
             'relationship_type': 'HAS_METRIC'},
            {'name': 'CEO', 'value': 'Dr. Victoria Chen',
             'properties': {'organization': 'Nexus Industries'},
             'relationship_type': 'HOLDS_POSITION'},
            {'name': 'Engineer', 'value': 'Jane Doe',
             'properties': {'organization': 'Nexus Industries'},
             'relationship_type': 'WORKS_FOR'},
        ]

    def test_filters_out_boeing(self, sample_entities):
        from src.context_foundry.agents.directed_retriever import DirectedGraphRetriever

        retriever = DirectedGraphRetriever.__new__(DirectedGraphRetriever)
        filtered = retriever.filter_by_anchor_organization(
            sample_entities,
            'Nexus Industries'
        )

        orgs = [e['properties'].get('organization') for e in filtered]
        assert 'Boeing' not in orgs, "Boeing should be filtered out"

    def test_keeps_nexus(self, sample_entities):
        from src.context_foundry.agents.directed_retriever import DirectedGraphRetriever

        retriever = DirectedGraphRetriever.__new__(DirectedGraphRetriever)
        filtered = retriever.filter_by_anchor_organization(
            sample_entities,
            'Nexus Industries'
        )

        nexus_count = sum(1 for e in filtered
                         if e['properties'].get('organization') == 'Nexus Industries')
        assert nexus_count >= 2, "Nexus entities should be kept"

    def test_keeps_generic_entities(self, sample_entities):
        from src.context_foundry.agents.directed_retriever import DirectedGraphRetriever

        retriever = DirectedGraphRetriever.__new__(DirectedGraphRetriever)
        filtered = retriever.filter_by_anchor_organization(
            sample_entities,
            'Nexus Industries'
        )

        # Revenue has no org, should be kept
        assert any(e['name'] == 'Revenue' for e in filtered)

    def test_edge_rank_ordering(self, sample_entities):
        from src.context_foundry.agents.directed_retriever import DirectedGraphRetriever

        retriever = DirectedGraphRetriever.__new__(DirectedGraphRetriever)
        filtered = retriever.filter_by_anchor_organization(
            sample_entities,
            'Nexus Industries',
            prefer_higher_rank=True
        )

        # HOLDS_POSITION (100) should come before WORKS_FOR (50)
        types = [e.get('relationship_type') for e in filtered]
        if 'HOLDS_POSITION' in types and 'WORKS_FOR' in types:
            assert types.index('HOLDS_POSITION') < types.index('WORKS_FOR')


class TestEdgeRank:
    """Test edge ranking function."""

    def test_holds_position_highest(self):
        from src.context_foundry.agents.directed_retriever import get_edge_rank

        assert get_edge_rank('HOLDS_POSITION') > get_edge_rank('WORKS_FOR')
        assert get_edge_rank('HOLDS_POSITION') > get_edge_rank('MEMBER_OF')

    def test_leads_above_works_for(self):
        from src.context_foundry.agents.directed_retriever import get_edge_rank

        assert get_edge_rank('LEADS') > get_edge_rank('WORKS_FOR')

    def test_unknown_type_low_rank(self):
        from src.context_foundry.agents.directed_retriever import get_edge_rank

        assert get_edge_rank('UNKNOWN_TYPE') == 10
```

**Run command**:
```bash
python -m pytest tests/smoke/test_anchor_filter.py -v
```

**Expected**: All 7 tests pass

---

# Part C: Sync Extraction with Health Check

## C1. Add Sync Extraction Option

**File**: `platform_foundation/src/document_service.py`

```python
def upload_document(
    self,
    tenant_id: str,
    filename: str,
    mime_type: str,
    file_content: bytes,
    auto_extract: bool = True,
    sync_extract: bool = False,  # NEW
    priority: str = "normal"
) -> dict:
    """
    Upload a document and optionally trigger extraction.

    Args:
        sync_extract: If True, run extraction synchronously (blocks until done).
                      Use for small batches or when worker may not be running.
    """
    # ... existing upload logic to create document record ...

    if auto_extract:
        if sync_extract:
            # Synchronous extraction - run inline
            document = self._extract_sync(document, tenant_id)
        else:
            # Async - queue for worker
            extraction_request = self.queue_for_extraction(
                document_id=UUID(str(document['id'])),
                tenant_id=tenant_id,
                priority=priority
            )
            document['extraction_request_id'] = extraction_request['request_id']

            # Check worker health
            pending = self._count_pending_extractions()
            if pending > 10:
                logger.warning(f"Found {pending} pending extractions - worker may be behind")

    return document


def _extract_sync(self, document: dict, tenant_id: str) -> dict:
    """Run extraction synchronously."""
    from context_foundry.extraction.extraction_pipeline import ExtractionPipeline

    try:
        pipeline = ExtractionPipeline()
        result = pipeline.process_document(
            document_id=str(document['id']),
            tenant_id=tenant_id
        )
        document['extraction_status'] = 'completed'
        document['extraction_result'] = {
            'entities': result.get('entity_count', 0),
            'relationships': result.get('relationship_count', 0),
        }
    except Exception as e:
        logger.error(f"Sync extraction failed for {document['id']}: {e}")
        document['extraction_status'] = 'failed'
        document['extraction_error'] = str(e)

    return document


def _count_pending_extractions(self) -> int:
    """Count pending extraction requests in the last hour."""
    query = """
        SELECT COUNT(*)
        FROM platform.extraction_requests
        WHERE status = 'pending'
        AND created_at > NOW() - INTERVAL '1 hour'
    """
    try:
        result = self.db.execute(query)
        return result.scalar() or 0
    except Exception:
        return 0
```

## C2. Smoke Test for Sync Extraction

**File**: `tests/smoke/test_sync_extraction.py`

```python
"""
Smoke test for sync extraction option.
Run: python -m pytest tests/smoke/test_sync_extraction.py -v
"""
import pytest
import inspect


class TestSyncExtractionSignature:
    """Verify sync_extract parameter exists."""

    def test_upload_has_sync_param(self):
        from platform_foundation.src.document_service import DocumentService

        sig = inspect.signature(DocumentService.upload_document)
        params = list(sig.parameters.keys())

        assert 'sync_extract' in params, "upload_document should have sync_extract param"

    def test_sync_param_default_false(self):
        from platform_foundation.src.document_service import DocumentService

        sig = inspect.signature(DocumentService.upload_document)
        sync_param = sig.parameters.get('sync_extract')

        assert sync_param is not None
        assert sync_param.default is False, "sync_extract should default to False"


class TestHealthCheck:
    """Verify health check function exists."""

    def test_count_pending_exists(self):
        from platform_foundation.src.document_service import DocumentService

        ds = DocumentService.__new__(DocumentService)
        assert hasattr(ds, '_count_pending_extractions')
```

**Run command**:
```bash
python -m pytest tests/smoke/test_sync_extraction.py -v
```

**Expected**: All 3 tests pass

---

# Part D: Regression Verification

## D1. Run Full 100-Question Suite

After implementing Parts A, B, C:

```bash
# Re-extract corpus with new patterns (use sync mode)
python3 -c "
from platform_foundation.src.document_service import DocumentService
ds = DocumentService()
vault_id = 'e7c8b55c-7765-462a-bec2-c7f1072961ac'

# Clear existing extraction data (entities/relationships only)
ds.clear_extraction_data(vault_id)

# Re-extract all documents
docs = ds.list_documents(vault_id)
print(f'Re-extracting {len(docs)} documents...')
for i, doc in enumerate(docs):
    ds.trigger_extraction(doc['id'], sync_extract=True)
    if (i + 1) % 20 == 0:
        print(f'  {i + 1}/{len(docs)} done')
print('Extraction complete.')
"

# Run test suite
python -m src.test_runner.runner \
    --vault-id "e7c8b55c-7765-462a-bec2-c7f1072961ac" \
    --questions "src/test_questions/nexus_100q.json"
```

**Expected output**:
```
Score: 82+/100 (82%+)

Specifically check:
- Q17 (Nel Hydrogen): PASS
- Q18 (Shell): PASS
- Q40 (Backlog): PASS (no Boeing)
- Q78 (Honeywell): PASS
- Q95 (Raytheon): PASS
```

## D2. Regression Checklist

| Test | Command | Pass Criteria |
|------|---------|---------------|
| SUPPLIES_TO patterns | `pytest tests/smoke/test_supplies_to.py -v` | 7/7 pass |
| Anchor filter | `pytest tests/smoke/test_anchor_filter.py -v` | 7/7 pass |
| Sync extraction | `pytest tests/smoke/test_sync_extraction.py -v` | 3/3 pass |
| Full suite | `python -m src.test_runner.runner ...` | 82+ correct |

---

# Summary

## Files Modified

| File | Changes |
|------|---------|
| `src/context_foundry/extraction/post_processor.py` | Add SUPPLIER_PATTERNS, extract_supplier_relationships() |
| `src/context_foundry/extraction/relation_extractor.py` | Add canonical mapping, integrate supplier extraction |
| `src/context_foundry/agents/directed_retriever.py` | Add EDGE_RANK, filter_by_anchor_organization(), update call sites |
| `src/context_foundry/agents/query_pipeline.py` | Add _get_anchor_organization(), set context |
| `platform_foundation/src/document_service.py` | Add sync_extract param, _extract_sync(), _count_pending_extractions() |

## Files Created

| File | Purpose |
|------|---------|
| `tests/smoke/test_supplies_to.py` | Pattern matching tests (Q17, Q18, Q78, Q95) |
| `tests/smoke/test_anchor_filter.py` | Organization filtering tests (Q40) |
| `tests/smoke/test_sync_extraction.py` | Sync extraction signature tests |

## Expected Results

| Metric | Before | After |
|--------|--------|-------|
| Accuracy | 76/100 | 82+/100 |
| Q17 (Nel Hydrogen) | FAIL | PASS |
| Q18 (Shell) | FAIL | PASS |
| Q40 (Boeing contamination) | FAIL | PASS |
| Q78 (Honeywell) | FAIL | PASS |
| Q95 (Raytheon) | FAIL | PASS |

---

# Phase 2 (Next)

After Phase 1 is verified at 82%+:

1. **REPORTS_TO inference engine** - infer CFO→CEO relationships (Q15)
2. **Temporal data handling** - track role changes over time (Q38, Q61)
3. **Role assignment fixes** - ITAR Empowered Official (Q5, Q68)

Target: 82% → 88%+
