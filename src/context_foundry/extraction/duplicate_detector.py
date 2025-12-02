"""
Duplicate Detection for Context Foundry MVP2.
Detects potential duplicate entities using fuzzy matching and normalization.
"""
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
import re

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.schema import Entity, EntityType, LifecycleState
from .entity_extractor import ExtractedEntity


@dataclass
class DuplicateCandidate:
    """A potential duplicate entity pair."""
    new_entity_name: str
    new_entity_type: str
    existing_entity_id: str
    existing_entity_name: str
    existing_entity_type: str
    match_type: str
    similarity_score: float
    
    def to_dict(self) -> Dict:
        return {
            "new_entity_name": self.new_entity_name,
            "new_entity_type": self.new_entity_type,
            "existing_entity_id": self.existing_entity_id,
            "existing_entity_name": self.existing_entity_name,
            "existing_entity_type": self.existing_entity_type,
            "match_type": self.match_type,
            "similarity_score": self.similarity_score,
        }


@dataclass
class DuplicateDetectionResult:
    """Result of duplicate detection."""
    entities_checked: int = 0
    exact_duplicates: int = 0
    fuzzy_duplicates: int = 0
    candidates: List[DuplicateCandidate] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "entities_checked": self.entities_checked,
            "exact_duplicates": self.exact_duplicates,
            "fuzzy_duplicates": self.fuzzy_duplicates,
            "candidates": [c.to_dict() for c in self.candidates],
        }


