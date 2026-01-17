# QA Accuracy Fixes Spec - Target 100%
**Date:** 2026-01-17
**Current Accuracy:** 79% (83/105 correct)
**Target Accuracy:** 100%

---

## Executive Summary

The NexaTech QA test revealed 22 issues across 4 categories:
1. **Critical Bugs:** 4 questions return completely irrelevant answers
2. **Wrong Values:** 9 questions return incorrect numbers/metrics
3. **Missing Information:** 9 questions couldn't find existing data

This spec provides fixes for each category to achieve 100% accuracy.

---

## Issue 1: "Document Owner" Entity Pollution

### Problem
Questions 22, 45, 50, and 75 return completely irrelevant answers about "Document Owner" instead of actual content.

**Example:**
- Q22: "Who is the CTO?" → Returns "Document Owner" instead of "Dr. Marcus Rodriguez"
- Q75: "Is MFA required?" → Returns answer about CTO roles

### Root Cause
The entity extractor is capturing document metadata fields as entities:
- "Document Owner" appears in document headers/metadata
- It's being extracted as a PERSON or ROLE entity
- Query matching returns it inappropriately

### Fix

**File:** `src/context_foundry/extraction/entity_extractor.py`

Add metadata field blacklist to entity filtering:

```python
# Add near top of file
METADATA_BLACKLIST = {
    # Document metadata fields that should never be entities
    'document owner',
    'document author',
    'author',
    'owner',
    'created by',
    'modified by',
    'last modified by',
    'file owner',
    'prepared by',
    'reviewed by',
    'approved by',
    # Generic role placeholders
    'direct reports',
    'incident commander',
    'tbd',
    'n/a',
    'unknown',
}

def _is_metadata_entity(self, entity_name: str) -> bool:
    """Check if entity name is actually document metadata."""
    name_lower = entity_name.lower().strip()

    # Exact match
    if name_lower in METADATA_BLACKLIST:
        return True

    # Pattern match (e.g., "Document Owner (VP of Engineering)")
    for blacklisted in METADATA_BLACKLIST:
        if name_lower.startswith(blacklisted):
            return True

    return False

# In extract_entities() or _deduplicate_entities(), add filter:
def _deduplicate_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
    """Deduplicate entities by canonical name, keeping highest confidence."""
    entity_map = {}

    for entity in entities:
        # NEW: Skip metadata entities
        if self._is_metadata_entity(entity.canonical_name):
            logger.debug(f"Filtered metadata entity: {entity.canonical_name}")
            continue

        key = (entity.entity_type, entity.canonical_name.lower())

        if key not in entity_map:
            entity_map[key] = entity
        elif entity.confidence > entity_map[key].confidence:
            entity_map[key] = entity

    return sorted(entity_map.values(), key=lambda e: (e.entity_type, e.canonical_name))
```

### Verification
After fix, re-run these queries:
- "Who is the CTO?" → Should return "Dr. Marcus Rodriguez"
- "What is the referral bonus for Director?" → Should return "$5,000"
- "Can remote employees work from public WiFi without VPN?" → Should return "No"
- "Is MFA required?" → Should return "Yes"

---

## Issue 2: Net Income vs EBITDA Confusion

### Problem
Questions 4, 5, 6 ask for "net income" but system returns "EBITDA" (different metrics).

| Question | Expected | Got |
|----------|----------|-----|
| Net income FY 2023 | -$13.2M | -$13.0M (EBITDA) |
| Net income FY 2024 | -$12.4M | -$12.8M (EBITDA) |
| Net income FY 2025 | -$9.5M | -$10.6M (EBITDA) |

### Root Cause
1. The document may use "EBITDA" and "Operating Income" but the system treats them as equivalent to "Net Income"
2. Financial metric extraction doesn't distinguish between:
   - Net Income (bottom line, after all expenses and taxes)
   - EBITDA (Earnings Before Interest, Taxes, Depreciation, Amortization)
   - Operating Income/Loss

### Fix

**File:** `src/context_foundry/extraction/entity_extractor.py`

Add financial metric type distinction:

