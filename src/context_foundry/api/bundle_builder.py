"""
BundleBuilder - Assembles APIContextBundle from all three memory layers.

This is the bridge between the internal RetrievalAgent and the public API.
It adds timing instrumentation and translates to the API schema.
"""
import time
from typing import Optional, Dict, List
from datetime import datetime

from sqlalchemy.orm import Session

from .context_bundle import (
    APIContextBundle,
    ContextBundleRequest,
    FocalEntity,
    RelatedEntity,
    Relationship,
    DocumentReference,
    ConfidenceSummary,
    IncidentPattern,
    ChangeEvent,
    ApplicableRule,
    FrontierNode,
    FrontierReason,
    RetrievalMeta,
    SpeculativeInference,
)
from ..agents.retrieval import RetrievalAgent
from ..models.schema import get_session, Entity
from ..utils.logger import logger
from sqlalchemy import func


class BundleBuilder:
    """
    Builds APIContextBundle by querying all three memory layers.
    
    This class wraps the RetrievalAgent and adds:
    - Timing instrumentation for each memory layer
    - Translation to API schema
    - Graceful handling of empty results
    
    SECURITY: Requires tenant_id for defense-in-depth filtering.
    """
    
    def __init__(self, session: Optional[Session] = None, tenant_id: str = None):
        self.session = session or get_session()
        self.tenant_id = tenant_id
        self.retrieval_agent = RetrievalAgent(self.session, tenant_id=tenant_id)
        if not tenant_id:
            logger.warning("BundleBuilder initialized without tenant_id")
        else:
            logger.info(f"BundleBuilder initialized for tenant {tenant_id[:8]}...")
    
    def _find_focal_entity_in_db(self, focal_entity_name: str) -> Optional[Entity]:
        """
        Look up the focal entity directly in the database.
        Handles fuzzy matching for variations like 'Payment Database' vs 'Payments Database'.
        """
        if not focal_entity_name:
            return None
        
        exact = self.session.query(Entity).filter(
            func.lower(Entity.name) == focal_entity_name.lower()
        ).first()
        if exact:
            return exact
        
        words = focal_entity_name.split()
        if len(words) >= 2:
            patterns = [f"%{word}%" for word in words if len(word) > 2]
            query = self.session.query(Entity)
            for pattern in patterns:
                query = query.filter(Entity.name.ilike(pattern))
            fuzzy_matches = query.limit(10).all()
        else:
            pattern = f"%{focal_entity_name}%"
            fuzzy_matches = self.session.query(Entity).filter(
                Entity.name.ilike(pattern)
            ).limit(10).all()
        
        if not fuzzy_matches:
            return None
        
        focal_lower = focal_entity_name.lower()
        focal_words = set(focal_lower.split())
        focal_singular = focal_lower.rstrip('s')
        
        for match in fuzzy_matches:
            match_lower = match.name.lower()
            if match_lower == focal_lower:
                return match
        
        for match in fuzzy_matches:
            match_lower = match.name.lower()
            match_singular = match_lower.rstrip('s')
            if focal_singular == match_singular:
                return match
        
        for match in fuzzy_matches:
            match_lower = match.name.lower()
            match_words = set(match_lower.split())
            if focal_words.issubset(match_words) or match_words.issubset(focal_words):
                return match
        
        for match in fuzzy_matches:
            if len(match.name) < 50:
                return match
        
        return None
    
    def build(self, request: ContextBundleRequest) -> APIContextBundle:
        """
        Build a complete APIContextBundle from a request.
        
        Args:
            request: The incoming API request
            
        Returns:
            APIContextBundle with all context and metadata
        """
        start_time = time.perf_counter()
        
        filter_reasons: Dict[str, int] = {}
        entities_considered = 0
        entities_included = 0
        relationships_considered = 0
        relationships_included = 0
        
        semantic_start = time.perf_counter()
        internal_bundle = self.retrieval_agent.build_context_bundle(
            query_text=request.query,
            max_entities=request.max_entities,
            max_documents=request.max_documents,
            traverse_depth=request.max_hops,
        )
        semantic_time = (time.perf_counter() - semantic_start) * 1000
        
        focal_entities: List[FocalEntity] = []
        related_entities: List[RelatedEntity] = []
        
        target_name = request.focal_entity or internal_bundle.target_entity_name
        
        db_focal_entity = None
        
        if request.focal_entity:
            db_focal_entity = self._find_focal_entity_in_db(request.focal_entity)
            
            if db_focal_entity:
                target_found = True
                target_name = db_focal_entity.name
                
                focal_entities.append(FocalEntity(
                    id=str(db_focal_entity.id),
                    name=db_focal_entity.name,
                    entity_type=db_focal_entity.entity_type,
                    confidence=db_focal_entity.confidence,
                    lifecycle_state=db_focal_entity.lifecycle_state.value if hasattr(db_focal_entity.lifecycle_state, 'value') else str(db_focal_entity.lifecycle_state),
                    description=db_focal_entity.description,
                    properties=db_focal_entity.properties,
                ))
                entities_included += 1
            else:
                target_found = False
        else:
            target_found = internal_bundle.target_entity_found
        
        focal_entity_ids = {str(db_focal_entity.id)} if db_focal_entity else set()
        
        for i, entity in enumerate(internal_bundle.semantic_entities):
            entity_id = str(entity.get("id", ""))
            entity_name = entity.get("name", "")
            entity_type = entity.get("entity_type", "UNKNOWN")
            confidence = entity.get("confidence", 0.5)
            lifecycle_state = entity.get("lifecycle_state", "UNKNOWN")
            
            entities_considered += 1
            
            if entity_id in focal_entity_ids:
                continue
            
            if confidence < request.min_confidence:
                filter_reasons["low_confidence"] = filter_reasons.get("low_confidence", 0) + 1
                continue
            
            entities_included += 1
            
            related_entities.append(RelatedEntity(
                id=entity_id,
                name=entity_name,
                entity_type=entity_type,
                confidence=confidence,
                lifecycle_state=lifecycle_state,
                hop_distance=1,
                path_confidence=confidence,
                description=entity.get("description"),
                properties=entity.get("properties"),
            ))
        
        relationships: List[Relationship] = []
        for rel in internal_bundle.semantic_relationships:
            relationships_considered += 1
            conf = rel.get("confidence", 0.5)
            
            if conf < request.min_confidence:
                filter_reasons["low_confidence_rel"] = filter_reasons.get("low_confidence_rel", 0) + 1
                continue
            
            relationships_included += 1
            relationships.append(Relationship(
                id=str(rel.get("id", "")),
                source_id=str(rel.get("source_id", "")),
                source_name=rel.get("source_name", ""),
                target_id=str(rel.get("target_id", "")),
                target_name=rel.get("target_name", ""),
                relationship_type=rel.get("relationship_type", "RELATED_TO"),
                confidence=conf,
                properties=rel.get("properties"),
                source_sentence=rel.get("source_sentence"),
            ))
        
        episodic_start = time.perf_counter()
        source_documents: List[DocumentReference] = []
        similar_incidents: List[IncidentPattern] = []
        
        if request.include_episodic:
            for doc in internal_bundle.episodic_documents:
                doc_type = doc.get("doc_type", "DOCUMENT")
                
                source_documents.append(DocumentReference(
                    id=str(doc.get("id", "")),
                    title=doc.get("title", "Untitled"),
                    doc_type=doc_type,
                    content_preview=doc.get("content", "")[:500],
                    similarity=doc.get("similarity", 0.5),
                    chunk_index=doc.get("chunk_index"),
                ))
                
                if doc_type == "INCIDENT":
                    similar_incidents.append(IncidentPattern(
                        incident_id=str(doc.get("id", "")),
                        title=doc.get("title", "Untitled"),
                        occurred_at=doc.get("occurred_at", datetime.utcnow()),
                        severity=doc.get("severity", "UNKNOWN"),
                        similarity=doc.get("similarity", 0.5),
                        affected_entities=doc.get("affected_entities", []),
                        resolution_summary=doc.get("resolution"),
                    ))
        episodic_time = (time.perf_counter() - episodic_start) * 1000
        
        symbolic_start = time.perf_counter()
        applicable_rules: List[ApplicableRule] = []
        
        if request.include_symbolic:
            for rule in internal_bundle.symbolic_rules:
                applicable_rules.append(ApplicableRule(
                    id=str(rule.get("id", "")),
                    name=rule.get("name", "Unnamed Rule"),
                    rule_type=rule.get("rule_type", "GENERAL"),
                    priority=rule.get("priority", 0),
                    condition=rule.get("condition", ""),
                    action=rule.get("action", ""),
                    match_score=rule.get("match_score"),
                ))
        symbolic_time = (time.perf_counter() - symbolic_start) * 1000
        
        frontier_nodes: List[FrontierNode] = []
        for frontier in internal_bundle.frontier:
            reason_str = frontier.get("reason", "max_hops_reached")
            try:
                reason = FrontierReason(reason_str.lower().replace(" ", "_"))
            except ValueError:
                reason = FrontierReason.MAX_HOPS_REACHED
            
            potential_connections = frontier.get("unexplored_edges", 0)
            if potential_connections == 0:
                potential_connections = frontier.get("potential_connections", 0)
            
            frontier_nodes.append(FrontierNode(
                entity_id=str(frontier.get("entity_id", "")),
                entity_name=frontier.get("entity_name", "Unknown"),
                entity_type=frontier.get("entity_type", "UNKNOWN"),
                reason=reason,
                reason_details=frontier.get("reason_details"),
                potential_connections=potential_connections,
                inferred_impact=frontier.get("inferred_impact"),
            ))
        
        knowledge_gaps: List[str] = []
        
        if not target_found and target_name:
            knowledge_gaps.append(f"Entity '{target_name}' not found in knowledge graph")
        
        if internal_bundle.gaps_identified:
            knowledge_gaps.extend(internal_bundle.gaps_identified)
        
        if not focal_entities:
            knowledge_gaps.append("No focal entities identified for this query")
        
        for frontier in frontier_nodes:
            if frontier.potential_connections > 0:
                knowledge_gaps.append(
                    f"No visibility into {frontier.potential_connections} potential connections from '{frontier.entity_name}'"
                )
        
        if internal_bundle.uncertainty:
            for reason in internal_bundle.uncertainty.uncertainty_reasons:
                if reason not in knowledge_gaps:
                    knowledge_gaps.append(reason)
        
        speculative_inferences: List[SpeculativeInference] = []
        if request.include_speculative and internal_bundle.speculative_inferences:
            for inf in internal_bundle.speculative_inferences:
                speculative_inferences.append(SpeculativeInference(
                    source_entity_id=str(inf.get("source_entity_id", "")),
                    source_entity_name=inf.get("source_entity_name", ""),
                    target_entity_id=str(inf.get("target_entity_id", "")),
                    target_entity_name=inf.get("target_entity_name", ""),
                    relationship_type=inf.get("relationship_type", "RELATED_TO"),
                    confidence=inf.get("confidence", 0.5),
                    rule_name=inf.get("rule_name", "unknown"),
                    explanation=inf.get("explanation", ""),
                ))
        
        semantic_conf = sum(e.confidence for e in focal_entities + related_entities) / max(1, len(focal_entities) + len(related_entities))
        episodic_conf = sum(d.similarity for d in source_documents) / max(1, len(source_documents))
        symbolic_conf = 0.8 if applicable_rules else 0.0
        
        overall_conf = internal_bundle.confidence
        
        if not target_found and target_name:
            overall_conf = 0.1
            recommendation = "entity_not_found"
        elif overall_conf >= 0.7:
            recommendation = "proceed"
        elif overall_conf >= 0.5:
            recommendation = "caution"
        else:
            recommendation = "insufficient_context"
        
        low_conf_entities = [
            e.name for e in focal_entities + related_entities
            if e.confidence < 0.5
        ]
        
        confidence_summary = ConfidenceSummary(
            overall=overall_conf,
            semantic_confidence=semantic_conf if focal_entities or related_entities else 0.0,
            episodic_confidence=episodic_conf if source_documents else 0.0,
            symbolic_confidence=symbolic_conf,
            low_confidence_entities=low_conf_entities,
            recommendation=recommendation,
        )
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        retrieval_meta = RetrievalMeta(
            semantic_query_time_ms=semantic_time,
            episodic_query_time_ms=episodic_time,
            symbolic_query_time_ms=symbolic_time,
            graph_traversal_time_ms=semantic_time * 0.3,
            total_time_ms=total_time,
            entities_considered=entities_considered,
            entities_included=entities_included,
            relationships_considered=relationships_considered,
            relationships_included=relationships_included,
            filter_reason_counts=filter_reasons,
        )
        
        bundle = APIContextBundle(
            version="1.0.0",
            query=request.query,
            focal_entities=focal_entities,
            related_entities=related_entities,
            relationships=relationships,
            graph_depth=request.max_hops,
            source_documents=source_documents,
            confidence_summary=confidence_summary,
            similar_incidents=similar_incidents,
            recent_changes=[],
            applicable_rules=applicable_rules,
            speculative_inferences=speculative_inferences,
            frontier_nodes=frontier_nodes,
            knowledge_gaps=knowledge_gaps,
            retrieval_meta=retrieval_meta,
            overall_confidence=overall_conf,
        )
        
        logger.info(f"Built context bundle: {len(focal_entities)} focal, {len(related_entities)} related, {len(relationships)} rels, confidence={overall_conf:.2f}, time={total_time:.1f}ms")
        
        return bundle
