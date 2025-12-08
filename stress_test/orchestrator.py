"""
Main Stress Test Orchestrator

Coordinates document generation, ingestion, queries, and reporting
for the full stress test run.
"""
import os
import sys
import time
import logging
import signal
import threading
from datetime import datetime, timedelta
from typing import Optional

from stress_test.config import StressTestConfig, QUICK_CONFIG, OVERNIGHT_CONFIG
from stress_test.document_generator import DocumentGenerator
from stress_test.query_generator import QueryGenerator
from stress_test.ingestion_runner import IngestionRunner
from stress_test.query_runner import QueryRunner
from stress_test.metrics_collector import MetricsCollector
from stress_test.report_generator import ReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class StressTestOrchestrator:
    def __init__(self, config: StressTestConfig):
        self.config = config
        self.running = True
        self.start_time = None
        self.end_time = None
        
        os.makedirs(config.results_dir, exist_ok=True)
        
        self.doc_generator = DocumentGenerator(config)
        self.query_generator = QueryGenerator(config)
        self.ingestion_runner = IngestionRunner(config)
        self.query_runner = QueryRunner(config)
        self.metrics = MetricsCollector(config)
        self.report = ReportGenerator(config, self.metrics)
        
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info("Shutdown signal received. Finishing current batch and generating report...")
        self.running = False
    
    def _time_remaining(self) -> float:
        """Get remaining time in seconds"""
        if not self.end_time:
            return 0
        return max(0, (self.end_time - datetime.now()).total_seconds())
    
    def _current_hour(self) -> int:
        """Get current hour of the test"""
        if not self.start_time:
            return 0
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return int(elapsed / 3600)
    
    def run(self):
        """Main test loop"""
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(hours=self.config.duration_hours)
        
        logger.info("=" * 70)
        logger.info("CONTEXT FOUNDRY STRESS TEST STARTING")
        logger.info("=" * 70)
        logger.info(f"Duration: {self.config.duration_hours} hours")
        logger.info(f"Target Documents: {self.config.target_documents}")
        logger.info(f"Target Queries: {self.config.target_queries}")
        logger.info(f"Results Directory: {self.config.results_dir}")
        logger.info("=" * 70)
        
        logger.info("Generating edge case documents first...")
        edge_cases = self.doc_generator.generate_edge_case_documents()
        logger.info(f"Generated {len(edge_cases)} edge case documents")
        
        edge_results = self.ingestion_runner.ingest_batch(edge_cases)
        self.metrics.record_ingestion_results(edge_results)
        self.report.write_documents_log(edge_results)
        self.report.write_errors_log(edge_results, [])
        
        logger.info("Starting main test loop...")
        
        docs_generated = len(edge_cases)
        queries_executed = 0
        last_hour_logged = -1
        last_hourly_checkpoint = time.time()
        
        batch_size_docs = max(1, self.config.docs_per_hour // 12)
        batch_size_queries = max(1, self.config.queries_per_hour // 12)
        
        while self.running and self._time_remaining() > 0:
            current_hour = self._current_hour()
            
            if current_hour > last_hour_logged:
                logger.info(f"\n{'='*50}")
                logger.info(f"HOUR {current_hour} STARTING")
                logger.info(f"{'='*50}")
                last_hour_logged = current_hour
            
            if time.time() - last_hourly_checkpoint >= 3600:
                self._take_checkpoint()
                last_hourly_checkpoint = time.time()
            
            if docs_generated < self.config.target_documents:
                logger.info(f"Generating batch of {batch_size_docs} documents...")
                docs = []
                for i in range(batch_size_docs):
                    if not self.running:
                        break
                    doc = self.doc_generator.generate_document(docs_generated + i)
                    docs.append(doc)
                    
                    if doc.is_adversarial:
                        logger.info(f"  Generated adversarial doc: {doc.doc_id} ({doc.adversarial_type})")
                
                if docs:
                    logger.info(f"Ingesting {len(docs)} documents...")
                    results = self.ingestion_runner.ingest_batch(docs)
                    self.metrics.record_ingestion_results(results)
                    self.report.write_documents_log(results)
                    self.report.write_extractions_log(results)
                    
                    for r in results:
                        if r.success and r.extracted_entities:
                            entity_names = [e.get('name', '') if isinstance(e, dict) else str(e) 
                                          for e in r.extracted_entities]
                            self.doc_generator.register_extracted_entities(entity_names)
                            self.query_generator.register_entities(r.extracted_entities)
                    
                    successful = sum(1 for r in results if r.success)
                    total_entities = sum(r.entities_extracted for r in results if r.success)
                    logger.info(f"  Ingested: {successful}/{len(docs)} successful, {total_entities} entities extracted")
                    
                    docs_generated += len(docs)
            
            if queries_executed < self.config.target_queries and self.query_generator.known_entities:
                logger.info(f"Executing batch of {batch_size_queries} queries...")
                queries = self.query_generator.generate_batch(batch_size_queries)
                
                adversarial_count = sum(1 for q in queries if q.is_adversarial)
                if adversarial_count > 0:
                    logger.info(f"  Including {adversarial_count} adversarial queries")
                
                results = self.query_runner.run_batch(queries)
                self.metrics.record_query_results(results)
                self.report.write_queries_log(results)
                self.report.write_errors_log([], results)
                
                successful = sum(1 for r in results if r.success)
                hallucinations = sum(1 for r in results if r.hallucination_detected)
                logger.info(f"  Queries: {successful}/{len(queries)} successful, {hallucinations} hallucinations")
                
                queries_executed += len(queries)
            
            stats = self.ingestion_runner.get_stats()
            query_stats = self.query_runner.get_stats()
            logger.info(f"Progress: {docs_generated}/{self.config.target_documents} docs, "
                       f"{queries_executed}/{self.config.target_queries} queries, "
                       f"{stats['total_entities']} entities, "
                       f"{query_stats['hallucinations']} hallucinations")
            
            if docs_generated >= self.config.target_documents and queries_executed >= self.config.target_queries:
                logger.info("All targets reached!")
                break
            
            time.sleep(1)
        
        self._finalize()
    
    def _take_checkpoint(self):
        """Take hourly checkpoint"""
        logger.info("Taking hourly checkpoint...")
        snapshot = self.metrics.take_hourly_snapshot()
        self.report.write_hourly_stats()
        self.report.write_summary()
        
        logger.info(f"Checkpoint - Hour {snapshot.hour}:")
        logger.info(f"  Documents: {snapshot.documents_ingested} ingested, {snapshot.documents_failed} failed")
        logger.info(f"  Entities: {snapshot.entities_extracted}")
        logger.info(f"  Queries: {snapshot.queries_executed} executed, {snapshot.queries_failed} failed")
        logger.info(f"  Hallucinations: {snapshot.hallucinations}")
        logger.info(f"  Avg Extraction Latency: {snapshot.avg_extraction_latency_ms:.0f}ms")
        logger.info(f"  Avg Query Latency: {snapshot.avg_query_latency_ms:.0f}ms")
        logger.info(f"  Memory: {snapshot.memory_usage_mb:.0f}MB")
    
    def _finalize(self):
        """Finalize test and generate reports"""
        logger.info("\n" + "=" * 70)
        logger.info("STRESS TEST COMPLETE - GENERATING FINAL REPORTS")
        logger.info("=" * 70)
        
        self.metrics.take_hourly_snapshot()
        
        self.report.write_summary()
        self.report.write_hourly_stats()
        
        summary = self.metrics.get_summary()
        
        logger.info("\nFINAL RESULTS:")
        logger.info(f"  Duration: {summary['duration_hours']:.2f} hours")
        logger.info(f"  Documents: {summary['documents']['succeeded']}/{summary['documents']['attempted']} "
                   f"({summary['documents']['success_rate']*100:.1f}%)")
        logger.info(f"  Entities Extracted: {summary['entities']['total_extracted']}")
        logger.info(f"  Relationships Extracted: {summary['relationships']['total_extracted']}")
        logger.info(f"  Queries: {summary['queries']['succeeded']}/{summary['queries']['total']} "
                   f"({summary['queries']['success_rate']*100:.1f}%)")
        logger.info(f"  Hallucinations: {summary['hallucinations']}")
        logger.info(f"  Correct Refusals: {summary['correct_refusals']}")
        
        logger.info("\nTop Failure Modes:")
        for failure, count in summary['top_failures'][:5]:
            logger.info(f"  - {failure}: {count}")
        
        logger.info(f"\nResults saved to: {self.config.results_dir}")
        logger.info(f"  - SUMMARY.md")
        logger.info(f"  - documents_log.jsonl")
        logger.info(f"  - extractions_log.jsonl")
        logger.info(f"  - queries_log.jsonl")
        logger.info(f"  - errors_log.jsonl")
        logger.info(f"  - hourly_stats.json")


def run_quick_test():
    """Run a quick 1-hour test"""
    config = QUICK_CONFIG
    orchestrator = StressTestOrchestrator(config)
    orchestrator.run()


def run_overnight_test():
    """Run the full 8-hour overnight test"""
    config = OVERNIGHT_CONFIG
    orchestrator = StressTestOrchestrator(config)
    orchestrator.run()


def run_custom_test(duration_hours: float, target_docs: int, target_queries: int):
    """Run a custom duration test"""
    config = StressTestConfig()
    config.duration_hours = duration_hours
    config.target_documents = target_docs
    config.target_queries = target_queries
    config.docs_per_hour = max(1, int(target_docs / duration_hours))
    config.queries_per_hour = max(1, int(target_queries / duration_hours))
    
    orchestrator = StressTestOrchestrator(config)
    orchestrator.run()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Context Foundry Stress Test")
    parser.add_argument("--mode", choices=["quick", "medium", "overnight", "custom"], 
                       default="quick", help="Test mode")
    parser.add_argument("--hours", type=float, default=1.0, help="Duration for custom mode")
    parser.add_argument("--docs", type=int, default=50, help="Target documents for custom mode")
    parser.add_argument("--queries", type=int, default=500, help="Target queries for custom mode")
    
    args = parser.parse_args()
    
    if args.mode == "quick":
        run_quick_test()
    elif args.mode == "medium":
        config = StressTestConfig().get_medium_test_config()
        orchestrator = StressTestOrchestrator(config)
        orchestrator.run()
    elif args.mode == "overnight":
        run_overnight_test()
    else:
        run_custom_test(args.hours, args.docs, args.queries)
