"""
Context Foundry Core - Main orchestration layer.
Coordinates all agents and memory layers for query processing.

Supports dual-tier query routing:
- Tier 1: Simple single-hop queries via RetrievalAgent pipeline
- Tier 2: Complex multi-hop queries via RLM iterative reasoning
"""
import uuid
import json
from dataclasses import asdict
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session

from .models.schema import get_session, init_database, QueryLog
from .models.context_bundle import ContextBundle
from .agents.graph_loader import GraphLoaderAgent
from .agents.retrieval import RetrievalAgent
from .agents.reasoning import ReasoningAgent
from .agents.validation import ValidationAgent
from .agents.query_pipeline import QueryPipeline, PipelineResult
from .utils.logger import logger, QueryLogger, display_context_bundle, display_response
from .rlm.router import QueryComplexityRouter, QueryTier
from .rlm.executor import RLMExecutor, RLMResult
from .rlm.schemas import RLMConfig
from .agents.financial_query_handler import FinancialQueryHandler
from .pipeline.precedence_pipeline import apply_precedence

try:
    from src.decision_trace_layer.decision_orchestrator import (
        DecisionOrchestrator, DecisionType, OrchestratorConfig, create_orchestrator_for_tenant
    )
    DTL_AVAILABLE = True
except ImportError:
    DTL_AVAILABLE = False


DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"
CF_DECISION_MAKER_ID = "00000000-0000-0000-0000-cf0000000001"


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
        rlm_config: Optional[RLMConfig] = None,
        enable_precedent_lookup: bool = True
    ):
        self.session = session or get_session()
        self.tenant_id = tenant_id
        self.enable_rlm = enable_rlm
        self.rlm_config = rlm_config
        self.enable_precedent_lookup = enable_precedent_lookup and DTL_AVAILABLE
        
        self._set_tenant_context()
        
        self.retrieval = RetrievalAgent(self.session, tenant_id=tenant_id)
        self.reasoning = ReasoningAgent()
        self.validation = ValidationAgent(self.session)
        
        self.router = QueryComplexityRouter()
        
        self._decision_orchestrator = None
        if self.enable_precedent_lookup:
            try:
                self._decision_orchestrator = create_orchestrator_for_tenant(
                    tenant_id=tenant_id,
                    decision_maker_id=CF_DECISION_MAKER_ID,
                    enabled=True
                )
                logger.info("Decision orchestrator initialized with precedent lookup")
            except Exception as e:
                logger.warning(f"Failed to initialize decision orchestrator: {e}")
                self._decision_orchestrator = None
        
        self.is_initialized = False
        
        logger.info(f"ContextFoundry core initialized for tenant {tenant_id[:8] if tenant_id else 'default'}... (RLM enabled: {enable_rlm}, precedents: {self.enable_precedent_lookup})")
    
    def _set_tenant_context(self):
        """Set RLS tenant context on the session."""
        if self.tenant_id:
            try:
                from sqlalchemy import text
                self.session.execute(text(f"SET app.current_tenant_id = '{self.tenant_id}'"))
                logger.debug(f"RLS tenant context set: {self.tenant_id[:8]}...")
            except Exception as e:
                logger.warning(f"Failed to set RLS tenant context: {e}")
    
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
        loader = GraphLoaderAgent(self.session, auto_promote=auto_promote, tenant_id=self.tenant_id)
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
        
        # Re-set tenant context at start of every query (defensive - in case of session reset)
        self._set_tenant_context()
        
        try:
            tier, signals = self.router.route(query_text)
            precedent_info = {"status": "disabled", "latency_ms": 0}
            
            if self._decision_orchestrator and not force_tier:
                tier, precedent_info = self._route_with_precedents(query_text, tier, signals)
            
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
                "rlm_enabled": self.enable_rlm,
                "precedent_lookup": precedent_info
            })
            
            if tier == QueryTier.TIER2_RLM and self.enable_rlm:
                return self._query_tier2_rlm(query_text, query_id, query_logger, display_output, save_to_log)
            
            # Use 3-step pipeline for impact/blast radius queries (precise direction filtering)
            if self._is_impact_query(query_text):
                query_logger.log_event("USING_3STEP_PIPELINE", {"reason": "impact_query_detected"})
                return self._query_with_3step_pipeline(query_text, query_id, query_logger, display_output, save_to_log)
            
            bundle = self.retrieval.build_context_bundle(
                query_text,
                query_logger=query_logger,
                as_of_date=as_of_date
            )
            
            # AGGREGATION FRAMEWORK: Inject aggregation facts into bundle, let reasoning compose rich response
            # This allows follow-up questions to work because entities are in context
            if bundle.is_aggregation_query and bundle.aggregation_result:
                agg_result = bundle.aggregation_result
                logger.info("Aggregation query - injecting structured facts into context bundle for reasoning")
                
                # Add aggregation facts as structured knowledge for the reasoning agent
                aggregation_fact = {
                    "type": "aggregation_fact",
                    "count": agg_result.value,
                    "unit": agg_result.unit,
                    "result_kind": agg_result.result_kind.value,
                    "display_text": agg_result.display_text,
                    "confidence": agg_result.confidence,
                    "entities_counted": len(bundle.counted_entities) if bundle.counted_entities else 0,
                }
                
                # Add to symbolic rules as a deterministic fact
                bundle.symbolic_rules.append({
                    "rule_type": "aggregation_count",
                    "description": f"Deterministic count: {agg_result.display_text}",
                    "fact": aggregation_fact,
                    "confidence": 1.0,  # SQL count is deterministic
                })
                
                # Log what entities were found for context
                if bundle.counted_entities:
                    entity_names = [e.get("name", "Unknown") for e in bundle.counted_entities[:10]]
                    logger.info(f"Counted entities available for response: {entity_names}")
                
                # Continue to normal reasoning pipeline - don't short-circuit!
            
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
                    "context_bundle": bundle.to_dict(),
                    "answer_source": "gate_blocked",
                    "gate_blocked": True,
                    "gate_name": "entity_not_found",
                    "precedence_applied": True,
                    "precedence_confidence": 1.0
                }
                
                summary = query_logger.log_complete(success=True, final_confidence=0.0)
                response["query_log"] = summary
                return response
            
            if display_output:
                display_context_bundle(bundle.to_dict())
            
            response = self.reasoning.reason(bundle, query_logger=query_logger)
            
            # Apply precedence pipeline (Symbolic > Semantic > Episodic)
            current_answer = response.get("answer", "")
            final_answer, answer_source, prec_confidence = apply_precedence(
                session=self.session,
                tenant_id=self.tenant_id,
                query=query_text,
                current_answer=current_answer,
                bundle=bundle,
                context={"target_entity": bundle.target_entity_name}
            )
            
            # Always set precedence metadata
            response["answer_source"] = answer_source
            response["precedence_applied"] = True
            response["precedence_confidence"] = prec_confidence
            response["gate_blocked"] = False
            
            # Update response if precedence changed it
            if final_answer != current_answer:
                query_logger.log_event("PRECEDENCE_OVERRIDE", {
                    "source": answer_source,
                    "confidence": prec_confidence
                })
                response["answer"] = final_answer
                response["precedence_source"] = answer_source
                if answer_source == "symbolic":
                    response["confidence"] = prec_confidence
            
            response = self.validation.validate_response(
                response, bundle, query_logger=query_logger
            )
            
            # Add aggregation metadata to response if this was an aggregation query
            if bundle.is_aggregation_query and bundle.aggregation_result:
                agg_result = bundle.aggregation_result
                response["is_aggregation"] = True
                response["aggregation_result"] = {
                    "result_kind": agg_result.result_kind.value,
                    "value": agg_result.value,
                    "unit": agg_result.unit,
                    "display_text": agg_result.display_text,
                    "confidence": agg_result.confidence,
                }
                if bundle.counted_entities:
                    response["counted_entities"] = bundle.counted_entities
                # Include anchor entity for pronoun resolution in follow-ups
                if agg_result.cat and agg_result.cat.anchor:
                    anchor = agg_result.cat.anchor
                    response["primary_entity"] = {
                        "id": str(anchor.entity_id) if anchor.entity_id else None,
                        "name": anchor.name,
                        "type": "PERSON"  # Anchor entities are typically PERSON
                    }
                # Use aggregation confidence as primary if higher
                if agg_result.confidence > response.get("confidence", 0):
                    response["confidence"] = agg_result.confidence
                
                # Compose rich answer with entity details
                anchor_name = None
                if agg_result.cat and agg_result.cat.anchor:
                    anchor_name = agg_result.cat.anchor.name
                
                if bundle.counted_entities and len(bundle.counted_entities) > 0:
                    entity_names = [e.get("name", "Unknown") for e in bundle.counted_entities]
                    if anchor_name:
                        if agg_result.result_kind.value == "LOWER_BOUND":
                            response["answer"] = f"{anchor_name} has worked at {agg_result.value} companies: {', '.join(entity_names)}."
                        else:
                            response["answer"] = f"{anchor_name} has worked at {agg_result.value} companies: {', '.join(entity_names)}."
                    else:
                        response["answer"] = f"{agg_result.display_text}: {', '.join(entity_names)}."
                else:
                    response["answer"] = agg_result.display_text
            
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
                self._set_tenant_context()
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
        
        Returns structured impact analysis from graph traversal.
        """
        impact = self.retrieval.get_impact_analysis(entity_name)
        
        if not impact or not impact.get("affected_entities"):
            return {
                "entity_name": entity_name,
                "status": "NO_IMPACT_DATA",
                "message": f"No impact data found for {entity_name}",
                "affected_entities": [],
                "impact_paths": [],
                "confidence": 0.0
            }
        
        return {
            "entity_name": entity_name,
            "status": "IMPACT_FOUND",
            "affected_entities": impact.get("affected_entities", []),
            "impact_paths": impact.get("paths", []),
            "total_affected": len(impact.get("affected_entities", [])),
            "max_depth": impact.get("max_depth", 0),
            "confidence": impact.get("confidence", 0.7)
        }
    
    def query_escalation(self, context: str) -> Dict:
        """
        Special query: Who should I escalate to?
        """
        query_text = f"Who should I escalate to for {context}?"
        return self.query(query_text)
    
    def _route_with_precedents(
        self,
        query_text: str,
        default_tier: QueryTier,
        signals
    ) -> tuple:
        """
        Apply precedent lookup to query routing decision.
        
        GUARDRAIL: 300ms timeout, no-block fallback.
        
        Returns:
            (tier, precedent_info) - tier may be overridden by precedent
        """
        if not self._decision_orchestrator:
            return default_tier, {"status": "disabled", "latency_ms": 0}
        
        try:
            def decide_tier(precedents):
                if precedents:
                    best = precedents[0]
                    if best.score >= 0.7:
                        prior_tier = best.choice.get("tier", default_tier.value)
                        return {
                            "choice": {"tier": prior_tier, "from_precedent": True},
                            "rationale": f"Following precedent {best.summary[:50]}...",
                            "followed_precedent_id": best.precedent_id
                        }
                return {
                    "choice": {"tier": default_tier.value, "from_precedent": False},
                    "rationale": f"No strong precedent, using complexity score {signals.complexity_score:.2f}"
                }
            
            result = self._decision_orchestrator.make_decision(
                decision_type=DecisionType.TIER_SELECTION,
                situation=f"Query routing for: {query_text[:100]}",
                decide_fn=decide_tier
            )
            
            chosen_tier_value = result.choice.get("tier", default_tier.value)
            if chosen_tier_value == "tier1":
                chosen_tier = QueryTier.TIER1_SIMPLE
            elif chosen_tier_value == "tier2":
                chosen_tier = QueryTier.TIER2_RLM
            else:
                chosen_tier = default_tier
            
            precedent_info = {
                "status": result.precedent_lookup_status,
                "latency_ms": result.precedent_lookup_latency_ms,
                "precedents_considered": result.precedents_considered,
                "followed": result.precedent_followed,
                "deviated": result.deviated
            }
            
            return chosen_tier, precedent_info
            
        except Exception as e:
            logger.warning(f"Precedent lookup failed, using default tier: {e}")
            return default_tier, {"status": "error", "latency_ms": 0, "error": str(e)}
    
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
                self._set_tenant_context()
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
    
    def _is_impact_query(self, query_text: str) -> bool:
        """
        Detect if this is a blast radius / impact analysis query.
        
        These queries need precise directional filtering from the 3-step pipeline.
        """
        query_lower = query_text.lower()
        
        impact_patterns = [
            'blast radius',
            'if .* fails',
            'if .* goes down',
            'if .* is corrupted',
            'if .* is down',
            'what.*affected',
            'what.*impacted',
            r'\baffected\b.*\boutage\b',
            r'\boutage\b.*\baffected\b',
            r'\bwould be affected\b',
            r'\bservices are impacted\b',
            r'\bteams.*affected\b',
            'cascade',
            'downstream impact',
            'what depends on',
            'what relies on',
        ]
        
        import re
        for pattern in impact_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def _query_with_3step_pipeline(
        self,
        query_text: str,
        query_id: str,
        query_logger: QueryLogger,
        display_output: bool,
        save_to_log: bool
    ) -> Dict:
        """
        Process a query through the 3-step pipeline for precise directed retrieval.
        
        This pipeline is used for impact/blast radius queries where direction
        matters: we need to find INBOUND DEPENDS_ON relationships (what depends
        on the target entity), not all relationships.
        
        Steps:
        1. Query Interpretation (LLM) - Parse into structured QueryIntent
        2. Directed Retrieval (Code) - Precise graph traversal with paths
        3. Answer Synthesis (LLM) - Format results with cascade paths
        """
        from .models.context_bundle import create_bundle
        
        query_logger.log_event("3STEP_PIPELINE_START", {"query": query_text})
        
        try:
            pipeline = QueryPipeline(self.session, self.tenant_id)
            result: PipelineResult = pipeline.execute(query_text)
            
            if result.error:
                query_logger.log_error("3STEP_PIPELINE_ERROR", result.error)
                return {
                    "answer": f"Error processing query: {result.error}",
                    "confidence": 0.0,
                    "confidence_level": "very_low",
                    "error": True,
                    "error_message": result.error,
                    "query_tier": "tier1_3step",
                    "query_id": query_id,
                    "query_text": query_text
                }
            
            # Build response with cascade paths
            cascade_breakdown = result.step2_result.get_cascade_breakdown() if result.step2_result else {}
            cascade_paths = [p.to_dict() for p in result.step2_result.cascade_paths] if result.step2_result else []
            
            # Format answer with paths for display
            answer_with_paths = result.step3_answer or ""
            if cascade_paths:
                answer_with_paths += "\n\n**Impact Chains:**\n"
                for path_info in cascade_paths[:15]:
                    answer_with_paths += f"- {path_info['formatted']}\n"
                if len(cascade_paths) > 15:
                    answer_with_paths += f"- ... and {len(cascade_paths) - 15} more chains\n"
            
            confidence = result.step3_confidence
            confidence_level = "high" if confidence >= 0.7 else \
                              "medium" if confidence >= 0.4 else \
                              "low" if confidence >= 0.2 else "very_low"
            
            # Build a minimal bundle for logging
            bundle = create_bundle(query_text)
            bundle.retrieval_metadata["query_tier"] = "tier1_3step"
            bundle.retrieval_metadata["pipeline_result"] = result.to_dict()
            
            response = {
                "answer": answer_with_paths,
                "confidence": confidence,
                "confidence_level": confidence_level,
                "query_tier": "tier1_3step",
                "entity_found": result.step2_result.entity_found if result.step2_result else False,
                "entity_name": result.step2_result.entity_name if result.step2_result else None,
                "relationships_count": len(result.step2_result.relationships) if result.step2_result else 0,
                "affected_entities_count": len(result.step2_result.affected_entities) if result.step2_result else 0,
                "cascade_breakdown": cascade_breakdown,
                "cascade_paths": cascade_paths,
                "evidence_chain": [{
                    "type": "graph_traversal",
                    "description": f"Precise directional traversal: {result.step1_intent.direction} {result.step1_intent.relationship_types}",
                    "confidence": confidence,
                    "source": "3-Step Pipeline"
                }] if result.step1_intent else [],
                "pipeline_timing": {
                    "step1_interpretation_ms": result.step1_duration_ms,
                    "step2_retrieval_ms": result.step2_duration_ms,
                    "step3_synthesis_ms": result.step3_duration_ms,
                    "total_ms": result.total_duration_ms
                },
                "query_id": query_id,
                "query_text": query_text,
                "context_bundle": bundle.to_dict()
            }
            
            query_logger.log_event("3STEP_PIPELINE_COMPLETE", {
                "confidence": confidence,
                "relationships": response["relationships_count"],
                "affected_entities": response["affected_entities_count"],
                "cascade_paths": len(cascade_paths),
                "total_ms": result.total_duration_ms
            })
            
            if display_output:
                logger.info(f"3-Step Pipeline Answer (confidence: {confidence:.2f}):")
                logger.info(answer_with_paths[:500])
            
            if save_to_log:
                self._save_query_log(query_id, query_text, bundle, response)
            
            summary = query_logger.log_complete(success=True, final_confidence=confidence)
            response["query_log"] = summary
            
            return response
            
        except Exception as e:
            query_logger.log_error("3STEP_PIPELINE_ERROR", str(e))
            logger.exception(f"3-step pipeline error: {e}")
            
            try:
                self.session.rollback()
                self._set_tenant_context()
            except Exception:
                pass
            
            return {
                "answer": f"Error in 3-step pipeline: {str(e)}",
                "confidence": 0,
                "confidence_level": "very_low",
                "error": True,
                "error_message": str(e),
                "query_tier": "tier1_3step",
                "query_id": query_id,
                "query_text": query_text
            }
    
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
                tenant_id=uuid.UUID(self.tenant_id) if self.tenant_id else None,
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
            self._set_tenant_context()
            logger.debug(f"Query log saved: {query_id}")
        except Exception as e:
            logger.error(f"Failed to save query log: {e}")
            try:
                self.session.rollback()
                self._set_tenant_context()
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
        self._set_tenant_context()
        self.retrieval = RetrievalAgent(self.session, tenant_id=self.tenant_id)
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
        SECURITY: Must filter by tenant_id to prevent cross-tenant data leakage.
        """
        from .models.schema import Entity, LifecycleState
        from uuid import UUID as PyUUID
        
        try:
            base_query = self.session.query(Entity.name).filter(
                Entity.lifecycle_state.in_([LifecycleState.TRUSTED, LifecycleState.STAGING])
            )
            
            # CRITICAL: Add tenant filtering to prevent cross-tenant leakage
            if self.tenant_id:
                try:
                    tenant_uuid = PyUUID(self.tenant_id) if isinstance(self.tenant_id, str) else self.tenant_id
                    base_query = base_query.filter(Entity.tenant_id == tenant_uuid)
                except (ValueError, TypeError):
                    pass  # Invalid tenant_id format, skip filter
            
            all_entities = base_query.distinct().limit(500).all()
            
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
