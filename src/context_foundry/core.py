"""
Context Foundry Core - Main orchestration layer.
Coordinates all agents and memory layers for query processing.
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


class ContextFoundry:
    """
    Main orchestration class for the Context Foundry system.
    Coordinates tri-memory architecture for intelligent query processing.
    """
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()
        
        self.retrieval = RetrievalAgent(self.session)
        self.reasoning = ReasoningAgent()
        self.validation = ValidationAgent(self.session)
        
        self.is_initialized = False
        
        logger.info("ContextFoundry core initialized")
    
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
        as_of_date: str = None
    ) -> Dict:
        """
        Process a query through the full Context Foundry pipeline.
        
        Pipeline:
        1. Retrieval Agent builds ContextBundle from all three memory layers
        2. Reasoning Agent generates response with LLM
        3. Validation Agent checks response against rules
        4. Response returned with full provenance
        
        Args:
            as_of_date: Optional ISO date string for temporal queries.
                        If provided, returns knowledge graph state as of this date.
        """
        query_id = str(uuid.uuid4())
        query_logger = QueryLogger(query_id, query_text)
        
        try:
            query_logger.log_event("PIPELINE_START", {"query": query_text, "as_of_date": as_of_date})
            
            bundle = self.retrieval.build_context_bundle(
                query_text,
                query_logger=query_logger,
                as_of_date=as_of_date
            )
            
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
