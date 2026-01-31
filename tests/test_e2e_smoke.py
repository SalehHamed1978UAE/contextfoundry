"""
E2E Smoke Test for Context Foundry Full Workflow.

Validates the complete ingestion-to-learning pipeline:
1. Ingest a test document with entities and relationships
2. Trigger entity promotion (if applicable)
3. Query the system for ingested data
4. Verify learning tickets are created for knowledge gaps
5. Process the learning tickets

This test mocks external LLM calls and is self-contained with cleanup.
"""

import pytest
import json
from uuid import uuid4
from unittest.mock import patch, MagicMock
from sqlalchemy import text

from src.context_foundry.models.schema import get_session
from src.context_foundry.agents.graph_builder import GraphBuilderAgent
from src.context_foundry.agents.learning_ticket_agent import LearningTicketAgent
from src.context_foundry.agents.gardener_learning import GardenerLearningProcessor


TEST_DOCUMENT = """
Acme Corporation is a technology company founded in 2020.
John Smith is the CEO of Acme Corporation.
The Engineering Team is responsible for the Platform Service.
Platform Service depends on the User Database for data storage.
Sarah Chen works as a Senior Engineer at Acme Corporation.
"""

MOCK_ENTITIES_RESPONSE = json.dumps([
    {
        "type": "ORGANIZATION",
        "canonical_name": "Acme Corporation",
        "aliases": ["Acme"],
        "properties": {"founded": "2020"},
        "confidence": 0.95,
        "source_sentence": "Acme Corporation is a technology company founded in 2020."
    },
    {
        "type": "PERSON",
        "canonical_name": "John Smith",
        "aliases": [],
        "properties": {},
        "confidence": 0.92,
        "source_sentence": "John Smith is the CEO of Acme Corporation."
    },
    {
        "type": "JOB_TITLE",
        "canonical_name": "CEO",
        "aliases": ["Chief Executive Officer"],
        "properties": {},
        "confidence": 0.90,
        "source_sentence": "John Smith is the CEO of Acme Corporation."
    },
    {
        "type": "TEAM",
        "canonical_name": "Engineering Team",
        "aliases": [],
        "properties": {},
        "confidence": 0.88,
        "source_sentence": "The Engineering Team is responsible for the Platform Service."
    },
    {
        "type": "SERVICE",
        "canonical_name": "Platform Service",
        "aliases": [],
        "properties": {},
        "confidence": 0.90,
        "source_sentence": "The Engineering Team is responsible for the Platform Service."
    },
    {
        "type": "DATABASE",
        "canonical_name": "User Database",
        "aliases": [],
        "properties": {},
        "confidence": 0.85,
        "source_sentence": "Platform Service depends on the User Database for data storage."
    },
    {
        "type": "PERSON",
        "canonical_name": "Sarah Chen",
        "aliases": [],
        "properties": {},
        "confidence": 0.90,
        "source_sentence": "Sarah Chen works as a Senior Engineer at Acme Corporation."
    },
    {
        "type": "JOB_TITLE",
        "canonical_name": "Senior Engineer",
        "aliases": [],
        "properties": {},
        "confidence": 0.88,
        "source_sentence": "Sarah Chen works as a Senior Engineer at Acme Corporation."
    }
])

