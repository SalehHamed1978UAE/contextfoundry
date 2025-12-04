#!/usr/bin/env python3
"""High-concurrency stress test at 100x scale to find breaking point."""

import time
import psutil
import logging
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from rich.console import Console
from rich.table import Table

logging.getLogger().setLevel(logging.ERROR)
console = Console()

# Test queries
QUERIES = [
    "What concerns has Mia White raised?",
    "Who owns Auth Service?",
    "What services depend on Payment Service?",
    "What decisions were made about cloud migration?",
    "Who is on the Platform Team?",
    "What is the escalation path for API Gateway?",
    "What happened in the Q4 planning meeting?",
    "What are Alex Rivera's responsibilities?",
]

def get_memory_usage():
    """Get current memory usage in MB."""
    process = psutil.Process()
    return process.memory_info().rss / (1024 * 1024)

def run_single_query(query_idx):
    """Run a single query and return timing + success."""
    from src.context_foundry.core import ContextFoundry
    query = QUERIES[query_idx % len(QUERIES)]
    cf = ContextFoundry()
    
    start = time.time()
    try:
        result = cf.query(query)
        elapsed = time.time() - start
        confidence = result.get('confidence', 0)
        return {
            'success': True,
            'latency': elapsed,
            'confidence': confidence,
            'query': query[:40]
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            'success': False,
            'latency': elapsed,
            'error': str(e)[:50],
            'query': query[:40]
        }

def run_stress_test(concurrency, timeout_per_query=180):
    """Run stress test at given concurrency level."""
    console.print(f"\n[cyan]Testing {concurrency} concurrent queries...[/cyan]")
    
    mem_before = get_memory_usage()
    start_time = time.time()
    results = []
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(run_single_query, i): i for i in range(concurrency)}
        
        try:
            for future in as_completed(futures, timeout=timeout_per_query * 2):
                try:
                    result = future.result(timeout=timeout_per_query)
                    results.append(result)
                    status = "OK" if result['success'] else "FAIL"
                    console.print(f"  [{status}] {result.get('latency', 0):.1f}s - {result.get('query', '')[:30]}...")
                except TimeoutError:
                    results.append({'success': False, 'latency': timeout_per_query, 'error': 'TIMEOUT'})
                    console.print(f"  [TIMEOUT] Query exceeded {timeout_per_query}s")
                except Exception as e:
                    results.append({'success': False, 'latency': 0, 'error': str(e)[:50]})
                    console.print(f"  [ERROR] {str(e)[:50]}")
        except TimeoutError:
            unfinished = concurrency - len(results)
            console.print(f"  [GLOBAL_TIMEOUT] {unfinished} queries still pending")
            for _ in range(unfinished):
                results.append({'success': False, 'latency': timeout_per_query * 2, 'error': 'GLOBAL_TIMEOUT'})
    
    total_time = time.time() - start_time
    mem_after = get_memory_usage()
    
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    
    avg_latency = sum(r['latency'] for r in successful) / len(successful) if successful else 0
    success_rate = len(successful) / len(results) * 100 if results else 0
    
    return {
        'concurrency': concurrency,
        'total_queries': len(results),
        'successful': len(successful),
        'failed': len(failed),
        'success_rate': success_rate,
        'avg_latency': avg_latency,
        'max_latency': max((r['latency'] for r in results), default=0),
        'total_time': total_time,
        'mem_before_mb': mem_before,
        'mem_after_mb': mem_after,
        'mem_delta_mb': mem_after - mem_before,
        'failures': [r.get('error', 'unknown') for r in failed]
    }

def main():
    console.print("[bold cyan]Phase 3: High-Concurrency Stress Test at 100x Scale[/bold cyan]")
    console.print("Finding the breaking point...\n")
    
    # Test levels
    concurrency_levels = [15, 20, 25]
    all_results = []
    breaking_point = None
    
    for level in concurrency_levels:
        result = run_stress_test(level)
        all_results.append(result)
        
        # Check for breaking point
        if result['success_rate'] < 100 or result['avg_latency'] > 60:
            if breaking_point is None:
                breaking_point = level
                console.print(f"\n[red]BREAKING POINT DETECTED at {level} concurrent![/red]")
        
        console.print(f"\n  Success rate: {result['success_rate']:.0f}%")
        console.print(f"  Avg latency: {result['avg_latency']:.1f}s")
        console.print(f"  Memory: {result['mem_before_mb']:.0f} MB -> {result['mem_after_mb']:.0f} MB")
        
        # If we're failing, don't continue
        if result['success_rate'] < 50:
            console.print("[red]Success rate below 50%, stopping tests.[/red]")
            break
    
    # Summary table
    table = Table(title="\nStress Test Summary (100x Scale)")
    table.add_column("Concurrent", justify="center")
    table.add_column("Success Rate", justify="center")
    table.add_column("Avg Latency", justify="center")
    table.add_column("Max Latency", justify="center")
    table.add_column("Memory Delta", justify="center")
    table.add_column("Status", justify="center")
    
    for r in all_results:
        status = "[green]OK[/green]" if r['success_rate'] == 100 and r['avg_latency'] < 60 else "[red]BREAKING[/red]"
        table.add_row(
            str(r['concurrency']),
            f"{r['success_rate']:.0f}%",
            f"{r['avg_latency']:.1f}s",
            f"{r['max_latency']:.1f}s",
            f"{r['mem_delta_mb']:+.1f} MB",
            status
        )
    
    console.print(table)
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'scale': '100x',
        'document_count': 4709,
        'breaking_point': breaking_point,
        'results': all_results
    }
    
    with open('scale_test_results/stress_test_100x.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    console.print(f"\n[cyan]Results saved to scale_test_results/stress_test_100x.json[/cyan]")
    
    if breaking_point:
        console.print(f"\n[bold red]Breaking point: {breaking_point} concurrent queries[/bold red]")
    else:
        console.print("\n[bold green]No breaking point detected up to 25 concurrent queries![/bold green]")

if __name__ == "__main__":
    main()
