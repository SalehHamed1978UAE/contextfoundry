"""
Unit tests for sufficiency signal computation.
Part 1.1 of MVP Verification Test Suite.
"""

import pytest
from datetime import datetime, timedelta
from src.context_foundry.agents.sufficiency import compute_sufficiency, SufficiencySignals


class TestSufficiencyComputation:
    """Unit tests for sufficiency signal computation."""
    
    def test_perfect_sufficiency(self):
        """All signals high -> confidence near 1.0"""
        recent_date = datetime.utcnow() - timedelta(days=5)
        
        signals = compute_sufficiency(
            query_entities=["Alice Johnson"],
            found_entities=[
                {"id": "e1", "name": "Alice Johnson", "entity_type": "PERSON"}
            ],
            relationships=[
                {"source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "WORKS_AT", 
                 "source_document_id": "doc1", "valid_from": recent_date},
                {"source_entity_id": "e1", "target_entity_id": "e3", "relationship_type": "REPORTS_TO",
                 "source_document_id": "doc2", "valid_from": recent_date},
                {"source_entity_id": "e1", "target_entity_id": "e4", "relationship_type": "MEMBER_OF",
                 "source_document_id": "doc1", "valid_from": recent_date},
                {"source_entity_id": "e1", "target_entity_id": "e5", "relationship_type": "LEADS",
                 "source_document_id": "doc3", "valid_from": recent_date},
                {"source_entity_id": "e1", "target_entity_id": "e6", "relationship_type": "MENTORS",
                 "source_document_id": "doc2", "valid_from": recent_date},
            ],
            query_timestamp=datetime.utcnow()
        )
        
        assert signals.coverage == 1.0, f"Expected coverage 1.0, got {signals.coverage}"
        assert signals.freshness >= 0.8, f"Expected freshness >= 0.8, got {signals.freshness}"
        assert signals.overall_confidence >= 0.5, f"Expected confidence >= 0.5, got {signals.overall_confidence}"
    
    def test_zero_coverage(self):
        """No entities found -> low confidence"""
        signals = compute_sufficiency(
            query_entities=["Unknown Person"],
            found_entities=[],
            relationships=[],
            query_timestamp=datetime.utcnow()
        )
        
        assert signals.coverage == 0.0
        assert signals.overall_confidence < 0.3
    
    def test_stale_data(self):
        """Old data -> low freshness"""
        old_date = datetime.utcnow() - timedelta(days=365 * 6)  # 6 years old
        
        signals = compute_sufficiency(
            query_entities=["Alice Johnson"],
            found_entities=[{"id": "e1", "name": "Alice Johnson"}],
            relationships=[{
                "source_entity_id": "e1", 
                "target_entity_id": "e2", 
                "relationship_type": "WORKS_AT",
                "valid_from": old_date
            }],
            query_timestamp=datetime.utcnow()
        )
        
        assert signals.freshness < 0.3, f"Expected freshness < 0.3 for stale data, got {signals.freshness}"
    
    def test_single_source_low_agreement(self):
        """Single source -> lower source_agreement"""
        signals = compute_sufficiency(
            query_entities=["Alice Johnson"],
            found_entities=[{"id": "e1", "name": "Alice Johnson"}],
            relationships=[{
                "source_entity_id": "e1",
                "target_entity_id": "e2",
                "relationship_type": "WORKS_AT",
                "source_document_id": "only_one_doc",
                "valid_from": datetime.utcnow()
            }],
            query_timestamp=datetime.utcnow()
        )
        
        assert signals.source_agreement <= 0.5, f"Single source should have agreement <= 0.5, got {signals.source_agreement}"
    
    def test_multi_source_higher_agreement(self):
        """Multiple sources for same fact -> higher source_agreement"""
        signals = compute_sufficiency(
            query_entities=["Alice Johnson"],
            found_entities=[{"id": "e1", "name": "Alice Johnson"}],
            relationships=[
                {"source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "WORKS_AT",
                 "source_document_id": "doc1", "valid_from": datetime.utcnow()},
                {"source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "WORKS_AT",
                 "source_document_id": "doc2", "valid_from": datetime.utcnow()},
                {"source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "WORKS_AT",
                 "source_document_id": "doc3", "valid_from": datetime.utcnow()},
            ],
            query_timestamp=datetime.utcnow()
        )
        
        assert signals.source_agreement >= 0.5, f"Multiple sources should have higher agreement, got {signals.source_agreement}"
    
    def test_sparse_relationships_low_density(self):
        """Few relationships -> low density"""
        signals = compute_sufficiency(
            query_entities=["Alice Johnson"],
            found_entities=[
                {"id": "e1", "name": "Alice Johnson"},
                {"id": "e2", "name": "TechCorp"},
                {"id": "e3", "name": "Bob Smith"},
                {"id": "e4", "name": "Engineering"},
                {"id": "e5", "name": "San Francisco"}
            ],
            relationships=[{
                "source_entity_id": "e1",
                "target_entity_id": "e2",
                "relationship_type": "WORKS_AT",
                "valid_from": datetime.utcnow()
            }],
            query_timestamp=datetime.utcnow()
        )
        
        assert signals.relationship_density < 0.5, f"Sparse relationships should have low density, got {signals.relationship_density}"


