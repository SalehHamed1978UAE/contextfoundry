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
import struct
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID as UUIDType
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.context_foundry.extraction.multi_extractor import (
    MultiModelExtractor,
    DocumentInfo,
)
# Piece 1 — Document Classification in Production Extraction Path.
# Wraps brain/classifier (domain) + extraction/document_classifier (type).
# Never raises; failure is reported via classification_status='failed'.
from brain.classification_wrapper import (
    classify as classify_document,
    ClassificationResult,
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
from src.context_foundry.extraction.ontology_centric_pipeline import (
    OntologyCentricPipeline,
    OntologyCentricResult,
)
from src.context_foundry.models.schema import LifecycleState
from src.context_foundry.ingestion.document_loader import DocumentLoader
from src.context_foundry.monitoring.vault_consistency import build_vault_preflight_report
from src.context_foundry.workers.verification_worker import VerificationWorker
from src.context_foundry.agents.gardener import GardenerAgent, GardenerConfig

try:
    from platform_foundation.src.tenant_service import TenantService
    HAS_TENANT_SERVICE = True
except ImportError:
    HAS_TENANT_SERVICE = False


def vault_lock_key(vault_uuid_str: str) -> int:
    clean = vault_uuid_str.replace('-', '')
    first_8_bytes = bytes.fromhex(clean[:16])
    return struct.unpack('>q', first_8_bytes)[0]


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


def _persist_classification(session, document_id: str, result: "ClassificationResult") -> None:
    """Persist a Piece 1 classification result to the 8 platform.documents
    classification columns added by the 2026-05 migration.

    Wrapped in its own try/except by the caller — DB errors here MUST NOT
    stop the production extraction loop. Caller logs the failure and
    proceeds to extract_document with the classification still attached
    via DocumentInfo.metadata for downstream visibility.
    """
    session.execute(
        text("""
            UPDATE platform.documents
            SET primary_domain            = :primary_domain,
                secondary_domains         = CAST(:secondary_domains AS jsonb),
                document_type             = :document_type,
                classification_confidence = :classification_confidence,
                classifier_version        = :classifier_version,
                classification_evidence   = :classification_evidence,
                classification_status     = :classification_status,
                classification_error      = :classification_error
            WHERE id = :doc_id
        """),
        {
            "doc_id": document_id,
            "primary_domain": result.primary_domain,
            "secondary_domains": json.dumps(result.secondary_domains),
            "document_type": result.document_type,
            "classification_confidence": result.classification_confidence,
            "classifier_version": result.classifier_version,
            "classification_evidence": result.classification_evidence,
            "classification_status": result.classification_status,
            "classification_error": result.classification_error,
        },
    )
    session.commit()


def get_documents_for_extraction(
    session,
    vault_id: str,
    limit: Optional[int] = None,
    skip_multi: bool = True,
    use_ontology: bool = False
) -> List[Dict]:
    """Get documents from vault that need extraction.

    Args:
        session: Database session
        vault_id: Vault/tenant ID
        limit: Max documents to return
        skip_multi: If True, skip documents with extraction_level='multi' (resume capability)
        use_ontology: If True, skip documents with extraction_level='ontology' (ontology resume)
    """
    if use_ontology:
        # For ontology mode: skip docs already extracted at ontology level
        query = """
            SELECT d.id, d.name, d.status, d.mime_type, d.storage_path, d.original_filename
            FROM platform.documents d
            WHERE d.tenant_id = :vault_id
            AND d.status IN ('queued', 'uploaded', 'chunked', 'extracted')
            AND (d.extraction_level IS NULL OR d.extraction_level != 'ontology')
            ORDER BY d.created_at
        """
    elif skip_multi:
        # Existing multi-model resume logic
        query = """
            SELECT d.id, d.name, d.status, d.mime_type, d.storage_path, d.original_filename
            FROM platform.documents d
            WHERE d.tenant_id = :vault_id
            AND d.status IN ('queued', 'uploaded', 'chunked', 'extracted')
            AND (d.extraction_level IS NULL OR d.extraction_level != 'multi')
            ORDER BY d.created_at
        """
    else:
        # No resume
        query = """
            SELECT d.id, d.name, d.status, d.mime_type, d.storage_path, d.original_filename
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
            "storage_path": row[4],
            "original_filename": row[5],
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


def _read_text_from_storage(storage_path: Optional[str], file_name: Optional[str], mime_type: Optional[str]) -> Optional[str]:
    """Read text directly from storage_path as a last-resort content fallback."""
    if not storage_path:
        return None
    if not os.path.exists(storage_path):
        return None

    loader = DocumentLoader()
    ext = (Path(file_name).suffix.lower() if file_name else "")

    try:
        if ext == ".pdf":
            return loader.load_pdf(storage_path).content
        if ext == ".docx":
            return loader.load_docx(storage_path).content
        if ext in {".xlsx", ".xls", ".csv"}:
            try:
                from src.context_foundry.extraction.spreadsheet_loader import SpreadsheetLoader

                spreadsheet = SpreadsheetLoader().load(storage_path, original_filename=file_name or "spreadsheet")
                if spreadsheet.raw_text:
                    return spreadsheet.raw_text
                return "\n\n".join(t.markdown for t in spreadsheet.tables if t.markdown)
            except Exception:
                pass
        if ext in {".txt", ".md", ".markdown", ".json", ".jsonl", ".html", ".xml", ".csv"}:
            return loader.load_text(storage_path).content
    except Exception:
        # Fall through to permissive read below
        pass

    try:
        with open(storage_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None


def _split_text_to_chunks(text_value: str, chunk_size: int = 2000, overlap: int = 400) -> List[Tuple[int, int, str]]:
    """Split content into overlapping chunks with stable char offsets."""
    chunks: List[Tuple[int, int, str]] = []
    if not text_value:
        return chunks

    start_pos = 0
    length = len(text_value)
    while start_pos < length:
        end_pos = min(start_pos + chunk_size, length)
        chunk_text = text_value[start_pos:end_pos].strip()
        if chunk_text:
            chunks.append((start_pos, end_pos, chunk_text))
        if end_pos >= length:
            break
        start_pos = max(0, end_pos - overlap)
    return chunks


def _ensure_public_document_row(session, vault_id: str, doc_id: str, title: str, content: str) -> str:
    """Ensure a public.documents row exists and return its id."""
    existing = session.execute(
        text("""
            SELECT id
            FROM public.documents
            WHERE tenant_id = CAST(:vault_id AS uuid)
              AND source_document_id = :doc_id
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"vault_id": vault_id, "doc_id": doc_id},
    ).fetchone()
    if existing and existing[0]:
        return str(existing[0])

    public_doc_id = str(uuid4())
    session.execute(
        text("""
            INSERT INTO public.documents
            (id, tenant_id, title, doc_type, content, source_document_id, created_at)
            VALUES (CAST(:id AS uuid), CAST(:vault_id AS uuid), :title, 'DOCUMENT', :content, :doc_id, NOW())
        """),
        {
            "id": public_doc_id,
            "vault_id": vault_id,
            "title": title or "Document",
            "content": content[:5000],
            "doc_id": doc_id,
        },
    )
    return public_doc_id


