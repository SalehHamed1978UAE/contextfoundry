#!/usr/bin/env python3
"""Find the breaking point with incremental concurrency testing."""

import time
import psutil
import logging
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from rich.console import Console
from rich.table import Table

logging.getLogger().setLevel(logging.ERROR)
console = Console()

QUERIES = [
    "What concerns has Mia White raised?",
    "Who owns Auth Service?",
    "What services depend on Payment Service?",
    "What decisions were made about cloud migration?",
    "Who is on the Platform Team?",
]

def get_memory():
    return psutil.Process().memory_info().rss / (1024**2)

def run_query(idx):
    from src.context_foundry.core import ContextFoundry
    cf = ContextFoundry()
    query = QUERIES[idx % len(QUERIES)]
    start = time.time()
    try:
        result = cf.query(query)
        return {'ok': True, 'lat': time.time() - start, 'conf': result.get('confidence', 0)}
    except Exception as e:
        return {'ok': False, 'lat': time.time() - start, 'err': str(e)[:40]}

def test_concurrency(n, query_timeout=120):
    """Test n concurrent queries."""
    console.print(f"[cyan]Testing {n} concurrent...[/cyan]", end=" ")
    
    mem_start = get_memory()
    t_start = time.time()
    results = []
    
    with ThreadPoolExecutor(max_workers=n) as ex:
        futures = [ex.submit(run_query, i) for i in range(n)]
        done = 0
        try:
            for f in as_completed(futures, timeout=query_timeout * 1.5):
                try:
                    r = f.result(timeout=5)
                    results.append(r)
                    done += 1
                except Exception as e:
                    results.append({'ok': False, 'lat': query_timeout, 'err': 'individual_timeout'})
        except FuturesTimeout:
            # Some futures didn't complete
            for _ in range(n - len(results)):
                results.append({'ok': False, 'lat': query_timeout * 1.5, 'err': 'global_timeout'})
    
    elapsed = time.time() - t_start
    mem_end = get_memory()
    
    successes = [r for r in results if r.get('ok')]
    success_rate = 100 * len(successes) / n
    avg_lat = sum(r['lat'] for r in successes) / len(successes) if successes else 0
    max_lat = max((r['lat'] for r in results), default=0)
    
    status = "[green]OK[/green]" if success_rate == 100 and avg_lat < 60 else "[red]BREAKING[/red]"
    console.print(f"{status} | {success_rate:.0f}% | avg={avg_lat:.1f}s max={max_lat:.1f}s | mem={mem_end:.0f}MB")
    
    return {
        'n': n,
        'success_rate': success_rate,
        'avg_lat': avg_lat,
        'max_lat': max_lat,
        'elapsed': elapsed,
        'mem_mb': mem_end,
        'status': 'ok' if success_rate == 100 and avg_lat < 60 else 'breaking'
    }

def main():
    console.print("\n[bold cyan]Finding Breaking Point at 100x Scale (4,709 docs)[/bold cyan]\n")
    
    # Test incrementally: 10, 12, 15, 18, 20, 25
    levels = [10, 12, 15, 18, 20, 25]
    results = []
    breaking_point = None
    
    for level in levels:
        r = test_concurrency(level)
        results.append(r)
        
        if r['status'] == 'breaking' and breaking_point is None:
            breaking_point = level
            console.print(f"\n[red]Breaking point detected at {level} concurrent queries![/red]")
        
        # Stop if success rate drops below 80%
        if r['success_rate'] < 80:
            console.print("[red]Stopping: success rate too low[/red]")
            break
    
    # Summary
    console.print("\n")
    table = Table(title="Breaking Point Analysis")
    table.add_column("Concurrent", justify="center")
    table.add_column("Success", justify="center")
    table.add_column("Avg Lat", justify="center")
    table.add_column("Max Lat", justify="center")
    table.add_column("Memory", justify="center")
    table.add_column("Status", justify="center")
    
    for r in results:
        status = "[green]OK[/green]" if r['status'] == 'ok' else "[red]BREAKING[/red]"
        table.add_row(
            str(r['n']),
            f"{r['success_rate']:.0f}%",
            f"{r['avg_lat']:.1f}s",
            f"{r['max_lat']:.1f}s",
            f"{r['mem_mb']:.0f} MB",
            status
        )
    console.print(table)
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'scale': '100x',
        'docs': 4709,
        'breaking_point': breaking_point,
        'results': results
    }
    with open('scale_test_results/breaking_point_100x.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    console.print(f"\n[cyan]Results saved to scale_test_results/breaking_point_100x.json[/cyan]")
    
    if breaking_point:
        console.print(f"\n[bold]Breaking Point: {breaking_point} concurrent queries[/bold]")
        console.print(f"[bold]Recommended Production Limit: {breaking_point - 2} concurrent queries[/bold]")
    else:
        console.print("\n[bold green]No breaking point found up to 25 concurrent queries![/bold green]")

if __name__ == "__main__":
    main()
