# Context Foundry: Stage 2 Implementation Spec

## For: Replit
## Goal: Prove context-attached beats bare triples
## Reference: CF_Foundational_Reference_v1.md

---

## 1. What You're Proving

**Hypothesis:** Relationships with context (temporal, provenance, confidence, event) answer questions that bare triples cannot.

**Current state:** Relationships are bare triples: `(source, type, target)`

**Target state:** Relationships carry context: `(source, type, target, temporal, provenance, confidence, event_context)`

---

## 2. Success Criteria

You're done when:

1. ✓ Relationships table has context fields
2. ✓ Extraction populates context fields from documents
3. ✓ Context Bundle includes relationship context
4. ✓ System answers contextual questions correctly
5. ✓ **16/20 correct on the test suite below**

---

## 3. Implementation Tasks

### Task 1: Extend Relationships Schema

Add context fields to the relationships table:

```sql
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ;
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ;
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS provenance_chunk_id UUID REFERENCES document_chunks(id);
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS provenance_text TEXT;  -- The actual sentence/passage
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS event_context TEXT;    -- What situation/event this relates to
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS qualifiers JSONB;      -- Flexible additional context

-- Add index for temporal queries
CREATE INDEX IF NOT EXISTS idx_relationships_temporal 
ON relationships (tenant_id, valid_from, valid_to);

COMMENT ON COLUMN relationships.valid_from IS 'When this relationship became true';
COMMENT ON COLUMN relationships.valid_to IS 'When this relationship ended (NULL = still active)';
COMMENT ON COLUMN relationships.provenance_chunk_id IS 'Source document chunk this was extracted from';
COMMENT ON COLUMN relationships.provenance_text IS 'The actual text that supports this relationship';
COMMENT ON COLUMN relationships.event_context IS 'The situation or event this relationship belongs to';
COMMENT ON COLUMN relationships.qualifiers IS 'Additional context (role details, conditions, etc.)';
```

### Task 2: Update Extraction to Capture Context

Modify the extraction prompt to capture context:

```python
EXTRACTION_PROMPT = """
Extract entities and relationships from this text.

For each relationship, also extract:
- TEMPORAL: When did this start? When did it end? (dates, years, or "ongoing")
- PROVENANCE: Quote the exact sentence that supports this relationship
- EVENT_CONTEXT: What situation or event is this part of? (e.g., "first tenure", "during restructuring")
- QUALIFIERS: Any additional details (role level, department, conditions)

Example input:
"In August 2011, Jobs resigned as CEO and was appointed Chairman of Apple."

Example output:
{
  "entities": [
    {"name": "Steve Jobs", "type": "PERSON"},
    {"name": "Apple", "type": "ORGANIZATION"},
    {"name": "CEO", "type": "POSITION"},
    {"name": "Chairman", "type": "POSITION"}
  ],
  "relationships": [
    {
      "source": "Steve Jobs",
      "type": "HELD_POSITION",
      "target": "CEO",
      "valid_from": null,
      "valid_to": "2011-08",
      "provenance_text": "In August 2011, Jobs resigned as CEO",
      "event_context": "Jobs' resignation due to health issues",
      "qualifiers": {"at_organization": "Apple", "end_reason": "resignation"}
    },
    {
      "source": "Steve Jobs",
      "type": "HELD_POSITION", 
      "target": "Chairman",
      "valid_from": "2011-08",
      "valid_to": null,
      "provenance_text": "was appointed Chairman of Apple",
      "event_context": "Jobs' resignation and appointment as Chairman",
      "qualifiers": {"at_organization": "Apple"}
    }
  ]
}

Now extract from this text:
{text}
"""
```

Update the extraction code to save context fields:

```python
def save_relationship(session, tenant_id, rel_data, chunk_id):
    """Save relationship with context fields."""
    
    relationship = Relationship(
        tenant_id=tenant_id,
        source_entity_id=resolve_entity(rel_data["source"]),
        target_entity_id=resolve_entity(rel_data["target"]),
        relationship_type=rel_data["type"],
        # Context fields:
        valid_from=parse_date(rel_data.get("valid_from")),
        valid_to=parse_date(rel_data.get("valid_to")),
        provenance_chunk_id=chunk_id,
        provenance_text=rel_data.get("provenance_text"),
        event_context=rel_data.get("event_context"),
        qualifiers=rel_data.get("qualifiers", {}),
        # Standard fields:
        confidence=rel_data.get("confidence", 0.8),
        lifecycle_state="STAGING",
        source_chunk_ids=[chunk_id]
    )
    
    session.add(relationship)
    return relationship


def parse_date(date_str):
    """Parse various date formats to timestamp."""
    if not date_str or date_str.lower() in ["null", "none", "ongoing", "present"]:
        return None
    
    # Handle various formats: "2011-08", "August 2011", "2011", etc.
    # Use dateutil or similar for flexible parsing
    try:
        from dateutil import parser
        return parser.parse(date_str, default=datetime(2000, 1, 1))
    except:
        return None
```

### Task 3: Update Context Bundle to Include Relationship Context

Modify the retrieval to include context:

```python
def build_context_bundle(session, tenant_id, entity_id, query=None):
    """Build Context Bundle with relationship context."""
    
    # Get entity with attributes
    entity = get_entity_with_context(session, tenant_id, entity_id)
    
    # Get relationships WITH context (both directions)
    relationships = session.execute(
        text("""
            SELECT 
                r.id,
                r.relationship_type,
                r.valid_from,
                r.valid_to,
                r.provenance_text,
                r.event_context,
                r.qualifiers,
                r.confidence,
                'outgoing' as direction,
                target.id as other_id,
                target.name as other_name,
                target.entity_type as other_type
            FROM relationships r
            JOIN entities target ON target.id = r.target_entity_id
            WHERE r.tenant_id = :tenant_id
            AND r.source_entity_id = :entity_id
            AND r.lifecycle_state = 'TRUSTED'
            
            UNION ALL
            
            SELECT 
                r.id,
                r.relationship_type,
                r.valid_from,
                r.valid_to,
                r.provenance_text,
                r.event_context,
                r.qualifiers,
                r.confidence,
                'incoming' as direction,
                source.id as other_id,
                source.name as other_name,
                source.entity_type as other_type
            FROM relationships r
            JOIN entities source ON source.id = r.source_entity_id
            WHERE r.tenant_id = :tenant_id
            AND r.target_entity_id = :entity_id
            AND r.lifecycle_state = 'TRUSTED'
        """),
        {"tenant_id": tenant_id, "entity_id": entity_id}
    ).fetchall()
    
    # Format relationships with context
    formatted_rels = []
    for r in relationships:
        formatted_rels.append({
            "type": r.relationship_type,
            "direction": r.direction,
            "other_entity": {
                "id": str(r.other_id),
                "name": r.other_name,
                "type": r.other_type
            },
            # Context:
            "valid_from": r.valid_from.isoformat() if r.valid_from else None,
            "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            "provenance": r.provenance_text,
            "event_context": r.event_context,
            "qualifiers": r.qualifiers or {},
            "confidence": r.confidence
        })
    
    return {
        "focal_entity": entity,
        "relationships": formatted_rels,
        "relationship_count": len(formatted_rels)
    }
```

### Task 4: Update Reasoning to Use Context

Update the reasoning prompt to use relationship context:

```python
REASONING_PROMPT = """
Answer the question based on this structured knowledge.

ENTITY:
{entity}

RELATIONSHIPS:
{relationships}

Each relationship includes:
- type: The relationship type
- other_entity: The connected entity
- valid_from/valid_to: When this relationship was active
- provenance: The source text that supports this
- event_context: What situation this relates to
- confidence: How confident we are (0-1)

QUESTION: {question}

INSTRUCTIONS:
1. Use the relationship context to answer accurately
2. If asked "when", use valid_from/valid_to
3. If asked "how many", count relationships but note any with low confidence
4. If asked "source", cite the provenance text
5. If context is missing or confidence is low, say so
6. Never make up information not in the data

ANSWER:
"""

def format_relationships_for_prompt(relationships):
    """Format relationships with context for LLM."""
    lines = []
    for r in relationships:
        line = f"- {r['type']} → {r['other_entity']['name']} ({r['other_entity']['type']})"
        
        # Add temporal context
        if r['valid_from'] or r['valid_to']:
            temporal = []
            if r['valid_from']:
                temporal.append(f"from {r['valid_from']}")
            if r['valid_to']:
                temporal.append(f"to {r['valid_to']}")
            else:
                temporal.append("ongoing")
            line += f" [{', '.join(temporal)}]"
        
        # Add event context
        if r['event_context']:
            line += f" (context: {r['event_context']})"
        
        # Add provenance
        if r['provenance']:
            line += f"\n  Source: \"{r['provenance']}\""
        
        # Add confidence if not high
        if r['confidence'] and r['confidence'] < 0.8:
            line += f" [confidence: {r['confidence']:.0%}]"
        
        lines.append(line)
    
    return "\n".join(lines)
```

### Task 5: Add Temporal Query Support

Add ability to query relationships by time:

```python
def get_relationships_at_time(session, tenant_id, entity_id, at_time, rel_type=None):
    """Get relationships that were active at a specific time."""
    
    query = """
        SELECT r.*, e.name as other_name, e.entity_type as other_type
        FROM relationships r
        JOIN entities e ON e.id = r.target_entity_id
        WHERE r.tenant_id = :tenant_id
        AND r.source_entity_id = :entity_id
        AND r.lifecycle_state = 'TRUSTED'
        AND (r.valid_from IS NULL OR r.valid_from <= :at_time)
        AND (r.valid_to IS NULL OR r.valid_to >= :at_time)
    """
    
    params = {
        "tenant_id": tenant_id,
        "entity_id": entity_id,
        "at_time": at_time
    }
    
    if rel_type:
        query += " AND r.relationship_type = :rel_type"
        params["rel_type"] = rel_type
    
    return session.execute(text(query), params).fetchall()


def get_relationship_timeline(session, tenant_id, entity_id, rel_type=None):
    """Get chronological timeline of relationships."""
    
    query = """
        SELECT r.*, e.name as other_name, e.entity_type as other_type
        FROM relationships r
        JOIN entities e ON e.id = r.target_entity_id
        WHERE r.tenant_id = :tenant_id
        AND r.source_entity_id = :entity_id
        AND r.lifecycle_state = 'TRUSTED'
    """
    
    params = {"tenant_id": tenant_id, "entity_id": entity_id}
    
    if rel_type:
        query += " AND r.relationship_type = :rel_type"
        params["rel_type"] = rel_type
    
    query += " ORDER BY COALESCE(r.valid_from, '1900-01-01') ASC"
    
    return session.execute(text(query), params).fetchall()
```

---

## 4. Test Suite

Create these test documents and questions. You pass when 16/20 are correct.

### Test Documents

**Document 1: Career History (temporal complexity)**
```
SALEH HAMED - CAREER HISTORY

Emirates Nuclear Energy Corporation (ENEC)
- Systems Engineer (August 2003 - September 2008)
- Manager, Systems Design & Strategic Planning (September 2008 - December 2012)
- Director, Enterprise Support Services (January 2013 - December 2015)
- Executive Director, Operations (January 2016 - August 2022)

Department of Government Enablement (DGE)
- Executive Director, Cloud & Infrastructure (September 2022 - August 2025)

ADQ - QData
- Head of QData (September 2025 - Present)
```

