"""
Contract tests for QueryParser.

These tests verify that the QueryParser correctly:
1. Classifies query types (impact, dependency, ownership, etc.)
2. Extracts entity names without including intent keywords
3. Handles edge cases like malformed queries

Critical test: "What was affected by X" should NOT parse "affected by X" as entity name.
"""

import pytest
from src.context_foundry.contracts.query_parser import (
    QueryParserContract,
    PatternBasedQueryParser,
    QueryIntent,
    QueryType,
)


class TestQueryIntentContract:
    """Test the QueryIntent dataclass invariants."""
    
    def test_query_type_required(self):
        """QueryType cannot be None."""
        with pytest.raises(ValueError, match="query_type cannot be None"):
            QueryIntent(query_type=None, raw_query="test")
    
    def test_entity_name_validation_rejects_intent_keywords(self):
        """Entity names starting with intent keywords should be rejected."""
        with pytest.raises(ValueError, match="starts with intent keyword"):
            QueryIntent(
                query_type=QueryType.IMPACT,
                target_entity="affected by Payment Service",
                raw_query="What was affected by Payment Service?"
            )
    
    def test_entity_name_validation_accepts_clean_names(self):
        """Clean entity names should be accepted."""
        intent = QueryIntent(
            query_type=QueryType.IMPACT,
            target_entity="Payment Service",
            raw_query="What was affected by Payment Service?"
        )
        assert intent.target_entity == "Payment Service"
    
    def test_entity_name_with_depends_on_rejected(self):
        """Entity names starting with 'depends on' should be rejected."""
        with pytest.raises(ValueError, match="starts with intent keyword"):
            QueryIntent(
                query_type=QueryType.DEPENDENCY,
                target_entity="depends on Auth Service",
                raw_query="What depends on Auth Service?"
            )


class TestPatternBasedQueryParserContract:
    """Contract tests for the PatternBasedQueryParser implementation."""
    
    @pytest.fixture
    def parser(self) -> QueryParserContract:
        return PatternBasedQueryParser()
    
    def test_parse_returns_query_intent(self, parser):
        """Parse must return a QueryIntent object."""
        result = parser.parse("What is the Payment Service?")
        assert isinstance(result, QueryIntent)
    
    def test_parse_preserves_raw_query(self, parser):
        """Parse must preserve the original query text."""
        query = "What depends on Auth Service?"
        result = parser.parse(query)
        assert result.raw_query == query


class TestImpactQueryClassification:
    """Tests for impact/blast radius query detection - THIS IS THE BUG FIX."""
    
    @pytest.fixture
    def parser(self) -> QueryParserContract:
        return PatternBasedQueryParser()
    
    def test_what_was_affected_by_is_impact_query(self, parser):
        """'What was affected by X' should be classified as IMPACT."""
        result = parser.parse("What was affected by Payment Service?")
        assert result.query_type == QueryType.IMPACT
    
    def test_what_was_affected_extracts_correct_entity(self, parser):
        """'What was affected by X' should extract 'X' as target entity."""
        result = parser.parse("What was affected by Payment Service?")
        assert result.target_entity == "Payment Service"
        assert "affected" not in result.target_entity.lower()
    
    def test_blast_radius_query(self, parser):
        """Blast radius queries should be IMPACT type."""
        result = parser.parse("What is the blast radius of Database failure?")
        assert result.query_type == QueryType.IMPACT
    
    def test_blast_radius_extracts_entity(self, parser):
        """Blast radius query should extract the failing entity."""
        result = parser.parse("What is the blast radius of Auth Database?")
        assert result.target_entity == "Auth Database"
    
    def test_if_x_fails_is_impact(self, parser):
        """'If X fails, what breaks?' should be IMPACT type."""
        result = parser.parse("If Payment Gateway fails, what breaks?")
        assert result.query_type == QueryType.IMPACT
    
    def test_if_x_fails_extracts_entity(self, parser):
        """'If X fails' should extract X as target."""
        result = parser.parse("If Payment Gateway fails, what breaks?")
        assert result.target_entity == "Payment Gateway"
    
    def test_what_services_affected(self, parser):
        """'What services are affected' should be IMPACT."""
        result = parser.parse("What services are affected if Order Service goes down?")
        assert result.query_type == QueryType.IMPACT
    
    def test_which_services_impacted(self, parser):
        """'Which services are impacted' should be IMPACT."""
        result = parser.parse("Which services are impacted by Cache failure?")
        assert result.query_type == QueryType.IMPACT
    
    def test_downstream_impact(self, parser):
        """'downstream impact' should be IMPACT type."""
        result = parser.parse("What is the downstream impact of API Gateway?")
        assert result.query_type == QueryType.IMPACT
    
    def test_cascade_failure(self, parser):
        """'cascade' keyword should trigger IMPACT type."""
        result = parser.parse("Will there be a cascade if Redis fails?")
        assert result.query_type == QueryType.IMPACT


