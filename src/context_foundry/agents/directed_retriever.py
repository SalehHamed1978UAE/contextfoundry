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

from .query_interpreter import QueryIntent
from .entity_resolver import EntityResolver

logger = logging.getLogger(__name__)

# Edge rank for relationship type priority - higher scores = more important relationships
EDGE_RANK = {
    'HOLDS_POSITION': 100,
    'CEO_OF': 95,
    'CFO_OF': 90,
    'CTO_OF': 90,
    'FOUNDED': 85,
    'FOUNDED_BY': 85,
    'OWNS': 80,
    'OWNED_BY': 80,
    'INVESTED_IN': 75,
    'WORKS_FOR': 70,
    'WORKS_AT': 70,
    'EMPLOYED_BY': 65,
    'REPORTS_TO': 60,
    'MANAGES': 55,
    'MEMBER_OF': 50,
    'SUPPLIES_TO': 45,
    'PROVIDES_TO': 45,
    'AFFILIATED_WITH': 40,
    'ASSOCIATED_WITH': 35,
    'LOCATED_IN': 30,
    'HEADQUARTERED_IN': 30,
}

DEFAULT_EDGE_RANK = 25


def get_edge_rank(relationship_type: str) -> int:
    """Get priority score for a relationship type. Higher = more important."""
    return EDGE_RANK.get(relationship_type.upper(), DEFAULT_EDGE_RANK)


def filter_by_anchor_organization(
    entities: List[Dict],
    anchor_org: str,
    prefer_higher_rank: bool = True
) -> List[Dict]:
    """
    Filter entities by anchor organization affiliation.
    
    Args:
        entities: List of entity dicts with 'name', 'type', and optional 'organization'
        anchor_org: The anchor organization name to filter by
        prefer_higher_rank: If True, sort by edge rank (descending) before filtering
        
    Returns:
        Filtered list of entities that:
        - Belong to the anchor organization, OR
        - Have no organization specified (generic entities)
    """
    if not anchor_org:
        logger.info(f"[AnchorFilter] No anchor org specified, returning all {len(entities)} entities")
        return entities
    
    anchor_lower = anchor_org.lower().strip()
    filtered = []
    rejected = []
    
    logger.info(f"[AnchorFilter] Filtering {len(entities)} entities for anchor '{anchor_org}'")
    
    for entity in entities:
        org = entity.get('organization', '').lower().strip()
        entity_name = entity.get('name', 'UNKNOWN')
        entity_type = entity.get('type', entity.get('entity_type', 'UNKNOWN'))
        
        # Keep if no organization specified (generic entity)
        if not org:
            logger.info(f"  [PASS-GENERIC] {entity_name} ({entity_type}): org='NONE' (no org specified)")
            filtered.append(entity)
            continue
        
        # Keep if matches anchor organization
        if org == anchor_lower or anchor_lower in org or org in anchor_lower:
            logger.info(f"  [PASS-MATCH] {entity_name} ({entity_type}): org='{org}' matches anchor")
            filtered.append(entity)
            continue
        
        # Reject - organization doesn't match
        logger.info(f"  [REJECT] {entity_name} ({entity_type}): org='{org}' != anchor '{anchor_lower}'")
        rejected.append(entity)
    
    logger.info(f"[AnchorFilter] Result: {len(filtered)} passed, {len(rejected)} rejected")
    
    # Sort by edge rank if requested
    if prefer_higher_rank and filtered:
        filtered.sort(
            key=lambda e: get_edge_rank(e.get('discovered_via', '')),
            reverse=True
        )
    
    return filtered