**Document 2: Investment Portfolio (multiple instances)**
```
HORIZON VENTURES - PORTFOLIO

Series A Investments:
- TechStart Inc (March 2020, $2M) - AI/ML startup
- GreenEnergy Co (June 2020, $1.5M) - Clean energy
- HealthFirst (September 2020, $3M) - Healthcare tech

Series B Investments:
- TechStart Inc (January 2022, $8M) - Follow-on investment
- DataFlow Systems (March 2022, $5M) - Data infrastructure

Exited:
- CloudNine (invested March 2019, exited December 2021) - 3x return
```

**Document 3: Project Team (same relationship, different contexts)**
```
PROJECT PHOENIX - TEAM STRUCTURE

Phase 1 (Jan 2024 - June 2024):
- Project Lead: Sarah Chen
- Tech Lead: Marcus Johnson
- Team: Alice Wong, Bob Smith, Carol Davis

Phase 2 (July 2024 - Present):
- Project Lead: Marcus Johnson (promoted from Tech Lead)
- Tech Lead: Alice Wong (promoted)
- Team: Bob Smith, Carol Davis, David Lee, Emma Wilson
```

**Document 4: Board Positions (overlapping tenures)**
```
CORPORATE GOVERNANCE

James Morrison - Board Positions:
- Acme Corp: Board Member (2018-2021), Chairman (2021-present)
- Beta Industries: Board Member (2019-2022)
- Gamma Holdings: Advisory Board (2020-present)

Note: Morrison resigned from Beta Industries to avoid conflict of interest 
when Acme Corp acquired a competitor of Beta Industries in early 2022.
```

**Document 5: Research Collaboration (event context)**
```
FEDERATED LEARNING RESEARCH COLLABORATION

Initial Paper (NeurIPS 2023):
- Authors: Dr. Lisa Park, Dr. James Chen, Dr. Amir Hassan
- Institution: Stanford AI Lab

Follow-up Paper (ICML 2024):
- Authors: Dr. Lisa Park, Dr. James Chen, Dr. Sarah Miller
- Institution: Stanford AI Lab + MIT CSAIL
- Note: Dr. Hassan moved to industry; Dr. Miller joined from MIT

Dr. Lisa Park served as corresponding author for both papers.
```

### Test Questions

**Temporal Questions (1-5):**
1. "What was Saleh's role at ENEC in 2010?" → Manager, Systems Design & Strategic Planning
2. "How many positions has Saleh held total?" → 6 positions
3. "When did Saleh become Head of QData?" → September 2025
4. "What positions has Saleh held since 2020?" → Executive Director at ENEC (until Aug 2022), Executive Director at DGE (Sep 2022-Aug 2025), Head of QData (Sep 2025-present)
5. "How long was Saleh at ENEC?" → Approximately 19 years (2003-2022)

**Multiple Instance Questions (6-10):**
6. "How many times has Horizon invested in TechStart?" → 2 times (Series A in 2020, Series B in 2022)
7. "What's Horizon's total investment in TechStart?" → $10M ($2M + $8M)
8. "Which investments has Horizon exited?" → CloudNine (invested March 2019, exited December 2021)
9. "How many active investments does Horizon have?" → 5 (TechStart, GreenEnergy, HealthFirst, DataFlow, excluding exited CloudNine)
10. "When did Horizon first invest in the AI/ML sector?" → March 2020 (TechStart)

**Context Differentiation Questions (11-15):**
11. "Who leads Project Phoenix now?" → Marcus Johnson (since July 2024)
12. "Who was the original Project Phoenix lead?" → Sarah Chen (Phase 1)
13. "Who has been promoted within Project Phoenix?" → Marcus Johnson (to Project Lead) and Alice Wong (to Tech Lead)
14. "How many people are currently on Project Phoenix?" → 6 (Marcus, Alice, Bob, Carol, David, Emma)
15. "Who joined Project Phoenix in Phase 2?" → David Lee and Emma Wilson

