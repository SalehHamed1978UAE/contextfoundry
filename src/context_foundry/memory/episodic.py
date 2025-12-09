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
    """
    
    def __init__(self, session: Optional[Session] = None, embedding_dim: int = EMBEDDING_DIM):
        self.session = session or get_session()
        self.embedding_dim = embedding_dim
        logger.info(f"EpisodicMemory initialized (embedding_dim={embedding_dim}, model={EMBEDDING_MODEL})")
    
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
        
        OPTIMIZED: Uses pgvector's cosine distance operator for in-database
        similarity search instead of loading all documents into Python.
        """
        query_embedding = openai_embedding(query_text, self.embedding_dim)
        
        # Build base query using pgvector's cosine_distance function
        # Cosine similarity = 1 - cosine distance
        query = self.session.query(Document)
        if doc_types:
            query = query.filter(Document.doc_type.in_(doc_types))
        
        query = query.filter(Document.embedding.isnot(None))
        
        # Use pgvector's cosine_distance function for efficient in-database similarity
        # The embedding column type handles proper vector casting automatically
        cosine_dist = Document.embedding.cosine_distance(query_embedding)
        query = query.add_columns((1 - cosine_dist).label('similarity'))
        query = query.order_by(cosine_dist)
        query = query.limit(limit * 2)
        
        rows = query.all()
        
        results = []
        for row in rows:
            doc = row[0]  # First element is the Document object
            similarity = float(row[1]) if row[1] else 0.0  # Second element is similarity
            if similarity >= min_similarity:
                # Use to_dict() to preserve the contract expected by RetrievalAgent
                result = doc.to_dict()
                result["similarity"] = similarity
                results.append(result)
        
        results = results[:limit]
        
        logger.debug(f"Episodic search '{query_text[:50]}...': found {len(results)} similar documents (pgvector)")
        return results
    
    def search_by_keywords(
        self,
        keywords: List[str],
        doc_types: List[str] = None,
        limit: int = 5
    ) -> List[Dict]:
        """Fallback keyword search when vector search returns nothing."""
        query = self.session.query(Document)
        
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
        """Get a document by its ID."""
        return self.session.query(Document).filter(
            Document.id == doc_id
        ).first()
    
    def get_documents_by_type(self, doc_type: str) -> List[Document]:
        """Get all documents of a specific type."""
        return self.session.query(Document).filter(
            Document.doc_type == doc_type
        ).all()
    
    def get_statistics(self) -> Dict:
        """Get statistics about the episodic memory."""
        total = self.session.query(Document).count()
        
        type_counts = {}
        for doc_type in ["RUNBOOK", "INCIDENT", "PROCEDURE", "DOCUMENTATION", 
                         "MEETING_NOTES", "EMAIL_THREAD", "STRATEGY_DOC", "SLACK_EXPORT",
                         "MEETING_NOTES_CHUNK", "EMAIL_THREAD_CHUNK", "STRATEGY_DOC_CHUNK", "SLACK_EXPORT_CHUNK"]:
            count = self.session.query(Document).filter(
                Document.doc_type == doc_type
            ).count()
            if count > 0:
                type_counts[doc_type] = count
        
        return {
            "total_documents": total,
            "by_type": type_counts,
            "embedding_dimension": self.embedding_dim,
            "embedding_model": EMBEDDING_MODEL
        }
    
    def clear_all_documents(self) -> int:
        """Clear all documents from episodic memory. Returns count deleted."""
        count = self.session.query(Document).count()
        self.session.query(Document).delete()
        self.session.commit()
        logger.info(f"Cleared {count} documents from episodic memory")
        return count
