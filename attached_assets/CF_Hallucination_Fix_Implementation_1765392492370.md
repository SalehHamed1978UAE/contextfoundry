# Context Foundry: Hallucination Fix Implementation

## Executive Summary

Four independent AI systems (Perplexity, Gemini, Claude, ChatGPT) analyzed CF's hallucination problem and reached **unanimous consensus**:

> **"Don't ask the LLM to not hallucinate. Don't give it the opportunity to hallucinate."**

The solution is **architectural, not prompt-based**: detect insufficient data BEFORE calling the LLM.

---

## The Problem

After promoting 8,511 entities with only 2,013 relationships (~0.24 per entity):
- Hallucination rate spiked from 1% → 26.7%
- Many entities exist but have ZERO relationships
- LLM "helpfully" invents plausible relationships when none exist

---

## The Solution: Data Gates Architecture

```
Query → Entity Guard → Relationship Guard → Sufficiency Check → Constrained LLM → Verification → Response
```

**Key principle:** The LLM only sees queries where sufficient data exists to answer safely.

---

## Implementation Instructions for Replit

### STEP 1: Add Query Classification (Day 1)

Create a new file or add to existing retrieval module:

```python
# src/context_foundry/agents/query_classifier.py

def classify_query(query: str) -> str:
    """
    Classify query type for routing decisions.
    
    Returns one of: 'existence', 'relationship', 'impact', 'general'
    """
    query_lower = query.lower()
    
    # Existence queries (safe to answer with just entity data)
    existence_keywords = ['exist', 'is there', 'do we have', 'do you know', 'what is']
    if any(w in query_lower for w in existence_keywords):
        return 'existence'
    
    # Relationship queries (NEED relationship data)
    relationship_keywords = [
        'depend', 'depends on', 'dependency', 'dependencies',
        'owner', 'owns', 'owned by', 'who owns',
        'manages', 'managed by', 'manager',
        'connects', 'connected to', 'connection',
        'related', 'relationship', 'upstream', 'downstream',
        'talks to', 'calls', 'uses', 'used by'
    ]
    if any(w in query_lower for w in relationship_keywords):
        return 'relationship'
    
    # Impact queries (NEED relationship data for blast radius)
    impact_keywords = [
        'blast', 'radius', 'impact', 'affects', 'affected',
        'fail', 'fails', 'failure', 'outage',
        'cascade', 'cascading', 'downstream impact',
        'what happens if', 'what breaks'
    ]
    if any(w in query_lower for w in impact_keywords):
        return 'impact'
    
    # Default: general query
    return 'general'


def get_data_sufficiency(session, entity_id: str) -> dict:
    """
    Check if entity has enough data for different query types.
    
    Returns:
        {
            'level': 'empty' | 'sparse' | 'adequate' | 'rich',
            'relationship_count': int,
            'incident_count': int,
            'can_answer_relationship': bool,
            'can_answer_impact': bool
        }
    """
    from context_foundry.models.schema import Relationship, LifecycleState
    
    # Count TRUSTED relationships where this entity is source or target
    rel_count = session.query(Relationship).filter(
        Relationship.lifecycle_state == LifecycleState.TRUSTED,
        (Relationship.source_id == entity_id) | (Relationship.target_id == entity_id)
    ).count()
    
    # Count incidents (if we have an incidents table)
    incident_count = 0  # TODO: Add incident count if episodic memory has incidents
    
    total = rel_count + incident_count
    
    # Determine sufficiency level
    if rel_count == 0:
        level = 'empty'
    elif total < 3:
        level = 'sparse'
    elif total < 6:
        level = 'adequate'
    else:
        level = 'rich'
    
    return {
        'level': level,
        'relationship_count': rel_count,
        'incident_count': incident_count,
        'can_answer_relationship': rel_count > 0,
        'can_answer_impact': rel_count >= 2  # Need multiple relationships for blast radius
    }
```

---

### STEP 2: Add Relationship Guard (Day 1 - CRITICAL)

This is the **highest impact change**. Add to the main query processing flow:

