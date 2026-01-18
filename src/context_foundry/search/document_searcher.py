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
            if word.endswith("'s"):
                word = word[:-2]
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
        """
        Hybrid search: Vector similarity + phrase-first re-ranking.
        
        This combines semantic similarity with:
        1. Strong phrase boosting for exact multi-word matches (+0.15)
        2. Discriminative keyword boosting (rare terms get higher boost)
        3. Soft phrase requirement when query contains compound terms
        """
        try:
            from ..memory.episodic import EpisodicMemory
            episodic = EpisodicMemory(session=self.session, tenant_id=self.tenant_id)
            results = episodic.search_similar(query, limit=limit * 3)
            
            if not results:
                return []
            
            regular_keywords, abbrev_alternatives = self._extract_keywords(query)
            all_keywords = regular_keywords + [a[0] for a in abbrev_alternatives] + [a[1] for a in abbrev_alternatives]
            
            query_ngrams = self._extract_ngrams(query)
            logger.info(f"[SEARCHER] Query ngrams extracted: {query_ngrams}")
            
            keyword_doc_freq = {}
            for r in results:
                text_content = (r.get("content", r.get("text", "")) or "").lower()
                for kw in all_keywords:
                    if kw.lower() in text_content:
                        keyword_doc_freq[kw] = keyword_doc_freq.get(kw, 0) + 1
            
            scored_results = []
            for r in results:
                text_content = (r.get("content", r.get("text", "")) or "").lower()
                base_similarity = r.get("similarity", 0.7)
                
                keyword_boost = 0.0
                matched_keywords = []
                for kw in all_keywords:
                    kw_lower = kw.lower()
                    if kw_lower in text_content:
                        doc_freq = keyword_doc_freq.get(kw, 1)
                        idf_weight = 1.0 / (1.0 + 0.3 * doc_freq)
                        keyword_boost += 0.04 * idf_weight
                        matched_keywords.append(kw)
                
                phrase_boost = 0.0
                matched_phrases = []
                for ngram in query_ngrams:
                    ngram_pattern = self._phrase_to_pattern(ngram)
                    if re.search(ngram_pattern, text_content, re.IGNORECASE):
                        word_count = len(ngram.split())
                        phrase_boost += 0.25 * word_count
                        matched_phrases.append(ngram)
                
                final_score = min(base_similarity + keyword_boost + phrase_boost, 1.0)
                
                scored_results.append({
                    "id": str(r.get("id", "")),
                    "text": r.get("content", r.get("text", ""))[:2500],
                    "document_name": r.get("source_document", "Unknown document"),
                    "similarity": final_score,
                    "_base_similarity": base_similarity,
                    "_keyword_boost": keyword_boost,
                    "_phrase_boost": phrase_boost,
                    "_matched_keywords": matched_keywords,
                    "_matched_phrases": matched_phrases
                })
            
            scored_results.sort(key=lambda x: x["similarity"], reverse=True)
            
            all_phrase_boosted = [r for r in scored_results if r.get("_phrase_boost", 0) > 0]
            if all_phrase_boosted:
                for r in all_phrase_boosted[:3]:
                    logger.info(f"[SEARCHER] Phrase boost: {r['document_name'][:30]} base={r['_base_similarity']:.3f} +kw={r['_keyword_boost']:.3f} +phrase={r['_phrase_boost']:.3f} = {r['similarity']:.3f} phrases={r['_matched_phrases']}")
            
            top_results = scored_results[:limit]
            if top_results:
                phrase_boosted = [r for r in top_results if r.get("_phrase_boost", 0) > 0]
                if phrase_boosted:
                    logger.info(f"[SEARCHER] Hybrid search: {len(phrase_boosted)}/{len(top_results)} boosted by phrases in final results")
            
            return top_results
        except Exception as e:
            logger.warning(f"[SEARCHER] Vector search failed: {e}")
            return []
    
    def _extract_ngrams(self, query: str) -> List[str]:
        """
        Extract 2-3 word n-grams from the query.
        
        These are consecutive word sequences that help match compound terms
        like "referral bonus", "stock options", "performance review", etc.
        """
        words = query.lower().split()
        content_words = [w for w in words if w not in self.STOPWORDS and len(w) >= 3]
        
        ngrams = []
        
        clean_query = ' '.join(words)
        
        for i in range(len(content_words) - 1):
            w1, w2 = content_words[i], content_words[i+1]
            bigram_pattern = rf'\b{re.escape(w1)}\b.*?\b{re.escape(w2)}\b'
            match = re.search(bigram_pattern, clean_query)
            if match:
                matched_text = match.group(0)
                word_count = len(matched_text.split())
                if word_count <= 3:
                    ngrams.append(matched_text)
        
        for i in range(len(content_words) - 2):
            w1, w2, w3 = content_words[i], content_words[i+1], content_words[i+2]
            trigram_pattern = rf'\b{re.escape(w1)}\b.*?\b{re.escape(w2)}\b.*?\b{re.escape(w3)}\b'
            match = re.search(trigram_pattern, clean_query)
            if match:
                matched_text = match.group(0)
                word_count = len(matched_text.split())
                if word_count <= 5:
                    ngrams.append(matched_text)
        
        return ngrams
    
    def _phrase_to_pattern(self, phrase: str) -> str:
        """
        Convert a phrase to a flexible regex pattern.
        
        Handles:
        - Singular/plural variations (bonus -> bonus(es)?)
        - Word boundaries
        - Minor variations in spacing
        """
        words = phrase.split()
        patterns = []
        for word in words:
            word_escaped = re.escape(word.lower())
            if word.endswith('s'):
                pattern = rf'\b{word_escaped}(es)?\b'
            else:
                pattern = rf'\b{word_escaped}(s|es)?\b'
            patterns.append(pattern)
        
        return r'\s+'.join(patterns)
    
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
