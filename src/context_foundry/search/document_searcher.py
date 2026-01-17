"""
DocumentSearcher - Single source of truth for document search.

This class provides consistent document search logic used by both:
- RetrievalRouter (pre-processing pipeline)
- ToolExecutor (tool calls during agent loop)
"""
import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DocumentSearcher:
    """Single source of truth for document search."""
    
    ABBREVIATION_EXPANSIONS = {
        'ceo': 'chief executive officer',
        'cto': 'chief technology officer',
        'cfo': 'chief financial officer',
        'coo': 'chief operating officer',
        'cdo': 'chief data officer',
        'vp': 'vice president',
        'svp': 'senior vice president',
        'evp': 'executive vice president',
    }
    
    STOPWORDS = {
        'what', 'where', 'when', 'which', 'who', 'whom', 'whose', 'that', 'this',
        'these', 'those', 'have', 'has', 'had', 'does', 'did', 'will', 'would',
        'could', 'should', 'might', 'must', 'shall', 'from', 'with', 'about',
        'into', 'through', 'during', 'before', 'after', 'above', 'below',
        'between', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
        'why', 'how', 'all', 'each', 'few', 'more', 'most',
        'other', 'some', 'such', 'only', 'own', 'same', 'than', 'very',
        'just', 'also', 'now', 'the', 'and', 'but', 'for', 'are', 'was', 'were',
        'been', 'being', 'having', 'doing', 'many', 'much', 'any',
        'tell', 'me', 'you', 'can', 'please', 'give', 'show', 'list', 'describe'
    }
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def search(
        self,
        query: str,
        limit: int = 5,
        offset: int = 0,
        use_vector: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search documents using consistent logic.
        
        1. Try vector similarity search (if enabled)
        2. Fall back to text search with LIKE (OR logic for keywords)
        3. Return chunks with metadata
        
        Args:
            query: Search query
            limit: Max results to return
            offset: Pagination offset
            use_vector: Whether to try vector search first
            
        Returns:
            List of chunk dicts with id, text, document_name, similarity
        """
        chunks = []
        
        if use_vector:
            chunks = self._vector_search(query, limit + offset)
            if chunks:
                logger.info(f"[SEARCHER] Vector search found {len(chunks)} chunks")
                return chunks[offset:offset + limit]
        
        text_chunks = self._text_search(query, limit, offset)
        logger.info(f"[SEARCHER] Text search found {len(text_chunks)} chunks")
        return text_chunks
    
    def _extract_keywords(self, query: str) -> tuple:
        """
        Extract keywords from query, separating regular keywords from abbreviations.
        
        Returns:
            (regular_keywords, abbreviation_alternatives)
            where abbreviation_alternatives is list of (abbrev, expansion) tuples
        """
        words = re.findall(r'\b[a-zA-Z0-9]+\b', query.lower())
        
        regular_keywords = []
        abbreviation_alternatives = []
        
        for word in words:
            word = word.rstrip("'s")
            if len(word) < 3:
                continue
            if word in self.STOPWORDS:
                continue
            
            if word in self.ABBREVIATION_EXPANSIONS:
                abbreviation_alternatives.append((word, self.ABBREVIATION_EXPANSIONS[word]))
            else:
                regular_keywords.append(word)
        
        return regular_keywords, abbreviation_alternatives
    
    def _vector_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Vector similarity search using embeddings."""
        try:
            from ..memory.episodic import EpisodicMemory
            episodic = EpisodicMemory(session=self.session, tenant_id=self.tenant_id)
            results = episodic.search_similar(query, limit=limit)
            
            return [
                {
                    "id": str(r.get("id", "")),
                    "text": r.get("content", r.get("text", ""))[:2500],  # Increased to preserve full financial data
                    "document_name": r.get("source_document", "Unknown document"),
                    "similarity": r.get("similarity", 0.7)
                }
                for r in results
            ] if results else []
        except Exception as e:
            logger.warning(f"[SEARCHER] Vector search failed: {e}")
            return []
    
    def _text_search(
        self,
        query: str,
        limit: int,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Text search using LIKE with OR logic for keywords.
        
        Uses OR between keywords so that any keyword match is included.
        This is critical - using AND would fail for queries like
        "Tell me about CloudMatrix" where docs have "cloudmatrix" but not "tell".
        """
        regular_keywords, abbreviation_alternatives = self._extract_keywords(query)
        
        if not regular_keywords and not abbreviation_alternatives:
            logger.info("[SEARCHER] No keywords extracted from query")
            return []
        
        params = {"tenant_id": self.tenant_id, "limit": limit, "offset": offset}
        conditions = []
        param_idx = 0
        
        for kw in regular_keywords:
            conditions.append(f"LOWER(dc.text) LIKE :kw{param_idx}")
            params[f"kw{param_idx}"] = f"%{kw}%"
            param_idx += 1
        
        for abbrev, expansion in abbreviation_alternatives:
            conditions.append(f"(LOWER(dc.text) LIKE :kw{param_idx} OR LOWER(dc.text) LIKE :kw{param_idx+1})")
            params[f"kw{param_idx}"] = f"%{abbrev}%"
            params[f"kw{param_idx+1}"] = f"%{expansion}%"
            param_idx += 2
        
        or_clause = " OR ".join(conditions) if conditions else "TRUE"
        
        sql = text(f"""
            SELECT dc.id, dc.text, d.name as doc_name
            FROM document_chunks dc
            LEFT JOIN platform.documents d ON dc.document_id = d.id
            WHERE dc.tenant_id = :tenant_id
            AND ({or_clause})
            ORDER BY dc.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        
        try:
            results = self.session.execute(sql, params).fetchall()
            
            all_keywords = regular_keywords + [a[0] for a in abbreviation_alternatives]
            logger.info(f"[SEARCHER] Text search with OR logic found {len(results)} chunks for keywords: {all_keywords}")
            
            return [
                {
                    "id": str(r.id),
                    "text": r.text[:2500] if r.text else "",  # Increased to preserve full financial data
                    "document_name": r.doc_name or "Unknown document",
                    "similarity": 0.6
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"[SEARCHER] Text search failed: {e}")
            return []
