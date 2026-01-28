"""
CRITICAL: These tests MUST pass before deployment.
Tests the anchor organization filter that prevents Boeing data in Nexus queries.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from context_foundry.agents.directed_retriever import filter_by_anchor_organization


class TestAnchorFilterCritical:
    """Tests that MUST pass to fix Q2 and Q40."""

    def test_boeing_excluded_when_anchor_is_nexus(self):
        """CRITICAL: Boeing entities must be filtered out when querying Nexus."""
        entities = [
            {'name': 'Total Backlog', 'organization': 'Nexus Industries', 'value': '12.4B'},
            {'name': 'Total Backlog', 'organization': 'The Boeing Company', 'value': '11.5B'},
        ]

        filtered = filter_by_anchor_organization(entities, 'Nexus Industries')

        assert len(filtered) == 1, f"Expected 1 entity, got {len(filtered)}"
        assert filtered[0]['organization'] == 'Nexus Industries'
        assert filtered[0]['value'] == '12.4B'

    def test_boeing_cfo_excluded(self):
        """CRITICAL: Boeing's CFO must not appear in Nexus queries."""
        entities = [
            {'name': 'Michael Chang', 'organization': 'Nexus Industries', 'role': 'CFO'},
            {'name': 'Rahul Ghai', 'organization': 'Boeing', 'role': 'CFO'},
            {'name': 'Rahul Ghai', 'organization': 'The Boeing Company', 'role': 'CFO'},
        ]

        filtered = filter_by_anchor_organization(entities, 'Nexus Industries')

        assert len(filtered) == 1, f"Expected 1 CFO, got {len(filtered)}"
        assert filtered[0]['name'] == 'Michael Chang'

        for entity in filtered:
            org = entity.get('organization', '').lower()
            assert 'boeing' not in org, f"Boeing leaked through: {entity}"

    def test_generic_entities_kept(self):
        """Entities without organization should be kept."""
        entities = [
            {'name': 'Generic Metric', 'value': '100'},
            {'name': 'Nexus Metric', 'organization': 'Nexus Industries', 'value': '200'},
            {'name': 'Boeing Metric', 'organization': 'Boeing', 'value': '300'},
        ]

        filtered = filter_by_anchor_organization(entities, 'Nexus Industries')

        assert len(filtered) == 2, "Should keep generic + Nexus, filter Boeing"

    def test_partial_org_match(self):
        """Should match partial organization names."""
        entities = [
            {'name': 'A', 'organization': 'Nexus Industries Inc.'},
            {'name': 'B', 'organization': 'Nexus'},
            {'name': 'C', 'organization': 'Boeing Corporation'},
        ]

        filtered = filter_by_anchor_organization(entities, 'Nexus')

        assert len(filtered) == 2, "Should match 'Nexus' in both Nexus orgs"

    def test_empty_anchor_returns_all(self):
        """Empty anchor should not filter anything."""
        entities = [
            {'name': 'A', 'organization': 'Nexus'},
            {'name': 'B', 'organization': 'Boeing'},
        ]

        filtered = filter_by_anchor_organization(entities, '')
        assert len(filtered) == 2

        filtered = filter_by_anchor_organization(entities, None)
        assert len(filtered) == 2
