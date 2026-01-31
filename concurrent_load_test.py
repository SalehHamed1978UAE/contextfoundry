#!/usr/bin/env python3
"""
Concurrent load testing for Context Foundry.

Tests parallel query execution to find breaking points.

Usage:
    python concurrent_load_test.py                    # Run standard test (5, 10, 15 concurrent)
    python concurrent_load_test.py --max-concurrent 20  # Custom max concurrency
    python concurrent_load_test.py --stress            # Aggressive stress test
"""

import argparse
import asyncio
import json
import time
import gc
import os
import psutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

TEST_QUERIES = [
    "What concerns has Mia White raised?",
    "What decisions about cloud migration?",
    "What's the blast radius if API Gateway fails?",
    "Who are the Directors in Engineering?",
    "What's the escalation path for SEV1?",
    "Who owns the Payment Service?",
    "What is the status of cost reduction?",
    "What services depend on Auth Service?",
    "What were the key Q4 budget decisions?",
    "What security concerns have been raised?",
    "Who is responsible for Notification Service?",
    "What is the current migration timeline?",
    "What incidents affected Payment Service?",
    "Who should I contact about database issues?",
    "What are the main platform team priorities?",
]


def run_single_query(query: str, query_id: int) -> Dict[str, Any]:
    """Execute a single query and return timing/result info."""
    from src.context_foundry.core import ContextFoundry
    
    start_time = time.time()
    
    try:
        cf = ContextFoundry()
        result = cf.query(query)
        
        elapsed = time.time() - start_time
        
        return {
            "query_id": query_id,
            "query": query[:50],
            "success": True,
            "latency": elapsed,
            "confidence": result.get('confidence', 0),
            "answer_length": len(result.get('answer', '')),
            "error": None,
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "query_id": query_id,
            "query": query[:50],
            "success": False,
            "latency": elapsed,
            "confidence": 0,
            "answer_length": 0,
            "error": str(e),
        }