@dataclass
class RetrievedRelationship:
    """A single relationship retrieved from the graph with context metadata."""
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
    # Context metadata (Phase 3: Pipeline Integration)
    provenance_text: Optional[str] = None
    description: Optional[str] = None
    context_confidence: Optional[float] = None
    source_location: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = {
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
        # Include context if available
        if self.description:
            result["description"] = self.description
        if self.provenance_text:
            result["provenance_text"] = self.provenance_text
        if self.source_location:
            result["source_location"] = self.source_location
        return result


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
    
    def __init__(self, session: Session, tenant_id: str, anchor_organization: Optional[str] = None):
        self.session = session
        self.tenant_id = str(tenant_id)
        self.anchor_organization = anchor_organization
        self.entity_resolver = EntityResolver(session, tenant_id)
        
        self.session.execute(
            text("SELECT platform.set_current_tenant(:tid)"),
            {'tid': self.tenant_id}
        )
        
        # If no anchor provided, try to get from tenant metadata
        if not self.anchor_organization:
            self.anchor_organization = self._get_anchor_from_tenant()
        
        logger.info(f"DirectedGraphRetriever initialized for tenant {tenant_id[:8]}... (anchor: {self.anchor_organization})")
    
    def _get_anchor_from_tenant(self) -> Optional[str]:
        """Get anchor organization from tenant - check primary_organization_name first, then settings."""
        try:
            result = self.session.execute(
                text("""
                    SELECT 
                        COALESCE(primary_organization_name, settings->>'anchor_organization') as anchor
                    FROM platform.tenants
                    WHERE id = :tid
                """),
                {'tid': self.tenant_id}
            ).fetchone()

            if result and result.anchor:
                logger.info(f"[AnchorFilter] Found anchor organization: {result.anchor}")
                return result.anchor
        except Exception as e:
            logger.warning(f"[AnchorFilter] Could not get anchor organization: {e}")

        return None
    
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
        
        if intent.target_type:
            direct_rels, direct_paths = self._get_direct_target_type_neighbors(
                entity_id=entity_id,
                entity_name=entity_name,
                target_type=intent.target_type
            )
            
            if direct_rels:
                logger.info(f"Found {len(direct_rels)} direct {intent.target_type} neighbors (N_T(X))")
                
                existing_rel_ids = {r.relationship_id for r in relationships}
                for rel in direct_rels:
                    if rel.relationship_id not in existing_rel_ids:
                        relationships.append(rel)
                        existing_rel_ids.add(rel.relationship_id)
                
                existing_path_sigs = {p.to_string() for p in cascade_paths}
                for path in direct_paths:
                    if path.to_string() not in existing_path_sigs:
                        cascade_paths.append(path)
        
        affected = self._collect_affected_entities(relationships, entity_id)
        
        # CRITICAL: Filter by anchor organization to prevent cross-org contamination (e.g., Boeing in Nexus queries)
        if self.anchor_organization:
            affected_before = len(affected)
            affected = filter_by_anchor_organization(affected, self.anchor_organization)
            if affected_before != len(affected):
                logger.info(f"[AnchorFilter] Filtered {affected_before} -> {len(affected)} entities (removed {affected_before - len(affected)} cross-org)")
        
        if intent.target_type:
            affected_before = len(affected)
            affected = [e for e in affected if e.get('type', '').upper() == intent.target_type.upper()]
            logger.info(f"Filtered by target_type '{intent.target_type}': "
                       f"{affected_before} -> {len(affected)} entities")
        
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
        Handles disambiguation by picking the best candidate when multiple exist.
        """
        try:
            result = self.entity_resolver.resolve(entity_name)
            
            # Direct match - return it
            if result and result.entity and result.confidence >= 0.5:
                return {
                    'id': str(result.entity.entity_id),
                    'name': result.entity.name,
                    'type': result.entity.entity_type,
                    'confidence': result.confidence,
                    'match_stage': result.match_stage
                }
            
            # Disambiguation case - pick the best candidate
            if result and result.needs_disambiguation and result.candidates:
                # If all candidates have the same name, pick the first one
                # This handles cases like "Users Database" appearing as both DATABASE and SERVICE
                best = result.candidates[0]
                logger.info(f"Disambiguation: picking '{best.name}' ({best.entity_type}) "
                           f"from {len(result.candidates)} candidates")
                return {
                    'id': str(best.entity_id),
                    'name': best.name,
                    'type': best.entity_type,
                    'confidence': best.confidence,
                    'match_stage': result.match_stage
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Entity resolution failed: {e}")
            return None
    
    def _get_direct_target_type_neighbors(
        self,
        entity_id: str,
        entity_name: str,
        target_type: str
    ) -> tuple:
        """
        Get direct neighbors of entity X that are of the specified target_type.
        
        This implements N_T(X) - finding all entities of type T that are directly
        connected to X by ANY relationship type.
        
        This fixes the case where BR(X) = empty but teams/databases still 
        OWN or MANAGE X directly.
        
        Args:
            entity_id: The UUID of entity X
            entity_name: The name of entity X (for path building)
            target_type: The type of neighbor we want (e.g., "TEAM")
            
        Returns:
            Tuple of (List[RetrievedRelationship], List[CascadePath])
        """
        relationships = []
        cascade_paths = []
        
        query = text("""
            SELECT 
                r.id as rel_id,
                r.relationship_type,
                r.source_id,
                src.name as source_name,
                src.entity_type as source_type,
                r.target_id,
                tgt.name as target_name,
                tgt.entity_type as target_type,
                r.confidence,
                CASE 
                    WHEN r.target_id = :entity_id THEN 'inbound'
                    ELSE 'outbound'
                END as direction,
                rc.provenance_text,
                rc.description,
                rc.confidence_combined,
                rc.source_location
            FROM relationships r
            JOIN entities src ON r.source_id = src.id
            JOIN entities tgt ON r.target_id = tgt.id
            LEFT JOIN relationship_contexts rc ON r.id = rc.relationship_id
            WHERE r.tenant_id = :tenant_id
              AND (r.source_id = :entity_id OR r.target_id = :entity_id)
              AND (
                  (r.source_id = :entity_id AND tgt.entity_type = :target_type)
                  OR (r.target_id = :entity_id AND src.entity_type = :target_type)
              )
        """)
        
        try:
            result = self.session.execute(query, {
                'entity_id': entity_id,
                'tenant_id': self.tenant_id,
                'target_type': target_type.upper()
            })
            
            for row in result.fetchall():
                rel = RetrievedRelationship(
                    relationship_id=str(row.rel_id),
                    relationship_type=row.relationship_type,
                    source_id=str(row.source_id),
                    source_name=row.source_name,
                    source_type=row.source_type,
                    target_id=str(row.target_id),
                    target_name=row.target_name,
                    target_type=row.target_type,
                    confidence=row.confidence or 0.9,
                    direction_relative_to_entity=row.direction,
                    depth=0,
                    provenance_text=row.provenance_text if hasattr(row, 'provenance_text') else None,
                    description=row.description if hasattr(row, 'description') else None,
                    context_confidence=float(row.confidence_combined) if hasattr(row, 'confidence_combined') and row.confidence_combined else None,
                    source_location=row.source_location if hasattr(row, 'source_location') else None
                )
                relationships.append(rel)
                
                if row.direction == 'inbound':
                    other_name = row.source_name
                else:
                    other_name = row.target_name
                
                cascade_paths.append(CascadePath(
                    path=[entity_name, other_name],
                    depth=0,
                    relationship_types=[row.relationship_type]
                ))
                
            logger.debug(f"Direct {target_type} neighbors of {entity_name}: "
                        f"{len(relationships)} found")
            
        except Exception as e:
            logger.error(f"Failed to get direct target_type neighbors: {e}")
            self.session.rollback()
        
        return relationships, cascade_paths
    
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
        
        Tracks ALL valid paths to each entity (not just the first discovery).
        Uses path signatures to avoid duplicate paths while allowing multiple
        routes to the same entity.
        
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
        
        # Track ALL paths to each entity: entity_id -> list of (path_names, path_rel_types)
        entity_all_paths: Dict[str, List[tuple]] = {entity_id: [([entity_name], [])]}
        
        # Track path signatures to avoid exact duplicates
        seen_path_signatures: Set[str] = set()
        
        # Track visited per depth to prevent infinite loops while allowing multi-path
        visited_at_depth: Dict[str, int] = {entity_id: 0}
        
        current_frontier: Set[str] = {entity_id}
        
        for current_depth in range(1, depth + 1):
            next_frontier: Set[str] = set()
            
            for frontier_entity_id in current_frontier:
                # Get all paths to this frontier entity
                paths_to_here = entity_all_paths.get(frontier_entity_id, [([entity_name], [])])
                
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
                    
                    # Build paths through each route to get here
                    for current_path, current_rel_types in paths_to_here:
                        new_path = current_path + [other_name]
                        new_rel_types = current_rel_types + [rel.relationship_type]
                        
                        # Create path signature to detect duplicates
                        path_sig = "->".join(new_path) + ":" + ",".join(new_rel_types)
                        
                        if path_sig not in seen_path_signatures:
                            seen_path_signatures.add(path_sig)
                            
                            # Store path for potential further extension
                            if other_id not in entity_all_paths:
                                entity_all_paths[other_id] = []
                            entity_all_paths[other_id].append((new_path, new_rel_types))
                            
                            # Create cascade path
                            cascade_paths.append(CascadePath(
                                path=new_path,
                                depth=current_depth,
                                relationship_types=new_rel_types
                            ))
                    
                    # Add to frontier only if not visited at equal or earlier depth
                    if other_id not in visited_at_depth or visited_at_depth[other_id] > current_depth:
                        next_frontier.add(other_id)
                        visited_at_depth[other_id] = current_depth
            
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
                    r.confidence,
                    rc.provenance_text,
                    rc.description,
                    rc.confidence_combined,
                    rc.source_location
                FROM relationships r
                JOIN entities se ON r.source_id = se.id
                JOIN entities te ON r.target_id = te.id
                LEFT JOIN relationship_contexts rc ON r.id = rc.relationship_id
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
                    depth=0,
                    provenance_text=row[9] if len(row) > 9 else None,
                    description=row[10] if len(row) > 10 else None,
                    context_confidence=float(row[11]) if len(row) > 11 and row[11] else None,
                    source_location=row[12] if len(row) > 12 else None
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
                    r.confidence,
                    rc.provenance_text,
                    rc.description,
                    rc.confidence_combined,
                    rc.source_location
                FROM relationships r
                JOIN entities se ON r.source_id = se.id
                JOIN entities te ON r.target_id = te.id
                LEFT JOIN relationship_contexts rc ON r.id = rc.relationship_id
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
                    depth=0,
                    provenance_text=row[9] if len(row) > 9 else None,
                    description=row[10] if len(row) > 10 else None,
                    context_confidence=float(row[11]) if len(row) > 11 and row[11] else None,
                    source_location=row[12] if len(row) > 12 else None
                ))
        
        return results
    
    def _get_entity_organization(self, entity_id: str) -> Optional[str]:
        """
        Look up the organization an entity belongs to via WORKS_FOR, PART_OF, or entity properties.
        
        Returns the organization name if found, None otherwise.
        """
        try:
            result = self.session.execute(
                text("""
                    SELECT DISTINCT e2.canonical_name as org_name
                    FROM relationships r
                    JOIN entities e2 ON r.target_id = e2.id
                    WHERE r.source_id = :entity_id
                    AND r.relationship_type IN ('WORKS_FOR', 'PART_OF', 'EMPLOYED_BY', 'MEMBER_OF')
                    AND e2.entity_type IN ('ORGANIZATION', 'COMPANY', 'CORPORATION')
                    AND r.lifecycle = 'TRUSTED'
                    LIMIT 1
                """),
                {'entity_id': entity_id}
            ).fetchone()
            
            if result:
                return result[0]
            
            result = self.session.execute(
                text("""
                    SELECT properties->>'organization' as org
                    FROM entities
                    WHERE id = :entity_id
                    AND properties->>'organization' IS NOT NULL
                """),
                {'entity_id': entity_id}
            ).fetchone()
            
            if result and result[0]:
                return result[0]
                
        except Exception as e:
            logger.debug(f"Error looking up organization for entity {entity_id}: {e}")
        
        return None
    
    def _collect_affected_entities(
        self,
        relationships: List[RetrievedRelationship],
        queried_entity_id: str
    ) -> List[Dict]:
        """
        Collect unique entities that were discovered in the traversal.
        
        Excludes the originally queried entity.
        Enriches each entity with organization affiliation for anchor filtering.
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
                    "depth": rel.depth,
                    "organization": None
                }
            
            if rel.target_id != queried_entity_id and rel.target_id not in entities:
                entities[rel.target_id] = {
                    "id": rel.target_id,
                    "name": rel.target_name,
                    "type": rel.target_type,
                    "discovered_via": rel.relationship_type,
                    "direction": rel.direction_relative_to_entity,
                    "depth": rel.depth,
                    "organization": None
                }
        
        entity_ids = list(entities.keys())
        if entity_ids and self.anchor_organization:
            org_lookup = self._batch_get_entity_organizations(entity_ids)
            for entity_id, org in org_lookup.items():
                if entity_id in entities:
                    entities[entity_id]["organization"] = org
            
            enriched_count = sum(1 for e in entities.values() if e.get("organization"))
            logger.debug(f"[OrgEnrich] Enriched {enriched_count}/{len(entities)} entities with organization")
        
        return list(entities.values())
    
    def _batch_get_entity_organizations(self, entity_ids: List[str]) -> Dict[str, str]:
        """
        Batch lookup organizations for multiple entities.
        Returns dict mapping entity_id -> organization_name.
        """
        if not entity_ids:
            return {}
        
        org_lookup: Dict[str, str] = {}
        
        try:
            result = self.session.execute(
                text("""
                    SELECT r.source_id, e2.canonical_name as org_name
                    FROM relationships r
                    JOIN entities e2 ON r.target_id = e2.id
                    WHERE r.source_id = ANY(:entity_ids)
                    AND r.relationship_type IN ('WORKS_FOR', 'PART_OF', 'EMPLOYED_BY', 'MEMBER_OF')
                    AND e2.entity_type IN ('ORGANIZATION', 'COMPANY', 'CORPORATION')
                    AND r.lifecycle = 'TRUSTED'
                """),
                {'entity_ids': entity_ids}
            ).fetchall()
            
            for row in result:
                entity_id, org_name = str(row[0]), row[1]
                if entity_id not in org_lookup:
                    org_lookup[entity_id] = org_name
            
            remaining_ids = [eid for eid in entity_ids if eid not in org_lookup]
            if remaining_ids:
                result = self.session.execute(
                    text("""
                        SELECT id::text, properties->>'organization' as org
                        FROM entities
                        WHERE id = ANY(:entity_ids)
                        AND properties->>'organization' IS NOT NULL
                    """),
                    {'entity_ids': remaining_ids}
                ).fetchall()
                
                for row in result:
                    entity_id, org = str(row[0]), row[1]
                    if org and entity_id not in org_lookup:
                        org_lookup[entity_id] = org
                        
        except Exception as e:
            logger.warning(f"Error in batch org lookup: {e}")
        
        return org_lookup
