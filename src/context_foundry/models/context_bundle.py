"""
ContextBundle: The core data structure that aggregates information from all three memory layers.
Every response is built from a ContextBundle, ensuring full provenance tracking.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
import uuid

if TYPE_CHECKING:
    from ..aggregation.models import CAT, EvidenceEnvelope, AggregationResult


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
    
    # Entity listing/aggregation query fields
    is_aggregation_query: bool = False  # True if listing entities by type
    aggregation_type: Optional[str] = None  # The entity type being listed (e.g., "PROCESS")
    aggregation_count: int = 0  # Number of entities found
    
    # Property-based query detection - queries about entity attributes (expertise, role, level, department)
    is_property_query: bool = False
    property_filters: List[Dict] = field(default_factory=list)
    
    # Temporal query support - "as of when?" queries
    as_of_date: Optional[str] = None  # ISO format date string for time-travel queries
    
    # Blast radius / impact query - structured list of affected entities from graph traversal
    # This is DETERMINISTIC - populated directly from exhaustive graph traversal, not LLM
    blast_radius_entities: List[str] = field(default_factory=list)  # Sorted list of affected entity names
    blast_radius_complete: bool = True  # Whether traversal reached max_depth limit
    
    # Frontier detection - where knowledge ends in the graph
    # Frontier nodes are entities where traversal stopped (no more edges for the mode)
    frontier: List[Dict] = field(default_factory=list)  # List of frontier node dicts
    gaps_identified: List[str] = field(default_factory=list)  # Documentation gaps found
    traversal_result: Optional[Dict] = None  # Full structured traversal result
    
    # Speculative inference - AI-inferred relationships beyond confirmed knowledge
    # Populated by InferenceEngine using transitive dependency, co-occurrence, and shared dependency rules
    speculative_inferences: List[Dict] = field(default_factory=list)  # List of inferred relationships with confidence
    
    # Aggregation Framework fields (v1.3) - for quantitative queries
    # CAT (Canonical Aggregation Target) defines "what exactly are we counting?"
    aggregation_target: Optional[Any] = None  # CAT object - semantic contract for aggregation
    aggregation_plan: Optional[Dict] = None  # Execution plan from planner
    evidence_envelope: Optional[Any] = None  # EvidenceEnvelope - audit trail for reproducibility
    aggregation_result: Optional[Any] = None  # AggregationResult from service
    
    # Counted entities from aggregation - for rich responses and follow-up questions
    counted_entities: List[Dict] = field(default_factory=list)
    
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
        result = {
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
        
        # Add blast radius entities if this is an impact query
        if self.blast_radius_entities:
            result["blast_radius_entities"] = self.blast_radius_entities
            result["blast_radius_complete"] = self.blast_radius_complete
        
        # Add frontier detection results
        if self.frontier:
            result["frontier"] = self.frontier
        if self.gaps_identified:
            result["gaps_identified"] = self.gaps_identified
        if self.traversal_result:
            result["traversal_result"] = self.traversal_result
        
        # Add aggregation framework fields
        if self.aggregation_target:
            result["aggregation_target"] = {
                "anchor": str(self.aggregation_target.anchor.entity_id) if self.aggregation_target.anchor else None,
                "target_source": self.aggregation_target.target.source.value if self.aggregation_target.target else None,
                "semantic_confidence": self.aggregation_target.semantic_confidence,
            }
        if self.aggregation_plan:
            result["aggregation_plan"] = self.aggregation_plan
        if self.aggregation_result:
            result["aggregation_result"] = {
                "result_kind": self.aggregation_result.result_kind.value,
                "value": self.aggregation_result.value,
                "display_text": self.aggregation_result.display_text,
                "confidence": self.aggregation_result.confidence,
            }
        
        return result
    
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
        
        # AGGREGATION QUERY: We have the entity list - present it confidently
        if self.is_aggregation_query and self.aggregation_type:
            lines.append(f"=== ENTITY LISTING QUERY: {self.aggregation_type} ===")
            lines.append(f"Found {self.aggregation_count} entities of type {self.aggregation_type}.")
            lines.append("INSTRUCTIONS:")
            lines.append("1. List ALL the entities shown below in your response")
            lines.append("2. Include each entity's name and description if available")
            lines.append("3. Organize the list in a clear, readable format")
            lines.append("4. This is a complete list of TRUSTED entities of this type\n")
        # ANALYSIS QUERY: Honest limitation - requires aggregation (only if NOT an aggregation query)
        elif self.is_analysis_query:
            lines.append("=== ANALYSIS QUERY DETECTED ===")
            lines.append("The user is asking for pattern analysis, trends, or aggregated statistics.")
            lines.append("This type of query requires aggregation capabilities beyond simple retrieval.")
            lines.append("You MUST respond with LOW CONFIDENCE and explain the limitation:")
            lines.append("- Pattern/trend analysis requires statistical aggregation across all data")
            lines.append("- I can answer questions about specific incidents, services, or escalation paths")
            lines.append("- For aggregate analysis, the user should query their incident database directly")
            lines.append("DO NOT attempt to synthesize patterns from partial data - this risks hallucination.\n")
        
        # IMPACT QUERY: Guide LLM to structure response with three tiers
        if self.query_type == 'impact':
            lines.append("=== IMPACT/CASCADE QUERY DETECTED ===")
            lines.append("The user is asking about blast radius, impact, or who needs to be notified if something fails.")
            lines.append("")
            
            # Include the actual traversal results - the structured data from graph traversal
            if self.blast_radius_entities:
                lines.append(f"=== GRAPH TRAVERSAL RESULT: {len(self.blast_radius_entities)} AFFECTED ENTITIES ===")
                lines.append(f"Traversal complete: {self.blast_radius_complete}")
                lines.append("")
                lines.append("CONFIRMED AFFECTED ENTITIES (from graph traversal):")
                for entity_name in self.blast_radius_entities:
                    lines.append(f"  - {entity_name}")
                lines.append("")
            
            # Include frontier nodes (where knowledge ends)
            if self.frontier:
                lines.append(f"=== KNOWLEDGE BOUNDARIES: {len(self.frontier)} FRONTIER NODES ===")
                lines.append("These entities mark where our knowledge ends:")
                for fn in self.frontier:
                    lines.append(f"  - {fn.get('entity_name', 'Unknown')} [{fn.get('entity_type', 'Unknown')}]")
                    lines.append(f"    Reason: {fn.get('reason', 'Unknown')}")
                    if fn.get('message'):
                        lines.append(f"    Details: {fn.get('message')}")
                lines.append("")
            
            # Include identified documentation gaps
            if self.gaps_identified:
                lines.append(f"=== DOCUMENTATION GAPS IDENTIFIED ===")
                for gap in self.gaps_identified:
                    lines.append(f"  - {gap}")
                lines.append("")
            
            lines.append("STRUCTURE YOUR RESPONSE IN THREE TIERS:")
            lines.append("")
            lines.append("**CONFIRMED IMPACT:** (High confidence)")
            lines.append("  - List the entities from GRAPH TRAVERSAL RESULT above")
            lines.append("  - These are KNOWN relationships we are certain about")
            lines.append("")
            lines.append("**INFERRED IMPACT:** (Lower confidence)")
            lines.append("  - Transitive/indirect dependencies inferred through chains")
            lines.append("  - Include the confidence percentage for each inferred item")
            lines.append("  - Example: 'User Database (inferred via Auth Gateway, 57% confidence)'")
            lines.append("")
            lines.append("**KNOWLEDGE BOUNDARY:** (Unknown)")
            lines.append("  - List the FRONTIER NODES above - where our knowledge ends")
            lines.append("  - Explicitly state what we DON'T know based on the gaps identified")
            lines.append("")
            lines.append("CRITICAL: Be explicit about uncertainty. Do NOT present inferred impacts as confirmed facts.\n")
        
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
                rel_id = rel.get("id", "unknown")[:8] if rel.get("id") else ""
                
                # Build temporal string (Stage 2: Context-Attached Knowledge)
                valid_from = rel.get("valid_from")
                valid_to = rel.get("valid_to")
                temporal_str = ""
                if valid_from or valid_to:
                    from_str = str(valid_from)[:10] if valid_from else "?"
                    to_str = str(valid_to)[:10] if valid_to else "ongoing"
                    temporal_str = f" [{from_str} → {to_str}]"
                
                lines.append(f"  - {rel.get('source_name')} --[{rel.get('relationship_type')}]--> "
                           f"{rel.get('target_name')}{temporal_str} (confidence: {conf:.2f}) [REL-{rel_id}]")
                
                # Event context (Stage 2)
                if rel.get("event_context"):
                    lines.append(f"    Context: {rel.get('event_context')}")
                
                # Provenance text (Stage 2)
                if rel.get("provenance_text"):
                    lines.append(f"    Source: \"{rel.get('provenance_text')}\"")
                elif rel.get("source_sentence"):
                    lines.append(f"    Source: \"{rel.get('source_sentence')}\"")
                
                # Qualifiers (Stage 2)
                if rel.get("qualifiers"):
                    qualifiers = rel.get("qualifiers")
                    if isinstance(qualifiers, list):
                        qual_strs = [f"{q.get('type', 'qual')}: {q.get('text', q.get('value', ''))}" 
                                    for q in qualifiers if isinstance(q, dict)]
                        if qual_strs:
                            lines.append(f"    Qualifiers: {', '.join(qual_strs)}")
        
        lines.append("\n=== APPLICABLE RULES (SYMBOLIC MEMORY) ===\n")
        if self.symbolic_rules:
            for rule in self.symbolic_rules:
                lines.append(f"  [{rule.get('rule_type')}] {rule.get('name')} (priority: {rule.get('priority')})")
                lines.append(f"    Condition: {rule.get('condition')}")
                lines.append(f"    Action: {rule.get('action')}")
        else:
            lines.append("  No specific rules apply.")
        
        # SPECULATIVE INFERENCES: AI-inferred relationships beyond confirmed facts
        if self.speculative_inferences:
            lines.append("\n=== SPECULATIVE INFERENCES (AI-INFERRED) ===")
            lines.append("These are relationships INFERRED by analysis rules, NOT confirmed in the knowledge graph.")
            lines.append("You MUST clearly label these as inferred with their confidence percentage.\n")
            for inf in self.speculative_inferences:
                rule_name = inf.get("rule_name", "unknown")
                source = inf.get("source_entity_name", "unknown")
                target = inf.get("target_entity_name", "unknown")
                rel_type = inf.get("relationship_type", "RELATED_TO")
                confidence = inf.get("confidence", 0)
                explanation = inf.get("explanation", "")
                lines.append(f"  - {source} --[{rel_type}]--> {target}")
                lines.append(f"    Inferred by: {rule_name} ({confidence:.0%} confidence)")
                if explanation:
                    lines.append(f"    Reason: {explanation}")
        
        # KNOWLEDGE BOUNDARIES: Where graph traversal stopped
        # Only show here for non-impact queries (impact queries show it earlier with context)
        if self.frontier and self.query_type != 'impact':
            lines.append("\n=== KNOWLEDGE BOUNDARIES (FRONTIER NODES) ===")
            lines.append("These mark where our knowledge ends. Traversal stopped at these points.\n")
            for frontier_node in self.frontier:
                entity_name = frontier_node.get("entity_name", "unknown")
                entity_type = frontier_node.get("entity_type", "unknown")
                reason = frontier_node.get("reason", "Unknown reason")
                reason_details = frontier_node.get("reason_details", "")
                lines.append(f"  - {entity_name} [{entity_type}]")
                lines.append(f"    Boundary reason: {reason}")
                if reason_details:
                    lines.append(f"    Details: {reason_details}")
        
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
