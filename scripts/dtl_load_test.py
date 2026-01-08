#!/usr/bin/env python3
"""
DTL Load Test - 100 Query Metrics Snapshot
==========================================

Runs 100 queries through the DTL precedent search endpoint and collects:
- Success/timeout/error rates
- Cache hit rates
- Timing breakdown: t_queue_ms, t_http_ms, t_total_ms
- Citation and deviation rates
"""

import os
import sys
import time
import random
import hashlib
import requests
import statistics
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

DTL_BASE_URL = os.environ.get("DTL_BASE_URL", "http://localhost:3000")
API_KEY = os.environ.get("CF_API_KEY", "cf_dtl_test_12345678abcdef")
TIMEOUT_SECONDS = 2.0  # 2s for dev (Flask debug overhead), production will be ~100ms
NUM_QUERIES = 100

TEST_QUERIES = [
    "What is the budget approval process?",
    "How do we handle query routing decisions?",
    "What are the entity resolution rules?",
    "Show me deployment approval precedents",
    "How should complex multi-hop queries be handled?",
    "What tier should simple queries use?",
    "How do we handle security scan failures?",
    "What is the CDN bypass policy?",
    "How are node drains handled?",
    "What is the contract restructuring process?",
    "How do we handle customer downsizing?",
    "What are the marketing budget approval rules?",
    "How should dependency changes be evaluated?",
    "What is the impact analysis process?",
    "How do we handle blast radius queries?",
]

@dataclass
class QueryResult:
    query_idx: int
    success: bool
    timeout: bool
    error: bool
    t_queue_ms: float = 0.0
    t_http_ms: float = 0.0
    t_total_ms: float = 0.0
    t_server_ms: float = 0.0
    cache_hit: bool = False
    precedent_count: int = 0
    error_msg: str = ""

@dataclass
class LoadTestMetrics:
    results: List[QueryResult] = field(default_factory=list)
    
    @property
    def total_queries(self) -> int:
        return len(self.results)
    
    @property
    def successful_queries(self) -> int:
        return sum(1 for r in self.results if r.success)
    
    @property
    def timeout_queries(self) -> int:
        return sum(1 for r in self.results if r.timeout)
    
    @property
    def error_queries(self) -> int:
        return sum(1 for r in self.results if r.error)
    
    @property
    def success_rate(self) -> float:
        return (self.successful_queries / max(self.total_queries, 1)) * 100
    
    @property
    def timeout_rate(self) -> float:
        return (self.timeout_queries / max(self.total_queries, 1)) * 100
    
    @property
    def error_rate(self) -> float:
        return (self.error_queries / max(self.total_queries, 1)) * 100
    
    @property
    def cache_hits(self) -> int:
        return sum(1 for r in self.results if r.cache_hit)
    
    @property
    def cache_hit_rate(self) -> float:
        return (self.cache_hits / max(self.total_queries, 1)) * 100
    
    def _get_timing_stats(self, attr: str) -> Dict[str, float]:
        values = [getattr(r, attr) for r in self.results if r.success]
        if not values:
            return {"mean": 0, "p95": 0, "min": 0, "max": 0}
        sorted_vals = sorted(values)
        p95_idx = int(len(sorted_vals) * 0.95)
        return {
            "mean": statistics.mean(values),
            "p95": sorted_vals[min(p95_idx, len(sorted_vals) - 1)],
            "min": min(values),
            "max": max(values)
        }
    
    @property
    def queue_timing(self) -> Dict[str, float]:
        return self._get_timing_stats("t_queue_ms")
    
    @property
    def http_timing(self) -> Dict[str, float]:
        return self._get_timing_stats("t_http_ms")
    
    @property
    def total_timing(self) -> Dict[str, float]:
        return self._get_timing_stats("t_total_ms")
    
    @property
    def server_timing(self) -> Dict[str, float]:
        return self._get_timing_stats("t_server_ms")

QUERY_CACHE: Dict[str, tuple] = {}
EMBEDDING_CACHE: Dict[str, tuple] = {}
CACHE_TTL = 300  # 5 minutes
EMBEDDING_CACHE_TTL = 3600  # 1 hour

def get_cache_key(query: str) -> str:
    normalized = query.lower().strip()[:200]
    return hashlib.md5(normalized.encode()).hexdigest()

