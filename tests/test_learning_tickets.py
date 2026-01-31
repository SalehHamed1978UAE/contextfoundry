"""
Unit tests for Learning Ticket Agent.
Part 1.2 of MVP Verification Test Suite.
"""

import pytest
from uuid import uuid4
from sqlalchemy import text
from src.context_foundry.models.schema import get_session
from src.context_foundry.agents.learning_ticket_agent import LearningTicketAgent, BASE_SEVERITY


class TestLearningTicketCreation:
    """Unit tests for learning ticket creation."""
    
    @pytest.fixture
    def setup(self):
        """Create agent with fresh tenant"""
        session = get_session()
        tenant_id = str(uuid4())
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        agent = LearningTicketAgent(session=session, tenant_id=tenant_id)
        yield agent, session, tenant_id
        session.execute(text("DELETE FROM learning_tickets WHERE tenant_id = :tid"), {'tid': tenant_id})
        session.commit()
        session.close()
    
    def test_create_missing_entity_ticket(self, setup):
        """Create ticket for missing entity."""
        agent, session, tenant_id = setup
        
        gaps = [{'type': 'missing_entity', 'entity_name': 'Unknown Person', 'severity': 0.8}]
        ticket_ids = agent.create_tickets_from_gaps(gaps)
        
        assert len(ticket_ids) == 1
        
        result = session.execute(
            text("SELECT * FROM learning_tickets WHERE id = :id"),
            {'id': ticket_ids[0]}
        ).fetchone()
        
        assert result is not None
        assert result.gap_type == 'missing_entity'
        assert result.focal_entity_name == 'Unknown Person'
        assert result.status == 'pending'
        assert result.hit_count == 1
    
    def test_create_sparse_relationships_ticket(self, setup):
        """Create ticket for sparse relationships."""
        agent, session, tenant_id = setup
        
        gaps = [{'type': 'sparse_relationships', 'entity_name': 'John Smith', 'severity': 0.6}]
        ticket_ids = agent.create_tickets_from_gaps(gaps)
        
        assert len(ticket_ids) == 1
        
        result = session.execute(
            text("SELECT * FROM learning_tickets WHERE id = :id"),
            {'id': ticket_ids[0]}
        ).fetchone()
        
        assert result.gap_type == 'sparse_relationships'
    
    def test_create_stale_data_ticket(self, setup):
        """Create ticket for stale data."""
        agent, session, tenant_id = setup
        
        gaps = [{'type': 'stale_data', 'entity_name': 'TechCorp', 'severity': 0.5}]
        ticket_ids = agent.create_tickets_from_gaps(gaps)
        
        assert len(ticket_ids) == 1
        
        result = session.execute(
            text("SELECT * FROM learning_tickets WHERE id = :id"),
            {'id': ticket_ids[0]}
        ).fetchone()
        
        assert result.gap_type == 'stale_data'


class TestTicketDeduplication:
    """Test that duplicate tickets are handled correctly."""
    
    @pytest.fixture
    def setup(self):
        """Create agent with fresh tenant"""
        session = get_session()
        tenant_id = str(uuid4())
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        agent = LearningTicketAgent(session=session, tenant_id=tenant_id)
        yield agent, session, tenant_id
        session.execute(text("DELETE FROM learning_tickets WHERE tenant_id = :tid"), {'tid': tenant_id})
        session.commit()
        session.close()
    
    def test_duplicate_increments_hit_count(self, setup):
        """Same gap should increment hit_count, not create new ticket."""
        agent, session, tenant_id = setup
        
        gaps = [{'type': 'missing_entity', 'entity_name': 'Unknown Person', 'severity': 0.8}]
        
        ticket_ids_1 = agent.create_tickets_from_gaps(gaps)
        ticket_ids_2 = agent.create_tickets_from_gaps(gaps)
        
        assert str(ticket_ids_1[0]) == str(ticket_ids_2[0]), "Should return same ticket ID"
        
        result = session.execute(
            text("SELECT hit_count FROM learning_tickets WHERE id = :id"),
            {'id': ticket_ids_1[0]}
        ).fetchone()
        
        assert result.hit_count == 2


