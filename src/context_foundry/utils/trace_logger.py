"""Structured trace logging for query execution and debugging."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class QueryTrace:
    """Structured trace for a single query execution."""
    query_id: str
    question: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    intent: Optional[Dict[str, Any]] = None
    route: Optional[Dict[str, str]] = None
    kg_results: Optional[Dict[str, Any]] = None
    doc_results: Optional[Dict[str, Any]] = None
    synthesis: Optional[Dict[str, Any]] = None
    answer: Optional[Dict[str, Any]] = None
    evaluation: Optional[Dict[str, Any]] = None


class QueryTraceLogger:
    """Structured trace logging for query execution."""

    def __init__(self, query_id: str, question: str):
        self.trace = QueryTrace(query_id=query_id, question=question)

    def log_intent(self, query_type: str, entity: Optional[str] = None, 
                   target_type: Optional[str] = None, confidence: float = 0.0):
        """Log the interpreted query intent."""
        self.trace.intent = {
            "query_type": query_type,
            "entity": entity,
            "target_type": target_type,
            "confidence": confidence
        }
        logger.info(f"[TRACE:{self.trace.query_id}] Intent: {query_type} for '{entity}' (conf={confidence:.2f})")

    def log_route(self, route: str, reason: str):
        """Log the routing decision."""
        self.trace.route = {"path": route, "reason": reason}
        logger.info(f"[TRACE:{self.trace.query_id}] Route: {route} ({reason})")

    def log_kg_results(self, entities: List, relationships: List):
        """Log knowledge graph retrieval results."""
        entity_names = []
        for e in entities[:10]:
            if hasattr(e, 'name'):
                entity_names.append(e.name)
            elif isinstance(e, dict):
                entity_names.append(e.get('name', str(e)[:30]))
            else:
                entity_names.append(str(e)[:30])
        
        rel_strs = []
        for r in relationships[:10]:
            if hasattr(r, 'source_name'):
                rel_strs.append(f"{r.source_name}->{r.relationship_type}->{r.target_name}")
            elif isinstance(r, dict):
                rel_strs.append(f"{r.get('source', '?')}->{r.get('type', '?')}->{r.get('target', '?')}")
            else:
                rel_strs.append(str(r)[:50])
        
        self.trace.kg_results = {
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "entities": entity_names,
            "relationships": rel_strs
        }
        logger.info(f"[TRACE:{self.trace.query_id}] KG: {len(entities)} entities, {len(relationships)} rels")

    def log_doc_results(self, chunks: List, sources: Optional[List[str]] = None):
        """Log document retrieval results."""
        if sources is None:
            sources = []
            for c in chunks[:5]:
                if hasattr(c, 'source'):
                    sources.append(c.source)
                elif isinstance(c, dict):
                    sources.append(c.get('source', c.get('filename', 'unknown')))
        
        self.trace.doc_results = {
            "chunk_count": len(chunks),
            "sources": sources[:10],
            "top_scores": [getattr(c, 'score', c.get('score', 0) if isinstance(c, dict) else 0) for c in chunks[:5]]
        }
        logger.info(f"[TRACE:{self.trace.query_id}] Docs: {len(chunks)} chunks from {sources[:3]}")

    def log_synthesis(self, method: str, prompt_tokens: int = 0, 
                      response_tokens: int = 0, latency_ms: int = 0):
        """Log synthesis/LLM call details."""
        self.trace.synthesis = {
            "method": method,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "latency_ms": latency_ms
        }
        logger.info(f"[TRACE:{self.trace.query_id}] Synthesis: {method} ({latency_ms}ms)")

    def log_answer(self, answer: str, confidence: float = 0.0, 
                   sources: Optional[List[str]] = None):
        """Log the final answer."""
        self.trace.answer = {
            "text": answer[:500],
            "confidence": confidence,
            "sources": sources or [],
            "length": len(answer)
        }
        logger.info(f"[TRACE:{self.trace.query_id}] Answer: {answer[:80]}... (conf={confidence:.2f})")

    def log_evaluation(self, passed: bool, match_type: str, 
                       expected: Optional[str] = None, reason: Optional[str] = None):
        """Log evaluation result."""
        self.trace.evaluation = {
            "passed": passed,
            "match_type": match_type,
            "expected": expected[:100] if expected else None,
            "reason": reason
        }
        status = 'PASS' if passed else 'FAIL'
        logger.info(f"[TRACE:{self.trace.query_id}] Eval: {status} ({match_type})")

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary."""
        return asdict(self.trace)

    def save(self, output_dir: str = "test_results/traces"):
        """Save trace to file for analysis."""
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        
        filename = f"trace_{self.trace.query_id}.json"
        filepath = path / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        
        logger.debug(f"[TRACE:{self.trace.query_id}] Saved to {filepath}")
        return filepath


class TraceAggregator:
    """Aggregate multiple traces for analysis."""
    
    def __init__(self):
        self.traces: List[QueryTrace] = []
    
    def add(self, tracer: QueryTraceLogger):
        """Add a trace to the aggregator."""
        self.traces.append(tracer.trace)
    
    def summary(self) -> Dict[str, Any]:
        """Generate summary statistics."""
        if not self.traces:
            return {"total": 0}
        
        passed = sum(1 for t in self.traces if t.evaluation and t.evaluation.get('passed'))
        failed = len(self.traces) - passed
        
        route_counts = {}
        match_types = {}
        failure_reasons = {}
        
        for t in self.traces:
            if t.route:
                route = t.route.get('path', 'unknown')
                route_counts[route] = route_counts.get(route, 0) + 1
            
            if t.evaluation:
                mt = t.evaluation.get('match_type', 'unknown')
                match_types[mt] = match_types.get(mt, 0) + 1
                
                if not t.evaluation.get('passed'):
                    reason = t.evaluation.get('reason', 'unknown')
                    failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        
        return {
            "total": len(self.traces),
            "passed": passed,
            "failed": failed,
            "accuracy": passed / len(self.traces) if self.traces else 0,
            "routes": route_counts,
            "match_types": match_types,
            "failure_reasons": failure_reasons
        }
    
    def save_summary(self, output_path: str = "test_results/trace_summary.json"):
        """Save summary to file."""
        summary = self.summary()
        summary['traces'] = [asdict(t) for t in self.traces]
        
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return output_path
