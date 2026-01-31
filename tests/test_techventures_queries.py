"""
End-to-end integration tests for TechVentures queries.

Tests the full query pipeline with real database:
- CEO's salary (role resolution)
- Portfolio companies (list query)  
- Who reports to CEO (relationship query)
- Tell me about DataFlow AI (exploration query)
"""
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


TENANT_ID = "556305eb-886e-44b6-8e48-9b48c74849e2"


@pytest.fixture(scope="module")
def db_session():
    """Create database session for testing."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        pytest.skip("DATABASE_URL not set")
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestQueryClassification:
    """Test query classification for different query types."""
    
    def test_ceo_salary_classification(self, db_session):
        """CEO salary should be classified as ATTRIBUTE with role reference."""
        from src.context_foundry.agents.query_classifier import QueryClassifier
        
        classifier = QueryClassifier()
        result = classifier.classify("What is the CEO's salary?")
        
        assert result.has_role_reference is True
        assert result.role_referenced is not None
        assert "CEO" in result.role_referenced.upper()
        assert result.expects_list is False
    
    def test_portfolio_companies_classification(self, db_session):
        """Portfolio companies should be classified as list query."""
        from src.context_foundry.agents.query_classifier import QueryClassifier
        
        classifier = QueryClassifier()
        result = classifier.classify("What portfolio companies does TechVentures have?")
        
        assert result.expects_list is True
    
    def test_who_reports_classification(self, db_session):
        """Who reports to CEO should be classified as list query with role reference."""
        from src.context_foundry.agents.query_classifier import QueryClassifier
        
        classifier = QueryClassifier()
        result = classifier.classify("Who reports to the CEO?")
        
        assert result.expects_list is True
        assert result.has_role_reference is True
    
    def test_exploration_classification(self, db_session):
        """Tell me about X should be classified as EXPLORATION."""
        from src.context_foundry.agents.query_classifier import QueryClassifier
        
        classifier = QueryClassifier()
        result = classifier.classify("Tell me about DataFlow AI")
        
        assert result.query_type == "EXPLORATION"


class TestRoleResolution:
    """Test role resolution for executive titles."""
    
    def test_ceo_resolution(self, db_session):
        """CEO should resolve to Sarah Chen."""
        from src.context_foundry.agents.role_resolver import RoleResolver
        
        resolver = RoleResolver(db_session, TENANT_ID)
        resolution = resolver.resolve("CEO")
        
        assert resolution.is_resolved is True
        assert resolution.resolved_name is not None
        name_lower = resolution.resolved_name.lower()
        assert "sarah" in name_lower or "chen" in name_lower
    
    def test_cto_resolution(self, db_session):
        """CTO should resolve to Marcus Williams."""
        from src.context_foundry.agents.role_resolver import RoleResolver
        
        resolver = RoleResolver(db_session, TENANT_ID)
        resolution = resolver.resolve("CTO")
        
        assert resolution.is_resolved is True
        assert resolution.resolved_name is not None
        name_lower = resolution.resolved_name.lower()
        assert "marcus" in name_lower or "williams" in name_lower
    
    def test_cfo_resolution(self, db_session):
        """CFO should resolve to James O'Brien."""
        from src.context_foundry.agents.role_resolver import RoleResolver
        
        resolver = RoleResolver(db_session, TENANT_ID)
        resolution = resolver.resolve("CFO")
        
        assert resolution.is_resolved is True
        assert resolution.resolved_name is not None
        name_lower = resolution.resolved_name.lower()
        assert "james" in name_lower or "brien" in name_lower
    
    def test_chief_executive_officer_resolution(self, db_session):
        """Full title should also resolve."""
        from src.context_foundry.agents.role_resolver import RoleResolver
        
        resolver = RoleResolver(db_session, TENANT_ID)
        resolution = resolver.resolve("Chief Executive Officer")
        
        assert resolution.is_resolved is True


class TestQueryPipeline:
    """Test full query pipeline."""
    
    def test_ceo_salary_pipeline(self, db_session):
        """Pipeline should resolve CEO and retrieve salary docs."""
        from src.context_foundry.agents.retrieval_router import QueryPipeline
        
        pipeline = QueryPipeline(db_session, TENANT_ID)
        result = pipeline.process("What is the CEO's salary?")
        
        assert result.role_resolution is not None
        assert result.role_resolution.is_resolved is True
        assert result.has_data is True
    
    def test_portfolio_companies_pipeline(self, db_session):
        """Pipeline should use higher limit for list query."""
        from src.context_foundry.agents.retrieval_router import QueryPipeline
        
        pipeline = QueryPipeline(db_session, TENANT_ID)
        result = pipeline.process("What portfolio companies does TechVentures have?")
        
        assert result.classification is not None
        assert result.classification.expects_list is True
    
    def test_who_reports_pipeline(self, db_session):
        """Pipeline should resolve CEO for reports-to query."""
        from src.context_foundry.agents.retrieval_router import QueryPipeline
        
        pipeline = QueryPipeline(db_session, TENANT_ID)
        result = pipeline.process("Who reports to the CEO?")
        
        assert result.classification is not None
        assert result.classification.expects_list is True
        assert result.role_resolution is not None
    
    def test_exploration_pipeline(self, db_session):
        """Pipeline should use HYBRID for exploration query."""
        from src.context_foundry.agents.retrieval_router import QueryPipeline
        
        pipeline = QueryPipeline(db_session, TENANT_ID)
        result = pipeline.process("Tell me about DataFlow AI")
        
        assert result.classification is not None
        assert result.classification.retrieval_strategy in ["HYBRID", "DOCS_ONLY"]


class TestToolAgentIntegration:
    """Test ToolAgent with integrated pipeline."""
    
    def test_ceo_salary_answer(self, db_session):
        """ToolAgent should answer CEO salary correctly."""
        from src.context_foundry.agents.tool_agent import ToolAgent
        
        agent = ToolAgent(db_session, TENANT_ID)
        result = agent.query("What is the CEO's salary?", debug=False)
        
        answer = result.get("answer", "")
        answer_lower = answer.lower()
        
        assert "sarah" in answer_lower or "chen" in answer_lower
        assert "850" in answer or "$850" in answer or "850,000" in answer
    
    def test_who_reports_to_ceo(self, db_session):
        """ToolAgent should list executives who report to CEO."""
        from src.context_foundry.agents.tool_agent import ToolAgent
        
        agent = ToolAgent(db_session, TENANT_ID)
        result = agent.query("Who reports to the CEO?", debug=False)
        
        answer = result.get("answer", "")
        answer_lower = answer.lower()
        
        executives_found = 0
        for name in ["james", "marcus", "amira", "o'brien", "williams", "hassan"]:
            if name in answer_lower:
                executives_found += 1
        
        assert executives_found >= 2, f"Expected at least 2 executives in answer, found {executives_found}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
