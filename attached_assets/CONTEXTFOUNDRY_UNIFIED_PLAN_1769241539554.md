# ContextFoundry Unified Improvement Plan

## Target
**Manus Orion accuracy ≥ 90%** using `/Users/saleh/Downloads/orion_verified_106q.json`

## Current State
- Accuracy: 57.5% (69/120 on different set)
- Gap: ~35 questions need to pass on 106q set
- KG: 3301 entities, 2168 relationships (loosely typed, missing key relationships)

---

## CRITICAL GUARDRAILS

### Absolute Rules - Violating These Fails the Task

1. **NO HARDCODED ANSWERS** - No answer strings, entity names, or business facts in code
2. **NO HARDCODED MAPPINGS** - No dictionaries mapping abbreviations, synonyms, or values
3. **ALL FACTS FROM CORPUS** - Every piece of data originates from documents or KG extraction
4. **CONFIGURATION-DRIVEN** - Use authority_map, extraction rules, prompts - not literal strings
5. **LLM FOR SEMANTICS** - Use LLM for any semantic understanding (equivalence, classification, normalization)

### How to Check Yourself

Before committing code, ask:
- "Am I writing a dictionary/map?" → Use LLM instead
- "Am I adding an if/else for a specific entity name?" → Use LLM classification instead
- "Am I embedding a fact from the corpus?" → Extract it from documents instead
- "Am I adding a regex pattern list?" → Use LLM understanding instead

---

## Task 1: Business Unit Knowledge Graph Coverage

### Goal
Every business unit has explicit KG properties (focus areas, core industries, leadership) and edges to its owned programs/projects.

### What to Extract
- **FOCUSES_ON** relationships: BU → focus area
- **OWNS_PROGRAM** relationships: BU → project/program
- **OPERATES_IN** relationships: BU → industry/sector
- **LEADS** relationships: Person → BU

### Source Documents
- `strategy/strategic_plan_2025_2027.md`
- `strategy/*.md`
- Any document mentioning business unit structure

### Implementation

**File**: `src/context_foundry/extraction/bu_extractor.py`

```python
class BusinessUnitExtractor:
    """Extract business unit relationships using LLM - NO HARDCODING."""

    def extract(self, document_text: str, document_name: str) -> List[Relationship]:
        prompt = f"""Extract business unit information from this document.

For each business unit mentioned, identify:
1. What it FOCUSES_ON (areas of specialization, products, services)
2. What programs/projects it OWNS (subsidiary projects, initiatives)
3. What industries it OPERATES_IN (sectors, markets)
4. Who LEADS it (executives, directors)

Document: {document_name}
Text:
{document_text}

Return as JSON array:
[
    {{"source": "BU name", "relationship": "FOCUSES_ON", "target": "focus area", "confidence": 0.9}},
    {{"source": "BU name", "relationship": "OWNS_PROGRAM", "target": "project name", "confidence": 0.85}},
    ...
]

Only include relationships explicitly stated or strongly implied in the text.
Return empty array if no business unit information found."""

        response = self.llm.chat(prompt)
        return self._parse_relationships(response)
```

### Success Criteria
- Q18: "What are the four main business units?" → Returns Orion Aerospace, Orion Energy Solutions, Orion Logistics, Orion SmartCity
- Q19-24: "What does [BU] focus on?" → Returns specific focus areas from KG

### Guardrails
- Use ingestion rules/authority config
- Do not embed BU names or focus areas in code
- All data sourced from strategy documents

---

## Task 2: Project Metadata & Relationships

### Goal
Each major project has KG entries for: budget, capacity, location, owning business unit, supplier chain links.

### Projects to Cover (extracted from corpus, not hardcoded)
The extraction should find these projects in documents:
- Falcon UAV Program
- Project Helios
- UrbanMesh
- AutoNav Logistics System
- Project Borealis
- GreenStream Hydrogen Initiative
- NexGen Composite Materials
- SkyLink Satellite Network

