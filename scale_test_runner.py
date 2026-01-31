#!/usr/bin/env python3
"""
Scale testing runner for Context Foundry.

Measures:
- Ingestion time (embedding generation)
- Database size (storage)
- Query latencies
- Memory usage

Usage:
    python scale_test_runner.py --phase baseline    # Measure current state
    python scale_test_runner.py --phase ingest      # Ingest scale data
    python scale_test_runner.py --phase benchmark   # Run query benchmarks
    python scale_test_runner.py --phase all         # Run full scale test
"""

import argparse
import json
import os
import time
import gc
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from sqlalchemy import func, text

console = Console()

BENCHMARK_QUERIES = [
    ("entity_person", "What concerns has Mia White raised recently?"),
    ("entity_service", "Who owns the Auth Service?"),
    ("topic_migration", "What decisions have been made about cloud migration?"),
    ("topic_cost", "What is the status of cost reduction initiatives?"),
    ("impact_cascade", "What's the blast radius if API Gateway fails?"),
    ("impact_dependency", "What services depend on Payment Service?"),
    ("temporal_recent", "What were the key decisions in the last Q4 meeting?"),
    ("multi_hop", "What is the escalation path for Auth Service incidents?"),
    ("abstention_unknown", "What is Project Omega's current status?"),
    ("analysis_trend", "Are latency issues getting better or worse?"),
]


def get_database_stats() -> Dict[str, Any]:
    """Get database size and row counts."""
    from src.context_foundry.models.schema import get_session, Entity, Relationship, Document
    
    session = get_session()
    try:
        entity_count = session.query(func.count(Entity.id)).scalar()
        relationship_count = session.query(func.count(Relationship.id)).scalar()
        document_count = session.query(func.count(Document.id)).scalar()
        
        size_query = text("""
            SELECT 
                pg_size_pretty(pg_database_size(current_database())) as db_size,
                pg_database_size(current_database()) as db_size_bytes
        """)
        result = session.execute(size_query).fetchone()
        
        table_sizes_query = text("""
            SELECT 
                relname as table_name,
                pg_size_pretty(pg_total_relation_size(relid)) as total_size,
                pg_total_relation_size(relid) as size_bytes
            FROM pg_catalog.pg_statio_user_tables
            ORDER BY pg_total_relation_size(relid) DESC
            LIMIT 10
        """)
        table_sizes = session.execute(table_sizes_query).fetchall()
        
        return {
            "entity_count": entity_count,
            "relationship_count": relationship_count,
            "document_count": document_count,
            "database_size": result[0] if result else "unknown",
            "database_size_bytes": result[1] if result else 0,
            "table_sizes": [
                {"table": row[0], "size": row[1], "bytes": row[2]}
                for row in table_sizes
            ],
        }
    finally:
        session.close()


def get_memory_usage() -> Dict[str, float]:
    """Get current memory usage."""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    
    return {
        "rss_mb": mem_info.rss / (1024 * 1024),
        "vms_mb": mem_info.vms / (1024 * 1024),
        "percent": process.memory_percent(),
    }


def run_baseline_measurement() -> Dict[str, Any]:
    """Measure baseline metrics before scale testing."""
    console.print("\n[bold cyan]Baseline Measurement[/bold cyan]\n")
    
    db_stats = get_database_stats()
    mem_usage = get_memory_usage()
    
    table = Table(title="Current Database State")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Entities", f"{db_stats['entity_count']:,}")
    table.add_row("Relationships", f"{db_stats['relationship_count']:,}")
    table.add_row("Documents", f"{db_stats['document_count']:,}")
    table.add_row("Database Size", db_stats['database_size'])
    table.add_row("Memory (RSS)", f"{mem_usage['rss_mb']:.1f} MB")
    
    console.print(table)
    
    if db_stats['table_sizes']:
        table2 = Table(title="Table Sizes")
        table2.add_column("Table", style="cyan")
        table2.add_column("Size", style="green")
        
        for ts in db_stats['table_sizes'][:5]:
            table2.add_row(ts['table'], ts['size'])
        
        console.print(table2)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "database": db_stats,
        "memory": mem_usage,
    }