class TestDependencyQueryClassification:
    """Tests for dependency query detection."""
    
    @pytest.fixture
    def parser(self) -> QueryParserContract:
        return PatternBasedQueryParser()
    
    def test_what_depends_on_is_dependency(self, parser):
        """'What does X depend on' should be DEPENDENCY type."""
        result = parser.parse("What does Payment Service depend on?")
        assert result.query_type == QueryType.DEPENDENCY
    
    def test_dependencies_of_is_dependency(self, parser):
        """'Dependencies of X' should be DEPENDENCY type."""
        result = parser.parse("Show me the dependencies of Order Service")
        assert result.query_type == QueryType.DEPENDENCY
    
    def test_upstream_services(self, parser):
        """'upstream' keyword should trigger DEPENDENCY."""
        result = parser.parse("What are the upstream services of API Gateway?")
        assert result.query_type == QueryType.DEPENDENCY


class TestOwnershipQueryClassification:
    """Tests for ownership query detection."""
    
    @pytest.fixture
    def parser(self) -> QueryParserContract:
        return PatternBasedQueryParser()
    
    def test_who_owns_is_ownership(self, parser):
        """'Who owns X' should be OWNERSHIP type."""
        result = parser.parse("Who owns the Payment Service?")
        assert result.query_type == QueryType.OWNERSHIP
    
    def test_owner_of_is_ownership(self, parser):
        """'Owner of X' should be OWNERSHIP type."""
        result = parser.parse("What is the owner of Auth Database?")
        assert result.query_type == QueryType.OWNERSHIP
    
    def test_who_manages_is_ownership(self, parser):
        """'Who manages' should be OWNERSHIP type."""
        result = parser.parse("Who manages the infrastructure?")
        assert result.query_type == QueryType.OWNERSHIP


class TestRuleQueryClassification:
    """Tests for rule/policy query detection."""
    
    @pytest.fixture
    def parser(self) -> QueryParserContract:
        return PatternBasedQueryParser()
    
    def test_escalation_is_rule(self, parser):
        """Escalation queries should be RULE type."""
        result = parser.parse("What is the escalation process for Sev1?")
        assert result.query_type == QueryType.RULE
    
    def test_runbook_is_rule(self, parser):
        """Runbook queries should be RULE type."""
        result = parser.parse("Show me the runbook for database failover")
        assert result.query_type == QueryType.RULE
    
    def test_policy_is_rule(self, parser):
        """Policy queries should be RULE type."""
        result = parser.parse("What is the policy for access requests?")
        assert result.query_type == QueryType.RULE


class TestAnalysisQueryClassification:
    """Tests for analysis/aggregation query detection."""
    
    @pytest.fixture
    def parser(self) -> QueryParserContract:
        return PatternBasedQueryParser()
    
    def test_how_many_is_analysis(self, parser):
        """'How many' queries should be ANALYSIS type."""
        result = parser.parse("How many services depend on the database?")
        assert result.query_type == QueryType.ANALYSIS
    
    def test_patterns_is_analysis(self, parser):
        """Pattern queries should be ANALYSIS type."""
        result = parser.parse("What patterns exist in recent incidents?")
        assert result.query_type == QueryType.ANALYSIS
    
    def test_most_common_is_analysis(self, parser):
        """'Most common' queries should be ANALYSIS type."""
        result = parser.parse("What are the most common error types?")
        assert result.query_type == QueryType.ANALYSIS


class TestEntityExtraction:
    """Tests for entity name extraction."""
    
    @pytest.fixture
    def parser(self) -> QueryParserContract:
        return PatternBasedQueryParser()
    
    def test_extracts_service_suffix_entity(self, parser):
        """Should extract entities with 'Service' suffix."""
        result = parser.parse("Tell me about Payment Service")
        assert result.target_entity == "Payment Service"
    
    def test_extracts_database_suffix_entity(self, parser):
        """Should extract entities with 'Database' suffix."""
        result = parser.parse("What is Auth Database?")
        assert result.target_entity == "Auth Database"
    
    def test_extracts_multi_word_entity(self, parser):
        """Should extract multi-word entity names."""
        result = parser.parse("Describe the User Management Service")
        assert result.target_entity == "User Management Service"
    
    def test_removes_trailing_question_mark(self, parser):
        """Should clean trailing punctuation from entity names."""
        result = parser.parse("What is Payment Gateway?")
        assert "?" not in result.target_entity if result.target_entity else True
    
    def test_removes_trailing_failure_keywords(self, parser):
        """Should remove 'failure', 'fails' from entity names."""
        result = parser.parse("What happens when Payment Service fails?")
        if result.target_entity:
            assert "fails" not in result.target_entity.lower()
            assert "failure" not in result.target_entity.lower()


class TestEdgeCases:
    """Tests for edge cases and malformed queries."""
    
    @pytest.fixture
    def parser(self) -> QueryParserContract:
        return PatternBasedQueryParser()
    
    def test_empty_query(self, parser):
        """Empty query should return GENERAL type."""
        result = parser.parse("")
        assert result.query_type == QueryType.GENERAL
        assert result.target_entity is None
    
    def test_whitespace_only_query(self, parser):
        """Whitespace-only query should return GENERAL type."""
        result = parser.parse("   ")
        assert result.query_type == QueryType.GENERAL
    
    def test_no_entity_found(self, parser):
        """Query with no clear entity should have None target."""
        result = parser.parse("Hello, how are you?")
        assert result.target_entity is None
    
    def test_general_question(self, parser):
        """General questions should be GENERAL type."""
        result = parser.parse("What time is it?")
        assert result.query_type == QueryType.GENERAL