### What to Extract
- **budget**: Numeric value with currency
- **capacity**: Production/operational capacity
- **location**: Geographic location
- **timeline**: Start date, end date, milestones
- **OWNED_BY**: Project → Business Unit
- **SUPPLIED_BY**: Project → Supplier

### Implementation

**File**: `src/context_foundry/extraction/project_extractor.py`

```python
class ProjectExtractor:
    """Extract project metadata using LLM."""

    def extract(self, document_text: str) -> List[Entity]:
        prompt = f"""Extract project information from this document.

For each project/program/initiative mentioned, extract:
1. Name
2. Budget (if mentioned) - preserve exact figure and currency
3. Capacity/target (if mentioned) - preserve exact figure and units
4. Location (if mentioned)
5. Timeline/deadline (if mentioned)
6. Owning organization/business unit (if mentioned)
7. Suppliers involved (if mentioned)

Text:
{document_text}

Return as JSON array:
[
    {{
        "name": "Project Name",
        "type": "PROJECT",
        "properties": {{
            "budget": "$50 million",
            "capacity": "500 units/year",
            "location": "Austin, TX",
            "deadline": "2027"
        }},
        "relationships": [
            {{"type": "OWNED_BY", "target": "Business Unit Name"}},
            {{"type": "SUPPLIED_BY", "target": "Supplier Name"}}
        ],
        "confidence": 0.85
    }}
]

Only include information explicitly stated. Do not infer or guess values."""

        response = self.llm.chat(prompt)
        return self._parse_entities(response)
```

### Success Criteria
- Q26-36: "Which BU owns [project]?" → Returns correct owning BU
- Q27-32: "What is [project] budget/timeline?" → Returns correct values

### Guardrails
- All data sourced from engineering/strategy docs
- Code only defines extraction/parsing rules
- No project names or budgets in code

---

## Task 3: Financial Targets & Budgets

### Goal
Financial metrics stored as normalized numeric properties with source authority ranking.

### Metrics to Extract
- EBITDA margin (percentage)
- Revenue targets (currency)
- Capex allocation (currency or percentage)
- R&D percentage
- ROI range
- Payback period
- Working capital allocation

### Implementation

**File**: `src/context_foundry/extraction/financial_extractor.py`

```python
class FinancialExtractor:
    """Extract financial metrics with normalization."""

    def extract(self, document_text: str, document_name: str) -> List[Entity]:
        prompt = f"""Extract financial metrics from this document.

For each financial metric, extract:
1. Metric name (e.g., "EBITDA margin", "revenue target", "R&D budget")
2. Value - preserve exact figure
3. Type: "percentage", "currency", "ratio", "period"
4. Time period if mentioned (e.g., "2025", "Q4 2024")

Document: {document_name}
Text:
{document_text}

Return as JSON array:
[
    {{
        "metric": "EBITDA margin",
        "value": "15%",
        "value_type": "percentage",
        "numeric_value": 0.15,
        "period": "2025",
        "confidence": 0.9
    }},
    {{
        "metric": "R&D budget",
        "value": "$120 million",
        "value_type": "currency",
        "numeric_value": 120000000,
        "currency": "USD",
        "period": "2025",
        "confidence": 0.85
    }}
]

Preserve exact values as stated. Also provide normalized numeric_value."""

        response = self.llm.chat(prompt)
        return self._parse_metrics(response)
```

**File**: `src/context_foundry/ontology/authority_map.py`

```python
# Authority ranking for conflict resolution - configuration, not hardcoded facts
AUTHORITY_RANKING = {
    "financial_statements": 1,      # Highest authority
    "annual_report": 1,
    "strategic_plan": 2,
    "finance_doc": 2,
    "policy_doc": 3,
    "meeting_notes": 4,
    "general": 5                    # Lowest authority
}

def get_document_authority(document_name: str) -> int:
    """Get authority level for a document based on its type."""
    doc_lower = document_name.lower()
    for pattern, authority in AUTHORITY_RANKING.items():
        if pattern in doc_lower:
            return authority
    return 5  # Default to lowest
```

