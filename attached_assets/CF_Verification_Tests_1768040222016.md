# Context Foundry: MVP Verification Test Suite

**Purpose:** Verify all components work end-to-end before declaring MVP complete  
**Date:** January 10, 2026

---

## Instructions for Replit

Run each section in order. Report PASS/FAIL with actual output.
Do not skip failures — document them all.

---

## PART 1: Unit Tests for Stage 3/4 Components

These components lack unit tests. Create and run them.

### 1.1 Sufficiency Signal Tests

```python
# tests/test_sufficiency.py

import pytest
from src.context_foundry.agents.sufficiency import compute_sufficiency, SufficiencySignals

class TestSufficiencyComputation:
    """Unit tests for sufficiency signal computation."""
    
    def test_perfect_sufficiency(self):
        """All signals high → confidence near 1.0"""
        # Setup: Entity with multiple sources, recent data, dense relationships
        signals = compute_sufficiency(
            entities_found=["entity_1"],
            entities_requested=["entity_1"],
            relationships=[
                {"source": "entity_1", "target": "entity_2", "source_chunks": ["c1", "c2"]},
                {"source": "entity_1", "target": "entity_3", "source_chunks": ["c1"]},
                {"source": "entity_1", "target": "entity_4", "source_chunks": ["c2", "c3"]},
                {"source": "entity_1", "target": "entity_5", "source_chunks": ["c1", "c2"]},
                {"source": "entity_1", "target": "entity_6", "source_chunks": ["c3"]},
            ],
            data_timestamps=["2026-01-01", "2026-01-05", "2026-01-08"]
        )
        
        assert signals.coverage == 1.0, f"Expected coverage 1.0, got {signals.coverage}"
        assert signals.freshness >= 0.8, f"Expected freshness >= 0.8, got {signals.freshness}"
        assert signals.overall_confidence >= 0.7, f"Expected confidence >= 0.7, got {signals.overall_confidence}"
    
    def test_zero_coverage(self):
        """No entities found → low confidence"""
        signals = compute_sufficiency(
            entities_found=[],
            entities_requested=["entity_1"],
            relationships=[],
            data_timestamps=[]
        )
        
        assert signals.coverage == 0.0
        assert signals.overall_confidence < 0.3
    
    def test_stale_data(self):
        """Old data → low freshness"""
        signals = compute_sufficiency(
            entities_found=["entity_1"],
            entities_requested=["entity_1"],
            relationships=[{"source": "entity_1", "target": "entity_2", "source_chunks": ["c1"]}],
            data_timestamps=["2020-01-01"]  # 6 years old
        )
        
        assert signals.freshness < 0.3, f"Expected freshness < 0.3 for stale data, got {signals.freshness}"
    
    def test_single_source_agreement(self):
        """Single source → source_agreement = 0"""
        signals = compute_sufficiency(
            entities_found=["entity_1"],
            entities_requested=["entity_1"],
            relationships=[
                {"source": "entity_1", "target": "entity_2", "source_chunks": ["c1"]},  # Only 1 source
            ],
            data_timestamps=["2026-01-01"]
        )
        
        assert signals.source_agreement == 0.0, "Single source should have 0 agreement"
    
    def test_multi_source_agreement(self):
        """Multiple sources agree → source_agreement > 0"""
        signals = compute_sufficiency(
            entities_found=["entity_1"],
            entities_requested=["entity_1"],
            relationships=[
                {"source": "entity_1", "target": "entity_2", "source_chunks": ["c1", "c2", "c3"]},
            ],
            data_timestamps=["2026-01-01"]
        )
        
        assert signals.source_agreement > 0.5, "Multiple sources should have higher agreement"
    
    def test_sparse_relationships(self):
        """Few relationships → low density"""
        signals = compute_sufficiency(
            entities_found=["e1", "e2", "e3", "e4", "e5"],  # 5 entities
            entities_requested=["e1"],
            relationships=[{"source": "e1", "target": "e2", "source_chunks": ["c1"]}],  # Only 1 rel
            data_timestamps=["2026-01-01"]
        )
        
        assert signals.relationship_density < 0.5, "Sparse relationships should have low density"


class TestGapDetection:
    """Test that gaps are correctly identified."""
    
    def test_missing_entity_gap(self):
        signals = compute_sufficiency(
            entities_found=[],
            entities_requested=["unknown_person"],
            relationships=[],
            data_timestamps=[]
        )
        
        assert "missing_entity" in signals.gaps_detected
    
    def test_sparse_relationships_gap(self):
        signals = compute_sufficiency(
            entities_found=["entity_1"],
            entities_requested=["entity_1"],
            relationships=[{"source": "entity_1", "target": "entity_2", "source_chunks": ["c1"]}],
            data_timestamps=["2026-01-01"]
        )
        
        assert "sparse_relationships" in signals.gaps_detected
    
    def test_stale_data_gap(self):
        signals = compute_sufficiency(
            entities_found=["entity_1"],
            entities_requested=["entity_1"],
            relationships=[{"source": "entity_1", "target": "entity_2", "source_chunks": ["c1"]}],
            data_timestamps=["2020-01-01"]
        )
        
        assert "stale_data" in signals.gaps_detected
```

**Run:** `pytest tests/test_sufficiency.py -v`

**Expected:** All tests pass

---

### 1.2 Learning Ticket Agent Tests

```python
# tests/test_learning_ticket_agent.py

import pytest
from uuid import uuid4
from src.context_foundry.agents.learning_ticket_agent import LearningTicketAgent

class TestLearningTicketCreation:
    """Unit tests for learning ticket creation."""
    
    @pytest.fixture
    def agent(self, db_session):
        tenant_id = str(uuid4())
        return LearningTicketAgent(session=db_session, tenant_id=tenant_id)
    
    def test_create_missing_entity_ticket(self, agent):
        """Create ticket for missing entity."""
        ticket = agent.create_ticket(
            gap_type="missing_entity",
            focal_entity="Unknown Person",
            query_text="Who is Unknown Person?"
        )
        
        assert ticket is not None
        assert ticket.gap_type == "missing_entity"
        assert ticket.focal_entity == "Unknown Person"
        assert ticket.status == "PENDING"
        assert ticket.hit_count == 1
        assert ticket.priority == 0.8  # Base severity for missing_entity
    
    def test_create_sparse_relationships_ticket(self, agent):
        """Create ticket for sparse relationships."""
        ticket = agent.create_ticket(
            gap_type="sparse_relationships",
            focal_entity="John Smith",
            query_text="What positions has John Smith held?"
        )
        
        assert ticket.gap_type == "sparse_relationships"
        assert ticket.priority == 0.6  # Base severity for sparse_relationships
    
    def test_create_stale_data_ticket(self, agent):
        """Create ticket for stale data."""
        ticket = agent.create_ticket(
            gap_type="stale_data",
            focal_entity="TechCorp",
            query_text="What is TechCorp's current revenue?"
        )
        
        assert ticket.gap_type == "stale_data"
        assert ticket.priority == 0.5  # Base severity for stale_data


class TestTicketDeduplication:
    """Test that duplicate tickets are handled correctly."""
    
    @pytest.fixture
    def agent(self, db_session):
        tenant_id = str(uuid4())
        return LearningTicketAgent(session=db_session, tenant_id=tenant_id)
    
    def test_duplicate_increments_hit_count(self, agent):
        """Same gap should increment hit_count, not create new ticket."""
        # Create first ticket
        ticket1 = agent.create_ticket(
            gap_type="missing_entity",
            focal_entity="Unknown Person",
            query_text="Who is Unknown Person?"
        )
        ticket1_id = ticket1.id
        
        # Create "duplicate" ticket
        ticket2 = agent.create_ticket(
            gap_type="missing_entity",
            focal_entity="Unknown Person",
            query_text="Tell me about Unknown Person"
        )
        
        # Should be same ticket with incremented hit_count
        assert ticket2.id == ticket1_id
        assert ticket2.hit_count == 2


class TestPriorityFormula:
    """Test priority calculation: priority = base_severity * (1 + 0.2 * hit_count)"""
    
    @pytest.fixture
    def agent(self, db_session):
        tenant_id = str(uuid4())
        return LearningTicketAgent(session=db_session, tenant_id=tenant_id)
    
    def test_priority_increases_with_hits(self, agent):
        """Priority should increase as hit_count increases."""
        ticket = agent.create_ticket(
            gap_type="missing_entity",
            focal_entity="Test Entity",
            query_text="Query 1"
        )
        
        initial_priority = ticket.priority
        assert initial_priority == 0.8  # Base for missing_entity
        
        # Simulate 4 more hits
        for i in range(4):
            ticket = agent.create_ticket(
                gap_type="missing_entity",
                focal_entity="Test Entity",
                query_text=f"Query {i+2}"
            )
        
        # After 5 hits: priority = 0.8 * (1 + 0.2 * 5) = 0.8 * 2.0 = 1.6 → capped at 1.0
        assert ticket.hit_count == 5
        assert ticket.priority == 1.0  # Capped
    
    def test_priority_capped_at_1(self, agent):
        """Priority should never exceed 1.0"""
        ticket = agent.create_ticket(
            gap_type="missing_entity",
            focal_entity="Test Entity",
            query_text="Query"
        )
        
        # Simulate 100 hits
        for i in range(100):
            ticket = agent.create_ticket(
                gap_type="missing_entity",
                focal_entity="Test Entity",
                query_text=f"Query {i}"
            )
        
        assert ticket.priority <= 1.0
```