class TestPriorityFormula:
    """Test priority calculation: priority = base_severity * (1 + 0.2 * hit_count)"""
    
    @pytest.fixture
    def setup(self):
        """Create agent with fresh tenant"""
        session = get_session()
        tenant_id = str(uuid4())
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        agent = LearningTicketAgent(session=session, tenant_id=tenant_id)
        yield agent, session, tenant_id
        session.execute(text("DELETE FROM learning_tickets WHERE tenant_id = :tid"), {'tid': tenant_id})
        session.commit()
        session.close()
    
    def test_initial_priority(self, setup):
        """Initial priority should be base_severity * 1.2 (for hit_count=1)."""
        agent, session, tenant_id = setup
        
        gaps = [{'type': 'missing_entity', 'entity_name': 'Test Entity', 'severity': 0.8}]
        ticket_ids = agent.create_tickets_from_gaps(gaps)
        
        result = session.execute(
            text("SELECT priority FROM learning_tickets WHERE id = :id"),
            {'id': ticket_ids[0]}
        ).fetchone()
        
        expected_priority = 0.8 * (1 + 0.2 * 1)  # 0.8 * 1.2 = 0.96
        assert abs(result.priority - expected_priority) < 0.01, f"Expected {expected_priority}, got {result.priority}"
    
    def test_priority_increases_with_hits(self, setup):
        """Priority should increase as hit_count increases."""
        agent, session, tenant_id = setup
        
        gaps = [{'type': 'missing_entity', 'entity_name': 'Test Entity', 'severity': 0.8}]
        
        for i in range(5):
            ticket_ids = agent.create_tickets_from_gaps(gaps)
        
        result = session.execute(
            text("SELECT hit_count, priority FROM learning_tickets WHERE id = :id"),
            {'id': ticket_ids[0]}
        ).fetchone()
        
        assert result.hit_count == 5
        expected = 0.8 * (1 + 0.2 * 5)  # 0.8 * 2.0 = 1.6 -> capped at 1.0
        assert result.priority <= 1.0
    
    def test_priority_capped_at_1(self, setup):
        """Priority should never exceed 1.0"""
        agent, session, tenant_id = setup
        
        gaps = [{'type': 'missing_entity', 'entity_name': 'Test Entity', 'severity': 0.8}]
        
        for i in range(20):
            ticket_ids = agent.create_tickets_from_gaps(gaps)
        
        result = session.execute(
            text("SELECT priority FROM learning_tickets WHERE id = :id"),
            {'id': ticket_ids[0]}
        ).fetchone()
        
        assert result.priority <= 1.0


class TestGetPendingTickets:
    """Test retrieving pending tickets."""
    
    @pytest.fixture
    def setup(self):
        """Create agent with fresh tenant"""
        session = get_session()
        tenant_id = str(uuid4())
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        agent = LearningTicketAgent(session=session, tenant_id=tenant_id)
        yield agent, session, tenant_id
        session.execute(text("DELETE FROM learning_tickets WHERE tenant_id = :tid"), {'tid': tenant_id})
        session.commit()
        session.close()
    
    def test_get_pending_tickets(self, setup):
        """Should retrieve pending tickets ordered by priority"""
        agent, session, tenant_id = setup
        
        agent.create_tickets_from_gaps([{'type': 'missing_entity', 'entity_name': 'Entity A', 'severity': 0.8}])
        agent.create_tickets_from_gaps([{'type': 'stale_data', 'entity_name': 'Entity B', 'severity': 0.5}])
        
        tickets = agent.get_pending_tickets(limit=10)
        
        assert len(tickets) >= 2
        assert all(t['status'] == 'pending' for t in tickets)
