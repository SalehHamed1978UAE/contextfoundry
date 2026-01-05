"""
Memory Contracts - Defines interfaces for Semantic and Symbolic Memory systems.

These contracts ensure parity between:
- SemanticMemory (used by Tier 1 queries via RetrievalAgent)
- SymbolicMemoryAPI (used by Tier 2 queries via RLM)

CRITICAL: Both systems must return consistent results for the same entity/relationship
queries. The RLM parity bug occurs when SymbolicMemoryAPI returns 0 relationships
while SemanticMemory returns correct data.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from enum import Enum
import uuid


class LifecycleState(str, Enum):
    """Entity/Relationship lifecycle states."""
    STAGING = "STAGING"
    TRUSTED = "TRUSTED"
    ARCHIVED = "ARCHIVED"
    DEPRECATED = "DEPRECATED"


@dataclass
class EntityRecord:
    """
    Canonical entity record structure.
    
    This is the contract for entity data - both SemanticMemory and SymbolicMemoryAPI
    must use this format to ensure parity.
    """
    id: str
    name: str
    entity_type: str
    description: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    lifecycle_state: LifecycleState = LifecycleState.TRUSTED
    tenant_id: Optional[str] = None
    created_at: Optional[datetime] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "properties": self.properties,
            "confidence": self.confidence,
            "lifecycle_state": self.lifecycle_state.value,
            "tenant_id": self.tenant_id,
        }


@dataclass
class RelationshipRecord:
    """
    Canonical relationship record structure.
    
    Both memory systems must return relationships in this format.
    """
    id: str
    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    relationship_type: str
    confidence: float = 0.5
    lifecycle_state: LifecycleState = LifecycleState.TRUSTED
    properties: Dict[str, Any] = field(default_factory=dict)
    direction: Optional[str] = None
    tenant_id: Optional[str] = None
    source_document_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "source_entity_name": self.source_entity_name,
            "target_entity_id": self.target_entity_id,
            "target_entity_name": self.target_entity_name,
            "relationship_type": self.relationship_type,
            "confidence": self.confidence,
            "lifecycle_state": self.lifecycle_state.value,
            "properties": self.properties,
            "direction": self.direction,
        }


class SemanticMemoryContract(ABC):
    """
    Abstract contract for Semantic Memory (Knowledge Graph layer).
    
    This is the primary memory system used by RetrievalAgent for Tier 1 queries.
    It provides entity search, relationship traversal, and impact chain analysis.
    """
    
    @property
    @abstractmethod
    def tenant_id(self) -> Optional[str]:
        """Return the tenant ID for tenant-scoped queries."""
        pass
    
    @abstractmethod
    def search_entities(
        self,
        query_text: str,
        entity_types: Optional[List[str]] = None,
        trusted_only: bool = True,
        limit: int = 10,
        as_of_date: Optional[datetime] = None
    ) -> List[Any]:
        """
        Search for entities by name or description.
        
        Args:
            query_text: Search query (entity name or partial match)
            entity_types: Filter by entity types (e.g., ['SERVICE', 'DATABASE'])
            trusted_only: If True, only return TRUSTED entities
            limit: Maximum results
            as_of_date: Optional temporal query date
            
        Returns:
            List of Entity objects
            
        Contract:
            - Must support exact and partial name matching
            - Must respect tenant isolation
            - Must filter by lifecycle_state when trusted_only=True
        """
        pass
    
    @abstractmethod
    def find_entity_by_name(
        self,
        name: str,
        entity_type: Optional[str] = None
    ) -> Optional[Any]:
        """
        Find a single entity by exact name match.
        
        Args:
            name: Exact entity name (case-insensitive)
            entity_type: Optional type filter
            
        Returns:
            Entity object or None
        """
        pass
    
    @abstractmethod
    def get_entity_relationships(
        self,
        entity_id: uuid.UUID,
        relationship_types: Optional[List[str]] = None,
        direction: str = "both",
        trusted_only: bool = True,
        max_depth: int = 1,
        as_of_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get relationships for an entity.
        
        Args:
            entity_id: Entity UUID
            relationship_types: Filter by relationship types
            direction: 'outgoing', 'incoming', or 'both'
            trusted_only: Only return TRUSTED relationships
            max_depth: Traversal depth (currently only depth=1 supported)
            as_of_date: Optional temporal query date
            
        Returns:
            List of dicts with 'relationship' and 'connected_entity' keys
            
        Contract:
            - MUST return same relationships as SymbolicMemoryAPI.get_relationships
            - Must respect tenant isolation
            - Direction 'both' returns union of incoming + outgoing
        """
        pass
    
    @abstractmethod
    def traverse_dependencies(
        self,
        entity_id: uuid.UUID,
        relationship_type: str = "DEPENDS_ON",
        direction: str = "outgoing",
        max_depth: int = 3,
        as_of_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Traverse dependency graph from an entity.
        
        Args:
            entity_id: Starting entity UUID
            relationship_type: Relationship type to traverse
            direction: 'outgoing' or 'incoming'
            max_depth: Maximum traversal depth
            as_of_date: Optional temporal query date
            
        Returns:
            List of dicts with 'entity', 'relationship', 'depth', 'path'
            
        Contract:
            - Must use BFS or DFS to traverse graph
            - Must track visited entities to avoid cycles
            - Must respect tenant isolation
        """
        pass
    
    @abstractmethod
    def find_impact_chain(
        self,
        entity_name: str,
        max_depth: int = 3
    ) -> Dict:
        """
        Find what services/components are impacted if this entity fails.
        
        This is the core blast radius analysis function.
        
        Args:
            entity_name: Name of the failing entity
            max_depth: Maximum traversal depth
            
        Returns:
            Dict with 'entity', 'impacted' (list of affected entities)
            
        Contract:
            - Traverses DEPENDS_ON in 'incoming' direction
            - Returns all entities that depend on the target (directly or transitively)
        """
        pass


class SymbolicMemoryAPIContract(ABC):
    """
    Abstract contract for Symbolic Memory API (RLM REPL layer).
    
    This is the memory interface exposed to RLM for Tier 2 complex queries.
    It must maintain parity with SemanticMemory for relationship queries.
    """
    
    @property
    @abstractmethod
    def tenant_id(self) -> str:
        """Return the tenant ID for tenant-scoped queries."""
        pass
    
    @abstractmethod
    def get_accessed_relationship_ids(self) -> List[str]:
        """Returns list of relationship IDs accessed during this session."""
        pass
    
    @abstractmethod
    def clear_access_tracking(self) -> None:
        """Clear the accessed relationship tracking."""
        pass
    
    @abstractmethod
    def get_relationships(
        self,
        entity_id: str,
        direction: str = "both",
        relationship_type: Optional[str] = None,
        include_staging: bool = True
    ) -> List[Any]:
        """
        Get relationships for an entity.
        
        Args:
            entity_id: Entity UUID string
            direction: 'outgoing', 'incoming', or 'both'
            relationship_type: Optional type filter
            include_staging: Include STAGING relationships
            
        Returns:
            List of Relationship objects
            
        Contract:
            - MUST return same relationships as SemanticMemory.get_entity_relationships
              (when comparing with equivalent parameters)
            - Must track accessed relationship IDs
            - Must respect tenant isolation
        """
        pass
    
    @abstractmethod
    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 3
    ) -> List[Any]:
        """
        Find relationship paths between two entities using BFS.
        
        Args:
            source_id: Source entity UUID string
            target_id: Target entity UUID string
            max_depth: Maximum path length
            
        Returns:
            List of Path objects (may be empty)
            
        Contract:
            - Must find shortest paths
            - Must respect tenant isolation
        """
        pass
    
    @abstractmethod
    def get_related_entities(
        self,
        entity_id: str,
        relationship_type: str,
        include_staging: bool = True
    ) -> List[Any]:
        """
        Get entities connected by specific relationship type.
        
        Args:
            entity_id: Entity UUID string
            relationship_type: Relationship type to filter
            include_staging: Include STAGING relationships
            
        Returns:
            List of EntitySummary objects
        """
        pass


def verify_relationship_parity(
    semantic_relationships: List[Dict],
    symbolic_relationships: List[Any],
    entity_id: str
) -> Dict[str, Any]:
    """
    Utility function to verify parity between SemanticMemory and SymbolicMemoryAPI.
    
    This function helps catch the RLM parity bug where SymbolicMemoryAPI
    returns 0 relationships while SemanticMemory returns correct data.
    
    Args:
        semantic_relationships: Results from SemanticMemory.get_entity_relationships
        symbolic_relationships: Results from SymbolicMemoryAPI.get_relationships
        entity_id: The entity ID queried
        
    Returns:
        Dict with 'parity': bool, 'semantic_count': int, 'symbolic_count': int,
        'missing_in_symbolic': list, 'extra_in_symbolic': list
    """
    semantic_rel_ids: Set[str] = set()
    for rel_info in semantic_relationships:
        rel = rel_info.get("relationship", {})
        if isinstance(rel, dict) and "id" in rel:
            semantic_rel_ids.add(str(rel["id"]))
    
    symbolic_rel_ids: Set[str] = set()
    for rel in symbolic_relationships:
        if hasattr(rel, 'id'):
            symbolic_rel_ids.add(str(rel.id))
        elif isinstance(rel, dict) and "id" in rel:
            symbolic_rel_ids.add(str(rel["id"]))
    
    missing_in_symbolic = semantic_rel_ids - symbolic_rel_ids
    extra_in_symbolic = symbolic_rel_ids - semantic_rel_ids
    
    return {
        "parity": len(missing_in_symbolic) == 0 and len(extra_in_symbolic) == 0,
        "semantic_count": len(semantic_rel_ids),
        "symbolic_count": len(symbolic_rel_ids),
        "missing_in_symbolic": list(missing_in_symbolic),
        "extra_in_symbolic": list(extra_in_symbolic),
        "entity_id": entity_id,
    }
