#!/usr/bin/env python3
"""
Multi-Model Extraction Batch Runner

This script runs the multi-model extraction pipeline on documents
in a specified directory or corpus.

Usage:
    python scripts/run_multi_extraction.py --corpus "Manus Orion"
    python scripts/run_multi_extraction.py --directory "test documents/Manus Orion/documents"
    python scripts/run_multi_extraction.py --file "test documents/Manus Orion/documents/strategy_doc_001.md"
"""

import argparse
import json
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.context_foundry.extraction.multi_extractor import (
    MultiModelExtractor,
    DocumentInfo,
)


CORPUS_PATHS = {
    "Manus Orion": "test documents/Manus Orion",
    "Manus Medsync": "test documents/Manus Medsync",
    "Manus Healthtec": "test documents/Manus Healthtec",
    "ClaudeCode Medsync": "test documents/ClaudeCode Medsync",
    "Codex Horizon_Nexus": "test documents/Codex Horizon_Nexus",
}

DOCUMENT_EXTENSIONS = [".md", ".txt", ".html", ".json"]


def extract_corpus(corpus_name: str, models: list, output_dir: str, limit: int = None):
    """Extract from all documents in a corpus."""
    if corpus_name not in CORPUS_PATHS:
        print(f"Unknown corpus: {corpus_name}")
        print(f"Available corpora: {list(CORPUS_PATHS.keys())}")
        return None
    
    corpus_path = Path(CORPUS_PATHS[corpus_name])
    if not corpus_path.exists():
        print(f"Corpus path not found: {corpus_path}")
        return None
    
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
                print(f"Error loading {file_path}: {e}")
    
    if limit:
        documents = documents[:limit]
    
    print(f"\n{'='*60}")
    print(f"MULTI-MODEL EXTRACTION: {corpus_name}")
    print(f"{'='*60}")
    print(f"Documents: {len(documents)}")
    print(f"Models: {models}")
    print(f"Output: {output_dir}/{vault_id}/")
    print(f"{'='*60}\n")
    
    results = extractor.extract_batch(documents, vault_id)
    
    summary = extractor.get_extraction_summary(vault_id)
    
    print(f"\n{'='*60}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"Total documents: {summary['total_documents']}")
    print(f"Total entities: {summary['total_entities']}")
    print(f"Total relationships: {summary['total_relationships']}")
    print("\nBy model:")
    for model, stats in summary.get('models', {}).items():
        print(f"  {model}: {stats['entities']} entities, {stats['relationships']} relationships")
    print(f"{'='*60}\n")
    
    summary_path = Path(output_dir) / vault_id / "extraction_summary.json"
    with open(summary_path, 'w') as f:
        json.dump({
            **summary,
            "extraction_completed_at": datetime.utcnow().isoformat(),
            "corpus": corpus_name,
        }, f, indent=2)
    
    return summary


def extract_directory(directory: str, models: list, output_dir: str, limit: int = None):
    """Extract from all documents in a directory."""
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"Directory not found: {directory}")
        return None
    
    vault_id = dir_path.name.lower().replace(" ", "_")
    
    extractor = MultiModelExtractor(output_dir=output_dir, models=models)
    results = extractor.extract_from_directory(directory, vault_id, DOCUMENT_EXTENSIONS)
    
    summary = extractor.get_extraction_summary(vault_id)
    print(f"\nExtraction complete: {summary}")
    
    return summary


def extract_single_file(file_path: str, models: list, output_dir: str):
    """Extract from a single file."""
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        return None
    
    vault_id = "single_file"
    
    doc = DocumentInfo.from_file(file_path)
    
    extractor = MultiModelExtractor(output_dir=output_dir, models=models)
    results = extractor.extract_document(doc, vault_id)
    
    print(f"\nExtraction results:")
    for model, output in results.items():
        print(f"  {model}: {len(output.entities)} entities, {len(output.relationships)} relationships")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Multi-Model Extraction Batch Runner")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--corpus", type=str, help="Corpus name to extract")
    group.add_argument("--directory", type=str, help="Directory to extract from")
    group.add_argument("--file", type=str, help="Single file to extract")
    
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
    
    args = parser.parse_args()
    
    if args.corpus:
        extract_corpus(args.corpus, args.models, args.output_dir, args.limit)
    elif args.directory:
        extract_directory(args.directory, args.models, args.output_dir, args.limit)
    elif args.file:
        extract_single_file(args.file, args.models, args.output_dir)


if __name__ == "__main__":
    main()