```python
# Add to entity types or as sub-types
FINANCIAL_METRIC_TYPES = {
    'net_income': ['net income', 'net profit', 'net loss', 'bottom line', 'net earnings'],
    'ebitda': ['ebitda', 'operating income', 'operating loss', 'operating profit'],
    'gross_profit': ['gross profit', 'gross margin', 'gross income'],
    'revenue': ['revenue', 'sales', 'total revenue', 'net revenue'],
}

def _classify_financial_metric(self, text: str) -> str:
    """Classify financial metric type from text context."""
    text_lower = text.lower()

    for metric_type, keywords in FINANCIAL_METRIC_TYPES.items():
        for keyword in keywords:
            if keyword in text_lower:
                return metric_type

    return 'unknown_financial'
```

**File:** `src/context_foundry/agents/reasoning.py`

Add metric disambiguation in query processing:

```python
def _disambiguate_financial_query(self, query: str, retrieved_data: List[Dict]) -> str:
    """Ensure financial queries return the correct metric type."""

    query_lower = query.lower()

    # Detect what metric user is asking for
    if 'net income' in query_lower or 'net loss' in query_lower:
        requested_metric = 'net_income'
    elif 'ebitda' in query_lower or 'operating' in query_lower:
        requested_metric = 'ebitda'
    elif 'gross' in query_lower:
        requested_metric = 'gross_profit'
    else:
        return None  # No disambiguation needed

    # Check if retrieved data has the right metric
    # If not, flag as potential gap
    for chunk in retrieved_data:
        if requested_metric == 'net_income' and 'ebitda' in chunk.get('text', '').lower():
            # We have EBITDA but user asked for net income
            # These are different - flag this
            return f"Note: The documents contain EBITDA figures but not specific net income. EBITDA and net income are different metrics."

    return None
```

### Verification
After fix:
- "What was the net income/loss in FY 2023?" → Should clarify if only EBITDA is available, or return actual net income if present

---

## Issue 3: Wrong Calculations

### Problem
Q11: "What was the year-over-year revenue growth rate from FY 2023 to FY 2024?"
- Expected: 35%
- Got: 53.2%

The system calculated: (64.8 - 42.3) / 42.3 = 53.2%

But the expected answer is 35%, which suggests the document explicitly states this figure.

### Root Cause
The system is calculating the growth rate instead of extracting the pre-calculated value from the document.

### Fix

**File:** `src/context_foundry/agents/reasoning.py`

Prefer extracted values over calculated values:

```python
def _handle_calculation_query(self, query: str, retrieved_chunks: List[Dict]) -> Optional[str]:
    """
    For queries that could be calculated, prefer extracted values.
    Only calculate if no pre-calculated value exists.
    """

    # Check if any chunk contains a pre-calculated answer
    calculation_keywords = ['growth rate', 'percentage', 'increase', 'decrease', 'change']

    query_lower = query.lower()
    is_calculation_query = any(kw in query_lower for kw in calculation_keywords)

    if not is_calculation_query:
        return None

    # Look for explicit percentage values in chunks that match the query timeframe
    for chunk in retrieved_chunks:
        text = chunk.get('text', '')

        # Look for patterns like "35% growth" or "growth of 35%"
        import re
        percentage_pattern = r'(\d+(?:\.\d+)?)\s*%'
        matches = re.findall(percentage_pattern, text)

        if matches and self._chunk_matches_query_timeframe(chunk, query):
            # Prefer the explicitly stated percentage
            logger.info(f"Found pre-calculated value in document: {matches[0]}%")
            return f"The document states: {matches[0]}%"

    # Fall back to calculation only if no explicit value found
    return None
```

### Note
Need to verify what the source document actually says. If it explicitly states "35% growth", the extraction should capture that. If it only has the raw numbers, then the calculation is correct (53.2%).

---

## Issue 4: Year/Temporal Confusion

### Problem
Several questions return data for the wrong fiscal year:

| # | Question | Expected | Got |
|---|----------|----------|-----|
| 27 | Employees end FY 2024 | 537 | "537 at end FY 2025" |
| 76 | GDPR access requests 2024 | 45 | "45 in 2025" |
| 77 | GDPR erasure requests 2024 | 12 | "12 in 2025" |

### Root Cause
1. Temporal context not being extracted with entities
2. Query doesn't filter by year properly
3. System returns most recent data instead of year-specific data

### Fix

**File:** `src/context_foundry/extraction/entity_extractor.py`

Add temporal context to entity extraction:

```python
@dataclass
class ExtractedEntity:
    """Entity with temporal context."""
    entity_type: str
    canonical_name: str
    mentions: List[str]
    confidence: float
    # NEW: Temporal context
    temporal_context: Optional[str] = None  # e.g., "FY 2024", "Q1 2025", "2024"

def _extract_temporal_context(self, text: str, entity_mention: str) -> Optional[str]:
    """Extract temporal context around an entity mention."""
    import re

    # Find position of entity in text
    pos = text.lower().find(entity_mention.lower())
    if pos == -1:
        return None

    # Look for year/quarter patterns within 100 chars of entity
    context_window = text[max(0, pos-100):pos+len(entity_mention)+100]

    # Patterns to match
    patterns = [
        r'FY\s*20\d{2}',           # FY 2024
        r'Q[1-4]\s*20\d{2}',       # Q1 2024
        r'(?:end of|at the end of)\s*(?:FY\s*)?20\d{2}',  # end of 2024
        r'20\d{2}',                # 2024
    ]

    for pattern in patterns:
        match = re.search(pattern, context_window, re.IGNORECASE)
        if match:
            return match.group(0)

    return None
```

**File:** `src/context_foundry/agents/reasoning.py`

Add year filtering to retrieval:

```python
def _extract_query_year(self, query: str) -> Optional[str]:
    """Extract the target year from a query."""
    import re

    patterns = [
        r'FY\s*(20\d{2})',
        r'(?:in|for|during|end of)\s*(?:FY\s*)?(20\d{2})',
        r'(20\d{2})',
    ]

    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1)

    return None

def _filter_by_year(self, entities: List[Entity], target_year: str) -> List[Entity]:
    """Filter entities to those matching the target year."""
    if not target_year:
        return entities

    filtered = []
    for entity in entities:
        # Check if entity's temporal context matches
        if entity.temporal_context and target_year in entity.temporal_context:
            filtered.append(entity)
        elif not entity.temporal_context:
            # Include entities without temporal context (might be relevant)
            filtered.append(entity)

    return filtered if filtered else entities  # Fall back to all if no matches
```

### Verification
After fix:
- "How many employees did NexaTech have at the end of FY 2024?" → Should return 430 (not 537 which is FY 2025)
- "How many GDPR access requests were processed in 2024?" → Should return 2024 data or clarify if only 2025 available

---

## Issue 5: Missing Information Extraction

### Problem
9 questions have answers that exist in documents but weren't extracted:

| # | Question | Expected | Issue |
|---|----------|----------|-------|
| 28 | Customers end FY 2024 | 2,147 | Not extracted |
| 43 | Paid company holidays | 11 | Not extracted |
| 62 | Cloud provider | AWS | Not connected to NexaTech |
| 72 | ISO 27001 certified? | Yes | Not extracted |
| 84 | Fraud detection improvement | 10% | Specific % not extracted |
| 90 | Market share mid-market | 3.2% | Not extracted |
| 95 | Max hotel reimbursement | $200/night | Not extracted |

### Fix: Learning Flow Integration

These are exactly the gaps Learning Flow should catch. After Learning Flow is wired up:

1. Query returns "does not specify"
2. ResponseAnalyzer detects gap
3. Gap added to learning queue
4. Targeted extractor re-processes relevant documents
5. Missing data gets extracted
6. Next query returns correct answer

### Additional Fix: Improve Initial Extraction

**File:** `src/context_foundry/extraction/entity_extractor.py`

Add more entity type patterns:

```python
# Add to extraction prompts or patterns
ADDITIONAL_EXTRACTION_PATTERNS = {
    'customer_count': r'(\d{1,3}(?:,\d{3})*)\s*(?:customers|clients|organizations)',
    'holiday_count': r'(\d+)\s*(?:paid\s*)?(?:company\s*)?holidays',
    'certification': r'(?:ISO\s*27001|SOC\s*2|GDPR|HIPAA)\s*(?:certified|compliant|certification)',
    'percentage_improvement': r'(\d+(?:\.\d+)?)\s*%\s*(?:improvement|increase|reduction|decrease)',
    'market_share': r'(\d+(?:\.\d+)?)\s*%\s*(?:market\s*share)',
    'reimbursement_limit': r'\$(\d+(?:,\d{3})*)\s*(?:per\s*night|maximum|limit)',
}

def _extract_with_patterns(self, text: str) -> List[Dict]:
    """Extract entities using regex patterns for specific types."""
    extracted = []

    for entity_type, pattern in ADDITIONAL_EXTRACTION_PATTERNS.items():
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            extracted.append({
                'type': entity_type,
                'value': match.group(1) if match.groups() else match.group(0),
                'context': text[max(0, match.start()-50):match.end()+50]
            })

    return extracted
```

---

## Issue 6: Query-Answer Mismatch

### Problem
Some queries are answered with wrong metric type:

| # | Question | Expected | Got |
|---|----------|----------|-----|
| 58 | Customer retention rate | 94% | NRR 118% |

### Root Cause
"Customer retention rate" and "Net Revenue Retention (NRR)" are different metrics:
- Customer retention = % of customers who stay
- NRR = revenue retained + expansion from existing customers

### Fix

**File:** `src/context_foundry/agents/reasoning.py`

Add metric type validation:

```python
METRIC_DISTINCTIONS = {
    'customer_retention': {
        'aliases': ['customer retention', 'retention rate', 'customer churn'],
        'not_same_as': ['nrr', 'net revenue retention', 'revenue retention']
    },
    'nrr': {
        'aliases': ['net revenue retention', 'nrr', 'revenue retention'],
        'not_same_as': ['customer retention', 'churn rate']
    },
}

def _validate_metric_match(self, query: str, answer: str) -> bool:
    """Ensure answer contains the right type of metric."""
    query_lower = query.lower()
    answer_lower = answer.lower()

    for metric_type, config in METRIC_DISTINCTIONS.items():
        # Check if query asks for this metric type
        query_asks_for = any(alias in query_lower for alias in config['aliases'])

        if query_asks_for:
            # Check if answer provides a different metric type
            answer_has_wrong = any(wrong in answer_lower for wrong in config['not_same_as'])

            if answer_has_wrong:
                logger.warning(f"Metric mismatch: Query asks for {metric_type} but answer contains different metric")
                return False

    return True
```

---

## Implementation Priority

### Phase 1: Critical Bugs (Week 1)
1. Fix "Document Owner" entity pollution
2. Add metadata blacklist
3. Test Q22, Q45, Q50, Q75

### Phase 2: Data Quality (Week 2)
4. Add financial metric distinction
5. Add temporal context extraction
6. Add year filtering to queries
7. Test Q4-6, Q27, Q76-77

### Phase 3: Learning Flow (Week 3)
8. Wire up Learning Flow (already spec'd)
9. Test gap detection triggers
10. Verify re-extraction works
11. Test Q28, Q43, Q62, Q72, Q84, Q90, Q95

### Phase 4: Edge Cases (Week 4)
12. Add calculation vs extraction preference
13. Add metric type validation
14. Full regression test all 105 questions

---

## Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| Total Correct | 83/105 | 105/105 |
| Accuracy | 79% | 100% |
| Critical Bugs | 4 | 0 |
| Wrong Values | 9 | 0 |
| Missing Info | 9 | 0 |

---

## Testing Plan

After each phase, run full QA test:

```bash
# Run QA test
python run_qa_test.py --vault nexatech --questions qa_test_content.json

# Compare results
python compare_qa_results.py --baseline qa_results_baseline.json --new qa_results_new.json
```

Track progress in spreadsheet showing each question's status across runs.