def run_concurrent_batch(n_concurrent: int, queries: List[str] = None) -> Dict[str, Any]:
    """Run a batch of concurrent queries."""
    if queries is None:
        queries = TEST_QUERIES[:n_concurrent]
    
    queries = (queries * ((n_concurrent // len(queries)) + 1))[:n_concurrent]
    
    console.print(f"\n[cyan]Running {n_concurrent} concurrent queries...[/cyan]")
    
    start_time = time.time()
    mem_before = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    
    results = []
    
    with ThreadPoolExecutor(max_workers=n_concurrent) as executor:
        futures = {
            executor.submit(run_single_query, query, i): i 
            for i, query in enumerate(queries)
        }
        
        for future in as_completed(futures):
            try:
                result = future.result(timeout=120)
                results.append(result)
            except Exception as e:
                query_id = futures[future]
                results.append({
                    "query_id": query_id,
                    "success": False,
                    "latency": -1,
                    "error": f"Timeout/Exception: {e}",
                })
    
    elapsed = time.time() - start_time
    mem_after = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    latencies = [r["latency"] for r in successful if r["latency"] > 0]
    
    batch_result = {
        "n_concurrent": n_concurrent,
        "total_time": elapsed,
        "queries_succeeded": len(successful),
        "queries_failed": len(failed),
        "success_rate": len(successful) / n_concurrent if n_concurrent > 0 else 0,
        "avg_latency": sum(latencies) / len(latencies) if latencies else -1,
        "min_latency": min(latencies) if latencies else -1,
        "max_latency": max(latencies) if latencies else -1,
        "throughput_qps": len(successful) / elapsed if elapsed > 0 else 0,
        "memory_before_mb": mem_before,
        "memory_after_mb": mem_after,
        "memory_delta_mb": mem_after - mem_before,
        "individual_results": results,
        "errors": [r.get("error") for r in failed if r.get("error")],
    }
    
    console.print(f"  Completed: {len(successful)}/{n_concurrent} succeeded")
    console.print(f"  Total time: {elapsed:.2f}s")
    console.print(f"  Avg latency: {batch_result['avg_latency']:.2f}s" if batch_result['avg_latency'] > 0 else "  Avg latency: N/A")
    console.print(f"  Throughput: {batch_result['throughput_qps']:.2f} queries/sec")
    
    if failed:
        console.print(f"  [yellow]Failures: {len(failed)}[/yellow]")
        for err in batch_result['errors'][:3]:
            console.print(f"    - {err[:80]}")
    
    return batch_result


def run_load_test(
    concurrency_levels: List[int] = None,
    iterations_per_level: int = 2,
) -> Dict[str, Any]:
    """Run load test across multiple concurrency levels."""
    
    if concurrency_levels is None:
        concurrency_levels = [1, 3, 5, 10, 15]
    
    console.print("\n[bold magenta]═══ Concurrent Load Test ═══[/bold magenta]\n")
    console.print(f"Testing concurrency levels: {concurrency_levels}")
    console.print(f"Iterations per level: {iterations_per_level}")
    
    all_results = []
    
    for n_concurrent in concurrency_levels:
        console.print(f"\n[bold]Testing {n_concurrent} concurrent queries[/bold]")
        
        level_results = []
        for iteration in range(iterations_per_level):
            console.print(f"  Iteration {iteration + 1}/{iterations_per_level}")
            result = run_concurrent_batch(n_concurrent)
            level_results.append(result)
            gc.collect()
            time.sleep(1)
        
        avg_latency = sum(r['avg_latency'] for r in level_results if r['avg_latency'] > 0) / len(level_results)
        avg_throughput = sum(r['throughput_qps'] for r in level_results) / len(level_results)
        avg_success_rate = sum(r['success_rate'] for r in level_results) / len(level_results)
        
        aggregated = {
            "n_concurrent": n_concurrent,
            "iterations": iterations_per_level,
            "avg_latency": avg_latency,
            "avg_throughput": avg_throughput,
            "avg_success_rate": avg_success_rate,
            "raw_results": level_results,
        }
        all_results.append(aggregated)
    
    table = Table(title="Load Test Summary")
    table.add_column("Concurrent", style="cyan")
    table.add_column("Avg Latency", style="green")
    table.add_column("Throughput", style="yellow")
    table.add_column("Success Rate", style="green")
    table.add_column("Status", style="bold")
    
    breaking_point = None
    
    for r in all_results:
        status = "[green]OK[/green]"
        if r['avg_success_rate'] < 0.95:
            status = "[yellow]DEGRADED[/yellow]"
            if breaking_point is None:
                breaking_point = r['n_concurrent']
        if r['avg_success_rate'] < 0.80:
            status = "[red]FAILING[/red]"
            if breaking_point is None:
                breaking_point = r['n_concurrent']
        
        table.add_row(
            str(r['n_concurrent']),
            f"{r['avg_latency']:.2f}s" if r['avg_latency'] > 0 else "N/A",
            f"{r['avg_throughput']:.2f} q/s",
            f"{r['avg_success_rate']*100:.0f}%",
            status,
        )
    
    console.print("\n")
    console.print(table)
    
    if breaking_point:
        console.print(f"\n[yellow]Breaking point detected at {breaking_point} concurrent queries[/yellow]")
    else:
        console.print(f"\n[green]No breaking point detected up to {concurrency_levels[-1]} concurrent queries[/green]")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "concurrency_levels": concurrency_levels,
        "iterations_per_level": iterations_per_level,
        "breaking_point": breaking_point,
        "results": all_results,
    }


def run_stress_test(max_concurrent: int = 25, ramp_step: int = 5) -> Dict[str, Any]:
    """Run aggressive stress test to find true breaking point."""
    
    console.print("\n[bold red]═══ STRESS TEST ═══[/bold red]\n")
    console.print(f"Ramping from 1 to {max_concurrent} concurrent queries (step: {ramp_step})")
    console.print("[yellow]Warning: This may consume significant resources[/yellow]")
    
    levels = list(range(1, max_concurrent + 1, ramp_step))
    if levels[-1] != max_concurrent:
        levels.append(max_concurrent)
    
    return run_load_test(
        concurrency_levels=levels,
        iterations_per_level=1,
    )


def main():
    parser = argparse.ArgumentParser(description="Context Foundry Concurrent Load Testing")
    parser.add_argument("--max-concurrent", type=int, default=15, 
                       help="Maximum concurrent queries to test")
    parser.add_argument("--iterations", type=int, default=2,
                       help="Iterations per concurrency level")
    parser.add_argument("--stress", action="store_true",
                       help="Run aggressive stress test")
    parser.add_argument("--output", type=str, default=None,
                       help="Output file for results")
    args = parser.parse_args()
    
    if args.output is None:
        args.output = f"scale_test_results/load_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    if args.stress:
        results = run_stress_test(max_concurrent=args.max_concurrent)
    else:
        levels = [1, 3, 5]
        step = 5
        current = 10
        while current <= args.max_concurrent:
            levels.append(current)
            current += step
        
        results = run_load_test(
            concurrency_levels=levels,
            iterations_per_level=args.iterations,
        )
    
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    console.print(f"\n[green]Results saved to {args.output}[/green]")
    console.print("\n[bold green]Load test complete![/bold green]")


if __name__ == "__main__":
    main()
