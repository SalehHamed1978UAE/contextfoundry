# Replit Instructions: Fix Manus Orion Accuracy (52.8% → 70%+)

## Problem Summary

The system has sophisticated LLM-based query understanding components that aren't being used in the main query flow. The fix is to **wire them in**, not add hardcoded patterns.

## Existing Components (Already Built)

### 1. QueryInterpreter (`query_interpreter.py`)
Uses LLM to parse queries into structured intent:
```python
@dataclass
class QueryIntent:
    entity: str                    # "Sarah Chen"
    direction: str                 # "inbound" | "outbound" | "both"
    relationship_types: List[str]  # ["MANAGES", "OWNS"]
    depth: int                     # 1-3 hops
    target_type: Optional[str]     # "TEAM" | "BUSINESS_UNIT" | None
    query_type: str                # "graph_traversal" | "property_lookup"
    include_properties: bool
    reasoning: str                 # LLM's explanation
```

### 2. DirectedGraphRetriever (`directed_retriever.py`)
Executes structured QueryIntent against the KG with proper traversal:
```python
def execute(self, intent: QueryIntent) -> RetrievalResult:
    # Resolves entity, traverses relationships, respects depth
    # Returns relationships, affected_entities, cascade_paths
```

### 3. QueryIntentClassifier (`query/intent_classifier.py`)
Classifies query intent without hardcoding:
```python
class QueryIntent(Enum):
    PERSON_ROLE = "person_role"
    RELATIONSHIP = "relationship"
    METRIC = "metric"
    POLICY = "policy"
    # etc.
```

## Current Flow (Missing the Good Parts)

```
ToolAgent.query()
    ↓
QueryPipeline.process()  ← Uses simple QueryClassifier
    ↓
RetrievalRouter.route()  ← Does basic graph/doc search
    ↓
_synthesize_direct_answer()  ← LLM has no query understanding context
```

## Fixed Flow (Wire In Existing Components)

```
ToolAgent.query()
    ↓
QueryInterpreter.interpret()  ← ADD: LLM understands what user wants
    ↓
DirectedGraphRetriever.execute()  ← ADD: Proper KG traversal
    ↓
_synthesize_direct_answer(intent=intent)  ← MODIFY: Pass intent to synthesis
```

---

## Implementation Steps

### Step 1: Add QueryInterpreter to ToolAgent

**File**: `src/context_foundry/agents/tool_agent.py`

**In `__init__`** (around line 106):
```python
def __init__(self, session: Session, tenant_id: str, model: str = "gpt-4o-mini"):
    # ... existing code ...

    # ADD these imports at top of file:
    # from .query_interpreter import QueryInterpreter
    # from .directed_retriever import DirectedGraphRetriever

    # ADD after existing initializations:
    self.query_interpreter = QueryInterpreter(
        model=model,
        session=session,
        tenant_id=tenant_id
    )
    self.directed_retriever = DirectedGraphRetriever(session, tenant_id)
```

### Step 2: Use QueryInterpreter in Query Flow

**File**: `src/context_foundry/agents/tool_agent.py`

**In `query()` method** (around line 604, before `pipeline_result = ...`):
```python
def query(self, question: str, ...):
    # ... existing code up to pipeline_result ...

    # ADD: Interpret query using LLM
    query_intent = None
    try:
        query_intent = self.query_interpreter.interpret(question)
        logger.info(f"[AGENT] QueryIntent: entity='{query_intent.entity}', "
                   f"target_type={query_intent.target_type}, "
                   f"query_type={query_intent.query_type}")
    except Exception as e:
        logger.warning(f"[AGENT] Query interpretation failed: {e}")

    # ADD: For graph-suitable queries, use DirectedGraphRetriever
    directed_result = None
    if query_intent and query_intent.query_type == "graph_traversal":
        try:
            directed_result = self.directed_retriever.execute(query_intent)
            if directed_result.entity_found and directed_result.relationships:
                logger.info(f"[AGENT] DirectedRetriever found {len(directed_result.relationships)} relationships")
        except Exception as e:
            logger.warning(f"[AGENT] Directed retrieval failed: {e}")

    # existing pipeline_result code continues...
    pipeline_result = self.query_pipeline.process(question, vault_context=vault_context)
```

### Step 3: Pass Intent to Synthesis

**File**: `src/context_foundry/agents/tool_agent.py`

**Modify `_synthesize_direct_answer`** signature and prompt:
```python
def _synthesize_direct_answer(
    self,
    question: str,
    pipeline_result: RetrievalResult,
    query_intent: Optional[QueryIntent] = None  # ADD parameter
) -> str:
    # ... existing context building code ...

    # ADD: Build intent-aware instruction (no hardcoding!)
    intent_instruction = ""
    if query_intent:
        if query_intent.target_type:
            intent_instruction += f"\n\nThe user is asking for: {query_intent.target_type}"
        if query_intent.query_type == "property_lookup":
            intent_instruction += "\nProvide the specific property/attribute value requested."
        if query_intent.reasoning:
            intent_instruction += f"\nQuery interpretation: {query_intent.reasoning}"

    synthesis_prompt = f"""Based on the following retrieved information, answer the user's question.

QUESTION: {question}
{intent_instruction}

RETRIEVED INFORMATION:
{context}

Answer the specific question asked. If the question asks for responsibilities, provide responsibilities. If it asks for a name, provide the name. Match your answer type to what was asked."""
```

