# Phase 6: Multi-Pass Gap-Check Extraction

**Why:** Research shows multi-pass extraction catches entities that single-pass misses. A "gap-check" pass specifically looks for missing entities.

**Scope:** Add a second extraction pass after the main extraction.

---

## Current Flow (Single Pass)

```
Document → Extract Entities → Done
```

## New Flow (Two Pass)

```
Document → Pass 1: Main Extraction → Pass 2: Gap Check → Merge & Dedupe → Done
```

---

## Implementation

### Gap-Check Prompt

```python
GAP_CHECK_PROMPT = '''
You previously extracted these entities from a document:

{existing_entities}

Now review the original text again and identify entities that might be MISSING.

Focus specifically on:
1. Document title and main subject
2. Section headers and headings
3. Capitalized multi-word phrases not yet extracted
4. Named frameworks, methodologies, or standards
5. Organizations mentioned as actors (entities that decide, issue, approve)
6. Roles and job titles

## ORIGINAL TEXT

{text}

## INSTRUCTIONS

Return ONLY NEW entities not already in the list above.
If all entities are captured, return an empty list.

Return valid JSON:
{{
  "missing_entities": [
    {{"name": "exact text", "type": "TYPE", "confidence": 0.8, "reasoning": "why this was missed"}}
  ]
}}
'''
```

---

### Two-Pass Extraction Function

```python
def extract_entities_two_pass(text: str, domain: str = "core") -> dict:
    """
    Two-pass extraction:
    1. Main extraction with few-shot examples
    2. Gap-check pass to find missing entities
    """
    
    # Pass 1: Main extraction
    pass1_result = extract_entities(text, domain)
    pass1_entities = pass1_result.get('entities', [])
    
    # Format existing entities for gap check
    existing_str = "\n".join([
        f"- {e['name']} ({e['type']})" 
        for e in pass1_entities
    ])
    
    # Pass 2: Gap check
    gap_prompt = GAP_CHECK_PROMPT.format(
        existing_entities=existing_str,
        text=text
    )
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # or your model
        messages=[{"role": "user", "content": gap_prompt}],
        temperature=0.0,
        seed=42
    )
    
    try:
        gap_result = json.loads(response.choices[0].message.content)
        missing_entities = gap_result.get('missing_entities', [])
    except json.JSONDecodeError:
        missing_entities = []
    
    # Merge results
    all_entities = pass1_entities + missing_entities
    
    # Deduplicate by name (case-insensitive)
    seen = set()
    unique_entities = []
    for e in all_entities:
        name_lower = e['name'].lower()
        if name_lower not in seen:
            seen.add(name_lower)
            unique_entities.append(e)
    
    return {
        'entities': unique_entities,
        'pass1_count': len(pass1_entities),
        'gap_check_count': len(missing_entities),
        'total_count': len(unique_entities)
    }
```

---

### Integration

Replace single-pass extraction with two-pass:

```python
# OLD
result = extract_entities(text, domain)

# NEW
result = extract_entities_two_pass(text, domain)
```

---

## Expected Improvement

| Metric | Single Pass | Two Pass |
|--------|-------------|----------|
| Entity count | 30-40 | 45-55 |
| Document title captured | Sometimes | Almost always |
| Section headers | Partial | Complete |

---

## Test

Run on the Federated Data Catalog document:

1. Record Pass 1 count
2. Record Gap Check count (new entities found)
3. Record Total after deduplication

Example output:
```
Pass 1: 35 entities
Gap Check: 8 new entities found
Total: 42 unique entities (1 duplicate removed)
```

---

## Optional: Three-Pass with Type Verification

If type confusion persists, add a third pass:

```python
TYPE_VERIFICATION_PROMPT = '''
Review these entities and verify their types are correct:

{entities_to_verify}

Apply the ACT test: If an entity PERFORMS ACTIONS (decides, issues, manages), it's ORGANIZATION not LOCATION.

Return corrections only:
{{
  "corrections": [
    {{"name": "...", "old_type": "LOCATION", "new_type": "ORGANIZATION", "reasoning": "..."}}
  ]
}}
'''
```

Only implement this if type confusion persists after Phase 4 testing.

---

## Success Criteria

✅ **Pass** if:
- Gap check finds 5+ additional entities
- Total entity count increases by 15%+
- No duplicate entities in final output

---

**This completes all 6 phases.**
