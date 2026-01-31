"""
Unit tests for Phase 2 Query Pipeline components:
- QueryClassifier
- RoleResolver  
- RetrievalRouter
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.context_foundry.agents.query_classifier import QueryClassifier, QueryClassification
from src.context_foundry.agents.role_resolver import RoleResolver, RoleResolution
from src.context_foundry.agents.retrieval_router import RetrievalRouter, QueryPipeline, RetrievalResult


class TestQueryClassifier:
    """Tests for QueryClassifier component."""
    
    def test_quick_role_check_ceo(self):
        """Should detect CEO role reference."""
        classifier = QueryClassifier()
        has_role, role_name = classifier._quick_role_check("What is the CEO's salary?")
        assert has_role is True
        assert role_name == "CEO"
    
    def test_quick_role_check_chief_executive(self):
        """Should detect full title role reference."""
        classifier = QueryClassifier()
        has_role, role_name = classifier._quick_role_check("What is the chief executive officer's salary?")
        assert has_role is True
        assert role_name == "CHIEF EXECUTIVE OFFICER"
    
    def test_quick_role_check_no_role(self):
        """Should not detect role in person name query."""
        classifier = QueryClassifier()
        has_role, role_name = classifier._quick_role_check("What is Sarah Chen's salary?")
        assert has_role is False
        assert role_name is None
    
    def test_quick_list_check_portfolio(self):
        """Should detect list query for portfolio companies."""
        classifier = QueryClassifier()
        expects_list = classifier._quick_list_check("What portfolio companies does TechVentures have?")
        assert expects_list is True
    
    def test_quick_list_check_who_reports(self):
        """Should detect list query for reports to."""
        classifier = QueryClassifier()
        expects_list = classifier._quick_list_check("Who reports to the CEO?")
        assert expects_list is True
    
    def test_quick_list_check_single_entity(self):
        """Should not detect list for single entity query."""
        classifier = QueryClassifier()
        expects_list = classifier._quick_list_check("Who is the CEO?")
        assert expects_list is False
    
    @patch('src.context_foundry.agents.query_classifier.OpenAI')
    def test_classify_role_query(self, mock_openai):
        """Should classify role-based query correctly."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
        {
            "query_type": "ATTRIBUTE",
            "retrieval_strategy": "DOCS_ONLY",
            "target_entity": "TechVentures",
            "has_role_reference": true,
            "role_referenced": "CEO",
            "expects_list": false,
            "confidence": 0.9,
            "reasoning": "Query asks for CEO salary attribute"
        }
        '''
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        
        classifier = QueryClassifier()
        result = classifier.classify("What is the CEO's salary?")
        
        assert result.has_role_reference is True
        assert result.role_referenced == "CEO"
        assert result.expects_list is False
        assert result.query_type == "ATTRIBUTE"
    
    @patch('src.context_foundry.agents.query_classifier.OpenAI')
    def test_classify_list_query(self, mock_openai):
        """Should classify list query correctly."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
        {
            "query_type": "RELATIONSHIP",
            "retrieval_strategy": "GRAPH_ONLY",
            "target_entity": "TechVentures",
            "has_role_reference": false,
            "role_referenced": null,
            "expects_list": true,
            "confidence": 0.85,
            "reasoning": "Query asks for list of portfolio companies"
        }
        '''
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        
        classifier = QueryClassifier()
        result = classifier.classify("What portfolio companies does TechVentures have?")
        
        assert result.expects_list is True
        assert result.query_type == "RELATIONSHIP"


class TestRoleResolver:
    """Tests for RoleResolver component."""
    
    def test_normalize_role_abbreviation(self):
        """Should expand CEO to full form."""
        session = Mock()
        resolver = RoleResolver(session, "test-tenant")
        
        variations = resolver._normalize_role("CEO")
        assert "chief executive officer" in variations
        assert "ceo" in variations
    
    def test_normalize_role_full_title(self):
        """Should handle full title."""
        session = Mock()
        resolver = RoleResolver(session, "test-tenant")
        
        variations = resolver._normalize_role("Chief Technology Officer")
        assert "chief technology officer" in variations
        assert "cto" in variations
    
    def test_resolution_is_resolved(self):
        """RoleResolution.is_resolved should work correctly."""
        resolved = RoleResolution(
            role="CEO",
            resolved_name="Sarah Chen",
            resolved_entity_id="123",
            confidence=0.9
        )
        assert resolved.is_resolved is True
        
        unresolved = RoleResolution(role="Unknown Role")
        assert unresolved.is_resolved is False
    
    def test_resolution_to_dict(self):
        """RoleResolution.to_dict should return all fields."""
        resolution = RoleResolution(
            role="CEO",
            resolved_name="Sarah Chen",
            resolved_entity_id="123",
            confidence=0.9,
            alternatives=[{"name": "John Doe", "role": "Acting CEO"}]
        )
        
        d = resolution.to_dict()
        assert d["role"] == "CEO"
        assert d["resolved_name"] == "Sarah Chen"
        assert d["is_resolved"] is True
        assert len(d["alternatives"]) == 1


class TestRetrievalRouter:
    """Tests for RetrievalRouter component."""
    
    def test_get_limit_list_query(self):
        """Should use higher limit for list queries."""
        session = Mock()
        router = RetrievalRouter(session, "test-tenant")
        
        classification = QueryClassification(
            query_type="RELATIONSHIP",
            retrieval_strategy="HYBRID",
            target_entity=None,
            has_role_reference=False,
            role_referenced=None,
            expects_list=True,
            confidence=0.9,
            reasoning=""
        )
        
        limit = router._get_limit(classification)
        assert limit == 15
    
    def test_get_limit_single_query(self):
        """Should use default limit for single entity queries."""
        session = Mock()
        router = RetrievalRouter(session, "test-tenant")
        
        classification = QueryClassification(
            query_type="ATTRIBUTE",
            retrieval_strategy="DOCS_ONLY",
            target_entity=None,
            has_role_reference=True,
            role_referenced="CEO",
            expects_list=False,
            confidence=0.9,
            reasoning=""
        )
        
        limit = router._get_limit(classification)
        assert limit == 5
    
    def test_retrieval_result_has_data(self):
        """RetrievalResult.has_data should detect presence of data."""
        empty = RetrievalResult()
        assert empty.has_data is False
        
        with_entities = RetrievalResult(entities=[{"id": "1", "name": "Test"}])
        assert with_entities.has_data is True
        
        with_chunks = RetrievalResult(chunks=[{"text": "test"}])
        assert with_chunks.has_data is True


class TestQueryClassification:
    """Tests for QueryClassification dataclass."""
    
    def test_to_dict(self):
        """Should serialize all fields correctly."""
        classification = QueryClassification(
            query_type="ATTRIBUTE",
            retrieval_strategy="DOCS_ONLY",
            target_entity="TechVentures",
            has_role_reference=True,
            role_referenced="CEO",
            expects_list=False,
            confidence=0.85,
            reasoning="Query asks for CEO salary"
        )
        
        d = classification.to_dict()
        assert d["query_type"] == "ATTRIBUTE"
        assert d["retrieval_strategy"] == "DOCS_ONLY"
        assert d["target_entity"] == "TechVentures"
        assert d["has_role_reference"] is True
        assert d["role_referenced"] == "CEO"
        assert d["expects_list"] is False
        assert d["confidence"] == 0.85


class TestIntegration:
    """Integration tests with real database."""
    
    @pytest.fixture
    def db_session(self):
        """Create database session for testing."""
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
    
    @pytest.fixture
    def tenant_id(self):
        """TechVentures tenant ID."""
        return "556305eb-886e-44b6-8e48-9b48c74849e2"
    
    def test_role_resolver_ceo(self, db_session, tenant_id):
        """Should resolve CEO to Sarah Chen."""
        resolver = RoleResolver(db_session, tenant_id)
        resolution = resolver.resolve("CEO")
        
        assert resolution.is_resolved is True
        assert "sarah" in resolution.resolved_name.lower() or "chen" in resolution.resolved_name.lower()
    
    def test_role_resolver_cto(self, db_session, tenant_id):
        """Should resolve CTO to Marcus Williams."""
        resolver = RoleResolver(db_session, tenant_id)
        resolution = resolver.resolve("CTO")
        
        assert resolution.is_resolved is True
        assert "marcus" in resolution.resolved_name.lower() or "williams" in resolution.resolved_name.lower()
    
    def test_query_pipeline_ceo_salary(self, db_session, tenant_id):
        """Full pipeline should work for CEO salary query."""
        pipeline = QueryPipeline(db_session, tenant_id)
        result = pipeline.process("What is the CEO's salary?")
        
        assert result.role_resolution is not None
        assert result.role_resolution.is_resolved is True
        assert result.has_data is True
    
    def test_query_pipeline_list_query(self, db_session, tenant_id):
        """Pipeline should set expects_list for portfolio query."""
        pipeline = QueryPipeline(db_session, tenant_id)
        result = pipeline.process("What portfolio companies does TechVentures have?")
        
        assert result.classification is not None
        assert result.classification.expects_list is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
