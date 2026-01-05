"""
Semantic Memory Layer - Knowledge Graph with Lifecycle States.
Stores entities and relationships with STAGING/TRUSTED/ARCHIVED lifecycle.
Supports temporal queries via as_of_date parameter.
"""
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
from sqlalchemy import or_, and_, text, func
from sqlalchemy.orm import Session, joinedload
from collections import deque
import uuid

from ..models.schema import (
    Entity, Relationship, LifecycleState, get_session
)
from ..config.domain_schema import (
    get_schema_loader,
    FrontierReason,
    FrontierNode,
    ConfirmedEntity,
    TraversalResult,
    generate_frontier_message,
    generate_gap_description
)
from ..utils.logger import logger


class SemanticMemory:
    """
    Knowledge Graph memory layer with lifecycle management.
    Only TRUSTED facts are used for reasoning by default.
    
    SECURITY: Requires tenant_id for defense-in-depth filtering.
    RLS provides the authoritative security boundary, but application-level
    filtering provides belt-and-suspenders protection.
    """
    
    def __init__(self, session: Optional[Session] = None, tenant_id: str = None):
        self.session = session or get_session()
        self.tenant_id = tenant_id
        if not tenant_id:
            logger.warning("SemanticMemory initialized without tenant_id - queries will not be tenant-scoped")
        else:
            logger.info(f"SemanticMemory initialized for tenant {tenant_id[:8]}...")
    
    def _apply_tenant_filter(self, query, model_class):
        """Apply tenant_id filter if tenant_id is set (defense-in-depth)."""
        if self.tenant_id and hasattr(model_class, 'tenant_id'):
            from uuid import UUID
            tid = UUID(self.tenant_id) if isinstance(self.tenant_id, str) else self.tenant_id
            return query.filter(model_class.tenant_id == tid)
        return query
    
    def _get_entity_by_id(self, entity_id: uuid.UUID) -> Optional[Entity]:
        """Get entity by ID with tenant filtering (defense-in-depth)."""
        query = self.session.query(Entity).filter(Entity.id == entity_id)
        query = self._apply_tenant_filter(query, Entity)
        return query.first()
    
    def add_entity(
        self,
        name: str,
        entity_type: str,
        properties: dict = None,
        description: str = None,
        confidence: float = 0.5,
        source_document_id: str = None,
        source_sentence: str = None,
        lifecycle_state: LifecycleState = LifecycleState.STAGING,
        aliases: list = None
    ) -> Entity:
        """Add an entity to the knowledge graph with optional aliases."""
        from .schema import EntityAlias
        
        entity = Entity(
            name=name,
            entity_type=entity_type.upper(),
            properties=properties or {},
            description=description,
            confidence=confidence,
            source_document_id=source_document_id,
            source_sentence=source_sentence,
            lifecycle_state=lifecycle_state,
            tenant_id=self.tenant_id
        )
        self.session.add(entity)
        
        try:
            self.session.flush()
            
            if aliases:
                for alias in aliases:
                    if alias and alias.lower() != name.lower():
                        alias_type = self._detect_alias_type(alias, name)
                        entity_alias = EntityAlias(
                            entity_id=entity.id,
                            alias=alias,
                            alias_type=alias_type,
                            source='extraction',
                            tenant_id=self.tenant_id
                        )
                        self.session.add(entity_alias)
            
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to add entity {name}: {e}")
            raise
        
        logger.debug(f"Added entity: {name} [{entity_type}] (state: {lifecycle_state.value}) with {len(aliases or [])} aliases")
        return entity
    
    def _detect_alias_type(self, alias: str, full_name: str) -> str:
        """Detect type of alias (acronym or synonym)."""
        if alias.isupper() and len(alias) <= 10:
            return 'acronym'
        initials = ''.join(word[0] for word in full_name.split() if word and word[0].isupper())
        if alias.upper() == initials:
            return 'acronym'
        return 'synonym'
    
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
        query = self._apply_tenant_filter(query, Entity)
        if trusted_only:
            query = query.filter(Entity.lifecycle_state == LifecycleState.TRUSTED)
        return query.first()
    
    def search_entities(
        self,
        query_text: str,
        entity_types: List[str] = None,
        trusted_only: bool = True,
        limit: int = 10,
        as_of_date: Optional[datetime] = None
    ) -> List[Entity]:
        """
        Search entities by name (prioritizes exact match, then case-insensitive contains).
        
        Args:
            query_text: Search term
            entity_types: Filter by entity types
            trusted_only: Only return TRUSTED entities
            limit: Max results
            as_of_date: If provided, filter entities that were valid at this date
                        (valid_from <= as_of_date AND (valid_to IS NULL OR valid_to > as_of_date))
        """
        results = []
        seen_ids = set()
        
        def build_base_query():
            q = self.session.query(Entity)
            q = self._apply_tenant_filter(q, Entity)
            if trusted_only:
                q = q.filter(Entity.lifecycle_state == LifecycleState.TRUSTED)
            if entity_types:
                normalized_types = [t.upper() if isinstance(t, str) else t for t in entity_types]
                q = q.filter(Entity.entity_type.in_(normalized_types))
            if as_of_date:
                q = q.filter(
                    Entity.valid_from <= as_of_date,
                    or_(Entity.valid_to.is_(None), Entity.valid_to > as_of_date)
                )
            else:
                q = q.filter(Entity.valid_to.is_(None))
            return q
        
        # Priority 1: Exact case-insensitive match
        exact_q = build_base_query().filter(
            func.lower(Entity.name) == func.lower(query_text)
        )
        for entity in exact_q.order_by(Entity.confidence.desc()).limit(limit).all():
            if entity.id not in seen_ids:
                results.append(entity)
                seen_ids.add(entity.id)
        
        # Priority 2: Fuzzy contains match (if we need more results)
        if len(results) < limit:
            fuzzy_q = build_base_query().filter(
                Entity.name.ilike(f"%{query_text}%")
            )
            for entity in fuzzy_q.order_by(Entity.confidence.desc()).limit(limit).all():
                if entity.id not in seen_ids:
                    results.append(entity)
                    seen_ids.add(entity.id)
                    if len(results) >= limit:
                        break
        
        logger.debug(f"Entity search '{query_text}': found {len(results)} results (as_of={as_of_date})")
        return results[:limit]
    
    def get_entity_relationships(
        self,
        entity_id: uuid.UUID,
        relationship_types: List[str] = None,
        direction: str = "both",
        trusted_only: bool = True,
        max_depth: int = 1,
        as_of_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get relationships for an entity.
        direction: 'outgoing', 'incoming', or 'both'
        as_of_date: If provided, filter relationships that were valid at this date
        Returns list of dicts with relationship and connected entity info.
        """
        results = []
        normalized_types = None
        if relationship_types:
            normalized_types = [t.upper() if isinstance(t, str) else t for t in relationship_types]
        
        if direction in ["outgoing", "both"]:
            q = self.session.query(Relationship).options(
                joinedload(Relationship.source_entity),
                joinedload(Relationship.target_entity)
            ).filter(
                Relationship.source_id == entity_id
            )
            q = self._apply_tenant_filter(q, Relationship)
            if trusted_only:
                q = q.filter(Relationship.lifecycle_state == LifecycleState.TRUSTED)
            if normalized_types:
                q = q.filter(Relationship.relationship_type.in_(normalized_types))
            if as_of_date:
                q = q.filter(
                    Relationship.valid_from <= as_of_date,
                    or_(Relationship.valid_to.is_(None), Relationship.valid_to > as_of_date)
                )
            else:
                q = q.filter(Relationship.valid_to.is_(None))
            
            for rel in q.all():
                target = self._get_entity_by_id(rel.target_id)
                if target and (not trusted_only or target.lifecycle_state == LifecycleState.TRUSTED):
                    if as_of_date:
                        if target.valid_from and target.valid_from <= as_of_date:
                            if target.valid_to is None or target.valid_to > as_of_date:
                                results.append({
                                    "relationship": rel.to_dict(),
                                    "direction": "outgoing",
                                    "connected_entity": target.to_dict()
                                })
                    elif target.valid_to is None:
                        results.append({
                            "relationship": rel.to_dict(),
                            "direction": "outgoing",
                            "connected_entity": target.to_dict()
                        })
        
        if direction in ["incoming", "both"]:
            q = self.session.query(Relationship).options(
                joinedload(Relationship.source_entity),
                joinedload(Relationship.target_entity)
            ).filter(
                Relationship.target_id == entity_id
            )
            q = self._apply_tenant_filter(q, Relationship)
            if trusted_only:
                q = q.filter(Relationship.lifecycle_state == LifecycleState.TRUSTED)
            if normalized_types:
                q = q.filter(Relationship.relationship_type.in_(normalized_types))
            if as_of_date:
                q = q.filter(
                    Relationship.valid_from <= as_of_date,
                    or_(Relationship.valid_to.is_(None), Relationship.valid_to > as_of_date)
                )
            else:
                q = q.filter(Relationship.valid_to.is_(None))
            
            for rel in q.all():
                source = self._get_entity_by_id(rel.source_id)
                if source and (not trusted_only or source.lifecycle_state == LifecycleState.TRUSTED):
                    if as_of_date:
                        if source.valid_from and source.valid_from <= as_of_date:
                            if source.valid_to is None or source.valid_to > as_of_date:
                                results.append({
                                    "relationship": rel.to_dict(),
                                    "direction": "incoming",
                                    "connected_entity": source.to_dict()
                                })
                    elif source.valid_to is None:
                        results.append({
                            "relationship": rel.to_dict(),
                            "direction": "incoming",
                            "connected_entity": source.to_dict()
                        })
        
        logger.debug(f"Entity {entity_id} relationships: found {len(results)} (as_of={as_of_date})")
        return results
    
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
        Returns all entities reachable via the specified relationship type.
        
        Args:
            as_of_date: If provided, only returns entities/relationships valid at this date.
        """
        visited = set()
        results = []
        
        def traverse(current_id: uuid.UUID, depth: int, path: List[str]):
            if depth > max_depth or current_id in visited:
                return
            
            visited.add(current_id)
            entity = self._get_entity_by_id(current_id)
            if not entity:
                return
            
            rels = self.get_entity_relationships(
                current_id,
                relationship_types=[relationship_type],
                direction=direction,
                trusted_only=True,
                as_of_date=as_of_date
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
        
        entity = self._get_entity_by_id(entity_id)
        if entity:
            traverse(entity_id, 1, [entity.name])
        
        logger.debug(f"Dependency traversal from {entity_id}: found {len(results)} connected entities (as_of={as_of_date})")
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
    
    def get_exhaustive_blast_radius(
        self,
        entity_name: str,
        max_depth: int = 10,
        as_of_date: Optional[datetime] = None
    ) -> Dict:
        """
        EXHAUSTIVE graph traversal for blast radius / impact queries.
        
        Uses BFS to find ALL entities that depend on the target entity,
        either directly or transitively. This is deterministic and complete,
        unlike LLM-based discovery which may vary.
        
        The result is a complete, reproducible set of affected entities
        that will be the same every time for the same graph state.
        
        Args:
            entity_name: Name of the entity that might fail
            max_depth: Maximum traversal depth (default 10 for exhaustive search)
            as_of_date: Optional datetime for temporal queries
        
        Returns:
            Dict with:
                - entity: The source entity
                - affected: List of all affected entities with paths
                - affected_count: Total count
                - relationships: All traversed relationships
                - traversal_complete: Whether we hit max_depth
        """
        entity = self.find_entity_by_name(entity_name)
        if not entity:
            logger.warning(f"Entity not found for blast radius: {entity_name}")
            return {
                "entity": entity_name, 
                "error": "Entity not found", 
                "affected": [],
                "affected_count": 0,
                "relationships": [],
                "traversal_complete": True
            }
        
        visited: Set[uuid.UUID] = set()
        affected: List[Dict] = []
        relationships: List[Dict] = []
        queue: List[tuple] = [(entity.id, 0, [entity.name])]
        max_depth_reached = False
        
        visited.add(entity.id)
        
        while queue:
            current_id, depth, path = queue.pop(0)
            
            if depth >= max_depth:
                max_depth_reached = True
                continue
            
            rels = self.get_entity_relationships(
                current_id,
                relationship_types=["DEPENDS_ON"],
                direction="incoming",
                trusted_only=True,
                as_of_date=as_of_date
            )
            
            for rel_info in rels:
                connected = rel_info["connected_entity"]
                connected_id = uuid.UUID(connected["id"])
                rel_dict = rel_info["relationship"]
                
                if rel_dict not in relationships:
                    relationships.append(rel_dict)
                
                if connected_id not in visited:
                    visited.add(connected_id)
                    new_path = path + [connected["name"]]
                    
                    affected.append({
                        "entity": connected,
                        "depth": depth + 1,
                        "path": new_path,
                        "dependency_chain": " -> ".join(new_path)
                    })
                    
                    queue.append((connected_id, depth + 1, new_path))
        
        affected.sort(key=lambda x: (x["depth"], x["entity"]["name"]))
        
        logger.info(f"Exhaustive blast radius for {entity_name}: {len(affected)} entities affected, {len(relationships)} relationships (depth_limited={max_depth_reached})")
        
        return {
            "entity": entity.to_dict(),
            "affected": affected,
            "affected_count": len(affected),
            "relationships": relationships,
            "traversal_complete": not max_depth_reached
        }
    
    def _get_relationships_for_entity(
        self, 
        entity_id: uuid.UUID, 
        as_of_date: Optional[datetime] = None,
        trusted_only: bool = True
    ) -> List[Relationship]:
        """Get all relationships where entity is source OR target.
        
        Args:
            entity_id: The entity to get relationships for
            as_of_date: Optional temporal filter
            trusted_only: If True, only return TRUSTED relationships (default)
        """
        q = self.session.query(Relationship).options(
            joinedload(Relationship.source_entity),
            joinedload(Relationship.target_entity)
        ).filter(
            or_(
                Relationship.source_id == entity_id,
                Relationship.target_id == entity_id
            )
        )
        q = self._apply_tenant_filter(q, Relationship)
        
        if trusted_only:
            q = q.filter(Relationship.lifecycle_state == LifecycleState.TRUSTED)
        else:
            q = q.filter(Relationship.lifecycle_state != LifecycleState.ARCHIVED)
        
        if as_of_date:
            q = q.filter(
                Relationship.valid_from <= as_of_date,
                or_(Relationship.valid_to.is_(None), Relationship.valid_to > as_of_date)
            )
        else:
            q = q.filter(Relationship.valid_to.is_(None))
        
        return q.all()
    
    def traverse_from_entity(
        self,
        entity_id: uuid.UUID,
        mode: str,
        max_depth: int = 10,
        as_of_date: Optional[datetime] = None
    ) -> Set[uuid.UUID]:
        """
        Generic graph traversal that respects relationship semantics for a given mode.
        
        This is SCHEMA-DRIVEN: the traversal rules are read from the schema YAML,
        not hardcoded. Each relationship type defines how it should be traversed
        in different modes (impact, dependency, ownership, etc.).
        
        Only TRUSTED entities and relationships are included in the traversal.
        
        Args:
            entity_id: The starting node ID
            mode: The traversal context (defined in schema per relationship type)
            max_depth: Maximum traversal depth
            as_of_date: Optional datetime for temporal queries
        
        Returns:
            Set of reachable entity IDs
            
        Behavior:
            - If relationship type has no semantics: not traversed
            - If mode not defined for relationship type: not traversed
            - Cycles handled via visited set
            - Only TRUSTED entities and relationships are followed
        """
        schema = get_schema_loader().schema
        reachable: Set[uuid.UUID] = set()
        visited: Set[uuid.UUID] = set()
        queue = deque([(entity_id, 0)])
        
        while queue:
            current_id, depth = queue.popleft()
            
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            
            relationships = self._get_relationships_for_entity(current_id, as_of_date, trusted_only=True)
            
            for rel in relationships:
                rel_type_def = schema.get_relationship_type(rel.relationship_type)
                
                if not rel_type_def or not rel_type_def.semantics:
                    continue
                
                rule = rel_type_def.semantics.modes.get(mode)
                
                if not rule or not rule.include:
                    continue
                
                neighbor_id = None
                
                if rel.source_id == current_id and rule.from_source:
                    neighbor_id = rel.target_id
                elif rel.target_id == current_id and rule.from_target:
                    neighbor_id = rel.source_id
                
                if neighbor_id and neighbor_id not in reachable:
                    neighbor_entity = self._get_entity_by_id(neighbor_id)
                    if not neighbor_entity:
                        continue
                    if neighbor_entity.lifecycle_state != LifecycleState.TRUSTED:
                        continue
                    if as_of_date:
                        if neighbor_entity.valid_from and neighbor_entity.valid_from > as_of_date:
                            continue
                        if neighbor_entity.valid_to and neighbor_entity.valid_to <= as_of_date:
                            continue
                    elif neighbor_entity.valid_to is not None:
                        continue
                    
                    reachable.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))
        
        logger.debug(f"Schema-driven traversal from {entity_id} in mode '{mode}': found {len(reachable)} entities")
        return reachable
    
    def get_schema_driven_blast_radius(
        self,
        entity_name: str,
        mode: str = "impact",
        max_depth: int = 10,
        confidence_threshold: float = 0.0,
        as_of_date: Optional[datetime] = None
    ) -> TraversalResult:
        """
        Schema-driven blast radius using generic traversal with frontier detection.
        
        Uses traverse_with_frontier_detection to find all affected entities,
        identify frontier nodes where knowledge ends, and surface documentation gaps.
        
        The mode determines which relationships are followed and in which direction,
        as defined in the schema YAML.
        
        Args:
            entity_name: Name of the entity that might fail
            mode: Traversal mode (default: "impact")
            max_depth: Maximum traversal depth
            confidence_threshold: Minimum confidence for relationships
            as_of_date: Optional datetime for temporal queries
        
        Returns:
            TraversalResult with confirmed entities, frontier nodes, and gaps
        """
        entity = self.find_entity_by_name(entity_name)
        if not entity:
            logger.warning(f"Entity not found for schema-driven blast radius: {entity_name}")
            return TraversalResult(
                start_entity_id="",
                start_entity_name=entity_name,
                start_entity_type="Unknown",
                mode=mode,
                max_depth=max_depth,
                confidence_threshold=confidence_threshold,
                traversal_complete=False,
                gaps_identified=[f"Entity '{entity_name}' not found in knowledge graph"],
                timestamp=datetime.utcnow().isoformat()
            )
        
        result = self.traverse_with_frontier_detection(
            entity.id,
            mode=mode,
            max_depth=max_depth,
            confidence_threshold=confidence_threshold,
            as_of_date=as_of_date
        )
        
        logger.info(
            f"Schema-driven blast radius for {entity_name} (mode={mode}): "
            f"{len(result.confirmed_entities)} confirmed, "
            f"{len(result.frontier_nodes)} frontier nodes"
        )
        
        return result
    
    def get_schema_driven_blast_radius_legacy(
        self,
        entity_name: str,
        mode: str = "impact",
        max_depth: int = 10,
        as_of_date: Optional[datetime] = None
    ) -> Dict:
        """
        Legacy blast radius method for backward compatibility.
        
        Returns the old Dict format instead of TraversalResult.
        Use get_schema_driven_blast_radius for new code.
        """
        entity = self.find_entity_by_name(entity_name)
        if not entity:
            logger.warning(f"Entity not found for schema-driven blast radius: {entity_name}")
            return {
                "entity": entity_name,
                "error": "Entity not found",
                "affected": [],
                "affected_count": 0,
                "relationships": [],
                "mode": mode,
                "traversal_complete": True
            }
        
        affected_ids, traversed_relationships = self.traverse_from_entity_with_relationships(
            entity.id,
            mode=mode,
            max_depth=max_depth,
            as_of_date=as_of_date
        )
        
        affected = []
        for aid in affected_ids:
            e = self._get_entity_by_id(aid)
            if e:
                affected.append({
                    "entity": e.to_dict(),
                    "id": str(aid)
                })
        
        affected.sort(key=lambda x: x["entity"]["name"])
        
        logger.info(f"Legacy blast radius for {entity_name} (mode={mode}): {len(affected)} entities")
        
        return {
            "entity": entity.to_dict(),
            "affected": affected,
            "affected_count": len(affected),
            "affected_entity_names": sorted([a["entity"]["name"] for a in affected]),
            "relationships": traversed_relationships,
            "mode": mode,
            "traversal_complete": True
        }
    
    def traverse_from_entity_with_relationships(
        self,
        entity_id: uuid.UUID,
        mode: str,
        max_depth: int = 10,
        as_of_date: Optional[datetime] = None
    ) -> Tuple[Set[uuid.UUID], List[Dict]]:
        """
        Generic graph traversal that returns both affected entities AND traversed relationships.
        
        This is like traverse_from_entity but also collects the relationships that were followed
        during traversal, so they can be displayed in the UI.
        
        Only TRUSTED entities and relationships are included in the traversal.
        
        Args:
            entity_id: The starting node ID
            mode: The traversal context (defined in schema per relationship type)
            max_depth: Maximum traversal depth
            as_of_date: Optional datetime for temporal queries
        
        Returns:
            Tuple of (Set of reachable entity IDs, List of traversed relationship dicts)
        """
        schema = get_schema_loader().schema
        reachable: Set[uuid.UUID] = set()
        visited: Set[uuid.UUID] = set()
        traversed_relationships: List[Dict] = []
        seen_rel_ids: Set[str] = set()
        queue = deque([(entity_id, 0)])
        
        while queue:
            current_id, depth = queue.popleft()
            
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            
            relationships = self._get_relationships_for_entity(current_id, as_of_date, trusted_only=True)
            
            for rel in relationships:
                rel_type_def = schema.get_relationship_type(rel.relationship_type)
                
                if not rel_type_def or not rel_type_def.semantics:
                    continue
                
                rule = rel_type_def.semantics.modes.get(mode)
                
                if not rule or not rule.include:
                    continue
                
                neighbor_id = None
                
                if rel.source_id == current_id and rule.from_source:
                    neighbor_id = rel.target_id
                elif rel.target_id == current_id and rule.from_target:
                    neighbor_id = rel.source_id
                
                if neighbor_id and neighbor_id not in reachable:
                    neighbor_entity = self._get_entity_by_id(neighbor_id)
                    if not neighbor_entity:
                        continue
                    if neighbor_entity.lifecycle_state != LifecycleState.TRUSTED:
                        continue
                    if as_of_date:
                        if neighbor_entity.valid_from and neighbor_entity.valid_from > as_of_date:
                            continue
                        if neighbor_entity.valid_to and neighbor_entity.valid_to <= as_of_date:
                            continue
                    elif neighbor_entity.valid_to is not None:
                        continue
                    
                    reachable.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))
                    
                    rel_id = str(rel.id)
                    if rel_id not in seen_rel_ids:
                        seen_rel_ids.add(rel_id)
                        traversed_relationships.append(rel.to_dict())
        
        logger.debug(f"Schema-driven traversal from {entity_id} in mode '{mode}': found {len(reachable)} entities, {len(traversed_relationships)} relationships")
        return reachable, traversed_relationships
    
    def traverse_with_frontier_detection(
        self,
        entity_id: uuid.UUID,
        mode: str,
        max_depth: int = 10,
        confidence_threshold: float = 0.0,
        as_of_date: Optional[datetime] = None
    ) -> TraversalResult:
        """
        Schema-driven graph traversal with frontier detection.
        
        This is the primary traversal method that returns a complete TraversalResult
        including confirmed entities, frontier nodes (where knowledge ends), and gaps.
        
        For each node visited, it determines:
        - NO_RELATIONSHIPS: Node has no relationships at all
        - NO_EDGES_FOR_MODE: Node has relationships, but none match the mode's direction/type rules
        - BELOW_CONFIDENCE_THRESHOLD: All edges are below the confidence threshold
        - MAX_DEPTH_REACHED: Hit the depth limit
        
        Args:
            entity_id: The starting node ID
            mode: The traversal context (defined in schema per relationship type)
            max_depth: Maximum traversal depth
            confidence_threshold: Minimum confidence for relationships (default 0.0)
            as_of_date: Optional datetime for temporal queries
        
        Returns:
            TraversalResult with confirmed entities, frontier nodes, and gaps
        """
        schema = get_schema_loader().schema
        
        start_entity = self._get_entity_by_id(entity_id)
        if not start_entity:
            logger.warning(f"Start entity not found: {entity_id}")
            return TraversalResult(
                start_entity_id=str(entity_id),
                start_entity_name="Unknown",
                start_entity_type="Unknown",
                mode=mode,
                max_depth=max_depth,
                confidence_threshold=confidence_threshold,
                traversal_complete=False,
                timestamp=datetime.utcnow().isoformat()
            )
        
        confirmed_entities: List[ConfirmedEntity] = []
        frontier_nodes: List[FrontierNode] = []
        gaps_identified: List[str] = []
        traversed_relationships: List[Dict] = []
        
        visited: Set[uuid.UUID] = set()
        seen_rel_ids: Set[str] = set()
        entity_depths: Dict[uuid.UUID, int] = {}
        entity_paths: Dict[uuid.UUID, List[str]] = {}
        
        queue = deque([(entity_id, 0, [])])
        
        while queue:
            current_id, depth, path = queue.popleft()
            
            if current_id in visited:
                continue
            
            if depth > max_depth:
                current_entity = self._get_entity_by_id(current_id)
                if current_entity and current_id != entity_id:
                    message = generate_frontier_message(
                        FrontierReason.MAX_DEPTH_REACHED,
                        mode,
                        current_entity.name,
                        current_entity.entity_type
                    )
                    frontier_nodes.append(FrontierNode(
                        entity_id=str(current_id),
                        entity_name=current_entity.name,
                        entity_type=current_entity.entity_type,
                        reason=FrontierReason.MAX_DEPTH_REACHED,
                        message=message,
                        depth=depth
                    ))
                continue
            
            visited.add(current_id)
            entity_depths[current_id] = depth
            entity_paths[current_id] = path
            
            current_entity = self._get_entity_by_id(current_id)
            if not current_entity:
                continue
            
            all_relationships = self._get_relationships_for_entity(current_id, as_of_date, trusted_only=True)
            
            if len(all_relationships) == 0 and current_id != entity_id:
                message = generate_frontier_message(
                    FrontierReason.NO_RELATIONSHIPS,
                    mode,
                    current_entity.name,
                    current_entity.entity_type
                )
                frontier_nodes.append(FrontierNode(
                    entity_id=str(current_id),
                    entity_name=current_entity.name,
                    entity_type=current_entity.entity_type,
                    reason=FrontierReason.NO_RELATIONSHIPS,
                    message=message,
                    depth=depth
                ))
                gap = generate_gap_description(
                    FrontierReason.NO_RELATIONSHIPS,
                    mode,
                    current_entity.name,
                    current_entity.entity_type
                )
                if gap:
                    gaps_identified.append(gap)
                continue
            
            valid_edges_for_mode = []
            edges_below_threshold = []
            
            for rel in all_relationships:
                rel_type_def = schema.get_relationship_type(rel.relationship_type)
                
                if not rel_type_def or not rel_type_def.semantics:
                    continue
                
                rule = rel_type_def.semantics.modes.get(mode)
                
                if not rule or not rule.include:
                    continue
                
                neighbor_id = None
                
                if rel.source_id == current_id and rule.from_source:
                    neighbor_id = rel.target_id
                elif rel.target_id == current_id and rule.from_target:
                    neighbor_id = rel.source_id
                
                if neighbor_id is None:
                    continue
                
                if rel.confidence < confidence_threshold:
                    edges_below_threshold.append((rel, neighbor_id))
                    continue
                
                neighbor_entity = self._get_entity_by_id(neighbor_id)
                if not neighbor_entity:
                    continue
                if neighbor_entity.lifecycle_state != LifecycleState.TRUSTED:
                    continue
                if as_of_date:
                    if neighbor_entity.valid_from and neighbor_entity.valid_from > as_of_date:
                        continue
                    if neighbor_entity.valid_to and neighbor_entity.valid_to <= as_of_date:
                        continue
                elif neighbor_entity.valid_to is not None:
                    continue
                
                valid_edges_for_mode.append((rel, neighbor_id, neighbor_entity))
            
            if len(valid_edges_for_mode) == 0 and current_id != entity_id:
                if len(edges_below_threshold) > 0:
                    reason = FrontierReason.BELOW_CONFIDENCE_THRESHOLD
                else:
                    reason = FrontierReason.NO_EDGES_FOR_MODE
                
                message = generate_frontier_message(
                    reason,
                    mode,
                    current_entity.name,
                    current_entity.entity_type
                )
                frontier_nodes.append(FrontierNode(
                    entity_id=str(current_id),
                    entity_name=current_entity.name,
                    entity_type=current_entity.entity_type,
                    reason=reason,
                    message=message,
                    depth=depth
                ))
                gap = generate_gap_description(
                    reason,
                    mode,
                    current_entity.name,
                    current_entity.entity_type
                )
                if gap:
                    gaps_identified.append(gap)
                continue
            
            new_neighbors_found = False
            for rel, neighbor_id, neighbor_entity in valid_edges_for_mode:
                rel_id = str(rel.id)
                if rel_id not in seen_rel_ids:
                    seen_rel_ids.add(rel_id)
                    traversed_relationships.append(rel.to_dict())
                
                if neighbor_id not in visited:
                    new_neighbors_found = True
                    new_path = path + [rel.relationship_type]
                    queue.append((neighbor_id, depth + 1, new_path))
                    
                    if neighbor_id not in entity_depths:
                        confirmed_entities.append(ConfirmedEntity(
                            entity_id=str(neighbor_id),
                            entity_name=neighbor_entity.name,
                            entity_type=neighbor_entity.entity_type,
                            confidence=neighbor_entity.confidence,
                            depth=depth + 1,
                            path=new_path
                        ))
        
        confirmed_entities.sort(key=lambda x: (x.depth, x.entity_name))
        
        logger.info(
            f"Traversal from {start_entity.name} (mode={mode}): "
            f"{len(confirmed_entities)} confirmed, {len(frontier_nodes)} frontier nodes, "
            f"{len(gaps_identified)} gaps"
        )
        
        return TraversalResult(
            start_entity_id=str(entity_id),
            start_entity_name=start_entity.name,
            start_entity_type=start_entity.entity_type,
            mode=mode,
            max_depth=max_depth,
            confidence_threshold=confidence_threshold,
            confirmed_entities=confirmed_entities,
            traversed_relationships=traversed_relationships,
            frontier_nodes=frontier_nodes,
            gaps_identified=gaps_identified,
            traversal_complete=True,
            timestamp=datetime.utcnow().isoformat()
        )
    
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
        entity = self._get_entity_by_id(entity_id)
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
        limit: int = 50,
        as_of_date: Optional[datetime] = None
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
            as_of_date: If provided, filter entities that were valid at this date
            
        Example filters:
            [{"property": "expertise", "contains": "frontend"}]
            [{"property": "level", "equals": "Director"}]
            [{"property": "department", "equals": "Engineering"}]
            
        SECURITY: Property names are whitelisted to prevent SQL injection.
        """
        filters = filters or []
        
        q = self.session.query(Entity)
        q = self._apply_tenant_filter(q, Entity)
        
        if trusted_only:
            q = q.filter(Entity.lifecycle_state == LifecycleState.TRUSTED)
        
        if entity_type:
            q = q.filter(Entity.entity_type == entity_type)
        
        if as_of_date:
            q = q.filter(
                Entity.valid_from <= as_of_date,
                or_(Entity.valid_to.is_(None), Entity.valid_to > as_of_date)
            )
        else:
            q = q.filter(Entity.valid_to.is_(None))
        
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
        """Get statistics about the semantic memory (tenant-scoped)."""
        entity_base = self._apply_tenant_filter(self.session.query(Entity), Entity)
        rel_base = self._apply_tenant_filter(self.session.query(Relationship), Relationship)
        
        stats = {
            "entities": {
                "total": entity_base.count(),
                "staging": entity_base.filter(
                    Entity.lifecycle_state == LifecycleState.STAGING
                ).count(),
                "trusted": entity_base.filter(
                    Entity.lifecycle_state == LifecycleState.TRUSTED
                ).count(),
                "archived": entity_base.filter(
                    Entity.lifecycle_state == LifecycleState.ARCHIVED
                ).count(),
            },
            "relationships": {
                "total": rel_base.count(),
                "staging": rel_base.filter(
                    Relationship.lifecycle_state == LifecycleState.STAGING
                ).count(),
                "trusted": rel_base.filter(
                    Relationship.lifecycle_state == LifecycleState.TRUSTED
                ).count(),
            }
        }
        return stats