def run_ingestion(data_dir: str, batch_size: int = 50) -> Dict[str, Any]:
    """Run scaled data ingestion with timing."""
    console.print(f"\n[bold cyan]Ingesting from {data_dir}[/bold cyan]\n")
    
    from src.context_foundry.ingestion.ingestion_pipeline import IngestionPipeline
    from src.context_foundry.memory.episodic import EpisodicMemory
    
    data_path = Path(data_dir)
    if not data_path.exists():
        console.print(f"[red]Directory not found: {data_dir}[/red]")
        return {"error": f"Directory not found: {data_dir}"}
    
    md_files = list(data_path.rglob("*.md"))
    console.print(f"Found {len(md_files)} markdown files")
    
    pipeline = IngestionPipeline(
        max_tokens=512,
        overlap_sentences=1,
        min_chunk_size=50,
    )
    
    episodic = EpisodicMemory()
    
    start_time = time.time()
    mem_before = get_memory_usage()
    
    total_docs = 0
    total_chunks = 0
    embedding_time = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=len(md_files))
        
        for i, md_file in enumerate(md_files):
            try:
                with open(md_file) as f:
                    content = f.read()
                
                doc_type = md_file.parent.name.upper()
                title = md_file.stem.replace("_", " ").title()
                
                embed_start = time.time()
                episodic.add_document(
                    title=title,
                    doc_type=f"{doc_type}_SCALE",
                    content=content,
                    metadata={
                        "source_path": str(md_file),
                        "ingestion_type": "scale_test",
                        "batch": i // batch_size,
                    },
                )
                embedding_time += time.time() - embed_start
                
                total_docs += 1
                
                lines = content.split("\n\n")
                chunks = ["\n\n".join(lines[j:j+3]) for j in range(0, len(lines), 3) if lines[j:j+3]]
                
                for chunk_idx, chunk_content in enumerate(chunks[:5]):
                    if len(chunk_content.strip()) > 50:
                        embed_start = time.time()
                        episodic.add_document(
                            title=f"{title} - Chunk {chunk_idx}",
                            doc_type=f"{doc_type}_CHUNK_SCALE",
                            content=chunk_content,
                            metadata={
                                "source_document": title,
                                "chunk_index": chunk_idx,
                                "ingestion_type": "scale_test",
                            },
                        )
                        embedding_time += time.time() - embed_start
                        total_chunks += 1
                
                progress.update(task, advance=1, description=f"Processing: {md_file.name[:30]}...")
                
                if (i + 1) % batch_size == 0:
                    gc.collect()
                    
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to process {md_file}: {e}[/yellow]")
    
    elapsed = time.time() - start_time
    mem_after = get_memory_usage()
    
    results = {
        "documents_ingested": total_docs,
        "chunks_created": total_chunks,
        "total_items": total_docs + total_chunks,
        "elapsed_seconds": elapsed,
        "embedding_time_seconds": embedding_time,
        "docs_per_second": total_docs / elapsed if elapsed > 0 else 0,
        "memory_before_mb": mem_before['rss_mb'],
        "memory_after_mb": mem_after['rss_mb'],
        "memory_delta_mb": mem_after['rss_mb'] - mem_before['rss_mb'],
    }
    
    console.print(f"\n[bold green]Ingestion Complete![/bold green]")
    console.print(f"  Documents: {total_docs}")
    console.print(f"  Chunks: {total_chunks}")
    console.print(f"  Total time: {elapsed:.1f}s")
    console.print(f"  Embedding time: {embedding_time:.1f}s ({embedding_time/elapsed*100:.1f}%)")
    console.print(f"  Throughput: {results['docs_per_second']:.2f} docs/sec")
    console.print(f"  Memory delta: {results['memory_delta_mb']:.1f} MB")
    
    return results


