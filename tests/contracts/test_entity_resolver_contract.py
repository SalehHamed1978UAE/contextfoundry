"""
Contract tests for EntityResolver.

These tests verify that the EntityResolver:
1. Follows the 3-stage resolution pipeline (exact -> semantic -> fuzzy)
2. Correctly handles disambiguation when candidates are close
3. Respects threshold configurations
4. Handles edge cases like empty queries
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.context_foundry.contracts.entity_resolver import (
    EntityResolverContract,
    EntityCandidate,
    ResolveResult,
    MatchStage,
)


class TestEntityCandidateContract:
    """Test the EntityCandidate dataclass invariants."""
    
    def test_valid_candidate(self):
        """Valid candidates should be created without errors."""
        candidate = EntityCandidate(
            entity_id="uuid-123",
            name="Payment Service",
            entity_type="SERVICE",
            description="Handles payments",
            score=0.95,
            match_stage="exact",
            confidence=0.95
        )
        assert candidate.name == "Payment Service"
        assert candidate.score == 0.95
    
    def test_score_must_be_in_range(self):
        """Score outside [0, 1] should raise ValueError."""
        with pytest.raises(ValueError, match="score must be in"):
            EntityCandidate(
                entity_id="uuid-123",
                name="Test",
                entity_type="SERVICE",
                description=None,
                score=1.5,
                match_stage="exact"
            )
    
    def test_negative_score_rejected(self):
        """Negative scores should be rejected."""
        with pytest.raises(ValueError, match="score must be in"):
            EntityCandidate(
                entity_id="uuid-123",
                name="Test",
                entity_type="SERVICE",
                description=None,
                score=-0.1,
                match_stage="exact"
            )
    
    def test_confidence_must_be_in_range(self):
        """Confidence outside [0, 1] should raise ValueError."""
        with pytest.raises(ValueError, match="confidence must be in"):
            EntityCandidate(
                entity_id="uuid-123",
                name="Test",
                entity_type="SERVICE",
                description=None,
                score=0.9,
                match_stage="exact",
                confidence=1.2
            )
    
    def test_to_dict_format(self):
        """to_dict should return proper format."""
        candidate = EntityCandidate(
            entity_id="uuid-123",
            name="Test Service",
            entity_type="SERVICE",
            description="Test desc",
            score=0.8765,
            match_stage="semantic",
            confidence=0.8765
        )
        d = candidate.to_dict()
        assert d["entity_id"] == "uuid-123"
        assert d["name"] == "Test Service"
        assert d["score"] == 0.8765
        assert d["match_stage"] == "semantic"


class TestResolveResultContract:
    """Test the ResolveResult dataclass invariants."""
    
    def test_empty_result(self):
        """Empty result should be valid."""
        result = ResolveResult(match_stage="not_found")
        assert result.entity is None
        assert result.is_found is False
    
    def test_result_with_entity(self):
        """Result with entity should have positive confidence."""
        candidate = EntityCandidate(
            entity_id="uuid-123",
            name="Test",
            entity_type="SERVICE",
            description=None,
            score=0.9,
            match_stage="exact",
            confidence=0.9
        )
        result = ResolveResult(
            entity=candidate,
            confidence=0.9,
            match_stage="exact"
        )
        assert result.is_found is True
        assert result.confidence == 0.9
    
    def test_entity_requires_positive_confidence(self):
        """If entity is set, confidence must be > 0."""
        candidate = EntityCandidate(
            entity_id="uuid-123",
            name="Test",
            entity_type="SERVICE",
            description=None,
            score=0.9,
            match_stage="exact",
            confidence=0.9
        )
        with pytest.raises(ValueError, match="confidence must be > 0"):
            ResolveResult(
                entity=candidate,
                confidence=0.0,
                match_stage="exact"
            )
    
    def test_disambiguation_requires_multiple_candidates(self):
        """needs_disambiguation=True requires 2+ candidates."""
        candidate = EntityCandidate(
            entity_id="uuid-123",
            name="Test",
            entity_type="SERVICE",
            description=None,
            score=0.9,
            match_stage="exact",
            confidence=0.9
        )
        with pytest.raises(ValueError, match="at least 2 candidates"):
            ResolveResult(
                needs_disambiguation=True,
                candidates=[candidate],
                match_stage="exact"
            )
    
    def test_disambiguation_with_multiple_candidates(self):
        """Disambiguation with 2+ candidates should be valid."""
        candidate1 = EntityCandidate(
            entity_id="uuid-1",
            name="Payment Service",
            entity_type="SERVICE",
            description=None,
            score=0.85,
            match_stage="semantic",
            confidence=0.85
        )
        candidate2 = EntityCandidate(
            entity_id="uuid-2",
            name="Payment Gateway",
            entity_type="SERVICE",
            description=None,
            score=0.83,
            match_stage="semantic",
            confidence=0.83
        )
        result = ResolveResult(
            needs_disambiguation=True,
            candidates=[candidate1, candidate2],
            match_stage="semantic"
        )
        assert result.needs_disambiguation is True
        assert len(result.candidates) == 2
    
    def test_is_high_confidence_threshold(self):
        """is_high_confidence should be True for confidence >= 0.8."""
        candidate = EntityCandidate(
            entity_id="uuid-123",
            name="Test",
            entity_type="SERVICE",
            description=None,
            score=0.8,
            match_stage="exact",
            confidence=0.8
        )
        result = ResolveResult(entity=candidate, confidence=0.8, match_stage="exact")
        assert result.is_high_confidence is True
        
        result2 = ResolveResult(entity=candidate, confidence=0.79, match_stage="exact")
        assert result2.is_high_confidence is False


class TestEntityResolverContractBehavior:
    """Test expected behavior of EntityResolver implementations."""
    
    def test_check_disambiguation_with_close_scores(self):
        """Candidates within delta should trigger disambiguation."""
        
        class TestResolver(EntityResolverContract):
            def resolve(self, query, entity_type_hint=None, top_k=20):
                pass
            def _exact_match(self, query, entity_type_hint=None):
                pass
            def _semantic_search(self, query, entity_type_hint=None, top_k=20):
                pass
            def _fuzzy_match(self, query, entity_type_hint=None):
                pass
        
        resolver = TestResolver()
        
        candidate1 = EntityCandidate(
            entity_id="uuid-1",
            name="Payment Service",
            entity_type="SERVICE",
            description=None,
            score=0.90,
            match_stage="semantic",
            confidence=0.90
        )
        candidate2 = EntityCandidate(
            entity_id="uuid-2",
            name="Payment Gateway",
            entity_type="SERVICE",
            description=None,
            score=0.85,
            match_stage="semantic",
            confidence=0.85
        )
        
        assert resolver._check_disambiguation([candidate1, candidate2]) is True
    
    def test_check_disambiguation_with_distant_scores(self):
        """Candidates outside delta should not trigger disambiguation."""
        
        class TestResolver(EntityResolverContract):
            def resolve(self, query, entity_type_hint=None, top_k=20):
                pass
            def _exact_match(self, query, entity_type_hint=None):
                pass
            def _semantic_search(self, query, entity_type_hint=None, top_k=20):
                pass
            def _fuzzy_match(self, query, entity_type_hint=None):
                pass
        
        resolver = TestResolver()
        
        candidate1 = EntityCandidate(
            entity_id="uuid-1",
            name="Payment Service",
            entity_type="SERVICE",
            description=None,
            score=0.95,
            match_stage="semantic",
            confidence=0.95
        )
        candidate2 = EntityCandidate(
            entity_id="uuid-2",
            name="User Service",
            entity_type="SERVICE",
            description=None,
            score=0.60,
            match_stage="semantic",
            confidence=0.60
        )
        
        assert resolver._check_disambiguation([candidate1, candidate2]) is False
    
    def test_check_disambiguation_single_candidate(self):
        """Single candidate should not trigger disambiguation."""
        
        class TestResolver(EntityResolverContract):
            def resolve(self, query, entity_type_hint=None, top_k=20):
                pass
            def _exact_match(self, query, entity_type_hint=None):
                pass
            def _semantic_search(self, query, entity_type_hint=None, top_k=20):
                pass
            def _fuzzy_match(self, query, entity_type_hint=None):
                pass
        
        resolver = TestResolver()
        
        candidate = EntityCandidate(
            entity_id="uuid-1",
            name="Payment Service",
            entity_type="SERVICE",
            description=None,
            score=0.90,
            match_stage="semantic",
            confidence=0.90
        )
        
        assert resolver._check_disambiguation([candidate]) is False


class TestThresholdConfiguration:
    """Test that threshold constants are properly defined."""
    
    def test_default_thresholds(self):
        """Default thresholds should match expected values."""
        assert EntityResolverContract.EXACT_MATCH_THRESHOLD == 0.95
        assert EntityResolverContract.SEMANTIC_THRESHOLD == 0.75
        assert EntityResolverContract.FUZZY_THRESHOLD == 0.70
        assert EntityResolverContract.DISAMBIGUATION_DELTA == 0.1
    
    def test_threshold_ordering(self):
        """Thresholds should be in decreasing order of strictness."""
        assert EntityResolverContract.EXACT_MATCH_THRESHOLD > \
               EntityResolverContract.SEMANTIC_THRESHOLD > \
               EntityResolverContract.FUZZY_THRESHOLD


class TestMatchStageEnum:
    """Test the MatchStage enumeration."""
    
    def test_match_stage_values(self):
        """MatchStage should have expected values."""
        assert MatchStage.EXACT.value == "exact"
        assert MatchStage.SEMANTIC.value == "semantic"
        assert MatchStage.FUZZY.value == "fuzzy"
        assert MatchStage.NOT_FOUND.value == "not_found"
        assert MatchStage.EMPTY_QUERY.value == "empty_query"
