# Replit Instructions: Fix Manus Orion Accuracy (52.8% → 70%+)

## The Real Problem

You already built LLM-based query understanding (`QueryTimeSemanticAgent`) but it's **disabled by default**. The system is using hardcoded patterns instead.

### What Exists (Disabled)

```python
# external.py line 381-384
use_semantic_agent = request.args.get('semantic_agent', 'false').lower() == 'true'
if use_semantic_agent:
    return _handle_semantic_agent_query(...)  # ← LLM-based, NOT used by default
```

### What's Being Used (Hardcoded)

1. **PatternBasedQueryParser** (query_parser.py) - 50+ regex patterns
2. **ABBREVIATION_MAP** (entity_resolver.py) - 40+ hardcoded abbreviations
3. **STATE_MAPPINGS** (evaluator.py) - 50 US state abbreviations
4. **No LLM semantic equivalence** in evaluator

The spec document you were given explicitly said:
> "Adding specific fixes for each case = **endless whack-a-mole**"
> "**No pre-defined synonym tables needed**"

But the current implementation IS whack-a-mole with hardcoded patterns.

---

## Fix 1: Enable LLM-Based Query Understanding

**Option A: Make it the default**

File: `src/context_foundry/api/external.py`

```python
# Change line 381 from:
use_semantic_agent = request.args.get('semantic_agent', 'false').lower() == 'true'

# To:
use_semantic_agent = request.args.get('semantic_agent', 'true').lower() == 'true'
```

**Option B: Wire QueryTimeSemanticAgent into ToolAgent**

File: `src/context_foundry/agents/tool_agent.py`

In `__init__`:
```python
from .semantic_agent import QueryTimeSemanticAgent

self.semantic_agent = QueryTimeSemanticAgent(
    session=session,
    tenant_id=tenant_id
)
```

In `query()` method, use it for query understanding instead of the pipeline's pattern-based classification.

---

## Fix 2: Add LLM Semantic Equivalence to Evaluator

`QAVerifier._llm_verify()` checks if an answer is *supported by evidence* - different use case.

For the evaluator, we need: "are expected and actual answers *semantically equivalent*?"

**Reuse the OpenAI client pattern** from QAVerifier, but with an equivalence-specific prompt:

File: `src/test_runner/evaluator.py`

**In `__init__`**:
```python
import os
from openai import OpenAI

# Reuse same client pattern as QAVerifier
api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
self.llm_client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
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

Are these semantically equivalent answers to the question?
Consider: abbreviations (CEO = Chief Executive Officer), different phrasings,
and cases where actual contains the expected information.

Reply YES or NO only."""
            }],
            temperature=0,
            max_tokens=3
        )
        return response.choices[0].message.content.strip().upper() == "YES"
    except Exception as e:
        eval_logger.warning(f"Semantic equivalence check failed: {e}")
        return False
```

**In `evaluate_detailed()`**, add as final fallback before returning no_match:
```python
# After all other matching attempts...

# Try LLM semantic equivalence as last resort
if self._check_semantic_equivalence(expected, actual, query):
    return EvaluationResult(
        True,
        "semantic_match",
        normalized_expected=norm_expected,
        normalized_actual=norm_actual
    )

# Only now return no_match
return EvaluationResult(False, "no_match", ...)
```

---

## Fix 3: Remove Hardcoded Abbreviation Maps

These should be deleted or deprecated. The LLM knows all abbreviations.

**Files to clean up:**
- `entity_resolver.py`: Remove `ABBREVIATION_MAP` (lines 26-63)
- `evaluator.py`: Remove `STATE_MAPPINGS` (lines 65-79)
- `query_parser.py`: Remove regex pattern lists (use `QueryTimeSemanticAgent` instead)

The LLM already knows:
- CEO = Chief Executive Officer
- CA = California
- API = Application Programming Interface
- K8s = Kubernetes
- ...and every other abbreviation

---

## Why This Is The Correct Fix

1. **You already built the LLM-based system** - it's in `semantic_agent.py`
2. **The spec told you not to hardcode** - it said "endless whack-a-mole"
3. **Hardcoded maps don't scale** - you can't anticipate every abbreviation
4. **LLM is the source of truth** for semantic understanding

---

## Testing

After changes, run:
```bash
# Restart server
# Run test
python -m src.test_runner.runner --corpus vault_d1eb12f7 --questions /path/to/orion_verified_106q.json
```

If accuracy doesn't improve, check logs for:
- Is `QueryTimeSemanticAgent` being called?
- Is `_check_semantic_equivalence` being called?
- What is the LLM returning?

---

## Summary

| Problem | Current State | Fix |
|---------|--------------|-----|
| Query understanding | Hardcoded regex patterns | Enable `QueryTimeSemanticAgent` |
| Entity resolution | Hardcoded `ABBREVIATION_MAP` | Use LLM in entity resolver |
| Answer evaluation | Hardcoded `STATE_MAPPINGS` | Add LLM semantic equivalence |

**The LLM-based components exist. Just enable them.**
