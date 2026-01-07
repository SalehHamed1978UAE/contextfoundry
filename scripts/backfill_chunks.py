#!/usr/bin/env python3
"""
Backfill document chunks for existing documents.

This script finds all documents that don't have chunks stored and
populates them without requiring full re-extraction.
"""
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session, set_tenant_context, DocumentChunk


def chunk_text(text_content: str, chunk_size: int = 2000, overlap: int = 400):
    """Split text into overlapping chunks with position tracking."""
    if len(text_content) <= chunk_size:
        return [(text_content, 0, len(text_content))]
    
    chunks = []
    start = 0
    while start < len(text_content):
        end = start + chunk_size
        if end < len(text_content):
            last_period = text_content.rfind('.', start, end)
            if last_period > start + int(chunk_size * 0.6):
                end = last_period + 1
        
        chunk_text_part = text_content[start:end].strip()
        if chunk_text_part:
            chunks.append((chunk_text_part, start, min(end, len(text_content))))
        
        start = end - overlap
        if start >= len(text_content):
            break
    
    return chunks


def get_document_text(doc_id: str, tenant_id: str) -> str:
    """Read document content from storage."""
    storage_path = f"storage/tenants/{tenant_id}/documents/{doc_id}/v1/content"
    if os.path.exists(storage_path):
        try:
            with open(storage_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                content = content.replace('\x00', '')
                content = ''.join(char for char in content if ord(char) >= 32 or char in '\n\r\t')
                return content
        except Exception as e:
            print(f"[Backfill] Error reading {storage_path}: {e}")
            return ""
    return ""


def backfill_chunks(tenant_id: str = None, dry_run: bool = False):
    """Backfill chunks for documents missing them."""
    session = get_session()
    
    try:
        if tenant_id:
            set_tenant_context(session, tenant_id)
            sql = text("""
                SELECT d.id, d.name as title, d.tenant_id
                FROM platform.documents d
                LEFT JOIN document_chunks dc ON d.id = dc.document_id
                WHERE d.tenant_id = :tenant_id
                GROUP BY d.id, d.name, d.tenant_id
                HAVING COUNT(dc.id) = 0
                ORDER BY d.created_at DESC
            """)
            docs = session.execute(sql, {"tenant_id": tenant_id}).fetchall()
        else:
            sql = text("""
                SELECT d.id, d.name as title, d.tenant_id
                FROM platform.documents d
                LEFT JOIN document_chunks dc ON d.id = dc.document_id
                GROUP BY d.id, d.name, d.tenant_id
                HAVING COUNT(dc.id) = 0
                ORDER BY d.created_at DESC
            """)
            docs = session.execute(sql).fetchall()
        
        print(f"[Backfill] Found {len(docs)} documents without chunks")
        
        if dry_run:
            for doc in docs[:10]:
                print(f"  - {doc.title} ({doc.id})")
            if len(docs) > 10:
                print(f"  ... and {len(docs) - 10} more")
            return
        
        total_chunks = 0
        for doc in docs:
            doc_text = get_document_text(str(doc.id), str(doc.tenant_id))
            
            if not doc_text:
                print(f"[Backfill] No content found for {doc.title}")
                continue
            
            chunks = chunk_text(doc_text)
            
            for idx, (chunk_content, char_start, char_end) in enumerate(chunks):
                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    tenant_id=doc.tenant_id,
                    chunk_index=idx,
                    text=chunk_content,
                    char_start=char_start,
                    char_end=char_end,
                    chunk_metadata={"source": "backfill"}
                )
                session.add(chunk)
            
            session.flush()
            total_chunks += len(chunks)
            print(f"[Backfill] {doc.title}: {len(chunks)} chunks stored")
        
        session.commit()
        print(f"[Backfill] Complete: {total_chunks} chunks stored for {len(docs)} documents")
        
    except Exception as e:
        print(f"[Backfill] Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill document chunks")
    parser.add_argument("--tenant-id", help="Specific tenant ID to backfill")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    
    args = parser.parse_args()
    
    backfill_chunks(tenant_id=args.tenant_id, dry_run=args.dry_run)
