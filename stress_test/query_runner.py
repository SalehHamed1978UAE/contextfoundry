"""
Query Runner

Executes queries against Context Foundry with:
- Parallel query execution
- Latency tracking
- Consistency analysis
- Error categorization
"""
import time
import json
import requests
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from stress_test.config import StressTestConfig
from stress_test.query_generator import GeneratedQuery

logger = logging.getLogger(__name__)

@dataclass
class QueryResult:
    query_id: str
    query: str
    pattern: str
    success: bool
    latency_ms: float
    response: Optional[Dict] = None
    answer: Optional[str] = None
    confidence: Optional[float] = None
    entity_found: bool = False
    error: Optional[str] = None
    is_adversarial: bool = False
    expected_exists: bool = True
    hallucination_detected: bool = False
    metadata: Dict = field(default_factory=dict)

class QueryRunner:
    def __init__(self, config: StressTestConfig):
        self.config = config
        self.base_url = config.base_url
        self.session = requests.Session()
        self.results = []
        self.lock = threading.Lock()
        
        self.total_queries = 0
        self.successful_queries = 0
        self.failed_queries = 0
        self.hallucination_count = 0
        self.correct_refusals = 0
        
        self.latencies = []
        self.consistency_results = {}
        self.error_categories = {}
        
    def execute_query(self, query: GeneratedQuery) -> QueryResult:
        """Execute a single query"""
        start_time = time.time()
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/query",
                json={"query": query.query},
                timeout=60
            )
            
            latency = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                with self.lock:
                    self.failed_queries += 1
                    self._categorize_error(f"HTTP_{response.status_code}")
                return QueryResult(
                    query_id=query.query_id,
                    query=query.query,
                    pattern=query.pattern,
                    success=False,
                    latency_ms=latency,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                    is_adversarial=query.is_adversarial,
                    expected_exists=query.expected_exists
                )
            
            data = response.json()
            answer = data.get('answer', '')
            confidence = data.get('confidence', 0)
            
            entity_found = not any(phrase in answer.lower() for phrase in [
                "don't have information",
                "no information",
                "not found",
                "cannot find",
                "doesn't exist",
                "does not exist",
                "unknown entity",
                "no entity"
            ])
            
            hallucination = False
            if not query.expected_exists and entity_found and confidence > 0.5:
                hallucination = True
                with self.lock:
                    self.hallucination_count += 1
            
            if not query.expected_exists and not entity_found:
                with self.lock:
                    self.correct_refusals += 1
            
            with self.lock:
                self.successful_queries += 1
                self.latencies.append(latency)
            
            result = QueryResult(
                query_id=query.query_id,
                query=query.query,
                pattern=query.pattern,
                success=True,
                latency_ms=latency,
                response=data,
                answer=answer[:500],
                confidence=confidence,
                entity_found=entity_found,
                is_adversarial=query.is_adversarial,
                expected_exists=query.expected_exists,
                hallucination_detected=hallucination,
                metadata={
                    "consistency_group": query.consistency_group,
                    "uncertainty": data.get('uncertainty', {})
                }
            )
            
            if query.consistency_group:
                self._record_consistency(query.consistency_group, result)
            
            return result
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            with self.lock:
                self.failed_queries += 1
                self._categorize_error(type(e).__name__)
            return QueryResult(
                query_id=query.query_id,
                query=query.query,
                pattern=query.pattern,
                success=False,
                latency_ms=latency,
                error=str(e),
                is_adversarial=query.is_adversarial,
                expected_exists=query.expected_exists
            )
    
    def _categorize_error(self, error_type: str):
        """Categorize errors for analysis"""
        self.error_categories[error_type] = self.error_categories.get(error_type, 0) + 1
    
    def _record_consistency(self, group_id: str, result: QueryResult):
        """Record result for consistency analysis"""
        if group_id not in self.consistency_results:
            self.consistency_results[group_id] = []
        self.consistency_results[group_id].append({
            "query_id": result.query_id,
            "answer": result.answer,
            "confidence": result.confidence,
            "entity_found": result.entity_found
        })
    
    def run_batch(self, queries: List[GeneratedQuery]) -> List[QueryResult]:
        """Run a batch of queries in parallel"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.parallel_queries) as executor:
            future_to_query = {
                executor.submit(self.execute_query, q): q 
                for q in queries
            }
            
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    result = future.result()
                    results.append(result)
                    with self.lock:
                        self.total_queries += 1
                except Exception as e:
                    results.append(QueryResult(
                        query_id=query.query_id,
                        query=query.query,
                        pattern=query.pattern,
                        success=False,
                        latency_ms=0,
                        error=str(e),
                        is_adversarial=query.is_adversarial,
                        expected_exists=query.expected_exists
                    ))
                    with self.lock:
                        self.total_queries += 1
                        self.failed_queries += 1
        
        self.results.extend(results)
        return results
    
    def get_stats(self) -> Dict:
        """Get query execution statistics"""
        with self.lock:
            return {
                "total_queries": self.total_queries,
                "successful_queries": self.successful_queries,
                "failed_queries": self.failed_queries,
                "success_rate": self.successful_queries / max(1, self.total_queries),
                "hallucinations": self.hallucination_count,
                "correct_refusals": self.correct_refusals,
                "hallucination_rate": self.hallucination_count / max(1, self.total_queries)
            }
    
    def get_latency_stats(self) -> Dict:
        """Get latency statistics"""
        with self.lock:
            if not self.latencies:
                return {}
            
            sorted_lat = sorted(self.latencies)
            n = len(sorted_lat)
            
            def percentile(p):
                k = (n - 1) * p / 100
                f = int(k)
                c = f + 1 if f + 1 < n else f
                return sorted_lat[f] + (sorted_lat[c] - sorted_lat[f]) * (k - f)
            
            return {
                "p50_ms": percentile(50),
                "p95_ms": percentile(95),
                "p99_ms": percentile(99),
                "min_ms": sorted_lat[0],
                "max_ms": sorted_lat[-1],
                "avg_ms": sum(sorted_lat) / n
            }
    
    def get_pattern_stats(self) -> Dict:
        """Get stats broken down by query pattern"""
        pattern_stats = {}
        
        for result in self.results:
            pattern = result.pattern
            if pattern not in pattern_stats:
                pattern_stats[pattern] = {
                    "total": 0,
                    "successful": 0,
                    "latencies": []
                }
            
            pattern_stats[pattern]["total"] += 1
            if result.success:
                pattern_stats[pattern]["successful"] += 1
                pattern_stats[pattern]["latencies"].append(result.latency_ms)
        
        for pattern, stats in pattern_stats.items():
            stats["success_rate"] = stats["successful"] / max(1, stats["total"])
            if stats["latencies"]:
                stats["avg_latency_ms"] = sum(stats["latencies"]) / len(stats["latencies"])
            del stats["latencies"]
        
        return pattern_stats
    
    def analyze_consistency(self) -> Dict:
        """Analyze consistency across rephrased queries"""
        if not self.consistency_results:
            return {"groups_analyzed": 0}
        
        consistency_scores = []
        
        for group_id, results in self.consistency_results.items():
            if len(results) < 2:
                continue
            
            entity_found_values = [r["entity_found"] for r in results]
            confidence_values = [r["confidence"] for r in results if r["confidence"] is not None]
            
            entity_consistency = len(set(entity_found_values)) == 1
            
            if confidence_values:
                conf_range = max(confidence_values) - min(confidence_values)
                conf_consistency = 1 - (conf_range / 1.0)
            else:
                conf_consistency = 0
            
            consistency_scores.append({
                "group_id": group_id,
                "entity_consistent": entity_consistency,
                "confidence_consistency": conf_consistency,
                "num_queries": len(results)
            })
        
        if not consistency_scores:
            return {"groups_analyzed": 0}
        
        return {
            "groups_analyzed": len(consistency_scores),
            "entity_consistency_rate": sum(1 for s in consistency_scores if s["entity_consistent"]) / len(consistency_scores),
            "avg_confidence_consistency": sum(s["confidence_consistency"] for s in consistency_scores) / len(consistency_scores),
            "details": consistency_scores[:10]
        }
    
    def get_error_breakdown(self) -> Dict:
        """Get breakdown of error types"""
        with self.lock:
            return dict(self.error_categories)
