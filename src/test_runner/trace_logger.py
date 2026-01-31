"""
Per-question trace logging for retrieval analysis.

Captures:
- Retrieved files with semantic scores
- Query type classification
- Evaluator rule that fired
- Time taken
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class QuestionTraceLogger:
    """Log retrieval traces for each question in a test run."""
    
    def __init__(self, output_dir: Path, corpus_name: str, run_id: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        safe_name = corpus_name.lower().replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_suffix = run_id[:8] if run_id else timestamp
        
        self.trace_file = self.output_dir / f"{safe_name}_traces_{run_suffix}.jsonl"
        self.summary_file = self.output_dir / f"{safe_name}_trace_summary_{run_suffix}.json"
        
        self.traces: List[Dict] = []
        self.stats = {
            "total_questions": 0,
            "avg_chunks_retrieved": 0,
            "avg_semantic_score": 0,
            "query_type_distribution": {},
            "evaluator_rule_distribution": {},
            "low_score_queries": 0
        }
    
    def log_question(
        self,
        question_id: int,
        question_text: str,
        expected_answer: str,
        actual_answer: str,
        passed: bool,
        match_type: str,
        retrieval_data: Dict[str, Any],
        duration_ms: int
    ):
        """Log a single question's trace data.
        
        Args:
            question_id: Question number
            question_text: The question asked
            expected_answer: Ground truth
            actual_answer: Model's answer
            passed: Whether it passed evaluation
            match_type: Which evaluator rule matched
            retrieval_data: Data from API including chunks, scores, query_type
            duration_ms: Query time in milliseconds
        """
        chunks = retrieval_data.get('chunk_sources', [])
        tool_calls = retrieval_data.get('tool_calls', [])
        
        semantic_scores = []
        retrieved_files = []
        
        for chunk in chunks:
            if isinstance(chunk, dict):
                doc_name = chunk.get('document', chunk.get('doc_name', 'unknown'))
                score = chunk.get('similarity', chunk.get('score', 0))
                retrieved_files.append(doc_name)
                if score:
                    semantic_scores.append(float(score))
            elif isinstance(chunk, str):
                retrieved_files.append(chunk)
        
        for tool_call in tool_calls:
            if tool_call.get('tool') == 'search_documents':
                results = tool_call.get('result', {})
                if isinstance(results, dict):
                    for chunk in results.get('chunks', []):
                        doc = chunk.get('document', 'unknown')
                        if doc not in retrieved_files:
                            retrieved_files.append(doc)
                        score = chunk.get('similarity')
                        if score:
                            semantic_scores.append(float(score))
        
        avg_score = sum(semantic_scores) / len(semantic_scores) if semantic_scores else 0.0
        max_score = max(semantic_scores) if semantic_scores else 0.0
        min_score = min(semantic_scores) if semantic_scores else 0.0
        
        query_type = retrieval_data.get('query_type', 'unknown')
        if query_type == 'unknown':
            for tool_call in tool_calls:
                if 'query_type' in tool_call:
                    query_type = tool_call['query_type']
                    break
        
        trace = {
            "q_id": question_id,
            "question": question_text[:200],
            "expected": expected_answer[:200],
            "actual": actual_answer[:500] if actual_answer else "",
            "passed": passed,
            "match_type": match_type,
            "query_type": query_type,
            "retrieval": {
                "files": retrieved_files[:10],
                "file_count": len(retrieved_files),
                "chunk_count": len(chunks),
                "semantic_scores": {
                    "avg": round(avg_score, 4),
                    "max": round(max_score, 4),
                    "min": round(min_score, 4)
                }
            },
            "tool_calls": [
                {"tool": tc.get('tool'), "duration_ms": tc.get('duration_ms', 0)} 
                for tc in tool_calls
            ],
            "duration_ms": duration_ms,
            "confidence": retrieval_data.get('confidence', 0),
            "gate_blocked": retrieval_data.get('gate_blocked', False),
            "gate_name": retrieval_data.get('gate_name'),
            "timestamp": datetime.now().isoformat()
        }
        
        self.traces.append(trace)
        self._update_stats(trace)
        
        with open(self.trace_file, 'a') as f:
            f.write(json.dumps(trace) + '\n')
    
    def _update_stats(self, trace: Dict):
        """Update running statistics."""
        self.stats["total_questions"] += 1
        
        qt = trace.get("query_type", "unknown")
        self.stats["query_type_distribution"][qt] = \
            self.stats["query_type_distribution"].get(qt, 0) + 1
        
        mt = trace.get("match_type", "unknown")
        self.stats["evaluator_rule_distribution"][mt] = \
            self.stats["evaluator_rule_distribution"].get(mt, 0) + 1
        
        avg_score = trace["retrieval"]["semantic_scores"]["avg"]
        if avg_score < 0.4:
            self.stats["low_score_queries"] += 1
        
        n = self.stats["total_questions"]
        old_avg_score = self.stats["avg_semantic_score"]
        self.stats["avg_semantic_score"] = old_avg_score + (avg_score - old_avg_score) / n
        
        chunk_count = trace["retrieval"]["chunk_count"]
        old_avg_chunks = self.stats["avg_chunks_retrieved"]
        self.stats["avg_chunks_retrieved"] = old_avg_chunks + (chunk_count - old_avg_chunks) / n
    
    def finalize(self) -> Dict:
        """Save summary and return stats."""
        summary = {
            "run_timestamp": datetime.now().isoformat(),
            "trace_file": str(self.trace_file),
            "stats": self.stats,
            "low_score_questions": [
                {"q_id": t["q_id"], "question": t["question"][:80], "avg_score": t["retrieval"]["semantic_scores"]["avg"]}
                for t in self.traces
                if t["retrieval"]["semantic_scores"]["avg"] < 0.4
            ],
            "failures_by_type": {}
        }
        
        for trace in self.traces:
            if not trace["passed"]:
                mt = trace["match_type"]
                if mt not in summary["failures_by_type"]:
                    summary["failures_by_type"][mt] = []
                summary["failures_by_type"][mt].append({
                    "q_id": trace["q_id"],
                    "question": trace["question"][:60],
                    "expected": trace["expected"][:40],
                    "actual": trace["actual"][:40],
                    "files_retrieved": trace["retrieval"]["files"][:3]
                })
        
        with open(self.summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary
