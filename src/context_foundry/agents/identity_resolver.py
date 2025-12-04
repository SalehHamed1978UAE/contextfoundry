"""
Identity Resolution for Context Foundry.

Detects and merges duplicate entities using multiple weighted signals:
1. exact_name_match (0.95) - Canonical names identical
2. external_id_match (0.95) - Same ID from authoritative source
3. email_match (0.90) - Same email (Person entities)
4. alias_overlap (0.40) - Shared alias between entities
5. name_similarity (0.30) - Jaro-Winkler > 0.85
6. relationship_overlap (0.25) - Same relationships to same targets
7. co_occurrence (0.15) - Mentioned together in same documents

Conservative merge policy:
- Auto-merge at >= 0.95 confidence (except PERSON)
- Flag for review at 0.70-0.95
- Never auto-merge Person entities - ALWAYS flag for review
"""
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from ..models.schema import (
    Entity, Relationship, LifecycleState, EntityType,
    MergeAudit as MergeAuditDB,
    DuplicateCandidate as DuplicateCandidateDB,
)
from ..utils.logger import logger


# Signal weights as specified
SIGNAL_WEIGHTS = {
    'exact_name_match': 0.95,
    'external_id_match': 0.95,
    'email_match': 0.90,
    'alias_overlap': 0.40,
    'name_similarity': 0.30,
    'relationship_overlap': 0.25,
    'co_occurrence': 0.15,
}


def jaro_winkler_similarity(s1: str, s2: str) -> float:
    """
    Calculate Jaro-Winkler similarity between two strings.
    Returns a score between 0.0 and 1.0 where 1.0 is an exact match.
    """
    if s1 == s2:
        return 1.0
    
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0
    
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0
    
    s1_matches = [False] * len1
    s2_matches = [False] * len2
    
    matches = 0
    transpositions = 0
    
    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break
    
    if matches == 0:
        return 0.0
    
    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1
    
    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3
    
    prefix = 0
    for i in range(min(len1, len2, 4)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
    
    return jaro + prefix * 0.1 * (1 - jaro)


class MergeDecision(str, Enum):
    AUTO_MERGE = "auto_merge"
    FLAG_FOR_REVIEW = "flag_for_review"
    NO_MERGE = "no_merge"
    BLOCKED = "blocked"


@dataclass
class DuplicateCandidate:
    """A pair of entities that may be duplicates."""
    entity_a_id: str
    entity_b_id: str
    entity_a_name: str
    entity_b_name: str
    entity_type: str
    similarity_score: float
    signals: List[str]
    merge_decision: MergeDecision
    reason: str = ""
    flagged_at: datetime = field(default_factory=datetime.utcnow)
    reviewed: bool = False
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "entity_a_id": self.entity_a_id,
            "entity_b_id": self.entity_b_id,
            "entity_a_name": self.entity_a_name,
            "entity_b_name": self.entity_b_name,
            "entity_type": self.entity_type,
            "similarity_score": self.similarity_score,
            "signals": self.signals,
            "merge_decision": self.merge_decision.value,
            "reason": self.reason,
            "flagged_at": self.flagged_at.isoformat(),
            "reviewed": self.reviewed,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
        }


@dataclass
class MergeAuditRecord:
    """Audit trail for entity merges."""
    id: str
    merged_entity_id: str
    merged_entity_name: str
    surviving_entity_id: str
    surviving_entity_name: str
    entity_type: str
    merge_confidence: float
    merge_signals: List[str]
    auto_merged: bool
    relationships_transferred: int = 0
    properties_merged: Dict = field(default_factory=dict)
    merged_at: datetime = field(default_factory=datetime.utcnow)
    merged_by: str = "identity_resolver"
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "merged_entity_id": self.merged_entity_id,
            "merged_entity_name": self.merged_entity_name,
            "surviving_entity_id": self.surviving_entity_id,
            "surviving_entity_name": self.surviving_entity_name,
            "entity_type": self.entity_type,
            "merge_confidence": self.merge_confidence,
            "merge_signals": self.merge_signals,
            "auto_merged": self.auto_merged,
            "relationships_transferred": self.relationships_transferred,
            "properties_merged": self.properties_merged,
            "merged_at": self.merged_at.isoformat(),
            "merged_by": self.merged_by,
        }