```python
# Add to src/context_foundry/agents/retrieval_agent.py or wherever queries are processed

from context_foundry.agents.query_classifier import classify_query, get_data_sufficiency

def process_query_with_guards(self, query: str, entity_name: str = None) -> dict:
    """
    Process query with data gates to prevent hallucination.
    
    This function implements the 4-LLM consensus architecture:
    1. Entity existence guard (already exists)
    2. Relationship guard (NEW - prevents hallucination)
    3. Sufficiency check (NEW - routes based on data quality)
    """
    
    # Extract entity from query if not provided
    if entity_name is None:
        entity_name = self._extract_target_entity_from_query(query)
    
    # ============================================
    # GUARD 1: Entity Existence (already working)
    # ============================================
    if entity_name:
        exists, similar_entities = self._entity_exists(entity_name)
        if not exists:
            return {
                'type': 'NO_ENTITY',
                'response': f"Entity '{entity_name}' was not found in the knowledge graph.",
                'confidence': 1.0,
                'similar_entities': similar_entities,
                'grounded': True
            }
        
        entity = self._get_entity(entity_name)
        entity_id = str(entity.id)
        
        # ============================================
        # GUARD 2: Relationship Guard (NEW - CRITICAL)
        # ============================================
        query_type = classify_query(query)
        sufficiency = get_data_sufficiency(self.session, entity_id)
        
        # If asking about relationships but entity has NONE
        if query_type in ['relationship', 'impact'] and sufficiency['relationship_count'] == 0:
            return {
                'type': 'NO_RELATIONSHIPS',
                'response': self._format_no_relationships_response(entity_name, query_type),
                'confidence': 1.0,
                'entity_found': True,
                'entity_name': entity_name,
                'relationship_count': 0,
                'grounded': True,  # This IS a grounded response - we're certain about the gap
                'data_gap': 'No relationships documented for this entity'
            }
        
        # ============================================
        # GUARD 3: Sufficiency Check
        # ============================================
        if sufficiency['level'] == 'sparse':
            # For sparse data, format only - no LLM reasoning
            return self._format_sparse_response(entity, query, sufficiency)
        
        # ============================================
        # PROCEED: Adequate or Rich data - LLM can reason
        # ============================================
        # Continue to existing LLM reasoning with constrained prompt
        return self._process_with_constrained_reasoning(query, entity, sufficiency)
    
    # No entity identified - use general query handling
    return self._process_general_query(query)


def _format_no_relationships_response(self, entity_name: str, query_type: str) -> str:
    """
    Format response for entities with no documented relationships.
    This is a GROUNDED response - we are certain about the data gap.
    """
    base = f"Entity '{entity_name}' exists in the knowledge graph."
    
    if query_type == 'impact':
        return (
            f"{base} However, no dependency relationships are currently documented. "
            f"Without relationship data, I cannot assess blast radius or downstream impact. "
            f"The impact of a failure would be limited to the entity itself based on current documentation."
        )
    elif query_type == 'relationship':
        return (
            f"{base} However, no relationships (dependencies, ownership, or connections) "
            f"are currently documented for this entity."
        )
    else:
        return f"{base} No relationship data is available."


def _format_sparse_response(self, entity, query: str, sufficiency: dict) -> dict:
    """
    Format response for entities with sparse data (1-2 relationships).
    Uses simple formatting, not full LLM reasoning.
    """
    relationships = self._get_relationships(entity.id)
    
    rel_descriptions = []
    for rel in relationships:
        rel_descriptions.append(
            f"- {rel.source.name} {rel.relationship_type} {rel.target.name} [REL-{rel.id}]"
        )
    
    response = f"Entity '{entity.name}' has limited documentation:\n\n"
    response += "DOCUMENTED RELATIONSHIPS:\n"
    response += "\n".join(rel_descriptions) if rel_descriptions else "None"
    response += f"\n\nNote: Only {sufficiency['relationship_count']} relationship(s) documented. "
    response += "Additional relationships may exist but are not in the knowledge graph."
    
    return {
        'type': 'SPARSE_DATA',
        'response': response,
        'confidence': 0.7,  # Lower confidence due to sparse data
        'entity_found': True,
        'relationship_count': sufficiency['relationship_count'],
        'grounded': True
    }
```

---

### STEP 3: Update Reasoning Prompt (Day 2)

Find the system prompt for the reasoning agent and replace with this:

```python
# In src/context_foundry/agents/reasoning_agent.py or prompts.py

REASONING_SYSTEM_PROMPT = """You are Context Foundry, an enterprise knowledge assistant that provides GROUNDED answers.

CRITICAL RULE: You may ONLY state relationships that are explicitly provided in the context below.

## YOUR RESPONSE PROTOCOL

1. **GROUNDED Section**: List ONLY facts from the provided data
   - Every relationship claim MUST cite its source: [REL-{id}]
   - Every entity fact MUST be from the provided context
   
2. **GAPS Section**: Acknowledge what is NOT known
   - If asked about relationships not in the data, state: "No documented [relationship type]"
   - Be explicit about missing information
   
3. **NO INFERRED Section**: Do NOT include an INFERRED section
   - Do NOT suggest possible or likely relationships
   - Do NOT use phrases like "might depend on" or "probably connects to"
   - Do NOT use your general knowledge to fill gaps

## WHAT YOU MUST NEVER DO

- State a relationship that is not in the provided context
- Suggest relationships based on naming patterns or conventions
- Use phrases like "typically", "usually", "likely", "probably" for relationships
- Infer relationships from your training data

## EXAMPLE CORRECT RESPONSE

Given: Entity "Payment Service" with relationships: [Payment Service DEPENDS_ON User Database]

GROUNDED:
- Payment Service exists in the knowledge graph
- Payment Service depends on User Database [REL-123]

GAPS:
- No ownership information documented for Payment Service
- No downstream dependencies documented (services that depend on Payment Service)

## EXAMPLE CORRECT RESPONSE (NO RELATIONSHIPS)

Given: Entity "API Gateway" with relationships: []

GROUNDED:
- API Gateway exists in the knowledge graph

GAPS:
- No dependency relationships documented
- No ownership information documented
- Cannot assess blast radius without relationship data

Remember: It is BETTER to say "not documented" than to guess. Your value is ACCURACY, not completeness."""
```

---

### STEP 4: Remove INFERRED from Output Parsing (Day 3)

Update the response parser to reject or filter INFERRED content:

```python
# In response parsing code

def parse_reasoning_response(response: str) -> dict:
    """
    Parse LLM response and filter any INFERRED content.
    """
    result = {
        'grounded': [],
        'gaps': [],
        'raw_response': response
    }
    
    # Parse GROUNDED section
    if 'GROUNDED:' in response:
        grounded_section = extract_section(response, 'GROUNDED:', ['GAPS:', 'INFERRED:'])
        result['grounded'] = parse_bullet_points(grounded_section)
    
    # Parse GAPS section
    if 'GAPS:' in response:
        gaps_section = extract_section(response, 'GAPS:', ['INFERRED:'])
        result['gaps'] = parse_bullet_points(gaps_section)
    
    # EXPLICITLY IGNORE any INFERRED section
    if 'INFERRED:' in response:
        result['warning'] = 'INFERRED section was present but ignored'
        # Log this for monitoring - the LLM shouldn't be producing this
        log_warning(f"LLM produced INFERRED section despite instructions: {response}")
    
    return result
```

---

### STEP 5: Add Verification Layer (Day 4 - Optional but Recommended)

```python
# src/context_foundry/agents/verifier.py

def verify_response_claims(response: str, context_bundle: dict) -> dict:
    """
    Extract claims from LLM response and verify against knowledge graph.
    
    This is a defense-in-depth measure to catch any hallucinations
    that slip through the other guards.
    """
    # Extract relationship claims from response
    claims = extract_relationship_claims(response)
    
    verified = []
    rejected = []
    
    for claim in claims:
        # Check if this relationship exists in the context
        if verify_claim_in_context(claim, context_bundle):
            verified.append(claim)
        else:
            rejected.append(claim)
            log_attempted_hallucination(claim)
    
    fidelity_score = len(verified) / len(claims) if claims else 1.0
    
    return {
        'verified_claims': verified,
        'rejected_claims': rejected,
        'fidelity_score': fidelity_score,
        'needs_regeneration': len(rejected) > 0
    }


def extract_relationship_claims(response: str) -> list:
    """
    Extract relationship claims as (source, relationship_type, target) triples.
    """
    claims = []
    
    # Pattern: "X depends on Y" or "X DEPENDS_ON Y"
    import re
    patterns = [
        r'(\w+(?:\s+\w+)*)\s+depends\s+on\s+(\w+(?:\s+\w+)*)',
        r'(\w+(?:\s+\w+)*)\s+DEPENDS_ON\s+(\w+(?:\s+\w+)*)',
        r'(\w+(?:\s+\w+)*)\s+owns\s+(\w+(?:\s+\w+)*)',
        r'(\w+(?:\s+\w+)*)\s+manages\s+(\w+(?:\s+\w+)*)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, response, re.IGNORECASE)
        for match in matches:
            claims.append({
                'source': match[0].strip(),
                'relationship': pattern.split('\\s+')[1],  # Extract relationship type
                'target': match[1].strip()
            })
    
    return claims
```

