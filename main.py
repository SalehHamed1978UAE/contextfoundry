#!/usr/bin/env python3
"""
Context Foundry CLI - Walking Skeleton MVP
A tri-memory cognitive architecture for intelligent IT operations.
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich import print as rprint

from src.context_foundry.core import ContextFoundry
from src.context_foundry.models.schema import init_database
from src.context_foundry.data.synthetic_generator import generate_synthetic_data
from src.context_foundry.utils.logger import logger

console = Console()


def display_banner():
    """Display the Context Foundry banner."""
    banner = """
[bold cyan]╔═══════════════════════════════════════════════════════════════╗
║                    CONTEXT FOUNDRY                              ║
║         Tri-Memory Cognitive Architecture MVP                   ║
╠═══════════════════════════════════════════════════════════════╣
║  Semantic Memory  │  Episodic Memory  │  Symbolic Memory       ║
║  (Knowledge Graph)│  (Vector Search)  │  (Rules Engine)        ║
╚═══════════════════════════════════════════════════════════════╝[/bold cyan]
    """
    console.print(banner)


def display_help():
    """Display available commands."""
    table = Table(title="Available Commands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="green")
    table.add_column("Description")
    
    table.add_row("query <text>", "Execute a natural language query")
    table.add_row("impact <entity>", "Analyze impact if entity goes down")
    table.add_row("escalation <context>", "Find escalation path")
    table.add_row("stats", "Show memory statistics")
    table.add_row("examples", "Show example queries")
    table.add_row("export", "Export last query results")
    table.add_row("help", "Show this help message")
    table.add_row("quit", "Exit the CLI")
    
    console.print(table)


def display_examples():
    """Display example multi-hop queries."""
    console.print("\n[bold cyan]Example Multi-Hop Queries:[/bold cyan]\n")
    
    examples = [
        ("Impact Analysis", "What services are affected if the Payments Database goes down?"),
        ("Escalation Path", "Who should I escalate to for a SEV1 on the Auth Service?"),
        ("Dependency Chain", "What does the Checkout Service depend on?"),
        ("Team Ownership", "Which team owns the Payment Service and who leads it?"),
        ("Incident Response", "How do I handle a database connection exhaustion incident?"),
        ("Multi-Hop Chain", "If Redis Session Cache fails, which teams need to be notified?"),
    ]
    
    for title, query in examples:
        console.print(f"  [yellow]{title}:[/yellow]")
        console.print(f"    > {query}\n")


def initialize_system():
    """Initialize the Context Foundry system with synthetic data."""
    console.print("\n[bold]Initializing Context Foundry...[/bold]")
    
    with console.status("[cyan]Setting up database..."):
        init_database()
    console.print("  [green]✓[/green] Database initialized")
    
    with console.status("[cyan]Generating synthetic IT operations data..."):
        synthetic_data = generate_synthetic_data()
    console.print(f"  [green]✓[/green] Generated {synthetic_data['metadata']['entity_count']} entities, "
                 f"{synthetic_data['metadata']['relationship_count']} relationships")
    
    cf = ContextFoundry()
    
    with console.status("[cyan]Loading data into tri-memory architecture..."):
        stats = cf.load_data(synthetic_data)
    
    console.print(f"  [green]✓[/green] Loaded {stats['entities_loaded']} entities")
    console.print(f"  [green]✓[/green] Loaded {stats['relationships_loaded']} relationships")
    console.print(f"  [green]✓[/green] Loaded {stats['documents_loaded']} documents (runbooks)")
    console.print(f"  [green]✓[/green] Loaded {stats['rules_loaded']} rules")
    
    if stats['errors']:
        console.print(f"  [yellow]![/yellow] {len(stats['errors'])} errors during load")
    
    console.print("\n[bold green]System ready![/bold green]")
    
    return cf


def run_interactive_cli():
    """Run the interactive CLI."""
    display_banner()
    
    try:
        cf = initialize_system()
    except Exception as e:
        console.print(f"\n[bold red]Failed to initialize system: {e}[/bold red]")
        logger.exception("Initialization failed")
        return
    
    display_help()
    console.print("\n[dim]Type 'examples' to see sample queries, or enter your own query.[/dim]\n")
    
    last_response = None
    last_bundle = None
    
    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]CF[/bold cyan]")
            
            if not user_input.strip():
                continue
            
            parts = user_input.strip().split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            if command in ['quit', 'exit', 'q']:
                console.print("\n[dim]Goodbye![/dim]")
                break
            
            elif command == 'help':
                display_help()
            
            elif command == 'examples':
                display_examples()
            
            elif command == 'stats':
                stats = cf.get_statistics()
                console.print("\n[bold]System Statistics:[/bold]")
                console.print(json.dumps(stats, indent=2, default=str))
            
            elif command == 'query':
                if not args:
                    console.print("[yellow]Usage: query <your question>[/yellow]")
                    continue
                
                console.print(f"\n[bold]Processing query:[/bold] {args}")
                last_response = cf.query(args)
            
            elif command == 'impact':
                if not args:
                    console.print("[yellow]Usage: impact <entity name>[/yellow]")
                    continue
                
                console.print(f"\n[bold]Analyzing impact for:[/bold] {args}")
                last_response = cf.query_impact(args)
            
            elif command == 'escalation':
                if not args:
                    console.print("[yellow]Usage: escalation <context>[/yellow]")
                    continue
                
                console.print(f"\n[bold]Finding escalation path for:[/bold] {args}")
                last_response = cf.query_escalation(args)
            
            elif command == 'export':
                if last_response:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filepath = f"exports/response_{timestamp}.json"
                    os.makedirs("exports", exist_ok=True)
                    cf.export_response(last_response, filepath)
                    console.print(f"[green]Exported to {filepath}[/green]")
                else:
                    console.print("[yellow]No query results to export. Run a query first.[/yellow]")
            
            else:
                console.print(f"\n[bold]Processing query:[/bold] {user_input}")
                last_response = cf.query(user_input)
        
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Type 'quit' to exit.[/dim]")
        
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            logger.exception("CLI error")


def run_demo():
    """Run a demonstration with predefined queries."""
    display_banner()
    
    try:
        cf = initialize_system()
    except Exception as e:
        console.print(f"\n[bold red]Failed to initialize system: {e}[/bold red]")
        logger.exception("Initialization failed")
        return
    
    console.print("\n" + "=" * 70)
    console.print("[bold cyan]RUNNING DEMONSTRATION QUERIES[/bold cyan]")
    console.print("=" * 70)
    
    demo_queries = [
        "What services are affected if the Payments Database goes down?",
        "Who should I escalate to for a SEV1 on the Auth Service?",
        "What team owns the Payment Service?",
    ]
    
    for i, query in enumerate(demo_queries, 1):
        console.print(f"\n[bold yellow]Demo Query {i}/{len(demo_queries)}:[/bold yellow]")
        console.print(f"[italic]{query}[/italic]")
        console.print("-" * 50)
        
        response = cf.query(query)
        
        os.makedirs("exports", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cf.export_response(response, f"exports/demo_query_{i}_{timestamp}.json")
        
        console.print("\n")
    
    console.print("=" * 70)
    console.print("[bold green]DEMONSTRATION COMPLETE[/bold green]")
    console.print("=" * 70)
    
    stats = cf.get_statistics()
    console.print("\n[bold]Final Statistics:[/bold]")
    console.print(json.dumps(stats, indent=2, default=str))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo()
    else:
        run_interactive_cli()