class DuplicateDetector:
    """
    Detects duplicate entities using multiple matching strategies.
    
    Strategies:
    1. Exact match (case-insensitive)
    2. Normalized match (remove common prefixes/suffixes)
    3. Fuzzy match (Levenshtein distance)
    4. Abbreviation match (API -> Application Programming Interface)
    """
    
    SERVICE_SUFFIXES = {"service", "api", "server", "gateway", "broker", "processor"}
    DATABASE_SUFFIXES = {"db", "database", "store", "cache"}
    
    COMMON_ABBREVIATIONS = {
        "db": "database",
        "api": "application programming interface",
        "svc": "service",
        "auth": "authentication",
        "msg": "message",
        "config": "configuration",
        "proc": "processor",
        "mgr": "manager",
    }
    
    def __init__(self, session: Session, similarity_threshold: float = 0.8):
        """
        Initialize the duplicate detector.
        
        Args:
            session: SQLAlchemy session for database operations
            similarity_threshold: Minimum similarity score for fuzzy matches (0.0-1.0)
        """
        self.session = session
        self.similarity_threshold = similarity_threshold
        self._existing_entities_cache: Optional[Dict[str, List[Entity]]] = None
    
    def _normalize_name(self, name: str) -> str:
        """Normalize an entity name for comparison."""
        normalized = name.lower().strip()
        
        normalized = re.sub(r'^(the|a|an)\s+', '', normalized)
        
        for suffix in self.SERVICE_SUFFIXES | self.DATABASE_SUFFIXES:
            normalized = re.sub(rf'\s+{suffix}$', '', normalized)
        
        normalized = re.sub(r'[_-]', ' ', normalized)
        
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        words = normalized.split()
        singularized = []
        for word in words:
            if word.endswith('ies'):
                singularized.append(word[:-3] + 'y')
            elif word.endswith('es') and len(word) > 3:
                singularized.append(word[:-2])
            elif word.endswith('s') and len(word) > 2 and not word.endswith('ss'):
                singularized.append(word[:-1])
            else:
                singularized.append(word)
        normalized = ' '.join(singularized)
        
        for abbr, expansion in self.COMMON_ABBREVIATIONS.items():
            if normalized == abbr or normalized.endswith(' ' + abbr):
                normalized = normalized.replace(abbr, expansion.split()[0])
        
        return normalized
    
    def _expand_abbreviations(self, name: str) -> str:
        """Expand common abbreviations in a name."""
        words = name.lower().split()
        expanded = []
        for word in words:
            if word in self.COMMON_ABBREVIATIONS:
                expanded.append(self.COMMON_ABBREVIATIONS[word])
            else:
                expanded.append(word)
        return ' '.join(expanded)
    
    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity based on Levenshtein distance."""
        if not s1 or not s2:
            return 0.0
        
        if s1 == s2:
            return 1.0
        
        len1, len2 = len(s1), len(s2)
        if len1 < len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1
        
        previous_row = list(range(len2 + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        distance = previous_row[-1]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len)
    
    def _load_existing_entities(self) -> Dict[str, List[Entity]]:
        """Load existing entities grouped by normalized name."""
        if self._existing_entities_cache is not None:
            return self._existing_entities_cache
        
        entities = self.session.query(Entity).filter(
            Entity.lifecycle_state.in_([LifecycleState.STAGING, LifecycleState.TRUSTED])
        ).all()
        
        grouped: Dict[str, List[Entity]] = {}
        for entity in entities:
            normalized = self._normalize_name(entity.name)
            if normalized not in grouped:
                grouped[normalized] = []
            grouped[normalized].append(entity)
        
        self._existing_entities_cache = grouped
        return grouped
    
    def clear_cache(self):
        """Clear the entity cache."""
        self._existing_entities_cache = None
    
    def find_exact_duplicate(
        self, 
        name: str, 
        entity_type: Optional[str] = None
    ) -> Optional[Entity]:
        """Find exact duplicate (case-insensitive)."""
        query = self.session.query(Entity).filter(
            func.lower(Entity.name) == name.lower()
        )
        if entity_type:
            try:
                et = EntityType(entity_type)
                query = query.filter(Entity.entity_type == et)
            except ValueError:
                pass
        
        return query.first()
    
    def find_normalized_duplicate(
        self, 
        name: str, 
        entity_type: Optional[str] = None
    ) -> Optional[Entity]:
        """Find duplicate by normalized name."""
        normalized = self._normalize_name(name)
        existing = self._load_existing_entities()
        
        if normalized in existing:
            for entity in existing[normalized]:
                if entity_type:
                    try:
                        et = EntityType(entity_type)
                        if entity.entity_type == et:
                            return entity
                    except ValueError:
                        pass
                else:
                    return entity
        
        return None
    
    def find_fuzzy_duplicates(
        self, 
        name: str, 
        entity_type: Optional[str] = None,
        top_n: int = 5
    ) -> List[Tuple[Entity, float]]:
        """Find potential duplicates using fuzzy matching."""
        normalized_query = self._normalize_name(name)
        expanded_query = self._expand_abbreviations(normalized_query)
        existing = self._load_existing_entities()
        
        candidates: List[Tuple[Entity, float]] = []
        
        for normalized_name, entities in existing.items():
            base_sim = self._levenshtein_similarity(normalized_query, normalized_name)
            
            expanded_existing = self._expand_abbreviations(normalized_name)
            expanded_sim = self._levenshtein_similarity(expanded_query, expanded_existing)
            
            best_sim = max(base_sim, expanded_sim)
            
            if best_sim >= self.similarity_threshold:
                for entity in entities:
                    if entity_type:
                        try:
                            et = EntityType(entity_type)
                            if entity.entity_type != et:
                                continue
                        except ValueError:
                            pass
                    candidates.append((entity, best_sim))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_n]
    
    def detect_duplicates(
        self, 
        extracted_entities: List[ExtractedEntity]
    ) -> DuplicateDetectionResult:
        """
        Detect duplicates for a list of extracted entities.
        
        Args:
            extracted_entities: List of ExtractedEntity to check
            
        Returns:
            DuplicateDetectionResult with found duplicates
        """
        result = DuplicateDetectionResult(entities_checked=len(extracted_entities))
        
        self.clear_cache()
        
        for extracted in extracted_entities:
            exact = self.find_exact_duplicate(
                extracted.canonical_name, 
                extracted.entity_type
            )
            if exact:
                result.exact_duplicates += 1
                result.candidates.append(DuplicateCandidate(
                    new_entity_name=extracted.canonical_name,
                    new_entity_type=extracted.entity_type,
                    existing_entity_id=str(exact.id),
                    existing_entity_name=exact.name,
                    existing_entity_type=exact.entity_type.value,
                    match_type="exact",
                    similarity_score=1.0,
                ))
                continue
            
            normalized = self.find_normalized_duplicate(
                extracted.canonical_name,
                extracted.entity_type
            )
            if normalized:
                result.fuzzy_duplicates += 1
                result.candidates.append(DuplicateCandidate(
                    new_entity_name=extracted.canonical_name,
                    new_entity_type=extracted.entity_type,
                    existing_entity_id=str(normalized.id),
                    existing_entity_name=normalized.name,
                    existing_entity_type=normalized.entity_type.value,
                    match_type="normalized",
                    similarity_score=0.95,
                ))
                continue
            
            fuzzy_matches = self.find_fuzzy_duplicates(
                extracted.canonical_name,
                extracted.entity_type,
                top_n=1
            )
            if fuzzy_matches:
                entity, score = fuzzy_matches[0]
                result.fuzzy_duplicates += 1
                result.candidates.append(DuplicateCandidate(
                    new_entity_name=extracted.canonical_name,
                    new_entity_type=extracted.entity_type,
                    existing_entity_id=str(entity.id),
                    existing_entity_name=entity.name,
                    existing_entity_type=entity.entity_type.value,
                    match_type="fuzzy",
                    similarity_score=score,
                ))
        
        return result
    
    def deduplicate_entities(
        self, 
        extracted_entities: List[ExtractedEntity],
        merge_strategy: str = "highest_confidence"
    ) -> List[ExtractedEntity]:
        """
        Deduplicate a list of extracted entities within the batch.
        
        Args:
            extracted_entities: List of ExtractedEntity to deduplicate
            merge_strategy: How to handle duplicates ('highest_confidence', 'first', 'merge')
            
        Returns:
            Deduplicated list of ExtractedEntity
        """
        seen: Dict[Tuple[str, str], ExtractedEntity] = {}
        
        for entity in extracted_entities:
            key = (self._normalize_name(entity.canonical_name), entity.entity_type)
            
            if key not in seen:
                seen[key] = entity
            elif merge_strategy == "highest_confidence":
                if entity.confidence > seen[key].confidence:
                    seen[key] = entity
            elif merge_strategy == "merge":
                existing = seen[key]
                merged_props = {**existing.properties, **entity.properties}
                if entity.confidence > existing.confidence:
                    existing.confidence = entity.confidence
                    existing.properties = merged_props
        
        return list(seen.values())
