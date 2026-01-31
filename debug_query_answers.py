#!/usr/bin/env python3
"""Show full answers for diagnostic queries."""

from src.context_foundry.agents.retrieval import RetrievalAgent
from src.context_foundry.agents.reasoning import ReasoningAgent
from rich.console import Console
from rich.panel import Panel

console = Console()

def run_query(query: str):
    console.print(f"\n[bold cyan]Query:[/bold cyan] {query}\n")
    
    retrieval = RetrievalAgent()
    context = retrieval.build_context_bundle(query)
    
    console.print(f"[dim]Query Type: {context.query_type}[/dim]")
    console.print(f"[dim]Target Entity Found: {context.target_entity_found}[/dim]")
    console.print(f"[dim]Target Entity Name: {context.target_entity_name}[/dim]")
    
    if context.episodic_documents:
        console.print(f"\n[yellow]Episodic Documents Retrieved ({len(context.episodic_documents)}):[/yellow]")
        for i, doc in enumerate(context.episodic_documents[:5]):
            title = doc.get('title', 'Unknown')[:60]
            score = doc.get('similarity', 0)
            console.print(f"  {i+1}. {title} (sim: {score:.2f})")
    
    reasoning = ReasoningAgent()
    response = reasoning.reason(context)
    
    console.print(Panel(
        response.get("answer", "No answer"),
        title=f"[bold green]Answer (Confidence: {response.get('confidence', 0)*100:.0f}%)[/bold green]",
        border_style="green"
    ))
    
    if response.get("reasoning"):
        console.print(f"\n[dim]Reasoning: {response.get('reasoning')[:300]}...[/dim]")
    
    if response.get("caveats"):
        console.print(f"\n[yellow]Caveats: {response.get('caveats')}[/yellow]")
    
    return response

def main():
    queries = [
        "What decisions were made about cloud migration?",
        "What concerns has Mia White raised?",
    ]
    
    for query in queries:
        run_query(query)
        console.print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
