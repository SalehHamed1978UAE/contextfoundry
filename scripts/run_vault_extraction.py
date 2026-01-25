#!/usr/bin/env python3
"""
Vault-Centric Multi-Model Extraction Pipeline

This script runs the complete multi-model extraction pipeline on an EXISTING vault:
1. Queries vault via TenantService by name or ID
2. Finds all documents needing extraction
3. Runs multi-model extraction (GPT-4o-mini + Claude Sonnet)
4. Entity resolution and consensus building
5. Validation and conflict resolution
6. KG ingestion

NO corpus configuration required - works directly with vaults.

Usage:
    python scripts/run_vault_extraction.py --vault-name "Claude Code Nexus Industries"
    python scripts/run_vault_extraction.py --vault-id "3dee5dac-37a8-4328-bac3-e074db4df374"
    python scripts/run_vault_extraction.py --vault-name "My Vault" --limit 10
    python scripts/run_vault_extraction.py --vault-name "My Vault" --skip-extraction
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID as UUIDType

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
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

try:
    from platform_foundation.src.tenant_service import TenantService
    HAS_TENANT_SERVICE = True
except ImportError:
    HAS_TENANT_SERVICE = False


def log(msg: str):
    """Print with timestamp and flush."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()


def get_db_session():
    """Get a database session."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def log_extraction_event(
    vault_id: str,
    vault_name: Optional[str],
    doc_id: Optional[str],
    doc_name: Optional[str],
    event_type: str,
    level: str = 'multi',
    details: Optional[str] = None
):
    """Log an extraction event to the database."""
    try:
        session = get_db_session()
        session.execute(text("""
            INSERT INTO platform.extraction_events
            (vault_id, vault_name, document_id, document_name, event_type, extraction_level, details)
            VALUES (:vault_id, :vault_name, :doc_id, :doc_name, :event_type, :level, :details)
        """), {
            "vault_id": vault_id,
            "vault_name": vault_name,
            "doc_id": doc_id,
            "doc_name": doc_name,
            "event_type": event_type,
            "level": level,
            "details": details
        })
        session.commit()
        session.close()
    except Exception as e:
        log(f"Warning: Failed to log extraction event: {e}")


def get_all_vaults() -> List[Dict]:
    """Get all vaults using TenantService."""
    if not HAS_TENANT_SERVICE:
        log("ERROR: TenantService not available")
        return []
    
    tenant_svc = TenantService()
    all_vaults = tenant_svc.list_tenants()
    return [{"id": str(v["id"]), "name": v["name"]} for v in all_vaults]


def find_vault(vault_name: Optional[str] = None, vault_id: Optional[str] = None) -> Optional[Dict]:
    """Find vault (tenant) by name or ID using TenantService."""
    if not HAS_TENANT_SERVICE:
        log("ERROR: TenantService not available")
        return None
    
    vaults = get_all_vaults()
    
    if vault_id:
        for v in vaults:
            if v["id"] == vault_id:
                return v
    elif vault_name:
        for v in vaults:
            if v["name"] == vault_name:
                return v
    
    return None


def get_documents_for_extraction(session, vault_id: str, limit: Optional[int] = None, skip_multi: bool = True) -> List[Dict]:
    """Get documents from vault that need extraction.
    
    Args:
        session: Database session
        vault_id: Vault/tenant ID
        limit: Max documents to return
        skip_multi: If True, skip documents with extraction_level='multi' (resume capability)
    """
    if skip_multi:
        query = """
            SELECT d.id, d.name, d.status, d.mime_type
            FROM platform.documents d
            WHERE d.tenant_id = :vault_id
            AND d.status IN ('queued', 'uploaded', 'chunked', 'extracted')
            AND (d.extraction_level IS NULL OR d.extraction_level != 'multi')
            ORDER BY d.created_at
        """
    else:
        query = """
            SELECT d.id, d.name, d.status, d.mime_type
            FROM platform.documents d
            WHERE d.tenant_id = :vault_id
            AND d.status IN ('queued', 'uploaded', 'chunked')
            ORDER BY d.created_at
        """
    if limit:
        query += f" LIMIT {limit}"
    
    results = session.execute(text(query), {"vault_id": vault_id}).fetchall()
    
    documents = []
    for row in results:
        documents.append({
            "id": str(row[0]),
            "name": row[1],
            "status": row[2],
            "mime_type": row[3],
        })
    return documents


def get_extraction_stats(session, vault_id: str) -> Tuple[int, int, int]:
    """Get extraction resume statistics for a vault.
    
    Returns: (total_docs, already_multi_extracted, remaining)
    """
    total = session.execute(
        text("SELECT COUNT(*) FROM platform.documents WHERE tenant_id = :vault_id"),
        {"vault_id": vault_id}
    ).scalar() or 0
    
    multi_done = session.execute(
        text("SELECT COUNT(*) FROM platform.documents WHERE tenant_id = :vault_id AND extraction_level = 'multi'"),
        {"vault_id": vault_id}
    ).scalar() or 0
    
    remaining = total - multi_done
    return total, multi_done, remaining


def get_document_content(session, doc_id: str) -> Optional[str]:
    """Get document content from chunks or raw storage."""
    chunks = session.execute(
        text("SELECT text FROM document_chunks WHERE document_id = :doc_id ORDER BY chunk_index"),
        {"doc_id": doc_id}
    ).fetchall()
    
    if chunks:
        return "\n\n".join(row[0] for row in chunks if row[0])
    
    raw = session.execute(
        text("SELECT content FROM public.documents WHERE id = :doc_id"),
        {"doc_id": doc_id}
    ).fetchone()
    
    if raw and raw[0]:
        return raw[0]
    
    return None


def run_extraction_from_db(
    session,
    vault_id: str,
    vault_name: str,
    output_dir: str,
    models: List[str],
    limit: int = None
) -> Dict[str, Any]:
    """Run multi-model extraction on documents from database.
    
    Uses resume capability - skips documents already marked with extraction_level='multi'.
    """
    documents = get_documents_for_extraction(session, vault_id, limit, skip_multi=True)
    
    if not documents:
        log("No documents found needing extraction (all may be already processed)")
        return {"total_documents": 0, "total_entities": 0, "total_relationships": 0, "document_ids": []}
    
    log(f"Found {len(documents)} documents needing extraction")
    
    vault_slug = vault_name.lower().replace(" ", "_")
    extractor = MultiModelExtractor(output_dir=output_dir, models=models)
    
    stats = {
        "total_documents": 0,
        "total_entities": 0,
        "total_relationships": 0,
        "document_ids": [],
        "models": {},
        "errors": [],
    }
    
    for i, doc in enumerate(documents, 1):
        doc_id = doc["id"]
        doc_name = doc["name"]
        
        content = get_document_content(session, doc_id)
        if not content:
            log(f"  [{i}/{len(documents)}] Skipping {doc_name}: no content")
            continue
        
        log(f"  [{i}/{len(documents)}] Extracting: {doc_name}")
        
        try:
            doc_info = DocumentInfo(
                document_id=doc_id,
                path=doc_name,
                content=content,
            )
            
            results = extractor.extract_document(doc_info, vault_slug)
            
            for model_name, output in results.items():
                if model_name not in stats["models"]:
                    stats["models"][model_name] = {"entities": 0, "relationships": 0}
                stats["models"][model_name]["entities"] += len(output.entities)
                stats["models"][model_name]["relationships"] += len(output.relationships)
                stats["total_entities"] += len(output.entities)
                stats["total_relationships"] += len(output.relationships)
            
            stats["total_documents"] += 1
            stats["document_ids"].append(doc_id)
            
        except Exception as e:
            log(f"    Error: {e}")
            stats["errors"].append(f"{doc_name}: {str(e)}")
    
    return stats


def run_consensus_and_ingest(
    vault_id: str,
    vault_name: str,
    output_dir: str,
    limit: int = None,
) -> Dict[str, Any]:
    """Run consensus, validation, and ingestion for all extracted documents."""
    vault_slug = vault_name.lower().replace(" ", "_")
    extraction_dir = Path(output_dir) / vault_slug
    
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
        "document_ids": [],
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
            
            ingestor = KGIngestor(session, vault_id)
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
            
            # IMMEDIATELY update extraction_level after each document (resume capability)
            try:
                session.execute(
                    text("UPDATE platform.documents SET extraction_level = 'multi', multi_extracted_at = NOW(), updated_at = NOW() WHERE id = :doc_id"),
                    {"doc_id": doc_id}
                )
                session.commit()
                
                # Log per-document completion event
                log_extraction_event(vault_id, vault_name, doc_id, None, 'completed')
            except Exception as update_err:
                log(f"  Warning: Failed to update extraction_level for {doc_id}: {update_err}")
            
            stats["documents_processed"] += 1
            stats["document_ids"].append(doc_id)
            
            if stats["documents_processed"] % 10 == 0:
                log(f"  Processed {stats['documents_processed']}/{len(doc_files)} documents...")
                
        except Exception as e:
            log(f"  Error processing {doc_id}: {e}")
            stats["errors"].append(f"{doc_id}: {str(e)}")
            
            # Log failure event
            log_extraction_event(
                vault_id, vault_name, doc_id, None, 'failed',
                details=str(e)[:500]
            )
    
    session.close()
    
    if stats["quality_scores"]:
        stats["avg_quality_score"] = sum(stats["quality_scores"]) / len(stats["quality_scores"])
    
    entity_reduction = 0
    if stats["total_entities_input"] > 0:
        entity_reduction = 1 - (stats["total_entities_consensus"] / stats["total_entities_input"])
    stats["entity_reduction_pct"] = round(entity_reduction * 100, 1)
    
    return stats


def list_vaults():
    """List all available vaults (tenants)."""
    vaults = get_all_vaults()
    
    log("Available vaults:")
    for v in vaults:
        log(f"  - {v['name']} (ID: {v['id']})")
    return vaults


def run_full_pipeline(
    vault_name: Optional[str] = None,
    vault_id: Optional[str] = None,
    output_dir: str = "extraction_outputs",
    models: Optional[List[str]] = None,
    limit: Optional[int] = None,
    skip_extraction: bool = False,
    list_only: bool = False,
):
    """Run the full multi-model extraction pipeline on a vault."""
    if models is None:
        models = ["gpt-4o-mini", "claude-sonnet"]
    
    session = get_db_session()
    
    if list_only:
        list_vaults()
        session.close()
        return
    
    log("=" * 70)
    log("VAULT-CENTRIC MULTI-MODEL EXTRACTION")
    log("=" * 70)
    
    vault = find_vault(vault_name=vault_name, vault_id=vault_id)
    if not vault:
        log(f"ERROR: Vault not found")
        if vault_name:
            log(f"  Searched for name: '{vault_name}'")
        if vault_id:
            log(f"  Searched for ID: '{vault_id}'")
        log("")
        list_vaults()
        session.close()
        return
    
    vault_id = vault["id"]
    vault_name = vault["name"]
    
    log(f"Vault: {vault_name}")
    log(f"Vault ID: {vault_id}")
    
    # Show resume status
    total_docs, multi_done, remaining = get_extraction_stats(session, vault_id)
    log("")
    log("=" * 40)
    log("EXTRACTION RESUME STATUS")
    log("=" * 40)
    log(f"Total documents: {total_docs}")
    log(f"Already multi-extracted: {multi_done}")
    log(f"Remaining to process: {remaining}")
    log("=" * 40)
    log("")
    
    if remaining == 0:
        log("All documents already have multi-model extraction complete!")
        log("Use --skip-extraction to only run consensus/ingestion on existing extractions.")
        session.close()
        return
    
    doc_count = len(get_documents_for_extraction(session, vault_id, skip_multi=True))
    log(f"Documents pending extraction: {doc_count}")
    if limit:
        log(f"Limit: {limit} documents")
    
    # Log start/resume event
    if multi_done > 0:
        log_extraction_event(
            vault_id, vault_name, None, None, 'resumed',
            details=f"Resuming from {multi_done}/{total_docs} ({remaining} remaining)"
        )
    else:
        log_extraction_event(
            vault_id, vault_name, None, None, 'started',
            details=f"Starting multi-model extraction for {doc_count} documents"
        )
    
    if not skip_extraction:
        log("")
        log("-" * 70)
        log("PHASE 1: Multi-Model Extraction")
        log("-" * 70)
        
        extraction_summary = run_extraction_from_db(
            session, vault_id, vault_name, output_dir, models, limit
        )
        
        log(f"Extraction complete:")
        log(f"  Total documents: {extraction_summary.get('total_documents', 0)}")
        log(f"  Total entities: {extraction_summary.get('total_entities', 0)}")
        log(f"  Total relationships: {extraction_summary.get('total_relationships', 0)}")
        if extraction_summary.get("errors"):
            log(f"  Errors: {len(extraction_summary['errors'])}")
    else:
        log("")
        log("Skipping extraction (--skip-extraction flag)")
    
    session.close()
    
    log("")
    log("-" * 70)
    log("PHASE 2-4: Consensus, Validation & Ingestion")
    log("-" * 70)
    
    ingest_stats = run_consensus_and_ingest(vault_id, vault_name, output_dir, limit)
    
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
    
    # Log vault completion event
    log_extraction_event(
        vault_id, vault_name, None, None, 'vault_complete',
        details=f"All {ingest_stats['documents_processed']} documents multi-model extracted. "
                f"Entities: {ingest_stats['total_entities_created']}, "
                f"Relationships: {ingest_stats['total_relationships_created']}"
    )
    
    session = get_db_session()
    try:
        doc_ids = ingest_stats.get('document_ids', [])
        if doc_ids:
            log(f"Updating extraction_level to 'multi' for {len(doc_ids)} documents...")
            session.execute(text("""
                UPDATE platform.documents
                SET extraction_level = 'multi', updated_at = NOW()
                WHERE id = ANY(:doc_ids)
            """), {"doc_ids": doc_ids})
            session.commit()
            log("Extraction level updated successfully.")
    except Exception as e:
        log(f"Warning: Failed to update extraction_level: {e}")
    finally:
        session.close()
    
    vault_slug = vault_name.lower().replace(" ", "_")
    summary_dir = Path(output_dir) / vault_slug
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "pipeline_summary.json"
    
    with open(summary_path, 'w') as f:
        json.dump({
            **ingest_stats,
            "vault_name": vault_name,
            "vault_id": vault_id,
            "models": models,
            "completed_at": datetime.utcnow().isoformat(),
        }, f, indent=2, default=str)
    
    log(f"\nSummary saved to: {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Vault-Centric Multi-Model Extraction Pipeline",
        epilog="Example: python scripts/run_vault_extraction.py --vault-name 'My Vault'"
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--vault-name", type=str, help="Name of the vault to process")
    group.add_argument("--vault-id", type=str, help="UUID of the vault to process")
    group.add_argument("--list", action="store_true", help="List all available vaults")
    
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
        help="Limit number of documents to process"
    )
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip extraction, only run consensus/validation/ingestion"
    )
    
    args = parser.parse_args()
    
    if args.list:
        run_full_pipeline(list_only=True)
    elif args.vault_name or args.vault_id:
        run_full_pipeline(
            vault_name=args.vault_name,
            vault_id=args.vault_id,
            output_dir=args.output_dir,
            models=args.models,
            limit=args.limit,
            skip_extraction=args.skip_extraction,
        )
    else:
        parser.print_help()
        print("\nError: Must specify --vault-name, --vault-id, or --list")
        sys.exit(1)


if __name__ == "__main__":
    main()
