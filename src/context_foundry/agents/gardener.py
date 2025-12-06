"""
Gardener Agent for Context Foundry.

Maintains knowledge graph health through scheduled passes:
1. Decay Pass: Apply type-specific confidence decay to aging facts
2. Promotion Pass: Move STAGING → TRUSTED when all criteria met
3. Conflict Resolution Pass: Resolve conflicts using type-specific strategies
4. Demotion Pass: Archive low-confidence or superseded facts
5. Cleanup Pass: Delete old STAGING facts and resolved conflicts
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
import uuid as uuid_module

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from sqlalchemy.orm.attributes import flag_modified

from ..models.schema import (
    Entity, Relationship, LifecycleState, ValidationStatus,
    ConflictLog as ConflictLogDB,
    GardenerLog, GardenerActionType,
    DuplicateCandidate,
    get_session
)

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    ATTRIBUTE_MISMATCH = "attribute_mismatch"
    RELATIONSHIP_CONTRADICTION = "relationship_contradiction"
    TEMPORAL_OVERLAP = "temporal_overlap"
    CARDINALITY_VIOLATION = "cardinality_violation"
    DUPLICATE_ENTITY = "duplicate_entity"


class ConflictResolution(str, Enum):
    HIGHER_CONFIDENCE_WINS = "higher_confidence_wins"
    NEWER_WINS = "newer_wins"
    RULE_DETERMINED = "rule_determined"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    AUTO_MERGED = "auto_merged"


@dataclass
class DecayConfig:
    """Configuration for a specific decay rate."""
    rate_per_week: float
    floor: float
    grace_days: int


@dataclass
class PromotionThreshold:
    """Database-backed promotion threshold for entity type."""
    entity_type_name: str
    min_confidence: float
    min_corroboration_count: int
    min_staging_hours: int
    entity_type_id: Optional[str] = None


@dataclass
class GardenerConfig:
    """Configuration for Gardener agent with type-specific decay rates."""
    
    decay_rates: Dict[str, DecayConfig] = field(default_factory=lambda: {
        "OWNS": DecayConfig(rate_per_week=0.02, floor=0.5, grace_days=14),
        "DEPENDS_ON": DecayConfig(rate_per_week=0.01, floor=0.6, grace_days=30),
        "SUPPORTS": DecayConfig(rate_per_week=0.015, floor=0.5, grace_days=21),
        "MEMBER_OF": DecayConfig(rate_per_week=0.01, floor=0.6, grace_days=30),
        "AFFECTS": DecayConfig(rate_per_week=0.02, floor=0.4, grace_days=7),
        "CAUSED_BY": DecayConfig(rate_per_week=0.02, floor=0.4, grace_days=7),
        "_DEFAULT": DecayConfig(rate_per_week=0.015, floor=0.4, grace_days=7),
    })
    
    entity_decay: DecayConfig = field(
        default_factory=lambda: DecayConfig(rate_per_week=0.015, floor=0.4, grace_days=7)
    )
    
    min_confidence_for_promotion: float = 0.75
    min_dwell_time_hours: float = 1.0
    archive_confidence_threshold: float = 0.4
    conflict_margin_for_escalation: float = 0.15
    staleness_threshold: float = 0.5
    
    staging_max_age_days: int = 30
    resolved_conflict_max_age_days: int = 90
    
    auto_merge_threshold: float = 0.95
    review_merge_threshold: float = 0.70
    never_auto_merge_types: List[str] = field(default_factory=lambda: ["PERSON"])
    
    use_database_thresholds: bool = True


@dataclass 
class DecayResult:
    """Result of the decay pass."""
    entities_decayed: int = 0
    relationships_decayed: int = 0
    entities_flagged_stale: int = 0
    relationships_flagged_stale: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "entities_decayed": self.entities_decayed,
            "relationships_decayed": self.relationships_decayed,
            "entities_flagged_stale": self.entities_flagged_stale,
            "relationships_flagged_stale": self.relationships_flagged_stale,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class PromotionResult:
    """Result of the promotion pass."""
    entities_promoted: int = 0
    relationships_promoted: int = 0
    entities_blocked: int = 0
    relationships_blocked: int = 0
    block_reasons: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "entities_promoted": self.entities_promoted,
            "relationships_promoted": self.relationships_promoted,
            "entities_blocked": self.entities_blocked,
            "relationships_blocked": self.relationships_blocked,
            "block_reasons": self.block_reasons,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class ConflictResult:
    """Result of the conflict resolution pass."""
    conflicts_processed: int = 0
    conflicts_resolved: int = 0
    conflicts_escalated: int = 0
    by_resolution: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "conflicts_processed": self.conflicts_processed,
            "conflicts_resolved": self.conflicts_resolved,
            "conflicts_escalated": self.conflicts_escalated,
            "by_resolution": self.by_resolution,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class DemotionResult:
    """Result of the demotion pass."""
    entities_demoted: int = 0
    relationships_demoted: int = 0
    superseded_count: int = 0
    low_confidence_count: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "entities_demoted": self.entities_demoted,
            "relationships_demoted": self.relationships_demoted,
            "superseded_count": self.superseded_count,
            "low_confidence_count": self.low_confidence_count,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class CleanupResult:
    """Result of the cleanup pass."""
    staging_deleted: int = 0
    conflicts_deleted: int = 0
    relationships_deleted: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "staging_deleted": self.staging_deleted,
            "conflicts_deleted": self.conflicts_deleted,
            "relationships_deleted": self.relationships_deleted,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class GardenerCycleResult:
    """Result of a complete gardener cycle."""
    cycle_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    decay_result: Optional[DecayResult] = None
    promotion_result: Optional[PromotionResult] = None
    conflict_result: Optional[ConflictResult] = None
    demotion_result: Optional[DemotionResult] = None
    cleanup_result: Optional[CleanupResult] = None
    
    facts_decayed: int = 0
    facts_promoted: int = 0
    facts_demoted: int = 0
    conflicts_resolved: int = 0
    
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "decay": self.decay_result.to_dict() if self.decay_result else None,
            "promotion": self.promotion_result.to_dict() if self.promotion_result else None,
            "conflict_resolution": self.conflict_result.to_dict() if self.conflict_result else None,
            "demotion": self.demotion_result.to_dict() if self.demotion_result else None,
            "cleanup": self.cleanup_result.to_dict() if self.cleanup_result else None,
            "summary": {
                "facts_decayed": self.facts_decayed,
                "facts_promoted": self.facts_promoted,
                "facts_demoted": self.facts_demoted,
                "conflicts_resolved": self.conflicts_resolved,
            },
            "success": self.success,
            "error": self.error,
        }


class GardenerAgent:
    """
    Gardener agent that maintains knowledge graph health.
    
    Runs 5 passes in order:
    1. Decay: Apply type-specific confidence decay
    2. Promotion: Move qualified STAGING facts to TRUSTED (uses database thresholds)
    3. Conflict Resolution: Resolve conflicts with type-specific strategies
    4. Demotion: Archive low-confidence or superseded facts
    5. Cleanup: Delete old STAGING data and resolved conflicts
    
    Promotion thresholds are loaded from the promotion_thresholds table:
    - Person: 0.85 confidence, 2 corroborations, 4 hours
    - Incident: 0.80 confidence, 3 corroborations, 2 hours  
    - Service: 0.75 confidence, 1 corroboration, 1 hour
    - Default: 0.70 confidence, 1 corroboration, 1 hour
    """
    
    def __init__(
        self,
        session: Session,
        config: Optional[GardenerConfig] = None,
    ):
        self.session = session
        self.config = config or GardenerConfig()
        self._cycle_count = 0
        self._promoted_entity_ids: Set[str] = set()
        self._promotion_thresholds: Dict[str, PromotionThreshold] = {}
        self._default_threshold: Optional[PromotionThreshold] = None
        
        if self.config.use_database_thresholds:
            self._load_promotion_thresholds()
    
    def _load_promotion_thresholds(self) -> None:
        """Load type-specific promotion thresholds from database."""
        try:
            from sqlalchemy import text
            result = self.session.execute(text("""
                SELECT entity_type_id, entity_type_name, 
                       min_confidence, min_corroboration_count, min_staging_hours,
                       is_default
                FROM promotion_thresholds
            """))
            
            for row in result.fetchall():
                threshold = PromotionThreshold(
                    entity_type_name=row[1],
                    min_confidence=float(row[2]),
                    min_corroboration_count=int(row[3]),
                    min_staging_hours=int(row[4]),
                    entity_type_id=str(row[0]) if row[0] else None
                )
                
                if row[5]:
                    self._default_threshold = threshold
                else:
                    self._promotion_thresholds[row[1]] = threshold
            
            logger.info(
                f"[Gardener] Loaded {len(self._promotion_thresholds)} type-specific thresholds "
                f"(default: conf={self._default_threshold.min_confidence if self._default_threshold else 'N/A'})"
            )
        except Exception as e:
            logger.warning(f"[Gardener] Failed to load DB thresholds, using defaults: {e}")
            self._default_threshold = PromotionThreshold(
                entity_type_name="_default",
                min_confidence=self.config.min_confidence_for_promotion,
                min_corroboration_count=1,
                min_staging_hours=int(self.config.min_dwell_time_hours)
            )
    
    def get_threshold(self, entity_type: str) -> PromotionThreshold:
        """Get promotion threshold for entity type (falls back to default)."""
        return self._promotion_thresholds.get(
            entity_type, 
            self._default_threshold or PromotionThreshold(
                entity_type_name="_default",
                min_confidence=self.config.min_confidence_for_promotion,
                min_corroboration_count=1,
                min_staging_hours=int(self.config.min_dwell_time_hours)
            )
        )
    
    def run_cycle(self) -> GardenerCycleResult:
        """
        Run a complete gardener cycle with all five passes.
        
        Returns:
            GardenerCycleResult with metrics from all passes
        """
        self._cycle_count += 1
        cycle_id = f"cycle-{self._cycle_count}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        result = GardenerCycleResult(
            cycle_id=cycle_id,
            started_at=datetime.utcnow(),
        )
        
        self._promoted_entity_ids.clear()
        
        try:
            logger.info(f"[Gardener] Starting cycle {cycle_id}")
            
            result.decay_result = self.decay_pass(cycle_id)
            result.facts_decayed = (
                result.decay_result.entities_decayed + 
                result.decay_result.relationships_decayed
            )
            
            result.promotion_result = self.promotion_pass(cycle_id)
            result.facts_promoted = (
                result.promotion_result.entities_promoted + 
                result.promotion_result.relationships_promoted
            )
            
            result.conflict_result = self.conflict_resolution_pass(cycle_id)
            result.conflicts_resolved = result.conflict_result.conflicts_resolved
            
            result.demotion_result = self.demotion_pass(cycle_id)
            result.facts_demoted = (
                result.demotion_result.entities_demoted + 
                result.demotion_result.relationships_demoted
            )
            
            result.cleanup_result = self.cleanup_pass(cycle_id)
            
            self.session.commit()
            result.success = True
            
            logger.info(
                f"[Gardener] Cycle {cycle_id} complete: "
                f"decayed={result.facts_decayed}, promoted={result.facts_promoted}, "
                f"demoted={result.facts_demoted}, conflicts={result.conflicts_resolved}"
            )
            
        except Exception as e:
            self.session.rollback()
            result.success = False
            result.error = str(e)
            logger.error(f"[Gardener] Cycle {cycle_id} failed: {e}")
        
        result.completed_at = datetime.utcnow()
        
        self._log_cycle_summary(cycle_id, result)
        
        return result
    
    def decay_pass(self, cycle_id: str = "") -> DecayResult:
        """
        Pass 1: Apply type-specific confidence decay to aging TRUSTED facts.
        
        Decay rules:
        - Only apply after grace period expires
        - Apply rate_per_week decay
        - Never go below floor threshold
        - Flag facts that drop below staleness_threshold
        """
        start_time = datetime.utcnow()
        result = DecayResult()
        
        try:
            trusted_relationships = self.session.query(Relationship).filter(
                Relationship.lifecycle_state == LifecycleState.TRUSTED
            ).all()
            
            for rel in trusted_relationships:
                decay_config = self.config.decay_rates.get(
                    rel.relationship_type,
                    self.config.decay_rates["_DEFAULT"]
                )
                
                age = datetime.utcnow() - (rel.updated_at or rel.created_at)
                age_days = age.total_seconds() / 86400
                
                if age_days <= decay_config.grace_days:
                    continue
                
                days_past_grace = age_days - decay_config.grace_days
                weeks_past_grace = days_past_grace / 7.0
                decay_amount = decay_config.rate_per_week * weeks_past_grace
                
                new_confidence = max(
                    decay_config.floor,
                    rel.confidence - decay_amount
                )
                
                if new_confidence < rel.confidence:
                    old_confidence = rel.confidence
                    rel.confidence = new_confidence
                    result.relationships_decayed += 1
                    
                    self._log_action(
                        cycle_id=cycle_id,
                        action_type=GardenerActionType.DECAY,
                        target_id=rel.id,
                        target_type="relationship",
                        target_name=f"{rel.relationship_type}",
                        old_confidence=old_confidence,
                        new_confidence=new_confidence,
                        reason=f"Decay after {age_days:.1f} days (rate={decay_config.rate_per_week}/week)",
                    )
                    
                    if new_confidence < self.config.staleness_threshold:
                        props = rel.properties or {}
                        props["_stale"] = True
                        props["_stale_at"] = datetime.utcnow().isoformat()
                        rel.properties = props
                        flag_modified(rel, "properties")
                        result.relationships_flagged_stale += 1
            
            trusted_entities = self.session.query(Entity).filter(
                Entity.lifecycle_state == LifecycleState.TRUSTED
            ).all()
            
            decay_config = self.config.entity_decay
            
            for entity in trusted_entities:
                age = datetime.utcnow() - (entity.updated_at or entity.created_at)
                age_days = age.total_seconds() / 86400
                
                if age_days <= decay_config.grace_days:
                    continue
                
                days_past_grace = age_days - decay_config.grace_days
                weeks_past_grace = days_past_grace / 7.0
                decay_amount = decay_config.rate_per_week * weeks_past_grace
                
                new_confidence = max(
                    decay_config.floor,
                    entity.confidence - decay_amount
                )
                
                if new_confidence < entity.confidence:
                    old_confidence = entity.confidence
                    entity.confidence = new_confidence
                    result.entities_decayed += 1
                    
                    self._log_action(
                        cycle_id=cycle_id,
                        action_type=GardenerActionType.DECAY,
                        target_id=entity.id,
                        target_type="entity",
                        target_name=entity.name,
                        old_confidence=old_confidence,
                        new_confidence=new_confidence,
                        reason=f"Decay after {age_days:.1f} days",
                    )
                    
                    if new_confidence < self.config.staleness_threshold:
                        props = entity.properties or {}
                        props["_stale"] = True
                        props["_stale_at"] = datetime.utcnow().isoformat()
                        entity.properties = props
                        flag_modified(entity, "properties")
                        result.entities_flagged_stale += 1
                        
        except Exception as e:
            result.errors.append(f"Decay pass error: {str(e)}")
            logger.error(f"[Gardener] Decay pass error: {e}")
        
        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result
    
    def promotion_pass(self, cycle_id: str = "") -> PromotionResult:
        """
        Pass 2: Promote STAGING facts to TRUSTED when ALL criteria met.
        
        Uses type-specific thresholds from promotion_thresholds table:
        - Person: confidence >= 0.85, corroborations >= 2, staging >= 4 hours
        - Incident: confidence >= 0.80, corroborations >= 3, staging >= 2 hours
        - Service: confidence >= 0.75, corroborations >= 1, staging >= 1 hour
        - Default: confidence >= 0.70, corroborations >= 1, staging >= 1 hour
        
        Also requires:
        - validation_status = VALID
        - no unresolved conflicts
        - identity resolution complete (no pending duplicates)
        """
        start_time = datetime.utcnow()
        result = PromotionResult()
        
        try:
            staging_entities = self.session.query(Entity).filter(
                Entity.lifecycle_state == LifecycleState.STAGING
            ).all()
            
            entity_ids_with_conflicts = self._get_entity_ids_with_unresolved_conflicts()
            entity_ids_with_pending_duplicates = self._get_entity_ids_with_pending_duplicates()
            
            for entity in staging_entities:
                block_reason = None
                
                threshold = self.get_threshold(entity.entity_type)
                
                min_age = datetime.utcnow() - timedelta(hours=threshold.min_staging_hours)
                
                corroboration_count = 1
                if hasattr(entity, 'properties') and entity.properties:
                    corroboration_count = entity.properties.get('_corroboration_count', 1)
                
                if entity.validation_status != ValidationStatus.VALID:
                    block_reason = "validation_not_valid"
                elif entity.confidence < threshold.min_confidence:
                    block_reason = f"confidence_too_low_{entity.entity_type}"
                elif entity.created_at > min_age:
                    block_reason = f"dwell_time_insufficient_{entity.entity_type}"
                elif corroboration_count < threshold.min_corroboration_count:
                    block_reason = f"corroboration_insufficient_{entity.entity_type}"
                elif str(entity.id) in entity_ids_with_conflicts:
                    block_reason = "unresolved_conflict"
                elif str(entity.id) in entity_ids_with_pending_duplicates:
                    block_reason = "pending_duplicate"
                
                if block_reason:
                    result.entities_blocked += 1
                    result.block_reasons[block_reason] = result.block_reasons.get(block_reason, 0) + 1
                    continue
                
                old_state = entity.lifecycle_state.value
                entity.lifecycle_state = LifecycleState.TRUSTED
                
                props = entity.properties or {}
                props["_promoted_at"] = datetime.utcnow().isoformat()
                props["_promoted_from"] = "STAGING"
                props["_promoted_threshold"] = {
                    "type": entity.entity_type,
                    "min_confidence": threshold.min_confidence,
                    "min_corroboration": threshold.min_corroboration_count,
                    "min_hours": threshold.min_staging_hours
                }
                entity.properties = props
                flag_modified(entity, "properties")
                
                self._promoted_entity_ids.add(str(entity.id))
                result.entities_promoted += 1
                
                self._log_action(
                    cycle_id=cycle_id,
                    action_type=GardenerActionType.PROMOTE,
                    target_id=entity.id,
                    target_type="entity",
                    target_name=entity.name,
                    old_state=old_state,
                    new_state=LifecycleState.TRUSTED.value,
                    old_confidence=entity.confidence,
                    new_confidence=entity.confidence,
                    reason=f"Met {entity.entity_type} thresholds: conf>={threshold.min_confidence}, "
                           f"corrob>={threshold.min_corroboration_count}, hours>={threshold.min_staging_hours}",
                )
            
            staging_relationships = self.session.query(Relationship).filter(
                Relationship.lifecycle_state == LifecycleState.STAGING
            ).all()
            
            rel_ids_with_conflicts = self._get_relationship_ids_with_unresolved_conflicts()
            
            rel_threshold = self.get_threshold("Relationship")
            rel_min_confidence = rel_threshold.min_confidence
            rel_min_age = datetime.utcnow() - timedelta(hours=rel_threshold.min_staging_hours)
            
            for rel in staging_relationships:
                block_reason = None
                
                source_entity = self.session.query(Entity).filter(
                    Entity.id == rel.source_id
                ).first()
                target_entity = self.session.query(Entity).filter(
                    Entity.id == rel.target_id
                ).first()
                
                source_trusted = (
                    source_entity and 
                    source_entity.lifecycle_state == LifecycleState.TRUSTED
                )
                target_trusted = (
                    target_entity and 
                    target_entity.lifecycle_state == LifecycleState.TRUSTED
                )
                
                if rel.validation_status != ValidationStatus.VALID:
                    block_reason = "validation_not_valid"
                elif rel.confidence < rel_min_confidence:
                    block_reason = "confidence_too_low"
                elif rel.created_at > rel_min_age:
                    block_reason = "dwell_time_insufficient"
                elif not (source_trusted and target_trusted):
                    block_reason = "endpoints_not_trusted"
                elif str(rel.id) in rel_ids_with_conflicts:
                    block_reason = "unresolved_conflict"
                
                if block_reason:
                    result.relationships_blocked += 1
                    result.block_reasons[block_reason] = result.block_reasons.get(block_reason, 0) + 1
                    continue
                
                old_state = rel.lifecycle_state.value
                rel.lifecycle_state = LifecycleState.TRUSTED
                
                props = rel.properties or {}
                props["_promoted_at"] = datetime.utcnow().isoformat()
                rel.properties = props
                flag_modified(rel, "properties")
                
                result.relationships_promoted += 1
                
                self._log_action(
                    cycle_id=cycle_id,
                    action_type=GardenerActionType.PROMOTE,
                    target_id=rel.id,
                    target_type="relationship",
                    target_name=rel.relationship_type,
                    old_state=old_state,
                    new_state=LifecycleState.TRUSTED.value,
                    reason="Met all promotion criteria",
                )
                
        except Exception as e:
            result.errors.append(f"Promotion pass error: {str(e)}")
            logger.error(f"[Gardener] Promotion pass error: {e}")
        
        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result
    
    def conflict_resolution_pass(self, cycle_id: str = "") -> ConflictResult:
        """
        Pass 3: Resolve unresolved conflicts using type-specific strategies:
        - attribute_mismatch → higher_confidence_wins
        - relationship_contradiction → higher_confidence_wins
        - temporal_overlap → newer_wins
        - cardinality_violation → rule_determined
        
        If margin < 0.15: keep in review_queue for human decision
        """
        start_time = datetime.utcnow()
        result = ConflictResult()
        
        try:
            unresolved_conflicts = self.session.query(ConflictLogDB).filter(
                ConflictLogDB.resolved_at.is_(None)
            ).all()
            
            for conflict in unresolved_conflicts:
                result.conflicts_processed += 1
                
                resolved, resolution = self._resolve_conflict(conflict)
                
                if resolved:
                    conflict.resolved_at = datetime.utcnow()
                    conflict.resolution = resolution.value
                    result.conflicts_resolved += 1
                    result.by_resolution[resolution.value] = (
                        result.by_resolution.get(resolution.value, 0) + 1
                    )
                    
                    self._log_action(
                        cycle_id=cycle_id,
                        action_type=GardenerActionType.RESOLVE_CONFLICT,
                        target_id=conflict.id,
                        target_type="conflict",
                        target_name=conflict.conflict_type,
                        reason=f"Resolved via {resolution.value}",
                        details={"conflict_type": conflict.conflict_type},
                    )
                else:
                    result.conflicts_escalated += 1
                    conflict.resolution = ConflictResolution.ESCALATE_TO_HUMAN.value
                    conflict.resolution_notes = "Margin too small for auto-resolution"
                    
        except Exception as e:
            result.errors.append(f"Conflict resolution error: {str(e)}")
            logger.error(f"[Gardener] Conflict resolution error: {e}")
        
        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result
    
    def demotion_pass(self, cycle_id: str = "") -> DemotionResult:
        """
        Pass 4: Demote TRUSTED facts to ARCHIVED when:
        - confidence < archive_threshold (0.4)
        - superseded by newly promoted facts
        
        Uses temporal columns (valid_to, superseded_by, change_reason) to preserve history.
        """
        start_time = datetime.utcnow()
        result = DemotionResult()
        now = datetime.utcnow()
        
        try:
            threshold = self.config.archive_confidence_threshold
            
            low_confidence_entities = self.session.query(Entity).filter(
                and_(
                    Entity.lifecycle_state == LifecycleState.TRUSTED,
                    Entity.confidence < threshold,
                    Entity.valid_to.is_(None),
                )
            ).all()
            
            for entity in low_confidence_entities:
                old_state = entity.lifecycle_state.value
                entity.lifecycle_state = LifecycleState.ARCHIVED
                entity.valid_to = now
                entity.change_reason = f"Low confidence ({entity.confidence:.2f} < {threshold})"
                
                result.entities_demoted += 1
                result.low_confidence_count += 1
                
                self._log_action(
                    cycle_id=cycle_id,
                    action_type=GardenerActionType.DEMOTE,
                    target_id=entity.id,
                    target_type="entity",
                    target_name=entity.name,
                    old_state=old_state,
                    new_state=LifecycleState.ARCHIVED.value,
                    old_confidence=entity.confidence,
                    reason=f"Confidence {entity.confidence:.2f} below threshold {threshold}",
                )
            
            low_confidence_rels = self.session.query(Relationship).filter(
                and_(
                    Relationship.lifecycle_state == LifecycleState.TRUSTED,
                    Relationship.confidence < threshold,
                    Relationship.valid_to.is_(None),
                )
            ).all()
            
            for rel in low_confidence_rels:
                old_state = rel.lifecycle_state.value
                rel.lifecycle_state = LifecycleState.ARCHIVED
                rel.valid_to = now
                rel.change_reason = f"Low confidence ({rel.confidence:.2f} < {threshold})"
                
                result.relationships_demoted += 1
                result.low_confidence_count += 1
                
                self._log_action(
                    cycle_id=cycle_id,
                    action_type=GardenerActionType.DEMOTE,
                    target_id=rel.id,
                    target_type="relationship",
                    target_name=rel.relationship_type,
                    old_state=old_state,
                    new_state=LifecycleState.ARCHIVED.value,
                    old_confidence=rel.confidence,
                    reason=f"Confidence {rel.confidence:.2f} below threshold {threshold}",
                )
            
            superseded_pairs = self._find_superseded_facts()
            for old_entity, new_entity_id, source_doc in superseded_pairs.get("entities", []):
                if old_entity.lifecycle_state == LifecycleState.ARCHIVED:
                    continue
                    
                old_state = old_entity.lifecycle_state.value
                old_entity.lifecycle_state = LifecycleState.ARCHIVED
                old_entity.valid_to = now
                old_entity.superseded_by = new_entity_id
                old_entity.change_reason = f"Superseded by information from {source_doc or 'newer document'}"
                
                result.entities_demoted += 1
                result.superseded_count += 1
                
                self._log_action(
                    cycle_id=cycle_id,
                    action_type=GardenerActionType.DEMOTE,
                    target_id=old_entity.id,
                    target_type="entity",
                    target_name=old_entity.name,
                    old_state=old_state,
                    new_state=LifecycleState.ARCHIVED.value,
                    reason=f"Superseded by {new_entity_id}",
                    details={"superseded_by": str(new_entity_id), "source_doc": source_doc},
                )
                
        except Exception as e:
            result.errors.append(f"Demotion pass error: {str(e)}")
            logger.error(f"[Gardener] Demotion pass error: {e}")
        
        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result
    
    def cleanup_pass(self, cycle_id: str = "") -> CleanupResult:
        """
        Pass 5: Cleanup old data:
        - Delete STAGING facts older than 30 days (never promoted)
        - Delete resolved conflicts older than 90 days
        """
        start_time = datetime.utcnow()
        result = CleanupResult()
        
        try:
            staging_cutoff = datetime.utcnow() - timedelta(
                days=self.config.staging_max_age_days
            )
            
            old_staging_entities = self.session.query(Entity).filter(
                and_(
                    Entity.lifecycle_state == LifecycleState.STAGING,
                    Entity.created_at < staging_cutoff,
                )
            ).all()
            
            entity_ids_to_delete = [e.id for e in old_staging_entities]
            
            if entity_ids_to_delete:
                self.session.query(Relationship).filter(
                    or_(
                        Relationship.source_id.in_(entity_ids_to_delete),
                        Relationship.target_id.in_(entity_ids_to_delete),
                    )
                ).delete(synchronize_session=False)
            
            for entity in old_staging_entities:
                self._log_action(
                    cycle_id=cycle_id,
                    action_type=GardenerActionType.ARCHIVE,
                    target_id=entity.id,
                    target_type="entity",
                    target_name=entity.name,
                    reason=f"Deleted: STAGING older than {self.config.staging_max_age_days} days",
                )
                self.session.delete(entity)
                result.staging_deleted += 1
            
            old_staging_rels = self.session.query(Relationship).filter(
                and_(
                    Relationship.lifecycle_state == LifecycleState.STAGING,
                    Relationship.created_at < staging_cutoff,
                )
            ).all()
            
            for rel in old_staging_rels:
                self.session.delete(rel)
                result.relationships_deleted += 1
            
            conflict_cutoff = datetime.utcnow() - timedelta(
                days=self.config.resolved_conflict_max_age_days
            )
            
            old_resolved_conflicts = self.session.query(ConflictLogDB).filter(
                and_(
                    ConflictLogDB.resolved_at.isnot(None),
                    ConflictLogDB.resolved_at < conflict_cutoff,
                )
            ).all()
            
            for conflict in old_resolved_conflicts:
                self.session.delete(conflict)
                result.conflicts_deleted += 1
                
        except Exception as e:
            result.errors.append(f"Cleanup pass error: {str(e)}")
            logger.error(f"[Gardener] Cleanup pass error: {e}")
        
        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result
    
    def _resolve_conflict(
        self, 
        conflict: ConflictLogDB
    ) -> Tuple[bool, Optional[ConflictResolution]]:
        """
        Apply resolution strategy based on conflict type.
        Returns (resolved, resolution_type).
        """
        margin = abs(
            (conflict.existing_confidence or 0) - 
            (conflict.new_confidence or 0)
        )
        
        if margin < self.config.conflict_margin_for_escalation:
            return False, None
        
        conflict_type = conflict.conflict_type
        
        if conflict_type in ["attribute_mismatch", "ATTRIBUTE_MISMATCH"]:
            if (conflict.new_confidence or 0) > (conflict.existing_confidence or 0):
                self._apply_new_value_wins(conflict)
            return True, ConflictResolution.HIGHER_CONFIDENCE_WINS
            
        elif conflict_type in ["relationship_contradiction", "RELATIONSHIP_CONTRADICTION"]:
            if (conflict.new_confidence or 0) > (conflict.existing_confidence or 0):
                self._apply_new_value_wins(conflict)
            return True, ConflictResolution.HIGHER_CONFIDENCE_WINS
            
        elif conflict_type in ["temporal_overlap", "TEMPORAL_OVERLAP"]:
            return True, ConflictResolution.NEWER_WINS
            
        elif conflict_type in ["cardinality_violation", "CARDINALITY_VIOLATION"]:
            return True, ConflictResolution.RULE_DETERMINED
            
        else:
            if (conflict.new_confidence or 0) > (conflict.existing_confidence or 0):
                self._apply_new_value_wins(conflict)
            return True, ConflictResolution.HIGHER_CONFIDENCE_WINS
    
    def _apply_new_value_wins(self, conflict: ConflictLogDB) -> None:
        """
        Apply the new value when it wins the conflict.
        Uses temporal columns to preserve history chain.
        """
        now = datetime.utcnow()
        
        if conflict.entity_id:
            old_entity = self.session.query(Entity).filter(
                Entity.id == conflict.entity_id,
                Entity.lifecycle_state == LifecycleState.TRUSTED,
            ).first()
            if old_entity:
                old_entity.lifecycle_state = LifecycleState.ARCHIVED
                old_entity.valid_to = now
                old_entity.change_reason = f"Conflict resolution: new value wins (confidence {conflict.new_confidence:.2f} > {conflict.existing_confidence:.2f})"
        
        if conflict.relationship_id:
            old_rel = self.session.query(Relationship).filter(
                Relationship.id == conflict.relationship_id,
                Relationship.lifecycle_state == LifecycleState.TRUSTED,
            ).first()
            if old_rel:
                old_rel.lifecycle_state = LifecycleState.ARCHIVED
                old_rel.valid_to = now
                old_rel.change_reason = f"Conflict resolution: new value wins (confidence {conflict.new_confidence:.2f} > {conflict.existing_confidence:.2f})"
    
    def _get_entity_ids_with_unresolved_conflicts(self) -> Set[str]:
        """Get IDs of entities with unresolved conflicts."""
        conflicts = self.session.query(ConflictLogDB.entity_id).filter(
            and_(
                ConflictLogDB.entity_id.isnot(None),
                ConflictLogDB.resolved_at.is_(None),
            )
        ).all()
        return {str(c.entity_id) for c in conflicts if c.entity_id}
    
    def _get_relationship_ids_with_unresolved_conflicts(self) -> Set[str]:
        """Get IDs of relationships with unresolved conflicts."""
        conflicts = self.session.query(ConflictLogDB.relationship_id).filter(
            and_(
                ConflictLogDB.relationship_id.isnot(None),
                ConflictLogDB.resolved_at.is_(None),
            )
        ).all()
        return {str(c.relationship_id) for c in conflicts if c.relationship_id}
    
    def _get_entity_ids_with_pending_duplicates(self) -> Set[str]:
        """Get IDs of entities with pending duplicate candidates."""
        candidates = self.session.query(
            DuplicateCandidate.entity_a_id,
            DuplicateCandidate.entity_b_id,
        ).filter(
            DuplicateCandidate.reviewed == False
        ).all()
        
        ids = set()
        for c in candidates:
            ids.add(str(c.entity_a_id))
            ids.add(str(c.entity_b_id))
        return ids
    
    def _find_superseded_facts(self) -> Dict[str, List]:
        """
        Find facts that are superseded by newly promoted facts.
        A fact is superseded if a newer fact with the same name/type was promoted.
        
        Returns dict with:
        - entities: List of tuples (old_entity, new_entity_id, source_document_id)
        - relationships: List of tuples (old_rel, new_rel_id, source_document_id)
        """
        superseded = {"entities": [], "relationships": []}
        
        for promoted_id in self._promoted_entity_ids:
            promoted = self.session.query(Entity).filter(
                Entity.id == promoted_id
            ).first()
            
            if not promoted:
                continue
            
            older_versions = self.session.query(Entity).filter(
                and_(
                    Entity.name == promoted.name,
                    Entity.entity_type == promoted.entity_type,
                    Entity.lifecycle_state == LifecycleState.TRUSTED,
                    Entity.id != promoted.id,
                    Entity.created_at < promoted.created_at,
                    Entity.valid_to.is_(None),
                )
            ).all()
            
            for old_entity in older_versions:
                superseded["entities"].append(
                    (old_entity, promoted.id, promoted.source_document_id)
                )
        
        return superseded
    
    def _log_action(
        self,
        cycle_id: str,
        action_type: GardenerActionType,
        target_id,
        target_type: str,
        target_name: str = "",
        old_state: str = None,
        new_state: str = None,
        old_confidence: float = None,
        new_confidence: float = None,
        reason: str = "",
        details: Dict = None,
    ) -> None:
        """Log a gardener action to the gardener_logs table."""
        try:
            log_entry = GardenerLog(
                action_type=action_type,
                target_id=target_id,
                target_type=target_type,
                target_name=target_name,
                old_state=old_state,
                new_state=new_state,
                old_confidence=old_confidence,
                new_confidence=new_confidence,
                reason=reason,
                details=details,
                cycle_id=cycle_id,
            )
            self.session.add(log_entry)
        except Exception as e:
            logger.warning(f"Failed to log gardener action: {e}")
    
    def _log_cycle_summary(self, cycle_id: str, result: GardenerCycleResult) -> None:
        """Log a summary entry for the entire cycle."""
        try:
            summary_id = uuid_module.uuid4()
            log_entry = GardenerLog(
                id=summary_id,
                action_type=GardenerActionType.VALIDATE,
                target_id=summary_id,
                target_type="cycle",
                target_name=cycle_id,
                reason=f"Cycle complete: success={result.success}",
                details={
                    "facts_decayed": result.facts_decayed,
                    "facts_promoted": result.facts_promoted,
                    "facts_demoted": result.facts_demoted,
                    "conflicts_resolved": result.conflicts_resolved,
                    "duration_seconds": (
                        (result.completed_at - result.started_at).total_seconds()
                        if result.completed_at else 0
                    ),
                },
                cycle_id=cycle_id,
            )
            self.session.add(log_entry)
            self.session.commit()
        except Exception as e:
            logger.warning(f"Failed to log cycle summary: {e}")


Gardener = GardenerAgent
