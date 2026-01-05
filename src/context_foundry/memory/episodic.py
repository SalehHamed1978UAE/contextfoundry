"""
Episodic Memory Layer - Vector embeddings for similarity search.
Stores document embeddings using pgvector.

Uses OpenAI text-embedding-3-small for semantic embeddings via Replit AI Integrations.
"""
import os
from typing import List, Dict, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from openai import OpenAI

from ..models.schema import Document, get_session
from ..utils.logger import logger

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

_openai_client: Optional[OpenAI] = None

def get_openai_client() -> OpenAI:
    """Get or create OpenAI client for embeddings (uses direct OpenAI API key)."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def openai_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """
    Generate embedding using OpenAI's text-embedding-3-small model.
    
    Args:
        text: Text to embed (will be truncated if too long)
        dim: Embedding dimension (1536 for text-embedding-3-small)
    
    Returns:
        List of floats representing the embedding vector
    """
    if not text or not text.strip():
        return [0.0] * dim
    
    truncated = text[:8000]
    
    try:
        client = get_openai_client()
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=truncated,
        )
        embedding = response.data[0].embedding
        
        if len(embedding) != dim:
            logger.warning(f"Embedding dimension mismatch: expected {dim}, got {len(embedding)}")
        
        return embedding
    except Exception as e:
        logger.error(f"OpenAI embedding failed: {e}")
        raise


class EpisodicMemory:
    """
    Vector-based memory for similarity search.
    Stores document embeddings for retrieval using OpenAI embeddings.
    
    SECURITY: Requires tenant_id for defense-in-depth filtering.
    RLS provides the authoritative security boundary, but application-level
    filtering provides belt-and-suspenders protection.
    """
    
    def __init__(self, session: Optional[Session] = None, embedding_dim: int = EMBEDDING_DIM, tenant_id: str = None):
        self.session = session or get_session()
        self.embedding_dim = embedding_dim
        self.tenant_id = tenant_id
        if not tenant_id:
            logger.warning("EpisodicMemory initialized without tenant_id - queries will not be tenant-scoped")
        else:
            logger.info(f"EpisodicMemory initialized for tenant {tenant_id[:8]}... (model={EMBEDDING_MODEL})")
    
    def _apply_tenant_filter(self, query, model_class):
        """Apply tenant_id filter if tenant_id is set (defense-in-depth)."""
        if self.tenant_id and hasattr(model_class, 'tenant_id'):
            return query.filter(model_class.tenant_id == self.tenant_id)
        return query
    
    def add_document(
        self,
        title: str,
        doc_type: str,
        content: str,
        metadata: dict = None,
        source_document_id: str = None
    ) -> Document:
        """Add a document with its OpenAI embedding."""
        text_for_embedding = f"{title}\n\n{content}"
        embedding = openai_embedding(text_for_embedding, self.embedding_dim)
        
        doc = Document(
            title=title,
            doc_type=doc_type,
            content=content,
            embedding=embedding,
            doc_metadata=metadata or {},
            source_document_id=source_document_id
        )
        self.session.add(doc)
        
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to add document {title}: {e}")
            raise
        
        logger.debug(f"Added document: {title} [{doc_type}]")
        return doc
    
    def search_similar(
        self,
        query_text: str,
        doc_types: List[str] = None,
        limit: int = 5,
        min_similarity: float = 0.0
    ) -> List[Dict]:
        """
        Search for similar documents using vector similarity.
        Returns documents with their similarity scores.
        """
        query_embedding = openai_embedding(query_text, self.embedding_dim)
        
        query = self.session.query(Document)
        query = self._apply_tenant_filter(query, Document)
        if doc_types:
            query = query.filter(Document.doc_type.in_(doc_types))
        
        results = []
        documents = query.all()
        
        for doc in documents:
            if doc.embedding is not None:
                doc_embedding = np.array(doc.embedding)
                query_vec = np.array(query_embedding)
                
                similarity = float(np.dot(doc_embedding, query_vec) / 
                                   (np.linalg.norm(doc_embedding) * np.linalg.norm(query_vec) + 1e-8))
                
                if similarity >= min_similarity:
                    results.append({
                        **doc.to_dict(),
                        "similarity": similarity
                    })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        results = results[:limit]
        
        logger.debug(f"Episodic search '{query_text[:50]}...': found {len(results)} similar documents")
        return results
    
    def search_by_keywords(
        self,
        keywords: List[str],
        doc_types: List[str] = None,
        limit: int = 5
    ) -> List[Dict]:
        """Fallback keyword search when vector search returns nothing."""
        query = self.session.query(Document)
        query = self._apply_tenant_filter(query, Document)
        
        if doc_types:
            query = query.filter(Document.doc_type.in_(doc_types))
        
        results = []
        for doc in query.all():
            score = 0
            content_lower = doc.content.lower()
            title_lower = doc.title.lower()
            
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in title_lower:
                    score += 2
                if keyword_lower in content_lower:
                    score += content_lower.count(keyword_lower)
            
            if score > 0:
                results.append({
                    **doc.to_dict(),
                    "similarity": min(score / 10, 1.0)
                })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        results = results[:limit]
        
        logger.debug(f"Keyword search {keywords}: found {len(results)} documents")
        return results
    
    def search_for_rule_context(
        self,
        rule_keywords: List[str],
        doc_types: List[str] = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search for documents that provide context for rule queries.
        
        Prioritizes:
        1. Exact title matches (e.g., "Escalation Procedures" for escalation queries)
        2. High keyword density in content
        3. RUNBOOK and PROCEDURE doc types
        """
        query = self.session.query(Document)
        query = self._apply_tenant_filter(query, Document)
        
        if doc_types:
            query = query.filter(Document.doc_type.in_(doc_types))
        
        results = []
        for doc in query.all():
            score = 0
            match_reasons = []
            content_lower = doc.content.lower()
            title_lower = doc.title.lower()
            
            for keyword in rule_keywords:
                keyword_lower = keyword.lower()
                
                if keyword_lower in title_lower:
                    score += 10
                    match_reasons.append(f"title:{keyword}")
                
                content_count = content_lower.count(keyword_lower)
                if content_count > 0:
                    score += min(content_count, 5)
                    match_reasons.append(f"content:{keyword}x{content_count}")
            
            if doc.doc_type in ['RUNBOOK', 'PROCEDURE']:
                score += 3
                match_reasons.append("type:runbook/procedure")
            
            if score > 0:
                results.append({
                    **doc.to_dict(),
                    "similarity": min(score / 20, 1.0),
                    "match_score": score,
                    "match_reasons": match_reasons
                })
        
        results.sort(key=lambda x: x["match_score"], reverse=True)
        results = results[:limit]
        
        logger.debug(f"Rule context search {rule_keywords}: found {len(results)} documents")
        return results
    
    def get_document_by_id(self, doc_id: str) -> Optional[Document]:
        """Get a document by its ID (tenant-scoped)."""
        query = self.session.query(Document).filter(Document.id == doc_id)
        query = self._apply_tenant_filter(query, Document)
        return query.first()
    
    def get_documents_by_type(self, doc_type: str) -> List[Document]:
        """Get all documents of a specific type (tenant-scoped)."""
        query = self.session.query(Document).filter(Document.doc_type == doc_type)
        query = self._apply_tenant_filter(query, Document)
        return query.all()
    
    def get_statistics(self) -> Dict:
        """Get statistics about the episodic memory (tenant-scoped)."""
        base_query = self._apply_tenant_filter(self.session.query(Document), Document)
        total = base_query.count()
        
        type_counts = {}
        for doc_type in ["RUNBOOK", "INCIDENT", "PROCEDURE", "DOCUMENTATION", 
                         "MEETING_NOTES", "EMAIL_THREAD", "STRATEGY_DOC", "SLACK_EXPORT",
                         "MEETING_NOTES_CHUNK", "EMAIL_THREAD_CHUNK", "STRATEGY_DOC_CHUNK", "SLACK_EXPORT_CHUNK"]:
            type_query = self._apply_tenant_filter(
                self.session.query(Document).filter(Document.doc_type == doc_type),
                Document
            )
            count = type_query.count()
            if count > 0:
                type_counts[doc_type] = count
        
        return {
            "total_documents": total,
            "by_type": type_counts,
            "embedding_dimension": self.embedding_dim,
            "embedding_model": EMBEDDING_MODEL
        }
    
    def clear_all_documents(self) -> int:
        """Clear all documents from episodic memory (tenant-scoped). Returns count deleted."""
        base_query = self._apply_tenant_filter(self.session.query(Document), Document)
        count = base_query.count()
        base_query.delete()
        self.session.commit()
        logger.info(f"Cleared {count} documents from episodic memory (tenant_id={self.tenant_id})")
        return count
