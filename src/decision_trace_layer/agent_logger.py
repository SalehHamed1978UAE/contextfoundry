"""
Agent Decision Logger

Provides easy-to-use functions for CF agents to log decisions during
query processing and extraction workflows. Automatically captures rationale,
evidence from source documents, and links to entities.

Usage:
    from src.decision_trace_layer.agent_logger import AgentDecisionLogger
    
    logger = AgentDecisionLogger(tenant_id, decision_maker_id)
    
    logger.log_query_routing_decision(
        query="What's the blast radius if API Gateway fails?",
        tier_selected="TIER2_RLM",
        rationale="Query contains impact/blast radius pattern requiring graph traversal",
        complexity_score=0.85
    )
"""
import os
import json
import uuid
import logging
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

import requests
from sqlalchemy import text

from src.context_foundry.models.schema import get_session, set_tenant_context

logger = logging.getLogger(__name__)


VALID_EVIDENCE_TYPES = [
    "slack_msg", "email", "meeting_segment", "jira", 
    "doc", "pr_comment", "code_review", "manual_note", "agent_log"
]


@dataclass
class DecisionEvidence:
    """Evidence supporting a decision."""
    evidence_type: str = "agent_log"
    source_uri: Optional[str] = None
    source_id: Optional[str] = None
    excerpt: Optional[str] = None


@dataclass 
class PendingDecision:
    """A decision awaiting outcome recording."""
    decision_uuid: str
    human_id: str
    summary: str
    decision_type: str
    created_at: datetime


