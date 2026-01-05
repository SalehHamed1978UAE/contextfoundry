"""
Context Foundry Core - Main orchestration layer.
Coordinates all agents and memory layers for query processing.

Supports dual-tier query routing:
- Tier 1: Simple single-hop queries via RetrievalAgent pipeline
- Tier 2: Complex multi-hop queries via RLM iterative reasoning
"""
import uuid
import json
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session

from .models.schema import get_session, init_database, QueryLog
from .models.context_bundle import ContextBundle
from .agents.graph_loader import GraphLoaderAgent
from .agents.retrieval import RetrievalAgent
from .agents.reasoning import ReasoningAgent
from .agents.validation import ValidationAgent
from .utils.logger import logger, QueryLogger, display_context_bundle, display_response
from .rlm.router import QueryComplexityRouter, QueryTier
from .rlm.executor import RLMExecutor, RLMResult
from .rlm.schemas import RLMConfig


DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"


class ContextFoundry:
    """
    Main orchestration class for the Context Foundry system.
    Coordinates tri-memory architecture for intelligent query processing.
    
    Supports dual-tier query routing:
    - Tier 1: Simple queries via RetrievalAgent + ReasoningAgent pipeline
    - Tier 2: Complex multi-hop queries via RLM iterative reasoning
    """
    
    def __init__(
        self, 
        tenant_id: str = DEFAULT_TENANT_ID,
        session: Optional[Session] = None, 
        enable_rlm: bool = True,
        rlm_config: Optional[RLMConfig] = None
    ):
        self.session = session or get_session()
        self.tenant_id = tenant_id
        self.enable_rlm = enable_rlm
        self.rlm_config = rlm_config
        
        self.retrieval = RetrievalAgent(self.session)
        self.reasoning = ReasoningAgent()
        self.validation = ValidationAgent(self.session)
        
        self.router = QueryComplexityRouter()
        
        self.is_initialized = False
        
        logger.info(f"ContextFoundry core initialized (RLM enabled: {enable_rlm})")
    
    def cleanup(self):
        """Clean up the session to recover from errors."""
        try:
            if self.session:
                self.session.rollback()
                self.session.close()
                logger.info("ContextFoundry session cleaned up")
        except Exception as e:
            logger.warning(f"Error during session cleanup: {e}")
    
    def initialize_database(self):
        """Initialize the database schema."""
        init_database()
        self.is_initialized = True
        logger.info("Database initialized")
    
    def load_data(self, data: Dict, auto_promote: bool = True) -> Dict:
        """Load data into the tri-memory system."""
        loader = GraphLoaderAgent(self.session, auto_promote=auto_promote)
        stats = loader.load_synthetic_data(data)
        logger.info(f"Data loaded: {stats}")
        return stats
    
    def query(
        self,
        query_text: str,
        display_output: bool = True,
        save_to_log: bool = True,
        as_of_date: str = None,
        force_tier: Optional[str] = None
    ) -> Dict:
        """
        Process a query through the full Context Foundry pipeline.
        
        Routes queries to appropriate tier:
        - Tier 1: Simple queries via RetrievalAgent + ReasoningAgent pipeline
        - Tier 2: Complex multi-hop queries via RLM iterative reasoning
        
        Pipeline (Tier 1):
        1. Retrieval Agent builds ContextBundle from all three memory layers
        2. Reasoning Agent generates response with LLM
        3. Validation Agent checks response against rules
        4. Response returned with full provenance
        
        Args:
            as_of_date: Optional ISO date string for temporal queries.
                        If provided, returns knowledge graph state as of this date.
            force_tier: Optional tier override ("tier1" or "tier2"). If None, uses router.
        """
        query_id = str(uuid.uuid4())
        query_logger = QueryLogger(query_id, query_text)
        
        try:
            tier, signals = self.router.route(query_text)
            
            if force_tier == "tier1":
                tier = QueryTier.TIER1_SIMPLE
            elif force_tier == "tier2":
                if not self.enable_rlm:
                    raise ValueError("Cannot force tier2 when RLM is disabled. Set enable_rlm=True.")
                tier = QueryTier.TIER2_RLM
            
            query_logger.log_event("PIPELINE_START", {
                "query": query_text, 
                "as_of_date": as_of_date,
                "tier": tier.value,
                "complexity_score": signals.complexity_score,
                "rlm_enabled": self.enable_rlm
            })
            
            if tier == QueryTier.TIER2_RLM and self.enable_rlm:
                return self._query_tier2_rlm(query_text, query_id, query_logger, display_output, save_to_log)
            
            bundle = self.retrieval.build_context_bundle(
                query_text,
                query_logger=query_logger,
                as_of_date=as_of_date
            )
            
            if bundle.target_entity_name and not bundle.target_entity_found:
                query_logger.log_event("ENTITY_NOT_FOUND_GUARD", {
                    "target_entity": bundle.target_entity_name,
                    "action": "short_circuit_before_reasoning"
                })
                logger.warning(f"ENTITY NOT FOUND: '{bundle.target_entity_name}' - refusing to hallucinate")
                
                similar = self._find_similar_entities(bundle.target_entity_name)
                similar_msg = f" Did you mean: {', '.join(similar[:3])}?" if similar else ""
                
                response = {
                    "answer": f"Entity '{bundle.target_entity_name}' was not found in the knowledge graph. "
                             f"Cannot answer questions about non-existent entities.{similar_msg}",
                    "confidence": 0.0,
                    "confidence_level": "very_low",
                    "entity_not_found": True,
                    "target_entity": bundle.target_entity_name,
                    "similar_entities": similar,
                    "evidence_chain": [],
                    "uncertainty": {
                        "reasons": ["The queried entity does not exist in the knowledge base"],
                        "would_help": [
                            f"Add documentation about '{bundle.target_entity_name}'",
                            "Check if the entity exists under a different name"
                        ]
                    },
                    "rules_applied": [],
                    "caveats": [
                        "Context Foundry refuses to fabricate information about non-existent entities"
                    ],
                    "bundle_id": bundle.query_id,
                    "query_text": bundle.query_text,
                    "context_bundle": bundle.to_dict()
                }
                
                summary = query_logger.log_complete(success=True, final_confidence=0.0)
                response["query_log"] = summary
                return response
            
            if display_output:
                display_context_bundle(bundle.to_dict())
            
            response = self.reasoning.reason(bundle, query_logger=query_logger)
            
            response = self.validation.validate_response(
                response, bundle, query_logger=query_logger
            )
            
            if display_output:
                display_response(response)
            
            if save_to_log:
                self._save_query_log(query_id, query_text, bundle, response)
            
            summary = query_logger.log_complete(
                success=not response.get("error", False),
                final_confidence=response.get("confidence", 0)
            )
            
            response["query_log"] = summary
            
            return response
            
        except Exception as e:
            query_logger.log_error("PIPELINE_ERROR", str(e))
            logger.exception(f"Query pipeline error: {e}")
            
            try:
                self.session.rollback()
            except Exception:
                pass
            
            return {
                "answer": f"Error processing query: {str(e)}",
                "confidence": 0,
                "confidence_level": "very_low",
                "error": True,
                "error_message": str(e),
                "query_id": query_id,
                "query_text": query_text
            }
    
    def query_impact(self, entity_name: str) -> Dict:
        """
        Special query: What services are affected if this entity fails?
        """
        query_text = f"What services are affected if {entity_name} goes down?"
        
        impact = self.retrieval.get_impact_analysis(entity_name)
        
        return self.query(query_text)
    
    def query_escalation(self, context: str) -> Dict:
        """
        Special query: Who should I escalate to?
        """
        query_text = f"Who should I escalate to for {context}?"
        return self.query(query_text)
    
    def _query_tier2_rlm(
        self,
        query_text: str,
        query_id: str,
        query_logger: QueryLogger,
        display_output: bool,
        save_to_log: bool
    ) -> Dict:
        """
        Process a complex query through the RLM (Recursive Language Model) pipeline.
        
        RLM allows iterative exploration of the knowledge graph with code execution.
        After RLM exploration, results are validated through ValidationAgent for
        rule compliance and governance parity with Tier 1.
        
        Args:
            query_text: The query to process
            query_id: Unique query identifier
            query_logger: Logger for query events
            display_output: Whether to display output
            save_to_log: Whether to save to query log
        
        Returns:
            Dict with answer, confidence, evidence, and RLM execution trace
        """
        from .models.context_bundle import create_bundle
        
        query_logger.log_event("RLM_START", {"tier": "tier2"})
        
        try:
            executor = RLMExecutor(
                tenant_id=self.tenant_id,
                db_session=self.session,
                config=self.rlm_config
            )
            
            result: RLMResult = executor.execute(query_text)
            
            query_logger.log_event("RLM_COMPLETE", {
                "status": result.status,
                "iterations": result.execution_trace.total_iterations,
                "entities_discovered": result.execution_trace.total_entities_discovered,
                "relationships_discovered": result.execution_trace.total_relationships_discovered,
                "tokens_used": result.tokens_used
            })
            
            bundle = self._build_rlm_context_bundle(query_text, result)
            
            confidence_level = "high" if result.confidence >= 0.7 else \
                              "medium" if result.confidence >= 0.4 else \
                              "low" if result.confidence >= 0.2 else "very_low"
            
            response = {
                "answer": result.answer_text or result.answer,
                "confidence": result.confidence,
                "confidence_level": confidence_level,
                "response_mode": result.response_mode,
                "evidence_chain": result.evidence_chain,
                "entities_found": [e.dict() if hasattr(e, 'dict') else e for e in result.entities_found],
                "relationships_found": [r.dict() if hasattr(r, 'dict') else r for r in result.relationships_found],
                "query_tier": "tier2_rlm",
                "caveats": self._build_rlm_caveats(result),
                "uncertainty": self._build_rlm_uncertainty(result),
                "rlm_execution": {
                    "status": result.status,
                    "query_id": result.query_id,
                    "iterations": result.execution_trace.total_iterations,
                    "entities_discovered": result.execution_trace.total_entities_discovered,
                    "relationships_discovered": result.execution_trace.total_relationships_discovered,
                    "tokens_used": result.tokens_used,
                    "estimated_cost_usd": result.estimated_cost_usd,
                    "latency_ms": result.latency_ms
                },
                "query_id": query_id,
                "query_text": query_text
            }
            
            response = self.validation.validate_response(response, bundle, query_logger=query_logger)
            
            response["context_bundle"] = bundle.to_dict()
            
            if display_output:
                logger.info(f"RLM Answer: {result.answer_text}")
                logger.info(f"Confidence: {result.confidence} ({confidence_level})")
                logger.info(f"Iterations: {result.execution_trace.total_iterations}")
                if response.get("rules_violations"):
                    logger.warning(f"Rule violations: {response['rules_violations']}")
            
            if save_to_log:
                self._save_query_log(query_id, query_text, bundle, response)
            
            summary = query_logger.log_complete(
                success=result.status in ("completed", "circuit_breaker", "max_iterations"),
                final_confidence=result.confidence
            )
            response["query_log"] = summary
            
            return response
            
        except Exception as e:
            query_logger.log_error("RLM_ERROR", str(e))
            logger.exception(f"RLM pipeline error: {e}")
            
            try:
                self.session.rollback()
            except Exception:
                pass
            
            return {
                "answer": f"Error in RLM processing: {str(e)}",
                "confidence": 0,
                "confidence_level": "very_low",
                "error": True,
                "error_message": str(e),
                "query_tier": "tier2_rlm",
                "rules_checked": [],
                "rules_passed": [],
                "rules_violations": [],
                "rules_warnings": [],
                "caveats": ["RLM execution encountered an error"],
                "uncertainty": {"reasons": [str(e)], "would_help": ["Review error logs"]},
                "query_id": query_id,
                "query_text": query_text
            }
    
    def _build_rlm_context_bundle(self, query_text: str, result: RLMResult) -> ContextBundle:
        """
        Build a ContextBundle from RLM execution results.
        
        This allows RLM results to be validated through the same ValidationAgent
        pipeline as Tier 1 queries, ensuring governance parity.
        
        Populates:
        - semantic_entities from RLM discovered entities
        - semantic_relationships from RLM discovered relationships
        - symbolic_rules loaded from SymbolicMemory based on discovered entity types
        """
        from .models.context_bundle import create_bundle
        from .memory.symbolic import SymbolicMemory
        
        bundle = create_bundle(query_text)
        
        entity_types = set()
        relationship_types = set()
        
        for entity in result.entities_found:
            if hasattr(entity, 'dict'):
                entity_dict = entity.dict()
                bundle.semantic_entities.append(entity_dict)
                if entity_dict.get('entity_type'):
                    entity_types.add(entity_dict['entity_type'])
            elif isinstance(entity, dict):
                bundle.semantic_entities.append(entity)
                if entity.get('entity_type'):
                    entity_types.add(entity['entity_type'])
            else:
                bundle.semantic_entities.append({"id": str(entity), "name": str(entity)})
        
        for rel in result.relationships_found:
            if hasattr(rel, 'dict'):
                rel_dict = rel.dict()
                bundle.semantic_relationships.append(rel_dict)
                if rel_dict.get('relationship_type'):
                    relationship_types.add(rel_dict['relationship_type'])
            elif isinstance(rel, dict):
                bundle.semantic_relationships.append(rel)
                if rel.get('relationship_type'):
                    relationship_types.add(rel['relationship_type'])
            else:
                bundle.semantic_relationships.append({"type": str(rel)})
        
        try:
            symbolic = SymbolicMemory(self.session)
            if entity_types or relationship_types:
                applicable_rules = symbolic.find_applicable_rules(
                    entity_types=list(entity_types) if entity_types else None,
                    relationship_types=list(relationship_types) if relationship_types else None,
                    query_keywords=query_text.split()[:10]
                )
                bundle.symbolic_rules = applicable_rules[:10]
        except Exception as e:
            logger.warning(f"Failed to load symbolic rules for RLM bundle: {e}")
        
        bundle.retrieval_metadata["rlm_execution"] = {
            "status": result.status,
            "iterations": result.execution_trace.total_iterations,
            "entities_discovered": result.execution_trace.total_entities_discovered,
            "relationships_discovered": result.execution_trace.total_relationships_discovered,
            "tokens_used": result.tokens_used,
            "estimated_cost_usd": result.estimated_cost_usd
        }
        bundle.retrieval_metadata["query_tier"] = "tier2_rlm"
        bundle.retrieval_metadata["entity_types_found"] = list(entity_types)
        bundle.retrieval_metadata["relationship_types_found"] = list(relationship_types)
        
        return bundle
    
    def _build_rlm_caveats(self, result: RLMResult) -> list:
        """Build caveats list based on RLM execution result."""
        caveats = []
        
        if result.status == "circuit_breaker":
            caveats.append("Query exploration was cut short due to lack of progress")
        elif result.status == "max_iterations":
            caveats.append("Query reached maximum exploration iterations")
        elif result.status == "budget_exhausted":
            caveats.append("Query budget was exhausted before completion")
        
        if result.response_mode == "INFERRED":
            caveats.append("Answer is based on partial information and inference")
        elif result.response_mode == "GAP":
            caveats.append("Insufficient data found to answer the query")
        
        if result.execution_trace.total_entities_discovered == 0:
            caveats.append("No relevant entities were discovered during exploration")
        
        return caveats
    
    def _build_rlm_uncertainty(self, result: RLMResult) -> dict:
        """Build uncertainty dict based on RLM execution result."""
        reasons = []
        would_help = []
        
        if result.confidence < 0.5:
            reasons.append("Low confidence in answer due to limited evidence")
        
        if result.execution_trace.total_entities_discovered < 3:
            reasons.append(f"Only {result.execution_trace.total_entities_discovered} entities discovered")
            would_help.append("Add more relevant entities to the knowledge graph")
        
        if result.execution_trace.total_relationships_discovered < 2:
            reasons.append(f"Only {result.execution_trace.total_relationships_discovered} relationships discovered")
            would_help.append("Document more relationships between entities")
        
        if result.status != "completed":
            reasons.append(f"Exploration ended with status: {result.status}")
            would_help.append("Simplify the query or increase exploration budget")
        
        return {"reasons": reasons, "would_help": would_help}
    
    def _save_query_log(
        self,
        query_id: str,
        query_text: str,
        bundle: ContextBundle,
        response: Dict
    ):
        """Save query execution to the query log table."""
        try:
            log_entry = QueryLog(
                id=uuid.UUID(query_id),
                query_text=query_text,
                semantic_entities_count=len(bundle.semantic_entities),
                semantic_relationships_count=len(bundle.semantic_relationships),
                episodic_documents_count=len(bundle.episodic_documents),
                rules_checked_count=len(response.get("rules_checked", [])),
                rules_passed_count=len(response.get("rules_passed", [])),
                response_text=response.get("answer", ""),
                confidence=response.get("confidence", 0),
                success=not response.get("error", False),
                context_bundle=bundle.to_dict(),
                evidence_chain=response.get("evidence_chain", []),
                duration_seconds=response.get("query_log", {}).get("duration_seconds", 0)
            )
            self.session.add(log_entry)
            self.session.commit()
            logger.debug(f"Query log saved: {query_id}")
        except Exception as e:
            logger.error(f"Failed to save query log: {e}")
            try:
                self.session.rollback()
            except Exception:
                pass
    
    def reset_session(self):
        """Reset session to recover from connection errors."""
        try:
            if self.session:
                self.session.rollback()
                self.session.close()
        except Exception:
            pass
        
        self.session = get_session()
        self.retrieval = RetrievalAgent(self.session)
        self.validation = ValidationAgent(self.session)
        logger.info("ContextFoundry session reset")
    
    def get_statistics(self) -> Dict:
        """Get statistics about the Context Foundry system."""
        return {
            "semantic_memory": self.retrieval.semantic.get_statistics(),
            "episodic_memory": self.retrieval.episodic.get_statistics(),
            "symbolic_memory": self.retrieval.symbolic.get_statistics(),
            "queries_executed": self.session.query(QueryLog).count()
        }
    
    def export_context_bundle(self, bundle: ContextBundle, filepath: str):
        """Export a ContextBundle to a JSON file for analysis."""
        with open(filepath, 'w') as f:
            json.dump(bundle.to_dict(), f, indent=2, default=str)
        logger.info(f"ContextBundle exported to {filepath}")
    
    def export_response(self, response: Dict, filepath: str):
        """Export a response to a JSON file for analysis."""
        with open(filepath, 'w') as f:
            json.dump(response, f, indent=2, default=str)
        logger.info(f"Response exported to {filepath}")
    
    def _find_similar_entities(self, target_name: str, limit: int = 5):
        """
        Find entities with similar names to suggest as alternatives.
        
        Uses substring matching and word overlap for fuzzy matching.
        """
        from .models.schema import Entity, LifecycleState
        
        try:
            all_entities = self.session.query(Entity.name).filter(
                Entity.lifecycle_state.in_([LifecycleState.TRUSTED, LifecycleState.STAGING])
            ).distinct().limit(500).all()
            
            target_lower = target_name.lower()
            target_words = set(target_lower.split())
            
            scored = []
            for (name,) in all_entities:
                name_lower = name.lower()
                score = 0
                if target_lower in name_lower or name_lower in target_lower:
                    score += 3
                name_words = set(name_lower.split())
                common_words = target_words & name_words
                score += len(common_words) * 2
                if score > 0:
                    scored.append((name, score))
            
            scored.sort(key=lambda x: -x[1])
            return [name for name, _ in scored[:limit]]
        except Exception as e:
            logger.warning(f"Failed to find similar entities: {e}")
            return []
