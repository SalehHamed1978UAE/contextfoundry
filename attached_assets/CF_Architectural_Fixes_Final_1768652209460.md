# Context Foundry - Architectural Fixes Spec (Final)

**Date:** 2026-01-17  
**Purpose:** Solve root causes, not symptoms. No more blacklists.

---

## Executive Summary

Current accuracy: **84%** (adjusted)  
Target accuracy: **95%+**  

We've been patching individual failures with blacklists and caveats. This spec replaces patches with proper architecture that **understands** queries and **enforces** constraints.

---

## The 4 Components to Build

| # | Component | Purpose | Replaces |
|---|-----------|---------|----------|
| 1 | Query Intent Classifier | Understand query type before retrieval | Pattern-matching to wrong entities |
| 2 | Entity Type Router | Only retrieve valid entity types for intent | Blacklists filtering after retrieval |
| 3 | Symbolic Distinction Rules | Enforce net_income ≠ ebitda, retention ≠ nrr | Caveat warnings |
| 4 | Schema-Constrained Extraction | Reject invalid entities at ingestion | Document Owner blacklist |

---

## Component 1: Query Intent Classifier

### Purpose
Understand what TYPE of question is being asked before attempting retrieval.

### File
`src/context_foundry/query/intent_classifier.py`

### Intent Categories

```python
class QueryIntent(Enum):
    PERSON = "person"           # Who is, who reports to, roles
    METRIC = "metric"           # Numbers, financials, KPIs, percentages
    POLICY = "policy"           # Rules, requirements, policies, compliance
    TEMPORAL = "temporal"       # When, dates, timelines, deadlines
    RELATIONSHIP = "relationship"  # Reports to, works at, manages
    DEFINITION = "definition"   # What is, describe, explain
    LIST = "list"               # List all, how many, enumerate
    UNKNOWN = "unknown"
```

### Pattern Rules (Examples)

```python
INTENT_PATTERNS = {
    QueryIntent.PERSON: [
        r'^who\s+is\s+(?:the\s+)?',
        r'^who\s+(?:are|were)\s+',
        r'(?:ceo|cto|cfo|cro|coo|cio|vp|director|manager)',
        r'reports?\s+to',
    ],
    QueryIntent.METRIC: [
        r'(?:revenue|income|profit|loss|margin|growth|percentage|rate|ratio|budget|cost|salary)',
        r'\d+(?:\.\d+)?\s*%',
        r'(?:how\s+many|how\s+much|what\s+percentage)',
        r'(?:cagr|yoy|ltv|cac|nrr|arr|mrr)',
    ],
    QueryIntent.POLICY: [
        r'^(?:is|are|can|do|does)\s+.*(?:required|allowed|permitted|mandatory)',
        r'(?:policy|policies|requirement|compliance|procedure|rule)',
        r'(?:mfa|authentication|security|access|permission)',
        r'(?:gdpr|hipaa|sox|pci|iso\s*27001|soc\s*2)',
    ],
    QueryIntent.TEMPORAL: [
        r'^when\s+',
        r'(?:fy\s*\d{4}|q[1-4]\s*\d{4}|\d{4})',
        r'(?:date|deadline|timeline|schedule)',
    ],
}
```

### Output

```python
@dataclass
class ClassifiedQuery:
    original_query: str
    primary_intent: QueryIntent
    confidence: float
    extracted_constraints: dict  # {"fiscal_year": "FY2024", "org": "NexaTech"}
```

### Test Cases

| Query | Expected Intent |
|-------|----------------|
| "Who is the CTO?" | PERSON |
| "Is MFA required?" | POLICY |
| "What was revenue in FY 2024?" | METRIC |
| "When was the company founded?" | TEMPORAL |
| "How many employees?" | LIST + METRIC |

---

## Component 2: Entity Type Router

### Purpose
Map query intent to valid entity types. Only retrieve entities that could possibly answer the question.

### File
`src/context_foundry/query/entity_router.py`