**Provenance/Event Questions (16-20):**
16. "Why did Morrison leave Beta Industries?" → To avoid conflict of interest when Acme Corp acquired a competitor of Beta Industries
17. "How many board positions does Morrison currently hold?" → 2 (Acme Corp Chairman, Gamma Holdings Advisory)
18. "Who was the corresponding author on the federated learning papers?" → Dr. Lisa Park
19. "Why isn't Dr. Hassan on the second paper?" → He moved to industry
20. "Which institutions collaborated on the ICML 2024 paper?" → Stanford AI Lab and MIT CSAIL

### Test Runner

```python
# tests/integration/stage2_context_test.py

import pytest
from context_foundry import ContextFoundry

TEST_CASES = [
    # (question, expected_answer_contains, category)
    ("What was Saleh's role at ENEC in 2010?", "Manager", "temporal"),
    ("How many positions has Saleh held total?", "6", "temporal"),
    ("When did Saleh become Head of QData?", "2025", "temporal"),
    # ... all 20 questions
]

@pytest.fixture
def cf_instance():
    """Set up CF with test documents."""
    cf = ContextFoundry(tenant_id="test")
    cf.ingest_document("test_docs/career_history.md")
    cf.ingest_document("test_docs/investment_portfolio.md")
    cf.ingest_document("test_docs/project_team.md")
    cf.ingest_document("test_docs/board_positions.md")
    cf.ingest_document("test_docs/research_collaboration.md")
    return cf

@pytest.mark.parametrize("question,expected,category", TEST_CASES)
def test_contextual_question(cf_instance, question, expected, category):
    """Test that contextual questions are answered correctly."""
    result = cf_instance.query(question)
    
    # Log for debugging
    print(f"\nQuestion: {question}")
    print(f"Expected to contain: {expected}")
    print(f"Got: {result['answer']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Used context: {result.get('used_context_fields', [])}")
    
    assert expected.lower() in result['answer'].lower(), \
        f"Expected '{expected}' in answer, got: {result['answer']}"

def test_pass_rate():
    """Verify 80% pass rate (16/20)."""
    results = run_all_tests()
    passed = sum(1 for r in results if r['passed'])
    assert passed >= 16, f"Only {passed}/20 passed, need 16"
```

---

## 5. Verification Checklist

Before declaring Stage 2 complete:

```
[ ] Schema: relationships table has context fields
[ ] Schema: Indexes on temporal fields exist
[ ] Extraction: Prompt captures temporal, provenance, event_context
[ ] Extraction: Context fields are saved to database
[ ] Retrieval: Context Bundle includes relationship context
[ ] Reasoning: LLM prompt uses context for answering
[ ] Temporal: Can query "what was X at time Y"
[ ] Temporal: Can get timeline of relationships
[ ] Test: All 5 test documents ingested
[ ] Test: 16/20 questions answered correctly
[ ] Test: Answers use context fields, not document fallback
```

---

## 6. What NOT To Do

1. **Don't fall back to documents** — The answer should come from relationship context, not re-reading documents at query time

2. **Don't hardcode question patterns** — The same code should handle all 20 questions

3. **Don't skip context extraction** — Every relationship needs temporal/provenance populated (even if null)

4. **Don't ignore confidence** — Low-confidence relationships should be flagged

5. **Don't break existing functionality** — Stage 1 capabilities must still work

---

## 7. When You're Done

Run the test suite:
```bash
python -m pytest tests/integration/stage2_context_test.py -v
```

If 16/20 pass:
1. Document what context fields are populated
2. Show example Context Bundle with context
3. Show example answer that uses temporal/provenance
4. Report any questions that failed and why

We'll review together and decide if Stage 2 is complete.

---

## 8. Questions?

If anything is unclear, ask. The goal is concrete: **prove that context-attached relationships answer questions that bare triples cannot.**

The test suite is the judge. 16/20 correct = Stage 2 complete.
