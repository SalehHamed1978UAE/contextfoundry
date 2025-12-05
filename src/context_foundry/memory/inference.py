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
    Transitive Dependency Rule: A→B and B→C implies A→C
    
    If we're at frontier node B, and we know:
    - A depends on B (A→B)
    - B depends on C (B→C)
    Then we infer: A likely depends on C (A→C)
    
    This works for any relationship type with similar semantics.
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
            incoming = session.query(Relationship).filter(
                Relationship.target_id == frontier_node.entity_id,
                Relationship.relationship_type == rel_type,
                Relationship.lifecycle_state == LifecycleState.TRUSTED
            ).all()
            
            outgoing = session.query(Relationship).filter(
                Relationship.source_id == frontier_node.entity_id,
                Relationship.relationship_type == rel_type,
                Relationship.lifecycle_state == LifecycleState.TRUSTED
            ).all()
            
            for inc in incoming:
                for out in outgoing:
                    source_entity = session.query(Entity).filter(
                        Entity.id == inc.source_id,
                        Entity.lifecycle_state == LifecycleState.TRUSTED
                    ).first()
                    target_entity = session.query(Entity).filter(
                        Entity.id == out.target_id,
                        Entity.lifecycle_state == LifecycleState.TRUSTED
                    ).first()
                    
                    if not source_entity or not target_entity:
                        continue
                    
                    if str(source_entity.id) == str(target_entity.id):
                        continue
                    
                    if str(target_entity.id) in visited_entities:
                        continue
                    
                    existing = session.query(Relationship).filter(
                        Relationship.source_id == source_entity.id,
                        Relationship.target_id == target_entity.id,
                        Relationship.relationship_type == rel_type,
                        Relationship.lifecycle_state == LifecycleState.TRUSTED
                    ).first()
                    
                    if existing:
                        continue
                    
                    inc_conf = float(inc.confidence) if inc.confidence else 0.0
                    out_conf = float(out.confidence) if out.confidence else 0.0
                    combined_confidence = min(inc_conf, out_conf) * self.confidence_modifier
                    
                    inferred.append(InferredRelationship(
                        source_entity_id=str(source_entity.id),
                        source_entity_name=str(source_entity.name),
                        source_entity_type=str(source_entity.entity_type),
                        target_entity_id=str(target_entity.id),
                        target_entity_name=str(target_entity.name),
                        target_entity_type=str(target_entity.entity_type),
                        inferred_relationship_type=f"LIKELY_{rel_type}",
                        confidence=combined_confidence,
                        rule_id=self.rule_id,
                        rule_name=self.name,
                        supporting_evidence=[
                            f"{source_entity.name} → {frontier_node.entity_name} ({rel_type})",
                            f"{frontier_node.entity_name} → {target_entity.name} ({rel_type})"
                        ]
                    ))
        
        return inferred
    
    def _get_transitive_relationship_types(self, schema: DomainSchema) -> List[str]:
        """Get relationship types that support transitive inference."""
        transitive_types = []
        for rel_name, rel_config in schema.relationship_types.items():
            if rel_name in ['DEPENDS_ON', 'REQUIRES', 'USES', 'CALLS', 'IMPORTS']:
                transitive_types.append(rel_name)
            elif rel_config.semantics and 'dependency' in rel_config.semantics.modes:
                transitive_types.append(rel_name)
        
        if not transitive_types:
            transitive_types = ['DEPENDS_ON']
        
        return transitive_types


class CoOccurrenceRule(InferenceRule):
    """
    Co-occurrence Rule: Entities mentioned together in 3+ documents may be related.
    
    If frontier node A and entity B are mentioned together in multiple documents,
    they likely have an undocumented relationship.
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
        
        frontier_docs = session.query(Entity.source_document_id).filter(
            Entity.id == frontier_node.entity_id
        ).all()
        frontier_doc_ids = {doc[0] for doc in frontier_docs if doc[0]}
        
        frontier_entity = session.query(Entity).filter(
            Entity.id == frontier_node.entity_id
        ).first()
        
        if not frontier_entity or not frontier_doc_ids:
            return inferred
        
        co_occurring = session.query(
            Entity,
            func.count(Entity.source_document_id).label('doc_count')
        ).filter(
            Entity.source_document_id.in_(frontier_doc_ids),
            Entity.id != frontier_node.entity_id,
            Entity.lifecycle_state == LifecycleState.TRUSTED
        ).group_by(Entity.id).having(
            func.count(Entity.source_document_id) >= 1
        ).all()
        
        for entity, doc_count in co_occurring:
            if str(entity.id) in visited_entities:
                continue
            
            entity_docs = session.query(Entity.source_document_id).filter(
                Entity.id == entity.id
            ).all()
            entity_doc_ids = {doc[0] for doc in entity_docs if doc[0]}
            
            shared_docs = frontier_doc_ids & entity_doc_ids
            
            if len(shared_docs) < self.MIN_CO_OCCURRENCE:
                continue
            
            existing = session.query(Relationship).filter(
                or_(
                    and_(
                        Relationship.source_id == frontier_node.entity_id,
                        Relationship.target_id == entity.id
                    ),
                    and_(
                        Relationship.source_id == entity.id,
                        Relationship.target_id == frontier_node.entity_id
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
                target_entity_id=str(entity.id),
                target_entity_name=str(entity.name),
                target_entity_type=str(entity.entity_type),
                inferred_relationship_type="POTENTIALLY_RELATES_TO",
                confidence=doc_confidence,
                rule_id=self.rule_id,
                rule_name=self.name,
                supporting_evidence=[f"Co-mentioned in {len(shared_docs)} documents"]
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
                if str(entity_a.id) in visited_entities or str(entity_b.id) in visited_entities:
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
    """
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()
        self.schema_loader = get_schema_loader()
        
        self.rules: List[InferenceRule] = [
            TransitiveDependencyRule(),
            CoOccurrenceRule(),
            SharedDependencyRule()
        ]
        
        logger.info(f"InferenceEngine initialized with {len(self.rules)} rules")
    
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
        episodic = EpisodicMemory(self.session)
        
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
        
        entity = self.session.query(Entity).filter(
            Entity.id == frontier.entity_id
        ).first()
        
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
            doc_entities = self.session.query(Entity).filter(
                Entity.source_document_id == doc.get('document_id'),
                Entity.lifecycle_state == LifecycleState.TRUSTED,
                Entity.id != frontier.entity_id
            ).all()
            
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