### Intent → Entity Type Mapping

```python
INTENT_TO_ENTITY_TYPES = {
    QueryIntent.PERSON: {
        "include": ["PERSON", "ROLE", "POSITION", "EMPLOYEE"],
        "exclude": ["POLICY", "METRIC", "FINANCIAL_DATA"]
    },
    QueryIntent.METRIC: {
        "include": ["FINANCIAL_METRIC", "KPI", "REVENUE", "NET_INCOME", "EBITDA", "MARGIN", "GROWTH_RATE"],
        "exclude": ["PERSON", "POLICY"]
    },
    QueryIntent.POLICY: {
        "include": ["POLICY", "REQUIREMENT", "RULE", "SECURITY_CONTROL", "COMPLIANCE"],
        "exclude": ["PERSON", "FINANCIAL_METRIC"]
    },
    QueryIntent.TEMPORAL: {
        "include": ["EVENT", "MILESTONE", "DATE", "DEADLINE"],
        "exclude": []
    },
}
```

### Database-Level Filtering

```python
def _search_entities(self, query: str, intent: QueryIntent) -> List[Entity]:
    """Apply type filters at database level, not after retrieval."""
    
    type_filter = INTENT_TO_ENTITY_TYPES.get(intent, {})
    
    where_clauses = ["tenant_id = :tenant_id"]
    
    if type_filter.get("include"):
        where_clauses.append("entity_type = ANY(:valid_types)")
        params['valid_types'] = type_filter["include"]
    
    if type_filter.get("exclude"):
        where_clauses.append("entity_type != ALL(:excluded_types)")
        params['excluded_types'] = type_filter["exclude"]
    
    # Execute constrained query
    ...
```

### Why This Fixes Q75

```
Query: "Is MFA required?"
Intent: POLICY
Valid types: [POLICY, REQUIREMENT, SECURITY_CONTROL]
Excluded types: [PERSON, FINANCIAL_METRIC]

Result: CTO entities NEVER retrieved. Only policy entities searched.
```

---

## Component 3: Symbolic Distinction Rules

### Purpose
Define concepts that are related but NOT interchangeable. Enforce these distinctions at answer validation.

### File
`src/context_foundry/symbolic/distinction_rules.py`

### Distinction Categories

```python
FINANCIAL_DISTINCTIONS = [
    DistinctionRule(
        concept_a="net_income",
        concept_b="ebitda",
        relationship="related_but_distinct",
        explanation="Net income includes interest, taxes, depreciation, amortization. EBITDA excludes them."
    ),
    DistinctionRule(
        concept_a="revenue",
        concept_b="profit",
        relationship="related_but_distinct",
        explanation="Revenue is total income. Profit is revenue minus expenses."
    ),
    DistinctionRule(
        concept_a="gross_margin",
        concept_b="net_margin",
        relationship="related_but_distinct",
        explanation="Gross margin excludes operating expenses. Net margin includes all expenses."
    ),
]

RETENTION_DISTINCTIONS = [
    DistinctionRule(
        concept_a="customer_retention",
        concept_b="net_revenue_retention",
        relationship="related_but_distinct",
        explanation="Customer retention counts customers. NRR measures revenue from existing customers including expansion."
    ),
]

TEMPORAL_DISTINCTIONS = [
    DistinctionRule(
        concept_a="fy2024",
        concept_b="fy2025",
        relationship="distinct_time_periods",
        explanation="Different fiscal years. Data from one cannot answer questions about the other."
    ),
]
```

### Validation Function

```python
def validate_answer(self, query_concept: str, answer_concept: str) -> Tuple[bool, Optional[str]]:
    """
    Check if answer provides what query asked for.
    
    Returns (is_valid, warning_message)
    """
    is_distinct, explanation = self.are_distinct(query_concept, answer_concept)
    
    if is_distinct:
        return False, f"Query asked for '{query_concept}' but answer provides '{answer_concept}'. {explanation}"
    
    return True, None
```

