"""Core corpus upload logic shared by CLI and API."""
import hashlib
import json
import logging
import shutil
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .normalizer import normalize_folder_name, normalize_questions, slugify
from .validator import validate_documents, validate_questions, list_valid_documents, SUPPORTED_EXTENSIONS
from .manifest import generate_manifest, compute_sha256
from .registry import register_corpus

logger = logging.getLogger(__name__)


@dataclass
class FolderMapping:
    """Mapping from source folder to destination category."""
    source_path: Path
    category: str
    
    def __post_init__(self):
        if isinstance(self.source_path, str):
            self.source_path = Path(self.source_path)


@dataclass
class UploadResult:
    """Result of corpus upload operation."""
    success: bool
    vault_id: str
    corpus_name: str
    document_count: int
    question_count: int
    manifest_path: Optional[Path]
    errors: List[str] = field(default_factory=list)
    extraction_status: Optional[str] = None
    uploaded_documents: List[Dict[str, Any]] = field(default_factory=list)


def upload_corpus(
    vault_id: str,
    corpus_name: str,
    anchor_org: str,
    folder_mappings: List[FolderMapping],
    question_file: Path,
    sync_extract: bool = True,
    user: str = "system",
    skip_extraction: bool = False
) -> UploadResult:
    """
    Upload and normalize a corpus to a vault.
    
    Args:
        vault_id: Target vault ID
        corpus_name: Human-readable corpus name
        anchor_org: Anchor organization for queries
        folder_mappings: List of source folder -> category mappings
        question_file: Path to questions JSON
        sync_extract: If True, run extraction synchronously
        user: User performing upload
        skip_extraction: If True, skip extraction entirely
    
    Returns:
        UploadResult with status and details
    """
    errors = []
    slug = slugify(corpus_name)
    
    if isinstance(question_file, str):
        question_file = Path(question_file)
    
    for mapping in folder_mappings:
        doc_errors = validate_documents(mapping.source_path, SUPPORTED_EXTENSIONS)
        errors.extend(doc_errors)
    
    question_errors = validate_questions(question_file)
    errors.extend(question_errors)
    
    if errors:
        return UploadResult(
            success=False,
            vault_id=vault_id,
            corpus_name=corpus_name,
            document_count=0,
            question_count=0,
            manifest_path=None,
            errors=errors
        )
    
    tenant = get_or_create_tenant(vault_id, corpus_name)
    if not tenant:
        return UploadResult(
            success=False,
            vault_id=vault_id,
            corpus_name=corpus_name,
            document_count=0,
            question_count=0,
            manifest_path=None,
            errors=[f"Failed to get or create tenant for vault {vault_id}"]
        )
    
    all_documents = []
    uploaded_docs = []
    
    for mapping in folder_mappings:
        category = normalize_folder_name(mapping.category)
        
        documents, doc_records = upload_documents_to_vault(
            tenant_id=vault_id,
            source_path=mapping.source_path,
            category=category,
            extensions=SUPPORTED_EXTENSIONS
        )
        all_documents.extend(documents)
        uploaded_docs.extend(doc_records)
    
    questions_dest = Path(f"test_questions/{slug}_100q.json")
    questions_dest.parent.mkdir(parents=True, exist_ok=True)
    question_count = normalize_questions(question_file, questions_dest)
    
    manifest = generate_manifest(
        corpus_name=corpus_name,
        documents=all_documents,
        question_file=questions_dest,
        user=user,
        anchor_org=anchor_org
    )
    
    manifest_path = Path(f"test_questions/{slug}_manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    update_tenant_metadata(
        vault_id=vault_id,
        metadata={
            "corpus_name": corpus_name,
            "anchor_organization": anchor_org,
            "question_file": f"{slug}_100q.json",
            "document_count": len(all_documents),
            "question_count": question_count,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "created_by": user
        }
    )
    
    register_corpus(
        corpus_name=corpus_name,
        vault_id=vault_id,
        questions_file=f"{slug}_100q.json",
        anchor_org=anchor_org,
        document_count=len(all_documents),
        question_count=question_count
    )
    
    extraction_status = None
    if not skip_extraction and len(uploaded_docs) > 0:
        extraction_status = trigger_extraction(vault_id, sync=sync_extract)
    
    log_audit(
        action="corpus_upload",
        user=user,
        vault_id=vault_id,
        corpus_name=corpus_name,
        document_count=len(all_documents),
        question_count=question_count,
        extraction_status=extraction_status
    )
    
    logger.info(
        f"Corpus '{corpus_name}' uploaded: "
        f"{len(all_documents)} documents, {question_count} questions"
    )
    
    return UploadResult(
        success=True,
        vault_id=vault_id,
        corpus_name=corpus_name,
        document_count=len(all_documents),
        question_count=question_count,
        manifest_path=manifest_path,
        errors=[],
        extraction_status=extraction_status,
        uploaded_documents=all_documents
    )


