#!/usr/bin/env python3
"""
Test Context Foundry's reasoning with synthetic organizational documents.
Focuses on temporal reasoning, contradiction detection, and ambiguity handling.
"""

from src.context_foundry.agents.retrieval import RetrievalAgent
from src.context_foundry.agents.reasoning import ReasoningAgent
from src.context_foundry.agents.validation import ValidationAgent
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

def run_test_query(query: str, description: str):
    """Run a single test query and display results."""
    
    console.print(f"\n[bold magenta]Test: {description}[/bold magenta]")
    console.print(f"[dim]Query: {query}[/dim]\n")
    
    retrieval = RetrievalAgent()
    context = retrieval.build_context_bundle(query)
    
    console.print(f"[cyan]Query Type:[/cyan] {context.query_type}")
    console.print(f"[cyan]Semantic Evidence:[/cyan] {len(context.semantic_entities)} entities, {len(context.semantic_relationships)} relationships")
    console.print(f"[cyan]Episodic Evidence:[/cyan] {len(context.episodic_documents)} documents")
    console.print(f"[cyan]Rules Applied:[/cyan] {len(context.symbolic_rules)} rules")
    
    if context.episodic_documents:
        console.print("\n[bold]Relevant Documents Found:[/bold]")
        for i, doc in enumerate(context.episodic_documents[:5]):
            title = doc.get('title', 'Unknown')[:50]
            score = doc.get('similarity', doc.get('similarity_score', 0))
            console.print(f"  {i+1}. {title} (score: {score:.2f})")
    
    reasoning = ReasoningAgent()
    response = reasoning.reason(context)
    
    validator = ValidationAgent()
    response = validator.validate_response(response, context)
    
    table = Table(title="Results", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    answer = response.get("answer", "No answer")
    table.add_row("Answer", answer[:200] + "..." if len(answer) > 200 else answer)
    table.add_row("Confidence", f"{response.get('confidence', 0) * 100:.0f}%")
    table.add_row("Validation", "Passed" if response.get("validation", {}).get("passed", False) else "Failed")
    
    citations = response.get("citations", [])
    if citations:
        table.add_row("Citations", str(len(citations)))
    
    console.print(table)
    
    reasoning_text = response.get("reasoning", "")
    if reasoning_text:
        console.print(f"\n[dim]Reasoning: {reasoning_text[:150]}...[/dim]")
    
    return {
        "query": query,
        "description": description,
        "answer": answer,
        "confidence": response.get("confidence", 0),
        "episodic_count": len(context.episodic_documents),
        "valid": response.get("validation", {}).get("passed", False),
    }

def main():
    console.print(Panel.fit(
        "[bold cyan]Context Foundry: Synthetic Data Query Tests[/bold cyan]\n"
        "Testing temporal reasoning, contradiction detection, and ambiguity handling",
        border_style="cyan"
    ))
    
    test_cases = [
        {
            "query": "What decisions were made about the cloud migration?",
            "description": "Temporal Synthesis - Track decisions across meetings",
        },
        {
            "query": "Has our position on vendor selection changed?",
            "description": "Contradiction Detection - CloudShift to MigrateX switch",
        },
        {
            "query": "What concerns has Mia White raised about costs?",
            "description": "Entity-based Temporal Retrieval - Person's concerns over time",
        },
        {
            "query": "What's the status of the cost reduction initiative?",
            "description": "Status Tracking - Ongoing initiative across documents",
        },
        {
            "query": "What's the Payment Service migration timeline?",
            "description": "Timeline Extraction - Specific project dates",
        },
        {
            "query": "What frontend framework did the team decide to use?",
            "description": "Decision Tracking - RFC outcome",
        },
        {
            "query": "Who was hired recently and what team are they on?",
            "description": "Entity Extraction - New hire identification",
        },
        {
            "query": "What customer complaints were escalated?",
            "description": "Issue Tracking - Escalation path",
        },
        {
            "query": "What observability improvements are planned?",
            "description": "Future Planning - Budget and roadmap",
        },
        {
            "query": "What concerns were raised about the cost reduction proposal?",
            "description": "Ambiguity Handling - Multiple perspectives on proposal",
        },
    ]
    
    results = []
    for test in test_cases:
        try:
            result = run_test_query(test["query"], test["description"])
            results.append(result)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            import traceback
            traceback.print_exc()
            results.append({
                "query": test["query"],
                "description": test["description"],
                "answer": f"ERROR: {str(e)}",
                "confidence": 0,
                "episodic_count": 0,
                "valid": False,
            })
        console.print("-" * 60)
    
    console.print("\n")
    summary = Table(title="Test Summary", box=box.DOUBLE)
    summary.add_column("Test", style="cyan", width=40)
    summary.add_column("Confidence", style="yellow", justify="center")
    summary.add_column("Evidence", style="green", justify="center")
    summary.add_column("Valid", style="blue", justify="center")
    
    for r in results:
        conf_style = "green" if r["confidence"] >= 0.7 else ("yellow" if r["confidence"] >= 0.4 else "red")
        summary.add_row(
            r["description"][:40],
            f"[{conf_style}]{r['confidence']*100:.0f}%[/{conf_style}]",
            str(r["episodic_count"]),
            "[green]Yes[/green]" if r["valid"] else "[red]No[/red]",
        )
    
    console.print(summary)
    
    avg_confidence = sum(r["confidence"] for r in results) / len(results) if results else 0
    total_evidence = sum(r["episodic_count"] for r in results)
    valid_count = sum(1 for r in results if r["valid"])
    
    console.print(f"\n[bold]Overall Stats:[/bold]")
    console.print(f"  Average Confidence: {avg_confidence*100:.0f}%")
    console.print(f"  Total Evidence Retrieved: {total_evidence}")
    console.print(f"  Validation Pass Rate: {valid_count}/{len(results)}")

if __name__ == "__main__":
    main()
