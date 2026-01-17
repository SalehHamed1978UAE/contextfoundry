# RLM Integration Spec - Achieving 100% QA Accuracy

**Date:** 2026-01-17
**Current Accuracy:** 77.1% (81/105)
**Target Accuracy:** 100%

---

## Executive Summary

Context Foundry has a **complete RLM (Recursive Language Model) infrastructure** that is not being used. The current query pipeline uses chunk-stuffing (RAG), which causes:

- Document Owner pollution (Q22, Q45, Q50, Q75)
- Net Income vs EBITDA confusion (Q4-6)
- Year confusion (Q27, Q76-77)
- Missing information (Q28, Q43, Q62, Q72, Q84, Q90, Q95)

**Solution:** Wire up the existing RLM system and add Query Intent Classification to the REPL tools.

---

## Current Architecture (Chunk-Stuffing)

```
Query → Vector Search → Stuff Chunks into Context → LLM → Answer
                ↓
        "Context Rot" - LLM confused by irrelevant chunks
```

**Problems:**
1. Retrieves "Document Owner" metadata as if it were an entity
2. Retrieves EBITDA when asked for Net Income (different metrics)
3. Retrieves FY 2025 data when asked for FY 2024
4. Cannot follow multi-hop relationships

---

## Target Architecture (RLM REPL)

```
Query → Intent Classifier → Route to Tier
                              ↓
              ┌───────────────┴───────────────┐
              ↓                               ↓
         Tier 1 (Simple)              Tier 2 (Complex)
              ↓                               ↓
         Direct Lookup               RLM REPL Loop
              ↓                               ↓
           Answer               LLM + Memory APIs → Answer
```

**The RLM REPL Loop:**
```python
while not finalized and iteration < max_iterations:
    code = llm.generate("Write Python to explore the knowledge graph")
    result = sandbox.execute(code)
    # Available APIs:
    #   semantic.find_similar("payment service")
    #   symbolic.get_relationships(entity_id)
    #   episodic.search("net income FY 2024")
    if llm.has_answer:
        finalize()
```

---

## Existing RLM Infrastructure (Already Built)

### 1. RLMExecutor (`src/context_foundry/rlm/executor.py`)
- Lines 102-515
- Manages conversation loop with root LLM
- Tracks progress, enforces timeouts, manages budget
- Supports Anthropic and OpenAI

### 2. QueryComplexityRouter (`src/context_foundry/rlm/router.py`)
- Lines 92-310
- Analyzes query complexity signals
- Routes Tier 1 (simple) vs Tier 2 (RLM)
- Has FORCE_RLM_PATTERNS for specific query types

### 3. REPLSandbox (`src/context_foundry/rlm/sandbox.py`)
- Lines 108-392
- Secure code execution environment
- Safe builtins only (no import, eval, exec)
- Captures print output, tracks entity/relationship discovery

### 4. Memory APIs

| API | File | Key Methods |
|-----|------|-------------|
| SemanticMemoryAPI | `memory_apis/semantic.py` | find_entities, find_similar, get_entity, find_by_property |
| EpisodicMemoryAPI | `memory_apis/episodic.py` | search, get_chunk, get_document_chunks, get_provenance |
| SymbolicMemoryAPI | `memory_apis/symbolic.py` | get_relationships, find_path, get_related_entities, traverse |

---

## Integration Plan

### Phase 1: Wire Up RLM to Query Pipeline

**File:** `src/context_foundry/agents/tool_agent.py` (or equivalent)