**Run:** `pytest tests/test_learning_ticket_agent.py -v`

**Expected:** All tests pass

---

### 1.3 Gardener Learning Processor Tests

```python
# tests/test_gardener_learning.py

import pytest
from uuid import uuid4
from src.context_foundry.agents.gardener_learning import GardenerLearningProcessor
from src.context_foundry.agents.learning_ticket_agent import LearningTicketAgent

class TestGardenerLearningProcessor:
    """Unit tests for the gardener learning processor."""
    
    @pytest.fixture
    def setup(self, db_session):
        tenant_id = str(uuid4())
        ticket_agent = LearningTicketAgent(session=db_session, tenant_id=tenant_id)
        processor = GardenerLearningProcessor(session=db_session, tenant_id=tenant_id)
        return ticket_agent, processor, tenant_id
    
    def test_process_pending_tickets(self, setup):
        """Processor should handle pending tickets."""
        ticket_agent, processor, tenant_id = setup
        
        # Create a ticket
        ticket = ticket_agent.create_ticket(
            gap_type="missing_entity",
            focal_entity="Test Person",
            query_text="Who is Test Person?"
        )
        
        # Process tickets
        results = processor.process_pending_tickets(limit=10)
        
        assert len(results) >= 1
        assert results[0]["ticket_id"] == str(ticket.id)
        assert results[0]["resolution"] in ["improved", "no_improvement", "no_source_data", "needs_human"]
    
    def test_resolution_payload_structure(self, setup):
        """Resolution should have required fields for audit."""
        ticket_agent, processor, tenant_id = setup
        
        ticket = ticket_agent.create_ticket(
            gap_type="sparse_relationships",
            focal_entity="Test Entity",
            query_text="What are Test Entity's relationships?"
        )
        
        results = processor.process_pending_tickets(limit=1)
        
        result = results[0]
        # Required fields per spec
        assert "ticket_id" in result
        assert "resolution" in result
        assert "facts_added" in result
        assert "lifecycle_states" in result
        assert "source_chunks_used" in result
    
    def test_ticket_marked_resolved_after_processing(self, setup):
        """Ticket status should be RESOLVED after processing."""
        ticket_agent, processor, tenant_id = setup
        
        ticket = ticket_agent.create_ticket(
            gap_type="stale_data",
            focal_entity="Old Company",
            query_text="What is Old Company's status?"
        )
        
        processor.process_pending_tickets(limit=1)
        
        # Refresh ticket from DB
        refreshed_ticket = ticket_agent.get_ticket(ticket.id)
        assert refreshed_ticket.status in ["RESOLVED", "IGNORED"]
    
    def test_no_source_data_resolution(self, setup):
        """When no source chunks exist, resolution should be 'no_source_data'."""
        ticket_agent, processor, tenant_id = setup
        
        # Create ticket for entity with no documents
        ticket = ticket_agent.create_ticket(
            gap_type="missing_entity",
            focal_entity="Completely Unknown Entity XYZ123",
            query_text="Who is Completely Unknown Entity XYZ123?"
        )
        
        results = processor.process_pending_tickets(limit=1)
        
        assert results[0]["resolution"] in ["no_source_data", "ignored"]
```

**Run:** `pytest tests/test_gardener_learning.py -v`

**Expected:** All tests pass

---

### 1.4 Entity Profile Generator Tests