def _create_chunks_for_document(
    session,
    vault_id: str,
    doc: Dict[str, Any],
    content: str,
) -> int:
    """Create document chunks for one platform document id."""
    doc_id = doc["id"]
    doc_name = doc.get("name") or doc.get("original_filename") or "Document"
    _ensure_public_document_row(session, vault_id, doc_id, doc_name, content)
    chunks = _split_text_to_chunks(content)
    created = 0

    for idx, (char_start, char_end, chunk_text) in enumerate(chunks):
        session.execute(
            text("""
                INSERT INTO public.document_chunks
                (id, document_id, tenant_id, chunk_index, text, char_start, char_end, chunk_metadata)
                VALUES (
                    CAST(:id AS uuid),
                    CAST(:document_id AS uuid),
                    CAST(:tenant_id AS uuid),
                    :chunk_index,
                    :text,
                    :char_start,
                    :char_end,
                    CAST(:chunk_metadata AS json)
                )
                ON CONFLICT (document_id, chunk_index) DO NOTHING
            """),
            {
                "id": str(uuid4()),
                "document_id": doc_id,
                "tenant_id": vault_id,
                "chunk_index": idx,
                "text": chunk_text,
                "char_start": char_start,
                "char_end": char_end,
                "chunk_metadata": json.dumps({"source": "run_vault_extraction_preflight"}),
            },
        )
        created += 1

    # Keep status aligned with chunk availability.
    session.execute(
        text("""
            UPDATE platform.documents
            SET status = CASE
                WHEN status IN ('queued', 'uploaded') THEN 'chunked'
                ELSE status
            END,
            updated_at = NOW()
            WHERE id = :doc_id
        """),
        {"doc_id": doc_id},
    )

    return created


