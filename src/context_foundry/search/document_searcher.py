"""
DocumentSearcher - Single source of truth for document search.

This class provides consistent document search logic used by both:
- RetrievalRouter (pre-processing pipeline)
- ToolExecutor (tool calls during agent loop)

Uses authority_config for folder weighting and canonical terms.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from .authority_config import load_authority_config, get_folder_priority, get_canonical_terms

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
    
    def __init__(self, session: Session, tenant_id: str, corpus_name: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.corpus_name = corpus_name
    
    SEMANTIC_SCORE_THRESHOLD = 0.4
    
    FOLDER_PRIORITY = {
        'strategy': 1.0,
        'finances': 0.95,
        'operations': 0.90,
        'engineering': 0.85,
        'projects': 0.85,
        'legal': 0.80,
        'compliance': 0.80,
        'customers': 0.75,
        'policies': 0.75,
        'meeting_notes': 0.60
    }
    
    COMPANY_METRIC_PATTERNS = [
        r'\b(company|total|our|nexus)\s+(backlog|revenue|income|profit|margin|earnings)',
        r'\b(total|overall|company|our)\s+(assets|debt|liabilities|equity)',
        r'\bwhat is (the|our|nexus)\s+(backlog|revenue|profit)',
        r'\b(fy\d{4}|fiscal year)\s+(results|performance|backlog)',
    ]
    
    CUSTOMER_PROFILE_PATTERNS = [
        r'_customer\.md$',
        r'_customer_profile\.md$',
        r'customer_profile',
        r'^customers/',
    ]

    # Patterns for detecting customer ranking/comparison queries
    CUSTOMER_RANKING_PATTERNS = [
        r'\b(largest|biggest|top|major|key|primary|main)\s+(aerospace\s+)?customer',
        r'\bcustomer.{0,30}(largest|biggest|most|highest|top)',
        r'\b(who|which|what)\s+(is|are)\s+the\s+(largest|biggest|top|main|major)',
        r'\btop\s*\d*\s*customer',
        r'\bcustomer\s+(relationship|value|revenue)',
        r'\blargest\s+(aerospace|defense|commercial)\s+customer',
    ]
    
    CANONICAL_TERMS = {
        'project_names': [
            'project helios', 'falcon uav', 'urbanmesh', 'autonav', 'project borealis',
            'greenstream', 'nexgen battery', 'skylink satellite', 'quantum-secured'
        ],
        'business_units': [
            'orion aerospace', 'orion energy', 'orion logistics', 'orion smartcity',
            'aerospace', 'energy solutions', 'logistics', 'smartcity'
        ],
        'executives': [
            'sarah chen', 'marcus webb', 'evelyn reed', 'alex thorne',
            'fatima al-mansoori', 'james park', 'elena rostova', 'michael torres'
        ]
    }
    
    def search(
        self,
        query: str,
        limit: int = 5,
        offset: int = 0,
        use_vector: bool = True,
        apply_folder_weighting: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search documents using consistent logic with semantic-keyword fusion.
        
        1. Try vector similarity search (if enabled)
        2. If top scores < 0.4, apply keyword boosting for canonical terms
        3. Optionally apply folder weighting to prioritize authoritative sources
        4. Fall back to text search with LIKE (OR logic for keywords)
        
        Args:
            query: Search query
            limit: Max results to return
            offset: Pagination offset
            use_vector: Whether to try vector search first
            apply_folder_weighting: Whether to weight results by source folder priority
            
        Returns:
            List of chunk dicts with id, text, document_name, similarity
        """
        chunks = []

        is_company_metric_query = self._is_company_metric_query(query)
        is_customer_ranking = self._is_customer_ranking_query(query)

        if use_vector:
            chunks = self._vector_search(query, limit + offset)

            # For customer ranking queries, always fetch and include customer profile documents
            if is_customer_ranking:
                customer_chunks = self._fetch_customer_profile_chunks(limit=10)
                if customer_chunks:
                    # Merge customer chunks with vector results, avoiding duplicates
                    existing_ids = {c.get('id') for c in chunks if c.get('id')}
                    for cc in customer_chunks:
                        if cc.get('id') not in existing_ids:
                            chunks.append(cc)
                    logger.info(f"[SEARCHER] Customer ranking query - added {len(customer_chunks)} customer profile chunks")

            if chunks:
                # For customer ranking queries, boost customer profile documents
                if is_customer_ranking:
                    chunks = self._boost_customer_documents(chunks)
                    logger.info(f"[SEARCHER] Customer ranking query - boosted customer docs: {len(chunks)} chunks")
                # For company metric queries, filter OUT customer docs (prevents Boeing in Nexus backlog queries)
                elif is_company_metric_query:
                    chunks = self._filter_customer_documents(chunks)
                    logger.info(f"[SEARCHER] Company metric query detected, filtered customer docs: {len(chunks)} chunks remain")
                
                avg_score = sum(c.get('_base_similarity', c.get('similarity', 0)) for c in chunks[:3]) / min(3, len(chunks)) if chunks else 0
                
                if avg_score < self.SEMANTIC_SCORE_THRESHOLD:
                    logger.info(f"[SEARCHER] Low semantic scores (avg={avg_score:.3f}), applying canonical term boosting")
                    chunks = self._apply_canonical_boost(query, chunks, limit + offset, self.corpus_name)
                
                if apply_folder_weighting:
                    chunks = self._apply_folder_weighting(chunks)
                
                logger.info(f"[SEARCHER] Vector search found {len(chunks)} chunks")
                return chunks[offset:offset + limit]
        
        text_chunks = self._text_search(query, limit, offset)
        
        if apply_folder_weighting and text_chunks:
            text_chunks = self._apply_folder_weighting(text_chunks)
        
        logger.info(f"[SEARCHER] Text search found {len(text_chunks)} chunks")
        return text_chunks
    
    def _apply_canonical_boost(self, query: str, chunks: List[Dict], limit: int, corpus_name: Optional[str] = None) -> List[Dict]:
        """Apply additional boosting for canonical project names, business units, and executives.
        
        Uses authority_config for canonical terms with per-corpus overrides.
        """
        query_lower = query.lower()
        
        canonical_terms = get_canonical_terms(corpus_name) or self.CANONICAL_TERMS
        
        matching_canonicals = []
        for category, terms in canonical_terms.items():
            for term in terms:
                if term in query_lower:
                    matching_canonicals.append((category, term))
        
        if not matching_canonicals:
            return chunks
        
        logger.info(f"[SEARCHER] Found canonical terms in query: {matching_canonicals}")
        
        boosted_chunks = []
        for chunk in chunks:
            text_content = (chunk.get("text", chunk.get("content", "")) or "").lower()
            doc_name = (chunk.get("document_name", "") or "").lower()
            
            canonical_boost = 0.0
            matched_terms = []
            
            for category, term in matching_canonicals:
                if term in text_content or term in doc_name:
                    if category == 'project_names':
                        canonical_boost += 0.25
                    elif category == 'business_units':
                        canonical_boost += 0.20
                    elif category == 'executives':
                        canonical_boost += 0.15
                    matched_terms.append(term)
            
            new_chunk = dict(chunk)
            if canonical_boost > 0:
                current_score = chunk.get('similarity', 0)
                new_chunk['similarity'] = min(current_score + canonical_boost, 1.0)
                new_chunk['_canonical_boost'] = canonical_boost
                new_chunk['_matched_canonicals'] = matched_terms
                logger.debug(f"[SEARCHER] Canonical boost: {doc_name[:40]} +{canonical_boost:.2f} -> {new_chunk['similarity']:.3f}")
            
            boosted_chunks.append(new_chunk)
        
        boosted_chunks.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        
        boosted_count = sum(1 for c in boosted_chunks[:limit] if c.get('_canonical_boost', 0) > 0)
        if boosted_count > 0:
            logger.info(f"[SEARCHER] Canonical boost applied: {boosted_count}/{min(limit, len(boosted_chunks))} chunks boosted")
        
        return boosted_chunks[:limit]
    
    def _get_folder_priority(self, doc_name: str) -> float:
        """Get folder priority weight from document name/path using authority config with per-corpus overrides."""
        doc_lower = doc_name.lower()
        
        config = load_authority_config()
        folder_priorities = config.get('default_folder_priority', self.FOLDER_PRIORITY)
        
        if self.corpus_name and self.corpus_name in config.get("corpus_overrides", {}):
            corpus_config = config["corpus_overrides"][self.corpus_name]
            if "folder_priority" in corpus_config:
                folder_priorities = {**folder_priorities, **corpus_config["folder_priority"]}
        
        for folder, weight in folder_priorities.items():
            if f'/{folder}/' in doc_lower or doc_lower.startswith(f'{folder}/') or f'_{folder}_' in doc_lower:
                return weight
            if folder in doc_lower.split('/'):
                return weight
        
        return 0.70
    
    def _apply_folder_weighting(self, chunks: List[Dict]) -> List[Dict]:
        """Apply folder-based priority weighting to chunk scores."""
        weighted_chunks = []
        
        for chunk in chunks:
            doc_name = chunk.get('document_name', '')
            folder_weight = self._get_folder_priority(doc_name)
            
            new_chunk = dict(chunk)
            current_score = chunk.get('similarity', 0)
            weighted_score = current_score * folder_weight
            new_chunk['similarity'] = weighted_score
            new_chunk['_folder_weight'] = folder_weight
            new_chunk['_original_similarity'] = current_score
            
            weighted_chunks.append(new_chunk)
        
        weighted_chunks.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return weighted_chunks
    
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
            try:
                self.session.rollback()
            except Exception:
                pass
            return []
    
    def _is_company_metric_query(self, query: str) -> bool:
        """Check if query is asking about company-level metrics (backlog, revenue, etc.)."""
        query_lower = query.lower()
        for pattern in self.COMPANY_METRIC_PATTERNS:
            if re.search(pattern, query_lower):
                return True
        return False

    def _is_customer_ranking_query(self, query: str) -> bool:
        """Check if query is asking about customer comparisons/rankings."""
        query_lower = query.lower()
        for pattern in self.CUSTOMER_RANKING_PATTERNS:
            if re.search(pattern, query_lower):
                logger.info(f"[SEARCHER] Customer ranking query detected: matched pattern '{pattern}'")
                return True
        return False

    def _boost_customer_documents(self, chunks: List[Dict], boost_factor: float = 1.5) -> List[Dict]:
        """Boost customer profile documents to the top of results."""
        boosted = []
        others = []

        for chunk in chunks:
            doc_name = chunk.get('document_name', '').lower()
            is_customer_doc = False
            for pattern in self.CUSTOMER_PROFILE_PATTERNS:
                if re.search(pattern, doc_name):
                    is_customer_doc = True
                    break

            if is_customer_doc:
                # Boost the similarity score
                chunk['similarity'] = chunk.get('similarity', 0.5) * boost_factor
                chunk['_boosted'] = True
                boosted.append(chunk)
                logger.info(f"[SEARCHER] Boosted customer doc: {doc_name}")
            else:
                others.append(chunk)

        # Put customer docs first, then others
        return boosted + others

    def _fetch_customer_profile_chunks(self, limit: int = 10) -> List[Dict]:
        """Directly fetch chunks from customer profile documents."""
        try:
            query = text("""
                SELECT c.id, c.content as text, d.name as doc_name
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.tenant_id = :tid
                AND (
                    d.name LIKE '%_customer.md'
                    OR d.name LIKE '%customer_profile%'
                    OR d.folder_path LIKE '%customers%'
                )
                ORDER BY d.name
                LIMIT :limit
            """)

            results = self.session.execute(query, {'tid': self.tenant_id, 'limit': limit}).fetchall()

            chunks = []
            for r in results:
                chunks.append({
                    "id": str(r.id),
                    "text": r.text[:2500] if r.text else "",
                    "document_name": r.doc_name or "Unknown customer doc",
                    "similarity": 0.85,  # High similarity for direct fetch
                    "_customer_profile": True
                })

            logger.info(f"[SEARCHER] Fetched {len(chunks)} customer profile chunks directly from DB")
            return chunks

        except Exception as e:
            logger.error(f"[SEARCHER] Failed to fetch customer profile chunks: {e}")
            return []

    def _filter_customer_documents(self, chunks: List[Dict]) -> List[Dict]:
        """Filter out customer profile documents from results."""
        filtered = []
        for chunk in chunks:
            doc_name = chunk.get('document_name', '').lower()
            is_customer_doc = False
            for pattern in self.CUSTOMER_PROFILE_PATTERNS:
                if re.search(pattern, doc_name):
                    is_customer_doc = True
                    break
            if not is_customer_doc:
                filtered.append(chunk)
        return filtered