MOCK_RELATIONSHIPS_RESPONSE = json.dumps([
    {
        "type": "HELD_POSITION",
        "source_name": "John Smith",
        "target_name": "CEO",
        "properties": {},
        "confidence": 0.90,
        "source_sentence": "John Smith is the CEO of Acme Corporation.",
        "provenance_text": "John Smith is the CEO of Acme Corporation.",
        "description": "John Smith holds the CEO position",
        "valid_from": "2020",
        "valid_to": None,
        "event_context": "current leadership",
        "qualifiers": [{"type": "at_organization", "text": "Acme Corporation"}],
        "confidence_reasoning": "Explicit statement"
    },
    {
        "type": "WORKS_AT",
        "source_name": "John Smith",
        "target_name": "Acme Corporation",
        "properties": {},
        "confidence": 0.92,
        "source_sentence": "John Smith is the CEO of Acme Corporation.",
        "provenance_text": "John Smith is the CEO of Acme Corporation.",
        "description": "John Smith works at Acme Corporation",
        "valid_from": None,
        "valid_to": None,
        "event_context": "",
        "qualifiers": [],
        "confidence_reasoning": "Implied by CEO position"
    },
    {
        "type": "OWNS",
        "source_name": "Engineering Team",
        "target_name": "Platform Service",
        "properties": {},
        "confidence": 0.85,
        "source_sentence": "The Engineering Team is responsible for the Platform Service.",
        "provenance_text": "The Engineering Team is responsible for the Platform Service.",
        "description": "Engineering Team owns Platform Service",
        "valid_from": None,
        "valid_to": None,
        "event_context": "",
        "qualifiers": [],
        "confidence_reasoning": "Stated responsibility"
    },
    {
        "type": "DEPENDS_ON",
        "source_name": "Platform Service",
        "target_name": "User Database",
        "properties": {},
        "confidence": 0.88,
        "source_sentence": "Platform Service depends on the User Database for data storage.",
        "provenance_text": "Platform Service depends on the User Database for data storage.",
        "description": "Platform Service depends on User Database",
        "valid_from": None,
        "valid_to": None,
        "event_context": "",
        "qualifiers": [{"type": "purpose", "text": "data storage"}],
        "confidence_reasoning": "Explicit dependency statement"
    },
    {
        "type": "HELD_POSITION",
        "source_name": "Sarah Chen",
        "target_name": "Senior Engineer",
        "properties": {},
        "confidence": 0.88,
        "source_sentence": "Sarah Chen works as a Senior Engineer at Acme Corporation.",
        "provenance_text": "Sarah Chen works as a Senior Engineer at Acme Corporation.",
        "description": "Sarah Chen holds Senior Engineer position",
        "valid_from": None,
        "valid_to": None,
        "event_context": "",
        "qualifiers": [{"type": "at_organization", "text": "Acme Corporation"}],
        "confidence_reasoning": "Explicit statement"
    },
    {
        "type": "WORKS_AT",
        "source_name": "Sarah Chen",
        "target_name": "Acme Corporation",
        "properties": {},
        "confidence": 0.88,
        "source_sentence": "Sarah Chen works as a Senior Engineer at Acme Corporation.",
        "provenance_text": "Sarah Chen works as a Senior Engineer at Acme Corporation.",
        "description": "Sarah Chen works at Acme Corporation",
        "valid_from": None,
        "valid_to": None,
        "event_context": "",
        "qualifiers": [],
        "confidence_reasoning": "Explicit statement"
    }
])


def create_mock_openai_response(content: str):
    """Create a mock OpenAI API response."""
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


