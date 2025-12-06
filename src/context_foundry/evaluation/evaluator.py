"""
Blind Evaluation Framework for Context Foundry.

Compares Context Foundry (tri-memory) vs GraphRAG baseline:
- Runs same queries through both systems
- Collects responses without revealing source
- Measures factual accuracy, provenance, confidence calibration
- Stores results for human review
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid
import json
import random

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Float, Boolean, DateTime, JSON, Text, Integer
from sqlalchemy.dialects.postgresql import UUID

from ..models.schema import Base, get_session
from .query_set import EvaluationQuery, QuerySet, QueryCategory
from .graphrag_baseline import GraphRAGBaseline, GraphRAGResponse


class SystemType(str, Enum):
    CONTEXT_FOUNDRY = "context_foundry"
    GRAPHRAG_BASELINE = "graphrag_baseline"


@dataclass
class EvaluationResponse:
    """A single response from one system."""
    system: SystemType
    query_id: str
    query_text: str
    answer: str
    latency_ms: float
    context_size: int
    
    confidence: Optional[float] = None
    evidence_chain: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "system": self.system.value,
            "query_id": self.query_id,
            "query_text": self.query_text,
            "answer": self.answer,
            "latency_ms": self.latency_ms,
            "context_size": self.context_size,
            "confidence": self.confidence,
            "evidence_chain": self.evidence_chain,
        }


@dataclass
class BlindPair:
    """A pair of responses (A/B) for blind comparison."""
    pair_id: str
    query: EvaluationQuery
    response_a: EvaluationResponse
    response_b: EvaluationResponse
    
    a_is_context_foundry: bool = True
    
    human_preference: Optional[str] = None
    human_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    
    def to_dict(self, reveal_source: bool = False) -> Dict:
        """Convert to dict, optionally revealing which system produced each response."""
        result = {
            "pair_id": self.pair_id,
            "query": self.query.to_dict(),
            "response_a": self._blind_response(self.response_a),
            "response_b": self._blind_response(self.response_b),
            "human_preference": self.human_preference,
            "human_notes": self.human_notes,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
        }
        
        if reveal_source:
            result["source_mapping"] = {
                "A": "context_foundry" if self.a_is_context_foundry else "graphrag_baseline",
                "B": "graphrag_baseline" if self.a_is_context_foundry else "context_foundry",
            }
            result["response_a_full"] = self.response_a.to_dict()
            result["response_b_full"] = self.response_b.to_dict()
        
        return result
    
    def _blind_response(self, response: EvaluationResponse) -> Dict:
        """Return response without revealing system source."""
        return {
            "answer": response.answer,
            "latency_ms": response.latency_ms,
            "context_size": response.context_size,
        }
    
    def get_blind_responses(self) -> Tuple[Dict, Dict]:
        """Get responses without revealing which system produced them."""
        return (
            {"label": "A", "answer": self.response_a.answer, "latency_ms": self.response_a.latency_ms},
            {"label": "B", "answer": self.response_b.answer, "latency_ms": self.response_b.latency_ms},
        )


@dataclass
class EvaluationMetrics:
    """Metrics comparing the two systems."""
    total_queries: int = 0
    
    cf_wins: int = 0
    graphrag_wins: int = 0
    ties: int = 0
    
    cf_avg_latency_ms: float = 0.0
    graphrag_avg_latency_ms: float = 0.0
    
    cf_avg_confidence: float = 0.0
    graphrag_avg_confidence: float = 0.0
    
    cf_factual_accuracy: float = 0.0
    graphrag_factual_accuracy: float = 0.0
    
    cf_provenance_quality: float = 0.0
    graphrag_provenance_quality: float = 0.0
    
    by_category: Dict[str, Dict] = field(default_factory=dict)
    by_difficulty: Dict[str, Dict] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "total_queries": self.total_queries,
            "cf_wins": self.cf_wins,
            "graphrag_wins": self.graphrag_wins,
            "ties": self.ties,
            "cf_win_rate": self.cf_wins / self.total_queries if self.total_queries > 0 else 0,
            "cf_avg_latency_ms": self.cf_avg_latency_ms,
            "graphrag_avg_latency_ms": self.graphrag_avg_latency_ms,
            "cf_avg_confidence": self.cf_avg_confidence,
            "graphrag_avg_confidence": self.graphrag_avg_confidence,
            "cf_factual_accuracy": self.cf_factual_accuracy,
            "graphrag_factual_accuracy": self.graphrag_factual_accuracy,
            "cf_provenance_quality": self.cf_provenance_quality,
            "graphrag_provenance_quality": self.graphrag_provenance_quality,
            "by_category": self.by_category,
            "by_difficulty": self.by_difficulty,
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result."""
    evaluation_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    total_queries: int = 0
    completed_queries: int = 0
    
    pairs: List[BlindPair] = field(default_factory=list)
    metrics: Optional[EvaluationMetrics] = None
    
    def to_dict(self) -> Dict:
        return {
            "evaluation_id": self.evaluation_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_queries": self.total_queries,
            "completed_queries": self.completed_queries,
            "pairs": [p.to_dict() for p in self.pairs],
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


class BlindEvaluator:
    """
    Runs blind evaluation comparing Context Foundry vs GraphRAG baseline.
    
    Process:
    1. Load query set
    2. Run each query through both systems
    3. Randomize A/B ordering to prevent bias
    4. Collect human preferences
    5. Calculate metrics
    """
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()
        self.query_set = QuerySet()
        self.graphrag = GraphRAGBaseline(self.session)
        self._context_foundry = None
    
    def _get_context_foundry(self):
        """Lazy load Context Foundry to avoid circular imports."""
        if self._context_foundry is None:
            from ..core import ContextFoundry
            self._context_foundry = ContextFoundry(self.session)
        return self._context_foundry
    
    def run_evaluation(
        self,
        query_ids: Optional[List[str]] = None,
        categories: Optional[List[QueryCategory]] = None,
        sample_size: Optional[int] = None,
    ) -> EvaluationResult:
        """
        Run blind evaluation on specified queries.
        
        Args:
            query_ids: Specific query IDs to run (optional)
            categories: Filter by categories (optional)
            sample_size: Random sample size (optional)
            
        Returns:
            EvaluationResult with all pairs
        """
        evaluation_id = str(uuid.uuid4())[:8]
        result = EvaluationResult(
            evaluation_id=evaluation_id,
            started_at=datetime.utcnow(),
        )
        
        queries = self._select_queries(query_ids, categories, sample_size)
        result.total_queries = len(queries)
        
        for query in queries:
            try:
                pair = self._run_query_pair(query)
                result.pairs.append(pair)
                result.completed_queries += 1
            except Exception as e:
                print(f"Error running query {query.id}: {e}")
        
        result.completed_at = datetime.utcnow()
        return result
    
    def run_single_query(self, query_id: str) -> Optional[BlindPair]:
        """Run a single query through both systems."""
        query = next((q for q in self.query_set.queries if q.id == query_id), None)
        if not query:
            return None
        return self._run_query_pair(query)
    
    def _select_queries(
        self,
        query_ids: Optional[List[str]],
        categories: Optional[List[QueryCategory]],
        sample_size: Optional[int],
    ) -> List[EvaluationQuery]:
        """Select queries based on criteria."""
        queries = self.query_set.queries
        
        if query_ids:
            queries = [q for q in queries if q.id in query_ids]
        
        if categories:
            queries = [q for q in queries if q.category in categories]
        
        if sample_size and sample_size < len(queries):
            queries = random.sample(queries, sample_size)
        
        return queries
    
    def _run_query_pair(self, query: EvaluationQuery) -> BlindPair:
        """Run a query through both systems and create a blind pair."""
        pair_id = str(uuid.uuid4())[:8]
        
        cf_response = self._run_context_foundry(query)
        graphrag_response = self._run_graphrag(query)
        
        a_is_cf = random.choice([True, False])
        
        if a_is_cf:
            response_a = cf_response
            response_b = graphrag_response
        else:
            response_a = graphrag_response
            response_b = cf_response
        
        return BlindPair(
            pair_id=pair_id,
            query=query,
            response_a=response_a,
            response_b=response_b,
            a_is_context_foundry=a_is_cf,
        )
    
    def _run_context_foundry(self, query: EvaluationQuery) -> EvaluationResponse:
        """Run query through Context Foundry."""
        start_time = datetime.utcnow()
        
        cf = self._get_context_foundry()
        result = cf.query(query.query_text, display_output=False, save_to_log=False)
        
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        evidence_chain = result.get("evidence_chain", [])
        
        raw_answer = result.get("answer", "")
        
        # Try to parse JSON string into dict
        if isinstance(raw_answer, str) and raw_answer.strip().startswith("{"):
            try:
                raw_answer = json.loads(raw_answer)
            except json.JSONDecodeError:
                pass
        
        if isinstance(raw_answer, dict):
            if "text" in raw_answer:
                answer = raw_answer["text"]
            elif "content" in raw_answer:
                answer = raw_answer["content"]
            elif "CONFIRMED IMPACT" in raw_answer or "confirmed_impact" in raw_answer:
                parts = []
                confirmed = raw_answer.get("CONFIRMED IMPACT", raw_answer.get("confirmed_impact", []))
                if confirmed:
                    parts.append("Confirmed Impact:")
                    for item in confirmed:
                        svc = item.get("service", item.get("name", "Unknown"))
                        desc = item.get("description", "")
                        conf = item.get("confidence")
                        conf_str = f" ({int(conf*100)}%)" if conf else ""
                        parts.append(f"  - {svc}{conf_str}: {desc}" if desc else f"  - {svc}{conf_str}")
                inferred = raw_answer.get("INFERRED IMPACT", raw_answer.get("inferred_impact", []))
                if inferred:
                    parts.append("\nInferred Impact:")
                    for item in inferred:
                        svc = item.get("service", item.get("name", "Unknown"))
                        inference = item.get("inference", "")
                        conf = item.get("confidence")
                        conf_str = f" ({int(conf*100)}%)" if conf else ""
                        parts.append(f"  - {svc}{conf_str}: {inference}" if inference else f"  - {svc}{conf_str}")
                boundary = raw_answer.get("KNOWLEDGE BOUNDARY", raw_answer.get("knowledge_boundary", []))
                if boundary:
                    parts.append("\nKnowledge Boundaries:")
                    for item in boundary:
                        parts.append(f"  - {item}" if isinstance(item, str) else f"  - {item}")
                answer = "\n".join(parts) if parts else json.dumps(raw_answer, indent=2)
            else:
                answer = json.dumps(raw_answer, indent=2)
        elif isinstance(raw_answer, list):
            answer = json.dumps(raw_answer, indent=2)
        else:
            answer = str(raw_answer) if raw_answer else ""
        
        return EvaluationResponse(
            system=SystemType.CONTEXT_FOUNDRY,
            query_id=query.id,
            query_text=query.query_text,
            answer=answer,
            latency_ms=latency,
            context_size=len(evidence_chain),
            confidence=result.get("confidence"),
            evidence_chain=evidence_chain,
        )
    
    def _run_graphrag(self, query: EvaluationQuery) -> EvaluationResponse:
        """Run query through GraphRAG baseline."""
        result = self.graphrag.query(query.query_text)
        
        return EvaluationResponse(
            system=SystemType.GRAPHRAG_BASELINE,
            query_id=query.id,
            query_text=query.query_text,
            answer=result.answer,
            latency_ms=result.latency_ms,
            context_size=result.context.to_dict()["total_items"],
            confidence=None,
            evidence_chain=[],
        )
    
    def calculate_metrics(self, result: EvaluationResult) -> EvaluationMetrics:
        """Calculate evaluation metrics from human preferences."""
        metrics = EvaluationMetrics(total_queries=len(result.pairs))
        
        cf_latencies = []
        graphrag_latencies = []
        cf_confidences = []
        
        for pair in result.pairs:
            if pair.a_is_context_foundry:
                cf_latencies.append(pair.response_a.latency_ms)
                graphrag_latencies.append(pair.response_b.latency_ms)
                if pair.response_a.confidence:
                    cf_confidences.append(pair.response_a.confidence)
            else:
                cf_latencies.append(pair.response_b.latency_ms)
                graphrag_latencies.append(pair.response_a.latency_ms)
                if pair.response_b.confidence:
                    cf_confidences.append(pair.response_b.confidence)
            
            if pair.human_preference:
                if pair.human_preference == "A":
                    if pair.a_is_context_foundry:
                        metrics.cf_wins += 1
                    else:
                        metrics.graphrag_wins += 1
                elif pair.human_preference == "B":
                    if pair.a_is_context_foundry:
                        metrics.graphrag_wins += 1
                    else:
                        metrics.cf_wins += 1
                else:
                    metrics.ties += 1
        
        if cf_latencies:
            metrics.cf_avg_latency_ms = sum(cf_latencies) / len(cf_latencies)
        if graphrag_latencies:
            metrics.graphrag_avg_latency_ms = sum(graphrag_latencies) / len(graphrag_latencies)
        if cf_confidences:
            metrics.cf_avg_confidence = sum(cf_confidences) / len(cf_confidences)
        
        result.metrics = metrics
        return metrics
    
    def record_preference(
        self,
        pair_id: str,
        preference: str,
        notes: str = "",
        reviewer: str = "anonymous",
        result: EvaluationResult = None,
    ) -> bool:
        """Record human preference for a blind pair."""
        if result is None:
            return False
        
        for pair in result.pairs:
            if pair.pair_id == pair_id:
                pair.human_preference = preference
                pair.human_notes = notes
                pair.reviewed_at = datetime.utcnow()
                pair.reviewed_by = reviewer
                return True
        
        return False
    
    def get_query_set_stats(self) -> Dict:
        """Get statistics about the query set."""
        return self.query_set.get_statistics()
    
    def cleanup(self):
        """Clean up resources."""
        if self.graphrag:
            self.graphrag.cleanup()
        if self._context_foundry:
            self._context_foundry.cleanup()