def run_preflight_checks(
    session,
    vault_id: str,
    documents: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Ensure documents have chunked content before extraction begins."""
    report: Dict[str, Any] = {
        "documents_total": len(documents),
        "documents_with_chunks": 0,
        "documents_missing_chunks": 0,
        "queued_or_uploaded": 0,
        "chunks_created": 0,
        "autofixed_documents": 0,
        "unresolved_documents": 0,
    }

    if not documents:
        return report

    for doc in documents:
        doc_id = doc["id"]
        doc_name = doc.get("name") or doc.get("original_filename") or doc_id

        existing_chunks = session.execute(
            text("""
                SELECT COUNT(*)
                FROM public.document_chunks
                WHERE tenant_id = CAST(:vault_id AS uuid)
                  AND document_id = CAST(:doc_id AS uuid)
            """),
            {"vault_id": vault_id, "doc_id": doc_id},
        ).scalar() or 0

        if existing_chunks > 0:
            report["documents_with_chunks"] += 1
            continue

        report["documents_missing_chunks"] += 1
        if doc.get("status") in {"queued", "uploaded"}:
            report["queued_or_uploaded"] += 1

        public_doc = session.execute(
            text("""
                SELECT content
                FROM public.documents
                WHERE tenant_id = CAST(:vault_id AS uuid)
                  AND source_document_id = :doc_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"vault_id": vault_id, "doc_id": doc_id},
        ).fetchone()

        text_content = None
        if public_doc and public_doc[0]:
            text_content = public_doc[0]

        if not text_content:
            text_content = _read_text_from_storage(
                doc.get("storage_path"),
                doc.get("original_filename") or doc_name,
                doc.get("mime_type"),
            )

        if not text_content:
            log(f"[Preflight] Unable to backfill chunks for {doc_name}: no readable content")
            report["unresolved_documents"] += 1
            continue

        created = _create_chunks_for_document(session, vault_id, doc, text_content)
        report["chunks_created"] += created
        report["autofixed_documents"] += 1
        if created == 0:
            report["unresolved_documents"] += 1
            log(f"[Preflight] No chunks created for {doc_name} (content present, but empty chunk set)")
        else:
            log(f"[Preflight] Backfilled {created} chunks for {doc_name}")

    session.commit()
    return report


