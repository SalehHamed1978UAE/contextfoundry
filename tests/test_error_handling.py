"""
Negative/Error Handling Tests for Context Foundry.
Part of MVP Verification Test Suite.
"""

import pytest
from uuid import uuid4
from datetime import datetime
from sqlalchemy import text
from src.context_foundry.models.schema import get_session
from src.context_foundry.agents.sufficiency import compute_sufficiency
from src.context_foundry.agents.learning_ticket_agent import LearningTicketAgent


class TestEmptyInputHandling:
    """Tests for empty input scenarios."""
    
    def test_sufficiency_empty_query_entities(self):
        """Empty query entities should return zero coverage gracefully."""
        signals = compute_sufficiency(
            query_entities=[],
            found_entities=[{"id": "e1", "name": "Test"}],
            relationships=[],
            query_timestamp=datetime.utcnow()
        )
        assert signals.coverage == 0.0
        assert signals.overall_confidence == 0.0
    
    def test_sufficiency_empty_found_entities(self):
        """Empty found entities should return zero coverage gracefully."""
        signals = compute_sufficiency(
            query_entities=["Test Query"],
            found_entities=[],
            relationships=[],
            query_timestamp=datetime.utcnow()
        )
        assert signals.coverage == 0.0
        assert signals.overall_confidence < 0.3
    
    def test_sufficiency_all_empty(self):
        """All empty inputs should return zeros gracefully."""
        signals = compute_sufficiency(
            query_entities=[],
            found_entities=[],
            relationships=[],
            query_timestamp=datetime.utcnow()
        )
        assert signals.coverage == 0.0
        assert signals.freshness == 0.0
        assert signals.overall_confidence == 0.0


class TestInvalidInputHandling:
    """Tests for invalid input scenarios."""
    
    def test_sufficiency_none_query_timestamp(self):
        """None timestamp should use current time or handle gracefully."""
        try:
            signals = compute_sufficiency(
                query_entities=["Test"],
                found_entities=[{"id": "e1", "name": "Test"}],
                relationships=[],
                query_timestamp=None
            )
            assert signals is not None
        except (TypeError, ValueError) as e:
            pytest.fail(f"Should handle None timestamp gracefully, got: {e}")
    
    def test_sufficiency_malformed_entity(self):
        """Malformed entity dict should not crash."""
        try:
            signals = compute_sufficiency(
                query_entities=["Test"],
                found_entities=[{"missing_id": "e1"}],
                relationships=[],
                query_timestamp=datetime.utcnow()
            )
            assert signals is not None
        except KeyError as e:
            pytest.fail(f"Should handle malformed entity gracefully, got: {e}")
    
    def test_sufficiency_malformed_relationship(self):
        """Malformed relationship dict should not crash."""
        try:
            signals = compute_sufficiency(
                query_entities=["Test"],
                found_entities=[{"id": "e1", "name": "Test"}],
                relationships=[{"missing_source": "e1"}],
                query_timestamp=datetime.utcnow()
            )
            assert signals is not None
        except KeyError as e:
            pytest.fail(f"Should handle malformed relationship gracefully, got: {e}")


class TestTenantIsolation:
    """Tests for tenant isolation and security."""
    
    def test_none_tenant_id_warning(self):
        """None tenant_id should log warning, not crash."""
        session = get_session()
        try:
            agent = LearningTicketAgent(session=session, tenant_id=None)
            assert agent is not None
        except (TypeError, ValueError) as e:
            pytest.fail(f"Should handle None tenant_id with warning, got: {e}")
        finally:
            session.close()
    
    def test_invalid_uuid_tenant_id(self):
        """Invalid UUID tenant_id should fail gracefully with clear error."""
        session = get_session()
        try:
            agent = LearningTicketAgent(session=session, tenant_id="not-a-valid-uuid")
            gaps = [{'type': 'missing_entity', 'entity_name': 'Test', 'severity': 0.5}]
            agent.create_tickets_from_gaps(gaps)
            pytest.fail("Should have raised error for invalid UUID")
        except Exception as e:
            error_msg = str(e).lower()
            assert 'uuid' in error_msg or 'invalid' in error_msg or 'syntax' in error_msg, \
                f"Error should mention UUID issue: {e}"
        finally:
            session.close()


class TestDatabaseErrorHandling:
    """Tests for database error scenarios."""
    
    def test_create_ticket_rollback_on_error(self):
        """Failed ticket creation should rollback, not leave partial state."""
        session = get_session()
        tenant_id = str(uuid4())
        
        try:
            session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
            agent = LearningTicketAgent(session=session, tenant_id=tenant_id)
            
            initial_count = session.execute(
                text("SELECT COUNT(*) FROM learning_tickets WHERE tenant_id = :tid"),
                {'tid': tenant_id}
            ).scalar()
            
            try:
                agent.create_tickets_from_gaps([
                    {'type': 'valid_gap', 'entity_name': 'Test1', 'severity': 0.5},
                    {'type': None, 'entity_name': None, 'severity': 'invalid'},
                ])
            except Exception:
                session.rollback()
            
            final_count = session.execute(
                text("SELECT COUNT(*) FROM learning_tickets WHERE tenant_id = :tid"),
                {'tid': tenant_id}
            ).scalar()
            
            assert final_count == initial_count, "Partial state should be rolled back"
        finally:
            session.execute(text("DELETE FROM learning_tickets WHERE tenant_id = :tid"), {'tid': tenant_id})
            session.commit()
            session.close()


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_very_long_entity_name(self):
        """Very long entity name should be handled gracefully."""
        long_name = "A" * 10000
        signals = compute_sufficiency(
            query_entities=[long_name],
            found_entities=[{"id": "e1", "name": long_name}],
            relationships=[],
            query_timestamp=datetime.utcnow()
        )
        assert signals.coverage == 1.0
    
    def test_unicode_entity_names(self):
        """Unicode entity names should work."""
        unicode_names = [
            "北京科技公司",
            "Société Générale",
            "Müller & Söhne GmbH",
            "🏢 TechCorp",
        ]
        for name in unicode_names:
            signals = compute_sufficiency(
                query_entities=[name],
                found_entities=[{"id": "e1", "name": name}],
                relationships=[],
                query_timestamp=datetime.utcnow()
            )
            assert signals.coverage == 1.0, f"Unicode name '{name}' should match"
    
    def test_empty_string_entity_name(self):
        """Empty string entity name should be handled gracefully."""
        signals = compute_sufficiency(
            query_entities=[""],
            found_entities=[{"id": "e1", "name": ""}],
            relationships=[],
            query_timestamp=datetime.utcnow()
        )
        assert signals is not None
    
    def test_whitespace_entity_name(self):
        """Whitespace-only entity name should be handled gracefully."""
        signals = compute_sufficiency(
            query_entities=["   "],
            found_entities=[{"id": "e1", "name": "   "}],
            relationships=[],
            query_timestamp=datetime.utcnow()
        )
        assert signals is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
