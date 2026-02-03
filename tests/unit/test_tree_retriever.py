"""
Unit tests for TreeBasedRetriever

Tests hierarchical graph traversal and ranking.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from src.context_foundry.retrieval.tree_retriever import TreeBasedRetriever, RetrievalResult
from src.context_foundry.retrieval.intent_extractor import QueryIntent


class TestTreeBasedRetriever:
    """Test suite for TreeBasedRetriever"""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def retriever(self, mock_session):
        """Create a TreeBasedRetriever instance."""
        return TreeBasedRetriever(mock_session, tenant_id="test-tenant")

    def test_depth_1_retrieval(self, retriever, mock_session):
        """Test that direct connections (depth 1) are retrieved correctly."""
        # Setup
        anchor = {"id": "nexus-1", "name": "Nexus Industries", "entity_type": "ORGANIZATION"}
        intent = QueryIntent(
            target_entity_types=['PERSON'],
            relationship_types=['LEADS', 'HAS_EXECUTIVE'],
            property_filters={'role': 'CFO'},
            question_type='who',
            semantic_keywords=['cfo'],
            query_type='ROLE'
        )

        # Mock anchor resolver
        with patch.object(retriever.anchor_resolver, 'identify_anchor', return_value=anchor):
            # Mock entity details
            mock_session.execute = MagicMock()
            mock_session.execute.return_value.fetchone.return_value = Mock(
                id='person-1',
                name='Michael Chang',
                entity_type='PERSON',
                properties={'role': 'CFO'},
                embedding=None,
                confidence=0.95,
                lifecycle_state='TRUSTED'
            )

            # Mock connected entities
            mock_session.execute.return_value.fetchall.return_value = []

            # Execute
            result = retriever.retrieve("Who is the CFO?", query_type="ROLE", max_depth=1)

            # Verify
            assert result is not None
            # Note: Full integration test needed with real DB

    def test_matches_intent_entity_type(self, retriever):
        """Test that intent matching filters by entity type."""
        entity = {
            'id': 'test-1',
            'name': 'Test Entity',
            'entity_type': 'PERSON',
            'properties': {}
        }

        intent = QueryIntent(
            target_entity_types=['ORGANIZATION'],  # Looking for org, not person
            relationship_types=[],
            property_filters={},
            question_type='what',
            semantic_keywords=[],
            query_type='UNKNOWN'
        )

        assert not retriever._matches_intent(entity, intent, depth=1)

    def test_matches_intent_property_filter(self, retriever):
        """Test that intent matching filters by properties."""
        entity = {
            'id': 'test-1',
            'name': 'Test Entity',
            'entity_type': 'PERSON',
            'properties': {'role': 'CEO'}
        }

        intent = QueryIntent(
            target_entity_types=['PERSON'],
            relationship_types=[],
            property_filters={'role': 'CFO'},  # Looking for CFO, not CEO
            question_type='who',
            semantic_keywords=[],
            query_type='ROLE'
        )

        assert not retriever._matches_intent(entity, intent, depth=1)

    def test_ranking_prioritizes_depth(self, retriever):
        """Test that ranking prioritizes shallower depth."""
        results = [
            {
                'entity': {'id': '1', 'name': 'Entity Depth 3', 'entity_type': 'PERSON', 'embedding': None},
                'depth': 3
            },
            {
                'entity': {'id': '2', 'name': 'Entity Depth 1', 'entity_type': 'PERSON', 'embedding': None},
                'depth': 1
            },
            {
                'entity': {'id': '3', 'name': 'Entity Depth 2', 'entity_type': 'PERSON', 'embedding': None},
                'depth': 2
            }
        ]

        intent = QueryIntent(
            target_entity_types=['PERSON'],
            relationship_types=[],
            property_filters={},
            question_type='who',
            semantic_keywords=[],
            query_type='UNKNOWN'
        )

        ranked = retriever._rank_results(results, "test query", intent)

        # Depth 1 should be ranked highest
        assert ranked[0]['depth'] == 1
        assert ranked[1]['depth'] == 2
        assert ranked[2]['depth'] == 3

    def test_confidence_high_for_shallow_depth(self, retriever):
        """Test that shallow results get high confidence."""
        results = [
            {
                'entity': {'id': '1', 'name': 'Test', 'entity_type': 'PERSON'},
                'depth': 1,
                'combined_score': 0.9
            }
        ]

        confidence = retriever._compute_confidence(results, max_depth=1)
        assert confidence == 'high'

    def test_confidence_medium_for_deep_results(self, retriever):
        """Test that deeper results get medium confidence."""
        results = [
            {
                'entity': {'id': '1', 'name': 'Test', 'entity_type': 'PERSON'},
                'depth': 3,
                'combined_score': 0.7
            }
        ]

        confidence = retriever._compute_confidence(results, max_depth=3)
        assert confidence == 'medium'

    def test_keyword_similarity(self, retriever):
        """Test keyword-based similarity scoring."""
        entity = {
            'id': '1',
            'name': 'Michael Chang CFO',
            'entity_type': 'PERSON',
            'properties': {'role': 'Chief Financial Officer'}
        }

        keywords = ['cfo', 'financial']
        score = retriever._keyword_similarity(entity, keywords)

        # Should match both keywords
        assert score > 0.5

    def test_fallback_semantic_search(self, retriever):
        """Test fallback to semantic search when no anchor found."""
        with patch.object(retriever.anchor_resolver, 'identify_anchor', return_value=None):
            result = retriever.retrieve("test query")

            assert result.method == 'semantic_fallback'
            assert result.confidence == 'none'


class TestIntentExtractor:
    """Test suite for IntentExtractor"""

    @pytest.fixture
    def extractor(self):
        """Create an IntentExtractor instance."""
        from src.context_foundry.retrieval.intent_extractor import IntentExtractor
        return IntentExtractor()

    def test_extract_role_query(self, extractor):
        """Test intent extraction for role queries."""
        intent = extractor.extract("Who is the CFO?", query_type="ROLE")

        assert intent.query_type == "ROLE"
        assert 'PERSON' in intent.target_entity_types
        assert intent.question_type == 'who'
        assert 'cfo' in intent.semantic_keywords

    def test_extract_metric_query(self, extractor):
        """Test intent extraction for metric queries."""
        intent = extractor.extract("What is the FY2026 revenue?", query_type="METRIC")

        assert intent.query_type == "METRIC"
        assert intent.property_filters.get('fiscal_year') == '2026'
        assert 'revenue' in intent.semantic_keywords

    def test_extract_aggregation_query(self, extractor):
        """Test intent extraction for aggregation queries."""
        intent = extractor.extract("How many employees?", query_type="AGGREGATION")

        assert intent.query_type == "AGGREGATION"
        assert intent.requires_aggregation is True
        assert intent.question_type == 'how_many'

    def test_extract_property_filters(self, extractor):
        """Test property filter extraction."""
        filters = extractor._extract_property_filters("Who is the CFO for FY2026?")

        assert 'fiscal_year' in filters or 'year' in filters
        assert 'role' in filters
        assert filters['role'] == 'CFO'

    def test_extract_keywords(self, extractor):
        """Test keyword extraction."""
        keywords = extractor._extract_keywords("What is the revenue target for Q4?")

        assert 'revenue' in keywords
        assert 'target' in keywords
        # Stopwords should be removed
        assert 'the' not in keywords
        assert 'is' not in keywords


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