```python
from src.context_foundry.rlm.router import QueryComplexityRouter, QueryTier
from src.context_foundry.rlm.executor import execute_rlm_query

class QueryProcessor:
    def __init__(self, tenant_id: str, db_session: Session):
        self.tenant_id = tenant_id
        self.db_session = db_session
        self.router = QueryComplexityRouter(complexity_threshold=0.10)

    def process_query(self, query: str) -> dict:
        tier, signals = self.router.route(query)

        if tier == QueryTier.TIER2_RLM:
            # Use RLM for complex queries
            result = execute_rlm_query(
                tenant_id=self.tenant_id,
                query=query,
                db_session=self.db_session
            )
            return {
                "answer": result.answer_text,
                "confidence": result.confidence,
                "evidence": result.evidence_chain,
                "mode": "RLM"
            }
        else:
            # Use existing retrieval for simple queries
            return self._simple_retrieval(query)
```

### Phase 2: Add Query Intent Classification to REPL

**Purpose:** Solve "Document Owner" pollution by classifying query intent BEFORE retrieval.

**File:** `src/context_foundry/rlm/intent_classifier.py` (NEW)

```python
"""
Query Intent Classifier for RLM.

Classifies queries into intent categories to guide entity type filtering.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import re


class QueryIntent(Enum):
    PERSON_LOOKUP = "person_lookup"           # "Who is the CTO?"
    METRIC_LOOKUP = "metric_lookup"           # "What is the net income?"
    POLICY_LOOKUP = "policy_lookup"           # "Is MFA required?"
    ENTITY_RELATIONSHIP = "entity_relationship"  # "Who reports to the CEO?"
    TEMPORAL_METRIC = "temporal_metric"       # "Revenue in FY 2024"
    AGGREGATION = "aggregation"               # "How many employees?"
    UNKNOWN = "unknown"


@dataclass
class IntentClassification:
    primary_intent: QueryIntent
    valid_entity_types: List[str]
    temporal_constraint: Optional[str]
    metric_type: Optional[str]
    confidence: float


INTENT_PATTERNS = {
    QueryIntent.PERSON_LOOKUP: {
        "patterns": [
            r"^who is",
            r"^who are",
            r"^who was",
            r"who\s+(?:is|are|was)\s+(?:the\s+)?(?:\w+\s+)*(?:cto|ceo|cfo|coo|vp|director|manager|owner|lead)",
        ],
        "valid_entity_types": ["PERSON", "ROLE", "EXECUTIVE"],
        "invalid_entity_types": ["DOCUMENT", "POLICY", "METRIC"],
    },
    QueryIntent.METRIC_LOOKUP: {
        "patterns": [
            r"what is the (?:net income|revenue|ebitda|profit|loss|margin)",
            r"how much (?:is|was|were)",
            r"what (?:is|was|were) the .* (?:rate|percentage|amount|total|count)",
        ],
        "valid_entity_types": ["METRIC", "FINANCIAL_METRIC", "KPI"],
        "invalid_entity_types": ["PERSON", "DOCUMENT", "ROLE"],
    },
    QueryIntent.POLICY_LOOKUP: {
        "patterns": [
            r"is (?:mfa|vpn|encryption) required",
            r"(?:can|may|should) (?:employees|users|staff)",
            r"what is the policy",
            r"is .* (?:allowed|permitted|required|mandatory)",
        ],
        "valid_entity_types": ["POLICY", "RULE", "REQUIREMENT", "COMPLIANCE"],
        "invalid_entity_types": ["PERSON", "METRIC", "ROLE"],
    },
    QueryIntent.TEMPORAL_METRIC: {
        "patterns": [
            r"(?:in|for|during|at the end of)\s+(?:fy\s*)?20\d{2}",
            r"(?:fy|fiscal year)\s*20\d{2}",
            r"q[1-4]\s*20\d{2}",
        ],
        "valid_entity_types": ["METRIC", "FINANCIAL_METRIC", "KPI", "COUNT"],
        "requires_temporal_filter": True,
    },
}


class IntentClassifier:
    """Classifies query intent to guide entity type filtering."""

    def classify(self, query: str) -> IntentClassification:
        query_lower = query.lower()

        # Check each intent pattern
        for intent, config in INTENT_PATTERNS.items():
            for pattern in config["patterns"]:
                if re.search(pattern, query_lower):
                    return IntentClassification(
                        primary_intent=intent,
                        valid_entity_types=config.get("valid_entity_types", []),
                        temporal_constraint=self._extract_temporal(query_lower),
                        metric_type=self._extract_metric_type(query_lower),
                        confidence=0.9,
                    )

        return IntentClassification(
            primary_intent=QueryIntent.UNKNOWN,
            valid_entity_types=[],
            temporal_constraint=None,
            metric_type=None,
            confidence=0.5,
        )

    def _extract_temporal(self, query: str) -> Optional[str]:
        """Extract temporal constraint from query."""
        patterns = [
            r"fy\s*(20\d{2})",
            r"fiscal year\s*(20\d{2})",
            r"(?:in|for|during)\s*(20\d{2})",
            r"q([1-4])\s*(20\d{2})",
            r"(?:end of|at the end of)\s*(?:fy\s*)?(20\d{2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return match.group(0)

        return None

    def _extract_metric_type(self, query: str) -> Optional[str]:
        """Extract specific metric type from query."""
        METRIC_KEYWORDS = {
            "net_income": ["net income", "net profit", "net loss", "net earnings"],
            "ebitda": ["ebitda", "operating income", "operating profit"],
            "revenue": ["revenue", "sales", "total revenue"],
            "retention": ["customer retention", "retention rate", "churn"],
            "nrr": ["net revenue retention", "nrr", "revenue retention"],
        }

        for metric_type, keywords in METRIC_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    return metric_type

        return None
```

