#!/usr/bin/env python3
"""
Ingest synthetic test documents into Context Foundry's episodic memory.
"""

from pathlib import Path
from src.context_foundry.ingestion.ingestion_pipeline import IngestionPipeline
from src.context_foundry.memory.episodic import EpisodicMemory
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

def determine_doc_type(path: str) -> str:
    """Determine document type from path."""
    if "meetings" in path:
        return "MEETING_NOTES"
    elif "emails" in path:
        return "EMAIL_THREAD"
    elif "strategy" in path:
        return "STRATEGY_DOC"
    elif "slack" in path:
        return "SLACK_EXPORT"
    else:
        return "DOCUMENT"

def main():
    console.print("\n[bold cyan]Context Foundry: Synthetic Document Ingestion[/bold cyan]\n")
    
    synthetic_dir = Path("test_data/synthetic_docs")
    if not synthetic_dir.exists():
        console.print(f"[red]Directory not found: {synthetic_dir}[/red]")
        return
    
    pipeline = IngestionPipeline(
        max_tokens=512,
        overlap_sentences=1,
        min_chunk_size=50,
    )
    
    episodic = EpisodicMemory()
    
    console.print("[dim]Loading and chunking documents...[/dim]")
    ingested, stats = pipeline.ingest_directory(str(synthetic_dir), recursive=True)
    
    console.print(f"\n[green]Loaded {len(ingested)} documents[/green]")
    console.print(f"  - Total chunks: {stats.total_chunks}")
    console.print(f"  - Total sentences: {stats.total_sentences}")
    console.print(f"  - Total tokens: {stats.total_tokens}")
    
    console.print("\n[dim]Storing documents in episodic memory...[/dim]")
    
    docs_added = 0
    chunks_added = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing documents...", total=len(ingested))
        
        for ingested_doc in ingested:
            doc = ingested_doc.document
            doc_type = determine_doc_type(doc.source_path)
            
            episodic.add_document(
                title=doc.title,
                doc_type=doc_type,
                content=doc.content,
                metadata={
                    "source_path": doc.source_path,
                    "file_type": doc.file_type,
                    "word_count": doc.metadata.get("word_count", 0),
                    "ingestion_type": "synthetic_test_data",
                },
                source_document_id=doc.id,
            )
            docs_added += 1
            
            for chunk in ingested_doc.chunks:
                episodic.add_document(
                    title=f"{doc.title} - Chunk {chunk.chunk_id.split('_')[-1]}",
                    doc_type=f"{doc_type}_CHUNK",
                    content=chunk.content,
                    metadata={
                        "source_document": doc.title,
                        "chunk_id": chunk.chunk_id,
                        "start_sentence": chunk.start_sentence,
                        "end_sentence": chunk.end_sentence,
                        "token_count": chunk.token_count,
                    },
                    source_document_id=doc.id,
                )
                chunks_added += 1
            
            progress.update(task, advance=1, description=f"Processing: {doc.title[:40]}...")
    
    console.print(f"\n[bold green]Ingestion Complete![/bold green]")
    console.print(f"  - Documents added: {docs_added}")
    console.print(f"  - Chunks added: {chunks_added}")
    console.print(f"  - Total items in episodic memory: {docs_added + chunks_added}")
    
    console.print("\n[dim]Sample queries to test:[/dim]")
    console.print('  - "What decisions were made about the cloud migration?"')
    console.print('  - "What concerns has Mia White raised recently?"')
    console.print('  - "Has our position on vendor selection changed?"')
    console.print('  - "What\'s the status of the cost reduction initiative?"')
    console.print()

if __name__ == "__main__":
    main()