def get_document_content(session, doc: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """Get document content with deterministic fallback order.

    Order:
      1) public.document_chunks by platform document id
      2) public.documents by source_document_id
      3) direct file read from storage_path
    """
    doc_id = doc["id"]

    chunks = session.execute(
        text("""
            SELECT text
            FROM public.document_chunks
            WHERE document_id = CAST(:doc_id AS uuid)
            ORDER BY chunk_index
        """),
        {"doc_id": doc_id}
    ).fetchall()
    
    if chunks:
        return "\n\n".join(row[0] for row in chunks if row[0]), "chunks"
    
    raw = session.execute(
        text("""
            SELECT content
            FROM public.documents
            WHERE source_document_id = :doc_id
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"doc_id": doc_id}
    ).fetchone()
    
    if raw and raw[0]:
        return raw[0], "public.documents"

    fallback = _read_text_from_storage(
        doc.get("storage_path"),
        doc.get("original_filename") or doc.get("name"),
        doc.get("mime_type"),
    )
    if fallback:
        return fallback, "storage_path"
    
    return None, "none"


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
    
    # Count existing extraction files for resume visibility
    from pathlib import Path
    vault_output_dir = Path(output_dir) / vault_slug
    gpt_dir = vault_output_dir / "gpt_4o_mini"
    claude_dir = vault_output_dir / "claude_sonnet"
    gpt_existing = len(list(gpt_dir.glob("*.json"))) if gpt_dir.exists() else 0
    claude_existing = len(list(claude_dir.glob("*.json"))) if claude_dir.exists() else 0
    already_extracted = min(gpt_existing, claude_existing)
    if already_extracted > 0:
        log(f"Found {already_extracted} documents already extracted (will skip them)")
    
    stats = {
        "total_documents": 0,
        "total_entities": 0,
        "total_relationships": 0,
        "document_ids": [],
        "models": {},
        "errors": [],
        "content_sources": {
            "chunks": 0,
            "public.documents": 0,
            "storage_path": 0,
            "none": 0,
        },
    }
    
    for i, doc in enumerate(documents, 1):
        doc_id = doc["id"]
        doc_name = doc["name"]
        
        content, content_source = get_document_content(session, doc)
        if content_source not in stats["content_sources"]:
            stats["content_sources"][content_source] = 0
        stats["content_sources"][content_source] += 1
        if not content:
            log(f"  [{i}/{len(documents)}] Skipping {doc_name}: no content")
            continue
        
        # Piece 1: Document classification — runs BEFORE extraction.
        # classify_document() never raises (catches all internal errors and
        # returns classification_status='failed'). DB persist IS wrapped to
        # catch errors so a transient DB issue cannot block extraction.
        # Classification metadata also rides through DocumentInfo.metadata
        # so MultiExtractor and downstream stages can read it WITHOUT any
        # change to EXTRACTION_SYSTEM_PROMPT (Piece 2 territory).
        classification = classify_document(
            content,
            filename=doc.get("original_filename") or doc_name,
        )
        log(
            f"  [{i}/{len(documents)}] [classify] {doc_name}: "
            f"status={classification.classification_status} "
            f"primary_domain={classification.primary_domain!r} "
            f"document_type={classification.document_type!r} "
            f"confidence={classification.classification_confidence}"
        )
        try:
            _persist_classification(session, doc_id, classification)
        except Exception as ce:
            log(f"    [classify] DB persist failed for {doc_name}: {ce}")
            try:
                session.rollback()
            except Exception:
                pass
        
        log(f"  [{i}/{len(documents)}] Extracting: {doc_name} (content: {content_source})")
        
        try:
            doc_info = DocumentInfo(
                document_id=doc_id,
                path=doc_name,
                content=content,
                metadata={
                    "filename": doc.get("original_filename") or doc_name,
                    "classification": classification.to_dict(),
                },
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


def run_ontology_extraction(
    session,
    vault_id: str,
    vault_name: str,
    limit: int = None,
) -> Dict[str, Any]:
    """Run ontology-centric extraction on documents.
    
    Uses OntologyCentricPipeline which:
    - Classifies document type
    - Loads per-document-type ontology schemas  
    - Extracts with ontology guidance (constrained types)
    - Canonicalizes using embeddings
    - Stages directly to KG (no multi-model consensus needed)
    """
    documents = get_documents_for_extraction(session, vault_id, limit, skip_multi=True, use_ontology=True)

    if not documents:
        log("No documents found needing extraction")
        return {"total_documents": 0, "total_entities": 0, "total_relationships": 0}
    
    log(f"Found {len(documents)} documents for ontology extraction")
    
    pipeline = OntologyCentricPipeline(
        session=session,
        tenant_id=vault_id,
        model="gpt-4o-mini",
        enable_canonicalization=True,
        auto_stage=True,
        enable_job_tracking=True,
    )
    
    stats = {
        "total_documents": 0,
        "total_entities": 0,
        "total_relationships": 0,
        "total_chunks": 0,
        "document_types": {},
        "new_entity_types": [],
        "new_relationship_types": [],
        "errors": [],
        "content_sources": {
            "chunks": 0,
            "public.documents": 0,
            "storage_path": 0,
            "none": 0,
        },
    }
    
    for i, doc in enumerate(documents, 1):
        doc_id = doc["id"]
        doc_name = doc["name"]
        
        content, content_source = get_document_content(session, doc)
        if content_source not in stats["content_sources"]:
            stats["content_sources"][content_source] = 0
        stats["content_sources"][content_source] += 1
        if not content:
            log(f"  [{i}/{len(documents)}] Skipping {doc_name}: no content")
            continue
        
        # Piece 1.5: Document classification — runs BEFORE ontology extraction.
        # Mirrors the Piece 1 multi-model wiring exactly: same wrapper
        # (empty-text guard + partial-failure semantics built in), same
        # log format, same persist helper, same DB-error tolerance. The
        # classification metadata is passed into pipeline.extract() as
        # metadata only — it does NOT influence document_type
        # classification, ontology loading, or any prompt content. That
        # consumption decision is Piece 2.
        classification = classify_document(
            content,
            filename=doc.get("original_filename") or doc_name,
        )
        log(
            f"  [{i}/{len(documents)}] [classify] {doc_name}: "
            f"status={classification.classification_status} "
            f"primary_domain={classification.primary_domain!r} "
            f"document_type={classification.document_type!r} "
            f"confidence={classification.classification_confidence}"
        )
        try:
            _persist_classification(session, doc_id, classification)
        except Exception as ce:
            log(f"    [classify] DB persist failed for {doc_name}: {ce}")
            try:
                session.rollback()
            except Exception:
                pass
        
        log(f"  [{i}/{len(documents)}] Ontology extracting: {doc_name} (content: {content_source})")
        
        try:
            result: OntologyCentricResult = pipeline.extract(
                text=content,
                document_id=doc_id,
                filename=doc_name,
                classification_metadata=classification.to_dict(),
            )
            
            if result.success:
                stats["total_documents"] += 1
                stats["total_entities"] += len(result.entities)
                stats["total_relationships"] += len(result.relations)
                stats["total_chunks"] += result.chunks_stored
                
                doc_type = result.document_type
                stats["document_types"][doc_type] = stats["document_types"].get(doc_type, 0) + 1
                
                for et in result.new_entity_types:
                    if et not in stats["new_entity_types"]:
                        stats["new_entity_types"].append(et)
                for rt in result.new_relationship_types:
                    if rt not in stats["new_relationship_types"]:
                        stats["new_relationship_types"].append(rt)
                
                log(f"    Type: {doc_type}, Entities: {len(result.entities)}, Relations: {len(result.relations)}")
                
                if result.staging_result:
                    log(f"    Staged: {result.staging_result.entities_created} entities, {result.staging_result.relations_created} relationships")
                
                # Mark document as extracted AND update status
                try:
                    session.execute(
                        text("""
                            UPDATE platform.documents
                            SET extraction_level = 'ontology',
                                status = 'extracted',
                                updated_at = NOW()
                            WHERE id = :doc_id
                        """),
                        {"doc_id": doc_id}
                    )
                    session.commit()
                except Exception as update_err:
                    log(f"    Warning: Failed to update extraction_level: {update_err}")
            else:
                log(f"    Error: {result.error}")
                stats["errors"].append(f"{doc_name}: {result.error}")
                
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
    use_ontology: bool = False,
    force: bool = False,
):
    """Run the full extraction pipeline on a vault.
    
    Args:
        use_ontology: If True, use OntologyCentricPipeline instead of multi-model extraction
    """
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

    lock_key = vault_lock_key(vault_id)
    log(f"[Lock] Vault advisory lock key: {lock_key}")
    lock_acquired = session.execute(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key}
    ).scalar()
    if not lock_acquired:
        log(f"[Lock] ERROR: Could not acquire advisory lock for vault {vault_id}. Another extraction is running.")
        session.close()
        return

    log(f"[Lock] Advisory lock acquired for vault {vault_id}")

    try:
        _run_full_pipeline_body(
            session, vault_id, vault_name, output_dir, models, limit,
            skip_extraction, use_ontology, force, lock_key,
        )
    finally:
        session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
        log(f"[Lock] Advisory lock released for vault {vault_id}")
        session.close()


def _run_full_pipeline_body(
    session,
    vault_id: str,
    vault_name: str,
    output_dir: str,
    models: List[str],
    limit: Optional[int],
    skip_extraction: bool,
    use_ontology: bool,
    force: bool,
    lock_key: int,
):
    run_started_at = datetime.utcnow().isoformat()
    import subprocess
    try:
        git_rev = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        git_rev = "git_unavailable"

    run_manifest: Dict[str, Any] = {
        "run_started_at": run_started_at,
        "vault_id": vault_id,
        "vault_name": vault_name,
        "mode": "ontology" if use_ontology else "multi_model",
        "tree_based_retrieval": os.environ.get("CF_TREE_BASED_RETRIEVAL"),
        "models": models,
        "git_rev": git_rev,
        "is_valid": True,
        "status": "running",
        "invalid_reason": None,
        "verification_stats": {},
        "promotion_stats": {},
    }
    
    log(f"Vault: {vault_name}")
    log(f"Vault ID: {vault_id}")

    preflight_report = build_vault_preflight_report(session, vault_id)
    run_manifest["preflight"] = preflight_report
    if not preflight_report.get("exists"):
        log("ERROR: Vault UUID not found in platform.tenants for this database connection.")
        log(f"DB identity: {preflight_report.get('db_identity', {})}")
        return
    log("")
    log("=" * 40)
    log("RUN PREFLIGHT")
    log("=" * 40)
    log(f"DB identity: {preflight_report.get('db_identity', {})}")
    log(f"Documents total: {preflight_report['documents']['total']}")
    log(f"KG entities: {preflight_report['knowledge_graph']['entities_total']}")
    log(f"KG relationships: {preflight_report['knowledge_graph']['relationships_total']}")
    log(f"Checks: {preflight_report.get('checks', {})}")
    log("=" * 40)
    
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
        return
    
    pending_documents = get_documents_for_extraction(session, vault_id, limit=limit, skip_multi=True)
    doc_count = len(pending_documents)
    log(f"Documents pending extraction: {doc_count}")
    if limit:
        log(f"Limit: {limit} documents")

    if not skip_extraction:
        log("")
        log("-" * 70)
        log("PREFLIGHT: Content & Chunk Readiness")
        log("-" * 70)
        preflight = run_preflight_checks(session, vault_id, pending_documents)
        log(f"Documents inspected: {preflight['documents_total']}")
        log(f"Documents with existing chunks: {preflight['documents_with_chunks']}")
        log(f"Documents missing chunks (initial): {preflight['documents_missing_chunks']}")
        log(f"Queued/uploaded docs observed: {preflight['queued_or_uploaded']}")
        log(f"Autofixed documents: {preflight['autofixed_documents']}")
        log(f"Chunks created by preflight: {preflight['chunks_created']}")
        log(f"Unresolved documents after preflight: {preflight['unresolved_documents']}")

        if preflight["unresolved_documents"] > 0 and not force:
            log("")
            log("FATAL: Preflight found unresolved documents with no readable content.")
            log("Chunking failed for at least one document. Run marked INVALID.")
            log("Use --force to proceed anyway, or fix document ingestion for those files first.")
            run_manifest["is_valid"] = False
            run_manifest["invalid_reason"] = f"Preflight: {preflight['unresolved_documents']} docs have 0 chunks and chunking failed"
            run_manifest["status"] = "invalid"
            run_manifest["run_completed_at"] = datetime.utcnow().isoformat()
            vault_slug = vault_name.lower().replace(" ", "_")
            invalid_dir = Path(output_dir) / vault_slug
            invalid_dir.mkdir(parents=True, exist_ok=True)
            invalid_manifest_path = invalid_dir / f"run_manifest_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
            with open(invalid_manifest_path, "w") as f:
                json.dump(run_manifest, f, indent=2, default=str)
            log(f"Invalid run manifest saved to: {invalid_manifest_path}")
            return
    
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
        if use_ontology:
            log("")
            log("-" * 70)
            log("PHASE 1: Ontology-Centric Extraction")
            log("-" * 70)
            log("Using OntologyCentricPipeline (document-aware, ontology-constrained)")
            
            extraction_summary = run_ontology_extraction(
                session, vault_id, vault_name, limit
            )
            
            log(f"\nOntology extraction complete:")
            log(f"  Total documents: {extraction_summary.get('total_documents', 0)}")
            log(f"  Total entities: {extraction_summary.get('total_entities', 0)}")
            log(f"  Total relationships: {extraction_summary.get('total_relationships', 0)}")
            log(f"  Total chunks stored: {extraction_summary.get('total_chunks', 0)}")
            log(f"  Content paths used: {extraction_summary.get('content_sources', {})}")
            if extraction_summary.get("document_types"):
                log(f"  Document types: {extraction_summary['document_types']}")
            if extraction_summary.get("new_entity_types"):
                log(f"  New entity types discovered: {extraction_summary['new_entity_types']}")
            if extraction_summary.get("new_relationship_types"):
                log(f"  New relationship types discovered: {extraction_summary['new_relationship_types']}")
            if extraction_summary.get("errors"):
                log(f"  Errors: {len(extraction_summary['errors'])}")
            run_manifest["extraction_summary"] = extraction_summary

            # Note: Do NOT return here - continue to verification/promotion phase
            log("")
            log("=" * 70)
            log("ONTOLOGY EXTRACTION COMPLETE - PROCEEDING TO VERIFICATION")
            log("=" * 70)
        else:
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
            log(f"  Content paths used: {extraction_summary.get('content_sources', {})}")
            if extraction_summary.get("errors"):
                log(f"  Errors: {len(extraction_summary['errors'])}")
            run_manifest["extraction_summary"] = extraction_summary
    else:
        log("")
        log("Skipping extraction (--skip-extraction flag)")

    # Consensus phase only applies to multi-model extraction, not ontology
    if not use_ontology:
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

        update_session = get_db_session()
        try:
            doc_ids = ingest_stats.get('document_ids', [])
            if doc_ids:
                log(f"Updating extraction_level to 'multi' for {len(doc_ids)} documents...")
                update_session.execute(text("""
                    UPDATE platform.documents
                    SET extraction_level = 'multi', updated_at = NOW()
                    WHERE id = ANY(:doc_ids)
                """), {"doc_ids": doc_ids})
                update_session.commit()
                log("Extraction level updated successfully.")
        except Exception as e:
            log(f"Warning: Failed to update extraction_level: {e}")
        finally:
            update_session.close()
    
    log("")
    log("-" * 70)
    log("POST-EXTRACTION: Verification + Promotion")
    log("-" * 70)

    verification_stats = {}
    promotion_stats = {}

    verify_session = None
    try:
        verify_session = get_db_session()
        worker = VerificationWorker(session=verify_session, tenant_id=vault_id)
        verification_stats = worker.run(limit=200)
        log(f"Verification: {verification_stats.get('facts_processed', 0)} facts processed, "
            f"{verification_stats.get('verified', 0)} verified, "
            f"{verification_stats.get('rejected', 0)} rejected")
    except Exception as e:
        log(f"WARNING: Verification step failed (non-fatal): {e}")
        verification_stats = {"error": str(e)}
    finally:
        if verify_session:
            verify_session.close()

    gardener_session = None
    try:
        gardener_session = get_db_session()
        gardener_config = GardenerConfig(
            require_verification_for_promotion=True,
            validate_against_ontology=True,
        )
        gardener = GardenerAgent(session=gardener_session, config=gardener_config)
        cycle_id = f"post_extraction_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"
        promotion_result = gardener.promotion_pass(cycle_id=cycle_id)
        promotion_stats = promotion_result.to_dict()
        log(f"Promotion: {promotion_result.entities_promoted} entities promoted, "
            f"{promotion_result.relationships_promoted} relationships promoted, "
            f"{promotion_result.entities_blocked} entities blocked, "
            f"{promotion_result.relationships_blocked} relationships blocked")
        gardener_session.commit()
    except Exception as e:
        log(f"WARNING: Promotion step failed (non-fatal): {e}")
        promotion_stats = {"error": str(e)}
    finally:
        if gardener_session:
            gardener_session.close()

    run_manifest["verification_stats"] = verification_stats
    run_manifest["promotion_stats"] = promotion_stats

    # Mark run invalid if verification or promotion failed
    if verification_stats.get("error") or promotion_stats.get("error"):
        run_manifest["is_valid"] = False
        run_manifest["invalid_reason"] = f"Verification/Promotion failed: verify={verification_stats.get('error', 'ok')}, promote={promotion_stats.get('error', 'ok')}"
        run_manifest["status"] = "invalid"

    vault_slug = vault_name.lower().replace(" ", "_")
    summary_dir = Path(output_dir) / vault_slug
    summary_dir.mkdir(parents=True, exist_ok=True)

    # Save consensus summary only for multi-model mode
    if not use_ontology:
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
        run_manifest["consensus_ingestion_summary"] = ingest_stats
        run_manifest["pipeline_summary_path"] = str(summary_path)

    run_manifest["run_completed_at"] = datetime.utcnow().isoformat()
    # Only set completed if not already marked invalid
    if run_manifest["status"] != "invalid":
        run_manifest["status"] = "completed"

    manifest_path = summary_dir / f"run_manifest_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
    with open(manifest_path, "w") as f:
        json.dump(run_manifest, f, indent=2, default=str)
    log(f"Run manifest saved to: {manifest_path}")


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
    parser.add_argument(
        "--use-ontology",
        action="store_true",
        help="Use ontology-centric pipeline instead of multi-model extraction"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed even if preflight finds unresolved missing-content documents"
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
            use_ontology=args.use_ontology,
            force=args.force,
        )
    else:
        parser.print_help()
        print("\nError: Must specify --vault-name, --vault-id, or --list")
        sys.exit(1)


if __name__ == "__main__":
    main()