class AgentDecisionLogger:
    """
    Logger for capturing agent decisions during CF workflows.
    
    Captures:
    - Query routing decisions (simple vs RLM)
    - Entity resolution decisions (which entity matched and why)
    - Sufficiency assessments (SUFFICIENT/PARTIAL/INSUFFICIENT)
    - Confidence calibration decisions (quadrant, adjustments)
    - Answer synthesis decisions (grounded vs gap vs inferred)
    """
    
    DECISION_TYPES = {
        "query_routing": "Query Routing",
        "entity_resolution": "Entity Resolution", 
        "sufficiency_assessment": "Sufficiency Assessment",
        "confidence_calibration": "Confidence Calibration",
        "answer_synthesis": "Answer Synthesis",
        "extraction_decision": "Extraction Decision",
        "duplicate_detection": "Duplicate Detection",
        "schema_evolution": "Schema Evolution"
    }
    
    def __init__(
        self, 
        tenant_id: str,
        decision_maker_id: str,
        source_system: str = "cf_agent",
        auto_enact: bool = True
    ):
        """
        Initialize the decision logger.
        
        Args:
            tenant_id: The tenant this logger operates for
            decision_maker_id: UUID of the agent/user making decisions
            source_system: Identifier for the source system
            auto_enact: If True, decisions are immediately enacted (not draft)
        """
        self.tenant_id = tenant_id
        self.decision_maker_id = decision_maker_id
        self.source_system = source_system
        self.auto_enact = auto_enact
        self._pending_decisions: Dict[str, PendingDecision] = {}
    
    def _get_embedding(self, text_input: str) -> List[float]:
        """Get embedding from OpenAI."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, skipping embedding")
            return [0.0] * 1536
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={"model": "text-embedding-3-small", "input": text_input[:8000]},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
            return [0.0] * 1536
    
    def _format_embedding_for_pgvector(self, embedding: List[float]) -> str:
        """Format embedding list as pgvector-compatible string."""
        return "[" + ",".join(str(x) for x in embedding) + "]"
    
    def _create_decision(
        self,
        decision_type: str,
        summary: str,
        choice: Dict[str, Any],
        rationale: str,
        evidence: List[DecisionEvidence],
        entity_ids: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        sensitivity: str = "internal"
    ) -> Optional[str]:
        """
        Internal method to create a decision trace.
        
        Returns the human-readable decision ID (e.g., DEC-2025-ABC123).
        """
        session = None
        try:
            session = get_session(use_rls_role=True)
            set_tenant_context(session, self.tenant_id)
            
            decision_uuid = str(uuid.uuid4())
            human_id = f"DEC-{datetime.now().strftime('%Y')}-{decision_uuid[:8].upper()}"
            
            embedding = self._get_embedding(f"{summary}. {rationale}")
            embedding_str = self._format_embedding_for_pgvector(embedding)
            
            lifecycle = "enacted" if self.auto_enact else "draft"
            
            choice_json = json.dumps(choice)
            context_json = json.dumps(context or {})
            
            session.execute(text("""
                INSERT INTO decision_traces (
                    id, decision_id, decision_timestamp, decision_summary,
                    decision_choice, decision_maker_id, decision_type,
                    rationale_summary, rationale_embedding, context_snapshot,
                    lifecycle_state, source_system, created_by, tenant_id, sensitivity
                ) VALUES (
                    CAST(:id AS uuid), :human_id, :timestamp, :summary,
                    CAST(:choice AS jsonb), CAST(:maker_id AS uuid), :dtype,
                    :rationale, CAST(:embedding AS vector), CAST(:context AS jsonb),
                    :lifecycle, :source, :created_by, CAST(:tenant_id AS uuid), :sensitivity
                )
            """), {
                "id": decision_uuid,
                "human_id": human_id,
                "timestamp": datetime.utcnow(),
                "summary": summary,
                "choice": choice_json,
                "maker_id": self.decision_maker_id,
                "dtype": decision_type,
                "rationale": rationale,
                "embedding": embedding_str,
                "context": context_json,
                "lifecycle": lifecycle,
                "source": self.source_system,
                "created_by": "agent_logger",
                "tenant_id": self.tenant_id,
                "sensitivity": sensitivity
            })
            
            for ev in evidence:
                session.execute(text("""
                    INSERT INTO decision_evidence (
                        decision_id, evidence_type, source_uri, source_id, excerpt
                    ) VALUES (CAST(:decision_id AS uuid), :etype, :uri, :source_id, :excerpt)
                """), {
                    "decision_id": decision_uuid,
                    "etype": ev.evidence_type,
                    "uri": ev.source_uri,
                    "source_id": ev.source_id,
                    "excerpt": ev.excerpt
                })
            
            if entity_ids:
                for entity_id in entity_ids:
                    session.execute(text("""
                        INSERT INTO decision_entity_links (
                            decision_id, entity_id, entity_role, resolution_method
                        ) VALUES (CAST(:decision_id AS uuid), CAST(:entity_id AS uuid), 'subject', 'automatic')
                    """), {
                        "decision_id": decision_uuid,
                        "entity_id": entity_id
                    })
            
            session.execute(text("""
                INSERT INTO decision_confidence_scores (
                    decision_id, overall_confidence, rationale_completeness,
                    scoring_model_version
                ) VALUES (CAST(:decision_id AS uuid), 1.0, 1.0, 'agent_logger_v1')
            """), {"decision_id": decision_uuid})
            
            session.commit()
            
            self._pending_decisions[human_id] = PendingDecision(
                decision_uuid=decision_uuid,
                human_id=human_id,
                summary=summary,
                decision_type=decision_type,
                created_at=datetime.utcnow()
            )
            
            logger.info(f"Created decision {human_id}: {summary[:50]}...")
            return human_id
            
        except Exception as e:
            if session:
                session.rollback()
            logger.error(f"Failed to create decision: {e}")
            return None
        finally:
            if session:
                session.close()
    
    def log_query_routing_decision(
        self,
        query: str,
        tier_selected: str,
        rationale: str,
        complexity_score: float = 0.0,
        complexity_signals: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Log a query routing decision (TIER1_SIMPLE vs TIER2_RLM).
        
        Args:
            query: The original query text
            tier_selected: "TIER1_SIMPLE" or "TIER2_RLM"
            rationale: Why this tier was selected
            complexity_score: The computed complexity score
            complexity_signals: Detailed signals that contributed to the decision
        """
        return self._create_decision(
            decision_type="query_routing",
            summary=f"Routed query to {tier_selected}",
            choice={
                "tier": tier_selected,
                "complexity_score": complexity_score
            },
            rationale=rationale,
            evidence=[DecisionEvidence(
                evidence_type="agent_log",
                excerpt=f"Query: {query[:500]}"
            )],
            context={
                "query": query,
                "complexity_signals": complexity_signals or {}
            }
        )
    
    def log_entity_resolution_decision(
        self,
        query_text: str,
        resolved_entity_id: Optional[str],
        resolved_entity_name: Optional[str],
        match_stage: str,
        confidence: float,
        rationale: str,
        candidates: Optional[List[Dict]] = None,
        needs_disambiguation: bool = False
    ) -> Optional[str]:
        """
        Log an entity resolution decision.
        
        Args:
            query_text: The text being resolved
            resolved_entity_id: UUID of the resolved entity (if any)
            resolved_entity_name: Name of the resolved entity
            match_stage: Stage where match was found (exact, semantic, fuzzy)
            confidence: Match confidence score
            rationale: Why this entity was selected
            candidates: List of candidate entities considered
            needs_disambiguation: True if multiple close matches
        """
        summary = f"Resolved '{query_text}' to {resolved_entity_name or 'NO_MATCH'}"
        if needs_disambiguation:
            summary = f"Disambiguation needed for '{query_text}'"
        
        return self._create_decision(
            decision_type="entity_resolution",
            summary=summary,
            choice={
                "resolved_entity_id": resolved_entity_id,
                "resolved_entity_name": resolved_entity_name,
                "match_stage": match_stage,
                "confidence": confidence,
                "needs_disambiguation": needs_disambiguation
            },
            rationale=rationale,
            evidence=[DecisionEvidence(
                evidence_type="agent_log",
                excerpt=f"Query: '{query_text}' → {resolved_entity_name} ({match_stage}, conf={confidence:.2f})"
            )],
            entity_ids=[resolved_entity_id] if resolved_entity_id else None,
            context={
                "query_text": query_text,
                "candidates": candidates or []
            }
        )
    
    def log_sufficiency_decision(
        self,
        query: str,
        classification: str,
        key_facts_found: List[str],
        key_facts_missing: List[str],
        context_summary: str
    ) -> Optional[str]:
        """
        Log a sufficiency assessment decision.
        
        Args:
            query: The original query
            classification: SUFFICIENT, PARTIAL, or INSUFFICIENT
            key_facts_found: Facts that were found in context
            key_facts_missing: Facts that were needed but missing
            context_summary: Brief summary of the context evaluated
        """
        return self._create_decision(
            decision_type="sufficiency_assessment",
            summary=f"Context sufficiency: {classification}",
            choice={
                "classification": classification,
                "facts_found_count": len(key_facts_found),
                "facts_missing_count": len(key_facts_missing)
            },
            rationale=f"Found {len(key_facts_found)} key facts, missing {len(key_facts_missing)} facts. Classification: {classification}",
            evidence=[
                DecisionEvidence(
                    evidence_type="agent_log",
                    excerpt=f"Query: {query[:200]}... Context: {context_summary[:300]}"
                )
            ],
            context={
                "query": query,
                "key_facts_found": key_facts_found,
                "key_facts_missing": key_facts_missing
            }
        )
    
    def log_confidence_decision(
        self,
        query: str,
        quadrant: str,
        base_confidence: float,
        final_confidence: float,
        entity_found: bool,
        docs_found: bool,
        sufficiency: str,
        entity_density: float
    ) -> Optional[str]:
        """
        Log a confidence calibration decision.
        
        Args:
            query: The original query
            quadrant: Q1, Q2, Q3, or Q4
            base_confidence: Initial quadrant-based confidence
            final_confidence: Final calibrated confidence
            entity_found: Whether target entity was found
            docs_found: Whether supporting documents were found
            sufficiency: SUFFICIENT/PARTIAL/INSUFFICIENT
            entity_density: Ratio of known entities in docs
        """
        return self._create_decision(
            decision_type="confidence_calibration",
            summary=f"Confidence: {final_confidence:.0%} ({quadrant})",
            choice={
                "quadrant": quadrant,
                "base_confidence": base_confidence,
                "final_confidence": final_confidence,
                "entity_found": entity_found,
                "docs_found": docs_found
            },
            rationale=f"Quadrant {quadrant}: entity_found={entity_found}, docs_found={docs_found}, sufficiency={sufficiency}, density={entity_density:.2f}. Base {base_confidence:.2f} → Final {final_confidence:.2f}",
            evidence=[DecisionEvidence(
                evidence_type="agent_log",
                excerpt=f"Confidence calibration for: {query[:200]}"
            )],
            context={
                "query": query,
                "sufficiency": sufficiency,
                "entity_density": entity_density
            }
        )
    
    def log_answer_synthesis_decision(
        self,
        query: str,
        response_type: str,
        confidence: float,
        answer_preview: str,
        entities_cited: List[str],
        documents_cited: List[str]
    ) -> Optional[str]:
        """
        Log an answer synthesis decision.
        
        Args:
            query: The original query
            response_type: GROUNDED, GAP, or INFERRED
            confidence: Final answer confidence
            answer_preview: First 500 chars of answer
            entities_cited: Entity names cited in answer
            documents_cited: Document titles cited
        """
        return self._create_decision(
            decision_type="answer_synthesis",
            summary=f"Synthesized {response_type} answer (conf={confidence:.0%})",
            choice={
                "response_type": response_type,
                "confidence": confidence,
                "entities_cited_count": len(entities_cited),
                "documents_cited_count": len(documents_cited)
            },
            rationale=f"Generated {response_type} response with {len(entities_cited)} entities and {len(documents_cited)} documents cited. Confidence: {confidence:.2f}",
            evidence=[
                DecisionEvidence(
                    evidence_type="agent_log",
                    excerpt=f"Query: {query[:200]}... Answer: {answer_preview[:300]}"
                )
            ],
            context={
                "query": query,
                "entities_cited": entities_cited,
                "documents_cited": documents_cited
            }
        )
    
    def log_extraction_decision(
        self,
        document_id: str,
        document_name: str,
        entities_extracted: int,
        relationships_extracted: int,
        extraction_mode: str,
        rationale: str,
        chunk_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Log an extraction decision.
        
        Args:
            document_id: UUID of the document
            document_name: Name of the document
            entities_extracted: Number of entities extracted
            relationships_extracted: Number of relationships extracted
            extraction_mode: Mode used (full, incremental, ontology_centric)
            rationale: Why these extractions were made
            chunk_id: Source chunk ID if chunk-level extraction
        """
        return self._create_decision(
            decision_type="extraction_decision",
            summary=f"Extracted {entities_extracted}E/{relationships_extracted}R from {document_name}",
            choice={
                "entities_extracted": entities_extracted,
                "relationships_extracted": relationships_extracted,
                "extraction_mode": extraction_mode
            },
            rationale=rationale,
            evidence=[DecisionEvidence(
                evidence_type="doc",
                source_id=document_id,
                excerpt=f"Document: {document_name}, Mode: {extraction_mode}"
            )],
            context={
                "document_id": document_id,
                "document_name": document_name,
                "chunk_id": chunk_id
            }
        )
    
    def log_duplicate_detection_decision(
        self,
        entity_name: str,
        entity_id: str,
        is_duplicate: bool,
        duplicate_of_id: Optional[str],
        similarity_score: float,
        rationale: str
    ) -> Optional[str]:
        """
        Log a duplicate detection decision.
        
        Args:
            entity_name: Name of the entity being evaluated
            entity_id: UUID of the entity
            is_duplicate: Whether it was determined to be a duplicate
            duplicate_of_id: UUID of the entity it duplicates (if any)
            similarity_score: Similarity score to the potential duplicate
            rationale: Why this determination was made
        """
        summary = f"{'Duplicate' if is_duplicate else 'Unique'}: {entity_name}"
        if is_duplicate:
            summary += f" (of {duplicate_of_id})"
        
        return self._create_decision(
            decision_type="duplicate_detection",
            summary=summary,
            choice={
                "is_duplicate": is_duplicate,
                "duplicate_of_id": duplicate_of_id,
                "similarity_score": similarity_score
            },
            rationale=rationale,
            evidence=[DecisionEvidence(
                evidence_type="agent_log",
                excerpt=f"Entity: {entity_name}, Similarity: {similarity_score:.2f}"
            )],
            entity_ids=[entity_id]
        )
    
    def record_outcome(
        self,
        decision_id: str,
        outcome_status: str,
        notes: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record the outcome of a previous decision.
        
        Args:
            decision_id: The human-readable decision ID (DEC-2025-...)
            outcome_status: positive, neutral, negative, or unknown
            notes: Optional notes about the outcome
            metrics: Optional metrics (accuracy, latency, etc.)
        """
        session = None
        try:
            session = get_session(use_rls_role=True)
            set_tenant_context(session, self.tenant_id)
            
            decision_uuid = session.execute(text("""
                SELECT id FROM decision_traces 
                WHERE decision_id = :decision_id
                AND tenant_id = CAST(:tenant_id AS uuid)
            """), {"decision_id": decision_id, "tenant_id": self.tenant_id}).scalar()
            
            if not decision_uuid:
                logger.warning(f"Decision {decision_id} not found")
                return False
            
            result_id = str(uuid.uuid4())
            metrics_json = json.dumps(metrics or {})
            
            session.execute(text("""
                INSERT INTO decision_results (
                    id, decision_id, outcome_status, outcome_metrics, result_notes
                ) VALUES (CAST(:id AS uuid), CAST(:decision_id AS uuid), :status, CAST(:metrics AS jsonb), :notes)
            """), {
                "id": result_id,
                "decision_id": str(decision_uuid),
                "status": outcome_status,
                "metrics": metrics_json,
                "notes": notes
            })
            
            session.commit()
            
            if decision_id in self._pending_decisions:
                del self._pending_decisions[decision_id]
            
            logger.info(f"Recorded {outcome_status} outcome for {decision_id}")
            return True
            
        except Exception as e:
            if session:
                session.rollback()
            logger.error(f"Failed to record outcome: {e}")
            return False
        finally:
            if session:
                session.close()
    
    def get_pending_decisions(self) -> List[PendingDecision]:
        """Get decisions that haven't had outcomes recorded."""
        return list(self._pending_decisions.values())
