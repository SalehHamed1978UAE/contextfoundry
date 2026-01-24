#!/usr/bin/env python3
"""
Full Corpus Multi-Model Extraction Pipeline

This script runs the complete multi-model extraction pipeline on a corpus:
1. Multi-model extraction (GPT-4o-mini + Claude Sonnet)
2. Entity resolution and consensus building
3. Validation and conflict resolution
4. KG ingestion

Usage:
    python scripts/run_full_corpus_pipeline.py --corpus "Manus Orion"
    python scripts/run_full_corpus_pipeline.py --corpus "Manus Orion" --limit 10
    python scripts/run_full_corpus_pipeline.py --corpus "Manus Orion" --skip-extraction
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.context_foundry.extraction.multi_extractor import (
    MultiModelExtractor,
    DocumentInfo,
)
from src.context_foundry.extraction.entity_resolver import (
    run_consensus,
    ConsensusOutput,
)
from src.context_foundry.extraction.consensus_validator import (
    validate_consensus,
    resolve_conflicts,
)
from src.context_foundry.extraction.kg_ingestor import (
    KGIngestor,
    IngestionResult,
)
from src.context_foundry.models.schema import LifecycleState


CORPUS_PATHS = {
    "Manus Orion": "test documents/Manus Orion",
    "Manus Medsync": "test documents/Manus Medsync",
    "Manus Healthtec": "test documents/Manus Healthtec",
    "ClaudeCode Medsync": "test documents/ClaudeCode Medsync",
}

DOCUMENT_EXTENSIONS = [".md", ".txt", ".html", ".json"]


def log(msg: str):
    """Print with timestamp and flush."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()


def get_vault_id(corpus_name: str) -> Optional[str]:
    """Get vault ID for a corpus from the test config."""
    config_path = Path(__file__).parent.parent / "src" / "test_config.json"
    if not config_path.exists():
        log(f"Config file not found: {config_path}")
        return None
    
    with open(config_path) as f:
        config = json.load(f)
    
    corpus_config = config.get("corpora", {}).get(corpus_name)
    if corpus_config:
        return corpus_config.get("current_vault_id")
    return None


