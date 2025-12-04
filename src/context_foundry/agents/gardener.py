"""
Gardener Agent for Context Foundry.

Maintains knowledge graph health through scheduled passes:
1. Decay Pass: Apply confidence decay to aging facts
2. Promotion Pass: Move STAGING → TRUSTED when criteria met
3. Conflict Detection: Flag contradictions between new and trusted facts
4. Demotion Pass: Move low-confidence facts to ARCHIVED
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..models.schema import (
    Entity, Relationship, LifecycleState, EntityType,
    ConflictLog as ConflictLogDB,
    get_session
)


class ConflictType(str, Enum):
    ATTRIBUTE_MISMATCH = "attribute_mismatch"
    RELATIONSHIP_CONTRADICTION = "relationship_contradiction"
    DUPLICATE_ENTITY = "duplicate_entity"


class ConflictResolution(str, Enum):
    HIGHER_AUTHORITY_WINS = "higher_authority_wins"
    HIGHER_CONFIDENCE_WINS = "higher_confidence_wins"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    AUTO_MERGED = "auto_merged"


@dataclass
class GardenerConfig:
    """Configuration for Gardener agent."""
    decay_half_life_days: float = 30.0
    min_confidence_for_promotion: float = 0.75
    min_dwell_time_hours: float = 24.0
    archive_confidence_threshold: float = 0.3
    conflict_margin_for_escalation: float = 0.15
    
    auto_merge_threshold: float = 0.95
    review_merge_threshold: float = 0.70
    never_auto_merge_types: List[str] = field(default_factory=lambda: ["PERSON"])


@dataclass
class ConflictRecord:
    """Record of a detected conflict."""
    id: str
    conflict_type: ConflictType
    entity_id: Optional[str]
    relationship_id: Optional[str]
    existing_value: str
    new_value: str
    existing_confidence: float
    new_confidence: float
    resolution: Optional[ConflictResolution] = None
    resolved_at: Optional[datetime] = None
    notes: str = ""
    detected_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "conflict_type": self.conflict_type.value,
            "entity_id": self.entity_id,
            "relationship_id": self.relationship_id,
            "existing_value": self.existing_value,
            "new_value": self.new_value,
            "existing_confidence": self.existing_confidence,
            "new_confidence": self.new_confidence,
            "resolution": self.resolution.value if self.resolution else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "notes": self.notes,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class MergeAuditRecord:
    """Audit trail for entity merges."""
    id: str
    merged_entity_id: str
    surviving_entity_id: str
    merge_confidence: float
    merge_signals: List[str]
    auto_merged: bool
    merged_at: datetime = field(default_factory=datetime.utcnow)
    merged_by: str = "gardener"
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "merged_entity_id": self.merged_entity_id,
            "surviving_entity_id": self.surviving_entity_id,
            "merge_confidence": self.merge_confidence,
            "merge_signals": self.merge_signals,
            "auto_merged": self.auto_merged,
            "merged_at": self.merged_at.isoformat(),
            "merged_by": self.merged_by,
        }


@dataclass
class GardenerPassResult:
    """Result of a single gardener pass."""
    pass_name: str
    entities_affected: int = 0
    relationships_affected: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    merges_performed: int = 0
    merges_flagged: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "pass_name": self.pass_name,
            "entities_affected": self.entities_affected,
            "relationships_affected": self.relationships_affected,
            "conflicts_detected": self.conflicts_detected,
            "conflicts_resolved": self.conflicts_resolved,
            "merges_performed": self.merges_performed,
            "merges_flagged": self.merges_flagged,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class GardenerCycleResult:
    """Result of a complete gardener cycle."""
    cycle_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    passes: List[GardenerPassResult] = field(default_factory=list)
    total_entities_affected: int = 0
    total_relationships_affected: int = 0
    total_conflicts: int = 0
    total_merges: int = 0
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "passes": [p.to_dict() for p in self.passes],
            "total_entities_affected": self.total_entities_affected,
            "total_relationships_affected": self.total_relationships_affected,
            "total_conflicts": self.total_conflicts,
            "total_merges": self.total_merges,
            "success": self.success,
            "error": self.error,
        }


class Gardener:
    """
    Gardener agent that maintains knowledge graph health.
    
    Runs on a 5-minute cycle with four passes:
    1. Decay: Apply time-based confidence decay
    2. Promotion: Move qualified STAGING facts to TRUSTED
    3. Conflict Detection: Identify contradictions
    4. Demotion: Archive low-confidence facts
    """
    
    def __init__(
        self,
        session: Session,
        config: Optional[GardenerConfig] = None,
    ):
        self.session = session
        self.config = config or GardenerConfig()
        self.conflict_log: List[ConflictRecord] = []
        self.merge_audit: List[MergeAuditRecord] = []
        self._cycle_count = 0
    
    def run_cycle(self) -> GardenerCycleResult:
        """
        Run a complete gardener cycle with all four passes.
        
        Returns:
            GardenerCycleResult with metrics from all passes
        """
        self._cycle_count += 1
        cycle_id = f"cycle-{self._cycle_count}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        result = GardenerCycleResult(
            cycle_id=cycle_id,
            started_at=datetime.utcnow(),
        )
        
        try:
            decay_result = self._run_decay_pass()
            result.passes.append(decay_result)
            result.total_entities_affected += decay_result.entities_affected
            result.total_relationships_affected += decay_result.relationships_affected
            
            promotion_result = self._run_promotion_pass()
            result.passes.append(promotion_result)
            result.total_entities_affected += promotion_result.entities_affected
            result.total_relationships_affected += promotion_result.relationships_affected
            
            conflict_result = self._run_conflict_detection_pass(cycle_id=cycle_id)
            result.passes.append(conflict_result)
            result.total_conflicts += conflict_result.conflicts_detected
            
            demotion_result = self._run_demotion_pass()
            result.passes.append(demotion_result)
            result.total_entities_affected += demotion_result.entities_affected
            result.total_relationships_affected += demotion_result.relationships_affected
            
            self.session.commit()
            result.success = True
            
        except Exception as e:
            self.session.rollback()
            result.success = False
            result.error = str(e)
        
        result.completed_at = datetime.utcnow()
        return result
    
    def _calculate_decay(self, age_days: float) -> float:
        """
        Calculate confidence decay factor based on age.
        
        Uses exponential decay with configurable half-life:
        decay_factor = 0.5 ^ (age_days / half_life_days)
        
        Args:
            age_days: Age of the fact in days
            
        Returns:
            Decay factor between 0 and 1
        """
        half_life = self.config.decay_half_life_days
        return math.pow(0.5, age_days / half_life)
    
    def _run_decay_pass(self) -> GardenerPassResult:
        """
        Apply confidence decay to aging facts.
        
        Only decays TRUSTED facts (STAGING facts haven't been validated yet).
        Decay is applied based on time since last update.
        """
        start_time = datetime.utcnow()
        result = GardenerPassResult(pass_name="decay")
        
        try:
            trusted_entities = self.session.query(Entity).filter(
                Entity.lifecycle_state == LifecycleState.TRUSTED
            ).all()
            
            for entity in trusted_entities:
                age = datetime.utcnow() - (entity.updated_at or entity.created_at)
                age_days = age.total_seconds() / 86400
                
                if age_days > 1:
                    decay_factor = self._calculate_decay(age_days)
                    new_confidence = entity.confidence * decay_factor
                    
                    if new_confidence < entity.confidence * 0.99:
                        entity.confidence = max(0.1, new_confidence)
                        result.entities_affected += 1
            
            trusted_relationships = self.session.query(Relationship).filter(
                Relationship.lifecycle_state == LifecycleState.TRUSTED
            ).all()
            
            for rel in trusted_relationships:
                age = datetime.utcnow() - (rel.updated_at or rel.created_at)
                age_days = age.total_seconds() / 86400
                
                if age_days > 1:
                    decay_factor = self._calculate_decay(age_days)
                    new_confidence = rel.confidence * decay_factor
                    
                    if new_confidence < rel.confidence * 0.99:
                        rel.confidence = max(0.1, new_confidence)
                        result.relationships_affected += 1
                        
        except Exception as e:
            result.errors.append(f"Decay pass error: {str(e)}")
        
        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result
    
    def _run_promotion_pass(self) -> GardenerPassResult:
        """
        Promote STAGING facts to TRUSTED when criteria are met.
        
        Criteria:
        - Confidence >= 0.75
        - Dwell time >= 24 hours (configurable)
        - No unresolved conflicts
        """
        start_time = datetime.utcnow()
        result = GardenerPassResult(pass_name="promotion")
        
        try:
            min_confidence = self.config.min_confidence_for_promotion
            min_age = datetime.utcnow() - timedelta(hours=self.config.min_dwell_time_hours)
            
            staging_entities = self.session.query(Entity).filter(
                and_(
                    Entity.lifecycle_state == LifecycleState.STAGING,
                    Entity.confidence >= min_confidence,
                    Entity.created_at <= min_age,
                )
            ).all()
            
            entity_ids_with_conflicts = {
                c.entity_id for c in self.conflict_log 
                if c.entity_id and c.resolution is None
            }
            
            for entity in staging_entities:
                if str(entity.id) not in entity_ids_with_conflicts:
                    entity.lifecycle_state = LifecycleState.TRUSTED
                    entity.promoted_at = datetime.utcnow()
                    result.entities_affected += 1
            
            staging_relationships = self.session.query(Relationship).filter(
                and_(
                    Relationship.lifecycle_state == LifecycleState.STAGING,
                    Relationship.confidence >= min_confidence,
                    Relationship.created_at <= min_age,
                )
            ).all()
            
            rel_ids_with_conflicts = {
                c.relationship_id for c in self.conflict_log 
                if c.relationship_id and c.resolution is None
            }
            
            for rel in staging_relationships:
                source_trusted = self.session.query(Entity).filter(
                    and_(
                        Entity.id == rel.source_id,
                        Entity.lifecycle_state == LifecycleState.TRUSTED,
                    )
                ).first()
                
                target_trusted = self.session.query(Entity).filter(
                    and_(
                        Entity.id == rel.target_id,
                        Entity.lifecycle_state == LifecycleState.TRUSTED,
                    )
                ).first()
                
                if source_trusted and target_trusted:
                    if str(rel.id) not in rel_ids_with_conflicts:
                        rel.lifecycle_state = LifecycleState.TRUSTED
                        result.relationships_affected += 1
                        
        except Exception as e:
            result.errors.append(f"Promotion pass error: {str(e)}")
        
        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result
    
    def _run_conflict_detection_pass(self, cycle_id: str = "") -> GardenerPassResult:
        """
        Detect conflicts between STAGING and TRUSTED facts.
        
        Conflict types:
        - Attribute mismatch: Same entity, different properties
        - Relationship contradiction: Conflicting relationship claims
        - Duplicate entity: Possible duplicate entities
        """
        start_time = datetime.utcnow()
        result = GardenerPassResult(pass_name="conflict_detection")
        
        try:
            staging_entities = self.session.query(Entity).filter(
                Entity.lifecycle_state == LifecycleState.STAGING
            ).all()
            
            for staging in staging_entities:
                trusted_match = self.session.query(Entity).filter(
                    and_(
                        Entity.lifecycle_state == LifecycleState.TRUSTED,
                        Entity.name == staging.name,
                        Entity.entity_type == staging.entity_type,
                    )
                ).first()
                
                if trusted_match:
                    if staging.properties != trusted_match.properties:
                        conflict = self._create_attribute_conflict(
                            staging, trusted_match, cycle_id
                        )
                        if conflict:
                            self.conflict_log.append(conflict)
                            result.conflicts_detected += 1
                            
                            resolution = self._resolve_attribute_conflict(conflict)
                            if resolution:
                                result.conflicts_resolved += 1
            
            staging_relationships = self.session.query(Relationship).filter(
                Relationship.lifecycle_state == LifecycleState.STAGING
            ).all()
            
            for staging_rel in staging_relationships:
                contradicting = self._find_contradicting_relationship(staging_rel)
                if contradicting:
                    conflict = self._create_relationship_conflict(
                        staging_rel, contradicting, cycle_id
                    )
                    if conflict:
                        self.conflict_log.append(conflict)
                        result.conflicts_detected += 1
                        
                        resolution = self._resolve_relationship_conflict(conflict)
                        if resolution:
                            result.conflicts_resolved += 1
                            
        except Exception as e:
            result.errors.append(f"Conflict detection error: {str(e)}")
        
        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result
    
    def _find_contradicting_relationship(
        self, 
        staging_rel: Relationship
    ) -> Optional[Relationship]:
        """Find a TRUSTED relationship that contradicts the staging one."""
        if staging_rel.relationship_type == "OWNS":
            existing = self.session.query(Relationship).filter(
                and_(
                    Relationship.lifecycle_state == LifecycleState.TRUSTED,
                    Relationship.relationship_type == staging_rel.relationship_type,
                    Relationship.target_id == staging_rel.target_id,
                    Relationship.source_id != staging_rel.source_id,
                )
            ).first()
            return existing
        
        return None
    
    def _create_attribute_conflict(
        self,
        staging: Entity,
        trusted: Entity,
        cycle_id: str = "",
    ) -> Optional[ConflictRecord]:
        """Create a conflict record for attribute mismatch and persist to DB."""
        import uuid as uuid_module
        conflict_id = str(uuid_module.uuid4())
        
        db_conflict = ConflictLogDB(
            id=uuid_module.UUID(conflict_id),
            conflict_type=ConflictType.ATTRIBUTE_MISMATCH.value,
            entity_id=staging.id,
            relationship_id=None,
            existing_value=str(trusted.properties),
            new_value=str(staging.properties),
            existing_confidence=trusted.confidence,
            new_confidence=staging.confidence,
            cycle_id=cycle_id,
        )
        self.session.add(db_conflict)
        
        return ConflictRecord(
            id=conflict_id,
            conflict_type=ConflictType.ATTRIBUTE_MISMATCH,
            entity_id=str(staging.id),
            relationship_id=None,
            existing_value=str(trusted.properties),
            new_value=str(staging.properties),
            existing_confidence=trusted.confidence,
            new_confidence=staging.confidence,
        )
    
    def _create_relationship_conflict(
        self,
        staging: Relationship,
        trusted: Relationship,
        cycle_id: str = "",
    ) -> Optional[ConflictRecord]:
        """Create a conflict record for relationship contradiction and persist to DB."""
        import uuid as uuid_module
        conflict_id = str(uuid_module.uuid4())
        
        db_conflict = ConflictLogDB(
            id=uuid_module.UUID(conflict_id),
            conflict_type=ConflictType.RELATIONSHIP_CONTRADICTION.value,
            entity_id=None,
            relationship_id=staging.id,
            existing_value=f"{trusted.source_entity.name} -> {trusted.target_entity.name}",
            new_value=f"{staging.source_entity.name} -> {staging.target_entity.name}",
            existing_confidence=trusted.confidence,
            new_confidence=staging.confidence,
            cycle_id=cycle_id,
        )
        self.session.add(db_conflict)
        
        return ConflictRecord(
            id=conflict_id,
            conflict_type=ConflictType.RELATIONSHIP_CONTRADICTION,
            entity_id=None,
            relationship_id=str(staging.id),
            existing_value=f"{trusted.source_entity.name} -> {trusted.target_entity.name}",
            new_value=f"{staging.source_entity.name} -> {staging.target_entity.name}",
            existing_confidence=trusted.confidence,
            new_confidence=staging.confidence,
        )
    
    def _resolve_attribute_conflict(
        self,
        conflict: ConflictRecord
    ) -> bool:
        """
        Resolve an attribute mismatch conflict.
        
        Strategy: higher_authority_wins (source document authority)
        If margin < 0.15, escalate to human review.
        """
        margin = abs(conflict.existing_confidence - conflict.new_confidence)
        
        if margin < self.config.conflict_margin_for_escalation:
            conflict.resolution = ConflictResolution.ESCALATE_TO_HUMAN
            conflict.notes = f"Confidence margin {margin:.2f} < {self.config.conflict_margin_for_escalation}"
            return False
        
        if conflict.new_confidence > conflict.existing_confidence:
            conflict.resolution = ConflictResolution.HIGHER_AUTHORITY_WINS
            conflict.resolved_at = datetime.utcnow()
            conflict.notes = "New extraction has higher confidence, will replace on promotion"
            return True
        else:
            conflict.resolution = ConflictResolution.HIGHER_AUTHORITY_WINS
            conflict.resolved_at = datetime.utcnow()
            conflict.notes = "Existing trusted fact has higher confidence, staging discarded"
            
            if conflict.entity_id:
                staging = self.session.query(Entity).filter(
                    Entity.id == conflict.entity_id
                ).first()
                if staging:
                    staging.lifecycle_state = LifecycleState.ARCHIVED
                    staging.archived_at = datetime.utcnow()
            
            return True
    
    def _resolve_relationship_conflict(
        self,
        conflict: ConflictRecord
    ) -> bool:
        """
        Resolve a relationship contradiction conflict.
        
        Strategy: higher_confidence_wins
        If margin < 0.15, escalate to human review.
        """
        margin = abs(conflict.existing_confidence - conflict.new_confidence)
        
        if margin < self.config.conflict_margin_for_escalation:
            conflict.resolution = ConflictResolution.ESCALATE_TO_HUMAN
            conflict.notes = f"Confidence margin {margin:.2f} < {self.config.conflict_margin_for_escalation}"
            return False
        
        if conflict.new_confidence > conflict.existing_confidence:
            conflict.resolution = ConflictResolution.HIGHER_CONFIDENCE_WINS
            conflict.resolved_at = datetime.utcnow()
            conflict.notes = "New relationship has higher confidence"
            return True
        else:
            conflict.resolution = ConflictResolution.HIGHER_CONFIDENCE_WINS
            conflict.resolved_at = datetime.utcnow()
            conflict.notes = "Existing relationship has higher confidence, staging discarded"
            
            if conflict.relationship_id:
                staging = self.session.query(Relationship).filter(
                    Relationship.id == conflict.relationship_id
                ).first()
                if staging:
                    staging.lifecycle_state = LifecycleState.ARCHIVED
            
            return True
    
    def _run_demotion_pass(self) -> GardenerPassResult:
        """
        Demote low-confidence TRUSTED facts to ARCHIVED.
        
        Criteria:
        - Confidence below archive threshold (default 0.3)
        """
        start_time = datetime.utcnow()
        result = GardenerPassResult(pass_name="demotion")
        
        try:
            threshold = self.config.archive_confidence_threshold
            
            low_confidence_entities = self.session.query(Entity).filter(
                and_(
                    Entity.lifecycle_state == LifecycleState.TRUSTED,
                    Entity.confidence < threshold,
                )
            ).all()
            
            for entity in low_confidence_entities:
                entity.lifecycle_state = LifecycleState.ARCHIVED
                entity.archived_at = datetime.utcnow()
                result.entities_affected += 1
            
            low_confidence_relationships = self.session.query(Relationship).filter(
                and_(
                    Relationship.lifecycle_state == LifecycleState.TRUSTED,
                    Relationship.confidence < threshold,
                )
            ).all()
            
            for rel in low_confidence_relationships:
                rel.lifecycle_state = LifecycleState.ARCHIVED
                result.relationships_affected += 1
                
        except Exception as e:
            result.errors.append(f"Demotion pass error: {str(e)}")
        
        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result
    
    def get_unresolved_conflicts(self) -> List[ConflictRecord]:
        """Get all unresolved conflicts requiring human review."""
        return [
            c for c in self.conflict_log 
            if c.resolution == ConflictResolution.ESCALATE_TO_HUMAN
        ]
    
    def get_conflict_stats(self) -> Dict:
        """Get statistics about conflicts."""
        total = len(self.conflict_log)
        resolved = sum(1 for c in self.conflict_log if c.resolved_at)
        escalated = sum(
            1 for c in self.conflict_log 
            if c.resolution == ConflictResolution.ESCALATE_TO_HUMAN
        )
        
        by_type = {}
        for c in self.conflict_log:
            t = c.conflict_type.value
            by_type[t] = by_type.get(t, 0) + 1
        
        return {
            "total": total,
            "resolved": resolved,
            "escalated": escalated,
            "pending": total - resolved,
            "by_type": by_type,
        }
    
    def get_lifecycle_stats(self) -> Dict:
        """Get current lifecycle state statistics."""
        entity_counts = {}
        for state in LifecycleState:
            count = self.session.query(Entity).filter(
                Entity.lifecycle_state == state
            ).count()
            entity_counts[state.value] = count
        
        rel_counts = {}
        for state in LifecycleState:
            count = self.session.query(Relationship).filter(
                Relationship.lifecycle_state == state
            ).count()
            rel_counts[state.value] = count
        
        return {
            "entities": entity_counts,
            "relationships": rel_counts,
        }