---

### STEP 6: Integration - Update Main Query Flow

Integrate all the guards into the main query processing:

```python
# In the main query handler (e.g., api.py or main processing file)

@app.route('/api/v1/query', methods=['POST'])
def handle_query():
    query = request.json.get('query')
    
    # Use the new guarded query processing
    result = retrieval_agent.process_query_with_guards(query)
    
    # Add metadata about the response type
    response = {
        'answer': result['response'],
        'type': result['type'],
        'confidence': result['confidence'],
        'grounded': result.get('grounded', False),
        'data_gap': result.get('data_gap', None)
    }
    
    return jsonify(response)
```

---

### STEP 7: Run Evaluation (Day 5)

After implementing, run the 100-query evaluation:

```python
# Run this to compare before/after

from context_foundry.evaluation.run_100_eval import run_evaluation

print("Running post-fix evaluation...")
results = run_evaluation()

print("\n" + "="*60)
print("COMPARISON: Before vs After Hallucination Fix")
print("="*60)
print(f"\nBEFORE FIX (Dec 10 AM):")
print(f"  ACCURATE:      23 (23.0%)")
print(f"  PARTIAL:       54 (54.0%)")
print(f"  NOT_FOUND:     19 (19.0%)")
print(f"  HALLUCINATED:   1 ( 1.0%)")

print(f"\nAFTER PIPELINE FIX (without guards):")
print(f"  ACCURATE:       8 (26.7%)")
print(f"  PARTIAL:       14 (46.7%)")
print(f"  NOT_FOUND:      0 ( 0.0%)")
print(f"  HALLUCINATED:   8 (26.7%)")

print(f"\nAFTER HALLUCINATION FIX (with guards):")
print(f"  ACCURATE:      {results['accurate']} ({results['accurate_pct']:.1f}%)")
print(f"  PARTIAL:       {results['partial']} ({results['partial_pct']:.1f}%)")
print(f"  NOT_FOUND:     {results['not_found']} ({results['not_found_pct']:.1f}%)")
print(f"  HALLUCINATED:  {results['hallucinated']} ({results['hallucinated_pct']:.1f}%)")

# Success criteria
if results['hallucinated_pct'] < 5:
    print("\n✅ SUCCESS: Hallucination rate < 5%")
else:
    print("\n❌ FAIL: Hallucination rate still too high")

if results['not_found_pct'] < 10:
    print("✅ SUCCESS: NOT_FOUND rate < 10%")
else:
    print("⚠️  WARNING: NOT_FOUND rate increased significantly")
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `query_classifier.py` | NEW - Query classification + sufficiency checking |
| `retrieval_agent.py` | ADD - Relationship guard + sufficiency routing |
| `reasoning_agent.py` | UPDATE - New constrained prompt |
| `response_parser.py` | UPDATE - Ignore INFERRED section |
| `verifier.py` | NEW (optional) - Post-generation verification |

---

## Expected Results

| Metric | Before Guards | After Guards | Target |
|--------|---------------|--------------|--------|
| Hallucination | 26.7% | <5% | <5% ✓ |
| NOT_FOUND | 0% | 3-5% | <10% ✓ |
| Accurate | 26.7% | 50%+ | Higher ✓ |

---

## Key Principle

> **"Don't ask the LLM to not hallucinate. Don't give it the opportunity to hallucinate."**

The guards prevent the LLM from seeing queries it can't safely answer. This is architectural, not prompt-based.