```python
# tests/test_entity_profile_generator.py

import pytest
from uuid import uuid4
from src.context_foundry.agents.entity_profile_generator import EntityProfileGenerator

class TestEntityProfileGenerator:
    """Unit tests for entity profile generation."""
    
    @pytest.fixture
    def generator(self, db_session):
        tenant_id = str(uuid4())
        return EntityProfileGenerator(session=db_session, tenant_id=tenant_id)
    
    @pytest.fixture
    def seeded_data(self, db_session, generator):
        """Seed test data and return entity name."""
        # Ingest a test document
        from src.context_foundry.agents.graph_builder import GraphBuilderAgent
        
        tenant_id = generator.tenant_id
        builder = GraphBuilderAgent(session=db_session, tenant_id=tenant_id)
        
        builder.process_text(
            text="Jane Doe is CEO of Acme Corp since 2020. She previously worked at BigTech as VP of Engineering.",
            document_id="test_doc_1"
        )
        
        return "Jane Doe"
    
    def test_generate_profile_returns_dict(self, generator, seeded_data):
        """Profile should be a structured dict."""
        profile = generator.generate_profile(seeded_data)
        
        assert profile is not None
        assert isinstance(profile, dict)
        assert "entity_name" in profile
        assert "entity_type" in profile
        assert "relationships" in profile
        assert "sufficiency" in profile
    
    def test_profile_includes_relationships(self, generator, seeded_data):
        """Profile should include all relationships."""
        profile = generator.generate_profile(seeded_data)
        
        assert len(profile["relationships"]) >= 1
        
        rel = profile["relationships"][0]
        assert "type" in rel
        assert "target" in rel
    
    def test_profile_includes_sufficiency(self, generator, seeded_data):
        """Profile should include sufficiency signals."""
        profile = generator.generate_profile(seeded_data)
        
        sufficiency = profile["sufficiency"]
        assert "coverage" in sufficiency
        assert "freshness" in sufficiency
        assert "overall_confidence" in sufficiency
    
    def test_nonexistent_entity_returns_none(self, generator):
        """Non-existent entity should return None, not hallucinate."""
        profile = generator.generate_profile("Completely Fake Person XYZ999")
        
        assert profile is None
    
    def test_markdown_output(self, generator, seeded_data):
        """Markdown output should be well-formed."""
        markdown = generator.generate_profile_markdown(seeded_data)
        
        assert markdown is not None
        assert "# Jane Doe" in markdown or "Jane Doe" in markdown
        assert "Relationship" in markdown or "relationship" in markdown.lower()
```

**Run:** `pytest tests/test_entity_profile_generator.py -v`

**Expected:** All tests pass

---

## PART 2: Extraction Quality Fix

### 2.1 Add HAS_COMPENSATION Relationship Type

Update `config/domain_schema.yaml`:

```yaml
relationship_types:
  # ... existing types ...
  
  HAS_COMPENSATION:
    description: "Person has compensation/salary"
    valid_sources: [PERSON]
    valid_targets: [MONETARY_VALUE, CONCEPT]
    examples:
      - "John earns $200,000 annually"
      - "CEO compensation is $5M"
    
  EARNS:
    description: "Alternative for compensation relationships"
    valid_sources: [PERSON]
    valid_targets: [MONETARY_VALUE, CONCEPT]
```

### 2.2 Add Schema Validation to Extraction

```python
# Add to src/context_foundry/extraction/validation.py

def validate_relationship_target(rel_type: str, source_type: str, target_type: str) -> bool:
    """Validate that relationship connects appropriate entity types."""
    
    VALID_TARGETS = {
        "HELD_POSITION": ["JOB_TITLE", "ROLE"],
        "WORKS_AT": ["ORGANIZATION", "COMPANY"],
        "REPORTS_TO": ["PERSON"],
        "HAS_COMPENSATION": ["MONETARY_VALUE", "CONCEPT"],
        "MEMBER_OF": ["ORGANIZATION", "TEAM", "GROUP"],
        # ... add all relationship type constraints
    }
    
    if rel_type not in VALID_TARGETS:
        return True  # Unknown type, allow for now
    
    return target_type in VALID_TARGETS[rel_type]
```

### 2.3 Update Extraction Prompt

Add to the extraction prompt in `graph_builder.py`:

```
RELATIONSHIP TYPE RULES:
- HELD_POSITION: Source must be PERSON, Target must be JOB_TITLE (not ORGANIZATION)
- WORKS_AT / EMPLOYED_BY: Source must be PERSON, Target must be ORGANIZATION
- HAS_COMPENSATION / EARNS: Use for salary/compensation facts. Source is PERSON, Target is the amount.
- REPORTS_TO: Source and Target must both be PERSON

WRONG: John Smith --[HELD_POSITION]--> TechCorp (TechCorp is an ORG, not a job title)
RIGHT: John Smith --[HELD_POSITION]--> CTO
RIGHT: John Smith --[WORKS_AT]--> TechCorp

WRONG: Embedding salary as a qualifier on HELD_POSITION
RIGHT: John Smith --[HAS_COMPENSATION]--> $200,000
```

**Run:** Re-ingest "John Smith earns $200,000 annually" and verify:
- HAS_COMPENSATION relationship is created
- HELD_POSITION is NOT connected to ORGANIZATION

---

## PART 3: DTL Integration Verification

### 3.1 Verify DTL Is Wired In

```python
# scripts/verify_dtl_integration.py

"""Verify Decision Trace Layer is actually integrated."""

from sqlalchemy import create_engine, text
import os

def verify_dtl():
    engine = create_engine(os.environ["DATABASE_URL"])
    
    with engine.connect() as conn:
        # Check DTL tables exist
        tables = conn.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE '%decision%' OR table_name LIKE '%trace%' OR table_name LIKE '%precedent%'
        """)).fetchall()
        
        print("DTL Tables found:")
        for t in tables:
            print(f"  - {t[0]}")
        
        if not tables:
            print("❌ NO DTL TABLES FOUND")
            return False
        
        # Check if decisions are being logged
        decision_count = conn.execute(text("""
            SELECT COUNT(*) FROM decisions
        """)).scalar()
        
        print(f"\nDecisions logged: {decision_count}")
        
        if decision_count == 0:
            print("⚠️ WARNING: No decisions logged. DTL may not be integrated into query flow.")
        
        return True

if __name__ == "__main__":
    verify_dtl()
```

### 3.2 Verify DTL Logs During Query

```python
# scripts/test_dtl_logging.py

"""Run a query and verify it creates a DTL trace."""

from src.context_foundry.agents.query_pipeline import QueryPipeline
from sqlalchemy import create_engine, text
from uuid import uuid4
import os

def test_dtl_logging():
    tenant_id = str(uuid4())
    
    # Get decision count before
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        before_count = conn.execute(text("SELECT COUNT(*) FROM decisions")).scalar()
    
    # Run a query
    pipeline = QueryPipeline(tenant_id=tenant_id)
    result = pipeline.query("Who is John Smith?")
    
    # Get decision count after
    with engine.connect() as conn:
        after_count = conn.execute(text("SELECT COUNT(*) FROM decisions")).scalar()
    
    print(f"Decisions before: {before_count}")
    print(f"Decisions after: {after_count}")
    print(f"New decisions: {after_count - before_count}")
    
    if after_count > before_count:
        print("✅ DTL is logging decisions during queries")
    else:
        print("❌ DTL is NOT logging decisions. Integration may be missing.")

if __name__ == "__main__":
    test_dtl_logging()
```

**Expected:** Both scripts show DTL tables exist AND decisions are logged during queries.

---

## PART 4: Full End-to-End Test (Fresh Tenant)

### 4.1 Complete Pipeline Test

