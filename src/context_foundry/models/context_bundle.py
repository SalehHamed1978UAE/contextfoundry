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
        
        all_confidences = []
        
        for entity in self.semantic_entities:
            all_confidences.append(("entity", entity.get("name"), entity.get("confidence", 0.5)))
        for rel in self.semantic_relationships:
            all_confidences.append(("relationship", f"{rel.get('source_name')}->{rel.get('target_name')}", rel.get("confidence", 0.5)))
        
        high_conf = sum(1 for _, _, c in all_confidences if c >= 0.8)
        medium_conf = sum(1 for _, _, c in all_confidences if 0.5 <= c < 0.8)
        low_conf = sum(1 for _, _, c in all_confidences if c < 0.5)
        
        low_conf_items = [
            {"fact": name, "confidence": conf, "type": t}
            for t, name, conf in all_confidences if conf < 0.5
        ]
        
        overall = sum(c for _, _, c in all_confidences) / len(all_confidences) if all_confidences else 0.0
        
        if overall >= 0.7:
            recommendation = "proceed"
        elif overall >= 0.5:
            recommendation = "caution"
        else:
            recommendation = "insufficient_context"
        
        if low_conf > 0:
            uncertainty_reasons.append(f"{low_conf} facts have low confidence (<0.5)")
        if len(self.semantic_entities) == 0:
            uncertainty_reasons.append("No entities found in knowledge graph")
        if len(self.semantic_relationships) == 0:
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
        
        lines.append("=== CONTEXT FROM KNOWLEDGE GRAPH (SEMANTIC MEMORY) ===\n")
        
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
        
        lines.append("\n=== SIMILAR DOCUMENTS (EPISODIC MEMORY) ===\n")
        if self.episodic_documents:
            for doc in self.episodic_documents:
                lines.append(f"  [{doc.get('doc_type')}] {doc.get('title')} "
                           f"(similarity: {doc.get('similarity', 0):.2f})")
                lines.append(f"    Content: {doc.get('content', '')[:300]}...")
        else:
            lines.append("  No similar documents found.")
        
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