### Phase 3: Integrate Intent Classifier into REPL System Prompt

**File:** `src/context_foundry/rlm/executor.py`

Update the SYSTEM_PROMPT to include intent-aware guidance:

```python
SYSTEM_PROMPT = """You are an expert knowledge graph analyst with intent-aware search.

BEFORE SEARCHING: Classify the query intent:
- PERSON_LOOKUP: Search for PERSON, ROLE, EXECUTIVE entities only
- METRIC_LOOKUP: Search for METRIC, FINANCIAL_METRIC, KPI entities only
- POLICY_LOOKUP: Search for POLICY, RULE, REQUIREMENT entities only
- TEMPORAL_METRIC: Filter results by fiscal year/quarter mentioned in query

CRITICAL DISTINCTIONS:
- Net Income ≠ EBITDA (different financial metrics)
- Customer Retention ≠ Net Revenue Retention (different rates)
- FY 2024 ≠ FY 2025 (different time periods)

ANTI-PATTERNS to avoid:
- "Document Owner" is NOT a person - it's metadata
- "Author" is NOT a person - it's metadata
- "TBD", "N/A" are NOT valid answers

## Available Memory APIs:
- semantic: Entity memory (find_entities, find_similar, get_entity, find_by_property)
- episodic: Document chunk memory (search, get_chunk, get_document_chunks, get_provenance)
- symbolic: Relationship memory (get_relationships, find_path, get_related_entities, traverse)

## Example - Intent-Aware Search:
```python
# Query: "Who is the CTO?"
# Intent: PERSON_LOOKUP → Only search for PERSON/ROLE entities
entities = semantic.find_similar("CTO", entity_type="PERSON", k=5)
# Filter out metadata entities
entities = [e for e in entities if e.entity.name.lower() not in ["document owner", "author", "tbd"]]
```

## Example - Temporal-Aware Search:
```python
# Query: "How many employees at end of FY 2024?"
# Intent: TEMPORAL_METRIC → Must filter by temporal context
chunks = episodic.search("employees FY 2024", k=10)
# Look for chunks mentioning specifically FY 2024, not FY 2025
for chunk in chunks:
    if "FY 2024" in chunk.chunk.content or "2024" in chunk.chunk.content:
        # This is the right temporal context
        pass
```
"""
```

### Phase 4: Add Symbolic Distinction Rules

**File:** `src/context_foundry/rlm/distinction_rules.py` (NEW)

