"""
Tier 1 Entity Resolver for App Integration.

Fast, deterministic entity resolution without LLM calls.
Used by /api/v1/query (first pass) and /api/v1/verify (only pass).

Resolution stages:
1. Entity name scanning - find entity names that appear in raw text
2. Alias lookup - check CONFIRMED/TRUSTED aliases
3. Lexical matching - normalized token matching
4. Embedding similarity - semantic matching against entity names

Target latency: <100ms for Tier 1 only
"""
import re
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set, Tuple
from rapidfuzz import fuzz
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..models.schema import Entity, LifecycleState, get_session
from ..memory.episodic import openai_embedding
from ..utils.logger import logger


@dataclass
class EntityMatch:
    """A matched entity with scoring and evidence."""
    entity_id: str
    name: str
    entity_type: str
    score: float
    evidence: List[str]
    match_text: str
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "score": round(self.score, 4),
            "evidence": self.evidence,
            "match_text": self.match_text,
            "confidence": round(self.confidence, 4)
        }


@dataclass
class Tier1ResolveResult:
    """Result of Tier 1 entity resolution from raw text."""
    status: str
    entities: List[EntityMatch] = field(default_factory=list)
    extracted_terms: List[str] = field(default_factory=list)
    selected: Optional[EntityMatch] = None
    selection_reason: str = ""
    elapsed_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "entities": [e.to_dict() for e in self.entities],
            "extracted_terms": self.extracted_terms,
            "selected": self.selected.to_dict() if self.selected else None,
            "selection_reason": self.selection_reason,
            "elapsed_ms": round(self.elapsed_ms, 2)
        }