@dataclass
class IdentityResolutionConfig:
    """Configuration for identity resolution."""
    auto_merge_threshold: float = 0.95
    review_threshold: float = 0.70
    never_auto_merge_types: List[str] = field(default_factory=lambda: ["PERSON"])
    
    exact_name_weight: float = SIGNAL_WEIGHTS['exact_name_match']
    external_id_weight: float = SIGNAL_WEIGHTS['external_id_match']
    email_weight: float = SIGNAL_WEIGHTS['email_match']
    alias_overlap_weight: float = SIGNAL_WEIGHTS['alias_overlap']
    name_similarity_weight: float = SIGNAL_WEIGHTS['name_similarity']
    relationship_overlap_weight: float = SIGNAL_WEIGHTS['relationship_overlap']
    co_occurrence_weight: float = SIGNAL_WEIGHTS['co_occurrence']
    
    name_similarity_threshold: float = 0.85
    min_relationship_overlap_count: int = 2


@dataclass
class IdentityResolutionResult:
    """Result of identity resolution run."""
    started_at: datetime
    completed_at: Optional[datetime] = None
    entities_scanned: int = 0
    candidates_found: int = 0
    auto_merged: int = 0
    flagged_for_review: int = 0
    relationships_transferred: int = 0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "entities_scanned": self.entities_scanned,
            "candidates_found": self.candidates_found,
            "auto_merged": self.auto_merged,
            "flagged_for_review": self.flagged_for_review,
            "relationships_transferred": self.relationships_transferred,
            "errors": self.errors,
        }