def get_db_session():
    """Get a database session."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def count_documents(corpus_name: str) -> int:
    """Count documents in a corpus directory."""
    corpus_path = Path(CORPUS_PATHS.get(corpus_name, ""))
    if not corpus_path.exists():
        return 0
    
    count = 0
    for ext in DOCUMENT_EXTENSIONS:
        for file_path in corpus_path.rglob(f"*{ext}"):
            if file_path.name.startswith("README"):
                continue
            if "question_sets" in str(file_path):
                continue
            count += 1
    return count


def run_extraction(corpus_name: str, output_dir: str, models: List[str], limit: int = None) -> Dict[str, Any]:
    """Run multi-model extraction on all documents."""
    corpus_path = Path(CORPUS_PATHS[corpus_name])
    vault_id = corpus_name.lower().replace(" ", "_")
    
    extractor = MultiModelExtractor(output_dir=output_dir, models=models)
    
    documents = []
    for ext in DOCUMENT_EXTENSIONS:
        for file_path in corpus_path.rglob(f"*{ext}"):
            if file_path.name.startswith("README"):
                continue
            if "question_sets" in str(file_path):
                continue
            try:
                doc = DocumentInfo.from_file(str(file_path))
                documents.append(doc)
            except Exception as e:
                log(f"  Error loading {file_path}: {e}")
    
    if limit:
        documents = documents[:limit]
    
    log(f"Extracting from {len(documents)} documents with models: {models}")
    
    results = extractor.extract_batch(documents, vault_id)
    summary = extractor.get_extraction_summary(vault_id)
    
    return summary


def run_consensus_and_ingest(
    corpus_name: str,
    output_dir: str,
    tenant_id: str,
    limit: int = None,
) -> Dict[str, Any]:
    """Run consensus, validation, and ingestion for all extracted documents."""
    vault_id = corpus_name.lower().replace(" ", "_")
    extraction_dir = Path(output_dir) / vault_id
    
    if not extraction_dir.exists():
        log(f"ERROR: Extraction directory not found: {extraction_dir}")
        return {"error": "No extractions found"}
    
    model_dirs = [d for d in extraction_dir.iterdir() if d.is_dir() and d.name != "consensus"]
    if len(model_dirs) < 2:
        log(f"ERROR: Need at least 2 model outputs, found: {[d.name for d in model_dirs]}")
        return {"error": "Insufficient model outputs"}
    
    log(f"Found model outputs: {[d.name for d in model_dirs]}")
    
    first_model_dir = model_dirs[0]
    doc_files = list(first_model_dir.glob("*.json"))
    if limit:
        doc_files = doc_files[:limit]
    
    log(f"Processing {len(doc_files)} documents for consensus and ingestion")
    
    session = get_db_session()
    
    stats = {
        "documents_processed": 0,
        "total_entities_input": 0,
        "total_entities_consensus": 0,
        "total_entities_created": 0,
        "total_entities_updated": 0,
        "total_relationships_created": 0,
        "total_relationships_updated": 0,
        "errors": [],
        "quality_scores": [],
    }
    
    for doc_file in doc_files:
        doc_id = doc_file.stem
        
        extractions = {}
        for model_dir in model_dirs:
            model_file = model_dir / f"{doc_id}.json"
            if model_file.exists():
                try:
                    with open(model_file) as f:
                        extractions[model_dir.name] = json.load(f)
                except Exception as e:
                    log(f"  Error loading {model_file}: {e}")
        
        if len(extractions) < 2:
            log(f"  Skipping {doc_id}: insufficient model outputs")
            continue
        
        try:
            total_input = sum(len(e.get("entities", [])) for e in extractions.values())
            stats["total_entities_input"] += total_input
            
            consensus = run_consensus(extractions, doc_id)
            stats["total_entities_consensus"] += len(consensus.entities)
            
            report = validate_consensus(consensus)
            if report.conflicts:
                consensus = resolve_conflicts(consensus, report)
                report = validate_consensus(consensus)
            
            stats["quality_scores"].append(report.quality.overall_score)
            
            ingestor = KGIngestor(session, tenant_id)
            result = ingestor.ingest(
                consensus,
                validation_report=report,
                lifecycle_state=LifecycleState.STAGING,
                source_document_id=doc_id,
            )
            
            stats["total_entities_created"] += result.entities_created
            stats["total_entities_updated"] += result.entities_updated
            stats["total_relationships_created"] += result.relationships_created
            stats["total_relationships_updated"] += result.relationships_updated
            
            if result.errors:
                stats["errors"].extend(result.errors)
            
            stats["documents_processed"] += 1
            
            if stats["documents_processed"] % 10 == 0:
                log(f"  Processed {stats['documents_processed']}/{len(doc_files)} documents...")
                
        except Exception as e:
            log(f"  Error processing {doc_id}: {e}")
            stats["errors"].append(f"{doc_id}: {str(e)}")
    
    session.close()
    
    if stats["quality_scores"]:
        stats["avg_quality_score"] = sum(stats["quality_scores"]) / len(stats["quality_scores"])
    
    entity_reduction = 0
    if stats["total_entities_input"] > 0:
        entity_reduction = 1 - (stats["total_entities_consensus"] / stats["total_entities_input"])
    stats["entity_reduction_pct"] = round(entity_reduction * 100, 1)
    
    return stats


def run_full_pipeline(
    corpus_name: str,
    output_dir: str = "extraction_outputs",
    models: List[str] = None,
    limit: int = None,
    skip_extraction: bool = False,
):
    """Run the full multi-model extraction pipeline."""
    if models is None:
        models = ["gpt-4o-mini", "claude-sonnet"]
    
    log("=" * 70)
    log(f"FULL CORPUS PIPELINE: {corpus_name}")
    log("=" * 70)
    
    if corpus_name not in CORPUS_PATHS:
        log(f"ERROR: Unknown corpus: {corpus_name}")
        log(f"Available: {list(CORPUS_PATHS.keys())}")
        return
    
    tenant_id = get_vault_id(corpus_name)
    if not tenant_id:
        log(f"ERROR: No vault found for '{corpus_name}'. Run the test runner first to create it.")
        return
    
    log(f"Vault ID: {tenant_id}")
    
    doc_count = count_documents(corpus_name)
    log(f"Documents in corpus: {doc_count}")
    if limit:
        log(f"Limit: {limit} documents")
    
    if not skip_extraction:
        log("")
        log("-" * 70)
        log("PHASE 1: Multi-Model Extraction")
        log("-" * 70)
        
        extraction_summary = run_extraction(corpus_name, output_dir, models, limit)
        
        log(f"Extraction complete:")
        log(f"  Total documents: {extraction_summary.get('total_documents', 0)}")
        log(f"  Total entities: {extraction_summary.get('total_entities', 0)}")
        log(f"  Total relationships: {extraction_summary.get('total_relationships', 0)}")
    else:
        log("")
        log("Skipping extraction (--skip-extraction flag)")
    
    log("")
    log("-" * 70)
    log("PHASE 2-4: Consensus, Validation & Ingestion")
    log("-" * 70)
    
    ingest_stats = run_consensus_and_ingest(corpus_name, output_dir, tenant_id, limit)
    
    if "error" in ingest_stats:
        log(f"ERROR: {ingest_stats['error']}")
        return
    
    log("")
    log("=" * 70)
    log("PIPELINE COMPLETE")
    log("=" * 70)
    log(f"Documents processed: {ingest_stats['documents_processed']}")
    log(f"Entity reduction: {ingest_stats['total_entities_input']} -> {ingest_stats['total_entities_consensus']} ({ingest_stats['entity_reduction_pct']}% reduction)")
    log(f"Entities created: {ingest_stats['total_entities_created']}")
    log(f"Entities updated: {ingest_stats['total_entities_updated']}")
    log(f"Relationships created: {ingest_stats['total_relationships_created']}")
    log(f"Relationships updated: {ingest_stats['total_relationships_updated']}")
    log(f"Average quality score: {ingest_stats.get('avg_quality_score', 0):.3f}")
    if ingest_stats['errors']:
        log(f"Errors: {len(ingest_stats['errors'])}")
    log("=" * 70)
    
    summary_path = Path(output_dir) / corpus_name.lower().replace(" ", "_") / "pipeline_summary.json"
    with open(summary_path, 'w') as f:
        json.dump({
            **ingest_stats,
            "corpus": corpus_name,
            "tenant_id": tenant_id,
            "models": models,
            "completed_at": datetime.utcnow().isoformat(),
        }, f, indent=2, default=str)
    
    log(f"\nSummary saved to: {summary_path}")
    log("\nNext step: Run the Q&A test to measure accuracy:")
    log(f"  python -m src.test_runner.runner --corpus \"{corpus_name}\" --questions-only")


def main():
    parser = argparse.ArgumentParser(description="Full Corpus Multi-Model Extraction Pipeline")
    
    parser.add_argument("--corpus", type=str, required=True, help="Corpus name to process")
    parser.add_argument(
        "--models",
        type=str,
        nargs="+",
        default=["gpt-4o-mini", "claude-sonnet"],
        help="Models to use for extraction"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="extraction_outputs",
        help="Output directory for extraction results"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of documents to process (for testing)"
    )
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip extraction, only run consensus/validation/ingestion"
    )
    
    args = parser.parse_args()
    
    run_full_pipeline(
        corpus_name=args.corpus,
        output_dir=args.output_dir,
        models=args.models,
        limit=args.limit,
        skip_extraction=args.skip_extraction,
    )


if __name__ == "__main__":
    main()