class TestGapDetection:
    """Test that gaps are correctly identified."""
    
    def test_missing_entity_gap(self):
        """Missing entity should be detected as a gap"""
        signals = compute_sufficiency(
            query_entities=["Unknown Person"],
            found_entities=[],
            relationships=[],
            query_timestamp=datetime.utcnow()
        )
        
        gap_types = [g['type'] for g in signals.gaps_detected]
        assert 'missing_entity' in gap_types, f"Expected missing_entity gap, got {gap_types}"
    
    def test_sparse_relationships_gap(self):
        """Sparse relationships should be detected as a gap"""
        signals = compute_sufficiency(
            query_entities=["Alice Johnson"],
            found_entities=[{"id": "e1", "name": "Alice Johnson"}],
            relationships=[{
                "source_entity_id": "e1",
                "target_entity_id": "e2",
                "relationship_type": "WORKS_AT",
                "valid_from": datetime.utcnow()
            }],
            query_timestamp=datetime.utcnow()
        )
        
        gap_types = [g['type'] for g in signals.gaps_detected]
        assert 'sparse_relationships' in gap_types, f"Expected sparse_relationships gap, got {gap_types}"
    
    def test_stale_data_gap(self):
        """Stale data should be detected as a gap"""
        old_date = datetime.utcnow() - timedelta(days=365 * 3)  # 3 years old
        
        signals = compute_sufficiency(
            query_entities=["Alice Johnson"],
            found_entities=[{"id": "e1", "name": "Alice Johnson"}],
            relationships=[{
                "source_entity_id": "e1",
                "target_entity_id": "e2",
                "relationship_type": "WORKS_AT",
                "valid_from": old_date
            }],
            query_timestamp=datetime.utcnow()
        )
        
        gap_types = [g['type'] for g in signals.gaps_detected]
        assert 'stale_data' in gap_types, f"Expected stale_data gap, got {gap_types}"


class TestSufficiencySignals:
    """Test SufficiencySignals dataclass"""
    
    def test_to_dict(self):
        """to_dict should return all fields"""
        signals = SufficiencySignals(
            coverage=0.75,
            freshness=0.80,
            source_agreement=0.60,
            relationship_density=0.40,
            overall_confidence=0.65,
            gaps_detected=[{'type': 'missing_entity', 'entity_name': 'Test'}]
        )
        
        d = signals.to_dict()
        assert 'coverage' in d
        assert 'freshness' in d
        assert 'source_agreement' in d
        assert 'relationship_density' in d
        assert 'overall_confidence' in d
        assert 'gaps_detected' in d
        assert d['coverage'] == 0.75
