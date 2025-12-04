"""
Semantic Memory Layer - Knowledge Graph with Lifecycle States.
Stores entities and relationships with STAGING/TRUSTED/ARCHIVED lifecycle.
"""
from typing import List, Dict, Optional, Tuple
from sqlalchemy import or_, and_, text
from sqlalchemy.orm import Session
import uuid

from ..models.schema import (
    Entity, Relationship, LifecycleState, EntityType, RelationshipType, get_session
)
from ..utils.logger import logger


class SemanticMemory:
    """
    Knowledge Graph memory layer with lifecycle management.
    Only TRUSTED facts are used for reasoning by default.
    """
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()
        logger.info("SemanticMemory initialized")
    
    def add_entity(
        self,
        name: str,
        entity_type: str,
        properties: dict = None,
        description: str = None,
        confidence: float = 0.5,
        source_document_id: str = None,
        source_sentence: str = None,
        lifecycle_state: LifecycleState = LifecycleState.STAGING
    ) -> Entity:
        """Add an entity to the knowledge graph."""
        entity = Entity(
            name=name,
            entity_type=entity_type.upper(),
            properties=properties or {},
            description=description,
            confidence=confidence,
            source_document_id=source_document_id,
            source_sentence=source_sentence,
            lifecycle_state=lifecycle_state
        )
        self.session.add(entity)
        
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to add entity {name}: {e}")
            raise
        
        logger.debug(f"Added entity: {name} [{entity_type}] (state: {lifecycle_state.value})")
        return entity
    
    def add_relationship(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        relationship_type: str,
        properties: dict = None,
        description: str = None,
        confidence: float = 0.5,
        source_document_id: str = None,
        source_sentence: str = None,
        lifecycle_state: LifecycleState = LifecycleState.STAGING
    ) -> Relationship:
        """Add a relationship between entities."""
        rel = Relationship(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type.upper(),
            properties=properties or {},
            description=description,
            confidence=confidence,
            source_document_id=source_document_id,
            source_sentence=source_sentence,
            lifecycle_state=lifecycle_state
        )
        self.session.add(rel)
        
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to add relationship: {e}")
            raise
        
        logger.debug(f"Added relationship: {source_id} -[{relationship_type}]-> {target_id}")
        return rel
    
    def find_entity_by_name(self, name: str, trusted_only: bool = True) -> Optional[Entity]:
        """Find an entity by exact name match."""
        query = self.session.query(Entity).filter(Entity.name == name)
        if trusted_only:
            query = query.filter(Entity.lifecycle_state == LifecycleState.TRUSTED)
        return query.first()
    
    def search_entities(
        self,
        query_text: str,
        entity_types: List[str] = None,
        trusted_only: bool = True,
        limit: int = 10
    ) -> List[Entity]:
        """Search entities by name (case-insensitive contains)."""
        q = self.session.query(Entity).filter(
            Entity.name.ilike(f"%{query_text}%")
        )
        
        if trusted_only:
            q = q.filter(Entity.lifecycle_state == LifecycleState.TRUSTED)
        
        if entity_types:
            normalized_types = [t.upper() if isinstance(t, str) else t for t in entity_types]
            q = q.filter(Entity.entity_type.in_(normalized_types))
        
        results = q.order_by(Entity.confidence.desc()).limit(limit).all()
        logger.debug(f"Entity search '{query_text}': found {len(results)} results")
        return results
    
    def get_entity_relationships(
        self,
        entity_id: uuid.UUID,
        relationship_types: List[str] = None,
        direction: str = "both",
        trusted_only: bool = True,
        max_depth: int = 1
    ) -> List[Dict]:
        """
        Get relationships for an entity.
        direction: 'outgoing', 'incoming', or 'both'
        Returns list of dicts with relationship and connected entity info.
        """
        results = []
        normalized_types = None
        if relationship_types:
            normalized_types = [t.upper() if isinstance(t, str) else t for t in relationship_types]
        
        if direction in ["outgoing", "both"]:
            q = self.session.query(Relationship).filter(
                Relationship.source_id == entity_id
            )
            if trusted_only:
                q = q.filter(Relationship.lifecycle_state == LifecycleState.TRUSTED)
            if normalized_types:
                q = q.filter(Relationship.relationship_type.in_(normalized_types))
            
            for rel in q.all():
                target = self.session.query(Entity).get(rel.target_id)
                if target and (not trusted_only or target.lifecycle_state == LifecycleState.TRUSTED):
                    results.append({
                        "relationship": rel.to_dict(),
                        "direction": "outgoing",
                        "connected_entity": target.to_dict()
                    })
        
        if direction in ["incoming", "both"]:
            q = self.session.query(Relationship).filter(
                Relationship.target_id == entity_id
            )
            if trusted_only:
                q = q.filter(Relationship.lifecycle_state == LifecycleState.TRUSTED)
            if normalized_types:
                q = q.filter(Relationship.relationship_type.in_(normalized_types))
            
            for rel in q.all():
                source = self.session.query(Entity).get(rel.source_id)
                if source and (not trusted_only or source.lifecycle_state == LifecycleState.TRUSTED):
                    results.append({
                        "relationship": rel.to_dict(),
                        "direction": "incoming",
                        "connected_entity": source.to_dict()
                    })
        
        logger.debug(f"Entity {entity_id} relationships: found {len(results)}")
        return results
    
    def traverse_dependencies(
        self,
        entity_id: uuid.UUID,
        relationship_type: str = "DEPENDS_ON",
        direction: str = "outgoing",
        max_depth: int = 3
    ) -> List[Dict]:
        """
        Traverse dependency graph from an entity.
        Returns all entities reachable via the specified relationship type.
        """
        visited = set()
        results = []
        
        def traverse(current_id: uuid.UUID, depth: int, path: List[str]):
            if depth > max_depth or current_id in visited:
                return
            
            visited.add(current_id)
            entity = self.session.query(Entity).get(current_id)
            if not entity:
                return
            
            rels = self.get_entity_relationships(
                current_id,
                relationship_types=[relationship_type],
                direction=direction,
                trusted_only=True
            )
            
            for rel_info in rels:
                connected = rel_info["connected_entity"]
                connected_id = uuid.UUID(connected["id"])
                
                if connected_id not in visited:
                    results.append({
                        "entity": connected,
                        "relationship": rel_info["relationship"],
                        "depth": depth,
                        "path": path + [connected["name"]]
                    })
                    traverse(connected_id, depth + 1, path + [connected["name"]])
        
        entity = self.session.query(Entity).get(entity_id)
        if entity:
            traverse(entity_id, 1, [entity.name])
        
        logger.debug(f"Dependency traversal from {entity_id}: found {len(results)} connected entities")
        return results
    
    def find_impact_chain(
        self,
        entity_name: str,
        max_depth: int = 3
    ) -> Dict:
        """
        Find what services/components are impacted if this entity fails.
        Traverses DEPENDS_ON relationships in reverse (who depends on this).
        """
        entity = self.find_entity_by_name(entity_name)
        if not entity:
            logger.warning(f"Entity not found for impact analysis: {entity_name}")
            return {"entity": entity_name, "error": "Entity not found", "impacted": []}
        
        impacted = self.traverse_dependencies(
            entity.id,
            relationship_type="DEPENDS_ON",
            direction="incoming",
            max_depth=max_depth
        )
        
        logger.info(f"Impact chain for {entity_name}: {len(impacted)} services affected")
        return {
            "entity": entity.to_dict(),
            "impacted_count": len(impacted),
            "impacted": impacted
        }
    
    def find_escalation_path(
        self,
        start_entity_name: str
    ) -> List[Dict]:
        """Find escalation path from a person or team."""
        entity = self.find_entity_by_name(start_entity_name)
        if not entity:
            return []
        
        path = self.traverse_dependencies(
            entity.id,
            relationship_type="ESCALATES_TO",
            direction="outgoing",
            max_depth=5
        )
        
        logger.info(f"Escalation path from {start_entity_name}: {len(path)} hops")
        return path
    
    def promote_to_trusted(self, entity_id: uuid.UUID) -> bool:
        """Promote an entity from STAGING to TRUSTED."""
        entity = self.session.query(Entity).get(entity_id)
        if entity and entity.lifecycle_state == LifecycleState.STAGING:
            entity.lifecycle_state = LifecycleState.TRUSTED
            from datetime import datetime
            entity.promoted_at = datetime.utcnow()
            self.session.commit()
            logger.info(f"Promoted entity {entity.name} to TRUSTED")
            return True
        return False
    
    ALLOWED_PROPERTY_KEYS = frozenset([
        'role', 'level', 'department', 'expertise', 'email', 'phone', 'team',
        'domain', 'focus_area', 'headcount', 'tier', 'language', 'owner_team'
    ])
    
    def search_entities_by_properties(
        self,
        entity_type: Optional[str] = None,
        filters: List[Dict] = None,
        trusted_only: bool = True,
        limit: int = 50
    ) -> List[Entity]:
        """
        Search entities by their JSON properties.
        
        This is the GENERALIZED property search - works for any entity attribute
        stored in the properties JSON field (expertise, role, level, department, etc.)
        
        Args:
            entity_type: Filter by entity type (e.g., PERSON, TEAM)
            filters: List of filter dicts, each with:
                - property: the property name (e.g., "expertise", "role", "level")
                - operator: "contains", "equals", "in" (default: "contains")
                - value: the value to match
            trusted_only: Only return TRUSTED entities
            limit: Max results
            
        Example filters:
            [{"property": "expertise", "contains": "frontend"}]
            [{"property": "level", "equals": "Director"}]
            [{"property": "department", "equals": "Engineering"}]
            
        SECURITY: Property names are whitelisted to prevent SQL injection.
        """
        filters = filters or []
        
        q = self.session.query(Entity)
        
        if trusted_only:
            q = q.filter(Entity.lifecycle_state == LifecycleState.TRUSTED)
        
        if entity_type:
            q = q.filter(Entity.entity_type == entity_type)
        
        for f in filters:
            prop_name = f.get("property", "")
            if not prop_name:
                continue
            
            if prop_name not in self.ALLOWED_PROPERTY_KEYS:
                logger.warning(f"Blocked disallowed property key: {prop_name}")
                continue
            
            if "contains" in f:
                value = f["contains"]
                q = q.filter(
                    or_(
                        text(f"properties->>'{prop_name}' ILIKE :val").bindparams(val=f"%{value}%"),
                        text(f"properties::text ILIKE :val2").bindparams(val2=f"%{value}%")
                    )
                )
            elif "equals" in f:
                value = f["equals"]
                q = q.filter(
                    text(f"properties->>'{prop_name}' = :val").bindparams(val=value)
                )
            elif "in" in f:
                values = f["in"]
                if isinstance(values, list):
                    q = q.filter(
                        text(f"properties->>'{prop_name}' IN :vals").bindparams(vals=tuple(values))
                    )
        
        results = q.order_by(Entity.confidence.desc()).limit(limit).all()
        
        logger.debug(f"Property search: entity_type={entity_type}, filters={filters} -> {len(results)} results")
        return results
    
    def get_entity_schema(self, entity_type: str) -> Dict:
        """
        Get the schema of properties for a given entity type.
        
        This is used to tell the LLM what properties are queryable.
        """
        schemas = {
            "PERSON": {
                "properties": {
                    "role": "Job title (e.g., 'Software Engineer', 'Director of Engineering')",
                    "level": "Seniority level (e.g., 'IC', 'Manager', 'Director', 'VP', 'C-Level')",
                    "department": "Department name (e.g., 'Engineering', 'Product', 'Sales')",
                    "expertise": "List of skills/expertise areas (e.g., ['frontend', 'react', 'typescript'])",
                    "email": "Email address",
                    "phone": "Phone number",
                }
            },
            "TEAM": {
                "properties": {
                    "department": "Parent department",
                    "focus_area": "Team's primary focus",
                    "headcount": "Number of team members",
                }
            },
            "SERVICE": {
                "properties": {
                    "tier": "Service tier (e.g., 'tier1', 'tier2')",
                    "language": "Primary programming language",
                    "owner_team": "Owning team name",
                }
            },
        }
        return schemas.get(entity_type.upper() if entity_type else "", {"properties": {}})
    
    def get_statistics(self) -> Dict:
        """Get statistics about the semantic memory."""
        stats = {
            "entities": {
                "total": self.session.query(Entity).count(),
                "staging": self.session.query(Entity).filter(
                    Entity.lifecycle_state == LifecycleState.STAGING
                ).count(),
                "trusted": self.session.query(Entity).filter(
                    Entity.lifecycle_state == LifecycleState.TRUSTED
                ).count(),
                "archived": self.session.query(Entity).filter(
                    Entity.lifecycle_state == LifecycleState.ARCHIVED
                ).count(),
            },
            "relationships": {
                "total": self.session.query(Relationship).count(),
                "staging": self.session.query(Relationship).filter(
                    Relationship.lifecycle_state == LifecycleState.STAGING
                ).count(),
                "trusted": self.session.query(Relationship).filter(
                    Relationship.lifecycle_state == LifecycleState.TRUSTED
                ).count(),
            }
        }
        return stats
