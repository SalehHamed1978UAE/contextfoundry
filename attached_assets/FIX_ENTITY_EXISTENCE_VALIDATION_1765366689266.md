# Context Foundry: Entity Existence Validation Fix

## THE PROBLEM

Context Foundry hallucinates about entities that don't exist in the knowledge graph.

**Example:**
- Query: "What is the blast radius if Payment Processor fails?"
- Reality: "Payment Processor" doesn't exist in the database
- Current behavior: Makes up an answer about a non-existent entity
- Expected behavior: "Entity 'Payment Processor' not found"

**This applies to ALL query types, not just blast radius:**
- Impact queries: "What is affected if X fails?"
- Ownership queries: "Who owns X?"
- Dependency queries: "What does X depend on?"
- Expertise queries: "Who is the expert on X?"
- Escalation queries: "Who to contact for X issues?"

---

## ROOT CAUSE

The query flow is:

```
1. User query arrives
2. RetrievalAgent extracts entity mentions from query
3. RetrievalAgent searches for entities in semantic memory
4. RetrievalAgent builds ContextBundle (sets target_entity_found = True/False)
5. ReasoningAgent receives bundle and calls LLM
6. LLM generates answer (EVEN IF ENTITY DOESN'T EXIST)
7. Response returned to user
```

**The bug:** Step 5-6 happen even when `target_entity_found = False`. The LLM then fabricates an answer.

---

## THE FIX

### Principle

**Before calling the LLM, validate that the entity exists. If it doesn't exist, return "not found" immediately without calling the LLM.**

### Where to Fix

**File:** `src/context_foundry/agents/retrieval.py`

**Location:** In `build_context_bundle()` or `process_query()`, AFTER entity search, BEFORE returning bundle to reasoning.

### Logic to Add

```python
def _extract_target_entity_from_query(self, query: str, query_type: str) -> Optional[str]:
    """
    Extract the target entity name from the query.
    
    Examples:
    - "What is the blast radius if API Gateway fails?" → "API Gateway"
    - "Who owns the Payment Service?" → "Payment Service"
    - "What does Auth Service depend on?" → "Auth Service"
    """
    # Use patterns to extract entity name
    patterns = [
        # Impact patterns
        r"blast radius (?:of|if|when) (?:the )?(.+?)(?:\s+(?:fails|goes down|becomes unavailable|is unavailable|crashes))",
        r"(?:what|which) (?:services? )?(?:are |is |will be )?affected if (?:the )?(.+?)(?:\s+(?:fails|goes down))",
        r"impact (?:of|if|when) (?:the )?(.+?)(?:\s+(?:fails|goes down))",
        
        # Ownership patterns  
        r"who (?:owns|maintains|manages) (?:the )?(.+?)(?:\?|$)",
        r"(?:what|which) team (?:owns|maintains|manages) (?:the )?(.+?)(?:\?|$)",
        
        # Dependency patterns
        r"what does (?:the )?(.+?) depend on",
        r"dependencies (?:of|for) (?:the )?(.+?)(?:\?|$)",
        r"what (?:services? )?depend(?:s)? on (?:the )?(.+?)(?:\?|$)",
        
        # Expertise patterns
        r"who is the expert on (?:the )?(.+?)(?:\?|$)",
        r"who knows (?:about |the most about )?(?:the )?(.+?)(?:\?|$)",
        
        # Escalation patterns
        r"who (?:should I |to )(?:contact|escalate to) for (?:the )?(.+?)(?:\?|$)",
    ]
    
    query_lower = query.lower()
    for pattern in patterns:
        match = re.search(pattern, query_lower, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None


def _entity_exists(self, entity_name: str) -> Tuple[bool, List[str]]:
    """
    Check if entity exists in the knowledge graph.
    Returns: (exists: bool, similar_entities: List[str])
    """
    # Exact match (case-insensitive)
    exact_match = self.semantic_memory.find_entity_by_name(entity_name)
    if exact_match:
        return True, []
    
    # Fuzzy search for suggestions
    similar = self.semantic_memory.search_entities_by_name(
        entity_name, 
        limit=5, 
        min_similarity=0.6
    )
    similar_names = [e.name for e in similar]
    
    return False, similar_names


def _create_entity_not_found_response(self, entity_name: str, similar_entities: List[str]) -> dict:
    """
    Create a structured response for when entity doesn't exist.
    """
    response = {
        "success": True,
        "answer": f"Entity '{entity_name}' was not found in the knowledge graph. Cannot process query about a non-existent entity.",
        "confidence": 1.0,  # We are 100% confident it doesn't exist
        "confidence_level": "high",
        "grounded": [],
        "inferred": [],
        "gaps": [f"Entity '{entity_name}' does not exist in the knowledge graph"],
        "entity_found": False,
        "query_entity": entity_name,
    }
    
    if similar_entities:
        response["similar_entities"] = similar_entities
        response["answer"] += f"\n\nDid you mean one of these?\n- " + "\n- ".join(similar_entities)
    
    return response
```

