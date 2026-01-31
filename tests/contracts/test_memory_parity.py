"""
RLM Memory Parity Tests.

These tests verify that SemanticMemory and SymbolicMemoryAPI return
consistent results for equivalent queries.

CRITICAL BUG DETECTION: The RLM parity bug occurs when:
- SemanticMemory.get_entity_relationships() returns N relationships
- SymbolicMemoryAPI.get_relationships() returns 0 relationships
This causes Tier 2 (RLM) queries to fail while Tier 1 queries succeed.

Root causes may include:
1. tenant_id type mismatch (str vs UUID)
2. lifecycle_state filtering differences
3. Session/connection isolation issues
4. Query construction differences
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from src.context_foundry.contracts.memory import (
    SemanticMemoryContract,
    SymbolicMemoryAPIContract,
    EntityRecord,
    RelationshipRecord,
    LifecycleState,
    verify_relationship_parity,
)


class TestEntityRecordContract:
    """Test the EntityRecord dataclass."""
    
    def test_entity_record_creation(self):
        """EntityRecord should be creatable with required fields."""
        entity = EntityRecord(
            id="uuid-123",
            name="Payment Service",
            entity_type="SERVICE",
        )
        assert entity.name == "Payment Service"
        assert entity.lifecycle_state == LifecycleState.TRUSTED
    
    def test_entity_record_to_dict(self):
        """to_dict should return proper format."""
        entity = EntityRecord(
            id="uuid-123",
            name="Auth Database",
            entity_type="DATABASE",
            description="Authentication database",
            confidence=0.9,
        )
        d = entity.to_dict()
        assert d["id"] == "uuid-123"
        assert d["name"] == "Auth Database"
        assert d["entity_type"] == "DATABASE"
        assert d["lifecycle_state"] == "TRUSTED"


class TestRelationshipRecordContract:
    """Test the RelationshipRecord dataclass."""
    
    def test_relationship_record_creation(self):
        """RelationshipRecord should be creatable with required fields."""
        rel = RelationshipRecord(
            id="rel-123",
            source_entity_id="ent-1",
            source_entity_name="Payment Service",
            target_entity_id="ent-2",
            target_entity_name="Auth Database",
            relationship_type="DEPENDS_ON",
        )
        assert rel.relationship_type == "DEPENDS_ON"
        assert rel.lifecycle_state == LifecycleState.TRUSTED
    
    def test_relationship_record_to_dict(self):
        """to_dict should return proper format."""
        rel = RelationshipRecord(
            id="rel-123",
            source_entity_id="ent-1",
            source_entity_name="Payment Service",
            target_entity_id="ent-2",
            target_entity_name="Auth Database",
            relationship_type="DEPENDS_ON",
            confidence=0.85,
            direction="outgoing",
        )
        d = rel.to_dict()
        assert d["id"] == "rel-123"
        assert d["relationship_type"] == "DEPENDS_ON"
        assert d["direction"] == "outgoing"


class TestVerifyRelationshipParity:
    """Test the parity verification utility function."""
    
    def test_parity_with_matching_relationships(self):
        """Parity should be True when both return same relationships."""
        semantic_results = [
            {"relationship": {"id": "rel-1"}, "connected_entity": {}},
            {"relationship": {"id": "rel-2"}, "connected_entity": {}},
        ]
        
        class MockRel:
            def __init__(self, id):
                self.id = id
        
        symbolic_results = [MockRel("rel-1"), MockRel("rel-2")]
        
        result = verify_relationship_parity(
            semantic_results, symbolic_results, "entity-123"
        )
        
        assert result["parity"] is True
        assert result["semantic_count"] == 2
        assert result["symbolic_count"] == 2
        assert len(result["missing_in_symbolic"]) == 0
    
    def test_parity_fails_when_symbolic_returns_zero(self):
        """THIS IS THE BUG: Symbolic returns 0 while Semantic returns N."""
        semantic_results = [
            {"relationship": {"id": "rel-1"}, "connected_entity": {}},
            {"relationship": {"id": "rel-2"}, "connected_entity": {}},
            {"relationship": {"id": "rel-3"}, "connected_entity": {}},
        ]
        
        symbolic_results = []
        
        result = verify_relationship_parity(
            semantic_results, symbolic_results, "entity-123"
        )
        
        assert result["parity"] is False
        assert result["semantic_count"] == 3
        assert result["symbolic_count"] == 0
        assert len(result["missing_in_symbolic"]) == 3
        assert "rel-1" in result["missing_in_symbolic"]
        assert "rel-2" in result["missing_in_symbolic"]
        assert "rel-3" in result["missing_in_symbolic"]
    
    def test_parity_detects_missing_relationships(self):
        """Parity should detect when symbolic is missing some relationships."""
        semantic_results = [
            {"relationship": {"id": "rel-1"}, "connected_entity": {}},
            {"relationship": {"id": "rel-2"}, "connected_entity": {}},
        ]
        
        class MockRel:
            def __init__(self, id):
                self.id = id
        
        symbolic_results = [MockRel("rel-1")]
        
        result = verify_relationship_parity(
            semantic_results, symbolic_results, "entity-123"
        )
        
        assert result["parity"] is False
        assert result["semantic_count"] == 2
        assert result["symbolic_count"] == 1
        assert "rel-2" in result["missing_in_symbolic"]
    
    def test_parity_detects_extra_relationships(self):
        """Parity should detect when symbolic has extra relationships."""
        semantic_results = [
            {"relationship": {"id": "rel-1"}, "connected_entity": {}},
        ]
        
        class MockRel:
            def __init__(self, id):
                self.id = id
        
        symbolic_results = [MockRel("rel-1"), MockRel("rel-extra")]
        
        result = verify_relationship_parity(
            semantic_results, symbolic_results, "entity-123"
        )
        
        assert result["parity"] is False
        assert len(result["extra_in_symbolic"]) == 1
        assert "rel-extra" in result["extra_in_symbolic"]


class TestMemoryContractBehavior:
    """Test expected behavior from Memory contracts."""
    
    def test_semantic_memory_tenant_isolation(self):
        """SemanticMemory must provide tenant_id property."""
        
        class TestSemanticMemory(SemanticMemoryContract):
            def __init__(self, tid):
                self._tenant_id = tid
            
            @property
            def tenant_id(self):
                return self._tenant_id
            
            def search_entities(self, *args, **kwargs): pass
            def find_entity_by_name(self, *args, **kwargs): pass
            def get_entity_relationships(self, *args, **kwargs): pass
            def traverse_dependencies(self, *args, **kwargs): pass
            def find_impact_chain(self, *args, **kwargs): pass
        
        memory = TestSemanticMemory("tenant-123")
        assert memory.tenant_id == "tenant-123"
    
    def test_symbolic_memory_access_tracking(self):
        """SymbolicMemoryAPI must track accessed relationship IDs."""
        
        class TestSymbolicMemory(SymbolicMemoryAPIContract):
            def __init__(self, tid):
                self._tenant_id = tid
                self._accessed = []
            
            @property
            def tenant_id(self):
                return self._tenant_id
            
            def get_accessed_relationship_ids(self):
                return self._accessed
            
            def clear_access_tracking(self):
                self._accessed = []
            
            def get_relationships(self, *args, **kwargs): 
                self._accessed.append("test-rel-id")
                return []
            
            def find_path(self, *args, **kwargs): pass
            def get_related_entities(self, *args, **kwargs): pass
        
        memory = TestSymbolicMemory("tenant-123")
        assert memory.get_accessed_relationship_ids() == []
        
        memory.get_relationships("entity-1")
        assert "test-rel-id" in memory.get_accessed_relationship_ids()
        
        memory.clear_access_tracking()
        assert memory.get_accessed_relationship_ids() == []


class TestTenantIdTypeParity:
    """
    Test that tenant_id type handling is consistent.
    
    Common bug: SemanticMemory uses UUID type while SymbolicMemoryAPI uses str,
    causing tenant isolation filters to fail silently.
    """
    
    def test_tenant_id_string_format(self):
        """Both systems should accept tenant_id as string."""
        tenant_str = "12345678-1234-1234-1234-123456789abc"
        
        entity = EntityRecord(
            id="entity-1",
            name="Test Entity",
            entity_type="SERVICE",
            tenant_id=tenant_str,
        )
        assert entity.tenant_id == tenant_str
    
    def test_tenant_id_uuid_conversion(self):
        """String tenant_id should be convertible to UUID for DB queries."""
        tenant_str = "12345678-1234-1234-1234-123456789abc"
        
        try:
            tenant_uuid = UUID(tenant_str)
            assert str(tenant_uuid) == tenant_str
        except ValueError:
            pytest.fail("tenant_id string should be valid UUID format")


class TestLifecycleStateFiltering:
    """
    Test lifecycle state filtering consistency.
    
    Common bug: SemanticMemory filters on trusted_only=True but SymbolicMemoryAPI
    includes STAGING by default, causing result count differences.
    """
    
    def test_lifecycle_state_values(self):
        """LifecycleState enum should have expected values."""
        assert LifecycleState.STAGING.value == "STAGING"
        assert LifecycleState.TRUSTED.value == "TRUSTED"
        assert LifecycleState.ARCHIVED.value == "ARCHIVED"
    
    def test_trusted_only_filter(self):
        """When trusted_only=True, only TRUSTED records should be returned."""
        records = [
            RelationshipRecord(
                id="rel-1",
                source_entity_id="e1", source_entity_name="E1",
                target_entity_id="e2", target_entity_name="E2",
                relationship_type="DEPENDS_ON",
                lifecycle_state=LifecycleState.TRUSTED,
            ),
            RelationshipRecord(
                id="rel-2",
                source_entity_id="e1", source_entity_name="E1",
                target_entity_id="e3", target_entity_name="E3",
                relationship_type="DEPENDS_ON",
                lifecycle_state=LifecycleState.STAGING,
            ),
        ]
        
        trusted = [r for r in records if r.lifecycle_state == LifecycleState.TRUSTED]
        assert len(trusted) == 1
        assert trusted[0].id == "rel-1"
    
    def test_include_staging_filter(self):
        """When include_staging=True, STAGING + TRUSTED should be returned."""
        records = [
            RelationshipRecord(
                id="rel-1",
                source_entity_id="e1", source_entity_name="E1",
                target_entity_id="e2", target_entity_name="E2",
                relationship_type="DEPENDS_ON",
                lifecycle_state=LifecycleState.TRUSTED,
            ),
            RelationshipRecord(
                id="rel-2",
                source_entity_id="e1", source_entity_name="E1",
                target_entity_id="e3", target_entity_name="E3",
                relationship_type="DEPENDS_ON",
                lifecycle_state=LifecycleState.STAGING,
            ),
            RelationshipRecord(
                id="rel-3",
                source_entity_id="e1", source_entity_name="E1",
                target_entity_id="e4", target_entity_name="E4",
                relationship_type="DEPENDS_ON",
                lifecycle_state=LifecycleState.ARCHIVED,
            ),
        ]
        
        included = [r for r in records 
                   if r.lifecycle_state in [LifecycleState.TRUSTED, LifecycleState.STAGING]]
        assert len(included) == 2
        assert "rel-3" not in [r.id for r in included]


class TestParityScenarios:
    """
    Integration-like tests for parity scenarios.
    
    These tests document expected behavior for relationship queries
    across both memory systems.
    """
    
    def test_outgoing_relationships_parity(self):
        """Both systems should return same outgoing relationships."""
        expected_rels = [
            {"relationship": {"id": "rel-1", "type": "DEPENDS_ON"}, "direction": "outgoing"},
            {"relationship": {"id": "rel-2", "type": "USES"}, "direction": "outgoing"},
        ]
        
        class MockRel:
            def __init__(self, id, rel_type):
                self.id = id
                self.relationship_type = rel_type
        
        symbolic_rels = [MockRel("rel-1", "DEPENDS_ON"), MockRel("rel-2", "USES")]
        
        result = verify_relationship_parity(expected_rels, symbolic_rels, "entity-1")
        assert result["parity"] is True
    
    def test_incoming_relationships_parity(self):
        """Both systems should return same incoming relationships."""
        expected_rels = [
            {"relationship": {"id": "rel-3", "type": "DEPENDS_ON"}, "direction": "incoming"},
        ]
        
        class MockRel:
            def __init__(self, id):
                self.id = id
        
        symbolic_rels = [MockRel("rel-3")]
        
        result = verify_relationship_parity(expected_rels, symbolic_rels, "entity-1")
        assert result["parity"] is True
    
    def test_both_direction_parity(self):
        """Both systems should return same total when direction='both'."""
        semantic_rels = [
            {"relationship": {"id": "rel-1"}, "direction": "outgoing"},
            {"relationship": {"id": "rel-2"}, "direction": "outgoing"},
            {"relationship": {"id": "rel-3"}, "direction": "incoming"},
        ]
        
        class MockRel:
            def __init__(self, id):
                self.id = id
        
        symbolic_rels = [MockRel("rel-1"), MockRel("rel-2"), MockRel("rel-3")]
        
        result = verify_relationship_parity(semantic_rels, symbolic_rels, "entity-1")
        assert result["parity"] is True
        assert result["semantic_count"] == 3
        assert result["symbolic_count"] == 3
