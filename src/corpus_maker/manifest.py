"""Manifest generation with checksums for corpus versioning."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def generate_manifest(
    corpus_name: str,
    documents: List[Dict[str, Any]],
    question_file: Path,
    user: str = "system",
    anchor_org: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate manifest for corpus upload.
    
    Args:
        corpus_name: Human-readable corpus name
        documents: List of document metadata dicts with source_path, dest_path, sha256, size_bytes
        question_file: Path to normalized questions file
        user: User performing upload
        anchor_org: Anchor organization for queries
    
    Returns:
        Manifest dict suitable for JSON serialization
    """
    question_count = 0
    question_hash = ""
    question_size = 0
    
    if question_file.exists():
        with open(question_file, 'r', encoding='utf-8') as f:
            questions = json.load(f)
            question_count = len(questions)
        question_hash = compute_sha256(question_file)
        question_size = question_file.stat().st_size
    
    total_size = sum(d.get('size_bytes', 0) for d in documents) + question_size
    
    manifest = {
        "version": "1.0",
        "corpus_name": corpus_name,
        "anchor_organization": anchor_org,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "created_by": user,
        "documents": documents,
        "question_set": {
            "dest_path": str(question_file),
            "sha256": question_hash,
            "size_bytes": question_size,
            "question_count": question_count
        },
        "summary": {
            "total_documents": len(documents),
            "total_questions": question_count,
            "total_size_bytes": total_size
        }
    }
    
    return manifest


def load_manifest(manifest_path: Path) -> Optional[Dict[str, Any]]:
    """Load manifest from file."""
    if not manifest_path.exists():
        return None
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def verify_manifest(manifest: Dict[str, Any], base_path: Path) -> List[str]:
    """
    Verify manifest checksums against actual files.
    
    Returns:
        List of verification errors (empty if all OK)
    """
    errors = []
    
    for doc in manifest.get('documents', []):
        dest_path = base_path / doc['dest_path']
        if not dest_path.exists():
            errors.append(f"Missing document: {doc['dest_path']}")
            continue
        
        actual_hash = compute_sha256(dest_path)
        if actual_hash != doc.get('sha256'):
            errors.append(f"Checksum mismatch: {doc['dest_path']}")
    
    q_set = manifest.get('question_set', {})
    if q_set.get('dest_path'):
        q_path = Path(q_set['dest_path'])
        if q_path.exists():
            actual_hash = compute_sha256(q_path)
            if actual_hash != q_set.get('sha256'):
                errors.append(f"Question file checksum mismatch")
        else:
            errors.append(f"Missing question file: {q_set['dest_path']}")
    
    return errors


def diff_manifests(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two manifests and return differences.
    
    Returns:
        Dict with added, removed, modified document lists
    """
    old_docs = {d['dest_path']: d for d in old.get('documents', [])}
    new_docs = {d['dest_path']: d for d in new.get('documents', [])}
    
    added = [new_docs[p] for p in set(new_docs) - set(old_docs)]
    removed = [old_docs[p] for p in set(old_docs) - set(new_docs)]
    
    modified = []
    for path in set(old_docs) & set(new_docs):
        if old_docs[path].get('sha256') != new_docs[path].get('sha256'):
            modified.append({
                'path': path,
                'old_hash': old_docs[path].get('sha256'),
                'new_hash': new_docs[path].get('sha256')
            })
    
    return {
        'added': added,
        'removed': removed,
        'modified': modified,
        'unchanged_count': len(set(old_docs) & set(new_docs)) - len(modified)
    }