### Behavior When Distinction Violated

```
Query: "What was net income in FY 2024?"
Retrieved: EBITDA entity with value -$12.8M

Distinction check: net_income ≠ ebitda → VIOLATION

Response: "Net income data not found for FY 2024. 
           Note: EBITDA was -$12.8M, but this is a different metric 
           (EBITDA excludes interest, taxes, depreciation, amortization)."
```

---

## Component 4: Schema-Constrained Extraction

### Purpose
Prevent garbage entities from entering the knowledge graph in the first place.

### File
`src/context_foundry/extraction/schema_validator.py`

### Valid Entity Types (Ontology)

```python
VALID_ENTITY_TYPES = {
    # People & Organization
    "PERSON", "ROLE", "POSITION", "TEAM", "DEPARTMENT", "ORGANIZATION",
    
    # Financial (typed separately)
    "REVENUE", "NET_INCOME", "EBITDA", "GROSS_PROFIT", "OPERATING_INCOME",
    "GROWTH_RATE", "MARGIN", "RATIO",
    
    # Metrics
    "KPI", "TARGET", "QUOTA",
    
    # Policy & Compliance
    "POLICY", "REQUIREMENT", "RULE", "SECURITY_CONTROL", "COMPLIANCE_STANDARD",
    
    # Products & Projects
    "PRODUCT", "PROJECT", "FEATURE", "SERVICE",
    
    # Events & Time
    "EVENT", "MILESTONE", "DEADLINE",
    
    # Documents
    "DOCUMENT", "CONTRACT", "AGREEMENT",
}

# Explicitly INVALID - reject these
INVALID_PATTERNS = [
    r"document\s*owner",
    r"file\s*author",
    r"created\s*by",
    r"modified\s*by",
    r"last\s*edited",
]
```

### Validation at Extraction

```python
def validate_entity(self, entity: ExtractedEntity) -> Tuple[bool, Optional[str]]:
    """
    Validate entity before adding to knowledge graph.
    
    Returns (is_valid, rejection_reason)
    """
    # Check entity type is valid
    if entity.type not in VALID_ENTITY_TYPES:
        return False, f"Invalid entity type: {entity.type}"
    
    # Check name isn't metadata
    for pattern in INVALID_PATTERNS:
        if re.search(pattern, entity.name, re.IGNORECASE):
            return False, f"Entity name matches metadata pattern: {entity.name}"
    
    return True, None
```

### Extraction Prompt Update

Add to extraction prompt:

```
CRITICAL RULES:
1. ONLY extract entities that appear in document CONTENT
2. IGNORE document metadata (author, owner, created by, modified by)
3. Entity types MUST be one of: [PERSON, ROLE, REVENUE, NET_INCOME, EBITDA, POLICY, ...]
4. If a name appears ONLY in metadata headers, it is NOT an entity
```

---

## Component 5: Typed Financial Extraction

### Purpose
Extract financial metrics as distinct typed entities, not generic "METRIC" blobs.

### Financial Entity Types

```python
FINANCIAL_ENTITY_TYPES = {
    "REVENUE": ["revenue", "total revenue", "sales", "income"],
    "NET_INCOME": ["net income", "net profit", "net loss", "bottom line"],
    "EBITDA": ["ebitda", "operating income before"],
    "GROSS_PROFIT": ["gross profit", "gross margin amount"],
    "OPERATING_INCOME": ["operating income", "operating profit", "operating loss"],
}
```

### Extraction Output

```python
# Instead of:
{"type": "METRIC", "name": "FY2024 Loss", "value": "-$12.8M"}

# Extract as:
{"type": "EBITDA", "name": "EBITDA FY2024", "value": "-12800000", "fiscal_year": "FY2024", "is_stated": True}
{"type": "NET_INCOME", "name": "Net Income FY2024", "value": "-12400000", "fiscal_year": "FY2024", "is_stated": True}
```

### Query Routing for Financial

