"""
Episodic Memory Layer - Vector embeddings for similarity search.
Stores document embeddings using pgvector.
"""
from typing import List, Dict, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..models.schema import Document, get_session
from ..utils.logger import logger


def simple_embedding(text: str, dim: int = 384) -> List[float]:
    """
    Simple deterministic embedding for MVP.
    In production, use sentence-transformers or OpenAI embeddings.
    
    This creates a basic bag-of-words style embedding that allows
    for meaningful similarity comparisons.
    """
    np.random.seed(hash(text.lower()[:100]) % (2**32))
    
    words = text.lower().split()
    word_vectors = []
    
    for word in words[:50]:
        np.random.seed(hash(word) % (2**32))
        word_vectors.append(np.random.randn(dim))
    
    if word_vectors:
        embedding = np.mean(word_vectors, axis=0)
    else:
        embedding = np.zeros(dim)
    
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    
    return embedding.tolist()


class EpisodicMemory:
    """
    Vector-based memory for similarity search.
    Stores document embeddings for retrieval.
    """
    
    def __init__(self, session: Optional[Session] = None, embedding_dim: int = 384):
        self.session = session or get_session()
        self.embedding_dim = embedding_dim
        logger.info(f"EpisodicMemory initialized (embedding_dim={embedding_dim})")
    
    def add_document(
        self,
        title: str,
        doc_type: str,
        content: str,
        metadata: dict = None,
        source_document_id: str = None
    ) -> Document:
        """Add a document with its embedding."""
        embedding = simple_embedding(content, self.embedding_dim)
        
        doc = Document(
            title=title,
            doc_type=doc_type,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
            source_document_id=source_document_id
        )
        self.session.add(doc)
        self.session.commit()
        
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
        query_embedding = simple_embedding(query_text, self.embedding_dim)
        
        query = self.session.query(Document)
        if doc_types:
            query = query.filter(Document.doc_type.in_(doc_types))
        
        results = []
        documents = query.all()
        
        for doc in documents:
            if doc.embedding is not None:
                doc_embedding = np.array(doc.embedding)
                query_vec = np.array(query_embedding)
                
                similarity = float(np.dot(doc_embedding, query_vec))
                
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
        for doc_type in ["RUNBOOK", "INCIDENT", "PROCEDURE", "DOCUMENTATION"]:
            count = self.session.query(Document).filter(
                Document.doc_type == doc_type
            ).count()
            if count > 0:
                type_counts[doc_type] = count
        
        return {
            "total_documents": total,
            "by_type": type_counts,
            "embedding_dimension": self.embedding_dim
        }