### Step 4: Merge Directed Results with Pipeline Results

**File**: `src/context_foundry/agents/tool_agent.py`

**In `query()` method**, after getting both results:
```python
# Merge directed_result with pipeline_result if both exist
if directed_result and directed_result.entity_found:
    # Add relationships from directed retrieval
    if directed_result.relationships:
        existing_rels = pipeline_result.relationships if pipeline_result else []
        merged_rels = existing_rels + [
            {
                "type": r.relationship_type,
                "source": r.source_name,
                "target": r.target_name,
                "source_type": r.source_type,
                "target_type": r.target_type,
            }
            for r in directed_result.relationships
        ]
        if pipeline_result:
            pipeline_result.relationships = merged_rels

    # Add affected entities
    if directed_result.affected_entities:
        existing_entities = pipeline_result.entities if pipeline_result else []
        for ae in directed_result.affected_entities:
            if ae not in existing_entities:
                existing_entities.append(ae)
        if pipeline_result:
            pipeline_result.entities = existing_entities
```

### Step 5: Update Direct Answer Call

**File**: `src/context_foundry/agents/tool_agent.py`

**Where `_synthesize_direct_answer` is called** (around line 616):
```python
# Change from:
answer = self._synthesize_direct_answer(question, pipeline_result)

# To:
answer = self._synthesize_direct_answer(question, pipeline_result, query_intent)
```

---

## Why This Works (No Hardcoding)

1. **QueryInterpreter uses LLM** to understand "What are the CFO's responsibilities?" means:
   - entity: "CFO"
   - target_type: None (asking about attribute, not entity type)
   - query_type: "property_lookup"
   - reasoning: "User wants responsibilities/duties of CFO role"

2. **DirectedGraphRetriever uses KG traversal** to find:
   - CFO entity → relationships → responsibilities (if stored)
   - Or traverses to find related entities

3. **Synthesis LLM gets the intent** passed to it, so it knows to answer with responsibilities, not identity.

---

## Fixing "Which business unit handles X?" Queries

These require 2-hop traversal. QueryInterpreter already handles this:

**Example**: "Which business unit owns the Falcon UAV Program?"

QueryInterpreter will output:
```json
{
  "entity": "Falcon UAV Program",
  "direction": "inbound",
  "relationship_types": ["OWNS", "MANAGES", "PARENT_OF"],
  "depth": 2,
  "target_type": "BUSINESS_UNIT",
  "reasoning": "Find what OWNS Falcon UAV, filter to BUSINESS_UNIT type"
}
```

DirectedGraphRetriever will:
1. Find "Falcon UAV Program" entity
2. Traverse inbound OWNS/MANAGES relationships
3. Filter results to target_type="BUSINESS_UNIT"
4. Return "Orion Aerospace"

**No hardcoding needed** - the LLM understands the query structure.

---

## Evaluator Fix (Separate Issue)

For Q9 (CEO vs Chief Executive Officer) - use LLM-based semantic equivalence, not hardcoded mappings.

**In `FuzzyEvaluator.__init__`**:
```python
from openai import OpenAI

self.llm_client = OpenAI()
```

**Add method**:
```python
def _check_semantic_equivalence(self, expected: str, actual: str, question: str) -> bool:
    """Use LLM to check if expected and actual are semantically equivalent answers."""
    try:
        response = self.llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""Question: {question}
Expected answer: {expected}
Actual answer: {actual}

Are these semantically equivalent answers to the question? Reply only YES or NO."""
            }],
            temperature=0,
            max_tokens=3
        )
        return response.choices[0].message.content.strip().upper() == "YES"
    except Exception as e:
        logger.warning(f"Semantic equivalence check failed: {e}")
        return False
```

**Call it in `evaluate()`** as a fallback before returning `no_match`:
```python
# After all other matching attempts fail...
if self._check_semantic_equivalence(expected, actual, query):
    return EvaluationResult(True, "semantic_match", ...)

# Only then return no_match
return EvaluationResult(False, "no_match", ...)

---

## Testing

After changes:
```bash
# Restart server to pick up changes
# Then run test
python -m src.test_runner.runner --corpus vault_d1eb12f7 --questions /path/to/orion_verified_106q.json
```

## Summary

| Change | File | What |
|--------|------|------|
| Add QueryInterpreter | tool_agent.py | LLM-based query understanding |
| Add DirectedGraphRetriever | tool_agent.py | Proper KG traversal |
| Pass intent to synthesis | tool_agent.py | LLM knows what to answer |
| Merge results | tool_agent.py | Combine directed + pipeline results |
| Semantic equivalence | evaluator.py | LLM-based answer matching |

**Zero hardcoding. All intelligence comes from LLMs and existing components.**