```python
"""
Symbolic Distinction Rules - Prevent metric confusion.

net_income ≠ ebitda
customer_retention ≠ nrr
fy_2024 ≠ fy_2025
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class DistinctionRule:
    concept_a: str
    concept_b: str
    relationship: str  # "not_equal", "subset_of", "parent_of"
    explanation: str


DISTINCTION_RULES: List[DistinctionRule] = [
    DistinctionRule(
        concept_a="net_income",
        concept_b="ebitda",
        relationship="not_equal",
        explanation="Net Income is after all expenses including interest, taxes, depreciation, amortization. EBITDA excludes these."
    ),
    DistinctionRule(
        concept_a="net_income",
        concept_b="operating_income",
        relationship="not_equal",
        explanation="Net Income includes non-operating items. Operating Income is before interest and taxes."
    ),
    DistinctionRule(
        concept_a="customer_retention",
        concept_b="nrr",
        relationship="not_equal",
        explanation="Customer Retention is % of customers retained. NRR includes expansion revenue from existing customers."
    ),
    DistinctionRule(
        concept_a="revenue",
        concept_b="net_income",
        relationship="not_equal",
        explanation="Revenue is top line. Net Income is bottom line after all expenses."
    ),
]


class DistinctionValidator:
    """Validates that answers don't confuse distinct concepts."""

    def __init__(self):
        self.rules = {
            (r.concept_a, r.concept_b): r for r in DISTINCTION_RULES
        }
        # Also add reverse mappings
        for r in DISTINCTION_RULES:
            self.rules[(r.concept_b, r.concept_a)] = r

    def check_confusion(self, query_concept: str, answer_concept: str) -> Tuple[bool, str]:
        """
        Check if answer confuses the query concept with a different one.

        Returns:
            (is_confused, warning_message)
        """
        key = (query_concept.lower(), answer_concept.lower())
        if key in self.rules:
            rule = self.rules[key]
            return True, f"Warning: Query asks for {rule.concept_a} but answer contains {rule.concept_b}. {rule.explanation}"

        return False, ""

    def get_disambiguation_prompt(self, query: str) -> str:
        """Generate disambiguation guidance for the LLM."""
        prompts = []

        if "net income" in query.lower():
            prompts.append("IMPORTANT: User asked for Net Income. Do NOT return EBITDA or Operating Income.")
        if "ebitda" in query.lower():
            prompts.append("IMPORTANT: User asked for EBITDA. Do NOT return Net Income.")
        if "customer retention" in query.lower():
            prompts.append("IMPORTANT: User asked for Customer Retention Rate. Do NOT return Net Revenue Retention (NRR).")
        if "nrr" in query.lower() or "net revenue retention" in query.lower():
            prompts.append("IMPORTANT: User asked for NRR. Do NOT return Customer Retention Rate.")

        return "\n".join(prompts)
```

---

## Testing Plan

### Phase 1 Verification (RLM Wiring)

Run these queries through RLM and verify routing:

```python
# Should route to RLM (Tier 2 - complex)
"Compare the dependencies of Payment Service and Order Service"
"What is the root cause path from Network Outage to checkout failures?"

# Should route to simple retrieval (Tier 1)
"Who is the CTO?"
"What is the net income for FY 2024?"
```

### Phase 2 Verification (Intent Classification)

| Query | Expected Intent | Valid Entity Types |
|-------|-----------------|-------------------|
| "Who is the CTO?" | PERSON_LOOKUP | PERSON, ROLE |
| "What is the net income?" | METRIC_LOOKUP | METRIC, FINANCIAL_METRIC |
| "Is MFA required?" | POLICY_LOOKUP | POLICY, RULE |
| "Revenue in FY 2024" | TEMPORAL_METRIC | METRIC + temporal filter |

### Phase 3 Verification (Distinction Rules)