**File**: `src/context_foundry/ontology/conflict_resolver.py`

```python
class ConflictResolver:
    """Resolve conflicting values using authority ranking + LLM reasoning."""

    def resolve(self, metric_name: str, values: List[dict]) -> dict:
        """
        Resolve multiple values for same metric.

        Args:
            metric_name: e.g., "EBITDA margin"
            values: [{"value": "15%", "source": "doc.md", "authority": 2}, ...]
        """
        # Sort by authority (lower = more authoritative)
        sorted_values = sorted(values, key=lambda x: x.get('authority', 5))

        # If clear winner by authority, use it
        if len(sorted_values) >= 2:
            if sorted_values[0]['authority'] < sorted_values[1]['authority']:
                return sorted_values[0]

        # Otherwise, use LLM to reason about which is correct
        values_text = "\n".join([
            f"- {v['value']} (from {v['source']}, authority={v['authority']})"
            for v in sorted_values
        ])

        prompt = f"""Multiple values found for "{metric_name}":

{values_text}

Which value is most likely correct? Consider:
1. More authoritative sources (lower authority number = more authoritative)
2. More recent or specific documents
3. Whether values are actually different or just formatted differently

Return JSON:
{{
    "canonical_value": "the resolved value",
    "reasoning": "why this value was chosen",
    "source": "which document"
}}"""

        response = self.llm.chat(prompt)
        return json.loads(response)
```

### Success Criteria
- Q62-72: Financial metric questions return correct values
- Q71: "Working capital budget allocation" → "10%" (not "$12M reduction")

### Guardrails
- No constants in code
- Numbers always read from documents
- Use authority_map to prefer finance/strategy docs

---

## Task 4: Customer & Supplier Relationships

### Goal
Customers and suppliers modeled with CUSTOMER_OF, SUPPLIER_OF relationships.

### What to Extract
- **CUSTOMER_OF** relationships: Customer → Manus Orion (or specific BU)
- **SUPPLIER_OF** relationships: Supplier → Project/BU
- **RISK_NOTE** properties: Risk level, concerns

### Source Documents
- `customers/*.md`
- `compliance/*.md`
- Any document mentioning customer/supplier relationships

### Implementation

**File**: `src/context_foundry/extraction/stakeholder_extractor.py`

```python
class StakeholderExtractor:
    """Extract customer and supplier relationships."""

    def extract(self, document_text: str) -> List[Relationship]:
        prompt = f"""Extract customer and supplier relationships from this document.

Identify:
1. CUSTOMERS: Organizations that buy from or contract with the company
2. SUPPLIERS: Organizations that provide goods/services to the company
3. PARTNERS: Organizations in partnership or joint ventures

For each, extract:
- Name
- Type (CUSTOMER, SUPPLIER, PARTNER)
- What they buy/supply (if mentioned)
- Any risk notes or concerns (if mentioned)

Text:
{document_text}

Return as JSON:
{{
    "customers": [
        {{"name": "Org Name", "relationship": "CUSTOMER_OF", "product": "what they buy", "confidence": 0.8}}
    ],
    "suppliers": [
        {{"name": "Org Name", "relationship": "SUPPLIER_OF", "product": "what they supply", "risk": "any risk notes", "confidence": 0.8}}
    ],
    "partners": [
        {{"name": "Org Name", "relationship": "PARTNER_OF", "context": "partnership context", "confidence": 0.8}}
    ]
}}

Only include explicitly mentioned relationships."""

        response = self.llm.chat(prompt)
        return self._parse_stakeholders(response)
```

### Success Criteria
- Q86-95: "Who is [customer]?" → Returns correct customer info with relationship to Manus Orion

