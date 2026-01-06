"""
Directed Graph Retriever - Step 2 of the 3-Step Query Pipeline.

This module executes structured QueryIntent objects against the knowledge graph.
It returns EXACTLY what was asked for - no more, no less.

Key principles:
1. Deterministic: Same QueryIntent always returns same results
2. Precise: Only retrieves relationships matching the intent
3. Complete: Retrieves all matching relationships within specified depth
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.context_foundry.agents.query_interpreter import QueryIntent
from src.context_foundry.agents.entity_resolver import EntityResolver

logger = logging.getLogger(__name__)


@dataclass
class RetrievedRelationship:
    """A single relationship retrieved from the graph."""
    relationship_id: str
    relationship_type: str
    source_id: str
    source_name: str
    source_type: str
    target_id: str
    target_name: str
    target_type: str
    confidence: float
    direction_relative_to_entity: str  # "inbound" or "outbound"
    depth: int  # How many hops from the queried entity
    
    def to_dict(self) -> dict:
        return {
            "relationship_id": self.relationship_id,
            "relationship_type": self.relationship_type,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "target_type": self.target_type,
            "confidence": self.confidence,
            "direction": self.direction_relative_to_entity,
            "depth": self.depth
        }


@dataclass
class CascadePath:
    """A single impact chain path from the target entity to an affected entity."""
    path: List[str]  # List of entity names in the path
    depth: int
    relationship_types: List[str]  # Relationship types along the path
    
    def to_string(self) -> str:
        """Format as 'A -> B -> C'"""
        return " -> ".join(self.path)
    
    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "depth": self.depth,
            "relationship_types": self.relationship_types,
            "formatted": self.to_string()
        }


@dataclass
class RetrievalResult:
    """
    The complete result of executing a QueryIntent against the graph.
    
    This is the output of Step 2 (Directed Retrieval) and the input
    to Step 3 (Answer Synthesis).
    """
    query_intent: QueryIntent
    entity_found: bool
    entity_id: Optional[str]
    entity_name: Optional[str]
    entity_type: Optional[str]
    relationships: List[RetrievedRelationship] = field(default_factory=list)
    affected_entities: List[Dict] = field(default_factory=list)  # Unique entities discovered
    cascade_paths: List[CascadePath] = field(default_factory=list)  # Impact chains with paths
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "query_intent": self.query_intent.to_dict(),
            "entity_found": self.entity_found,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "relationship_count": len(self.relationships),
            "relationships": [r.to_dict() for r in self.relationships],
            "affected_entities": self.affected_entities,
            "cascade_paths": [p.to_dict() for p in self.cascade_paths],
            "error": self.error
        }
    
    def get_cascade_breakdown(self) -> Dict[int, List[str]]:
        """Get affected entities grouped by depth."""
        breakdown = {}
        for path in self.cascade_paths:
            if path.depth not in breakdown:
                breakdown[path.depth] = []
            # The last entity in the path is the affected one
            affected = path.path[-1] if path.path else None
            if affected and affected not in breakdown[path.depth]:
                breakdown[path.depth].append(affected)
        return breakdown
    
    def get_formatted_cascade(self) -> str:
        """Get a human-readable cascade breakdown."""
        breakdown = self.get_cascade_breakdown()
        lines = []
        total = 0
        for depth in sorted(breakdown.keys()):
            entities = breakdown[depth]
            total += len(entities)
            lines.append(f"Depth {depth}: {len(entities)} services")
            for entity in entities[:5]:
                lines.append(f"  - {entity}")
            if len(entities) > 5:
                lines.append(f"  ... and {len(entities) - 5} more")
        lines.append(f"\nTotal unique affected: {total}")
        return "\n".join(lines)
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the retrieval result."""
        if not self.entity_found:
            return f"Entity '{self.query_intent.entity}' not found in knowledge graph."
        
        if not self.relationships:
            return f"No {self.query_intent.direction} relationships of type {self.query_intent.relationship_types} found for '{self.entity_name}'."
        
        rel_counts = {}
        for rel in self.relationships:
            key = f"{rel.direction_relative_to_entity} {rel.relationship_type}"
            rel_counts[key] = rel_counts.get(key, 0) + 1
        
        summary_parts = [f"{count} {key}" for key, count in rel_counts.items()]
        return f"Found for '{self.entity_name}': " + ", ".join(summary_parts)


