# Context Foundry: Replit Implementation Instructions (Merged)

**Date:** February 1, 2026
**Current Baseline:** 84% (vault `1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91`)
**Target:** 90%+ accuracy
**Principle:** NO HARDCODING - all fixes must be systematic

---

## PART 1: THE HARDCODING GUARD

### The 5-Question Go/No-Go Checklist (MANDATORY)

**Before implementing ANY fix, you MUST answer these 5 questions:**

| # | Question | Required Answer |
|---|----------|-----------------|
| 1 | Would this fix work if we changed the company name from "Nexus" to "Acme Corp"? | **YES** |
| 2 | Would this fix work if we changed the expected value (e.g., "400 Wh/kg" to "500 Wh/kg")? | **YES** |
| 3 | Does this fix apply to ALL similar queries, not just the failing one? | **YES** |
| 4 | Am I fixing a CATEGORY of queries or just ONE specific question? | **CATEGORY** |
| 5 | Does this change involve adding a specific entity name, value, or keyword from the test? | **NO** |

**If ANY answer is wrong → STOP. Rethink the approach.**

---

### Examples: Hardcoding vs Systematic

#### ❌ HARDCODING (Never Do This)

```python
# ❌ Adds specific company name
if "toyota" in query.lower():
    return fetch_toyota_documents()

# ❌ Returns specific test value
if "energy density" in query:
    return "400 Wh/kg"

# ❌ Special case for one question
if question_id == 25:
    return battery_specs_document()

# ❌ Pattern with specific entity
PATTERNS = [r'\btoyota\b', r'\bnel hydrogen\b', r'\bshell\b']

# ❌ Hardcoded relationship values
if customer_name == "Boeing":
    return {"value": "$730M"}
```

#### ✅ SYSTEMATIC (Do This)

```python
# ✅ Detects query TYPE, not specific entities
def is_technical_spec_query(query: str) -> bool:
    """Detect queries asking for technical specifications."""
    spec_indicators = [
        'energy density', 'temperature range', 'capacity',
        'material', 'specification', 'rating', 'efficiency'
    ]
    return any(indicator in query.lower() for indicator in spec_indicators)

# ✅ Routes based on query pattern, not specific values
def is_supplier_query(query: str) -> bool:
    """Detect queries asking about suppliers."""
    patterns = [
        r'who\s+supplie[sd]',
        r'supplier\s+(?:of|for)',
        r'provided?\s+by',
        r'source[sd]?\s+from'
    ]
    return any(re.search(p, query, re.IGNORECASE) for p in patterns)

# ✅ Extracts ANY monetary value, not specific ones
def extract_relationship_value(text: str) -> Optional[float]:
    """Extract monetary value from relationship context."""
    patterns = [
        r'\$\s*([\d.,]+)\s*(million|billion|M|B)?',
        r'([\d.,]+)\s*(million|billion)\s*(?:dollars?|\$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return normalize_currency(match.group(0))
    return None

# ✅ Validates ANY answer against evidence
def validate_inference(question, answer, evidence):
    """LLM-based validation that works for any query."""
    prompt = f"Does this evidence support '{answer}' as the answer to '{question}'?"
    return llm_validate(prompt, evidence)
```

---

## PART 2: TEST PROTOCOL

### Before and After Every Change

Run the full test suite:

```bash
python -m src.test_runner.runner \
  --vault-id "1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91" \
  --questions "src/test_questions/nexus_100q.json" \
  --force
```

- Log the resulting JSON (accuracy, per-question status)
- **No change may be merged unless:**
  - The post-change run shows intended improvements
  - No other answers regressed
  - The 5-question checklist was passed

### Single-Query Testing

For targeted validation during development:

```bash
python scripts/run_single_query.py --vault 1f3320cd --qno <QUESTION_NUMBER>
```

### Smoke Test (10 queries - run before full suite)

```python
SMOKE_TEST_QUERIES = [
    "Who is the CEO?",                              # Role
    "When was the CFO appointed?",                  # Role + temporal
    "Who supplies components to the facility?",    # Supplier
    "What is the energy capacity?",                # Technical spec
    "What is the operating temperature?",          # Technical spec
    "Who is the largest customer?",                # Customer ranking
    "What is the total customer value?",           # Customer aggregation
    "Who does the company partner with?",          # Partnership
    "What percentage ownership in the JV?",        # Partnership detail
    "When was the company founded?",               # Company overview
]
```

---

## PART 3: IMPLEMENTATION TASKS

