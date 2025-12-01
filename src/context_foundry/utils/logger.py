"""
Comprehensive logging system for Context Foundry.
Logs EVERYTHING - every query, retrieval, rule check, confidence score.
Silent failures are the enemy.
"""
import logging
import json
import os
from datetime import datetime
from typing import Any, Optional
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

console = Console()

file_handler = logging.FileHandler(
    f"{LOG_DIR}/context_foundry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)
file_handler.setFormatter(
    logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(console=console, rich_tracebacks=True, show_path=False),
        file_handler
    ]
)

logger = logging.getLogger("context_foundry")


class QueryLogger:
    """Structured logging for query execution pipeline."""
    
    def __init__(self, query_id: str, query_text: str):
        self.query_id = query_id
        self.query_text = query_text
        self.start_time = datetime.now()
        self.events = []
        self.log_event("QUERY_START", {"query": query_text})
    
    def log_event(self, event_type: str, data: dict, level: str = "INFO"):
        event = {
            "timestamp": datetime.now().isoformat(),
            "query_id": self.query_id,
            "event_type": event_type,
            "data": data
        }
        self.events.append(event)
        
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"[{self.query_id[:8]}] {event_type}: {json.dumps(data, default=str)}")
    
    def log_semantic_retrieval(self, entities: list, relationships: list, confidence: float):
        self.log_event("SEMANTIC_RETRIEVAL", {
            "entities_count": len(entities),
            "relationships_count": len(relationships),
            "entities": [e.get("name", str(e)) if isinstance(e, dict) else str(e) for e in entities[:5]],
            "confidence": confidence
        })
    
    def log_episodic_retrieval(self, documents: list, similarity_scores: list):
        self.log_event("EPISODIC_RETRIEVAL", {
            "documents_count": len(documents),
            "top_similarity": max(similarity_scores) if similarity_scores else 0,
            "avg_similarity": sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0
        })
    
    def log_symbolic_check(self, rules_checked: list, rules_passed: list, violations: list):
        self.log_event("SYMBOLIC_CHECK", {
            "rules_checked": len(rules_checked),
            "rules_passed": len(rules_passed),
            "violations_count": len(violations),
            "violation_details": violations
        }, level="WARNING" if violations else "INFO")
    
    def log_context_bundle(self, bundle: dict):
        self.log_event("CONTEXT_BUNDLE_BUILT", {
            "semantic_items": bundle.get("semantic_count", 0),
            "episodic_items": bundle.get("episodic_count", 0),
            "rules_count": bundle.get("rules_count", 0),
            "overall_confidence": bundle.get("confidence", 0)
        })
    
    def log_reasoning(self, response: str, confidence: float, evidence_chain: list):
        self.log_event("REASONING_COMPLETE", {
            "response_length": len(response),
            "confidence": confidence,
            "evidence_items": len(evidence_chain)
        })
    
    def log_validation(self, passed: bool, issues: list):
        self.log_event("VALIDATION", {
            "passed": passed,
            "issues": issues
        }, level="WARNING" if not passed else "INFO")
    
    def log_error(self, error_type: str, error_message: str, context: dict = None):
        self.log_event("ERROR", {
            "error_type": error_type,
            "message": error_message,
            "context": context or {}
        }, level="ERROR")
    
    def log_complete(self, success: bool, final_confidence: float):
        duration = (datetime.now() - self.start_time).total_seconds()
        self.log_event("QUERY_COMPLETE", {
            "success": success,
            "duration_seconds": duration,
            "final_confidence": final_confidence,
            "total_events": len(self.events)
        })
        return self.get_summary()
    
    def get_summary(self) -> dict:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "start_time": self.start_time.isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "events": self.events
        }


def display_context_bundle(bundle: dict):
    """Rich display of a ContextBundle for CLI output."""
    console.print("\n")
    console.print(Panel.fit(
        f"[bold cyan]ContextBundle[/bold cyan]\n"
        f"Query ID: {bundle.get('query_id', 'N/A')}\n"
        f"Overall Confidence: {bundle.get('confidence', 0):.2%}",
        title="Context Foundry"
    ))
    
    if bundle.get("semantic_memory"):
        table = Table(title="Semantic Memory (Knowledge Graph)")
        table.add_column("Entity/Relationship", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Lifecycle", style="yellow")
        table.add_column("Confidence", style="magenta")
        
        for item in bundle["semantic_memory"][:10]:
            table.add_row(
                str(item.get("name", item.get("type", "Unknown"))),
                item.get("entity_type", item.get("rel_type", "N/A")),
                item.get("lifecycle_state", "N/A"),
                f"{item.get('confidence', 0):.2%}"
            )
        console.print(table)
    
    if bundle.get("episodic_memory"):
        table = Table(title="Episodic Memory (Vector Search)")
        table.add_column("Document", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Similarity", style="magenta")
        
        for item in bundle["episodic_memory"][:5]:
            table.add_row(
                item.get("title", "Unknown")[:50],
                item.get("doc_type", "N/A"),
                f"{item.get('similarity', 0):.2%}"
            )
        console.print(table)
    
    if bundle.get("symbolic_memory"):
        table = Table(title="Symbolic Memory (Rules)")
        table.add_column("Rule", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Priority", style="yellow")
        
        for item in bundle["symbolic_memory"][:5]:
            table.add_row(
                item.get("name", "Unknown"),
                item.get("rule_type", "N/A"),
                str(item.get("priority", "N/A"))
            )
        console.print(table)


def display_response(response: dict):
    """Rich display of a reasoning response."""
    confidence = response.get("confidence", 0)
    confidence_color = "green" if confidence >= 0.7 else "yellow" if confidence >= 0.5 else "red"
    
    console.print("\n")
    console.print(Panel(
        f"[bold]{response.get('answer', 'No answer generated')}[/bold]",
        title=f"Response (Confidence: [{confidence_color}]{confidence:.2%}[/{confidence_color}])",
        border_style=confidence_color
    ))
    
    if response.get("evidence_chain"):
        console.print("\n[bold]Evidence Chain:[/bold]")
        for i, evidence in enumerate(response["evidence_chain"], 1):
            console.print(f"  {i}. [{evidence.get('type', 'Unknown')}] {evidence.get('description', 'N/A')}")
            if evidence.get("source"):
                console.print(f"     Source: {evidence['source']}")
    
    if response.get("uncertainty"):
        console.print("\n[bold yellow]Uncertainty Notes:[/bold yellow]")
        for reason in response["uncertainty"].get("reasons", []):
            console.print(f"  - {reason}")
    
    if response.get("rules_violations"):
        console.print("\n[bold red]Rule Violations:[/bold red]")
        for violation in response["rules_violations"]:
            console.print(f"  ! {violation}")