### Guardrails
- Relationship edges must originate from document content
- No manual mapping embedded in Python
- Customer/supplier names not hardcoded

---

## Task 5: Query Routing Optimization

### Goal
Intent classifier tuned for person, ownership, budget, policy queries with proper fallback ordering.

### Current State
- QueryInterpreter implemented but disabled due to timeouts
- Fallback to document search working

### Fix: Performance Optimization

**File**: `src/context_foundry/agents/query_interpreter.py`

```python
class QueryInterpreter:
    def __init__(self):
        self.model = "gpt-4o-mini"  # Fast model, not gpt-4o
        self.timeout = 2.0          # 2 second max
        self._cache = {}            # Cache repeated patterns

    def interpret(self, question: str) -> QueryIntent:
        # Check cache
        cache_key = hashlib.md5(question.lower().strip().encode()).hexdigest()
        if cache_key in self._cache:
            logger.info(f"[INTERPRETER] Cache hit")
            return self._cache[cache_key]

        try:
            with timeout(self.timeout):
                intent = self._interpret_llm(question)
                self._cache[cache_key] = intent
                return intent
        except TimeoutError:
            logger.warning(f"[INTERPRETER] Timeout, using default")
            return QueryIntent(query_type="general")

    def _interpret_llm(self, question: str) -> QueryIntent:
        prompt = f"""Classify this question and extract key information.

Question: {question}

Determine:
1. query_type: "person_role" | "ownership" | "budget" | "metric" | "policy" | "relationship" | "general"
2. entity: The main entity being asked about (person name, project name, etc.)
3. target_type: What type of answer is expected (role, budget, percentage, list, etc.)

Return JSON:
{{
    "query_type": "...",
    "entity": "...",
    "target_type": "..."
}}"""

        response = self.llm.chat(prompt, model=self.model, max_tokens=100)
        return QueryIntent(**json.loads(response))
```

### Re-enable in ToolAgent

**File**: `src/context_foundry/agents/tool_agent.py`

```python
def query(self, question: str, ...):
    # Try intent-based routing (with timeout protection)
    intent = None
    if self._interpreter_enabled:
        try:
            intent = self.query_interpreter.interpret(question)
            logger.info(f"[AGENT] Intent: type={intent.query_type}, entity={intent.entity}")

            # Route based on intent
            if intent.query_type == "person_role":
                result = self._kg_person_role_lookup(intent.entity)
                if result:
                    return self._synthesize_with_intent(question, result, intent)

            elif intent.query_type == "ownership":
                result = self._kg_ownership_lookup(intent.entity)
                if result:
                    return self._synthesize_with_intent(question, result, intent)

            elif intent.query_type == "budget":
                result = self._kg_metric_lookup(intent.entity, "budget")
                if result:
                    return self._synthesize_with_intent(question, result, intent)

        except Exception as e:
            logger.warning(f"[AGENT] Intent routing failed: {e}, falling back")

    # Fallback to document search
    pipeline_result = self.query_pipeline.process(question, vault_context=vault_context)
    return self._synthesize_direct_answer(question, pipeline_result, intent)
```

### Success Criteria
- No timeout errors (was 29 errors before)
- Intent logged for every query
- KG-first path used when appropriate

### Guardrails
- Adjust classifier via prompt/config only
- Do not special-case entity names in code
- Log all routing decisions for observability

---

## Task 6: Answer Formatting & Verification

### Goal
LLM prompts enforce output type; evaluator catches semantic matches.

### Implementation: Intent-Aware Synthesis

**File**: `src/context_foundry/agents/tool_agent.py`