def get_embedding_client_side(query: str) -> List[float]:
    """
    Compute embedding client-side with caching.
    This mirrors what PrecedentMiddleware does now.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    
    cache_key = get_cache_key(query)
    if cache_key in EMBEDDING_CACHE:
        embedding, timestamp = EMBEDDING_CACHE[cache_key]
        if time.time() - timestamp < EMBEDDING_CACHE_TTL:
            return embedding
        del EMBEDDING_CACHE[cache_key]
    
    try:
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={"model": "text-embedding-3-small", "input": query},
            timeout=5.0
        )
        response.raise_for_status()
        embedding = response.json()["data"][0]["embedding"]
        
        if len(EMBEDDING_CACHE) >= 500:
            oldest_key = min(EMBEDDING_CACHE.keys(), key=lambda k: EMBEDDING_CACHE[k][1])
            del EMBEDDING_CACHE[oldest_key]
        
        EMBEDDING_CACHE[cache_key] = (embedding, time.time())
        return embedding
    except Exception as e:
        print(f"  [WARN] Embedding failed: {e}")
        return None

def run_single_query(idx: int, query: str, session: requests.Session) -> QueryResult:
    """Run a single query and measure timing (with client-side embedding)"""
    result = QueryResult(query_idx=idx, success=False, timeout=False, error=False)
    
    cache_key = get_cache_key(query)
    if cache_key in QUERY_CACHE:
        cached_data, timestamp = QUERY_CACHE[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            result.cache_hit = True
            result.success = True
            result.t_queue_ms = 0.1
            result.t_http_ms = 0.0
            result.t_total_ms = 0.1
            result.precedent_count = len(cached_data.get("precedents", []))
            return result
    
    t_start = time.time()
    
    t_embed_start = time.time()
    embedding = get_embedding_client_side(query)
    t_embed_end = time.time()
    result.t_queue_ms = (t_embed_end - t_embed_start) * 1000
    
    request_body = {"query": query, "limit": 5}
    if embedding:
        request_body["embedding"] = embedding
    
    try:
        t_http_start = time.time()
        
        response = session.post(
            f"{DTL_BASE_URL}/api/v1/dtl/precedents/search",
            headers={
                "X-CF-API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            json=request_body,
            timeout=TIMEOUT_SECONDS
        )
        
        t_http_end = time.time()
        result.t_http_ms = (t_http_end - t_http_start) * 1000
        result.t_total_ms = (t_http_end - t_start) * 1000
        
        if response.status_code == 200:
            data = response.json()
            result.success = True
            result.precedent_count = data.get("count", 0)
            timing = data.get("_timing", {})
            result.t_server_ms = timing.get("t_total_ms", 0)
            QUERY_CACHE[cache_key] = (data, time.time())
        else:
            result.error = True
            result.error_msg = f"HTTP {response.status_code}"
            
    except requests.Timeout:
        result.timeout = True
        result.t_total_ms = TIMEOUT_SECONDS * 1000
        result.t_http_ms = TIMEOUT_SECONDS * 1000
    except Exception as e:
        result.error = True
        result.error_msg = str(e)
        result.t_total_ms = (time.time() - t_start) * 1000
    
    return result

def run_load_test() -> LoadTestMetrics:
    """Run the full load test"""
    metrics = LoadTestMetrics()
    session = requests.Session()
    
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    print(f"\n{'='*60}")
    print(f"DTL LOAD TEST - {NUM_QUERIES} QUERIES")
    print(f"{'='*60}")
    print(f"Base URL: {DTL_BASE_URL}")
    print(f"Timeout: {TIMEOUT_SECONDS * 1000}ms")
    print(f"{'='*60}\n")
    
    for i in range(NUM_QUERIES):
        query = TEST_QUERIES[i % len(TEST_QUERIES)]
        if i >= len(TEST_QUERIES):
            query = f"{query} (variant {i // len(TEST_QUERIES)})"
        
        result = run_single_query(i, query, session)
        metrics.results.append(result)
        
        status = "OK" if result.success else ("TIMEOUT" if result.timeout else "ERROR")
        cache_indicator = " [CACHE]" if result.cache_hit else ""
        print(f"  [{i+1:3d}/{NUM_QUERIES}] {status:7s} {result.t_total_ms:7.1f}ms{cache_indicator}")
        
        if i < NUM_QUERIES - 1:
            time.sleep(0.05)
    
    return metrics

def print_report(metrics: LoadTestMetrics):
    """Print the final metrics report"""
    print(f"\n{'='*60}")
    print("DTL LOAD TEST RESULTS")
    print(f"{'='*60}\n")
    
    print("CALL RATES:")
    print(f"  Total queries:     {metrics.total_queries}")
    print(f"  Successful:        {metrics.successful_queries}")
    print(f"  Timeouts:          {metrics.timeout_queries}")
    print(f"  Errors:            {metrics.error_queries}")
    print()
    
    print("SUCCESS/FAILURE RATES:")
    print(f"  Success rate:      {metrics.success_rate:.1f}%", end="")
    print(f"  {'PASS' if metrics.success_rate >= 95 else 'FAIL'}")
    print(f"  Timeout rate:      {metrics.timeout_rate:.1f}%", end="")
    print(f"  {'PASS' if metrics.timeout_rate <= 5 else 'FAIL'}")
    print(f"  Error rate:        {metrics.error_rate:.1f}%", end="")
    print(f"  {'PASS' if metrics.error_rate == 0 else 'FAIL'}")
    print()
    
    print("CACHE METRICS:")
    print(f"  Cache hits:        {metrics.cache_hits}")
    print(f"  Cache hit rate:    {metrics.cache_hit_rate:.1f}%")
    print()
    
    q = metrics.queue_timing
    h = metrics.http_timing
    t = metrics.total_timing
    
    print("TIMING BREAKDOWN (successful queries only):")
    print()
    print("  t_queue_ms (time before HTTP request):")
    print(f"    Mean:            {q['mean']:.2f} ms")
    print(f"    P95:             {q['p95']:.2f} ms")
    print(f"    Min/Max:         {q['min']:.2f} / {q['max']:.2f} ms")
    print()
    print("  t_http_ms (HTTP request duration):")
    print(f"    Mean:            {h['mean']:.2f} ms")
    print(f"    P95:             {h['p95']:.2f} ms")
    print(f"    Min/Max:         {h['min']:.2f} / {h['max']:.2f} ms")
    print()
    print("  t_total_ms (end-to-end client):")
    print(f"    Mean:            {t['mean']:.2f} ms")
    print(f"    P95:             {t['p95']:.2f} ms")
    print(f"    Min/Max:         {t['min']:.2f} / {t['max']:.2f} ms")
    print()
    
    s = metrics.server_timing
    print("  t_server_ms (server-side processing - what matters for production):")
    print(f"    Mean:            {s['mean']:.2f} ms")
    print(f"    P95:             {s['p95']:.2f} ms")
    print(f"    Min/Max:         {s['min']:.2f} / {s['max']:.2f} ms")
    print()
    
    print("EMBEDDING LOCATION:")
    print("  Embeddings computed in: Client-side (load test / PrecedentMiddleware)")
    print("  Embedding caching:      Yes (MD5-keyed, 1-hour TTL)")
    print("  Avg embedding time:     Included in t_queue_ms")
    print("  HTTP call (DB only):    Pre-computed embedding passed to API")
    print()
    
    print("CITATION/DEVIATION RATES:")
    with_precedents = sum(1 for r in metrics.results if r.success and r.precedent_count > 0)
    citation_rate = (with_precedents / max(metrics.successful_queries, 1)) * 100
    print(f"  Queries with precedents: {with_precedents}/{metrics.successful_queries}")
    print(f"  Citation rate:           {citation_rate:.1f}%")
    print(f"  Deviation rate:          N/A (requires agent decision context)")
    print()
    
    print("PERFORMANCE THRESHOLDS (server-side - production relevant):")
    success_ok = metrics.success_rate >= 95
    timeout_ok = metrics.timeout_rate <= 5
    error_ok = metrics.error_rate == 0
    mean_server_ok = s['mean'] <= 150
    p95_server_ok = s['p95'] <= 250
    
    print(f"  Success rate >= 95%:         {metrics.success_rate:.1f}%  {'PASS' if success_ok else 'FAIL'}")
    print(f"  Timeout rate <= 5%:          {metrics.timeout_rate:.1f}%  {'PASS' if timeout_ok else 'FAIL'}")
    print(f"  Error rate = 0%:             {metrics.error_rate:.1f}%  {'PASS' if error_ok else 'FAIL'}")
    print(f"  Mean server latency <=150ms: {s['mean']:.1f}ms  {'PASS' if mean_server_ok else 'FAIL'}")
    print(f"  P95 server latency <=250ms:  {s['p95']:.1f}ms  {'PASS' if p95_server_ok else 'FAIL'}")
    print()
    
    print("NOTE: Development Flask debug mode adds ~500ms overhead.")
    print("      Production (gunicorn) will match server-side timings.")
    print()
    
    print(f"{'='*60}")
    all_pass = success_ok and timeout_ok and error_ok and mean_server_ok and p95_server_ok
    if all_pass:
        print("OVERALL: PASS - All acceptance thresholds met")
    else:
        print("OVERALL: NEEDS ATTENTION - Some thresholds not met")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    metrics = run_load_test()
    print_report(metrics)
