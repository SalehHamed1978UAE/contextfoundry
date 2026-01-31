# Context Foundry: Stage 3 Implementation Spec

## For: Replit
## Goal: Prove the system learns from interaction
## Reference: CF_Foundational_Reference_v1.2.md

---

## 1. What You're Proving

**Hypothesis:** Queries that reveal gaps improve the World Model. The same question asked later gets a better answer.

**Current state:** Queries retrieve and reason, but don't improve the system.

**Target state:** Gaps detected during queries create "learning tickets" that the Gardener processes to improve the World Model.

---

## 2. Success Criteria

You're done when:

1. ✓ Sufficiency signals are computed for each query (coverage, freshness, source agreement)
2. ✓ Low-confidence answers generate learning tickets
3. ✓ Gardener processes learning tickets asynchronously
4. ✓ Re-asking a question after learning produces a better answer
5. ✓ **6/10 learning cycles show measurable improvement**

---

## 3. Core Concepts

### 3.1 Sufficiency Signals

Don't rely on LLM "vibes" to know if we have enough information. Compute explicit signals:

| Signal | Computation | Example |
|--------|-------------|---------|
| **Coverage** | (entities found) / (entities in query) | "Found 3 of 4 entities" = 0.75 |
| **Freshness** | Age of most relevant relationships | "Newest data is 2 years old" = low |
| **Source Agreement** | Do multiple sources agree? | "2 agree, 1 contradicts" = 0.67 |
| **Relationship Density** | Relationships per focal entity | "2 positions over 14 years" = sparse |

Combined into a **confidence score** (0-1).

### 3.2 Uncertainty Transparency

When confidence is low, don't hide it:

```
HIGH CONFIDENCE (>0.8):
  "Saleh has held 6 positions across 3 organizations."

LOW CONFIDENCE (<0.6):
  "Based on current knowledge, Saleh has held at least 4 positions. 
   Checking for completeness... [confidence: 0.55]"
   
AFTER ASYNC CHECK:
  "Update: Found 2 additional positions. Saleh has held 6 positions total."
```

### 3.3 Learning Tickets

Queries don't modify the World Model directly. They create tickets:

```python
LearningTicket:
  id: UUID
  tenant_id: UUID
  query_id: UUID
  gap_type: str           # "missing_entity", "sparse_relationships", "stale_data", "low_confidence"
  focal_entity_id: UUID   # Which entity is affected
  context: dict           # Details about the gap
  source_chunk_ids: list  # Which documents might have more info
  created_at: timestamp
  priority: float         # Based on gap severity and query frequency
  status: str             # "pending", "processing", "resolved", "ignored"
```

### 3.4 Gardener as Gatekeeper

The Gardener processes learning tickets asynchronously:

```
Learning Ticket Queue
        │
        ▼
┌─────────────────────────────────┐
│ GARDENER                        │
├─────────────────────────────────┤
│ 1. Priority sort                │
│    (multiple queries = higher)  │
│                                 │
│ 2. For each ticket:             │
│    - Re-extract from sources    │
│    - Validate new facts         │
│    - Add to STAGING             │
│    - Promote if high confidence │
│                                 │
│ 3. Mark ticket resolved/ignored │
└─────────────────────────────────┘
```

**Pattern detection:** If 3+ queries hit the same gap, priority increases significantly.

---

## 4. Implementation Tasks

### Task 1: Create Learning Tickets Table

```sql
CREATE TABLE IF NOT EXISTS learning_tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  query_id UUID,  -- Reference to the query that created this
  gap_type TEXT NOT NULL,  -- 'missing_entity', 'sparse_relationships', 'stale_data', 'low_confidence', 'source_conflict'
  focal_entity_id UUID REFERENCES entities(id),
  focal_entity_name TEXT,  -- Denormalized for easier processing
  relationship_type TEXT,  -- If gap is about specific relationship type
  context JSONB NOT NULL,  -- Details about the gap
  source_chunk_ids UUID[],  -- Documents that might have more info
  priority FLOAT DEFAULT 0.5,
  hit_count INT DEFAULT 1,  -- How many queries have hit this gap
  status TEXT DEFAULT 'pending',  -- 'pending', 'processing', 'resolved', 'ignored'
  resolution_notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);

-- Index for priority processing
CREATE INDEX idx_learning_tickets_priority 
ON learning_tickets (tenant_id, status, priority DESC);

-- Index for duplicate detection
CREATE INDEX idx_learning_tickets_gap 
ON learning_tickets (tenant_id, focal_entity_id, gap_type, relationship_type);

-- RLS
ALTER TABLE learning_tickets ENABLE ROW LEVEL SECURITY;

CREATE POLICY learning_tickets_tenant_isolation ON learning_tickets
  FOR ALL USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

### Task 2: Implement Sufficiency Signals

Create a module to compute sufficiency:

```python
# agents/sufficiency.py

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timedelta