```python
def _synthesize_with_intent(self, question: str, data: dict, intent: QueryIntent) -> str:
    """Synthesize answer with intent-aware formatting."""

    # Build format instruction based on intent (NOT hardcoded answers)
    format_instruction = ""
    if intent.target_type == "role":
        format_instruction = "Return the job title/role. Be concise - just the title."
    elif intent.target_type == "budget":
        format_instruction = "Return the budget amount with currency. Be concise - just the figure."
    elif intent.target_type == "percentage":
        format_instruction = "Return the percentage value. Be concise - just the percentage."
    elif intent.target_type == "list":
        format_instruction = "Return a comma-separated list of items."

    prompt = f"""Question: {question}

Data from knowledge graph:
{json.dumps(data, indent=2)}

{format_instruction}

Provide a direct answer based on the data. If the data doesn't contain the answer, say so."""

    return self.llm.chat(prompt)
```

### Implementation: Evaluator Semantic Equivalence

**File**: `src/test_runner/evaluator.py`

```python
def evaluate_detailed(self, expected: str, actual: str, query: str = None) -> EvaluationResult:
    # ... existing pattern-based checks ...

    # ALWAYS try semantic equivalence before returning no_match
    logger.info(f"[EVAL] Trying semantic equivalence for: {query[:50]}...")

    if self._check_semantic_equivalence(expected, actual, query):
        logger.info(f"[EVAL] Semantic match succeeded!")
        return EvaluationResult(True, "semantic_match",
                                normalized_expected=norm_expected,
                                normalized_actual=norm_actual)

    logger.info(f"[EVAL] No match found")
    return EvaluationResult(False, "no_match",
                            failure_reason="No significant overlap",
                            normalized_expected=norm_expected,
                            normalized_actual=norm_actual)

def _check_semantic_equivalence(self, expected: str, actual: str, question: str) -> bool:
    """LLM-based semantic equivalence check."""

    prompt = f"""Question: {question}
Expected answer: {expected}
Actual answer: {actual}

Are these answers semantically equivalent? Consider:
1. Abbreviations: CEO = Chief Executive Officer, CFO = Chief Financial Officer, etc.
2. Rephrasing: "wind farm" ≈ "offshore wind farm initiative"
3. Containment: Actual contains the expected information
4. Numeric equivalence: "$45M" = "$45 million" = "45000000"
5. Percentage equivalence: "15%" = "0.15" = "15 percent"
6. Partial match: If actual answers the question correctly with equivalent info

Answer YES if the actual answer provides equivalent information to the expected answer.
Answer NO if the actual answer is wrong, incomplete, or answers a different question.

Reply with ONLY yes or no."""

    try:
        response = self.llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=5
        )
        result = response.choices[0].message.content.strip().upper()
        logger.info(f"[SEMANTIC] Result: {result}")
        return result == "YES"
    except Exception as e:
        logger.error(f"[SEMANTIC] Error: {e}")
        return False
```

### Success Criteria
- Q9: "CEO" matches "Chief Executive Officer"
- Q13: Responsibilities question matches detailed answer
- Q71: "10%" recognized even if answer has extra context

### Guardrails
- No answer strings embedded
- Rely on structured data + prompt instructions
- QAVerifier confirms match before returning

---

## Task 7: Corpus Validation Script

### Goal
Validate that every expected answer exists in the corpus before running tests.

### Implementation

**File**: `src/test_runner/validate_questions.py`

