# Phase 2: Create Core Few-Shot Examples

**Why:** Research shows few-shot examples improve accuracy from 19% to 97%. We currently have ZERO examples.

**Scope:** Start with Core Foundation examples only. Domain-specific examples come in Phase 5.

---

## Create Directory

```bash
mkdir -p brain/examples
```

---

## Create File: brain/examples/core_examples.json

```json
{
  "domain": "core",
  "description": "Generic business document examples for Core Foundation types",
  "examples": [
    {
      "input": "The Federated Data Catalog enables cross-entity data discovery while maintaining local autonomy. Data Stewards in each department manage their local metadata according to the Hub-and-Spoke governance model.",
      "output": [
        {"name": "Federated Data Catalog", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Named system/methodology for data management"},
        {"name": "Data Steward", "type": "ROLE", "confidence": 0.95, "reasoning": "Organizational position, not a specific person"},
        {"name": "Hub-and-Spoke", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Named governance model/framework"},
        {"name": "department", "type": "ORGANIZATION", "confidence": 0.80, "reasoning": "Organizational unit (generic reference)"}
      ]
    },
    {
      "input": "Corporate Holding Company acquired the Government Services Division. The Government issued new regulations affecting all subsidiaries.",
      "output": [
        {"name": "Corporate Holding Company", "type": "ORGANIZATION", "confidence": 0.90, "reasoning": "Entity that ACTS (acquired) - action verb indicates organization"},
        {"name": "Government Services Division", "type": "ORGANIZATION", "confidence": 0.95, "reasoning": "Named organizational unit"},
        {"name": "Government", "type": "ORGANIZATION", "confidence": 0.90, "reasoning": "Entity that ACTS (issued regulations) - not a location"},
        {"name": "subsidiaries", "type": "ORGANIZATION", "confidence": 0.80, "reasoning": "Organizational entities (generic reference)"}
      ]
    },
    {
      "input": "Phase 1: The Foundation covers months 1-3 and focuses on proving interoperability. The Crawl, Walk, Run Approach ensures gradual scaling.",
      "output": [
        {"name": "Phase 1: The Foundation", "type": "PROCESS", "confidence": 0.95, "reasoning": "Named implementation phase"},
        {"name": "months 1-3", "type": "DATE", "confidence": 0.90, "reasoning": "Time period reference"},
        {"name": "Crawl, Walk, Run Approach", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Named methodology/framework"},
        {"name": "interoperability", "type": "CONCEPT", "confidence": 0.85, "reasoning": "Technical concept being measured"}
      ]
    },
    {
      "input": "The Ministry of Health and Ministry of Transport must align on unified security classifications. Dr. Sarah Chen leads the cross-agency working group.",
      "output": [
        {"name": "Ministry of Health", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Named government agency"},
        {"name": "Ministry of Transport", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Named government agency"},
        {"name": "unified security classifications", "type": "CONCEPT", "confidence": 0.85, "reasoning": "Named standard/framework"},
        {"name": "Dr. Sarah Chen", "type": "PERSON", "confidence": 1.0, "reasoning": "Named individual"},
        {"name": "cross-agency working group", "type": "ORGANIZATION", "confidence": 0.85, "reasoning": "Organizational unit"}
      ]
    },
    {
      "input": "The Enterprise Risk Framework was documented in the Q3 Board Report. The CFO presented findings to the Investment Committee in Abu Dhabi.",
      "output": [
        {"name": "Enterprise Risk Framework", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Named framework"},
        {"name": "Q3 Board Report", "type": "DOCUMENT", "confidence": 0.95, "reasoning": "Named document"},
        {"name": "CFO", "type": "ROLE", "confidence": 0.95, "reasoning": "Job title/role, not specific person"},
        {"name": "Investment Committee", "type": "ORGANIZATION", "confidence": 0.90, "reasoning": "Organizational body"},
        {"name": "Abu Dhabi", "type": "LOCATION", "confidence": 1.0, "reasoning": "Physical location - city"}
      ]
    }
  ]
}
```

---

## Create Loader Function

Add to brain/app.py:

```python
import json
from pathlib import Path

def load_few_shot_examples(domain: str = "core") -> list:
    """Load few-shot examples for the specified domain."""
    examples_dir = Path(__file__).parent / "examples"
    
    # Try domain-specific first, fall back to core
    domain_file = examples_dir / f"{domain}_examples.json"
    core_file = examples_dir / "core_examples.json"
    
    file_to_load = domain_file if domain_file.exists() else core_file
    
    if not file_to_load.exists():
        return []
    
    with open(file_to_load, 'r') as f:
        data = json.load(f)
        return data.get('examples', [])
```

---

## Integration

The examples will be used in Phase 3 when we rewrite the prompt.

For now, just:
1. Create the directory
2. Create core_examples.json
3. Create the loader function
4. Verify it loads correctly: `print(load_few_shot_examples("core"))`

---

**DO NOT proceed to Phase 3 until examples load correctly.**