def upload_documents_to_vault(
    tenant_id: str,
    source_path: Path,
    category: str,
    extensions: set
) -> tuple:
    """
    Upload documents from source folder to vault via DocumentService.
    
    Returns:
        Tuple of (document_metadata_list, document_records)
    """
    from platform_foundation.src.document_service import DocumentService
    
    documents = []
    doc_records = []
    
    valid_files = list_valid_documents(source_path, extensions)
    
    ds = DocumentService()
    
    for file_path in valid_files:
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            doc_record = ds.upload_document(
                tenant_id=tenant_id,
                filename=file_path.name,
                content=content,
                folder=category,
                metadata={
                    'source_path': str(file_path),
                    'category': category,
                    'uploaded_at': datetime.utcnow().isoformat()
                }
            )
            
            if doc_record:
                documents.append({
                    "source_path": str(file_path),
                    "dest_path": f"documents/{category}/{file_path.name}",
                    "sha256": compute_sha256(file_path),
                    "size_bytes": file_path.stat().st_size,
                    "document_id": doc_record.get('id')
                })
                doc_records.append(doc_record)
                logger.debug(f"Uploaded: {file_path.name} -> {category}")
            
        except Exception as e:
            logger.error(f"Error uploading {file_path}: {e}")
    
    return documents, doc_records


def get_or_create_tenant(vault_id: str, corpus_name: str) -> Optional[Dict[str, Any]]:
    """Get existing tenant or create new one."""
    try:
        from platform_foundation.src.tenant_service import TenantService
        
        ts = TenantService()
        
        tenant = ts.get_tenant(vault_id)
        if tenant:
            return tenant
        
        tenant = ts.create_tenant(
            name=corpus_name,
            tenant_id=vault_id
        )
        return tenant
        
    except Exception as e:
        logger.error(f"Error getting/creating tenant: {e}")
        return None


def update_tenant_metadata(vault_id: str, metadata: dict) -> bool:
    """Update tenant record with corpus metadata."""
    try:
        from platform_foundation.src.tenant_service import TenantService
        
        ts = TenantService()
        ts.update_tenant_metadata(vault_id, metadata)
        return True
        
    except Exception as e:
        logger.warning(f"Could not update tenant metadata: {e}")
        return False


def trigger_extraction(vault_id: str, sync: bool = True) -> str:
    """Trigger extraction for all documents in vault."""
    try:
        from platform_foundation.src.document_service import DocumentService
        
        ds = DocumentService()
        
        pending_count = ds.trigger_extraction_for_vault(vault_id, sync_extract=sync)
        
        if sync:
            return f"completed ({pending_count} documents)"
        else:
            return f"queued ({pending_count} documents)"
        
    except Exception as e:
        logger.error(f"Extraction trigger failed: {e}")
        return f"error: {e}"


def log_audit(action: str, user: str, **kwargs) -> None:
    """Log action to audit log."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "user": user,
        **kwargs
    }
    
    logger.info(f"AUDIT: {json.dumps(log_entry)}")
    
    audit_path = Path("logs/corpus_audit.jsonl")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(audit_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry) + "\n")