```python
#!/usr/bin/env python3
"""Validate that all expected answers exist in the corpus."""

import json
import sys
from pathlib import Path
from typing import List, Tuple

def validate_questions(questions_file: str, corpus_dir: str) -> List[Tuple[int, str, str]]:
    """
    Validate each question's expected answer exists in corpus.

    Returns list of (question_id, question, expected_answer) for missing answers.
    """
    with open(questions_file) as f:
        questions = json.load(f)

    # Load all corpus text
    corpus_text = ""
    corpus_path = Path(corpus_dir)
    for file_path in corpus_path.rglob("*"):
        if file_path.is_file() and file_path.suffix in ['.md', '.txt', '.json']:
            try:
                corpus_text += file_path.read_text() + "\n"
            except:
                pass

    corpus_lower = corpus_text.lower()

    missing = []
    for q in questions:
        qid = q['id']
        question = q['question']
        expected = q['expected_answer']

        # Check if expected answer (or key parts) exist in corpus
        if not _answer_exists_in_corpus(expected, corpus_lower):
            missing.append((qid, question, expected))

    return missing

def _answer_exists_in_corpus(expected: str, corpus_lower: str) -> bool:
    """Check if expected answer exists in corpus."""
    expected_lower = expected.lower()

    # Direct match
    if expected_lower in corpus_lower:
        return True

    # Check key components (for multi-part answers)
    components = [c.strip() for c in expected_lower.replace(',', '|').replace(' and ', '|').split('|')]
    components = [c for c in components if len(c) > 3]

    if components:
        found = sum(1 for c in components if c in corpus_lower)
        if found >= len(components) * 0.7:  # 70% of components found
            return True

    return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python validate_questions.py <questions.json> <corpus_dir>")
        sys.exit(1)

    questions_file = sys.argv[1]
    corpus_dir = sys.argv[2]

    missing = validate_questions(questions_file, corpus_dir)

    if missing:
        print(f"WARNING: {len(missing)} questions have answers not found in corpus:\n")
        for qid, question, expected in missing:
            print(f"  Q{qid}: {question}")
            print(f"       Expected: {expected}\n")
        sys.exit(1)
    else:
        print("All expected answers found in corpus.")
        sys.exit(0)
```

### Usage
```bash
# Run before tests
python -m src.test_runner.validate_questions \
    /Users/saleh/Downloads/orion_verified_106q.json \
    /path/to/manus_orion_corpus

# Integrate into CI/nightly
```

### Success Criteria
- Script runs before every test suite
- Fails fast if expected answers missing
- Outputs list of problematic question IDs

### Guardrails
- Script only reports - no code editing to "fix" results
- Missing answers require either corpus update or question removal

---

## Task 8: Observability & Trace

### Goal
Trace logs show routing decisions, retrieved data, and evaluation reasons for every question.

### Implementation

**File**: `src/context_foundry/utils/trace_logger.py`

```python
class QueryTraceLogger:
    """Structured trace logging for query execution."""

    def __init__(self, query_id: str, question: str):
        self.query_id = query_id
        self.question = question
        self.trace = {
            "query_id": query_id,
            "question": question,
            "timestamp": datetime.now().isoformat(),
            "intent": None,
            "route": None,
            "kg_results": None,
            "doc_results": None,
            "synthesis": None,
            "answer": None,
            "evaluation": None
        }

    def log_intent(self, intent: QueryIntent):
        self.trace["intent"] = {
            "query_type": intent.query_type,
            "entity": intent.entity,
            "target_type": intent.target_type
        }
        logger.info(f"[TRACE:{self.query_id}] Intent: {intent.query_type} for {intent.entity}")

    def log_route(self, route: str, reason: str):
        self.trace["route"] = {"path": route, "reason": reason}
        logger.info(f"[TRACE:{self.query_id}] Route: {route} ({reason})")

    def log_kg_results(self, entities: List, relationships: List):
        self.trace["kg_results"] = {
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "entities": [e.get('name') for e in entities[:5]],
            "relationships": [f"{r.get('source')}->{r.get('type')}->{r.get('target')}" for r in relationships[:5]]
        }
        logger.info(f"[TRACE:{self.query_id}] KG: {len(entities)} entities, {len(relationships)} relationships")

    def log_doc_results(self, chunks: List, sources: List[str]):
        self.trace["doc_results"] = {
            "chunk_count": len(chunks),
            "sources": sources[:5]
        }
        logger.info(f"[TRACE:{self.query_id}] Docs: {len(chunks)} chunks from {sources[:3]}")

    def log_answer(self, answer: str, confidence: float):
        self.trace["answer"] = {
            "text": answer[:200],
            "confidence": confidence
        }
        logger.info(f"[TRACE:{self.query_id}] Answer: {answer[:100]}... (conf={confidence})")

    def log_evaluation(self, passed: bool, match_type: str, reason: str = None):
        self.trace["evaluation"] = {
            "passed": passed,
            "match_type": match_type,
            "reason": reason
        }
        logger.info(f"[TRACE:{self.query_id}] Eval: {'PASS' if passed else 'FAIL'} ({match_type})")

    def save(self, output_dir: str):
        """Save trace to file for analysis."""
        path = Path(output_dir) / f"trace_{self.query_id}.json"
        with open(path, 'w') as f:
            json.dump(self.trace, f, indent=2)
```

