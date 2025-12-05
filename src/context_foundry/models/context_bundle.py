"""
ContextBundle: The core data structure that aggregates information from all three memory layers.
Every response is built from a ContextBundle, ensuring full provenance tracking.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid


@dataclass
class SourceRef:
    """Reference to the original source of a fact."""
    source_id: str
    document_id: str
    document_title: str
    section: Optional[str] = None
    sentence_index: Optional[int] = None
    sentence_text: Optional[str] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    extracted_at: Optional[str] = None
    extraction_method: str = "direct_ingest"
    extraction_confidence: float = 1.0
    
    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "section": self.section,
            "sentence_text": self.sentence_text,
            "extraction_confidence": self.extraction_confidence
        }


@dataclass
class EvidenceItem:
    """Single piece of evidence supporting a response."""
    type: str
    description: str
    source: Optional[SourceRef] = None
    confidence: float = 0.5
    memory_layer: str = "unknown"
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "description": self.description,
            "source": self.source.to_dict() if self.source else None,
            "confidence": self.confidence,
            "memory_layer": self.memory_layer
        }


@dataclass
class UncertaintyReport:
    """Report on uncertainty in the context bundle."""
    overall_confidence: float
    recommendation: str
    high_confidence_facts: int = 0
    medium_confidence_facts: int = 0
    low_confidence_facts: int = 0
    low_confidence_items: List[Dict] = field(default_factory=list)
    unresolved_entities: List[str] = field(default_factory=list)
    missing_relationships: List[str] = field(default_factory=list)
    stale_facts: List[str] = field(default_factory=list)
    uncertainty_reasons: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "overall_confidence": self.overall_confidence,
            "recommendation": self.recommendation,
            "high_confidence_facts": self.high_confidence_facts,
            "medium_confidence_facts": self.medium_confidence_facts,
            "low_confidence_facts": self.low_confidence_facts,
            "low_confidence_items": self.low_confidence_items,
            "unresolved_entities": self.unresolved_entities,
            "missing_relationships": self.missing_relationships,
            "uncertainty_reasons": self.uncertainty_reasons
        }


@dataclass
class ContextBundle:
    """
    Aggregated context from all three memory layers for a query.
    This is the primary input to the Reasoning Agent.
    """
    query_id: str
    query_text: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    semantic_entities: List[Dict] = field(default_factory=list)
    semantic_relationships: List[Dict] = field(default_factory=list)
    
    episodic_documents: List[Dict] = field(default_factory=list)
    
    symbolic_rules: List[Dict] = field(default_factory=list)
    
    uncertainty: Optional[UncertaintyReport] = None
    
    retrieval_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Target entity tracking - CRITICAL for preventing hallucinations
    target_entity_name: Optional[str] = None  # The specific entity the query is asking about
    target_entity_found: bool = False  # Was the target entity actually found in the graph?
    target_entity_match: Optional[Dict] = None  # The matched entity if found
    
    # Query type classification
    query_type: str = "entity"  # 'entity', 'rule', 'impact', 'general'
    
    # Sequence intent detection - does query ask for ordered steps/path/chain?
    sequence_intent: bool = False
    sequence_intent_reason: Optional[str] = None
    has_multi_step_evidence: bool = False
    
    # Analysis query detection - requires aggregation beyond retrieval
    is_analysis_query: bool = False
    
    # Property-based query detection - queries about entity attributes (expertise, role, level, department)
    is_property_query: bool = False
    property_filters: List[Dict] = field(default_factory=list)
    
    # Temporal query support - "as of when?" queries
    as_of_date: Optional[str] = None  # ISO format date string for time-travel queries
    
    @property
    def confidence(self) -> float:
        """Calculate overall confidence from all memory layers."""
        if self.uncertainty:
            return self.uncertainty.overall_confidence
        
        # CRITICAL: If we're looking for a specific entity and didn't find it,
        # confidence should be very low regardless of other entities found
        if self.target_entity_name and not self.target_entity_found:
            return 0.1  # Very low confidence - target entity not in graph
        
        confidences = []
        
        for entity in self.semantic_entities:
            confidences.append(entity.get("confidence", 0.5))
        for rel in self.semantic_relationships:
            confidences.append(rel.get("confidence", 0.5))
        for doc in self.episodic_documents:
            confidences.append(doc.get("similarity", 0.5))
        
        if not confidences:
            return 0.0
        
        return sum(confidences) / len(confidences)
    
    def calculate_uncertainty(self) -> UncertaintyReport:
        """Calculate uncertainty report from bundle contents."""
        uncertainty_reasons = []
        
        # CRITICAL: Check if target entity was found first
        if self.target_entity_name and not self.target_entity_found:
            # Target entity not found - this is a critical uncertainty
            uncertainty_reasons.append(f"TARGET ENTITY NOT FOUND: '{self.target_entity_name}' does not exist in the knowledge graph")
            self.uncertainty = UncertaintyReport(
                overall_confidence=0.1,  # Very low confidence
                recommendation="entity_not_found",
                high_confidence_facts=0,
                medium_confidence_facts=0,
                low_confidence_facts=0,
                low_confidence_items=[],
                unresolved_entities=[self.target_entity_name],
                uncertainty_reasons=uncertainty_reasons
            )
            return self.uncertainty
        
        # Analysis queries require aggregation capabilities beyond retrieval
        if self.is_analysis_query:
            uncertainty_reasons.append(
                "ANALYSIS QUERY: Pattern/trend analysis requires aggregation capabilities "
                "beyond my current scope. I can answer questions about specific incidents, "
                "services, or escalation paths."
            )
            self.uncertainty = UncertaintyReport(
                overall_confidence=0.0,
                recommendation="analysis_not_supported",
                high_confidence_facts=0,
                medium_confidence_facts=0,
                low_confidence_facts=0,
                low_confidence_items=[],
                uncertainty_reasons=uncertainty_reasons
            )
            return self.uncertainty
        
        all_confidences = []
        
        for entity in self.semantic_entities:
            all_confidences.append(("entity", entity.get("name"), entity.get("confidence", 0.5)))
        for rel in self.semantic_relationships:
            all_confidences.append(("relationship", f"{rel.get('source_name')}->{rel.get('target_name')}", rel.get("confidence", 0.5)))
        
        if self.query_type == 'rule' and self.symbolic_rules:
            for rule in self.symbolic_rules:
                match_score = rule.get("match_score", 5) / 10
                rule_confidence = min(0.9, 0.6 + match_score * 0.3)
                all_confidences.append(("rule", rule.get("name"), rule_confidence))
            
            for doc in self.episodic_documents:
                doc_match_score = doc.get("match_score", 0)
                if doc_match_score > 10:
                    doc_confidence = min(0.85, 0.5 + doc_match_score / 30)
                    all_confidences.append(("document", doc.get("title"), doc_confidence))
        
        high_conf = sum(1 for _, _, c in all_confidences if c >= 0.8)
        medium_conf = sum(1 for _, _, c in all_confidences if 0.5 <= c < 0.8)
        low_conf = sum(1 for _, _, c in all_confidences if c < 0.5)
        
        low_conf_items = [
            {"fact": name, "confidence": conf, "type": t}
            for t, name, conf in all_confidences if conf < 0.5
        ]
        
        overall = sum(c for _, _, c in all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        if self.query_type == 'rule' and len(self.symbolic_rules) > 0:
            base_boost = 0.15 * min(len(self.symbolic_rules), 3)
            
            has_title_match = any(d.get("match_score", 0) > 10 for d in self.episodic_documents)
            if has_title_match:
                base_boost += 0.1
            
            has_resolved_person = any(e.get("resolved_from_rule") for e in self.semantic_entities)
            if has_resolved_person:
                base_boost += 0.1
            
            overall = min(0.95, overall + base_boost)
        
        if self.sequence_intent and not self.has_multi_step_evidence:
            overall = min(overall, 0.45)
            uncertainty_reasons.append(
                f"SEQUENCE REQUESTED but only single-step evidence found "
                f"(reason: {self.sequence_intent_reason})"
            )
        
        if overall >= 0.7:
            recommendation = "proceed"
        elif overall >= 0.5:
            recommendation = "caution"
        else:
            recommendation = "insufficient_context"
        
        if low_conf > 0:
            uncertainty_reasons.append(f"{low_conf} facts have low confidence (<0.5)")
        if len(self.semantic_entities) == 0 and self.query_type != 'rule':
            uncertainty_reasons.append("No entities found in knowledge graph")
        if len(self.semantic_relationships) == 0 and self.query_type != 'rule':
            uncertainty_reasons.append("No relationships found in knowledge graph")
        if len(self.episodic_documents) == 0:
            uncertainty_reasons.append("No similar documents found in episodic memory")
        
        self.uncertainty = UncertaintyReport(
            overall_confidence=overall,
            recommendation=recommendation,
            high_confidence_facts=high_conf,
            medium_confidence_facts=medium_conf,
            low_confidence_facts=low_conf,
            low_confidence_items=low_conf_items,
            uncertainty_reasons=uncertainty_reasons
        )
        
        return self.uncertainty
    
    def to_dict(self) -> dict:
        """Convert bundle to dictionary for serialization."""
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "created_at": self.created_at.isoformat(),
            "query_type": self.query_type,
            "is_analysis_query": self.is_analysis_query,
            "is_property_query": self.is_property_query,
            "property_filters": self.property_filters,
            "sequence_intent": self.sequence_intent,
            "as_of_date": self.as_of_date,
            "semantic_memory": self.semantic_entities + self.semantic_relationships,
            "semantic_count": len(self.semantic_entities) + len(self.semantic_relationships),
            "episodic_memory": self.episodic_documents,
            "episodic_count": len(self.episodic_documents),
            "symbolic_memory": self.symbolic_rules,
            "rules_count": len(self.symbolic_rules),
            "confidence": self.confidence,
            "uncertainty": self.uncertainty.to_dict() if self.uncertainty else None,
            "retrieval_metadata": self.retrieval_metadata
        }
    
    def to_llm_context(self) -> str:
        """Format bundle as context string for LLM reasoning."""
        lines = []
        
        # CRITICAL: If target entity not found, lead with that information
        if self.target_entity_name and not self.target_entity_found:
            lines.append("=== CRITICAL: TARGET ENTITY NOT FOUND ===")
            lines.append(f"The query asks about '{self.target_entity_name}' but this entity DOES NOT EXIST in the knowledge graph.")
            lines.append("You MUST acknowledge this in your response with LOW CONFIDENCE.")
            lines.append("DO NOT fabricate relationships or information about non-existent entities.")
            lines.append("The entities shown below are NOT related to the query target.\n")
        
        # ANALYSIS QUERY: Honest limitation - requires aggregation
        if self.is_analysis_query:
            lines.append("=== ANALYSIS QUERY DETECTED ===")
            lines.append("The user is asking for pattern analysis, trends, or aggregated statistics.")
            lines.append("This type of query requires aggregation capabilities beyond simple retrieval.")
            lines.append("You MUST respond with LOW CONFIDENCE and explain the limitation:")
            lines.append("- Pattern/trend analysis requires statistical aggregation across all data")
            lines.append("- I can answer questions about specific incidents, services, or escalation paths")
            lines.append("- For aggregate analysis, the user should query their incident database directly")
            lines.append("DO NOT attempt to synthesize patterns from partial data - this risks hallucination.\n")
        
        # IMPACT QUERY: Guide LLM to include ALL cascade services
        if self.query_type == 'impact':
            lines.append("=== IMPACT/CASCADE QUERY DETECTED ===")
            lines.append("The user is asking about blast radius, impact, or who needs to be notified if something fails.")
            lines.append("CRITICAL INSTRUCTIONS:")
            lines.append("1. Include ALL services in the cascade - both DIRECT dependencies AND DOWNSTREAM dependants")
            lines.append("2. The relationships below show the full dependency chain - follow ALL edges")
            lines.append("3. If A depends on B, and B depends on C (the failing entity), then BOTH A and B are affected")
            lines.append("4. Present a COMPLETE list of affected services, grouped by direct vs cascade if helpful")
            lines.append("5. Do NOT stop at just direct dependencies - the full blast radius includes transitive dependants")
            lines.append("Example: If User Database fails, and Auth Service depends on User Database, and API Gateway depends on Auth Service,")
            lines.append("         then BOTH Auth Service (direct) AND API Gateway (cascade) must be listed.\n")
        
        # SEQUENCE INTENT: Guide LLM to provide ordered steps from runbooks
        if self.sequence_intent:
            lines.append("=== SEQUENCE QUERY DETECTED ===")
            lines.append(f"The user is asking for an ordered sequence/path/chain ({self.sequence_intent_reason}).")
            if self.has_multi_step_evidence:
                lines.append("INSTRUCTIONS: Look for numbered steps, bullet lists, or ordered procedures in the documents below.")
                lines.append("Return the FULL ordered sequence from the runbook/procedure, then add any specific rules that apply.\n")
            else:
                lines.append("WARNING: No multi-step sequence found in retrieved documents.")
                lines.append("If you cannot find a complete ordered sequence, acknowledge this limitation.")
                lines.append("Do NOT present a single rule as if it were the complete path/chain.\n")
        
        # PROPERTY QUERY: Guide LLM to focus on matching entities
        if self.is_property_query:
            lines.append("=== PROPERTY-BASED QUERY DETECTED ===")
            lines.append(f"Filters applied: {self.property_filters}")
            lines.append("The entities below were retrieved by searching their properties (expertise, role, level, department, etc.).")
            lines.append("INSTRUCTIONS:")
            lines.append("1. Focus on the entities marked with 'matched_via_property_search: True'")
            lines.append("2. List ALL matching entities with their relevant properties")
            lines.append("3. If the query asked for multiple criteria (e.g., 'frontend AND backend expertise'),")
            lines.append("   only list entities that match ALL criteria")
            lines.append("4. If no entities match the criteria, state this clearly\n")
        
        lines.append("=== SIMILAR DOCUMENTS (EPISODIC MEMORY) ===\n")
        if self.episodic_documents:
            for doc in self.episodic_documents:
                lines.append(f"  [{doc.get('doc_type')}] {doc.get('title')} "
                           f"(similarity: {doc.get('similarity', 0):.2f})")
                lines.append(f"    Content: {doc.get('content', '')[:800]}...")
        else:
            lines.append("  No similar documents found.")
        
        lines.append("\n=== CONTEXT FROM KNOWLEDGE GRAPH (SEMANTIC MEMORY) ===\n")
        
        if self.semantic_entities:
            lines.append("ENTITIES:")
            for entity in self.semantic_entities:
                lifecycle = entity.get("lifecycle_state", "UNKNOWN")
                conf = entity.get("confidence", 0)
                lines.append(f"  - {entity.get('name')} [{entity.get('entity_type')}] "
                           f"(lifecycle: {lifecycle}, confidence: {conf:.2f})")
                if entity.get("description"):
                    lines.append(f"    Description: {entity.get('description')}")
                if entity.get("properties"):
                    lines.append(f"    Properties: {entity.get('properties')}")
        
        if self.semantic_relationships:
            lines.append("\nRELATIONSHIPS:")
            for rel in self.semantic_relationships:
                conf = rel.get("confidence", 0)
                lines.append(f"  - {rel.get('source_name')} --[{rel.get('relationship_type')}]--> "
                           f"{rel.get('target_name')} (confidence: {conf:.2f})")
                if rel.get("source_sentence"):
                    lines.append(f"    Source: \"{rel.get('source_sentence')}\"")
        
        lines.append("\n=== APPLICABLE RULES (SYMBOLIC MEMORY) ===\n")
        if self.symbolic_rules:
            for rule in self.symbolic_rules:
                lines.append(f"  [{rule.get('rule_type')}] {rule.get('name')} (priority: {rule.get('priority')})")
                lines.append(f"    Condition: {rule.get('condition')}")
                lines.append(f"    Action: {rule.get('action')}")
        else:
            lines.append("  No specific rules apply.")
        
        if self.uncertainty:
            lines.append(f"\n=== UNCERTAINTY REPORT ===")
            lines.append(f"  Overall Confidence: {self.uncertainty.overall_confidence:.2%}")
            lines.append(f"  Recommendation: {self.uncertainty.recommendation}")
            if self.uncertainty.uncertainty_reasons:
                lines.append("  Reasons for uncertainty:")
                for reason in self.uncertainty.uncertainty_reasons:
                    lines.append(f"    - {reason}")
        
        return "\n".join(lines)


def create_bundle(query_text: str) -> ContextBundle:
    """Factory function to create a new ContextBundle."""
    return ContextBundle(
        query_id=str(uuid.uuid4()),
        query_text=query_text
    )