class TestE2ESmokeWorkflow:
    """End-to-end smoke test for the full Context Foundry workflow."""
    
    @pytest.fixture
    def setup(self):
        """Set up test environment with fresh tenant and mocked LLM."""
        session = get_session()
        tenant_id = str(uuid4())
        
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        session.commit()
        
        yield session, tenant_id
        
        try:
            session.execute(text("DELETE FROM relationships WHERE tenant_id = :tid"), {'tid': tenant_id})
            session.execute(text("DELETE FROM entities WHERE tenant_id = :tid"), {'tid': tenant_id})
            session.execute(text("DELETE FROM learning_tickets WHERE tenant_id = :tid"), {'tid': tenant_id})
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    
    def test_full_workflow_e2e(self, setup):
        """
        Test the complete ingestion → promotion → query → learning workflow.
        
        Steps:
        1. Ingest document with mocked LLM extraction
        2. Verify entities and relationships are in STAGING
        3. Manually promote to TRUSTED (simulating gardener pass)
        4. Query the ingested data
        5. Create learning tickets for gaps
        6. Process learning tickets
        """
        session, tenant_id = setup
        
        call_count = 0
        
        def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return create_mock_openai_response(MOCK_ENTITIES_RESPONSE)
            else:
                return create_mock_openai_response(MOCK_RELATIONSHIPS_RESPONSE)
        
        with patch('src.context_foundry.agents.graph_builder.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = mock_create
            mock_openai.return_value = mock_client
            
            agent = GraphBuilderAgent(session=session)
            result = agent.ingest_document(
                text=TEST_DOCUMENT,
                doc_type="INTERNAL_DOC",
                title="Test Document",
                tenant_id=tenant_id
            )
        
        assert result.entities_extracted > 0, "Should extract entities"
        assert result.relationships_extracted > 0, "Should extract relationships"
        assert result.staged == True, "Should stage extractions"
        
        entities = session.execute(
            text("""
                SELECT id, name, entity_type, lifecycle_state, confidence 
                FROM entities 
                WHERE tenant_id = :tid
            """),
            {'tid': tenant_id}
        ).fetchall()
        
        assert len(entities) >= 5, f"Expected at least 5 entities, got {len(entities)}"
        
        entity_names = [e.name for e in entities]
        assert "Acme Corporation" in entity_names, "Should have Acme Corporation entity"
        assert "John Smith" in entity_names, "Should have John Smith entity"
        
        for entity in entities:
            assert entity.lifecycle_state == "STAGING", "All entities should be in STAGING"
        
        relationships = session.execute(
            text("""
                SELECT id, relationship_type, source_id, target_id, lifecycle_state
                FROM relationships
                WHERE tenant_id = :tid
            """),
            {'tid': tenant_id}
        ).fetchall()
        
        assert len(relationships) >= 3, f"Expected at least 3 relationships, got {len(relationships)}"
        
        for rel in relationships:
            assert rel.lifecycle_state == "STAGING", "All relationships should be in STAGING"
        
        session.execute(
            text("""
                UPDATE entities 
                SET lifecycle_state = 'TRUSTED',
                    validation_status = 'VALID',
                    confidence = 0.90,
                    created_at = NOW() - INTERVAL '2 hours'
                WHERE tenant_id = :tid
            """),
            {'tid': tenant_id}
        )
        session.commit()
        
        promoted_entities = session.execute(
            text("""
                SELECT COUNT(*) as count 
                FROM entities 
                WHERE tenant_id = :tid AND lifecycle_state = 'TRUSTED'
            """),
            {'tid': tenant_id}
        ).fetchone()
        
        assert promoted_entities.count >= 5, "Entities should be promoted to TRUSTED"
        
        query_results = session.execute(
            text("""
                SELECT e.name, e.entity_type, e.confidence
                FROM entities e
                WHERE e.tenant_id = :tid
                AND e.lifecycle_state = 'TRUSTED'
                ORDER BY e.confidence DESC
            """),
            {'tid': tenant_id}
        ).fetchall()
        
        assert len(query_results) >= 5, "Should return trusted entities"
        
        found_ceo = False
        for row in query_results:
            if row.entity_type == "JOB_TITLE" and row.name == "CEO":
                found_ceo = True
                break
        assert found_ceo, "Should find CEO entity in query results"
        
        ticket_agent = LearningTicketAgent(session=session, tenant_id=tenant_id)
        
        gaps = [
            {
                'type': 'missing_entity',
                'entity_name': 'Unknown Department',
                'severity': 0.7
            },
            {
                'type': 'sparse_relationships',
                'entity_name': 'Sarah Chen',
                'severity': 0.6
            }
        ]
        
        ticket_ids = ticket_agent.create_tickets_from_gaps(gaps)
        
        assert len(ticket_ids) == 2, "Should create 2 learning tickets"
        
        tickets = session.execute(
            text("""
                SELECT id, gap_type, focal_entity_name, status, priority
                FROM learning_tickets
                WHERE tenant_id = :tid
                ORDER BY priority DESC
            """),
            {'tid': tenant_id}
        ).fetchall()
        
        assert len(tickets) >= 2, "Should have at least 2 tickets"
        
        gap_types = [t.gap_type for t in tickets]
        assert 'missing_entity' in gap_types, "Should have missing_entity ticket"
        assert 'sparse_relationships' in gap_types, "Should have sparse_relationships ticket"
        
        for ticket in tickets:
            assert ticket.status == 'pending', "New tickets should be pending"
            assert ticket.priority > 0, "Tickets should have positive priority"
        
        processor = GardenerLearningProcessor(session=session, tenant_id=tenant_id)
        
        results = processor.process_pending_tickets(max_tickets=10)
        
        assert len(results) >= 2, "Should process at least 2 tickets"
        
        for result in results:
            assert 'ticket_id' in result, "Result should have ticket_id"
            assert 'action' in result, "Result should have action"
            assert 'improved' in result, "Result should have improved flag"
            assert result['action'] in ['extracted', 'not_found', 'no_sources', 'flagged_for_review', 'ignored', 'error'], \
                f"Unexpected action: {result['action']}"
        
        processed_tickets = session.execute(
            text("""
                SELECT id, status
                FROM learning_tickets
                WHERE tenant_id = :tid
            """),
            {'tid': tenant_id}
        ).fetchall()
        
        for ticket in processed_tickets:
            assert ticket.status in ['resolved', 'ignored', 'processing'], \
                f"Ticket should be processed, got status: {ticket.status}"
    
    def test_ingestion_with_mock_llm(self, setup):
        """Test document ingestion creates correct entities and relationships."""
        session, tenant_id = setup
        
        call_count = 0
        
        def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return create_mock_openai_response(MOCK_ENTITIES_RESPONSE)
            else:
                return create_mock_openai_response(MOCK_RELATIONSHIPS_RESPONSE)
        
        with patch('src.context_foundry.agents.graph_builder.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = mock_create
            mock_openai.return_value = mock_client
            
            agent = GraphBuilderAgent(session=session)
            result = agent.ingest_document(
                text=TEST_DOCUMENT,
                doc_type="INTERNAL_DOC",
                title="Test Ingestion Doc",
                tenant_id=tenant_id
            )
        
        assert result.staged == True
        assert result.entities_extracted >= 5
        assert result.relationships_extracted >= 3
        
        entity_types = session.execute(
            text("""
                SELECT DISTINCT entity_type 
                FROM entities 
                WHERE tenant_id = :tid
            """),
            {'tid': tenant_id}
        ).fetchall()
        
        type_set = {e.entity_type for e in entity_types}
        assert 'ORGANIZATION' in type_set or 'PERSON' in type_set, "Should have basic entity types"
    
    def test_learning_ticket_priority_accumulation(self, setup):
        """Test that repeated gaps increase ticket priority."""
        session, tenant_id = setup
        
        ticket_agent = LearningTicketAgent(session=session, tenant_id=tenant_id)
        
        gap = {'type': 'missing_entity', 'entity_name': 'Repeated Gap Entity', 'severity': 0.8}
        
        ticket_ids_1 = ticket_agent.create_tickets_from_gaps([gap])
        ticket_ids_2 = ticket_agent.create_tickets_from_gaps([gap])
        ticket_ids_3 = ticket_agent.create_tickets_from_gaps([gap])
        
        assert str(ticket_ids_1[0]) == str(ticket_ids_2[0]) == str(ticket_ids_3[0]), \
            "Same gap should return same ticket ID"
        
        result = session.execute(
            text("""
                SELECT hit_count, priority 
                FROM learning_tickets 
                WHERE id = :id
            """),
            {'id': ticket_ids_1[0]}
        ).fetchone()
        
        assert result.hit_count == 3, "Hit count should be 3 after 3 submissions"
        assert result.priority > 0, "Priority should be positive"
        assert result.priority <= 1.0, "Priority should be capped at 1.0"
    
    def test_gardener_promotion_eligibility(self, setup):
        """Test that entities can become eligible for promotion."""
        session, tenant_id = setup
        
        call_count = 0
        
        def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return create_mock_openai_response(MOCK_ENTITIES_RESPONSE)
            else:
                return create_mock_openai_response(MOCK_RELATIONSHIPS_RESPONSE)
        
        with patch('src.context_foundry.agents.graph_builder.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = mock_create
            mock_openai.return_value = mock_client
            
            agent = GraphBuilderAgent(session=session)
            agent.ingest_document(
                text=TEST_DOCUMENT,
                doc_type="INTERNAL_DOC",
                title="Promotion Test Doc",
                tenant_id=tenant_id
            )
        
        staging_count = session.execute(
            text("""
                SELECT COUNT(*) as count 
                FROM entities 
                WHERE tenant_id = :tid AND lifecycle_state = 'STAGING'
            """),
            {'tid': tenant_id}
        ).fetchone()
        
        assert staging_count.count > 0, "Should have entities in STAGING"
        
        session.execute(
            text("""
                UPDATE entities 
                SET validation_status = 'VALID',
                    confidence = 0.90,
                    created_at = NOW() - INTERVAL '5 hours'
                WHERE tenant_id = :tid AND lifecycle_state = 'STAGING'
            """),
            {'tid': tenant_id}
        )
        session.commit()
        
        eligible_entities = session.execute(
            text("""
                SELECT name, entity_type, confidence, validation_status, created_at
                FROM entities
                WHERE tenant_id = :tid 
                AND lifecycle_state = 'STAGING'
                AND validation_status = 'VALID'
                AND confidence >= 0.70
                AND created_at < NOW() - INTERVAL '1 hour'
            """),
            {'tid': tenant_id}
        ).fetchall()
        
        assert len(eligible_entities) > 0, "Should have promotion-eligible entities"
        
        for entity in eligible_entities:
            assert entity.confidence >= 0.70, "Eligible entity should have sufficient confidence"
            assert entity.validation_status == 'VALID', "Eligible entity should be validated"


