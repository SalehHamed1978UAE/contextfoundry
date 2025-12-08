"""
Report Generator

Creates SUMMARY.md and JSONL log files
"""
import os
import json
from typing import Dict, List
from datetime import datetime

from stress_test.config import StressTestConfig
from stress_test.metrics_collector import MetricsCollector, HourlySnapshot
from stress_test.ingestion_runner import IngestionResult
from stress_test.query_runner import QueryResult

class ReportGenerator:
    def __init__(self, config: StressTestConfig, metrics: MetricsCollector):
        self.config = config
        self.metrics = metrics
        self.results_dir = config.results_dir
        
        os.makedirs(self.results_dir, exist_ok=True)
        
    def write_summary(self):
        """Generate SUMMARY.md"""
        summary = self.metrics.get_summary()
        
        content = f"""# Context Foundry Stress Test Results

**Generated:** {datetime.now().isoformat()}
**Duration:** {summary['duration_hours']:.2f} hours

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Documents Attempted | {summary['documents']['attempted']} |
| Documents Succeeded | {summary['documents']['succeeded']} |
| Documents Failed | {summary['documents']['failed']} |
| Document Success Rate | {summary['documents']['success_rate']*100:.1f}% |
| Total Entities Extracted | {summary['entities']['total_extracted']} |
| Total Relationships Extracted | {summary['relationships']['total_extracted']} |
| Queries Executed | {summary['queries']['total']} |
| Query Success Rate | {summary['queries']['success_rate']*100:.1f}% |
| Hallucinations Detected | {summary['hallucinations']} |
| Correct Refusals | {summary['correct_refusals']} |

---

## Top 10 Failure Modes

| Rank | Failure Type | Count |
|------|--------------|-------|
"""
        for i, (failure_type, count) in enumerate(summary['top_failures'][:10], 1):
            content += f"| {i} | {failure_type} | {count} |\n"

        content += """
---

## Top 10 Slowest Operations

| Rank | Type | Latency (ms) | ID |
|------|------|-------------|-----|
"""
        for i, op in enumerate(summary['top_slow_operations'][:10], 1):
            content += f"| {i} | {op['type']} | {op['latency_ms']:.0f} | {op['id'][:30]}... |\n"

        content += """
---

## Confidence Calibration

| Confidence Range | Total Queries | Correct | Accuracy | Expected | Calibration Error |
|-----------------|---------------|---------|----------|----------|-------------------|
"""
        for bucket, data in summary['confidence_calibration'].items():
            content += f"| {bucket} | {data['total']} | {data['correct']} | {data['accuracy']*100:.1f}% | {data['expected_accuracy']*100:.1f}% | {data['calibration_error']*100:.1f}% |\n"

        content += """
---

## Hourly Stats

| Hour | Documents | Entities | Queries | Hallucinations | Avg Extract (ms) | Avg Query (ms) | Memory (MB) |
|------|-----------|----------|---------|----------------|-----------------|----------------|-------------|
"""
        for snapshot in self.metrics.hourly_snapshots:
            content += f"| {snapshot.hour} | {snapshot.documents_ingested} | {snapshot.entities_extracted} | {snapshot.queries_executed} | {snapshot.hallucinations} | {snapshot.avg_extraction_latency_ms:.0f} | {snapshot.avg_query_latency_ms:.0f} | {snapshot.memory_usage_mb:.0f} |\n"

        trends = summary.get('trends', {})
        content += f"""
---

## Trends Analysis

- **Extraction Latency Trend:** {trends.get('extraction_latency_trend', 'N/A')}
- **Query Latency Trend:** {trends.get('query_latency_trend', 'N/A')}
- **Memory Trend:** {trends.get('memory_trend', 'N/A')}

---

## Recommendations for Review

"""
        if summary['hallucinations'] > 0:
            content += f"- **CRITICAL:** {summary['hallucinations']} hallucinations detected. Review non-existent entity queries.\n"
        
        if summary['documents']['success_rate'] < 0.95:
            content += f"- **WARNING:** Document ingestion success rate below 95%. Check error logs.\n"
        
        if summary['queries']['success_rate'] < 0.95:
            content += f"- **WARNING:** Query success rate below 95%. Check query patterns.\n"
        
        if trends.get('extraction_latency_trend') == 'increasing':
            content += "- **ATTENTION:** Extraction latency increasing over time. Possible performance degradation.\n"
        
        if trends.get('memory_trend') == 'increasing':
            content += "- **ATTENTION:** Memory usage increasing. Possible memory leak.\n"
        
        if summary['documents']['success_rate'] >= 0.95 and summary['queries']['success_rate'] >= 0.95 and summary['hallucinations'] == 0:
            content += "- **PASSED:** All metrics within acceptable ranges. Context Foundry is ready for production.\n"

        content += f"""
---

## Raw Data Files

- `documents_log.jsonl` - All document ingestion attempts
- `extractions_log.jsonl` - Extraction details
- `queries_log.jsonl` - All query executions
- `errors_log.jsonl` - All errors encountered
- `hourly_stats.json` - Hourly snapshots

---

*Report generated by Context Foundry Stress Test Suite*
"""
        
        with open(os.path.join(self.results_dir, "SUMMARY.md"), "w") as f:
            f.write(content)
    
    def write_documents_log(self, results: List[IngestionResult]):
        """Append to documents_log.jsonl"""
        filepath = os.path.join(self.results_dir, "documents_log.jsonl")
        with open(filepath, "a") as f:
            for r in results:
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "doc_id": r.doc_id,
                    "success": r.success,
                    "document_db_id": r.document_db_id,
                    "upload_time_ms": r.upload_time_ms,
                    "extraction_time_ms": r.extraction_time_ms,
                    "entities_extracted": r.entities_extracted,
                    "relationships_extracted": r.relationships_extracted,
                    "error": r.error
                }
                f.write(json.dumps(entry) + "\n")
    
    def write_extractions_log(self, results: List[IngestionResult]):
        """Append to extractions_log.jsonl"""
        filepath = os.path.join(self.results_dir, "extractions_log.jsonl")
        with open(filepath, "a") as f:
            for r in results:
                if r.success and r.extracted_entities:
                    entry = {
                        "timestamp": datetime.now().isoformat(),
                        "doc_id": r.doc_id,
                        "entities": r.extracted_entities[:20],
                        "entity_count": r.entities_extracted,
                        "relationship_count": r.relationships_extracted
                    }
                    f.write(json.dumps(entry) + "\n")
    
    def write_queries_log(self, results: List[QueryResult]):
        """Append to queries_log.jsonl"""
        filepath = os.path.join(self.results_dir, "queries_log.jsonl")
        with open(filepath, "a") as f:
            for r in results:
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "query_id": r.query_id,
                    "query": r.query[:200],
                    "pattern": r.pattern,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                    "confidence": r.confidence,
                    "entity_found": r.entity_found,
                    "is_adversarial": r.is_adversarial,
                    "expected_exists": r.expected_exists,
                    "hallucination": r.hallucination_detected,
                    "error": r.error
                }
                f.write(json.dumps(entry) + "\n")
    
    def write_errors_log(self, ingestion_results: List[IngestionResult], 
                        query_results: List[QueryResult]):
        """Append to errors_log.jsonl"""
        filepath = os.path.join(self.results_dir, "errors_log.jsonl")
        with open(filepath, "a") as f:
            for r in ingestion_results:
                if not r.success:
                    entry = {
                        "timestamp": datetime.now().isoformat(),
                        "type": "ingestion",
                        "id": r.doc_id,
                        "error": r.error
                    }
                    f.write(json.dumps(entry) + "\n")
            
            for r in query_results:
                if not r.success:
                    entry = {
                        "timestamp": datetime.now().isoformat(),
                        "type": "query",
                        "id": r.query_id,
                        "query": r.query[:200],
                        "error": r.error
                    }
                    f.write(json.dumps(entry) + "\n")
    
    def write_hourly_stats(self):
        """Write hourly_stats.json"""
        filepath = os.path.join(self.results_dir, "hourly_stats.json")
        snapshots = []
        for s in self.metrics.hourly_snapshots:
            snapshots.append({
                "hour": s.hour,
                "timestamp": s.timestamp,
                "documents_ingested": s.documents_ingested,
                "documents_failed": s.documents_failed,
                "entities_extracted": s.entities_extracted,
                "relationships_extracted": s.relationships_extracted,
                "queries_executed": s.queries_executed,
                "queries_failed": s.queries_failed,
                "hallucinations": s.hallucinations,
                "correct_refusals": s.correct_refusals,
                "avg_extraction_latency_ms": s.avg_extraction_latency_ms,
                "avg_query_latency_ms": s.avg_query_latency_ms,
                "memory_usage_mb": s.memory_usage_mb,
                "cpu_percent": s.cpu_percent,
                "errors": s.errors
            })
        
        with open(filepath, "w") as f:
            json.dump({"snapshots": snapshots}, f, indent=2)
