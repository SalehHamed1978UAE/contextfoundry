"""
SymbolicMemoryAPI - Relationship and graph operations for RLM REPL.

Wraps the relationships table to provide relationship queries,
path finding, and graph traversal.
"""

from datetime import datetime
from typing import Optional, List, Set
from collections import deque
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from ..schemas import (
    EntitySummary,
    Relationship as RelationshipSchema,
    PathStep,
    Path,
    SubGraph,
    LifecycleState,
    StaleEntityError,
)


class SymbolicMemoryAPI:
    """
    Exposes symbolic memory (relationships, rules) to RLM REPL environment.
    
    All methods are tenant-scoped and track accessed relationship IDs
    for progress tracking.
    """
    
    def __init__(self, tenant_id: str, session: Session):
        self._tenant_id = tenant_id
        self._session = session
        self._accessed_relationship_ids: List[str] = []
    
    def get_accessed_relationship_ids(self) -> List[str]:
        """Returns list of relationship IDs accessed during this session."""
        return list(set(self._accessed_relationship_ids))
    
    def clear_access_tracking(self):
        """Clear the accessed relationship tracking."""
        self._accessed_relationship_ids = []
    
    def get_relationships(
        self, 
        entity_id: str,
        direction: str = "both",
        relationship_type: str = None,
        include_staging: bool = True
    ) -> List[RelationshipSchema]:
        """
        Get relationships for an entity.
        
        Args:
            entity_id: Entity UUID
            direction: "outgoing", "incoming", or "both" (default)
            relationship_type: Filter by type (e.g., "DEPENDS_ON")
            include_staging: Include STAGING relationships (default True)
        
        Returns:
            List of Relationship objects
        
        Raises:
            StaleEntityError: If entity no longer exists
        """
        from src.context_foundry.models.schema import Entity, Relationship
        
        entity = self._session.query(Entity).filter(
            Entity.id == entity_id,
            Entity.tenant_id == self._tenant_id
        ).first()
        
        if not entity:
            raise StaleEntityError(entity_id)
        
        lifecycle_filter = [LifecycleState.TRUSTED]
        if include_staging:
            lifecycle_filter.append(LifecycleState.STAGING)
        
        if direction == "outgoing":
            filter_clause = Relationship.source_id == entity_id
        elif direction == "incoming":
            filter_clause = Relationship.target_id == entity_id
        else:
            filter_clause = or_(
                Relationship.source_id == entity_id,
                Relationship.target_id == entity_id
            )
        
        query = self._session.query(Relationship).filter(
            filter_clause,
            Relationship.tenant_id == self._tenant_id,
            Relationship.lifecycle_state.in_(lifecycle_filter)
        )
        
        if relationship_type:
            query = query.filter(
                Relationship.relationship_type == relationship_type.upper()
            )
        
        relationships = query.order_by(Relationship.confidence.desc()).all()
        
        results = []
        for rel in relationships:
            self._accessed_relationship_ids.append(str(rel.id))
            
            source_doc_ids = []
            if rel.source_document_id:
                source_doc_ids.append(rel.source_document_id)
            
            results.append(RelationshipSchema(
                id=str(rel.id),
                source_entity_id=str(rel.source_id),
                source_entity_name=rel.source_entity.name if rel.source_entity else "Unknown",
                target_entity_id=str(rel.target_id),
                target_entity_name=rel.target_entity.name if rel.target_entity else "Unknown",
                relationship_type=rel.relationship_type,
                confidence=rel.confidence or 0.5,
                lifecycle_state=LifecycleState(rel.lifecycle_state.value),
                properties=rel.properties or {},
                created_at=rel.created_at or datetime.utcnow(),
                source_document_ids=source_doc_ids
            ))
        
        return results
    
    def find_path(
        self, 
        source_id: str, 
        target_id: str,
        max_depth: int = 3
    ) -> List[Path]:
        """
        Find relationship paths between two entities using BFS.
        
        Args:
            source_id: Source entity UUID
            target_id: Target entity UUID
            max_depth: Maximum path length (default 3)
        
        Returns:
            List of Path objects (may be empty if no path exists)
        
        Raises:
            StaleEntityError: If source or target entity no longer exists
        """
        from src.context_foundry.models.schema import Entity, Relationship
        
        source = self._session.query(Entity).filter(
            Entity.id == source_id,
            Entity.tenant_id == self._tenant_id
        ).first()
        
        if not source:
            raise StaleEntityError(source_id)
        
        target = self._session.query(Entity).filter(
            Entity.id == target_id,
            Entity.tenant_id == self._tenant_id
        ).first()
        
        if not target:
            raise StaleEntityError(target_id)
        
        if source_id == target_id:
            return [Path(
                source_entity_id=str(source.id),
                source_entity_name=source.name,
                target_entity_id=str(target.id),
                target_entity_name=target.name,
                steps=[],
                total_hops=0,
                min_confidence=1.0
            )]
        
        queue = deque([(source_id, [], 1.0)])
        visited = {source_id}
        paths_found = []
        
        while queue and len(paths_found) < 5:
            current_id, path_so_far, min_conf = queue.popleft()
            
            if len(path_so_far) >= max_depth:
                continue
            
            rels = self._session.query(Relationship).filter(
                or_(
                    Relationship.source_id == current_id,
                    Relationship.target_id == current_id
                ),
                Relationship.tenant_id == self._tenant_id,
                Relationship.lifecycle_state.in_([
                    LifecycleState.STAGING, 
                    LifecycleState.TRUSTED
                ])
            ).all()
            
            for rel in rels:
                next_id = str(rel.target_id) if str(rel.source_id) == current_id else str(rel.source_id)
                
                if next_id in visited:
                    continue
                
                next_entity = self._session.query(Entity).filter(
                    Entity.id == next_id
                ).first()
                
                if not next_entity:
                    continue
                
                self._accessed_relationship_ids.append(str(rel.id))
                
                new_step = PathStep(
                    entity_id=next_id,
                    entity_name=next_entity.name,
                    entity_type=next_entity.entity_type,
                    relationship_type=rel.relationship_type,
                    relationship_id=str(rel.id)
                )
                
                new_path = path_so_far + [new_step]
                new_min_conf = min(min_conf, rel.confidence or 0.5)
                
                if next_id == target_id:
                    paths_found.append(Path(
                        source_entity_id=str(source.id),
                        source_entity_name=source.name,
                        target_entity_id=str(target.id),
                        target_entity_name=target.name,
                        steps=new_path,
                        total_hops=len(new_path),
                        min_confidence=new_min_conf
                    ))
                else:
                    visited.add(next_id)
                    queue.append((next_id, new_path, new_min_conf))
        
        return sorted(paths_found, key=lambda p: (-p.min_confidence, p.total_hops))
    
    def get_related_entities(
        self, 
        entity_id: str,
        relationship_type: str,
        include_staging: bool = True
    ) -> List[EntitySummary]:
        """
        Get entities connected by specific relationship type.
        
        Args:
            entity_id: Entity UUID
            relationship_type: Relationship type filter
            include_staging: Include STAGING entities (default True)
        
        Returns:
            List of EntitySummary objects
        
        Raises:
            StaleEntityError: If entity no longer exists
        """
        from src.context_foundry.models.schema import Entity, Relationship
        
        entity = self._session.query(Entity).filter(
            Entity.id == entity_id,
            Entity.tenant_id == self._tenant_id
        ).first()
        
        if not entity:
            raise StaleEntityError(entity_id)
        
        lifecycle_filter = [LifecycleState.TRUSTED]
        if include_staging:
            lifecycle_filter.append(LifecycleState.STAGING)
        
        rels = self._session.query(Relationship).filter(
            or_(
                Relationship.source_id == entity_id,
                Relationship.target_id == entity_id
            ),
            Relationship.relationship_type == relationship_type.upper(),
            Relationship.tenant_id == self._tenant_id,
            Relationship.lifecycle_state.in_(lifecycle_filter)
        ).all()
        
        related_ids = set()
        for rel in rels:
            self._accessed_relationship_ids.append(str(rel.id))
            if str(rel.source_id) == entity_id:
                related_ids.add(str(rel.target_id))
            else:
                related_ids.add(str(rel.source_id))
        
        if not related_ids:
            return []
        
        entities = self._session.query(Entity).filter(
            Entity.id.in_(related_ids),
            Entity.tenant_id == self._tenant_id,
            Entity.lifecycle_state.in_(lifecycle_filter)
        ).all()
        
        results = []
        for e in entities:
            rel_count = self._session.query(func.count(Relationship.id)).filter(
                or_(
                    Relationship.source_id == e.id,
                    Relationship.target_id == e.id
                )
            ).scalar() or 0
            
            primary_prop = None
            if e.properties:
                for key in ['status', 'title', 'role', 'description']:
                    if key in e.properties:
                        primary_prop = f"{key}: {e.properties[key]}"
                        break
            
            results.append(EntitySummary(
                id=str(e.id),
                name=e.name,
                entity_type=e.entity_type,
                confidence=e.confidence or 0.5,
                lifecycle_state=LifecycleState(e.lifecycle_state.value),
                created_at=e.created_at or datetime.utcnow(),
                updated_at=e.updated_at or datetime.utcnow(),
                primary_property=primary_prop,
                property_count=len(e.properties) if e.properties else 0,
                relationship_count=rel_count
            ))
        
        return results
    
    def traverse(
        self, 
        start_id: str,
        relationship_types: List[str] = None,
        depth: int = 2,
        max_entities: int = 100
    ) -> SubGraph:
        """
        Traverse graph from starting entity.
        
        Args:
            start_id: Starting entity UUID
            relationship_types: List of relationship types to follow (None = all)
            depth: Maximum traversal depth (default 2)
            max_entities: Maximum entities to return (default 100)
        
        Returns:
            SubGraph object with discovered entities and relationships
        
        Raises:
            StaleEntityError: If start entity no longer exists
        """
        from src.context_foundry.models.schema import Entity, Relationship
        
        start_entity = self._session.query(Entity).filter(
            Entity.id == start_id,
            Entity.tenant_id == self._tenant_id
        ).first()
        
        if not start_entity:
            raise StaleEntityError(start_id)
        
        discovered_entities: List[EntitySummary] = []
        discovered_relationships: List[RelationshipSchema] = []
        visited_entity_ids: Set[str] = {start_id}
        current_level = [start_id]
        actual_depth = 0
        truncated = False
        
        for d in range(depth):
            if len(discovered_entities) >= max_entities:
                truncated = True
                break
            
            next_level = []
            
            for entity_id in current_level:
                query = self._session.query(Relationship).filter(
                    or_(
                        Relationship.source_id == entity_id,
                        Relationship.target_id == entity_id
                    ),
                    Relationship.tenant_id == self._tenant_id,
                    Relationship.lifecycle_state.in_([
                        LifecycleState.STAGING, 
                        LifecycleState.TRUSTED
                    ])
                )
                
                if relationship_types:
                    query = query.filter(
                        Relationship.relationship_type.in_([rt.upper() for rt in relationship_types])
                    )
                
                rels = query.all()
                
                for rel in rels:
                    self._accessed_relationship_ids.append(str(rel.id))
                    
                    source_doc_ids = []
                    if rel.source_document_id:
                        source_doc_ids.append(rel.source_document_id)
                    
                    discovered_relationships.append(RelationshipSchema(
                        id=str(rel.id),
                        source_entity_id=str(rel.source_id),
                        source_entity_name=rel.source_entity.name if rel.source_entity else "Unknown",
                        target_entity_id=str(rel.target_id),
                        target_entity_name=rel.target_entity.name if rel.target_entity else "Unknown",
                        relationship_type=rel.relationship_type,
                        confidence=rel.confidence or 0.5,
                        lifecycle_state=LifecycleState(rel.lifecycle_state.value),
                        properties=rel.properties or {},
                        created_at=rel.created_at or datetime.utcnow(),
                        source_document_ids=source_doc_ids
                    ))
                    
                    next_id = str(rel.target_id) if str(rel.source_id) == entity_id else str(rel.source_id)
                    
                    if next_id not in visited_entity_ids:
                        visited_entity_ids.add(next_id)
                        next_level.append(next_id)
                        
                        next_entity = self._session.query(Entity).filter(
                            Entity.id == next_id
                        ).first()
                        
                        if next_entity:
                            rel_count = self._session.query(func.count(Relationship.id)).filter(
                                or_(
                                    Relationship.source_id == next_entity.id,
                                    Relationship.target_id == next_entity.id
                                )
                            ).scalar() or 0
                            
                            primary_prop = None
                            if next_entity.properties:
                                for key in ['status', 'title', 'role', 'description']:
                                    if key in next_entity.properties:
                                        primary_prop = f"{key}: {next_entity.properties[key]}"
                                        break
                            
                            discovered_entities.append(EntitySummary(
                                id=str(next_entity.id),
                                name=next_entity.name,
                                entity_type=next_entity.entity_type,
                                confidence=next_entity.confidence or 0.5,
                                lifecycle_state=LifecycleState(next_entity.lifecycle_state.value),
                                created_at=next_entity.created_at or datetime.utcnow(),
                                updated_at=next_entity.updated_at or datetime.utcnow(),
                                primary_property=primary_prop,
                                property_count=len(next_entity.properties) if next_entity.properties else 0,
                                relationship_count=rel_count
                            ))
                        
                        if len(discovered_entities) >= max_entities:
                            truncated = True
                            break
                
                if truncated:
                    break
            
            if next_level:
                actual_depth = d + 1
                current_level = next_level
            else:
                break
        
        unique_rels = {r.id: r for r in discovered_relationships}
        
        return SubGraph(
            root_entity_id=str(start_entity.id),
            root_entity_name=start_entity.name,
            entities=discovered_entities[:max_entities],
            relationships=list(unique_rels.values()),
            depth_reached=actual_depth,
            truncated=truncated
        )
    
    def get_rules_for_entity(self, entity_id: str) -> List[dict]:
        """
        Get applicable validation rules for an entity.
        
        Args:
            entity_id: Entity UUID
        
        Returns:
            List of rule dictionaries
        """
        from src.context_foundry.models.schema import Entity, Rule
        
        entity = self._session.query(Entity).filter(
            Entity.id == entity_id,
            Entity.tenant_id == self._tenant_id
        ).first()
        
        if not entity:
            raise StaleEntityError(entity_id)
        
        rules = self._session.query(Rule).filter(
            Rule.is_active == True,
            or_(
                Rule.entity_types.contains([entity.entity_type]),
                Rule.entity_types == None
            )
        ).order_by(Rule.priority).all()
        
        return [rule.to_dict() for rule in rules]