### Integration in ToolAgent

```python
def query(self, question: str, ...):
    trace = QueryTraceLogger(query_id=str(uuid4())[:8], question=question)

    # Log intent
    intent = self.query_interpreter.interpret(question)
    trace.log_intent(intent)

    # Log routing decision
    if intent.query_type == "person_role":
        trace.log_route("KG_PERSON_ROLE", "Intent classified as person role query")
        result = self._kg_person_role_lookup(intent.entity)
        trace.log_kg_results(result.entities, result.relationships)
    else:
        trace.log_route("DOCUMENT_SEARCH", "Fallback to document retrieval")
        result = self.query_pipeline.process(question)
        trace.log_doc_results(result.chunks, [c['document'] for c in result.chunks])

    # Log answer
    answer = self._synthesize(question, result, intent)
    trace.log_answer(answer, confidence)

    trace.save("/tmp/traces/")
    return answer
```

### Success Criteria
- Every query has a trace file
- Can diagnose any failure by reading trace
- Trace shows: intent → route → data → answer

### Guardrails
- Logging only - no logic to short-circuit questions
- Traces saved for post-hoc analysis

---

## Implementation Order

### Phase 1: Quick Wins (1-2 days)
1. **Task 6**: Fix evaluator semantic equivalence - verify it's being called
2. **Task 8**: Add observability logging
3. **Task 7**: Create validation script

**Expected gain**: 5-10% from semantic matching

### Phase 2: Query Routing (2-3 days)
4. **Task 5**: Optimize QueryInterpreter performance
5. Re-enable intent-based routing with timeout protection

**Expected gain**: 5% from proper routing

### Phase 3: Data Extraction (3-5 days)
6. **Task 1**: Business Unit extraction
7. **Task 2**: Project extraction
8. **Task 4**: Customer/Supplier extraction

**Expected gain**: 15-20% from complete KG

### Phase 4: Financial Data (2-3 days)
9. **Task 3**: Financial metrics with authority ranking

**Expected gain**: 5-10% from accurate financials

---

## Success Metrics

| Checkpoint | Target Accuracy | Key Indicator |
|------------|-----------------|---------------|
| After Phase 1 | 65% | semantic_match count > 10 |
| After Phase 2 | 70% | Intent logs for all queries, no timeouts |
| After Phase 3 | 80% | BU/Project/Customer questions passing |
| After Phase 4 | 90% | Financial questions passing |

---

## Test Command

```bash
# Full test
python -m src.test_runner.runner \
    --corpus "Manus Orion" \
    --questions /Users/saleh/Downloads/orion_verified_106q.json

# With trace output
python -m src.test_runner.runner \
    --corpus "Manus Orion" \
    --questions /Users/saleh/Downloads/orion_verified_106q.json \
    --trace-dir /tmp/orion_traces/
```

---

## Final Checklist Before Each Commit

- [ ] No hardcoded entity names, answers, or facts
- [ ] No dictionary mappings for abbreviations/synonyms
- [ ] All semantic understanding uses LLM
- [ ] New schema changes documented
- [ ] Tests pass without regression on MedSync (94.9%)
- [ ] Trace logs show proper routing for sample queries