```python
# scripts/full_e2e_verification.py

"""
Complete end-to-end verification with fresh tenant.
Tests the entire flow: Ingest → Query → Learn → Query Again
"""

import os
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import all components
from src.context_foundry.agents.graph_builder import GraphBuilderAgent
from src.context_foundry.agents.query_pipeline import QueryPipeline
from src.context_foundry.agents.entity_profile_generator import EntityProfileGenerator
from src.context_foundry.agents.learning_ticket_agent import LearningTicketAgent
from src.context_foundry.agents.gardener_learning import GardenerLearningProcessor
from src.context_foundry.agents.sufficiency import compute_sufficiency

def run_full_e2e():
    # Setup
    engine = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=engine)
    session = Session()
    
    tenant_id = str(uuid4())
    print(f"=== FULL E2E TEST ===")
    print(f"Tenant ID: {tenant_id}")
    print()
    
    # Set tenant context
    session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
    
    results = {}
    
    # =========================================
    # STEP 1: Ingest Initial Document
    # =========================================
    print("STEP 1: Ingest Initial Document")
    print("-" * 40)
    
    builder = GraphBuilderAgent(session=session, tenant_id=tenant_id)
    doc1_result = builder.process_text(
        text="""
        Sarah Chen is the Chief Technology Officer at GlobalTech Inc since January 2022.
        She previously held the position of VP of Engineering at StartupCo from 2018 to 2021.
        Sarah reports to Michael Brown, the CEO of GlobalTech Inc.
        GlobalTech Inc is headquartered in San Francisco.
        """,
        document_id="doc_001"
    )
    
    print(f"  Entities created: {doc1_result.get('entities_created', 'unknown')}")
    print(f"  Relationships created: {doc1_result.get('relationships_created', 'unknown')}")
    results["step1_entities"] = doc1_result.get('entities_created', 0)
    print()
    
    # =========================================
    # STEP 2: Query - Answerable Question
    # =========================================
    print("STEP 2: Query - Answerable Question")
    print("-" * 40)
    
    pipeline = QueryPipeline(session=session, tenant_id=tenant_id)
    q1_result = pipeline.query("What is Sarah Chen's current position?")
    
    print(f"  Query: What is Sarah Chen's current position?")
    print(f"  Answer: {q1_result.get('answer', 'N/A')[:100]}...")
    print(f"  Confidence: {q1_result.get('confidence', 'N/A')}")
    results["step2_confidence"] = q1_result.get('confidence', 0)
    print()
    
    # =========================================
    # STEP 3: Query - Unanswerable Question (Should Create Ticket)
    # =========================================
    print("STEP 3: Query - Unanswerable Question")
    print("-" * 40)
    
    q2_result = pipeline.query("What is Sarah Chen's salary?")
    
    print(f"  Query: What is Sarah Chen's salary?")
    print(f"  Answer: {q2_result.get('answer', 'N/A')[:100]}...")
    print(f"  Confidence: {q2_result.get('confidence', 'N/A')}")
    print(f"  Gaps detected: {q2_result.get('gaps', [])}")
    results["step3_confidence"] = q2_result.get('confidence', 0)
    print()
    
    # =========================================
    # STEP 4: Verify Learning Ticket Created
    # =========================================
    print("STEP 4: Verify Learning Ticket Created")
    print("-" * 40)
    
    ticket_agent = LearningTicketAgent(session=session, tenant_id=tenant_id)
    tickets = ticket_agent.get_pending_tickets()
    
    print(f"  Pending tickets: {len(tickets)}")
    for t in tickets[:3]:
        print(f"    - {t.gap_type}: {t.focal_entity} (priority: {t.priority})")
    
    results["step4_tickets"] = len(tickets)
    print()
    
    # =========================================
    # STEP 5: Ask Same Question Again (Hit Count Should Increase)
    # =========================================
    print("STEP 5: Ask Same Question Again")
    print("-" * 40)
    
    q3_result = pipeline.query("What is Sarah Chen's salary?")
    
    tickets_after = ticket_agent.get_pending_tickets()
    salary_ticket = next((t for t in tickets_after if "salary" in t.focal_entity.lower() or t.gap_type == "missing_entity"), None)
    
    if salary_ticket:
        print(f"  Hit count: {salary_ticket.hit_count}")
        print(f"  Priority: {salary_ticket.priority}")
        results["step5_hit_count"] = salary_ticket.hit_count
    else:
        print("  ⚠️ Could not find salary-related ticket")
        results["step5_hit_count"] = 0
    print()
    
    # =========================================
    # STEP 6: Run Gardener
    # =========================================
    print("STEP 6: Run Gardener Learning Processor")
    print("-" * 40)
    
    processor = GardenerLearningProcessor(session=session, tenant_id=tenant_id)
    gardener_results = processor.process_pending_tickets(limit=10)
    
    print(f"  Tickets processed: {len(gardener_results)}")
    for r in gardener_results[:3]:
        print(f"    - {r['ticket_id'][:8]}...: {r['resolution']}")
    
    results["step6_processed"] = len(gardener_results)
    print()
    
    # =========================================
    # STEP 7: Ingest New Document (Salary Data)
    # =========================================
    print("STEP 7: Ingest New Document (Salary Data)")
    print("-" * 40)
    
    doc2_result = builder.process_text(
        text="""
        Sarah Chen's annual compensation at GlobalTech Inc is $450,000.
        This includes a base salary of $350,000 and a bonus of $100,000.
        """,
        document_id="doc_002"
    )
    
    print(f"  Entities created: {doc2_result.get('entities_created', 'unknown')}")
    print(f"  Relationships created: {doc2_result.get('relationships_created', 'unknown')}")
    results["step7_new_rels"] = doc2_result.get('relationships_created', 0)
    print()
    
    # =========================================
    # STEP 8: Query Again (Should Have Better Answer)
    # =========================================
    print("STEP 8: Query Again (Should Have Better Answer)")
    print("-" * 40)
    
    q4_result = pipeline.query("What is Sarah Chen's salary?")
    
    print(f"  Query: What is Sarah Chen's salary?")
    print(f"  Answer: {q4_result.get('answer', 'N/A')[:150]}...")
    print(f"  Confidence: {q4_result.get('confidence', 'N/A')}")
    results["step8_confidence"] = q4_result.get('confidence', 0)
    print()
    
    # =========================================
    # STEP 9: Entity Profile Generator
    # =========================================
    print("STEP 9: Entity Profile Generator")
    print("-" * 40)
    
    profile_gen = EntityProfileGenerator(session=session, tenant_id=tenant_id)
    profile = profile_gen.generate_profile("Sarah Chen")
    
    if profile:
        print(f"  Entity: {profile.get('entity_name')}")
        print(f"  Type: {profile.get('entity_type')}")
        print(f"  Relationships: {len(profile.get('relationships', []))}")
        print(f"  Confidence: {profile.get('sufficiency', {}).get('overall_confidence', 'N/A')}")
        results["step9_rels"] = len(profile.get('relationships', []))
    else:
        print("  ❌ Profile generation returned None")
        results["step9_rels"] = 0
    print()
    
    # =========================================
    # STEP 10: Multi-Tenant Isolation Check
    # =========================================
    print("STEP 10: Multi-Tenant Isolation Check")
    print("-" * 40)
    
    other_tenant_id = str(uuid4())
    other_profile_gen = EntityProfileGenerator(session=session, tenant_id=other_tenant_id)
    other_profile = other_profile_gen.generate_profile("Sarah Chen")
    
    if other_profile is None:
        print("  ✅ Sarah Chen NOT visible to other tenant (correct)")
        results["step10_isolated"] = True
    else:
        print("  ❌ Sarah Chen IS visible to other tenant (WRONG!)")
        results["step10_isolated"] = False
    print()
    
    # =========================================
    # SUMMARY
    # =========================================
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    checks = [
        ("Step 1: Ingestion", results.get("step1_entities", 0) > 0),
        ("Step 2: Answerable query confidence >= 0.4", results.get("step2_confidence", 0) >= 0.4),
        ("Step 3: Unanswerable query low confidence", results.get("step3_confidence", 0) < 0.5),
        ("Step 4: Learning tickets created", results.get("step4_tickets", 0) > 0),
        ("Step 5: Hit count increased", results.get("step5_hit_count", 0) >= 2),
        ("Step 6: Gardener processed tickets", results.get("step6_processed", 0) > 0),
        ("Step 7: New data ingested", results.get("step7_new_rels", 0) > 0),
        ("Step 8: Improved answer", results.get("step8_confidence", 0) > results.get("step3_confidence", 0)),
        ("Step 9: Profile generated", results.get("step9_rels", 0) > 0),
        ("Step 10: Tenant isolation", results.get("step10_isolated", False)),
    ]
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    for name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print()
    print(f"RESULT: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 FULL E2E VERIFICATION PASSED")
    else:
        print("⚠️ SOME CHECKS FAILED - Review above")
    
    session.close()
    return passed == total

if __name__ == "__main__":
    success = run_full_e2e()
    exit(0 if success else 1)
```

**Run:** `python scripts/full_e2e_verification.py`

**Expected:** 10/10 checks pass

---

## PART 5: Summary Checklist

After running all tests, report:

| Test Suite | Pass/Fail | Notes |
|------------|-----------|-------|
| **1.1** Sufficiency Unit Tests | | |
| **1.2** Learning Ticket Unit Tests | | |
| **1.3** Gardener Learning Unit Tests | | |
| **1.4** Entity Profile Unit Tests | | |
| **2.1** HAS_COMPENSATION added | | |
| **2.2** Schema validation added | | |
| **2.3** Extraction prompt updated | | |
| **3.1** DTL tables exist | | |
| **3.2** DTL logs during query | | |
| **4.1** Full E2E (10/10) | | |

**MVP is verified when all rows show PASS.**
