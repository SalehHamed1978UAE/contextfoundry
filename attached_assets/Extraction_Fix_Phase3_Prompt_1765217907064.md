# Phase 3: Rewrite Extraction Prompt

**Problem:** Current prompt is too conservative:
- "Only extract entities that are EXPLICITLY mentioned"
- "Do NOT infer or hallucinate"

This causes the LLM to miss obvious entities.

---

## Current Prompt Location

brain/app.py, approximately lines 158-191

---

## Replace With This Prompt

```python
EXTRACTION_PROMPT = '''
You are an expert entity extractor for enterprise knowledge graphs.

Your PRIMARY goal is COMPLETENESS—missing an entity is worse than including a borderline case.

Extract ALL entities from the following {domain} document.

## ENTITY TYPES

PERSON: Named individuals (e.g., "Dr. Sarah Chen", "John Smith")

ROLE: Job titles, positions, functional roles (e.g., "Data Steward", "CFO", "Project Manager")
- NOT the person, just the role itself

ORGANIZATION: Companies, agencies, departments, ministries, teams, committees, government bodies
- Key test: If it can PERFORM ACTIONS (decide, issue, approve, manage), it's ORGANIZATION
- Examples: "Ministry of Health", "Investment Committee", "Government", "Corporate Holding Company"

LOCATION: PHYSICAL places only - cities, countries, buildings, addresses
- NOT organizational types
- NOT contexts or settings
- Example: "Abu Dhabi" is LOCATION; "Government" is ORGANIZATION

CONCEPT: Frameworks, methodologies, principles, standards, named approaches
- Examples: "Federated Data Catalog", "Hub-and-Spoke", "Zero Trust Model", "GDPR"
- Include document titles that name concepts

PROCESS: Workflows, procedures, phases, implementation stages
- Examples: "Phase 1: Foundation", "Crawl-Walk-Run Approach", "Quarterly Review"

EVENT: Meetings, milestones, occurrences (e.g., "Board Meeting", "Q3 Review")

DATE: Time references (e.g., "December 2025", "Months 1-3", "Q4")

DOCUMENT: Referenced reports, policies, forms (e.g., "Annual Report", "Governance Policy")

## DISAMBIGUATION RULE

If an entity can PERFORM ACTIONS in the text (issues, decides, manages, owns, approves):
→ It is ORGANIZATION, not LOCATION

Example: "The Government issued regulations" → "Government" is ORGANIZATION (it acted)

## FEW-SHOT EXAMPLES

{examples}

## EXTRACTION RULES

1. Extract ALL named concepts, frameworks, and methodologies - these are high value
2. Include the document title and section headers as entities
3. When a term is capitalized or appears as a heading, it's likely an entity
4. If unsure, INCLUDE IT with confidence 0.7-0.8
5. Use confidence 0.9-1.0 for clearly named entities

## OUTPUT FORMAT

Return valid JSON only:
{{
  "entities": [
    {{"name": "exact text", "type": "TYPE", "confidence": 0.9, "reasoning": "brief explanation"}}
  ]
}}

## TEXT TO EXTRACT FROM

{text}
'''
```

---

## Format Few-Shot Examples

Add this function:

```python
def format_few_shot_examples(examples: list) -> str:
    """Format few-shot examples for inclusion in prompt."""
    if not examples:
        return "No examples available."
    
    formatted = []
    for i, ex in enumerate(examples, 1):
        input_text = ex.get('input', '')
        output = ex.get('output', [])
        
        output_str = "\n".join([
            f"  - \"{e['name']}\" → {e['type']} ({e.get('reasoning', '')})"
            for e in output
        ])
        
        formatted.append(f"Example {i}:\nInput: \"{input_text}\"\nOutput:\n{output_str}")
    
    return "\n\n".join(formatted)
```

---

## Update Extraction Call

```python
def extract_entities(text: str, domain: str = "core") -> dict:
    # Load examples for this domain
    examples = load_few_shot_examples(domain)
    formatted_examples = format_few_shot_examples(examples)
    
    # Build prompt
    prompt = EXTRACTION_PROMPT.format(
        domain=domain,
        examples=formatted_examples,
        text=text
    )
    
    # Call LLM with temperature=0 for consistency
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # or your model
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        seed=42
    )
    
    # Parse JSON response
    return json.loads(response.choices[0].message.content)
```

---

## Key Changes Summary

| Old | New |
|-----|-----|
| "ONLY extract EXPLICITLY mentioned" | "PRIMARY goal is COMPLETENESS" |
| "Do NOT infer or hallucinate" | "If unsure, INCLUDE IT with 0.7-0.8 confidence" |
| No examples | 5 few-shot examples |
| Ambiguous LOCATION definition | "PHYSICAL places only" + ACT test |
| No ROLE type | ROLE separate from PERSON |

---

**After implementing, proceed to Phase 4 (Test).**
