"""
Metrics Collector

Collects and analyzes all metrics:
- Accuracy sampling with verification
- Confidence calibration analysis
- Latency percentiles
- Error categorization
- Hourly trends
"""
import time
import json
import psutil
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import threading

from stress_test.config import StressTestConfig
from stress_test.ingestion_runner import IngestionResult
from stress_test.query_runner import QueryResult

logger = logging.getLogger(__name__)

@dataclass
class HourlySnapshot:
    hour: int
    timestamp: str
    documents_ingested: int
    documents_failed: int
    entities_extracted: int
    relationships_extracted: int
    queries_executed: int
    queries_failed: int
    hallucinations: int
    correct_refusals: int
    avg_extraction_latency_ms: float
    avg_query_latency_ms: float
    memory_usage_mb: float
    cpu_percent: float
    errors: Dict = field(default_factory=dict)

class MetricsCollector:
    def __init__(self, config: StressTestConfig):
        self.config = config
        self.start_time = time.time()
        self.lock = threading.Lock()
        
        self.hourly_snapshots = []
        self.current_hour = 0
        
        self.all_ingestion_results = []
        self.all_query_results = []
        
        self.confidence_buckets = {
            "0.0-0.2": {"total": 0, "correct": 0},
            "0.2-0.4": {"total": 0, "correct": 0},
            "0.4-0.6": {"total": 0, "correct": 0},
            "0.6-0.8": {"total": 0, "correct": 0},
            "0.8-1.0": {"total": 0, "correct": 0}
        }
        
        self.failure_modes = {}
        self.slowest_operations = []
        
    def record_ingestion_results(self, results: List[IngestionResult]):
        """Record ingestion results"""
        with self.lock:
            self.all_ingestion_results.extend(results)
            
            for result in results:
                if result.success:
                    self._record_slow_operation("extraction", result.extraction_time_ms, result.doc_id)
                else:
                    self._record_failure(result.error or "Unknown ingestion error")
    
    def record_query_results(self, results: List[QueryResult]):
        """Record query results"""
        with self.lock:
            self.all_query_results.extend(results)
            
            for result in results:
                if result.success:
                    self._record_slow_operation("query", result.latency_ms, result.query_id)
                    self._update_confidence_calibration(result)
                else:
                    self._record_failure(result.error or "Unknown query error")
    
    def _record_failure(self, error_message: str):
        """Categorize and count failure modes"""
        category = self._categorize_failure(error_message)
        self.failure_modes[category] = self.failure_modes.get(category, 0) + 1
    
    def _categorize_failure(self, error_message: str) -> str:
        """Categorize error message into failure mode"""
        error_lower = error_message.lower()
        
        if "timeout" in error_lower:
            return "Timeout"
        elif "connection" in error_lower:
            return "Connection Error"
        elif "500" in error_lower or "internal server" in error_lower:
            return "Internal Server Error"
        elif "400" in error_lower or "bad request" in error_lower:
            return "Bad Request"
        elif "404" in error_lower or "not found" in error_lower:
            return "Not Found"
        elif "memory" in error_lower or "oom" in error_lower:
            return "Memory Error"
        elif "database" in error_lower or "sql" in error_lower:
            return "Database Error"
        elif "json" in error_lower or "parse" in error_lower:
            return "Parse Error"
        elif "extraction" in error_lower:
            return "Extraction Error"
        else:
            return "Other"
    
    def _record_slow_operation(self, op_type: str, latency_ms: float, op_id: str):
        """Track slowest operations"""
        self.slowest_operations.append({
            "type": op_type,
            "latency_ms": latency_ms,
            "id": op_id,
            "timestamp": datetime.now().isoformat()
        })
        
        self.slowest_operations.sort(key=lambda x: x["latency_ms"], reverse=True)
        self.slowest_operations = self.slowest_operations[:100]
    
    def _update_confidence_calibration(self, result: QueryResult):
        """Update confidence calibration buckets"""
        if result.confidence is None:
            return
        
        conf = result.confidence
        bucket = None
        if conf < 0.2:
            bucket = "0.0-0.2"
        elif conf < 0.4:
            bucket = "0.2-0.4"
        elif conf < 0.6:
            bucket = "0.4-0.6"
        elif conf < 0.8:
            bucket = "0.6-0.8"
        else:
            bucket = "0.8-1.0"
        
        self.confidence_buckets[bucket]["total"] += 1
        
        if result.expected_exists == result.entity_found:
            self.confidence_buckets[bucket]["correct"] += 1
    
    def take_hourly_snapshot(self) -> HourlySnapshot:
        """Take a snapshot of current metrics"""
        with self.lock:
            hour = int((time.time() - self.start_time) / 3600)
            
            successful_ingestions = [r for r in self.all_ingestion_results if r.success]
            failed_ingestions = [r for r in self.all_ingestion_results if not r.success]
            
            successful_queries = [r for r in self.all_query_results if r.success]
            failed_queries = [r for r in self.all_query_results if not r.success]
            
            hallucinations = sum(1 for r in self.all_query_results if r.hallucination_detected)
            correct_refusals = sum(1 for r in self.all_query_results 
                                  if not r.expected_exists and not r.entity_found)
            
            avg_extraction_latency = 0
            if successful_ingestions:
                avg_extraction_latency = sum(r.extraction_time_ms for r in successful_ingestions) / len(successful_ingestions)
            
            avg_query_latency = 0
            if successful_queries:
                avg_query_latency = sum(r.latency_ms for r in successful_queries) / len(successful_queries)
            
            snapshot = HourlySnapshot(
                hour=hour,
                timestamp=datetime.now().isoformat(),
                documents_ingested=len(successful_ingestions),
                documents_failed=len(failed_ingestions),
                entities_extracted=sum(r.entities_extracted for r in successful_ingestions),
                relationships_extracted=sum(r.relationships_extracted for r in successful_ingestions),
                queries_executed=len(successful_queries),
                queries_failed=len(failed_queries),
                hallucinations=hallucinations,
                correct_refusals=correct_refusals,
                avg_extraction_latency_ms=avg_extraction_latency,
                avg_query_latency_ms=avg_query_latency,
                memory_usage_mb=psutil.Process().memory_info().rss / 1024 / 1024,
                cpu_percent=psutil.cpu_percent(),
                errors=dict(self.failure_modes)
            )
            
            self.hourly_snapshots.append(snapshot)
            return snapshot
    
    def get_confidence_calibration(self) -> Dict:
        """Get confidence calibration analysis"""
        with self.lock:
            calibration = {}
            for bucket, data in self.confidence_buckets.items():
                if data["total"] > 0:
                    accuracy = data["correct"] / data["total"]
                    expected = (float(bucket.split("-")[0]) + float(bucket.split("-")[1])) / 2
                    calibration[bucket] = {
                        "total": data["total"],
                        "correct": data["correct"],
                        "accuracy": accuracy,
                        "expected_accuracy": expected,
                        "calibration_error": abs(accuracy - expected)
                    }
            return calibration
    
    def get_top_failures(self, n: int = 10) -> List[Tuple[str, int]]:
        """Get top N failure modes"""
        with self.lock:
            sorted_failures = sorted(self.failure_modes.items(), key=lambda x: x[1], reverse=True)
            return sorted_failures[:n]
    
    def get_top_slow_operations(self, n: int = 10) -> List[Dict]:
        """Get top N slowest operations"""
        with self.lock:
            return self.slowest_operations[:n]
    
    def get_trends(self) -> Dict:
        """Analyze trends over time"""
        if len(self.hourly_snapshots) < 2:
            return {"message": "Not enough data for trend analysis"}
        
        with self.lock:
            snapshots = self.hourly_snapshots
            
            extraction_latencies = [s.avg_extraction_latency_ms for s in snapshots if s.avg_extraction_latency_ms > 0]
            query_latencies = [s.avg_query_latency_ms for s in snapshots if s.avg_query_latency_ms > 0]
            memory_usage = [s.memory_usage_mb for s in snapshots]
            
            def trend_direction(values):
                if len(values) < 2:
                    return "stable"
                first_half = sum(values[:len(values)//2]) / (len(values)//2)
                second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
                if second_half > first_half * 1.1:
                    return "increasing"
                elif second_half < first_half * 0.9:
                    return "decreasing"
                return "stable"
            
            return {
                "extraction_latency_trend": trend_direction(extraction_latencies),
                "query_latency_trend": trend_direction(query_latencies),
                "memory_trend": trend_direction(memory_usage),
                "hourly_throughput": [
                    {"hour": s.hour, "docs": s.documents_ingested, "queries": s.queries_executed}
                    for s in snapshots
                ]
            }
    
    def get_summary(self) -> Dict:
        """Get complete summary of all metrics"""
        with self.lock:
            total_docs = len(self.all_ingestion_results)
            successful_docs = sum(1 for r in self.all_ingestion_results if r.success)
            total_queries = len(self.all_query_results)
            successful_queries = sum(1 for r in self.all_query_results if r.success)
            
            return {
                "duration_hours": (time.time() - self.start_time) / 3600,
                "documents": {
                    "attempted": total_docs,
                    "succeeded": successful_docs,
                    "failed": total_docs - successful_docs,
                    "success_rate": successful_docs / max(1, total_docs)
                },
                "entities": {
                    "total_extracted": sum(r.entities_extracted for r in self.all_ingestion_results if r.success)
                },
                "relationships": {
                    "total_extracted": sum(r.relationships_extracted for r in self.all_ingestion_results if r.success)
                },
                "queries": {
                    "total": total_queries,
                    "succeeded": successful_queries,
                    "failed": total_queries - successful_queries,
                    "success_rate": successful_queries / max(1, total_queries)
                },
                "hallucinations": sum(1 for r in self.all_query_results if r.hallucination_detected),
                "correct_refusals": sum(1 for r in self.all_query_results 
                                       if not r.expected_exists and not r.entity_found),
                "top_failures": self.get_top_failures(),
                "top_slow_operations": self.get_top_slow_operations(),
                "confidence_calibration": self.get_confidence_calibration(),
                "trends": self.get_trends()
            }