class DirectedGraphRetriever:
    """
    Step 2 of the 3-Step Query Pipeline: Directed Graph Retrieval.
    
    Executes structured QueryIntent objects against the knowledge graph
    with precision. Returns only what was asked for.
    """
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = str(tenant_id)
        self.entity_resolver = EntityResolver(session, tenant_id)
        
        self.session.execute(
            text("SELECT platform.set_current_tenant(:tid)"),
            {'tid': self.tenant_id}
        )
        
        logger.info(f"DirectedGraphRetriever initialized for tenant {tenant_id[:8]}...")
    
    def execute(self, intent: QueryIntent) -> RetrievalResult:
        """
        Execute a QueryIntent and return precise results.
        
        Args:
            intent: The structured query intent from Step 1
            
        Returns:
            RetrievalResult with all matching relationships
        """
        self.session.execute(
            text("SELECT platform.set_current_tenant(:tid)"),
            {'tid': self.tenant_id}
        )
        
        logger.info(f"Executing directed retrieval: entity='{intent.entity}', "
                   f"direction={intent.direction}, types={intent.relationship_types}")
        
        entity = self._resolve_entity(intent.entity)
        
        if not entity:
            logger.warning(f"Entity not found: {intent.entity}")
            return RetrievalResult(
                query_intent=intent,
                entity_found=False,
                entity_id=None,
                entity_name=intent.entity,
                entity_type=None,
                error=f"Entity '{intent.entity}' not found in knowledge graph"
            )
        
        entity_id = str(entity['id'])
        entity_name = entity['name']
        entity_type = entity.get('type', 'UNKNOWN')
        
        logger.info(f"Entity resolved: {entity_name} ({entity_type})")
        
        relationships, cascade_paths = self._retrieve_relationships_with_paths(
            entity_id=entity_id,
            entity_name=entity_name,
            direction=intent.direction,
            relationship_types=intent.relationship_types,
            depth=intent.depth
        )
        
        affected = self._collect_affected_entities(relationships, entity_id)
        
        result = RetrievalResult(
            query_intent=intent,
            entity_found=True,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            relationships=relationships,
            affected_entities=affected,
            cascade_paths=cascade_paths
        )
        
        logger.info(f"Retrieval complete: {len(relationships)} relationships, "
                   f"{len(affected)} affected entities, {len(cascade_paths)} paths")
        
        return result
    
    def _resolve_entity(self, entity_name: str) -> Optional[Dict]:
        """
        Resolve an entity name to its database record.
        
        Uses EntityResolver for intelligent matching (aliases, normalization, etc.)
        """
        try:
            result = self.entity_resolver.resolve(entity_name)
            
            if result and result.entity and result.confidence >= 0.5:
                return {
                    'id': str(result.entity.entity_id),
                    'name': result.entity.name,
                    'type': result.entity.entity_type,
                    'confidence': result.confidence,
                    'match_stage': result.match_stage
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Entity resolution failed: {e}")
            return None
    
    def _retrieve_relationships_with_paths(
        self,
        entity_id: str,
        entity_name: str,
        direction: str,
        relationship_types: List[str],
        depth: int
    ) -> tuple:
        """
        Retrieve relationships with path tracking for cascade visualization.
        
        Args:
            entity_id: The UUID of the target entity
            entity_name: The name of the target entity (for path building)
            direction: "inbound", "outbound", or "both"
            relationship_types: List of relationship types to include
            depth: Maximum traversal depth
            
        Returns:
            Tuple of (List[RetrievedRelationship], List[CascadePath])
        """
        relationships = []
        cascade_paths = []
        
        # Track paths: entity_id -> (path_names, path_rel_types)
        entity_paths: Dict[str, tuple] = {entity_id: ([entity_name], [])}
        visited_entities: Set[str] = {entity_id}
        current_frontier: Set[str] = {entity_id}
        
        # Track first discovery depth for each entity
        entity_first_depth: Dict[str, int] = {}
        
        for current_depth in range(1, depth + 1):
            next_frontier: Set[str] = set()
            
            for frontier_entity_id in current_frontier:
                current_path, current_rel_types = entity_paths.get(frontier_entity_id, ([entity_name], []))
                
                rels = self._get_direct_relationships(
                    entity_id=frontier_entity_id,
                    direction=direction,
                    relationship_types=relationship_types,
                    original_entity_id=entity_id
                )
                
                for rel in rels:
                    rel.depth = current_depth
                    relationships.append(rel)
                    
                    # Get the "other" entity (the one we discovered)
                    if rel.direction_relative_to_entity == "inbound":
                        other_id = rel.source_id
                        other_name = rel.source_name
                    else:
                        other_id = rel.target_id
                        other_name = rel.target_name
                    
                    if other_id not in visited_entities:
                        visited_entities.add(other_id)
                        next_frontier.add(other_id)
                        
                        # Build path to this entity
                        new_path = current_path + [other_name]
                        new_rel_types = current_rel_types + [rel.relationship_type]
                        entity_paths[other_id] = (new_path, new_rel_types)
                        
                        # Record first discovery depth
                        entity_first_depth[other_id] = current_depth
                        
                        # Create cascade path
                        cascade_paths.append(CascadePath(
                            path=new_path,
                            depth=current_depth,
                            relationship_types=new_rel_types
                        ))
            
            current_frontier = next_frontier
            
            if not current_frontier:
                break
        
        return relationships, cascade_paths
    
    def _get_direct_relationships(
        self,
        entity_id: str,
        direction: str,
        relationship_types: List[str],
        original_entity_id: str
    ) -> List[RetrievedRelationship]:
        """
        Get direct relationships for a single entity.
        
        Args:
            entity_id: The entity to query
            direction: "inbound", "outbound", or "both"
            relationship_types: Types to filter by (empty = all)
            original_entity_id: The originally queried entity (for direction context)
        """
        results = []
        
        type_filter = ""
        if relationship_types:
            type_placeholders = ", ".join([f"'{t}'" for t in relationship_types])
            type_filter = f"AND r.relationship_type IN ({type_placeholders})"
        
        if direction in ("inbound", "both"):
            query = text(f"""
                SELECT 
                    r.id::text as rel_id,
                    r.relationship_type,
                    r.source_id::text,
                    se.name as source_name,
                    se.entity_type as source_type,
                    r.target_id::text,
                    te.name as target_name,
                    te.entity_type as target_type,
                    r.confidence
                FROM relationships r
                JOIN entities se ON r.source_id = se.id
                JOIN entities te ON r.target_id = te.id
                WHERE r.target_id = :entity_id
                AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
                {type_filter}
                ORDER BY r.confidence DESC
            """)
            
            rows = self.session.execute(query, {'entity_id': entity_id}).fetchall()
            
            for row in rows:
                results.append(RetrievedRelationship(
                    relationship_id=row[0],
                    relationship_type=row[1],
                    source_id=row[2],
                    source_name=row[3],
                    source_type=row[4] or "UNKNOWN",
                    target_id=row[5],
                    target_name=row[6],
                    target_type=row[7] or "UNKNOWN",
                    confidence=float(row[8]) if row[8] else 0.0,
                    direction_relative_to_entity="inbound",
                    depth=0
                ))
        
        if direction in ("outbound", "both"):
            query = text(f"""
                SELECT 
                    r.id::text as rel_id,
                    r.relationship_type,
                    r.source_id::text,
                    se.name as source_name,
                    se.entity_type as source_type,
                    r.target_id::text,
                    te.name as target_name,
                    te.entity_type as target_type,
                    r.confidence
                FROM relationships r
                JOIN entities se ON r.source_id = se.id
                JOIN entities te ON r.target_id = te.id
                WHERE r.source_id = :entity_id
                AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
                {type_filter}
                ORDER BY r.confidence DESC
            """)
            
            rows = self.session.execute(query, {'entity_id': entity_id}).fetchall()
            
            for row in rows:
                results.append(RetrievedRelationship(
                    relationship_id=row[0],
                    relationship_type=row[1],
                    source_id=row[2],
                    source_name=row[3],
                    source_type=row[4] or "UNKNOWN",
                    target_id=row[5],
                    target_name=row[6],
                    target_type=row[7] or "UNKNOWN",
                    confidence=float(row[8]) if row[8] else 0.0,
                    direction_relative_to_entity="outbound",
                    depth=0
                ))
        
        return results
    
    def _collect_affected_entities(
        self,
        relationships: List[RetrievedRelationship],
        queried_entity_id: str
    ) -> List[Dict]:
        """
        Collect unique entities that were discovered in the traversal.
        
        Excludes the originally queried entity.
        """
        entities: Dict[str, Dict] = {}
        
        for rel in relationships:
            if rel.source_id != queried_entity_id and rel.source_id not in entities:
                entities[rel.source_id] = {
                    "id": rel.source_id,
                    "name": rel.source_name,
                    "type": rel.source_type,
                    "discovered_via": rel.relationship_type,
                    "direction": rel.direction_relative_to_entity,
                    "depth": rel.depth
                }
            
            if rel.target_id != queried_entity_id and rel.target_id not in entities:
                entities[rel.target_id] = {
                    "id": rel.target_id,
                    "name": rel.target_name,
                    "type": rel.target_type,
                    "discovered_via": rel.relationship_type,
                    "direction": rel.direction_relative_to_entity,
                    "depth": rel.depth
                }
        
        return list(entities.values())