```
Query: "What was net income in FY 2024?"
Intent: METRIC
Constraints: {"fiscal_year": "FY2024", "metric_type": "NET_INCOME"}

Search: entity_type = 'NET_INCOME' AND fiscal_year = 'FY2024'
```

---

## Integration: Updated Query Pipeline

```
User Query
    │
    ▼
┌─────────────────────────────────────────┐
│      QUERY INTENT CLASSIFIER            │
│  "Is MFA required?" → POLICY            │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│      ENTITY TYPE ROUTER                 │
│  POLICY → search [POLICY, REQUIREMENT]  │
│           exclude [PERSON, METRIC]      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│      CONSTRAINED RETRIEVAL              │
│  SQL: WHERE entity_type IN (...)        │
│        AND entity_type NOT IN (...)     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│      SYMBOLIC DISTINCTION CHECK         │
│  Validate answer matches query concept  │
└─────────────────┬───────────────────────┘
                  │
                  ▼
            Response
```

---

## Migration Path

### Phase 1: Deploy Classification (Logging Only)
- Add QueryIntentClassifier
- Log intent for every query
- **No filtering yet** — just observe
- Duration: 1-2 days
- Success: Classification accuracy >90% on test queries

### Phase 2: Enable Soft Filtering
- Add EntityTypeRouter
- Log what WOULD be filtered
- Compare filtered vs unfiltered results
- Duration: 2-3 days
- Success: No valid entities incorrectly filtered

### Phase 3: Enable Hard Filtering
- Apply type filters at database query level
- Enable SymbolicDistinctionRules validation
- Remove blacklist code
- Duration: 2-3 days
- Success: Q75 returns policy answer, not CTO

### Phase 4: Schema Validation at Extraction
- Add SchemaValidator to extraction pipeline
- Reject invalid entities before they enter KG
- Clean up existing garbage entities
- Re-extract affected documents
- Duration: 2-3 days
- Success: No new "Document Owner" entities created

---

## Success Criteria

| Test | Before | After |
|------|--------|-------|
| Q75: "Is MFA required?" | ❌ Returns CTO list | ✅ Returns Yes/No policy answer |
| Q4-Q6: Net income questions | ❌ Returns EBITDA | ✅ Returns net income OR says "not found, EBITDA is X" |
| Q58: Customer retention | ❌ Returns NRR (118%) | ✅ Returns retention (94%) OR distinguishes them |
| Q76-Q77: FY2024 GDPR data | ❌ Returns FY2025 | ✅ Returns FY2024 OR says "2024 data not found" |
| No "Document Owner" anywhere | ❌ | ✅ |
| Overall accuracy | 84% | 95%+ |

---

## What Gets Removed After This

Once these components are working, DELETE:

1. `METADATA_BLACKLIST` in entity_extractor.py
2. `ROLE_RESOLVER_BLACKLIST` in role_resolver.py
3. Query-time blacklist filtering in retrieval_router.py
4. QA validation caveat patterns (replaced by distinction rules)

The system will be **architecturally correct**, not patched.

---

## Effort Estimate

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Query Intent Classifier | 2 days | None |
| Entity Type Router | 2 days | Intent Classifier |
| Symbolic Distinction Rules | 1-2 days | None |
| Schema-Constrained Extraction | 2 days | None |
| Typed Financial Extraction | 2 days | Schema Validator |
| Integration + Testing | 2-3 days | All above |

**Total: ~10-12 days**

---

## Summary

| Problem | Patch (Delete This) | Architectural Fix (Build This) |
|---------|---------------------|-------------------------------|
| Document Owner garbage | Blacklist | Schema-constrained extraction |
| Q75 returns CTO for MFA | More blacklists | Query intent classification + entity routing |
| Net Income vs EBITDA | Caveat warning | Symbolic distinction rules + typed extraction |
| Wrong year data | None | Temporal constraints in retrieval |
| Format mismatches | Fuzzy string matching | Not needed — retrieval returns correct type |

**The system will understand queries, not just pattern-match them.**