@dataclass
class SufficiencySignals:
    coverage: float          # 0-1: entities found / entities in query
    freshness: float         # 0-1: how recent is the data
    source_agreement: float  # 0-1: do sources agree
    relationship_density: float  # 0-1: relationships per entity
    overall_confidence: float    # Weighted combination
    gaps_detected: List[dict]    # Specific gaps found

def compute_sufficiency(
    query_entities: List[str],
    found_entities: List[dict],
    relationships: List[dict],
    query_timestamp: datetime = None
) -> SufficiencySignals:
    """Compute explicit sufficiency signals for a query."""
    
    query_timestamp = query_timestamp or datetime.utcnow()
    
    # 1. Coverage: Did we find all entities mentioned?
    found_names = {e['name'].lower() for e in found_entities}
    query_names = {name.lower() for name in query_entities}
    if query_names:
        coverage = len(found_names & query_names) / len(query_names)
    else:
        coverage = 1.0 if found_entities else 0.0
    
    # 2. Freshness: How old is our data?
    if relationships:
        # Get most recent valid_from or updated_at
        dates = []
        for r in relationships:
            if r.get('valid_from'):
                dates.append(parse_date(r['valid_from']))
            if r.get('updated_at'):
                dates.append(parse_date(r['updated_at']))
        
        if dates:
            most_recent = max(dates)
            age_days = (query_timestamp - most_recent).days
            # Freshness decays: 0 days = 1.0, 365 days = 0.5, 730 days = 0.25
            freshness = max(0.1, 1.0 / (1 + age_days / 365))
        else:
            freshness = 0.5  # Unknown freshness
    else:
        freshness = 0.0  # No relationships = not fresh
    
    # 3. Source Agreement: Do multiple sources say the same thing?
    if relationships:
        # Group by (source, type, target) and check provenance diversity
        fact_sources = {}
        for r in relationships:
            key = (r.get('source_entity_id'), r.get('relationship_type'), r.get('target_entity_id'))
            if key not in fact_sources:
                fact_sources[key] = []
            if r.get('provenance_chunk_id'):
                fact_sources[key].append(r['provenance_chunk_id'])
        
        # More sources = higher agreement confidence
        avg_sources = sum(len(s) for s in fact_sources.values()) / len(fact_sources) if fact_sources else 0
        source_agreement = min(1.0, avg_sources / 2)  # 2+ sources = 1.0
    else:
        source_agreement = 0.0
    
    # 4. Relationship Density: Do entities have enough connections?
    if found_entities and relationships:
        density = len(relationships) / len(found_entities)
        # Normalize: 5+ relationships per entity = 1.0
        relationship_density = min(1.0, density / 5)
    else:
        relationship_density = 0.0
    
    # 5. Detect specific gaps
    gaps_detected = []
    
    # Missing entities
    missing_entities = query_names - found_names
    for entity in missing_entities:
        gaps_detected.append({
            'type': 'missing_entity',
            'entity_name': entity,
            'severity': 0.8
        })
    
    # Sparse relationships
    for entity in found_entities:
        entity_rels = [r for r in relationships 
                       if r.get('source_entity_id') == entity.get('id') 
                       or r.get('target_entity_id') == entity.get('id')]
        if len(entity_rels) < 2:
            gaps_detected.append({
                'type': 'sparse_relationships',
                'entity_id': entity.get('id'),
                'entity_name': entity.get('name'),
                'relationship_count': len(entity_rels),
                'severity': 0.6
            })
    
    # Stale data
    if freshness < 0.5:
        gaps_detected.append({
            'type': 'stale_data',
            'freshness_score': freshness,
            'severity': 0.5
        })
    
    # 6. Compute overall confidence
    overall_confidence = (
        coverage * 0.35 +
        freshness * 0.20 +
        source_agreement * 0.20 +
        relationship_density * 0.25
    )
    
    return SufficiencySignals(
        coverage=coverage,
        freshness=freshness,
        source_agreement=source_agreement,
        relationship_density=relationship_density,
        overall_confidence=overall_confidence,
        gaps_detected=gaps_detected
    )