def run_query_benchmark(iterations: int = 3) -> Dict[str, Any]:
    """Run query benchmarks and measure latencies."""
    console.print(f"\n[bold cyan]Query Benchmark ({iterations} iterations each)[/bold cyan]\n")
    
    from src.context_foundry.core import ContextFoundry
    
    cf = ContextFoundry()
    
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running benchmarks...", total=len(BENCHMARK_QUERIES) * iterations)
        
        for query_type, query in BENCHMARK_QUERIES:
            latencies = []
            confidences = []
            
            for i in range(iterations):
                progress.update(task, description=f"Query: {query_type} (iter {i+1})")
                
                start = time.time()
                
                try:
                    result = cf.query(query)
                    
                    elapsed = time.time() - start
                    latencies.append(elapsed)
                    confidences.append(result.get('confidence', 0))
                    
                except Exception as e:
                    console.print(f"[yellow]Query failed: {query_type} - {e}[/yellow]")
                    latencies.append(-1)
                    confidences.append(0)
                
                progress.update(task, advance=1)
                gc.collect()
            
            valid_latencies = [l for l in latencies if l > 0]
            
            result = {
                "query_type": query_type,
                "query": query,
                "latencies": latencies,
                "avg_latency": sum(valid_latencies) / len(valid_latencies) if valid_latencies else -1,
                "min_latency": min(valid_latencies) if valid_latencies else -1,
                "max_latency": max(valid_latencies) if valid_latencies else -1,
                "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
                "success_rate": len(valid_latencies) / iterations,
            }
            results.append(result)
    
    table = Table(title="Query Latency Results")
    table.add_column("Query Type", style="cyan")
    table.add_column("Avg (s)", style="green")
    table.add_column("Min (s)", style="dim")
    table.add_column("Max (s)", style="dim")
    table.add_column("Confidence", style="yellow")
    table.add_column("Success", style="green")
    
    for r in results:
        table.add_row(
            r['query_type'],
            f"{r['avg_latency']:.2f}" if r['avg_latency'] > 0 else "FAIL",
            f"{r['min_latency']:.2f}" if r['min_latency'] > 0 else "-",
            f"{r['max_latency']:.2f}" if r['max_latency'] > 0 else "-",
            f"{r['avg_confidence']*100:.0f}%",
            f"{r['success_rate']*100:.0f}%",
        )
    
    console.print(table)
    
    valid_results = [r for r in results if r['avg_latency'] > 0]
    if valid_results:
        overall_avg = sum(r['avg_latency'] for r in valid_results) / len(valid_results)
        console.print(f"\n[bold]Overall average latency: {overall_avg:.2f}s[/bold]")
    
    return {
        "queries": results,
        "overall_avg_latency": overall_avg if valid_results else -1,
        "timestamp": datetime.now().isoformat(),
    }


def run_full_scale_test(scale_factor: int, output_file: str = None) -> Dict[str, Any]:
    """Run complete scale test pipeline."""
    console.print(f"\n[bold magenta]═══ Scale Test: {scale_factor}x ═══[/bold magenta]\n")
    
    results = {
        "scale_factor": scale_factor,
        "start_time": datetime.now().isoformat(),
    }
    
    console.print("[bold]Phase 1: Baseline Measurement[/bold]")
    results["baseline"] = run_baseline_measurement()
    
    data_dir = f"test_data/scale_docs_{scale_factor}x"
    data_path = Path(data_dir)
    
    if not data_path.exists():
        console.print(f"\n[bold]Phase 2: Generate Scale Data[/bold]")
        doc_count = 25 * scale_factor
        console.print(f"Generating {doc_count} documents...")
        os.system(f"python generate_scale_data.py --count {doc_count} --output {data_dir}")
    
    console.print(f"\n[bold]Phase 3: Ingestion[/bold]")
    results["ingestion"] = run_ingestion(data_dir)
    
    console.print(f"\n[bold]Phase 4: Post-Ingestion State[/bold]")
    results["post_ingestion"] = run_baseline_measurement()
    
    console.print(f"\n[bold]Phase 5: Query Benchmark[/bold]")
    results["benchmark"] = run_query_benchmark(iterations=3)
    
    results["end_time"] = datetime.now().isoformat()
    
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        console.print(f"\n[green]Results saved to {output_file}[/green]")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Context Foundry Scale Testing")
    parser.add_argument("--phase", choices=["baseline", "ingest", "benchmark", "all"], 
                       default="all", help="Test phase to run")
    parser.add_argument("--scale", type=int, default=10, help="Scale factor (10=10x, 50=50x)")
    parser.add_argument("--data-dir", type=str, default=None, help="Data directory for ingestion")
    parser.add_argument("--output", type=str, default=None, help="Output file for results")
    parser.add_argument("--iterations", type=int, default=3, help="Benchmark iterations per query")
    args = parser.parse_args()
    
    if args.output is None:
        args.output = f"scale_test_results/scale_{args.scale}x_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    if args.phase == "baseline":
        results = run_baseline_measurement()
    elif args.phase == "ingest":
        data_dir = args.data_dir or f"test_data/scale_docs_{args.scale}x"
        results = run_ingestion(data_dir)
    elif args.phase == "benchmark":
        results = run_query_benchmark(iterations=args.iterations)
    elif args.phase == "all":
        results = run_full_scale_test(args.scale, args.output)
    
    console.print("\n[bold green]Scale test complete![/bold green]")


if __name__ == "__main__":
    main()
