"""
Inference Engine - Rule-based and vector similarity inference for frontier nodes.

This module implements the speculative layer (Tier 2 and Tier 3) that hypothesizes
likely relationships beyond the confirmed knowledge frontier.

Tier 2: Rule-based inference (transitive dependencies, co-occurrence, shared dependencies)
Tier 3: Vector similarity (embedding-based entity similarity)

All rules are schema-driven, not domain-specific.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from ..models.schema import Entity, Relationship, Document, LifecycleState, get_session
from ..config.domain_schema import (
    get_schema_loader, 
    FrontierNode, 
    FrontierReason,
    DomainSchema
)
from ..utils.logger import logger


@dataclass
class InferredRelationship:
    """A hypothesized relationship inferred by the rule engine."""
    source_entity_id: str
    source_entity_name: str
    source_entity_type: str
    target_entity_id: str
    target_entity_name: str
    target_entity_type: str
    inferred_relationship_type: str  # Prefixed: LIKELY_DEPENDS_ON, POTENTIALLY_AFFECTS, etc.
    confidence: float
    rule_id: str
    rule_name: str
    supporting_evidence: List[str] = field(default_factory=list)
    inference_method: str = "rule_based"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "source_entity_id": self.source_entity_id,
            "source_entity_name": self.source_entity_name,
            "source_entity_type": self.source_entity_type,
            "target_entity_id": self.target_entity_id,
            "target_entity_name": self.target_entity_name,
            "target_entity_type": self.target_entity_type,
            "inferred_relationship_type": self.inferred_relationship_type,
            "confidence": round(self.confidence, 3),
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "supporting_evidence": self.supporting_evidence,
            "inference_method": self.inference_method
        }


@dataclass
class SimilarEntity:
    """An entity found via vector similarity to a frontier node."""
    entity_id: str
    entity_name: str
    entity_type: str
    confidence: float
    similarity_score: float
    co_occurrence_score: float
    inference_method: str = "similarity"
    supporting_evidence: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "confidence": round(self.confidence, 3),
            "similarity_score": round(self.similarity_score, 3),
            "co_occurrence_score": round(self.co_occurrence_score, 3),
            "inference_method": self.inference_method,
            "supporting_evidence": self.supporting_evidence
        }


@dataclass
class SpeculativeResult:
    """Combined speculative results from inference and similarity."""
    inferred: List[InferredRelationship] = field(default_factory=list)
    similar: List[SimilarEntity] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "inferred": [r.to_dict() for r in self.inferred],
            "similar": [s.to_dict() for s in self.similar]
        }
    
    @property
    def total_count(self) -> int:
        return len(self.inferred) + len(self.similar)


class InferenceRule:
    """Base class for inference rules."""
    
    def __init__(self, rule_id: str, name: str, confidence_modifier: float):
        self.rule_id = rule_id
        self.name = name
        self.confidence_modifier = confidence_modifier
    
    def apply(
        self, 
        frontier_node: FrontierNode, 
        session: Session,
        schema: DomainSchema,
        visited_entities: Set[str]
    ) -> List[InferredRelationship]:
        """Apply this rule to a frontier node and return inferred relationships."""
        raise NotImplementedError


class TransitiveDependencyRule(InferenceRule):
    """
    Transitive Dependency Rule: A→B→C implies A→C
    
    When at frontier node C (which has no outgoing edges), look backwards:
    - Find B where B→C (direct incoming edge to frontier)
    - Find A where A→B (indirect edge, one hop back)
    - Infer: A likely depends on C (A→C)
    
    This correctly handles frontiers which by definition have no outgoing edges.
    """
    
    def __init__(self):
        super().__init__(
            rule_id="transitive_dependency",
            name="Transitive Dependency",
            confidence_modifier=0.7
        )
    
    def apply(
        self, 
        frontier_node: FrontierNode, 
        session: Session,
        schema: DomainSchema,
        visited_entities: Set[str]
    ) -> List[InferredRelationship]:
        inferred = []
        
        rel_types_to_check = self._get_transitive_relationship_types(schema)
        
        for rel_type in rel_types_to_check:
            direct_incoming = session.query(Relationship).filter(
                Relationship.target_id == frontier_node.entity_id,
                Relationship.relationship_type == rel_type,
                Relationship.lifecycle_state == LifecycleState.TRUSTED
            ).all()
            
            for direct_rel in direct_incoming:
                middle_entity_id = direct_rel.source_id
                
                indirect_incoming = session.query(Relationship).filter(
                    Relationship.target_id == middle_entity_id,
                    Relationship.relationship_type == rel_type,
                    Relationship.lifecycle_state == LifecycleState.TRUSTED
                ).all()
                
                for indirect_rel in indirect_incoming:
                    source_entity = session.query(Entity).filter(
                        Entity.id == indirect_rel.source_id,
                        Entity.lifecycle_state == LifecycleState.TRUSTED
                    ).first()
                    
                    frontier_entity = session.query(Entity).filter(
                        Entity.id == frontier_node.entity_id,
                        Entity.lifecycle_state == LifecycleState.TRUSTED
                    ).first()
                    
                    middle_entity = session.query(Entity).filter(
                        Entity.id == middle_entity_id,
                        Entity.lifecycle_state == LifecycleState.TRUSTED
                    ).first()
                    
                    if not source_entity or not frontier_entity:
                        continue
                    
                    if str(source_entity.id) == str(frontier_entity.id):
                        continue
                    
                    existing = session.query(Relationship).filter(
                        Relationship.source_id == source_entity.id,
                        Relationship.target_id == frontier_entity.id,
                        Relationship.relationship_type == rel_type,
                        Relationship.lifecycle_state == LifecycleState.TRUSTED
                    ).first()
                    
                    if existing:
                        continue
                    
                    direct_conf = float(direct_rel.confidence) if direct_rel.confidence else 0.0
                    indirect_conf = float(indirect_rel.confidence) if indirect_rel.confidence else 0.0
                    combined_confidence = min(direct_conf, indirect_conf) * self.confidence_modifier
                    
                    middle_name = middle_entity.name if middle_entity else "unknown"
                    
                    inferred.append(InferredRelationship(
                        source_entity_id=str(source_entity.id),
                        source_entity_name=str(source_entity.name),
                        source_entity_type=str(source_entity.entity_type),
                        target_entity_id=str(frontier_entity.id),
                        target_entity_name=str(frontier_entity.name),
                        target_entity_type=str(frontier_entity.entity_type),
                        inferred_relationship_type=f"LIKELY_{rel_type}",
                        confidence=combined_confidence,
                        rule_id=self.rule_id,
                        rule_name=self.name,
                        supporting_evidence=[
                            f"{source_entity.name} → {middle_name} ({rel_type})",
                            f"{middle_name} → {frontier_entity.name} ({rel_type})"
                        ]
                    ))
        
        return inferred
    
    def _get_transitive_relationship_types(self, schema: DomainSchema) -> List[str]:
        """Get relationship types that support transitive inference."""
        default_transitive = ['DEPENDS_ON', 'REPORTS_TO', 'PART_OF', 'REQUIRES', 'USES', 'CALLS', 'IMPORTS']
        transitive_types = []
        
        if hasattr(schema, 'relationship_types'):
            rel_types = schema.relationship_types
            if isinstance(rel_types, dict):
                for rel_name, rel_config in rel_types.items():
                    if rel_name in default_transitive:
                        transitive_types.append(rel_name)
                    elif hasattr(rel_config, 'semantics') and rel_config.semantics:
                        modes = getattr(rel_config.semantics, 'modes', None) or {}
                        if 'dependency' in modes:
                            transitive_types.append(rel_name)
            elif isinstance(rel_types, list):
                for rel in rel_types:
                    if hasattr(rel, 'name') and rel.name in default_transitive:
                        transitive_types.append(rel.name)
                    elif isinstance(rel, str) and rel in default_transitive:
                        transitive_types.append(rel)
        
        return transitive_types if transitive_types else ['DEPENDS_ON']


class CoOccurrenceRule(InferenceRule):
    """
    Co-occurrence Rule: Entities mentioned together in 3+ documents may be related.
    
    Searches Document content for entity name mentions to find co-occurring entities.
    """
    
    MIN_CO_OCCURRENCE = 3
    
    def __init__(self):
        super().__init__(
            rule_id="co_occurrence",
            name="Co-occurrence",
            confidence_modifier=0.6
        )
    
    def apply(
        self, 
        frontier_node: FrontierNode, 
        session: Session,
        schema: DomainSchema,
        visited_entities: Set[str]
    ) -> List[InferredRelationship]:
        inferred = []
        
        try:
            frontier_uuid = uuid.UUID(frontier_node.entity_id) if isinstance(frontier_node.entity_id, str) else frontier_node.entity_id
        except ValueError:
            return inferred
        
        frontier_entity = session.query(Entity).filter(
            Entity.id == frontier_uuid
        ).first()
        
        if not frontier_entity:
            return inferred
        
        docs_mentioning_frontier = session.query(Document).filter(
            Document.content.ilike(f"%{frontier_entity.name}%")
        ).all()
        
        if len(docs_mentioning_frontier) < self.MIN_CO_OCCURRENCE:
            return inferred
        
        other_entities = session.query(Entity).filter(
            Entity.id != frontier_uuid,
            Entity.lifecycle_state == LifecycleState.TRUSTED
        ).all()
        
        for other_entity in other_entities:
            if other_entity.name.lower() == frontier_entity.name.lower():
                continue
            
            shared_docs = []
            for doc in docs_mentioning_frontier:
                if other_entity.name.lower() in doc.content.lower():
                    shared_docs.append(doc)
            
            if len(shared_docs) < self.MIN_CO_OCCURRENCE:
                continue
            
            existing = session.query(Relationship).filter(
                or_(
                    and_(
                        Relationship.source_id == frontier_uuid,
                        Relationship.target_id == other_entity.id
                    ),
                    and_(
                        Relationship.source_id == other_entity.id,
                        Relationship.target_id == frontier_uuid
                    )
                ),
                Relationship.lifecycle_state == LifecycleState.TRUSTED
            ).first()
            
            if existing:
                continue
            
            doc_confidence = min(1.0, len(shared_docs) / 5) * self.confidence_modifier
            
            inferred.append(InferredRelationship(
                source_entity_id=str(frontier_entity.id),
                source_entity_name=str(frontier_entity.name),
                source_entity_type=str(frontier_entity.entity_type),
                target_entity_id=str(other_entity.id),
                target_entity_name=str(other_entity.name),
                target_entity_type=str(other_entity.entity_type),
                inferred_relationship_type="POTENTIALLY_RELATES_TO",
                confidence=doc_confidence,
                rule_id=self.rule_id,
                rule_name=self.name,
                supporting_evidence=[
                    f"Co-mentioned in {len(shared_docs)} documents",
                    *[f"- {doc.title}" for doc in shared_docs[:3]]
                ]
            ))
        
        return inferred


class SharedDependencyRule(InferenceRule):
    """
    Shared Dependency Rule: If A→X and B→X, A and B may be related.
    
    If the frontier node X is a target of multiple entities (A, B, C...),
    those entities may have an indirect relationship through their shared dependency.
    """
    
    def __init__(self):
        super().__init__(
            rule_id="shared_dependency",
            name="Shared Dependency",
            confidence_modifier=0.5
        )
    
    def apply(
        self, 
        frontier_node: FrontierNode, 
        session: Session,
        schema: DomainSchema,
        visited_entities: Set[str]
    ) -> List[InferredRelationship]:
        inferred = []
        
        incoming_rels = session.query(Relationship).filter(
            Relationship.target_id == frontier_node.entity_id,
            Relationship.lifecycle_state == LifecycleState.TRUSTED
        ).all()
        
        if len(incoming_rels) < 2:
            return inferred
        
        dependents = []
        for rel in incoming_rels:
            entity = session.query(Entity).filter(
                Entity.id == rel.source_id,
                Entity.lifecycle_state == LifecycleState.TRUSTED
            ).first()
            if entity:
                dependents.append((entity, rel.relationship_type, rel.confidence))
        
        for i, (entity_a, rel_type_a, conf_a) in enumerate(dependents):
            for entity_b, rel_type_b, conf_b in dependents[i+1:]:
                if str(entity_a.id) in visited_entities and str(entity_b.id) in visited_entities:
                    continue
                
                existing = session.query(Relationship).filter(
                    or_(
                        and_(
                            Relationship.source_id == entity_a.id,
                            Relationship.target_id == entity_b.id
                        ),
                        and_(
                            Relationship.source_id == entity_b.id,
                            Relationship.target_id == entity_a.id
                        )
                    ),
                    Relationship.lifecycle_state == LifecycleState.TRUSTED
                ).first()
                
                if existing:
                    continue
                
                conf_a_val = float(conf_a) if conf_a else 0.0
                conf_b_val = float(conf_b) if conf_b else 0.0
                combined_confidence = min(conf_a_val, conf_b_val) * self.confidence_modifier
                
                inferred.append(InferredRelationship(
                    source_entity_id=str(entity_a.id),
                    source_entity_name=str(entity_a.name),
                    source_entity_type=str(entity_a.entity_type),
                    target_entity_id=str(entity_b.id),
                    target_entity_name=str(entity_b.name),
                    target_entity_type=str(entity_b.entity_type),
                    inferred_relationship_type="POTENTIALLY_RELATED_VIA",
                    confidence=combined_confidence,
                    rule_id=self.rule_id,
                    rule_name=self.name,
                    supporting_evidence=[
                        f"Both depend on {frontier_node.entity_name}",
                        f"{entity_a.name} → {frontier_node.entity_name} ({rel_type_a})",
                        f"{entity_b.name} → {frontier_node.entity_name} ({rel_type_b})"
                    ]
                ))
        
        return inferred


class InferenceEngine:
    """
    Main inference engine that applies rules and similarity matching to frontier nodes.
    
    Schema-driven design - all inference is based on the loaded domain schema,
    not hardcoded to any specific domain.
    
    SECURITY: Requires tenant_id for defense-in-depth filtering.
    RLS provides the authoritative security boundary, but application-level
    filtering provides belt-and-suspenders protection.
    """
    
    def __init__(self, session: Optional[Session] = None, tenant_id: str = None):
        self.session = session or get_session()
        self.tenant_id = tenant_id
        self.schema_loader = get_schema_loader()
        
        self.rules: List[InferenceRule] = [
            TransitiveDependencyRule(),
            CoOccurrenceRule(),
            SharedDependencyRule()
        ]
        
        self.shared_dependency_rule = SharedDependencyRule()
        self.co_occurrence_rule = CoOccurrenceRule()
        
        if not tenant_id:
            logger.warning("InferenceEngine initialized without tenant_id - queries will not be tenant-scoped")
        else:
            logger.info(f"InferenceEngine initialized for tenant {tenant_id[:8]}... with {len(self.rules)} rules")
    
    def _apply_tenant_filter(self, query, model_class):
        """Apply tenant_id filter if tenant_id is set (defense-in-depth)."""
        if self.tenant_id and hasattr(model_class, 'tenant_id'):
            return query.filter(model_class.tenant_id == self.tenant_id)
        return query
    
    def _get_entity_by_id(self, entity_id) -> Optional[Entity]:
        """Get entity by ID with tenant filtering (defense-in-depth)."""
        query = self.session.query(Entity).filter(Entity.id == entity_id)
        query = self._apply_tenant_filter(query, Entity)
        return query.first()
    
    def find_co_occurrences_for_entity(
        self,
        entity_id: str,
        visited_entities: Optional[Set[str]] = None
    ) -> List[InferredRelationship]:
        """
        Find co-occurrence relationships for a specific entity.
        
        Used when an entity has no neighbors (and thus no frontiers),
        to still apply co-occurrence analysis based on document content.
        
        Args:
            entity_id: ID of the entity to analyze
            visited_entities: Set of entity IDs to exclude
            
        Returns:
            List of inferred relationships via co-occurrence
        """
        visited = visited_entities or set()
        schema = self.schema_loader.schema
        
        try:
            entity_uuid = entity_id if isinstance(entity_id, uuid.UUID) else uuid.UUID(entity_id)
        except ValueError:
            return []
        
        entity = self._get_entity_by_id(entity_uuid)
        if not entity:
            return []
        
        pseudo_frontier = FrontierNode(
            entity_id=str(entity.id),
            entity_name=entity.name,
            entity_type=entity.entity_type,
            reason=FrontierReason.NO_RELATIONSHIPS,
            message="Entity has no relationships - checking co-occurrence",
            depth=0
        )
        
        inferred = self.co_occurrence_rule.apply(pseudo_frontier, self.session, schema, visited)
        
        logger.info(f"Co-occurrence analysis for {entity.name}: {len(inferred)} relationships found")
        
        return inferred
    
    def find_transitive_chains(
        self,
        center_id: str,
        neighbor_ids: List[str],
        visited_entities: Optional[Set[str]] = None
    ) -> List[InferredRelationship]:
        """
        Find transitive chains from center entity through neighbors.
        
        For center A with neighbor B, look for B's outgoing edges to C.
        If A→B and B→C exist, infer A→C (LIKELY_DEPENDS_ON).
        
        This runs on the center entity looking FORWARD, rather than
        waiting for frontiers to look backwards.
        
        Args:
            center_id: ID of the center entity being expanded
            neighbor_ids: List of neighbor entity IDs (direct targets of center)
            visited_entities: Set of entity IDs to exclude from results
            
        Returns:
            List of inferred transitive relationships
        """
        visited = visited_entities or set()
        inferred = []
        schema = self.schema_loader.schema
        
        try:
            center_uuid = center_id if isinstance(center_id, uuid.UUID) else uuid.UUID(center_id)
        except ValueError:
            return []
        
        center_entity = self._get_entity_by_id(center_uuid)
        if not center_entity:
            return []
        
        rel_types = self._get_transitive_relationship_types(schema)
        
        for neighbor_id in neighbor_ids:
            try:
                neighbor_uuid = neighbor_id if isinstance(neighbor_id, uuid.UUID) else uuid.UUID(neighbor_id)
            except ValueError:
                continue
            
            rel_query = self.session.query(Relationship).filter(
                Relationship.source_id == center_uuid,
                Relationship.target_id == neighbor_uuid,
                Relationship.lifecycle_state == LifecycleState.TRUSTED
            )
            rel_query = self._apply_tenant_filter(rel_query, Relationship)
            center_to_neighbor = rel_query.first()
            
            if not center_to_neighbor:
                continue
            
            if center_to_neighbor.relationship_type not in rel_types:
                continue
            
            outgoing_query = self.session.query(Relationship).filter(
                Relationship.source_id == neighbor_uuid,
                Relationship.relationship_type == center_to_neighbor.relationship_type,
                Relationship.lifecycle_state == LifecycleState.TRUSTED
            )
            outgoing_query = self._apply_tenant_filter(outgoing_query, Relationship)
            neighbor_outgoing = outgoing_query.all()
            
            for rel in neighbor_outgoing:
                target_id = rel.target_id
                
                if str(target_id) in visited or str(target_id) == str(center_uuid):
                    continue
                
                existing_query = self.session.query(Relationship).filter(
                    Relationship.source_id == center_uuid,
                    Relationship.target_id == target_id,
                    Relationship.lifecycle_state == LifecycleState.TRUSTED
                )
                existing_query = self._apply_tenant_filter(existing_query, Relationship)
                existing = existing_query.first()
                
                if existing:
                    continue
                
                target_entity = self._get_entity_by_id(target_id)
                neighbor_entity = self._get_entity_by_id(neighbor_uuid)
                
                if not target_entity or not neighbor_entity:
                    continue
                
                conf1 = float(center_to_neighbor.confidence) if center_to_neighbor.confidence else 0.9
                conf2 = float(rel.confidence) if rel.confidence else 0.9
                combined = conf1 * conf2 * 0.7
                
                inferred.append(InferredRelationship(
                    source_entity_id=str(center_entity.id),
                    source_entity_name=str(center_entity.name),
                    source_entity_type=str(center_entity.entity_type),
                    target_entity_id=str(target_entity.id),
                    target_entity_name=str(target_entity.name),
                    target_entity_type=str(target_entity.entity_type),
                    inferred_relationship_type=f"LIKELY_{center_to_neighbor.relationship_type}",
                    confidence=combined,
                    rule_id="transitive_dependency",
                    rule_name="Transitive Dependency",
                    supporting_evidence=[
                        f"{center_entity.name} → {neighbor_entity.name} ({center_to_neighbor.relationship_type})",
                        f"{neighbor_entity.name} → {target_entity.name} ({rel.relationship_type})"
                    ]
                ))
        
        logger.info(f"Transitive chain analysis from {center_entity.name}: {len(inferred)} relationships found")
        
        return inferred
    
    def _get_transitive_relationship_types(self, schema: DomainSchema) -> List[str]:
        """Get relationship types that support transitive inference."""
        transitive_types = []
        for rel in schema.relationship_types:
            if hasattr(rel, 'semantics'):
                semantics = rel.semantics or {}
                if semantics.get('transitive', False) or rel.name in ['DEPENDS_ON', 'REPORTS_TO', 'PART_OF']:
                    transitive_types.append(rel.name)
            elif hasattr(rel, 'name'):
                if rel.name in ['DEPENDS_ON', 'REPORTS_TO', 'PART_OF']:
                    transitive_types.append(rel.name)
            elif isinstance(rel, str):
                if rel in ['DEPENDS_ON', 'REPORTS_TO', 'PART_OF']:
                    transitive_types.append(rel)
        return transitive_types if transitive_types else ['DEPENDS_ON', 'REPORTS_TO', 'PART_OF']
    
    def find_shared_dependencies(
        self,
        neighbor_ids: List[str],
        center_id: str,
        visited_entities: Optional[Set[str]] = None
    ) -> List[InferredRelationship]:
        """
        Find shared dependency relationships among neighbors.
        
        This handles the case where a neighbor has multiple incoming edges
        (making it NOT a frontier, but still useful for inference).
        
        Args:
            neighbor_ids: List of neighbor entity IDs to analyze
            center_id: ID of the center entity being expanded
            visited_entities: Set of entity IDs to exclude from results
            
        Returns:
            List of inferred relationships via shared dependencies
        """
        visited = visited_entities or set()
        inferred = []
        schema = self.schema_loader.schema
        
        for neighbor_id in neighbor_ids:
            try:
                neighbor_uuid = neighbor_id if isinstance(neighbor_id, uuid.UUID) else uuid.UUID(neighbor_id)
            except ValueError:
                continue
            
            incoming_query = self.session.query(Relationship).filter(
                Relationship.target_id == neighbor_uuid,
                Relationship.lifecycle_state == LifecycleState.TRUSTED
            )
            incoming_query = self._apply_tenant_filter(incoming_query, Relationship)
            incoming_rels = incoming_query.all()
            
            if len(incoming_rels) < 2:
                continue
            
            dependents = []
            for rel in incoming_rels:
                entity = self._get_entity_by_id(rel.source_id)
                if entity and entity.lifecycle_state == LifecycleState.TRUSTED:
                    dependents.append((entity, rel.relationship_type, rel.confidence))
            
            neighbor_entity = self._get_entity_by_id(neighbor_uuid)
            neighbor_name = neighbor_entity.name if neighbor_entity else "unknown"
            
            for i, (entity_a, rel_type_a, conf_a) in enumerate(dependents):
                for entity_b, rel_type_b, conf_b in dependents[i+1:]:
                    if str(entity_a.id) in visited and str(entity_b.id) in visited:
                        continue
                    
                    existing_q = self.session.query(Relationship).filter(
                        or_(
                            and_(
                                Relationship.source_id == entity_a.id,
                                Relationship.target_id == entity_b.id
                            ),
                            and_(
                                Relationship.source_id == entity_b.id,
                                Relationship.target_id == entity_a.id
                            )
                        ),
                        Relationship.lifecycle_state == LifecycleState.TRUSTED
                    )
                    existing_q = self._apply_tenant_filter(existing_q, Relationship)
                    existing = existing_q.first()
                    
                    if existing:
                        continue
                    
                    conf_a_val = float(conf_a) if conf_a else 0.0
                    conf_b_val = float(conf_b) if conf_b else 0.0
                    combined_confidence = min(conf_a_val, conf_b_val) * 0.5
                    
                    inferred.append(InferredRelationship(
                        source_entity_id=str(entity_a.id),
                        source_entity_name=str(entity_a.name),
                        source_entity_type=str(entity_a.entity_type),
                        target_entity_id=str(entity_b.id),
                        target_entity_name=str(entity_b.name),
                        target_entity_type=str(entity_b.entity_type),
                        inferred_relationship_type="POTENTIALLY_RELATED_VIA",
                        confidence=combined_confidence,
                        rule_id="shared_dependency",
                        rule_name="Shared Dependency",
                        supporting_evidence=[
                            f"Both depend on {neighbor_name}",
                            f"{entity_a.name} → {neighbor_name} ({rel_type_a})",
                            f"{entity_b.name} → {neighbor_name} ({rel_type_b})"
                        ]
                    ))
        
        logger.info(f"Shared dependency analysis: {len(inferred)} relationships found "
                   f"from {len(neighbor_ids)} neighbors")
        
        return inferred
    
    def infer_from_frontiers(
        self,
        frontier_nodes: List[FrontierNode],
        visited_entities: Optional[Set[str]] = None,
        max_inferences_per_node: int = 5
    ) -> SpeculativeResult:
        """
        Apply inference rules to frontier nodes and return speculative relationships.
        
        Args:
            frontier_nodes: List of frontier nodes to analyze
            visited_entities: Set of entity IDs already in the confirmed result
            max_inferences_per_node: Maximum inferences per frontier node
            
        Returns:
            SpeculativeResult with inferred relationships
        """
        visited = visited_entities or set()
        result = SpeculativeResult()
        schema = self.schema_loader.schema
        
        for frontier in frontier_nodes:
            node_inferences = []
            
            for rule in self.rules:
                try:
                    inferred = rule.apply(frontier, self.session, schema, visited)
                    node_inferences.extend(inferred)
                    
                    if inferred:
                        logger.debug(f"Rule '{rule.name}' found {len(inferred)} inferences "
                                   f"for {frontier.entity_name}")
                except Exception as e:
                    logger.warning(f"Rule {rule.rule_id} failed on {frontier.entity_name}: {e}")
            
            node_inferences.sort(key=lambda x: x.confidence, reverse=True)
            result.inferred.extend(node_inferences[:max_inferences_per_node])
        
        seen_pairs = set()
        unique_inferred = []
        for inf in result.inferred:
            pair = (inf.source_entity_id, inf.target_entity_id)
            reverse_pair = (inf.target_entity_id, inf.source_entity_id)
            if pair not in seen_pairs and reverse_pair not in seen_pairs:
                seen_pairs.add(pair)
                unique_inferred.append(inf)
        result.inferred = unique_inferred
        
        logger.info(f"Inference complete: {len(result.inferred)} relationships inferred "
                   f"from {len(frontier_nodes)} frontier nodes")
        
        return result
    
    def find_similar_entities(
        self,
        frontier_nodes: List[FrontierNode],
        visited_entities: Optional[Set[str]] = None,
        min_confidence: float = 0.3,
        max_similar_per_node: int = 3
    ) -> List[SimilarEntity]:
        """
        Find entities similar to frontier nodes via vector embeddings.
        
        Args:
            frontier_nodes: List of frontier nodes to find similar entities for
            visited_entities: Set of entity IDs to exclude
            min_confidence: Minimum confidence threshold for results
            max_similar_per_node: Maximum similar entities per frontier node
            
        Returns:
            List of similar entities
        """
        visited = visited_entities or set()
        similar_entities = []
        schema = self.schema_loader.schema
        
        from ..memory.episodic import EpisodicMemory
        episodic = EpisodicMemory(self.session, tenant_id=self.tenant_id)
        
        for frontier in frontier_nodes:
            try:
                similar = self._find_similar_for_node(
                    frontier, 
                    episodic, 
                    schema, 
                    visited,
                    min_confidence,
                    max_similar_per_node
                )
                similar_entities.extend(similar)
            except Exception as e:
                logger.warning(f"Similarity search failed for {frontier.entity_name}: {e}")
        
        seen_ids = set()
        unique_similar = []
        for sim in similar_entities:
            if sim.entity_id not in seen_ids:
                seen_ids.add(sim.entity_id)
                unique_similar.append(sim)
        
        logger.info(f"Similarity search complete: {len(unique_similar)} similar entities "
                   f"found for {len(frontier_nodes)} frontier nodes")
        
        return unique_similar
    
    def _find_similar_for_node(
        self,
        frontier: FrontierNode,
        episodic: 'EpisodicMemory',
        schema: DomainSchema,
        visited: Set[str],
        min_confidence: float,
        max_results: int
    ) -> List[SimilarEntity]:
        """Find entities similar to a single frontier node."""
        similar = []
        
        entity = self._get_entity_by_id(frontier.entity_id)
        
        if not entity:
            return similar
        
        entity_desc = str(entity.description) if entity.description else ''
        search_text = f"{entity.name} {entity_desc}"
        
        compatible_types = self._get_compatible_types(frontier.entity_type, schema)
        
        try:
            vector_results = episodic.search_similar(
                query_text=search_text,
                limit=max_results * 3,
                min_similarity=0.4
            )
        except Exception as e:
            logger.debug(f"Vector search failed: {e}")
            return similar
        
        for doc in vector_results:
            doc_query = self.session.query(Entity).filter(
                Entity.source_document_id == doc.get('document_id'),
                Entity.lifecycle_state == LifecycleState.TRUSTED,
                Entity.id != frontier.entity_id
            )
            doc_query = self._apply_tenant_filter(doc_query, Entity)
            doc_entities = doc_query.all()
            
            for ent in doc_entities:
                if str(ent.id) in visited:
                    continue
                
                if ent.entity_type not in compatible_types:
                    continue
                
                similarity_score = doc.get('similarity', 0.5)
                co_occurrence = self._calculate_co_occurrence(
                    frontier.entity_id, str(ent.id)
                )
                
                combined_confidence = (similarity_score * 0.6) + (co_occurrence * 0.4)
                
                if combined_confidence >= min_confidence:
                    supporting_docs = []
                    if doc.get('title'):
                        supporting_docs.append(doc.get('title'))
                    
                    similar.append(SimilarEntity(
                        entity_id=str(ent.id),
                        entity_name=str(ent.name),
                        entity_type=str(ent.entity_type),
                        confidence=combined_confidence,
                        similarity_score=similarity_score,
                        co_occurrence_score=co_occurrence,
                        supporting_evidence=supporting_docs
                    ))
        
        similar.sort(key=lambda x: x.confidence, reverse=True)
        return similar[:max_results]
    
    def _get_compatible_types(self, entity_type: str, schema: DomainSchema) -> Set[str]:
        """Get entity types that can potentially relate to the given type."""
        compatible = set()
        
        for rel_name, rel_config in schema.relationship_types.items():
            if entity_type in rel_config.source_types:
                compatible.update(rel_config.target_types)
            if entity_type in rel_config.target_types:
                compatible.update(rel_config.source_types)
        
        if not compatible:
            compatible = set(schema.entity_types.keys())
        
        return compatible
    
    def _calculate_co_occurrence(self, entity_id_a: str, entity_id_b: str) -> float:
        """Calculate co-occurrence score between two entities."""
        docs_a = self.session.query(Entity.source_document_id).filter(
            Entity.id == entity_id_a
        ).all()
        docs_b = self.session.query(Entity.source_document_id).filter(
            Entity.id == entity_id_b
        ).all()
        
        set_a = {d[0] for d in docs_a if d[0]}
        set_b = {d[0] for d in docs_b if d[0]}
        
        if not set_a or not set_b:
            return 0.0
        
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def get_speculative_results(
        self,
        frontier_nodes: List[FrontierNode],
        visited_entities: Optional[Set[str]] = None,
        include_similar: bool = True
    ) -> SpeculativeResult:
        """
        Get complete speculative results for frontier nodes.
        
        Combines rule-based inference (Tier 2) and vector similarity (Tier 3).
        
        Args:
            frontier_nodes: List of frontier nodes to analyze
            visited_entities: Set of entity IDs already in confirmed results
            include_similar: Whether to include vector similarity results
            
        Returns:
            SpeculativeResult with inferred and similar entities
        """
        result = self.infer_from_frontiers(frontier_nodes, visited_entities)
        
        if include_similar:
            visited_plus_inferred = visited_entities.copy() if visited_entities else set()
            for inf in result.inferred:
                visited_plus_inferred.add(inf.target_entity_id)
            
            result.similar = self.find_similar_entities(
                frontier_nodes, 
                visited_plus_inferred
            )
        
        return result