```

### Task 3: Create Learning Tickets from Gaps

```python
# agents/learning_ticket_agent.py

from uuid import uuid4
from datetime import datetime
from typing import List, Optional
from sqlalchemy import text

class LearningTicketAgent:
    """Creates and manages learning tickets from query gaps."""
    
    def __init__(self, session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def create_tickets_from_gaps(
        self,
        gaps: List[dict],
        query_id: str = None,
        source_chunk_ids: List[str] = None
    ) -> List[str]:
        """Create learning tickets for detected gaps."""
        
        ticket_ids = []
        
        for gap in gaps:
            # Check for existing similar ticket
            existing = self._find_similar_ticket(gap)
            
            if existing:
                # Increment hit count and update priority
                self._increment_ticket_priority(existing['id'])
                ticket_ids.append(existing['id'])
            else:
                # Create new ticket
                ticket_id = self._create_ticket(gap, query_id, source_chunk_ids)
                ticket_ids.append(ticket_id)
        
        return ticket_ids
    
    def _find_similar_ticket(self, gap: dict) -> Optional[dict]:
        """Find an existing ticket for the same gap."""
        
        result = self.session.execute(
            text("""
                SELECT id, hit_count, priority 
                FROM learning_tickets
                WHERE tenant_id = :tenant_id
                AND gap_type = :gap_type
                AND status = 'pending'
                AND (
                    (focal_entity_id = :entity_id)
                    OR (focal_entity_name = :entity_name AND focal_entity_id IS NULL)
                )
                LIMIT 1
            """),
            {
                'tenant_id': self.tenant_id,
                'gap_type': gap['type'],
                'entity_id': gap.get('entity_id'),
                'entity_name': gap.get('entity_name')
            }
        ).fetchone()
        
        return dict(result._mapping) if result else None
    
    def _increment_ticket_priority(self, ticket_id: str):
        """Increment hit count and boost priority for existing ticket."""
        
        self.session.execute(
            text("""
                UPDATE learning_tickets
                SET hit_count = hit_count + 1,
                    priority = LEAST(1.0, priority + 0.1),
                    updated_at = NOW()
                WHERE id = :ticket_id
            """),
            {'ticket_id': ticket_id}
        )
        self.session.commit()
    
    def _create_ticket(
        self,
        gap: dict,
        query_id: str = None,
        source_chunk_ids: List[str] = None
    ) -> str:
        """Create a new learning ticket."""
        
        ticket_id = str(uuid4())
        
        # Calculate initial priority based on gap severity
        priority = gap.get('severity', 0.5)
        
        self.session.execute(
            text("""
                INSERT INTO learning_tickets (
                    id, tenant_id, query_id, gap_type,
                    focal_entity_id, focal_entity_name, relationship_type,
                    context, source_chunk_ids, priority, status
                ) VALUES (
                    :id, :tenant_id, :query_id, :gap_type,
                    :entity_id, :entity_name, :rel_type,
                    :context, :source_ids, :priority, 'pending'
                )
            """),
            {
                'id': ticket_id,
                'tenant_id': self.tenant_id,
                'query_id': query_id,
                'gap_type': gap['type'],
                'entity_id': gap.get('entity_id'),
                'entity_name': gap.get('entity_name'),
                'rel_type': gap.get('relationship_type'),
                'context': json.dumps(gap),
                'source_ids': source_chunk_ids,
                'priority': priority
            }
        )
        self.session.commit()
        
        return ticket_id
```

### Task 4: Update Query Flow with Sufficiency Check

Update the reasoning agent to compute sufficiency and create learning tickets:

```python
# In reasoning_agent.py or query handler

async def handle_query(query: str, tenant_id: str) -> QueryResponse:
    """Handle query with sufficiency checking and learning tickets."""
    
    # 1. Parse query and extract mentioned entities
    parsed = parse_query(query)
    query_entities = parsed['entities']
    
    # 2. Resolve entities in KG
    found_entities = resolve_entities(query_entities, tenant_id)
    
    # 3. Retrieve relationships with context
    relationships = get_relationships_for_entities(
        [e['id'] for e in found_entities], 
        tenant_id
    )
    
    # 4. Compute sufficiency signals
    sufficiency = compute_sufficiency(
        query_entities=query_entities,
        found_entities=found_entities,
        relationships=relationships
    )
    
    # 5. Build context bundle
    context_bundle = build_context_bundle(found_entities, relationships)
    
    # 6. Reason over context bundle
    answer = reason_over_bundle(context_bundle, query)
    
    # 7. Apply uncertainty transparency
    if sufficiency.overall_confidence < 0.6:
        # Qualify the answer
        answer = qualify_answer(answer, sufficiency)
        
        # Create learning tickets for gaps
        ticket_agent = LearningTicketAgent(session, tenant_id)
        ticket_ids = ticket_agent.create_tickets_from_gaps(
            gaps=sufficiency.gaps_detected,
            query_id=query_id,
            source_chunk_ids=get_relevant_chunks(query)
        )
        
        # Trigger async learning (don't wait)
        asyncio.create_task(process_learning_tickets_async(tenant_id))
    
    return QueryResponse(
        answer=answer,
        confidence=sufficiency.overall_confidence,
        signals=sufficiency,
        learning_tickets_created=len(sufficiency.gaps_detected) if sufficiency.overall_confidence < 0.6 else 0
    )


def qualify_answer(answer: str, sufficiency: SufficiencySignals) -> str:
    """Add qualification to low-confidence answers."""
    
    qualifiers = []
    
    if sufficiency.coverage < 0.8:
        qualifiers.append("based on partial information")
    
    if sufficiency.freshness < 0.5:
        qualifiers.append("data may be outdated")
    
    if sufficiency.relationship_density < 0.3:
        qualifiers.append("limited relationship data")
    
    if qualifiers:
        qualifier_text = ", ".join(qualifiers)
        return f"Based on current knowledge ({qualifier_text}): {answer}\n\n[Confidence: {sufficiency.overall_confidence:.0%}. Checking for completeness...]"
    
    return answer
```

### Task 5: Implement Gardener Learning Processor

```python
# agents/gardener_learning.py

class GardenerLearningProcessor:
    """Processes learning tickets to improve the World Model."""
    
    def __init__(self, session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.graph_builder = GraphBuilderAgent(session, tenant_id)
    
    async def process_pending_tickets(self, max_tickets: int = 10):
        """Process highest priority learning tickets."""
        
        # Get pending tickets, prioritized by hit_count and priority
        tickets = self.session.execute(
            text("""
                SELECT * FROM learning_tickets
                WHERE tenant_id = :tenant_id
                AND status = 'pending'
                ORDER BY (priority * hit_count) DESC
                LIMIT :limit
            """),
            {'tenant_id': self.tenant_id, 'limit': max_tickets}
        ).fetchall()
        
        results = []
        for ticket in tickets:
            result = await self._process_ticket(dict(ticket._mapping))
            results.append(result)
        
        return results
    
    async def _process_ticket(self, ticket: dict) -> dict:
        """Process a single learning ticket."""
        
        # Mark as processing
        self._update_ticket_status(ticket['id'], 'processing')
        
        try:
            if ticket['gap_type'] == 'missing_entity':
                result = await self._handle_missing_entity(ticket)
            elif ticket['gap_type'] == 'sparse_relationships':
                result = await self._handle_sparse_relationships(ticket)
            elif ticket['gap_type'] == 'stale_data':
                result = await self._handle_stale_data(ticket)
            else:
                result = {'action': 'ignored', 'reason': f"Unknown gap type: {ticket['gap_type']}"}
            
            # Mark as resolved
            self._update_ticket_status(
                ticket['id'], 
                'resolved' if result.get('improved') else 'ignored',
                result.get('notes')
            )
            
            return {'ticket_id': ticket['id'], **result}
            
        except Exception as e:
            self._update_ticket_status(ticket['id'], 'pending', f"Error: {str(e)}")
            raise
    
    async def _handle_missing_entity(self, ticket: dict) -> dict:
        """Try to extract a missing entity from source documents."""
        
        entity_name = ticket.get('focal_entity_name')
        source_chunks = ticket.get('source_chunk_ids', [])
        
        if not source_chunks:
            # Find chunks that might mention this entity
            source_chunks = self._find_chunks_mentioning(entity_name)
        
        if not source_chunks:
            return {
                'action': 'no_sources',
                'improved': False,
                'notes': f"No source documents found mentioning '{entity_name}'"
            }
        
        # Re-extract from source chunks with focus on the missing entity
        new_entities = []
        for chunk_id in source_chunks[:5]:  # Limit to 5 chunks
            chunk = self._get_chunk(chunk_id)
            if chunk:
                extracted = await self.graph_builder.extract_with_focus(
                    chunk['content'],
                    focus_entity=entity_name
                )
                new_entities.extend(extracted.get('entities', []))
        
        # Check if we found the entity
        found = any(
            e['name'].lower() == entity_name.lower() 
            for e in new_entities
        )
        
        return {
            'action': 'extracted' if found else 'not_found',
            'improved': found,
            'entities_added': len(new_entities),
            'notes': f"Found {len(new_entities)} entities, target entity {'found' if found else 'not found'}"
        }
    
    async def _handle_sparse_relationships(self, ticket: dict) -> dict:
        """Try to extract more relationships for an entity."""
        
        entity_id = ticket.get('focal_entity_id')
        entity_name = ticket.get('focal_entity_name')
        
        # Get current relationship count
        current_count = self._get_relationship_count(entity_id)
        
        # Find source chunks for this entity
        source_chunks = self._find_chunks_for_entity(entity_id)
        
        if not source_chunks:
            return {
                'action': 'no_sources',
                'improved': False,
                'notes': 'No source documents found for entity'
            }
        
        # Re-extract with relationship focus
        new_relationships = []
        for chunk_id in source_chunks[:5]:
            chunk = self._get_chunk(chunk_id)
            if chunk:
                extracted = await self.graph_builder.extract_relationships_for_entity(
                    chunk['content'],
                    entity_name=entity_name
                )
                new_relationships.extend(extracted.get('relationships', []))
        
        # Save new relationships to staging
        saved = 0
        for rel in new_relationships:
            if self._is_new_relationship(rel, entity_id):
                self._save_relationship(rel)
                saved += 1
        
        new_count = self._get_relationship_count(entity_id)
        
        return {
            'action': 'extracted',
            'improved': new_count > current_count,
            'relationships_before': current_count,
            'relationships_after': new_count,
            'relationships_added': saved,
            'notes': f"Added {saved} new relationships"
        }
    
    async def _handle_stale_data(self, ticket: dict) -> dict:
        """Flag stale data for review - may need new documents."""
        
        return {
            'action': 'flagged_for_review',
            'improved': False,
            'notes': 'Stale data detected. New documents may be needed.'
        }
    
    def _update_ticket_status(self, ticket_id: str, status: str, notes: str = None):
        """Update ticket status."""
        
        self.session.execute(
            text("""
                UPDATE learning_tickets
                SET status = :status,
                    resolution_notes = COALESCE(:notes, resolution_notes),
                    resolved_at = CASE WHEN :status IN ('resolved', 'ignored') THEN NOW() ELSE NULL END,
                    updated_at = NOW()
                WHERE id = :ticket_id
            """),
            {'ticket_id': ticket_id, 'status': status, 'notes': notes}
        )
        self.session.commit()
    
    # ... helper methods for _find_chunks_mentioning, _get_chunk, etc.
```

### Task 6: Create Test Suite

```python
# tests/integration/stage3_learning_test.py

import pytest
import asyncio
from context_foundry import ContextFoundry
from agents.gardener_learning import GardenerLearningProcessor

# Test documents - intentionally incomplete on first pass
TEST_DOC_INITIAL = """
COMPANY OVERVIEW

TechCorp was founded in 2015 by Jane Smith.
The company focuses on AI solutions.
"""

TEST_DOC_COMPLETE = """
COMPANY OVERVIEW

TechCorp was founded in 2015 by Jane Smith.
The company focuses on AI solutions.

LEADERSHIP TEAM

Jane Smith - CEO and Founder (2015-present)
Bob Johnson - CTO (2016-present)  
Alice Chen - CFO (2018-present)
David Park - VP Engineering (2019-2022)
Sarah Lee - VP Engineering (2022-present)

FUNDING HISTORY

Series A: $5M (2016) - led by Venture Capital Fund
Series B: $20M (2018) - led by Growth Partners
Series C: $50M (2021) - led by Mega Investments
"""

class TestStage3Learning:
    
    @pytest.fixture
    def cf_instance(self):
        """Set up CF with minimal initial data."""
        cf = ContextFoundry(tenant_id="test_learning")
        cf.ingest_document(TEST_DOC_INITIAL, doc_id="techcorp_overview")
        return cf
    
    def test_1_gap_detection(self, cf_instance):
        """Test that gaps are detected when knowledge is incomplete."""
        
        # Query about leadership when we only know about founder
        result = cf_instance.query("Who is the CTO of TechCorp?")
        
        assert result['confidence'] < 0.6, "Should have low confidence"
        assert any(g['type'] == 'missing_entity' for g in result.get('gaps', [])) or \
               any(g['type'] == 'sparse_relationships' for g in result.get('gaps', []))
        assert result.get('learning_tickets_created', 0) > 0
    
    def test_2_learning_ticket_created(self, cf_instance):
        """Test that learning tickets are created for gaps."""
        
        # Query that should create a ticket
        cf_instance.query("List all executives at TechCorp")
        
        # Check tickets exist
        tickets = cf_instance.get_learning_tickets(status='pending')
        assert len(tickets) > 0
        
        # Should have gap about sparse relationships
        gap_types = [t['gap_type'] for t in tickets]
        assert 'sparse_relationships' in gap_types or 'missing_entity' in gap_types
    
    def test_3_learning_improves_answers(self, cf_instance):
        """Test that learning actually improves answers."""
        
        # First query - incomplete knowledge
        result1 = cf_instance.query("How many executives does TechCorp have?")
        answer1_count = extract_number(result1['answer'])
        confidence1 = result1['confidence']
        
        # Add more complete document
        cf_instance.ingest_document(TEST_DOC_COMPLETE, doc_id="techcorp_complete")
        
        # Process learning tickets (triggers re-extraction)
        cf_instance.process_learning_tickets()
        
        # Same query - should be better now
        result2 = cf_instance.query("How many executives does TechCorp have?")
        answer2_count = extract_number(result2['answer'])
        confidence2 = result2['confidence']
        
        # Assert improvement
        assert answer2_count > answer1_count or confidence2 > confidence1, \
            f"Expected improvement. Before: {answer1_count} ({confidence1:.0%}), After: {answer2_count} ({confidence2:.0%})"
    
    def test_4_ticket_priority_increases(self, cf_instance):
        """Test that repeated queries increase ticket priority."""
        
        # Query multiple times
        for _ in range(3):
            cf_instance.query("What is TechCorp's funding history?")
        
        tickets = cf_instance.get_learning_tickets(status='pending')
        
        # Should have a high-priority ticket due to repeated queries
        high_priority = [t for t in tickets if t['hit_count'] >= 3]
        assert len(high_priority) > 0, "Repeated queries should increase hit count"
    
    def test_5_async_learning(self, cf_instance):
        """Test that learning happens asynchronously."""
        
        # This is a timing test - query should return quickly even if learning is slow
        import time
        
        start = time.time()
        result = cf_instance.query("Who founded TechCorp and when?")
        query_time = time.time() - start
        
        # Query should be fast (< 5 seconds) even with learning triggered
        assert query_time < 5.0, f"Query took {query_time:.1f}s, should be < 5s"
        
        # Learning ticket should exist (created async)
        time.sleep(1)  # Give async task time to create ticket
        tickets = cf_instance.get_learning_tickets()
        # At least check it doesn't crash
    
    def test_6_sufficiency_signals_computed(self, cf_instance):
        """Test that sufficiency signals are returned."""
        
        result = cf_instance.query("Tell me about TechCorp leadership")
        
        assert 'signals' in result or 'sufficiency' in result
        signals = result.get('signals') or result.get('sufficiency')
        
        assert 'coverage' in signals
        assert 'freshness' in signals
        assert 'overall_confidence' in signals
        assert 0 <= signals['coverage'] <= 1
        assert 0 <= signals['freshness'] <= 1


# Helper
def extract_number(text: str) -> int:
    """Extract first number from text."""
    import re
    numbers = re.findall(r'\d+', text)
    return int(numbers[0]) if numbers else 0


# Test runner
TEST_CASES = [
    ("test_1_gap_detection", "Gap detection works"),
    ("test_2_learning_ticket_created", "Learning tickets created"),
    ("test_3_learning_improves_answers", "Learning improves answers"),
    ("test_4_ticket_priority_increases", "Priority increases with repeated queries"),
    ("test_5_async_learning", "Learning is async (doesn't block)"),
    ("test_6_sufficiency_signals_computed", "Sufficiency signals returned"),
]

def run_stage3_tests():
    """Run all Stage 3 tests and report results."""
    
    results = []
    cf = ContextFoundry(tenant_id="test_learning")
    cf.ingest_document(TEST_DOC_INITIAL, doc_id="techcorp_overview")
    
    for test_name, description in TEST_CASES:
        try:
            test_func = globals().get(test_name) or getattr(TestStage3Learning, test_name)
            test_func(cf)
            results.append((test_name, description, "PASS", None))
        except AssertionError as e:
            results.append((test_name, description, "FAIL", str(e)))
        except Exception as e:
            results.append((test_name, description, "ERROR", str(e)))
    
    # Summary
    passed = sum(1 for r in results if r[2] == "PASS")
    print(f"\n{'='*60}")
    print(f"Stage 3 Results: {passed}/{len(results)} ({100*passed/len(results):.0f}%)")
    print(f"{'='*60}")
    
    for name, desc, status, error in results:
        icon = "✓" if status == "PASS" else "✗"
        print(f"{icon} {desc}: {status}")
        if error:
            print(f"  → {error}")
    
    return passed >= 6  # 6/10 = 60% pass rate
```

---

## 5. Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Gap detection accuracy | >80% | Gaps detected when knowledge is provably incomplete |
| Learning ticket creation | 100% | Every detected gap creates a ticket |
| Ticket deduplication | Works | Repeated queries increment hit_count, not create duplicates |
| Learning effectiveness | 60%+ | 6/10 learning cycles show measurable improvement |
| Query latency | <3s | Learning doesn't block query response |
| Async completion | Works | Tickets are processed within 60s of creation |

---

## 6. Verification Checklist

```
[ ] Schema: learning_tickets table exists with all fields
[ ] Schema: RLS enabled on learning_tickets
[ ] Sufficiency: compute_sufficiency returns all signals
[ ] Sufficiency: Gaps detected for missing entities
[ ] Sufficiency: Gaps detected for sparse relationships
[ ] Tickets: Created when confidence < 0.6
[ ] Tickets: Deduplicated (hit_count increments)
[ ] Tickets: Priority increases with hits
[ ] Gardener: Processes pending tickets
[ ] Gardener: Re-extracts from source documents
[ ] Gardener: Marks tickets resolved/ignored
[ ] Query: Returns qualified answer when uncertain
[ ] Query: Doesn't block on learning
[ ] Test: 6/10 tests pass
```

---

## 7. What NOT To Do

1. **Don't modify World Model during query** — Learning tickets only, async processing

2. **Don't block queries for learning** — Return immediately with qualified answer

3. **Don't create duplicate tickets** — Increment hit_count on existing

4. **Don't learn from every query** — Only when confidence < threshold

5. **Don't auto-promote to TRUSTED** — Gardener reviews, may need human approval for high-stakes

6. **Don't hide uncertainty** — Users should see confidence and qualification

---

## 8. When You're Done

Run the test suite:
```bash
python -m pytest tests/integration/stage3_learning_test.py -v
```

If 6/10 pass:
1. Show example of gap detection → ticket creation → learning → improved answer
2. Show sufficiency signals for a sample query
3. Show ticket processing by Gardener
4. Report any tests that failed and why

We'll review together and decide if Stage 3 is complete.

---

## 9. Questions?

This is the most complex stage so far. The key insight:

> **Queries don't modify the World Model. They create learning tickets. The Gardener decides what to learn.**

This separation keeps query-time fast and learning-time thorough.

6/10 tests passing = Stage 3 complete.
