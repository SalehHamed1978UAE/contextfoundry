"""
Smoke tests for anchor organization filtering and edge ranking.

Tests the EDGE_RANK and filter_by_anchor_organization in directed_retriever.py.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from context_foundry.agents.directed_retriever import (
    EDGE_RANK,
    DEFAULT_EDGE_RANK,
    get_edge_rank,
    filter_by_anchor_organization
)


class TestEdgeRank:
    """Test the edge rank priority system."""
    
    def test_holds_position_highest_rank(self):
        """HOLDS_POSITION should have the highest rank."""
        rank = get_edge_rank('HOLDS_POSITION')
        assert rank == 100
    
    def test_works_for_lower_than_holds_position(self):
        """WORKS_FOR should rank lower than HOLDS_POSITION."""
        holds_position_rank = get_edge_rank('HOLDS_POSITION')
        works_for_rank = get_edge_rank('WORKS_FOR')
        
        assert holds_position_rank > works_for_rank
    
    def test_unknown_type_returns_default(self):
        """Unknown relationship types should return default rank."""
        rank = get_edge_rank('UNKNOWN_RELATIONSHIP_TYPE')
        assert rank == DEFAULT_EDGE_RANK
    
    def test_case_insensitive(self):
        """Relationship type lookup should be case insensitive."""
        upper_rank = get_edge_rank('HOLDS_POSITION')
        lower_rank = get_edge_rank('holds_position')
        
        assert upper_rank == lower_rank
    
    def test_edge_rank_dict_has_expected_types(self):
        """EDGE_RANK should contain expected relationship types."""
        expected_types = [
            'HOLDS_POSITION', 'CEO_OF', 'WORKS_FOR', 'WORKS_AT',
            'INVESTED_IN', 'REPORTS_TO', 'SUPPLIES_TO'
        ]
        
        for rel_type in expected_types:
            assert rel_type in EDGE_RANK


class TestFilterByAnchorOrganization:
    """Test the anchor organization filtering."""
    
    def test_filters_out_boeing_when_anchor_is_nexus(self):
        """Should filter out Boeing entities when anchor is Nexus Industries."""
        entities = [
            {'name': 'John Smith', 'organization': 'Boeing'},
            {'name': 'Jane Doe', 'organization': 'Nexus Industries'},
            {'name': 'Bob Wilson', 'organization': 'Nexus Industries'}
        ]
        
        filtered = filter_by_anchor_organization(entities, 'Nexus Industries')
        
        org_names = [e.get('organization', '').lower() for e in filtered]
        assert 'boeing' not in org_names
        assert all('nexus' in org for org in org_names if org)
    
    def test_keeps_nexus_entities(self):
        """Should keep entities belonging to the anchor organization."""
        entities = [
            {'name': 'Jane Doe', 'organization': 'Nexus Industries'},
            {'name': 'Bob Wilson', 'organization': 'Nexus Industries'}
        ]
        
        filtered = filter_by_anchor_organization(entities, 'Nexus Industries')
        
        assert len(filtered) == 2
    
    def test_keeps_generic_entities(self):
        """Should keep entities with no organization specified."""
        entities = [
            {'name': 'John Smith', 'organization': 'Boeing'},
            {'name': 'Generic Person'},
            {'name': 'Another Generic', 'organization': ''}
        ]
        
        filtered = filter_by_anchor_organization(entities, 'Nexus Industries')
        
        names = [e['name'] for e in filtered]
        assert 'Generic Person' in names
        assert 'Another Generic' in names
        assert 'John Smith' not in names
    
    def test_empty_anchor_returns_all(self):
        """Empty anchor org should return all entities."""
        entities = [
            {'name': 'John', 'organization': 'Boeing'},
            {'name': 'Jane', 'organization': 'Nexus'}
        ]
        
        filtered = filter_by_anchor_organization(entities, '')
        
        assert len(filtered) == 2
    
    def test_edge_rank_ordering(self):
        """Results should be ordered by edge rank when prefer_higher_rank=True."""
        entities = [
            {'name': 'Worker', 'organization': 'Nexus', 'discovered_via': 'WORKS_FOR'},
            {'name': 'Executive', 'organization': 'Nexus', 'discovered_via': 'HOLDS_POSITION'},
            {'name': 'Member', 'organization': 'Nexus', 'discovered_via': 'MEMBER_OF'}
        ]
        
        filtered = filter_by_anchor_organization(entities, 'Nexus', prefer_higher_rank=True)
        
        assert len(filtered) == 3
        assert filtered[0]['discovered_via'] == 'HOLDS_POSITION'
    
    def test_partial_match_anchor(self):
        """Should match on partial organization name."""
        entities = [
            {'name': 'John', 'organization': 'Nexus Industries Inc.'},
            {'name': 'Jane', 'organization': 'Boeing Corp'}
        ]
        
        filtered = filter_by_anchor_organization(entities, 'Nexus')
        
        assert len(filtered) == 1
        assert filtered[0]['name'] == 'John'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
