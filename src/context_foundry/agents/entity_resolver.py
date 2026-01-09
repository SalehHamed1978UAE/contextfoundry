"""
Entity Resolver - Semantic entity resolution for Context Foundry.

Implements a three-stage entity resolution pipeline:
1. Stage 1: Exact match (fast, covers ~60% of queries)
2. Stage 2: Semantic search with OpenAI embeddings (similarity > 0.75)
3. Stage 3: Fuzzy string matching with Levenshtein ratio (> 0.7)

Plus disambiguation when multiple candidates score within 0.1 of each other.
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
from rapidfuzz import fuzz
from sqlalchemy.orm import Session
from sqlalchemy import text
import inflect

from ..models.schema import Entity, EntityAlias, LifecycleState, get_session
from ..memory.episodic import openai_embedding, EMBEDDING_DIM
from ..utils.logger import logger

_inflect_engine = inflect.engine()

ABBREVIATION_MAP = {
    "auth": "authentication",
    "db": "database",
    "svc": "service",
    "srv": "service", 
    "svr": "server",
    "msg": "message",
    "mgr": "manager",
    "cfg": "config",
    "config": "configuration",
    "repo": "repository",
    "api": "api",
    "k8s": "kubernetes",
    "pg": "postgresql",
    "postgres": "postgresql",
    "redis": "redis",
    "mq": "message queue",
    "lb": "load balancer",
    "cdn": "content delivery network",
    "ci": "continuous integration",
    "cd": "continuous deployment",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "vpc": "virtual private cloud",
    "vm": "virtual machine",
    "ec2": "elastic compute cloud",
    "s3": "simple storage service",
    "rds": "relational database service",
    "iam": "identity access management",
    "dns": "domain name system",
    "ssl": "secure sockets layer",
    "tls": "transport layer security",
    "http": "hypertext transfer protocol",
    "https": "hypertext transfer protocol secure",
    "ui": "user interface",
    "ux": "user experience",
    "qa": "quality assurance",
}

def normalize_for_matching(name: str) -> str:
    """
    Normalize entity name for matching by:
    1. Converting to lowercase
    2. Expanding common abbreviations (preserving token boundaries)
    3. Singularizing plural words using inflect
    4. Sorting tokens for order-independent matching
    """
    tokens = name.lower().replace('-', ' ').replace('_', ' ').split()
    expanded_tokens = []
    for token in tokens:
        expansion = ABBREVIATION_MAP.get(token, token)
        expanded_tokens.extend(expansion.split())
    
    normalized = []
    for token in expanded_tokens:
        singular = _inflect_engine.singular_noun(token)
        normalized.append(singular if singular else token)
    return ' '.join(sorted(normalized))


@dataclass
class EntityCandidate:
    """A candidate entity match with scoring details."""
    entity_id: str
    name: str
    entity_type: str
    description: Optional[str]
    score: float
    match_stage: str
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "score": round(self.score, 4),
            "match_stage": self.match_stage,
            "confidence": round(self.confidence, 4)
        }


@dataclass
class ResolveResult:
    """Result of entity resolution."""
    entity: Optional[EntityCandidate] = None
    confidence: float = 0.0
    needs_disambiguation: bool = False
    candidates: List[EntityCandidate] = field(default_factory=list)
    match_stage: str = "none"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity.to_dict() if self.entity else None,
            "confidence": round(self.confidence, 4),
            "needs_disambiguation": self.needs_disambiguation,
            "candidates": [c.to_dict() for c in self.candidates],
            "match_stage": self.match_stage
        }


class EntityResolver:
    """
    Three-stage entity resolution with semantic search and disambiguation.
    
    Stages:
    1. Exact match - case-insensitive exact match (fastest)
    2. Semantic search - OpenAI embeddings with cosine similarity
    3. Fuzzy match - Levenshtein ratio for typo tolerance
    
    Disambiguation:
    When top candidates are within 0.1 score of each other, returns
    needs_disambiguation=True with candidate list for user clarification.
    """
    
    EXACT_MATCH_THRESHOLD = 0.95
    SEMANTIC_THRESHOLD = 0.75
    FUZZY_THRESHOLD = 0.70
    DISAMBIGUATION_DELTA = 0.1
    
    def __init__(self, session: Optional[Session] = None, tenant_id: Optional[str] = None):
        from uuid import UUID as PyUUID
        from sqlalchemy import text
        self.session = session or get_session()
        self._tenant_id_str = tenant_id
        self.tenant_id = PyUUID(tenant_id) if isinstance(tenant_id, str) and tenant_id else None
        
        # Set RLS context for tenant isolation
        if self.tenant_id:
            try:
                self.session.execute(
                    text("SET LOCAL app.current_tenant_id = :tenant_id"),
                    {"tenant_id": str(self.tenant_id)}
                )
            except Exception as e:
                logger.debug(f"EntityResolver: RLS context set failed: {e}")
        
        logger.info("EntityResolver initialized")
    
    def resolve(
        self,
        query: str,
        entity_type_hint: Optional[str] = None,
        top_k: int = 20
    ) -> ResolveResult:
        """
        Resolve a query string to the best matching entity.
        
        Args:
            query: The search query (entity name or description)
            entity_type_hint: Optional type filter (e.g., 'SERVICE', 'PERSON')
            top_k: Maximum candidates to consider in semantic search
            
        Returns:
            ResolveResult with matched entity or disambiguation candidates
        """
        if not query or not query.strip():
            return ResolveResult(match_stage="empty_query")
        
        query = query.strip()
        
        # Re-set RLS context in case previous rollback cleared it
        if self.tenant_id:
            try:
                from sqlalchemy import text
                self.session.execute(
                    text("SET LOCAL app.current_tenant_id = :tenant_id"),
                    {"tenant_id": str(self.tenant_id)}
                )
            except Exception:
                pass
        logger.debug(f"Resolving entity: '{query}' (type_hint={entity_type_hint})")
        
        exact_result = self._exact_match(query, entity_type_hint)
        if exact_result.entity and exact_result.confidence >= self.EXACT_MATCH_THRESHOLD:
            logger.info(f"Exact match found: {exact_result.entity.name}")
            return exact_result
        if exact_result.needs_disambiguation:
            logger.info(f"Exact match disambiguation: {len(exact_result.candidates)} candidates")
            return exact_result
        
        alias_result = self._alias_match(query, entity_type_hint)
        if alias_result.entity and alias_result.confidence >= self.EXACT_MATCH_THRESHOLD:
            logger.info(f"Alias match found: {alias_result.entity.name}")
            return alias_result
        if alias_result.needs_disambiguation:
            logger.info(f"Alias match disambiguation: {len(alias_result.candidates)} candidates")
            return alias_result
        
        contains_result = self._contains_match(query, entity_type_hint)
        if contains_result.entity and contains_result.confidence >= 0.80:
            logger.info(f"Contains match found: {contains_result.entity.name}")
            return contains_result
        if contains_result.needs_disambiguation:
            logger.info(f"Contains match disambiguation: {len(contains_result.candidates)} candidates")
            return contains_result
        
        normalized_result = self._normalized_match(query, entity_type_hint)
        if normalized_result.entity and normalized_result.confidence >= 0.90:
            logger.info(f"Normalized match found: {normalized_result.entity.name} (query: '{query}')")
            return normalized_result
        if normalized_result.needs_disambiguation:
            logger.info(f"Normalized match disambiguation: {len(normalized_result.candidates)} candidates")
            return normalized_result
        
        semantic_result = self._semantic_search(query, entity_type_hint, top_k)
        if semantic_result.entity and semantic_result.confidence >= self.SEMANTIC_THRESHOLD:
            logger.info(f"Semantic match found: {semantic_result.entity.name}")
            return semantic_result
        if semantic_result.needs_disambiguation:
            logger.info(f"Semantic disambiguation: {len(semantic_result.candidates)} candidates")
            return semantic_result
        
        fuzzy_result = self._fuzzy_match(query, entity_type_hint)
        if fuzzy_result.entity and fuzzy_result.confidence >= self.FUZZY_THRESHOLD:
            logger.info(f"Fuzzy match found: {fuzzy_result.entity.name}")
            return fuzzy_result
        if fuzzy_result.needs_disambiguation:
            logger.info(f"Fuzzy disambiguation: {len(fuzzy_result.candidates)} candidates")
            return fuzzy_result
        
        logger.info(f"No match found for: '{query}'")
        return ResolveResult(match_stage="not_found")
    
    def resolve_alias(self, alias_text: str, entity_type_hint: Optional[str] = None) -> Optional[Entity]:
        """
        Public method to resolve an alias to an Entity.
        
        Used by RetrievalAgent to resolve acronyms/abbreviations to full entity names.
        Returns the Entity if found, None otherwise.
        """
        result = self._alias_match(alias_text, entity_type_hint)
        if result.entity:
            entity = self.session.query(Entity).filter(
                Entity.id == result.entity.entity_id
            ).first()
            return entity
        return None
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for matching."""
        import re
        name = name.lower().strip()
        name = re.sub(r'^(the|a|an)\s+', '', name)
        name = re.sub(r'\s+', ' ', name)
        return name
    
    def _normalized_match(
        self,
        query: str,
        entity_type_hint: Optional[str] = None
    ) -> ResolveResult:
        """
        Stage 2: Normalized match using inflect for plural/singular normalization
        and abbreviation expansion.
        
        This catches cases like:
        - "User Database" → "Users Database"
        - "Auth Service" → "Authentication Service"
        - "DB Service" → "Database Service"
        """
        normalized_query = normalize_for_matching(query)
        logger.debug(f"Normalized query: '{query}' → '{normalized_query}'")
        
        if self._tenant_id_str:
            try:
                self.session.execute(
                    text("SELECT platform.set_current_tenant(:tid)"),
                    {'tid': self._tenant_id_str}
                )
            except Exception:
                pass
        
        base_query = self.session.query(Entity).filter(
            Entity.lifecycle_state == LifecycleState.TRUSTED
        )
        
        if entity_type_hint:
            base_query = base_query.filter(Entity.entity_type == entity_type_hint)
        
        if self.tenant_id:
            base_query = base_query.filter(Entity.tenant_id == self.tenant_id)
        
        entities = base_query.limit(2000).all()
        logger.debug(f"Normalized match: loaded {len(entities)} entities")
        
        candidates = []
        for entity in entities:
            normalized_name = normalize_for_matching(entity.name)
            
            if normalized_query == normalized_name:
                candidates.append(EntityCandidate(
                    entity_id=str(entity.id),
                    name=entity.name,
                    entity_type=entity.entity_type,
                    description=entity.description,
                    score=0.96,
                    match_stage="normalized",
                    confidence=0.96
                ))
        
        if not candidates:
            return ResolveResult(match_stage="normalized")
        
        return self._check_disambiguation(candidates, "normalized")
    
    def _contains_match(
        self,
        query: str,
        entity_type_hint: Optional[str] = None
    ) -> ResolveResult:
        """Stage 1.5: Contains match - query in entity name or entity name in query."""
        normalized_query = self._normalize_name(query)
        
        base_query = self.session.query(Entity).filter(
            Entity.lifecycle_state == LifecycleState.TRUSTED,
            Entity.name.ilike(f'%{query}%')
        )
        
        if entity_type_hint:
            base_query = base_query.filter(Entity.entity_type == entity_type_hint)
        
        if self.tenant_id:
            base_query = base_query.filter(Entity.tenant_id == self.tenant_id)
        
        matches = base_query.limit(50).all()
        
        candidates = []
        for entity in matches:
            normalized_name = self._normalize_name(entity.name)
            if normalized_query == normalized_name:
                score = 0.98
            elif normalized_query in normalized_name:
                score = 0.95 - (len(normalized_name) - len(normalized_query)) * 0.01
                score = max(score, 0.85)
            elif normalized_name in normalized_query:
                score = 0.92 - (len(normalized_query) - len(normalized_name)) * 0.01
                score = max(score, 0.80)
            else:
                score = 0.90
            
            candidates.append(EntityCandidate(
                entity_id=str(entity.id),
                name=entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                score=score,
                match_stage="contains",
                confidence=score
            ))
        
        candidates.sort(key=lambda x: x.score, reverse=True)
        
        if not candidates:
            return ResolveResult(match_stage="contains")
        
        return self._check_disambiguation(candidates, "contains")
    
    def _exact_match(
        self,
        query: str,
        entity_type_hint: Optional[str] = None
    ) -> ResolveResult:
        """Stage 1: Exact case-insensitive match."""
        base_query = self.session.query(Entity).filter(
            Entity.lifecycle_state == LifecycleState.TRUSTED,
            Entity.name.ilike(query)
        )
        
        if entity_type_hint:
            base_query = base_query.filter(Entity.entity_type == entity_type_hint)
        
        if self.tenant_id:
            base_query = base_query.filter(Entity.tenant_id == self.tenant_id)
        
        matches = base_query.all()
        
        if not matches:
            return ResolveResult(match_stage="exact")
        
        if len(matches) == 1:
            entity = matches[0]
            candidate = EntityCandidate(
                entity_id=str(entity.id),
                name=entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                score=1.0,
                match_stage="exact",
                confidence=1.0
            )
            return ResolveResult(
                entity=candidate,
                confidence=1.0,
                match_stage="exact"
            )
        
        candidates = [
            EntityCandidate(
                entity_id=str(e.id),
                name=e.name,
                entity_type=e.entity_type,
                description=e.description,
                score=1.0,
                match_stage="exact",
                confidence=1.0
            )
            for e in matches
        ]
        
        return ResolveResult(
            entity=None,
            confidence=1.0,
            needs_disambiguation=True,
            candidates=candidates,
            match_stage="exact"
        )
    
    def _alias_match(
        self,
        query: str,
        entity_type_hint: Optional[str] = None
    ) -> ResolveResult:
        """Stage 1.5: Alias match - check if query matches any entity alias."""
        base_query = self.session.query(Entity).join(
            EntityAlias, Entity.id == EntityAlias.entity_id
        ).filter(
            Entity.lifecycle_state == LifecycleState.TRUSTED,
            EntityAlias.alias.ilike(query)
        )
        
        if entity_type_hint:
            base_query = base_query.filter(Entity.entity_type == entity_type_hint)
        
        if self.tenant_id:
            base_query = base_query.filter(
                Entity.tenant_id == self.tenant_id,
                EntityAlias.tenant_id == self.tenant_id
            )
        
        matches = base_query.all()
        
        if not matches:
            return ResolveResult(match_stage="alias")
        
        if len(matches) == 1:
            entity = matches[0]
            candidate = EntityCandidate(
                entity_id=str(entity.id),
                name=entity.name,
                entity_type=entity.entity_type,
                description=entity.description,
                score=0.98,
                match_stage="alias",
                confidence=0.98
            )
            logger.debug(f"Alias resolved: '{query}' -> {entity.name}")
            return ResolveResult(
                entity=candidate,
                confidence=0.98,
                match_stage="alias"
            )
        
        candidates = [
            EntityCandidate(
                entity_id=str(e.id),
                name=e.name,
                entity_type=e.entity_type,
                description=e.description,
                score=0.98,
                match_stage="alias",
                confidence=0.98
            )
            for e in matches
        ]
        
        return ResolveResult(
            entity=None,
            confidence=0.98,
            needs_disambiguation=True,
            candidates=candidates,
            match_stage="alias"
        )
    
    def _semantic_search(
        self,
        query: str,
        entity_type_hint: Optional[str] = None,
        top_k: int = 20
    ) -> ResolveResult:
        """Stage 2: Semantic search using OpenAI embeddings."""
        try:
            query_embedding = openai_embedding(query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return ResolveResult(match_stage="semantic_error")
        
        type_filter = ""
        params = {"top_k": top_k}
        
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
            logger.error(f"Semantic search query failed: {e}")
            try:
                self.session.rollback()
            except Exception:
                pass
            return ResolveResult(match_stage="semantic_error")
        
        if not rows:
            return ResolveResult(match_stage="semantic")
        
        candidates = []
        for row in rows:
            candidates.append(EntityCandidate(
                entity_id=str(row[0]),
                name=row[1],
                entity_type=row[2],
                description=row[3],
                score=float(row[4]) if row[4] else 0.0,
                match_stage="semantic",
                confidence=float(row[4]) if row[4] else 0.0
            ))
        
        return self._check_disambiguation(candidates, "semantic")
    
    def _fuzzy_match(
        self,
        query: str,
        entity_type_hint: Optional[str] = None
    ) -> ResolveResult:
        """Stage 3: Fuzzy string matching using Levenshtein ratio."""
        try:
            self.session.rollback()
        except Exception:
            pass
        
        try:
            base_query = self.session.query(Entity).filter(
                Entity.lifecycle_state == LifecycleState.TRUSTED
            )
            
            if entity_type_hint:
                base_query = base_query.filter(Entity.entity_type == entity_type_hint)
            
            if self.tenant_id:
                base_query = base_query.filter(Entity.tenant_id == self.tenant_id)
            
            entities = base_query.limit(5000).all()
            logger.debug(f"Fuzzy match: loaded {len(entities)} entities")
        except Exception as e:
            logger.error(f"Fuzzy match query failed: {e}")
            try:
                self.session.rollback()
            except Exception:
                pass
            return ResolveResult(match_stage="fuzzy_error")
        
        candidates = []
        query_lower = query.lower()
        
        for entity in entities:
            name_lower = entity.name.lower()
            ratio = fuzz.ratio(query_lower, name_lower) / 100.0
            token_ratio = fuzz.token_sort_ratio(query_lower, name_lower) / 100.0
            partial_ratio = fuzz.partial_ratio(query_lower, name_lower) / 100.0
            
            query_words = set(query_lower.split())
            name_words = set(name_lower.replace('-', ' ').split())
            word_overlap = len(query_words & name_words) / len(query_words) if query_words else 0
            word_boost = word_overlap * 0.15
            
            combined_score = max(ratio, token_ratio * 0.95, partial_ratio * 0.9) + word_boost
            combined_score = min(combined_score, 0.99)
            
            if combined_score >= self.FUZZY_THRESHOLD:
                candidates.append(EntityCandidate(
                    entity_id=str(entity.id),
                    name=entity.name,
                    entity_type=entity.entity_type,
                    description=entity.description,
                    score=combined_score,
                    match_stage="fuzzy",
                    confidence=combined_score
                ))
        
        candidates.sort(key=lambda x: x.score, reverse=True)
        candidates = candidates[:20]
        
        logger.debug(f"Fuzzy match: {len(candidates)} candidates above threshold {self.FUZZY_THRESHOLD}")
        
        if not candidates:
            return ResolveResult(match_stage="fuzzy")
        
        return self._check_disambiguation(candidates, "fuzzy")
    
    def _check_disambiguation(
        self,
        candidates: List[EntityCandidate],
        stage: str
    ) -> ResolveResult:
        """Check if disambiguation is needed based on score delta."""
        if not candidates:
            return ResolveResult(match_stage=stage)
        
        top = candidates[0]
        
        if len(candidates) == 1:
            return ResolveResult(
                entity=top,
                confidence=top.score,
                match_stage=stage
            )
        
        second = candidates[1]
        delta = top.score - second.score
        
        if delta < self.DISAMBIGUATION_DELTA:
            close_candidates = [c for c in candidates if top.score - c.score < self.DISAMBIGUATION_DELTA]
            return ResolveResult(
                entity=None,
                confidence=top.score,
                needs_disambiguation=True,
                candidates=close_candidates[:5],
                match_stage=stage
            )
        
        return ResolveResult(
            entity=top,
            confidence=top.score,
            candidates=candidates[:3],
            match_stage=stage
        )
    
    def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        """Retrieve entity by ID."""
        try:
            from uuid import UUID
            entity_uuid = UUID(entity_id)
            return self.session.query(Entity).filter(Entity.id == entity_uuid).first()
        except Exception as e:
            logger.error(f"Failed to get entity by ID {entity_id}: {e}")
            return None


def compute_entity_embedding(entity: Entity) -> Optional[List[float]]:
    """
    Compute embedding for an entity based on name and description.
    
    Args:
        entity: Entity to compute embedding for
        
    Returns:
        List of floats (1536 dimensions) or None on failure
    """
    text_for_embedding = entity.name
    if entity.description:
        text_for_embedding = f"{entity.name}: {entity.description}"
    if entity.entity_type:
        text_for_embedding = f"[{entity.entity_type}] {text_for_embedding}"
    
    try:
        return openai_embedding(text_for_embedding)
    except Exception as e:
        logger.error(f"Failed to compute embedding for entity {entity.name}: {e}")
        return None


def batch_compute_entity_embeddings(
    session: Optional[Session] = None,
    batch_size: int = 50,
    only_missing: bool = True,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Batch compute embeddings for TRUSTED entities.
    
    Args:
        session: SQLAlchemy session
        batch_size: Number of entities to process per batch
        only_missing: Only process entities without embeddings
        tenant_id: Optional tenant filter
        
    Returns:
        Statistics about the batch job
    """
    session = session or get_session()
    
    query = session.query(Entity).filter(
        Entity.lifecycle_state == LifecycleState.TRUSTED
    )
    
    if only_missing:
        query = query.filter(Entity.name_embedding.is_(None))
    
    if tenant_id:
        query = query.filter(Entity.tenant_id == tenant_id)
    
    total_count = query.count()
    logger.info(f"Starting batch embedding job for {total_count} entities")
    
    stats = {
        "total": total_count,
        "processed": 0,
        "success": 0,
        "failed": 0,
        "errors": []
    }
    
    offset = 0
    while offset < total_count:
        batch = query.offset(offset).limit(batch_size).all()
        
        for entity in batch:
            try:
                embedding = compute_entity_embedding(entity)
                if embedding:
                    entity.name_embedding = embedding
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
                    stats["errors"].append(f"No embedding returned for {entity.name}")
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"Error for {entity.name}: {str(e)}")
            
            stats["processed"] += 1
            
            if stats["processed"] % 100 == 0:
                logger.info(f"Processed {stats['processed']}/{total_count} entities")
        
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Batch commit failed: {e}")
            stats["errors"].append(f"Batch commit failed at offset {offset}")
        
        offset += batch_size
    
    logger.info(f"Batch embedding complete: {stats['success']} success, {stats['failed']} failed")
    return stats