| Query | Answer Contains | Should Flag |
|-------|-----------------|-------------|
| "Net income FY 2023" | "EBITDA: -$13.0M" | YES - wrong metric |
| "Customer retention rate" | "NRR: 118%" | YES - wrong metric |
| "Employees end FY 2024" | "537 at end FY 2025" | YES - wrong year |

### Full QA Test

After each phase, run:
```bash
python run_qa_test.py --vault nexatech --questions qa_test_content.json
```

Expected improvement:
- Phase 1: 81/105 → 85/105 (multi-hop queries work)
- Phase 2: 85/105 → 95/105 (Document Owner pollution fixed)
- Phase 3: 95/105 → 100/105 (metric confusion fixed)
- Phase 4: 100/105 → 105/105 (temporal confusion fixed)

---

## Files to Modify

| Phase | File | Change |
|-------|------|--------|
| 1 | `src/context_foundry/agents/tool_agent.py` | Add RLM routing |
| 1 | `src/context_foundry/rlm/router.py` | Lower threshold to 0.10 |
| 2 | `src/context_foundry/rlm/intent_classifier.py` | NEW - Intent classification |
| 3 | `src/context_foundry/rlm/executor.py` | Update SYSTEM_PROMPT |
| 3 | `src/context_foundry/rlm/distinction_rules.py` | NEW - Distinction validation |
| 4 | `src/context_foundry/rlm/memory_apis/semantic.py` | Add metadata blacklist |

---

## Success Criteria

| Metric | Before | After Phase 1 | After Phase 2 | After Phase 3 | Target |
|--------|--------|---------------|---------------|---------------|--------|
| Q22, Q45, Q50, Q75 (Document Owner) | FAIL | FAIL | PASS | PASS | PASS |
| Q4-6 (Net Income vs EBITDA) | FAIL | FAIL | FAIL | PASS | PASS |
| Q27, Q76-77 (Year confusion) | FAIL | FAIL | FAIL | PASS | PASS |
| Q58 (Retention vs NRR) | FAIL | FAIL | FAIL | PASS | PASS |
| Q11 (Calculation preference) | FAIL | PASS | PASS | PASS | PASS |
| Overall Accuracy | 77.1% | 81% | 90% | 95% | 100% |

---

## Why This Works

1. **RLM already exists** - We're not building new infrastructure, just wiring it up
2. **Intent Classification is simple** - Pattern matching + entity type filtering
3. **Distinction Rules are explicit** - No ML needed, just symbolic rules
4. **REPL is self-correcting** - If first search fails, LLM can try again with different parameters
5. **Learning Flow integrates naturally** - Gaps detected by ResponseAnalyzer feed back into extraction

---

## Implementation Order

1. **Week 1:** Wire up RLM to query pipeline (Phase 1)
   - Modify tool_agent.py to use router
   - Test with multi-hop queries

2. **Week 2:** Add Intent Classification (Phase 2)
   - Create intent_classifier.py
   - Update SYSTEM_PROMPT
   - Test Q22, Q45, Q50, Q75

3. **Week 3:** Add Distinction Rules (Phase 3)
   - Create distinction_rules.py
   - Add to reasoning validation
   - Test Q4-6, Q58

4. **Week 4:** Fix Temporal Filtering (Phase 4)
   - Add temporal extraction to intent classifier
   - Update episodic search to filter by year
   - Test Q27, Q76-77
   - Full regression test

---

## Conclusion

The RLM infrastructure is **complete and ready to use**. The 22 failing questions are caused by:

1. Using chunk-stuffing instead of RLM (causes context rot)
2. No intent classification (retrieves wrong entity types)
3. No distinction rules (confuses similar metrics)
4. No temporal filtering (returns wrong fiscal year)

All four issues can be solved by wiring up the existing RLM and adding three new files:
- `intent_classifier.py` (~150 lines)
- `distinction_rules.py` (~100 lines)
- Updates to `executor.py` SYSTEM_PROMPT (~50 lines)

Total new code: ~300 lines to achieve 100% accuracy.