### Task 0: Verify Inference Validation Layer is Running

**Why:** The LLM-based inference validation was built but isn't appearing in test results.

**File:** `src/context_foundry/validation/inference_validator.py`

**Steps:**

1. Confirm the file exists and is imported in `core.py`
2. Add logging:
   ```python
   logger.info(f"[INFERENCE_VALIDATOR] Running validation for: {question[:50]}")
   logger.info(f"[INFERENCE_VALIDATOR] Result: {validation.result.value}")
   ```
3. Run single test query and check logs

**Validation:**
```python
from context_foundry.core import ContextFoundry
cf = ContextFoundry(tenant_id='1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91')
result = cf.query('Who does Nexus partner with for solid-state batteries?')
print('inference_validated:', result.get('inference_validated'))
print('inference_correction_reason:', result.get('inference_correction_reason'))
```

**Expected:** Logs show validation running; result contains `inference_validated` field.

**Go/No-Go Check:**
- This is infrastructure, not a fix. No checklist needed.

---

### Task 1: Scoped Role & Date Resolution

**Outcome:** Role queries resolve to the correct person AND appointment date using structured data.

**Fixes:** Q29, Q45, Q61, Q91

**Steps:**

1. Finish Stage –1 scoped role resolution in `role_resolver.py`:
   - Detect `<role> of <entity>` patterns
   - Resolve against relationships linked to the scoped entity (`CEO_OF`, `HOLDS_POSITION`, `REPLACED`)
   - On success, return immediately (don't fall back to anchor org)

2. Add date extraction for appointments:
   ```python
   ROLE_DATE_PATTERNS = [
       r'appointed\s+(?:in\s+)?(\d{4})',
       r'since\s+(\w+\s+\d{4})',
       r'effective\s+(\w+\s+\d{1,2},?\s+\d{4})',
       r'(?:joined|started)\s+(?:in\s+)?(\w+\s+\d{4})',
   ]
   ```

3. Add succession query detection:
   ```python
   def is_succession_query(query: str) -> bool:
       patterns = [
           r'who\s+replaced',
           r'who\s+succeeded',
           r'predecessor\s+of',
           r'successor\s+to',
       ]
       return any(re.search(p, query, re.IGNORECASE) for p in patterns)
   ```

**Go/No-Go Check:**
| Question | Answer |
|----------|--------|
| Works for "When was John Smith appointed CFO at Acme"? | YES ✓ |
| Works for "Who replaced Jane Doe as CTO"? | YES ✓ |
| Adds specific names like "Thomas Anderson" or "Robert Kim"? | NO ✓ |
| Fixes category (all role/date queries) not just Q45? | YES ✓ |

**Validation:**
```bash
python scripts/run_single_query.py --vault 1f3320cd --qno 29
python scripts/run_single_query.py --vault 1f3320cd --qno 45
python scripts/run_single_query.py --vault 1f3320cd --qno 61
python scripts/run_single_query.py --vault 1f3320cd --qno 91
```

**SQL Check:**
```sql
SELECT COUNT(*) FROM relationships
WHERE relationship_type = 'HOLDS_ROLE'
AND properties->>'appointed_date' IS NOT NULL;
-- Expected: 10+
```

**Expected:** Each query returns correct person and date with `basis=verified_extraction`.

---

### Task 2: Technical Specification Extraction

**Outcome:** Technical specs (energy density, temperature, capacity, materials) are extracted into the KG from document tables/lists.

**Fixes:** Q24, Q25, Q67, Q93

**Steps:**

1. Add spec extraction patterns to `post_processor.py`:
   ```python
   TECHNICAL_SPEC_PATTERNS = [
       # "Energy Density: 400 Wh/kg" style
       (r'([\w\s]+):\s*([\d.,]+\s*(?:Wh/kg|°C|kg/hr|GWh|MW|kV|%))', 'SPECIFICATION'),
       # "Target: 400 Wh/kg" style
       (r'(?:target|goal|specification|rating):\s*([\d.,]+\s*\w+)', 'SPECIFICATION'),
       # Temperature ranges "-30°C to 60°C"
       (r'(-?\d+)\s*°?C?\s*to\s*(-?\d+)\s*°?C', 'TEMPERATURE_RANGE'),
   ]
   ```

2. Re-run extraction for battery specs and GreenHydrogen documents:
   - Capture `energy_density_target`, `operating_temp_range`, `electrolyte_material`
   - For GreenHydrogen: capture both `capacity_phase1` AND `capacity_full`

3. Update retrieval router to prefer Phase 1 values when query mentions "Phase 1," "initial," or "kg/hour"

**Go/No-Go Check:**
| Question | Answer |
|----------|--------|
| Would capture "Efficiency: 95%" in a different document? | YES ✓ |
| Would capture "Voltage: 400 kV" for a different product? | YES ✓ |
| Adds "400 Wh/kg" as a hardcoded value? | NO ✓ |
| Fixes category (all spec queries) not just Q25? | YES ✓ |

**Validation:**
```bash
python scripts/run_single_query.py --vault 1f3320cd --qno 24
python scripts/run_single_query.py --vault 1f3320cd --qno 25
python scripts/run_single_query.py --vault 1f3320cd --qno 67
python scripts/run_single_query.py --vault 1f3320cd --qno 93
```

**SQL Check:**
```sql
SELECT canonical_name, properties
FROM entities
WHERE canonical_name ILIKE 'GreenHydrogen%';

SELECT canonical_name, properties
FROM entities
WHERE canonical_name ILIKE 'Solid-State Battery%';
-- Expected: properties include energy_density, temp_range, electrolyte
```

**Expected:** 50+ technical specifications captured across all documents.

---

### Task 3: Supplier Relationship Extraction

**Outcome:** Supplier relationships (`SUPPLIES_TO`, `SUPPLIED_BY`) are extracted and queryable.

**Fixes:** Q17, Q18, Q46

**Steps:**

1. Add supplier patterns to `relation_extractor.py`:
   ```python
   SUPPLIER_PATTERNS = [
       # "X supplies Y to Z"
       (r'(\b[A-Z][\w\s]+?)\s+(?:supplies?|provides?|delivers?)\s+(.+?)\s+(?:to|for)', 'SUPPLIES_TO'),
       # "supplied by X"
       (r'(.+?)\s+(?:supplied|provided|sourced)\s+by\s+(\b[A-Z][\w\s]+)', 'SUPPLIED_BY'),
       # "X as supplier"
       (r'(\b[A-Z][\w\s]+?)\s+(?:as|is)\s+(?:the\s+)?(?:primary\s+)?supplier', 'IS_SUPPLIER'),
       # "offtake agreement with X"
       (r'offtake\s+agreement\s+with\s+(\b[A-Z][\w\s]+)', 'OFFTAKE_AGREEMENT'),
   ]
   ```

2. Re-run extraction on supplier-related documents

**Go/No-Go Check:**
| Question | Answer |
|----------|--------|
| Would capture "Acme Corp supplies widgets to BigCo"? | YES ✓ |
| Would work on a different corpus about manufacturing? | YES ✓ |
| Adds "Nel Hydrogen" or "Shell" as hardcoded values? | NO ✓ |
| Fixes category (all supplier queries) not just Q17? | YES ✓ |

**Validation:**
```bash
python scripts/run_single_query.py --vault 1f3320cd --qno 17
python scripts/run_single_query.py --vault 1f3320cd --qno 18
python scripts/run_single_query.py --vault 1f3320cd --qno 46
```

**SQL Check:**
```sql
SELECT COUNT(*) FROM relationships
WHERE relationship_type IN ('SUPPLIES_TO', 'SUPPLIED_BY', 'IS_SUPPLIER', 'OFFTAKE_AGREEMENT');
-- Expected: 20+
```

**Expected:** 20+ supplier relationships extracted.

---

### Task 4: Customer Relationship Values

**Outcome:** `CUSTOMER_OF` relationships contain dollar values for ranking queries.

**Fixes:** Q34, Q79, Q83, Q100

**Steps:**

1. Add value extraction to relationship processing:
   ```python
   VALUE_PATTERNS = [
       r'\$\s*([\d.,]+)\s*(million|billion|M|B|K)?',
       r'([\d.,]+)\s*(million|billion)\s*(?:dollars?|\$)',
       r'total[:\s]+\$?([\d.,]+)\s*(million|billion|M|B)?',
   ]

   def extract_relationship_value(text: str) -> Optional[float]:
       """Extract monetary value from relationship context."""
       for pattern in VALUE_PATTERNS:
           match = re.search(pattern, text, re.IGNORECASE)
           if match:
               return normalize_currency(match.group(0))
       return None
   ```

2. Re-extract customer profile documents with explicit prompt for "Total relationship value"

3. Store value on `CUSTOMER_OF` edge as `relationship_value`

4. Enhance ranking intent detection:
   ```python
   def is_ranking_query(query: str) -> bool:
       patterns = [
           r'largest|biggest|top|primary|main',
           r'most\s+(?:valuable|important|significant)',
           r'rank|ranking|order',
       ]
       return any(re.search(p, query, re.IGNORECASE) for p in patterns)
   ```

**Go/No-Go Check:**
| Question | Answer |
|----------|--------|
| Would capture "$500M" for a different customer? | YES ✓ |
| Would capture "€50 million" with minor extension? | YES ✓ |
| Hardcodes "Boeing = $730M"? | NO ✓ |
| Fixes category (all ranking queries) not just Q34? | YES ✓ |

**Validation:**
```bash
python scripts/run_single_query.py --vault 1f3320cd --qno 34
python scripts/run_single_query.py --vault 1f3320cd --qno 79
python scripts/run_single_query.py --vault 1f3320cd --qno 83
python scripts/run_single_query.py --vault 1f3320cd --qno 100
```

**SQL Check:**
```sql
SELECT e1.canonical_name, r.properties->>'relationship_value' as value
FROM relationships r
JOIN entities e1 ON r.source_id = e1.id
WHERE r.relationship_type = 'CUSTOMER_OF'
AND r.properties->>'relationship_value' IS NOT NULL;
-- Expected: 10+ customers with values
```

**Expected:** 10+ customer relationships have dollar values.

---

## PART 4: DELIVERABLES

### For Each Task, Report:

```
TASK: [Task number and name]
GO/NO-GO CHECKLIST:
  1. Works with different company name? [YES/NO]
  2. Works with different values? [YES/NO]
  3. Fixes all similar queries? [YES/NO]
  4. Fixes category not single question? [YES/NO]
  5. No specific names/values added? [YES/NO]

CODE CHANGES:
  - [File]: [Brief description of change]

SQL EVIDENCE:
  [Query and result showing data was added]

SINGLE-QUERY TESTS:
  Q[X]: [PASS/FAIL] - [Brief output]
  Q[Y]: [PASS/FAIL] - [Brief output]

FULL SUITE RESULT:
  Before: [X]% ([Y]/100)
  After: [X]% ([Y]/100)
  Changed: Q[list of questions that changed status]
```

---

## PART 5: SUCCESS CRITERIA

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| Overall Accuracy | 84% | 90%+ | Full test suite |
| Inference Validator Running | NO | YES | Check logs + result fields |
| Technical Specs in KG | ~0 | 50+ | `SELECT COUNT(*) FROM entities WHERE entity_type='SPECIFICATION'` |
| Supplier Relationships | ~0 | 20+ | `SELECT COUNT(*) FROM relationships WHERE relationship_type LIKE '%SUPPL%'` |
| Customer Values | ~0 | 10+ | `SELECT COUNT(*) FROM relationships WHERE relationship_type='CUSTOMER_OF' AND properties->>'relationship_value' IS NOT NULL` |
| Roles with Dates | ~0 | 10+ | `SELECT COUNT(*) FROM relationships WHERE relationship_type='HOLDS_ROLE' AND properties->>'appointed_date' IS NOT NULL` |

---

## PART 6: WHAT NOT TO DO

1. **DO NOT** add specific entity names to patterns (no "Toyota", "Nel Hydrogen", "Shell", "Boeing")
2. **DO NOT** add specific values to return (no "400 Wh/kg", "$12.4 billion", "$730M")
3. **DO NOT** create special cases for specific question IDs
4. **DO NOT** modify test questions or expected answers
5. **DO NOT** skip the 5-question Go/No-Go checklist
6. **DO NOT** merge without before/after test results
7. **DO NOT** run full test suite without passing smoke test first

---

## PART 7: PRIORITY ORDER

Execute in this order. Complete and verify each task before starting the next.

| Priority | Task | Expected Impact |
|----------|------|-----------------|
| 0 | Verify inference validation running | Infrastructure |
| 1 | Scoped role & date resolution | +2-4% (Q29, Q45, Q61, Q91) |
| 2 | Technical specification extraction | +2-4% (Q24, Q25, Q67, Q93) |
| 3 | Supplier relationship extraction | +2-3% (Q17, Q18, Q46) |
| 4 | Customer value extraction | +2-4% (Q34, Q79, Q83, Q100) |

**Total Expected Improvement:** 84% → 90-92%

---

## CONTACT

If unclear whether a fix is hardcoding:
1. Run the 5-question checklist
2. If still unsure, **ASK before implementing**

The checklist is the law. No exceptions.
