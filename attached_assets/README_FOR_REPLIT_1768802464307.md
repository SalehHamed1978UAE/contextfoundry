# Tri-Memory Precedence Pipeline - Implementation Package

## Purpose

This package implements the **tri-memory precedence system** described in the CF Bible:
- **Symbolic > Semantic > Episodic** precedence
- **Data Gates** - "Refuse to hallucinate" system

This addresses Validations #1, #2, and #6 from CF_Validations_Jan19_2026.md.

---

## What's In This Package

### New Files (copy to these locations)

| File | Destination |
|------|-------------|
| `new_files/symbolic_override.py` | `src/context_foundry/memory/symbolic_override.py` |
| `new_files/data_gates.py` | `src/context_foundry/validation/data_gates.py` |
| `new_files/precedence_pipeline.py` | `src/context_foundry/pipeline/precedence_pipeline.py` |

### Modified Files (replace existing files)

| File | Destination |
|------|-------------|
| `modified_files/memory__init__.py` | `src/context_foundry/memory/__init__.py` |
| `modified_files/validation__init__.py` | `src/context_foundry/validation/__init__.py` |
| `modified_files/pipeline__init__.py` | `src/context_foundry/pipeline/__init__.py` |
| `modified_files/core.py` | `src/context_foundry/core.py` |

---

## Installation Steps

### Step 1: Create validation directory if needed
```bash
mkdir -p src/context_foundry/validation
```

### Step 2: Copy new files
```bash
cp new_files/symbolic_override.py src/context_foundry/memory/
cp new_files/data_gates.py src/context_foundry/validation/
cp new_files/precedence_pipeline.py src/context_foundry/pipeline/
```

### Step 3: Replace modified files
```bash
cp modified_files/memory__init__.py src/context_foundry/memory/__init__.py
cp modified_files/validation__init__.py src/context_foundry/validation/__init__.py
cp modified_files/pipeline__init__.py src/context_foundry/pipeline/__init__.py
cp modified_files/core.py src/context_foundry/core.py
```

### Step 4: Verify syntax
```bash
python -c "
import ast
for f in [
    'src/context_foundry/memory/symbolic_override.py',
    'src/context_foundry/validation/data_gates.py',
    'src/context_foundry/pipeline/precedence_pipeline.py',
    'src/context_foundry/core.py'
]:
    with open(f) as file:
        ast.parse(file.read())
    print(f'{f} - OK')
"
```

---

## What Each Component Does

### 1. Symbolic Override Engine (`symbolic_override.py`)
- Evaluates symbolic rules against queries
- Can **override**, **constrain**, **prohibit**, or **augment** semantic answers
- Pattern matching for query types (compensation, PTO, confidential, etc.)
- Rule evaluation with priority ordering

### 2. Data Gates (`data_gates.py`)
- **Gate 1**: Entity existence check
- **Gate 2**: Chunk coverage check (do chunks mention query subjects?)
- **Gate 3**: Answer grounding check (is answer supported by sources?)
- **Gate 4**: Hedging/fabrication detection
- Returns "I don't know" responses when appropriate

### 3. Precedence Pipeline (`precedence_pipeline.py`)
- Orchestrates the flow: Symbolic -> Semantic -> Episodic -> Data Gates
- Returns `PrecedenceResult` with:
  - `answer`: Final answer
  - `source`: "symbolic" | "semantic" | "episodic" | "refused"
  - `confidence`: Confidence score
  - `explanation`: Why this source was used

### 4. Core Integration (`core.py`)
- Adds precedence check between reasoning and validation
- New response fields: `answer_source`, `precedence_confidence`
- Logs precedence events

---

## Query Flow After Integration

```
Query
  |
  v
Retrieval (build context bundle)
  |
  v
Reasoning (generate answer)
  |
  v
PRECEDENCE PIPELINE (NEW)
  |-- 1. Symbolic Override Check
  |     - Do any rules apply?
  |     - Should we override/constrain/prohibit?
  |
  |-- 2. Data Gates Validation
  |     - Is entity found?
  |     - Do chunks cover the query?
  |     - Is answer grounded in sources?
  |     - Is LLM hedging/fabricating?
  |
  v
Validation (existing rule checks)
  |
  v
Response (with answer_source field)
```

---

## Expected Impact on 235Q Test

### Data Gates should fix Q196-199
These queries expect `[NOT IN DOCUMENTS]`:
- Q196: CEO salary
- Q197: Series C valuation
- Q198: Q2 2026 pipeline
- Q199: Employee turnover rate

Currently CF hedges. After Data Gates, it should return clean "I don't know" responses.

### Symbolic Override enables rule enforcement
- Compensation queries can be constrained by rules
- Confidential information queries can be prohibited
- Policy-based answers can override semantic retrieval

---

## Testing After Integration

### Quick smoke test
```python
from src.context_foundry.core import ContextFoundry

cf = ContextFoundry(tenant_id="your-tenant-id")

# Test Data Gates - should refuse to hallucinate
result = cf.query("What is the CEO's salary?")
print(f"Source: {result.get('answer_source')}")  # Should be "refused" if not in docs

# Test normal query
result = cf.query("What is MedSync Health's revenue?")
print(f"Source: {result.get('answer_source')}")  # Should be "semantic"
```

### Run 235Q test
After integration, re-run the 235Q test to verify:
1. Q196-199 now return proper "I don't know" responses
2. No regression on other questions
3. New `answer_source` field appears in responses

---

## Spec Document

See `TRIMEMORY_IMPLEMENTATION_SPEC.md` for detailed technical specification including:
- Design rationale
- API contracts
- Test cases
- Future enhancements

---

---

## Step 5: Seed Test Rules

The symbolic override system needs rules in the database. Run the seed script:

```bash
# Dry run first (see what would be created)
python seed_test_rules.py --tenant-id YOUR_TENANT_ID --dry-run

# Actually create the rules
python seed_test_rules.py --tenant-id YOUR_TENANT_ID

# Verify rules exist
python seed_test_rules.py --tenant-id YOUR_TENANT_ID --list
```

### Rules Included

| Rule | Purpose | Helps With |
|------|---------|------------|
| Salary Confidentiality | Block salary queries | Q196 |
| Valuation Confidentiality | Block private valuation queries | Q197 |
| Executive PTO Minimum | Override with policy | Testing |
| VP Bonus Minimum | Constraint application | Q109 |
| Future Pipeline Data | Block future data queries | Q198 |
| HR Metrics Availability | Block missing HR metrics | Q199 |
| PHI Protection | Block health data | Healthcare safety |
| Contract Confidentiality | Block contract terms | Deal protection |

---

## Questions?

The core changes are:
1. **3 new files** - self-contained modules
2. **3 updated __init__.py** - just export additions
3. **1 updated core.py** - 30-line integration block between reasoning and validation

The integration is defensive - if precedence pipeline fails, it falls back to the original answer with an error logged.
