"""
Unit tests for Gardener Learning Processor.
Part 1.3 of MVP Verification Test Suite.
"""

import pytest
from uuid import uuid4
from sqlalchemy import text
from src.context_foundry.models.schema import get_session
from src.context_foundry.agents.learning_ticket_agent import LearningTicketAgent
from src.context_foundry.agents.gardener_learning import GardenerLearningProcessor


class TestGardenerLearningProcessor:
    """Unit tests for the gardener learning processor."""
    
    @pytest.fixture
    def setup(self):
        """Create agents with fresh tenant"""
        session = get_session()
        tenant_id = str(uuid4())
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        ticket_agent = LearningTicketAgent(session=session, tenant_id=tenant_id)
        processor = GardenerLearningProcessor(session=session, tenant_id=tenant_id)
        yield ticket_agent, processor, session, tenant_id
        session.execute(text("DELETE FROM learning_tickets WHERE tenant_id = :tid"), {'tid': tenant_id})
        session.commit()
        session.close()
    
    def test_process_pending_tickets(self, setup):
        """Processor should handle pending tickets."""
        ticket_agent, processor, session, tenant_id = setup
        
        gaps = [{'type': 'missing_entity', 'entity_name': 'Test Person', 'severity': 0.8}]
        ticket_ids = ticket_agent.create_tickets_from_gaps(gaps)
        
        results = processor.process_pending_tickets(max_tickets=10)
        
        assert len(results) >= 1
        assert results[0]["ticket_id"] == ticket_ids[0]
        assert results[0]["action"] in ["extracted", "not_found", "no_sources", "ignored", "error"]
    
    def test_resolution_payload_structure(self, setup):
        """Resolution should have required fields for audit."""
        ticket_agent, processor, session, tenant_id = setup
        
        gaps = [{'type': 'sparse_relationships', 'entity_name': 'Test Entity', 'severity': 0.6}]
        ticket_agent.create_tickets_from_gaps(gaps)
        
        results = processor.process_pending_tickets(max_tickets=1)
        
        result = results[0]
        assert "ticket_id" in result
        assert "action" in result
        assert "improved" in result
        assert "facts_added" in result
        assert "source_chunks_used" in result
    
    def test_ticket_status_updated_after_processing(self, setup):
        """Ticket status should be updated after processing."""
        ticket_agent, processor, session, tenant_id = setup
        
        gaps = [{'type': 'stale_data', 'entity_name': 'Old Company', 'severity': 0.5}]
        ticket_ids = ticket_agent.create_tickets_from_gaps(gaps)
        
        processor.process_pending_tickets(max_tickets=1)
        
        result = session.execute(
            text("SELECT status FROM learning_tickets WHERE id = :id"),
            {'id': ticket_ids[0]}
        ).fetchone()
        
        assert result.status in ["resolved", "ignored", "processing"]
    
    def test_no_source_data_resolution(self, setup):
        """When no source chunks exist, resolution should indicate this."""
        ticket_agent, processor, session, tenant_id = setup
        
        gaps = [{'type': 'missing_entity', 'entity_name': 'Completely Unknown Entity XYZ123', 'severity': 0.8}]
        ticket_agent.create_tickets_from_gaps(gaps)
        
        results = processor.process_pending_tickets(max_tickets=1)
        
        assert results[0]["action"] in ["no_sources", "not_found", "ignored", "error"]
        assert results[0]["improved"] == False


class TestProcessMultipleGapTypes:
    """Test processing different gap types."""
    
    @pytest.fixture
    def setup(self):
        """Create agents with fresh tenant"""
        session = get_session()
        tenant_id = str(uuid4())
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        ticket_agent = LearningTicketAgent(session=session, tenant_id=tenant_id)
        processor = GardenerLearningProcessor(session=session, tenant_id=tenant_id)
        yield ticket_agent, processor, session, tenant_id
        session.execute(text("DELETE FROM learning_tickets WHERE tenant_id = :tid"), {'tid': tenant_id})
        session.commit()
        session.close()
    
    def test_process_missing_entity(self, setup):
        """Process missing_entity gap type."""
        ticket_agent, processor, session, tenant_id = setup
        
        gaps = [{'type': 'missing_entity', 'entity_name': 'Missing Person', 'severity': 0.8}]
        ticket_agent.create_tickets_from_gaps(gaps)
        
        results = processor.process_pending_tickets(max_tickets=1)
        
        assert len(results) == 1
        assert "action" in results[0]
    
    def test_process_sparse_relationships(self, setup):
        """Process sparse_relationships gap type."""
        ticket_agent, processor, session, tenant_id = setup
        
        gaps = [{'type': 'sparse_relationships', 'entity_name': 'Sparse Entity', 'severity': 0.6}]
        ticket_agent.create_tickets_from_gaps(gaps)
        
        results = processor.process_pending_tickets(max_tickets=1)
        
        assert len(results) == 1
    
    def test_process_stale_data(self, setup):
        """Process stale_data gap type."""
        ticket_agent, processor, session, tenant_id = setup
        
        gaps = [{'type': 'stale_data', 'entity_name': 'Stale Entity', 'severity': 0.5}]
        ticket_agent.create_tickets_from_gaps(gaps)
        
        results = processor.process_pending_tickets(max_tickets=1)
        
        assert len(results) == 1