### Integration Point

In `build_context_bundle()` or the main query handler, add this check BEFORE calling reasoning:

```python
def process_query(self, query: str) -> dict:
    # Step 1: Classify query
    query_type = self._classify_query_type(query)
    
    # Step 2: Extract target entity from query
    target_entity = self._extract_target_entity_from_query(query, query_type)
    
    # Step 3: If query references a specific entity, verify it exists
    if target_entity:
        exists, similar = self._entity_exists(target_entity)
        
        if not exists:
            # SHORT-CIRCUIT: Don't call LLM, return "not found" immediately
            return self._create_entity_not_found_response(target_entity, similar)
    
    # Step 4: Entity exists (or query doesn't reference specific entity)
    # Continue with normal flow...
    bundle = self.build_context_bundle(query)
    response = self.reasoning_agent.reason(bundle)
    return response
```

---

## FILES TO MODIFY

| File | Change |
|------|--------|
| `src/context_foundry/agents/retrieval.py` | Add entity extraction, existence check, short-circuit logic |
| `src/context_foundry/memory/semantic.py` | Add `search_entities_by_name()` for fuzzy matching (if not exists) |

**DO NOT MODIFY:**
- `reasoning.py` — The fix should happen BEFORE reasoning is called
- `context_bundle.py` — No changes needed

---

## TEST CASES

After implementing, run these tests:

### Entity Not Found (should return "not found")

```bash
# Test 1: Non-existent service (blast radius)
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the blast radius if Payment Processor fails?"}'
# Expected: "Entity 'Payment Processor' was not found"

# Test 2: Non-existent service (ownership)
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Who owns the XYZ123 Service?"}'
# Expected: "Entity 'XYZ123 Service' was not found"

# Test 3: Non-existent service (dependencies)
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What does FakeService depend on?"}'
# Expected: "Entity 'FakeService' was not found"

# Test 4: Non-existent person (expertise)
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Who is the expert on the Nonexistent System?"}'
# Expected: "Entity 'Nonexistent System' was not found"
```

### Entity Exists (should work normally)

```bash
# Test 5: Real entity (blast radius)
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the blast radius if API Gateway fails?"}'
# Expected: Normal GROUNDED/GAP/INFERRED response

# Test 6: Real entity (ownership)
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Who owns the Auth Service?"}'
# Expected: Normal response with team info

# Test 7: Real entity (dependencies)
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What does the User Database depend on?"}'
# Expected: Normal response
```

### Edge Cases

```bash
# Test 8: Query without specific entity
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What services have had incidents this month?"}'
# Expected: Normal response (no entity extraction needed)

# Test 9: Empty query
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": ""}'
# Expected: 400 error "No query provided"

# Test 10: Partial entity name match
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the blast radius if API fails?"}'
# Expected: Either finds "API Gateway" or suggests similar entities
```

---

## VALIDATION CRITERIA

The fix is complete when:

1. ✅ Queries about non-existent entities return "Entity not found" (not hallucinations)
2. ✅ Queries about existing entities work exactly as before
3. ✅ Similar entity suggestions are provided when entity not found
4. ✅ The LLM is NOT called when entity doesn't exist (check logs)
5. ✅ All 10 test cases pass
6. ✅ No regressions in the 23-query validation suite

---

## IMPORTANT NOTES

1. **This is a RETRIEVAL layer fix, not a REASONING layer fix.** The check must happen before the LLM is called.

2. **The fix must be GENERAL, not query-type-specific.** Don't add separate checks for blast radius, ownership, dependencies, etc. One check covers all.

3. **Entity extraction patterns should be robust.** Handle variations like:
   - "API Gateway" vs "the API Gateway"
   - "fails" vs "goes down" vs "becomes unavailable"
   - "owns" vs "maintains" vs "manages"

4. **Fuzzy matching for suggestions should be helpful but not overly aggressive.** A threshold of 0.6 similarity is reasonable.

5. **The response format should match existing patterns.** Include `success`, `answer`, `confidence`, etc.

---

## COPY THIS PROMPT TO REPLIT

```
CRITICAL FIX: Entity Existence Validation

Read /mnt/user-data/outputs/FIX_ENTITY_EXISTENCE_VALIDATION.md for the complete specification.

Summary:
1. Add _extract_target_entity_from_query() to extract entity name from query
2. Add _entity_exists() to check if entity is in the knowledge graph
3. Add _create_entity_not_found_response() to return "not found" response
4. In process_query(), check entity exists BEFORE calling reasoning
5. If entity not found, return immediately without calling LLM
6. Run all 10 test cases
7. Confirm no regressions in 23-query validation suite

DO NOT add this check only for blast radius queries.
DO NOT add this check in reasoning.py.
Add the check in retrieval.py, BEFORE the reasoning agent is called.

Show me all 10 test results before marking complete.
```