class IdentityResolver:
    """
    Identity resolution agent that detects and merges duplicate entities.
    
    Uses three signals:
    1. Exact name match (case-insensitive)
    2. Alias overlap (from properties.aliases)
    3. Relationship overlap (shared relationships)
    
    Conservative merge policy:
    - Auto-merge only at >= 0.95 confidence
    - Flag for review at 0.70-0.95
    - Never auto-merge Person entities
    """
    
    def __init__(
        self,
        session: Session,
        config: Optional[IdentityResolutionConfig] = None,
    ):
        self.session = session
        self.config = config or IdentityResolutionConfig()
        self.candidates: List[DuplicateCandidate] = []
        self.merge_audit: List[MergeAuditRecord] = []
    
    def run(self, commit: bool = True, staging_only: bool = True) -> IdentityResolutionResult:
        """
        Run identity resolution to detect duplicate entities.
        
        Args:
            commit: Whether to commit merges to database
            staging_only: If True, only compare STAGING entities against all
                          If False, compare all entities (slower, for batch cleanup)
            
        Returns:
            IdentityResolutionResult with metrics
        """
        result = IdentityResolutionResult(started_at=datetime.utcnow())
        
        try:
            staging_entities = self.session.query(Entity).filter(
                Entity.lifecycle_state == LifecycleState.STAGING
            ).all()
            
            all_entities = self.session.query(Entity).filter(
                Entity.lifecycle_state.in_([
                    LifecycleState.STAGING,
                    LifecycleState.TRUSTED,
                ])
            ).all()
            
            result.entities_scanned = len(all_entities)
            
            if staging_only:
                candidates = self._find_staging_duplicates(staging_entities, all_entities)
            else:
                entities_by_type: Dict[str, List[Entity]] = {}
                for entity in all_entities:
                    t = entity.entity_type
                    if t not in entities_by_type:
                        entities_by_type[t] = []
                    entities_by_type[t].append(entity)
                
                candidates = []
                for entity_type, type_entities in entities_by_type.items():
                    candidates.extend(self._find_duplicates_in_type(type_entities))
            
            for candidate in candidates:
                self.candidates.append(candidate)
                result.candidates_found += 1
                
                if candidate.merge_decision == MergeDecision.AUTO_MERGE:
                    merge_result = self._perform_merge(candidate)
                    if merge_result:
                        result.auto_merged += 1
                        result.relationships_transferred += merge_result.relationships_transferred
                elif candidate.merge_decision == MergeDecision.FLAG_FOR_REVIEW:
                    self._persist_duplicate_candidate(candidate)
                    result.flagged_for_review += 1
            
            if commit:
                self.session.commit()
            
            logger.info(f"Identity resolution: scanned={result.entities_scanned}, "
                       f"found={result.candidates_found}, merged={result.auto_merged}, "
                       f"flagged={result.flagged_for_review}")
                
        except Exception as e:
            self.session.rollback()
            result.errors.append(str(e))
            logger.error(f"Identity resolution error: {e}")
        
        result.completed_at = datetime.utcnow()
        return result
    
    def _find_staging_duplicates(
        self,
        staging_entities: List[Entity],
        all_entities: List[Entity]
    ) -> List[DuplicateCandidate]:
        """
        Compare each STAGING entity against all entities to find duplicates.
        More efficient than all-vs-all comparison.
        """
        candidates = []
        seen_pairs: Set[Tuple[str, str]] = set()
        
        for staging_entity in staging_entities:
            for other_entity in all_entities:
                if staging_entity.id == other_entity.id:
                    continue
                if staging_entity.entity_type != other_entity.entity_type:
                    continue
                    
                pair_key = tuple(sorted([str(staging_entity.id), str(other_entity.id)]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                
                score, signals = self._calculate_similarity(staging_entity, other_entity)
                
                if score >= self.config.review_threshold:
                    decision = self._determine_merge_decision(
                        staging_entity, other_entity, score
                    )
                    
                    candidate = DuplicateCandidate(
                        entity_a_id=str(staging_entity.id),
                        entity_b_id=str(other_entity.id),
                        entity_a_name=staging_entity.name,
                        entity_b_name=other_entity.name,
                        entity_type=staging_entity.entity_type,
                        similarity_score=score,
                        signals=signals,
                        merge_decision=decision,
                        reason=self._get_decision_reason(decision, staging_entity, score),
                    )
                    candidates.append(candidate)
        
        return candidates
    
    def _find_duplicates_in_type(
        self, 
        entities: List[Entity]
    ) -> List[DuplicateCandidate]:
        """Find duplicate candidates within a single entity type (all-vs-all)."""
        candidates = []
        seen_pairs: Set[Tuple[str, str]] = set()
        
        for i, entity_a in enumerate(entities):
            for entity_b in entities[i+1:]:
                pair_key = tuple(sorted([str(entity_a.id), str(entity_b.id)]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                
                score, signals = self._calculate_similarity(entity_a, entity_b)
                
                if score >= self.config.review_threshold:
                    decision = self._determine_merge_decision(
                        entity_a, entity_b, score
                    )
                    
                    candidate = DuplicateCandidate(
                        entity_a_id=str(entity_a.id),
                        entity_b_id=str(entity_b.id),
                        entity_a_name=entity_a.name,
                        entity_b_name=entity_b.name,
                        entity_type=entity_a.entity_type,
                        similarity_score=score,
                        signals=signals,
                        merge_decision=decision,
                        reason=self._get_decision_reason(decision, entity_a, score),
                    )
                    candidates.append(candidate)
        
        return candidates
    
    def _calculate_similarity(
        self, 
        entity_a: Entity, 
        entity_b: Entity
    ) -> Tuple[float, List[str]]:
        """
        Calculate similarity score between two entities using weighted signals.
        
        Signals and weights:
        - exact_name_match: 0.95
        - external_id_match: 0.95
        - email_match: 0.90
        - alias_overlap: 0.40
        - name_similarity: 0.30 (Jaro-Winkler > 0.85)
        - relationship_overlap: 0.25
        - co_occurrence: 0.15
        
        Returns:
            Tuple of (score, list of signals that matched)
        """
        signals = []
        weighted_score = 0.0
        
        name_a = entity_a.name.lower().strip()
        name_b = entity_b.name.lower().strip()
        
        if name_a == name_b:
            signals.append("exact_name_match")
            weighted_score += self.config.exact_name_weight
        else:
            jw_score = jaro_winkler_similarity(name_a, name_b)
            if jw_score >= self.config.name_similarity_threshold:
                signals.append(f"name_similarity:{jw_score:.2f}")
                weighted_score += self.config.name_similarity_weight
        
        ext_id_a = self._get_external_id(entity_a)
        ext_id_b = self._get_external_id(entity_b)
        if ext_id_a and ext_id_b and ext_id_a == ext_id_b:
            signals.append("external_id_match")
            weighted_score += self.config.external_id_weight
        
        if entity_a.entity_type == "PERSON" or entity_b.entity_type == "PERSON":
            email_a = self._get_email(entity_a)
            email_b = self._get_email(entity_b)
            if email_a and email_b and email_a.lower() == email_b.lower():
                signals.append("email_match")
                weighted_score += self.config.email_weight
        
        aliases_a = self._get_aliases(entity_a)
        aliases_b = self._get_aliases(entity_b)
        
        alias_overlap = aliases_a.intersection(aliases_b)
        if alias_overlap:
            signals.append(f"alias_overlap:{len(alias_overlap)}")
            weighted_score += self.config.alias_overlap_weight
        
        if name_a in aliases_b or name_b in aliases_a:
            signals.append("name_in_aliases")
            weighted_score += self.config.alias_overlap_weight * 0.5
        
        rel_overlap = self._calculate_relationship_overlap(entity_a, entity_b)
        if rel_overlap >= self.config.min_relationship_overlap_count:
            signals.append(f"relationship_overlap:{rel_overlap}")
            overlap_score = min(1.0, rel_overlap / 5.0)
            weighted_score += self.config.relationship_overlap_weight * overlap_score
        
        co_occur = self._check_co_occurrence(entity_a, entity_b)
        if co_occur:
            signals.append(f"co_occurrence:{co_occur}")
            weighted_score += self.config.co_occurrence_weight
        
        return min(1.0, weighted_score), signals
    
    def _get_external_id(self, entity: Entity) -> Optional[str]:
        """Get external_id from entity properties."""
        if entity.properties:
            return entity.properties.get("external_id")
        return None
    
    def _get_email(self, entity: Entity) -> Optional[str]:
        """Get email from entity properties."""
        if entity.properties:
            return entity.properties.get("email")
        return None
    
    def _check_co_occurrence(self, entity_a: Entity, entity_b: Entity) -> int:
        """Check if entities appear in the same source documents."""
        docs_a = set()
        docs_b = set()
        
        if entity_a.source_document_id:
            docs_a.add(str(entity_a.source_document_id))
        if entity_b.source_document_id:
            docs_b.add(str(entity_b.source_document_id))
        
        return len(docs_a.intersection(docs_b))
    
    def _get_aliases(self, entity: Entity) -> Set[str]:
        """Get aliases from entity properties."""
        aliases = set()
        
        if entity.properties:
            prop_aliases = entity.properties.get("aliases", [])
            if isinstance(prop_aliases, list):
                aliases.update(a.lower().strip() for a in prop_aliases)
            
            alt_names = entity.properties.get("alternative_names", [])
            if isinstance(alt_names, list):
                aliases.update(n.lower().strip() for n in alt_names)
        
        return aliases
    
    def _calculate_relationship_overlap(
        self, 
        entity_a: Entity, 
        entity_b: Entity
    ) -> int:
        """Count overlapping relationships between two entities."""
        a_rel_targets = set()
        b_rel_targets = set()
        
        for rel in entity_a.outgoing_relationships:
            a_rel_targets.add((rel.relationship_type, str(rel.target_id)))
        for rel in entity_a.incoming_relationships:
            a_rel_targets.add((rel.relationship_type, str(rel.source_id)))
        
        for rel in entity_b.outgoing_relationships:
            b_rel_targets.add((rel.relationship_type, str(rel.target_id)))
        for rel in entity_b.incoming_relationships:
            b_rel_targets.add((rel.relationship_type, str(rel.source_id)))
        
        return len(a_rel_targets.intersection(b_rel_targets))
    
    def _determine_merge_decision(
        self,
        entity_a: Entity,
        entity_b: Entity,
        score: float,
    ) -> MergeDecision:
        """Determine merge decision based on score and entity type."""
        entity_type = entity_a.entity_type
        
        if entity_type in self.config.never_auto_merge_types:
            if score >= self.config.review_threshold:
                return MergeDecision.FLAG_FOR_REVIEW
            return MergeDecision.BLOCKED
        
        if score >= self.config.auto_merge_threshold:
            return MergeDecision.AUTO_MERGE
        elif score >= self.config.review_threshold:
            return MergeDecision.FLAG_FOR_REVIEW
        else:
            return MergeDecision.NO_MERGE
    
    def _get_decision_reason(
        self,
        decision: MergeDecision,
        entity: Entity,
        score: float,
    ) -> str:
        """Get human-readable reason for merge decision."""
        if decision == MergeDecision.AUTO_MERGE:
            return f"Score {score:.2f} >= {self.config.auto_merge_threshold} auto-merge threshold"
        elif decision == MergeDecision.FLAG_FOR_REVIEW:
            if entity.entity_type in self.config.never_auto_merge_types:
                return f"Person entities never auto-merged (score: {score:.2f})"
            return f"Score {score:.2f} in review range [{self.config.review_threshold}, {self.config.auto_merge_threshold})"
        elif decision == MergeDecision.BLOCKED:
            return f"Entity type {entity.entity_type} blocked from auto-merge"
        else:
            return f"Score {score:.2f} below review threshold {self.config.review_threshold}"
    
    def _persist_duplicate_candidate(self, candidate: DuplicateCandidate) -> None:
        """Persist a flagged duplicate candidate to the database for review."""
        existing = self.session.query(DuplicateCandidateDB).filter(
            DuplicateCandidateDB.entity_a_id == uuid.UUID(candidate.entity_a_id),
            DuplicateCandidateDB.entity_b_id == uuid.UUID(candidate.entity_b_id),
            DuplicateCandidateDB.reviewed == False,
        ).first()
        
        if existing:
            return
        
        db_candidate = DuplicateCandidateDB(
            id=uuid.uuid4(),
            entity_a_id=uuid.UUID(candidate.entity_a_id),
            entity_b_id=uuid.UUID(candidate.entity_b_id),
            entity_a_name=candidate.entity_a_name,
            entity_b_name=candidate.entity_b_name,
            entity_type=candidate.entity_type,
            similarity_score=candidate.similarity_score,
            signals=candidate.signals,
            merge_decision=candidate.merge_decision.value,
            reason=candidate.reason,
        )
        self.session.add(db_candidate)
    
    def _perform_merge(
        self,
        candidate: DuplicateCandidate,
    ) -> Optional[MergeAuditRecord]:
        """
        Perform the actual merge of two entities.
        
        The surviving entity is the one with:
        1. TRUSTED lifecycle (if one is TRUSTED, one is STAGING)
        2. Higher confidence
        3. Earlier creation date
        
        The merged entity's relationships are transferred to survivor.
        """
        entity_a = self.session.query(Entity).filter(
            Entity.id == candidate.entity_a_id
        ).first()
        entity_b = self.session.query(Entity).filter(
            Entity.id == candidate.entity_b_id
        ).first()
        
        if not entity_a or not entity_b:
            return None
        
        survivor, merged = self._choose_survivor(entity_a, entity_b)
        
        relationships_transferred = self._transfer_relationships(merged, survivor)
        
        merged_props = self._merge_properties(survivor.properties, merged.properties)
        survivor.properties = merged_props
        
        if merged.confidence > survivor.confidence:
            survivor.confidence = merged.confidence
        
        merged.lifecycle_state = LifecycleState.ARCHIVED
        merged.archived_at = datetime.utcnow()
        
        if merged.properties is None:
            merged.properties = {}
        merged.properties["merged_into"] = str(survivor.id)
        merged.properties["merged_at"] = datetime.utcnow().isoformat()
        
        audit_id = str(uuid.uuid4())
        
        db_audit = MergeAuditDB(
            id=uuid.UUID(audit_id),
            merged_entity_id=merged.id,
            merged_entity_name=merged.name,
            surviving_entity_id=survivor.id,
            surviving_entity_name=survivor.name,
            entity_type=survivor.entity_type,
            merge_confidence=candidate.similarity_score,
            merge_signals=candidate.signals,
            auto_merged=True,
            relationships_transferred=relationships_transferred,
            properties_merged=merged_props,
        )
        self.session.add(db_audit)
        
        audit = MergeAuditRecord(
            id=audit_id,
            merged_entity_id=str(merged.id),
            merged_entity_name=merged.name,
            surviving_entity_id=str(survivor.id),
            surviving_entity_name=survivor.name,
            entity_type=survivor.entity_type,
            merge_confidence=candidate.similarity_score,
            merge_signals=candidate.signals,
            auto_merged=True,
            relationships_transferred=relationships_transferred,
            properties_merged=merged_props,
        )
        
        self.merge_audit.append(audit)
        return audit
    
    def _choose_survivor(
        self,
        entity_a: Entity,
        entity_b: Entity,
    ) -> Tuple[Entity, Entity]:
        """Choose which entity survives the merge."""
        if entity_a.lifecycle_state == LifecycleState.TRUSTED and entity_b.lifecycle_state != LifecycleState.TRUSTED:
            return entity_a, entity_b
        if entity_b.lifecycle_state == LifecycleState.TRUSTED and entity_a.lifecycle_state != LifecycleState.TRUSTED:
            return entity_b, entity_a
        
        if entity_a.confidence > entity_b.confidence:
            return entity_a, entity_b
        if entity_b.confidence > entity_a.confidence:
            return entity_b, entity_a
        
        if entity_a.created_at <= entity_b.created_at:
            return entity_a, entity_b
        return entity_b, entity_a
    
    def _transfer_relationships(
        self,
        from_entity: Entity,
        to_entity: Entity,
    ) -> int:
        """Transfer relationships from merged entity to survivor."""
        transferred = 0
        
        for rel in from_entity.outgoing_relationships:
            existing = self.session.query(Relationship).filter(
                and_(
                    Relationship.source_id == to_entity.id,
                    Relationship.target_id == rel.target_id,
                    Relationship.relationship_type == rel.relationship_type,
                )
            ).first()
            
            if not existing:
                rel.source_id = to_entity.id
                transferred += 1
            else:
                if rel.confidence > existing.confidence:
                    existing.confidence = rel.confidence
                rel.lifecycle_state = LifecycleState.ARCHIVED
        
        for rel in from_entity.incoming_relationships:
            existing = self.session.query(Relationship).filter(
                and_(
                    Relationship.source_id == rel.source_id,
                    Relationship.target_id == to_entity.id,
                    Relationship.relationship_type == rel.relationship_type,
                )
            ).first()
            
            if not existing:
                rel.target_id = to_entity.id
                transferred += 1
            else:
                if rel.confidence > existing.confidence:
                    existing.confidence = rel.confidence
                rel.lifecycle_state = LifecycleState.ARCHIVED
        
        return transferred
    
    def _merge_properties(
        self,
        survivor_props: Optional[Dict],
        merged_props: Optional[Dict],
    ) -> Dict:
        """Merge properties from both entities."""
        result = dict(survivor_props or {})
        merged = merged_props or {}
        
        for key, value in merged.items():
            if key not in result:
                result[key] = value
            elif isinstance(result[key], list) and isinstance(value, list):
                combined = list(set(result[key] + value))
                result[key] = combined
        
        return result
    
    def get_pending_reviews(self) -> List[DuplicateCandidate]:
        """Get all candidates flagged for review."""
        return [
            c for c in self.candidates 
            if c.merge_decision == MergeDecision.FLAG_FOR_REVIEW and not c.reviewed
        ]
    
    def approve_merge(
        self,
        entity_a_id: str,
        entity_b_id: str,
        reviewed_by: str = "human",
    ) -> Optional[MergeAuditRecord]:
        """Approve a flagged merge after human review."""
        for candidate in self.candidates:
            if (candidate.entity_a_id == entity_a_id and 
                candidate.entity_b_id == entity_b_id):
                
                candidate.reviewed = True
                candidate.reviewed_at = datetime.utcnow()
                candidate.reviewed_by = reviewed_by
                
                result = self._perform_merge(candidate)
                if result:
                    result.auto_merged = False
                    result.merged_by = reviewed_by
                    self.session.commit()
                
                return result
        
        return None
    
    def reject_merge(
        self,
        entity_a_id: str,
        entity_b_id: str,
        reviewed_by: str = "human",
        reason: str = "",
    ) -> bool:
        """Reject a flagged merge after human review."""
        for candidate in self.candidates:
            if (candidate.entity_a_id == entity_a_id and 
                candidate.entity_b_id == entity_b_id):
                
                candidate.reviewed = True
                candidate.reviewed_at = datetime.utcnow()
                candidate.reviewed_by = reviewed_by
                candidate.merge_decision = MergeDecision.NO_MERGE
                candidate.reason = f"Rejected: {reason}" if reason else "Rejected by human review"
                
                return True
        
        return False
    
    def get_merge_stats(self) -> Dict:
        """Get statistics about merges."""
        return {
            "total_candidates": len(self.candidates),
            "auto_merged": sum(1 for a in self.merge_audit if a.auto_merged),
            "human_merged": sum(1 for a in self.merge_audit if not a.auto_merged),
            "pending_review": len(self.get_pending_reviews()),
            "relationships_transferred": sum(a.relationships_transferred for a in self.merge_audit),
        }