class Tier1Resolver:
    """
    Fast entity resolver for app integration.
    
    Scans raw text to find entity mentions by matching against
    known entity names in the graph. No LLM calls.
    
    Stages:
    1. Scan text for known entity names (substring/token match)
    2. Check aliases (CONFIRMED/TRUSTED only)
    3. Fuzzy lexical matching
    4. Embedding similarity (optional, for fallback)
    """
    
    EXACT_MATCH_SCORE = 1.0
    ALIAS_MATCH_SCORE = 0.95
    SUBSTRING_MATCH_SCORE = 0.90
    TOKEN_MATCH_SCORE = 0.85
    FUZZY_THRESHOLD = 0.75
    EMBEDDING_THRESHOLD = 0.70
    CONFIDENCE_THRESHOLD = 0.70
    
    def __init__(
        self,
        session: Optional[Session] = None,
        tenant_id: Optional[str] = None,
        use_embeddings: bool = True
    ):
        self.session = session or get_session()
        self.tenant_id = tenant_id
        self.use_embeddings = use_embeddings
        self._entity_cache: Optional[List[Dict]] = None
        self._alias_cache: Optional[Dict[str, str]] = None
        
        try:
            self.session.rollback()
        except Exception:
            pass
    
    def resolve_from_text(
        self,
        raw_text: str,
        entity_type_hint: Optional[str] = None,
        max_entities: int = 5
    ) -> Tier1ResolveResult:
        """
        Resolve entities from raw text input.
        
        Args:
            raw_text: The raw text to scan for entity mentions
            entity_type_hint: Optional type filter
            max_entities: Maximum entities to return
            
        Returns:
            Tier1ResolveResult with matched entities
        """
        import time
        start_time = time.time()
        
        if not raw_text or not raw_text.strip():
            return Tier1ResolveResult(
                status="NO_TEXT",
                elapsed_ms=(time.time() - start_time) * 1000
            )
        
        raw_text = raw_text.strip()
        text_lower = raw_text.lower()
        
        entities = self._load_entities(entity_type_hint)
        if not entities:
            return Tier1ResolveResult(
                status="NO_ENTITIES_IN_GRAPH",
                elapsed_ms=(time.time() - start_time) * 1000
            )
        
        matches: List[EntityMatch] = []
        matched_entity_ids: Set[str] = set()
        
        exact_matches = self._scan_for_entity_names(raw_text, text_lower, entities)
        for match in exact_matches:
            if match.entity_id not in matched_entity_ids:
                matches.append(match)
                matched_entity_ids.add(match.entity_id)
        
        alias_matches = self._check_aliases(text_lower, entities)
        for match in alias_matches:
            if match.entity_id not in matched_entity_ids:
                matches.append(match)
                matched_entity_ids.add(match.entity_id)
        
        if not matches:
            fuzzy_matches = self._fuzzy_scan(raw_text, text_lower, entities)
            for match in fuzzy_matches:
                if match.entity_id not in matched_entity_ids:
                    matches.append(match)
                    matched_entity_ids.add(match.entity_id)
        
        if not matches and self.use_embeddings:
            embedding_matches = self._embedding_search(raw_text, entity_type_hint)
            for match in embedding_matches:
                if match.entity_id not in matched_entity_ids:
                    matches.append(match)
                    matched_entity_ids.add(match.entity_id)
        
        matches.sort(key=lambda x: x.score, reverse=True)
        matches = matches[:max_entities]
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        if not matches:
            return Tier1ResolveResult(
                status="NO_MATCHES",
                extracted_terms=self._extract_noun_phrases(raw_text),
                elapsed_ms=elapsed_ms
            )
        
        top_match = matches[0]
        
        if top_match.score >= self.CONFIDENCE_THRESHOLD:
            if len(matches) > 1 and (top_match.score - matches[1].score) < 0.1:
                return Tier1ResolveResult(
                    status="AMBIGUOUS",
                    entities=matches,
                    selected=None,
                    selection_reason="Top candidates too close in score",
                    elapsed_ms=elapsed_ms
                )
            
            return Tier1ResolveResult(
                status="RESOLVED",
                entities=matches,
                selected=top_match,
                selection_reason=f"Highest score ({top_match.score:.2f}) above threshold",
                elapsed_ms=elapsed_ms
            )
        
        return Tier1ResolveResult(
            status="LOW_CONFIDENCE",
            entities=matches,
            selected=None,
            selection_reason=f"Best match ({top_match.score:.2f}) below confidence threshold ({self.CONFIDENCE_THRESHOLD})",
            elapsed_ms=elapsed_ms
        )
    
    def _load_entities(self, entity_type_hint: Optional[str] = None) -> List[Dict]:
        """Load TRUSTED entities from database."""
        if self._entity_cache is not None:
            if entity_type_hint:
                return [e for e in self._entity_cache if e['entity_type'] == entity_type_hint]
            return self._entity_cache
        
        try:
            query = self.session.query(Entity).filter(
                Entity.lifecycle_state == LifecycleState.TRUSTED
            )
            
            if self.tenant_id:
                query = query.filter(Entity.tenant_id == self.tenant_id)
            
            entities = query.all()
            
            self._entity_cache = [
                {
                    'id': str(e.id),
                    'name': e.name,
                    'name_lower': e.name.lower(),
                    'entity_type': e.entity_type,
                    'description': e.description,
                    'name_tokens': set(e.name.lower().replace('-', ' ').replace('_', ' ').split())
                }
                for e in entities
            ]
            
            if entity_type_hint:
                return [e for e in self._entity_cache if e['entity_type'] == entity_type_hint]
            return self._entity_cache
            
        except Exception as e:
            logger.error(f"Failed to load entities: {e}")
            try:
                self.session.rollback()
            except Exception:
                pass
            return []
    
    def _load_aliases(self) -> Dict[str, str]:
        """Load CONFIRMED/TRUSTED aliases from database."""
        if self._alias_cache is not None:
            return self._alias_cache
        
        self._alias_cache = {}
        
        try:
            sql = text("""
                SELECT alias_text, entity_id 
                FROM cf_entity_aliases 
                WHERE status IN ('CONFIRMED', 'TRUSTED')
                AND (:tenant_id IS NULL OR tenant_id = :tenant_id)
            """)
            
            result = self.session.execute(sql, {"tenant_id": self.tenant_id})
            for row in result:
                alias_lower = row[0].lower().strip()
                self._alias_cache[alias_lower] = row[1]
                
        except Exception as e:
            logger.debug(f"Alias table not available or empty: {e}")
            try:
                self.session.rollback()
            except Exception:
                pass
        
        return self._alias_cache
    
    def _scan_for_entity_names(
        self,
        raw_text: str,
        text_lower: str,
        entities: List[Dict]
    ) -> List[EntityMatch]:
        """Stage 1: Scan text for exact entity name occurrences."""
        matches = []
        
        entities_by_length = sorted(entities, key=lambda e: len(e['name']), reverse=True)
        
        for entity in entities_by_length:
            entity_name_lower = entity['name_lower']
            
            if entity_name_lower in text_lower:
                pattern = r'\b' + re.escape(entity_name_lower) + r'\b'
                if re.search(pattern, text_lower, re.IGNORECASE):
                    matches.append(EntityMatch(
                        entity_id=entity['id'],
                        name=entity['name'],
                        entity_type=entity['entity_type'],
                        score=self.EXACT_MATCH_SCORE,
                        evidence=["exact_name_match"],
                        match_text=entity['name'],
                        confidence=self.EXACT_MATCH_SCORE
                    ))
                    continue
                
                matches.append(EntityMatch(
                    entity_id=entity['id'],
                    name=entity['name'],
                    entity_type=entity['entity_type'],
                    score=self.SUBSTRING_MATCH_SCORE,
                    evidence=["substring_match"],
                    match_text=entity['name'],
                    confidence=self.SUBSTRING_MATCH_SCORE
                ))
        
        return matches
    
    def _check_aliases(
        self,
        text_lower: str,
        entities: List[Dict]
    ) -> List[EntityMatch]:
        """Stage 2: Check for alias matches."""
        matches = []
        aliases = self._load_aliases()
        
        entity_by_id = {e['id']: e for e in entities}
        
        for alias, entity_id in aliases.items():
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, text_lower, re.IGNORECASE):
                if entity_id in entity_by_id:
                    entity = entity_by_id[entity_id]
                    matches.append(EntityMatch(
                        entity_id=entity_id,
                        name=entity['name'],
                        entity_type=entity['entity_type'],
                        score=self.ALIAS_MATCH_SCORE,
                        evidence=["alias_match", f"alias:{alias}"],
                        match_text=alias,
                        confidence=self.ALIAS_MATCH_SCORE
                    ))
        
        return matches
    
    def _fuzzy_scan(
        self,
        raw_text: str,
        text_lower: str,
        entities: List[Dict]
    ) -> List[EntityMatch]:
        """Stage 3: Fuzzy matching for near-matches and typos."""
        matches = []
        
        words = text_lower.replace('-', ' ').replace('_', ' ').split()
        
        for entity in entities:
            entity_tokens = entity['name_tokens']
            if not entity_tokens:
                continue
            
            common_tokens = entity_tokens.intersection(set(words))
            if common_tokens:
                token_coverage = len(common_tokens) / len(entity_tokens)
                if token_coverage >= 0.5:
                    score = self.TOKEN_MATCH_SCORE * token_coverage
                    matches.append(EntityMatch(
                        entity_id=entity['id'],
                        name=entity['name'],
                        entity_type=entity['entity_type'],
                        score=score,
                        evidence=["token_overlap", f"tokens:{','.join(common_tokens)}"],
                        match_text=entity['name'],
                        confidence=score
                    ))
                    continue
            
            best_ratio = 0.0
            best_match_text = ""
            
            entity_word_count = len(entity['name'].split())
            
            for i in range(len(words)):
                for window in range(1, min(entity_word_count + 2, len(words) - i + 1)):
                    phrase = ' '.join(words[i:i + window])
                    ratio = fuzz.ratio(phrase, entity['name_lower']) / 100.0
                    partial = fuzz.partial_ratio(phrase, entity['name_lower']) / 100.0
                    score = max(ratio, partial * 0.95)
                    
                    if score > best_ratio:
                        best_ratio = score
                        best_match_text = phrase
            
            if best_ratio >= self.FUZZY_THRESHOLD:
                matches.append(EntityMatch(
                    entity_id=entity['id'],
                    name=entity['name'],
                    entity_type=entity['entity_type'],
                    score=best_ratio,
                    evidence=["fuzzy_match", f"ratio:{best_ratio:.2f}"],
                    match_text=best_match_text,
                    confidence=best_ratio
                ))
        
        matches.sort(key=lambda x: x.score, reverse=True)
        return matches[:10]
    
    def _embedding_search(
        self,
        raw_text: str,
        entity_type_hint: Optional[str] = None
    ) -> List[EntityMatch]:
        """Stage 4: Embedding similarity search as fallback."""
        try:
            query_embedding = openai_embedding(raw_text)
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return []
        
        type_filter = ""
        params = {"top_k": 5}
        
        if entity_type_hint:
            type_filter = "AND entity_type = :entity_type"
            params["entity_type"] = entity_type_hint
        
        tenant_filter = ""
        if self.tenant_id:
            tenant_filter = "AND tenant_id = :tenant_id"
            params["tenant_id"] = self.tenant_id
        
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        
        sql = text(f"""
            SELECT 
                id, name, entity_type, description,
                1 - (name_embedding <=> '{embedding_str}'::vector) as similarity
            FROM entities
            WHERE lifecycle_state = 'TRUSTED'
                AND name_embedding IS NOT NULL
                {type_filter}
                {tenant_filter}
            ORDER BY name_embedding <=> '{embedding_str}'::vector
            LIMIT :top_k
        """)
        
        try:
            result = self.session.execute(sql, params)
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Embedding search failed: {e}")
            try:
                self.session.rollback()
            except Exception:
                pass
            return []
        
        matches = []
        for row in rows:
            similarity = float(row[4]) if row[4] else 0.0
            if similarity >= self.EMBEDDING_THRESHOLD:
                matches.append(EntityMatch(
                    entity_id=str(row[0]),
                    name=row[1],
                    entity_type=row[2],
                    score=similarity,
                    evidence=["embedding_similarity", f"sim:{similarity:.3f}"],
                    match_text=raw_text[:50],
                    confidence=similarity
                ))
        
        return matches
    
    def _extract_noun_phrases(self, text: str) -> List[str]:
        """Extract potential entity mentions from text (simple heuristic)."""
        words = text.split()
        phrases = []
        
        capitalized = []
        for i, word in enumerate(words):
            clean = re.sub(r'[^\w\s]', '', word)
            if clean and clean[0].isupper():
                capitalized.append(clean)
            else:
                if capitalized:
                    phrases.append(' '.join(capitalized))
                    capitalized = []
        
        if capitalized:
            phrases.append(' '.join(capitalized))
        
        phrases = [p for p in phrases if len(p) > 2]
        
        return phrases[:5]


def tier1_resolve(
    raw_text: str,
    tenant_id: Optional[str] = None,
    entity_type_hint: Optional[str] = None,
    session: Optional[Session] = None
) -> Tier1ResolveResult:
    """
    Convenience function for Tier 1 entity resolution.
    
    Args:
        raw_text: The raw text to scan for entities
        tenant_id: Optional tenant filter
        entity_type_hint: Optional entity type filter
        session: Optional SQLAlchemy session
        
    Returns:
        Tier1ResolveResult with matched entities
    """
    resolver = Tier1Resolver(
        session=session,
        tenant_id=tenant_id,
        use_embeddings=True
    )
    return resolver.resolve_from_text(raw_text, entity_type_hint)
