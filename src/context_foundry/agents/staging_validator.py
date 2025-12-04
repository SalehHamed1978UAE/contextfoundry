"""
Staging Validator Agent - Validates STAGING entities/relationships against schema rules.

This is the validation layer of the cognitive loop. It checks:
1. Cardinality constraints (many-to-one relationships can only have one target per source)
2. Source/target type compatibility
3. Required field validation
4. Conflict detection with existing TRUSTED facts

Key principles:
1. All rules loaded from domain_schema.yaml (configurable)
2. Never auto-promotes - flags for human review if uncertain
3. Detects conflicts between STAGING and TRUSTED facts
4. Full logging of all validation decisions
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.schema import (
    Entity, Relationship, Conflict, ReviewQueue,
    LifecycleState, ConflictType, ConflictStatus,
    ReviewItemType, ReviewStatus,
    get_session
)
from ..config.domain_schema import (
    get_schema_loader, DomainSchema, Cardinality
)
from ..utils.logger import logger


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    ERROR = "ERROR"       # Blocks promotion
    WARNING = "WARNING"   # Flags for review
    INFO = "INFO"         # Logged but allowed


@dataclass
class ValidationIssue:
    """A single validation issue found."""
    severity: ValidationSeverity
    rule_name: str
    message: str
    entity_id: Optional[str] = None
    relationship_id: Optional[str] = None
    conflicting_fact_id: Optional[str] = None
    suggested_action: str = ""


@dataclass
class ValidationResult:
    """Result of validating staged data."""
    is_valid: bool
    entities_checked: int
    relationships_checked: int
    issues: List[ValidationIssue] = field(default_factory=list)
    conflicts_detected: int = 0
    review_items_created: int = 0
    errors: List[str] = field(default_factory=list)
    
    def get_errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]
    
    def get_warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


class StagingValidatorAgent:
    """
    Agent that validates STAGING entities and relationships against schema rules.
    
    Validates:
    - Cardinality constraints from config
    - Source/target type compatibility
    - Required fields
    - Conflicts with existing TRUSTED data
    
    All rules are loaded from domain_schema.yaml.
    """
    
    def __init__(self, session: Session = None, schema_config_path: str = None):
        self.session = session or get_session()
        
        self.schema_loader = get_schema_loader(
            config_path=schema_config_path,
            force_reload=schema_config_path is not None
        )
        self.schema = self.schema_loader.schema
        
        self.cardinality_constraints = self.schema_loader.get_cardinality_constraints()
        self.many_to_one_types = self.schema.get_many_to_one_relationships()
        
        logger.info(f"StagingValidatorAgent initialized for domain: {self.schema.domain}")
        logger.info(f"Many-to-one relationships: {self.many_to_one_types}")
    
    def validate_all_staging(self) -> ValidationResult:
        """
        Validate ALL entities and relationships currently in STAGING.
        
        Returns:
            ValidationResult with all issues found
        """
        logger.info("Starting validation of all STAGING data")
        
        staging_entities = self.session.query(Entity).filter(
            Entity.lifecycle_state == LifecycleState.STAGING
        ).all()
        
        staging_relationships = self.session.query(Relationship).filter(
            Relationship.lifecycle_state == LifecycleState.STAGING
        ).all()
        
        logger.info(f"Found {len(staging_entities)} entities and {len(staging_relationships)} relationships in STAGING")
        
        all_issues = []
        
        for entity in staging_entities:
            issues = self._validate_entity(entity)
            all_issues.extend(issues)
        
        for rel in staging_relationships:
            issues = self._validate_relationship(rel)
            all_issues.extend(issues)
        
        cardinality_issues = self._check_cardinality_violations(staging_relationships)
        all_issues.extend(cardinality_issues)
        
        conflicts_detected = self._detect_and_record_conflicts(staging_entities, staging_relationships)
        
        review_items = self._create_review_items(all_issues)
        
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in all_issues)
        
        self._mark_validation_status(staging_entities, staging_relationships, all_issues, conflicts_detected)
        
        result = ValidationResult(
            is_valid=not has_errors,
            entities_checked=len(staging_entities),
            relationships_checked=len(staging_relationships),
            issues=all_issues,
            conflicts_detected=conflicts_detected,
            review_items_created=review_items
        )
        
        logger.info(f"Validation complete: valid={result.is_valid}, "
                   f"issues={len(result.issues)}, conflicts={conflicts_detected}")
        
        return result
    
    def validate_entity(self, entity_id: str) -> ValidationResult:
        """Validate a specific entity by ID."""
        entity = self.session.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            return ValidationResult(
                is_valid=False,
                entities_checked=0,
                relationships_checked=0,
                errors=[f"Entity not found: {entity_id}"]
            )
        
        issues = self._validate_entity(entity)
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        
        return ValidationResult(
            is_valid=not has_errors,
            entities_checked=1,
            relationships_checked=0,
            issues=issues
        )
    
    def validate_relationship(self, relationship_id: str) -> ValidationResult:
        """Validate a specific relationship by ID."""
        rel = self.session.query(Relationship).filter(Relationship.id == relationship_id).first()
        if not rel:
            return ValidationResult(
                is_valid=False,
                entities_checked=0,
                relationships_checked=0,
                errors=[f"Relationship not found: {relationship_id}"]
            )
        
        issues = self._validate_relationship(rel)
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        
        return ValidationResult(
            is_valid=not has_errors,
            entities_checked=0,
            relationships_checked=1,
            issues=issues
        )
    
    def _validate_entity(self, entity: Entity) -> List[ValidationIssue]:
        """Validate a single entity against schema rules."""
        issues = []
        
        entity_type_str = entity.entity_type if entity.entity_type else ""
        
        schema_type = None
        if entity.properties and "_schema_type" in entity.properties:
            schema_type = entity.properties["_schema_type"]
        else:
            schema_type = entity_type_str
        
        entity_config = self.schema.get_entity_type(schema_type)
        
        if not entity_config:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                rule_name="unknown_entity_type",
                message=f"Entity type '{schema_type}' not in current schema",
                entity_id=str(entity.id),
                suggested_action="Verify schema config or update entity type"
            ))
            return issues
        
        for required_field in entity_config.required_fields:
            has_field = False
            
            if required_field == "canonical_name" or required_field == "name":
                has_field = bool(entity.name)
            elif entity.properties and required_field in entity.properties:
                has_field = bool(entity.properties[required_field])
            
            if not has_field:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    rule_name="missing_required_field",
                    message=f"Missing required field '{required_field}' for {entity_config.name}",
                    entity_id=str(entity.id),
                    suggested_action=f"Add {required_field} to entity properties"
                ))
        
        if entity.confidence is not None and entity.confidence < 0.7:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                rule_name="low_confidence",
                message=f"Entity has low confidence ({entity.confidence:.2f})",
                entity_id=str(entity.id),
                suggested_action="Review source and verify entity"
            ))
        
        return issues
    
    def _validate_relationship(self, rel: Relationship) -> List[ValidationIssue]:
        """Validate a single relationship against schema rules."""
        issues = []
        
        rel_type_str = rel.relationship_type if rel.relationship_type else ""
        
        schema_type = None
        if rel.properties and "_schema_type" in rel.properties:
            schema_type = rel.properties["_schema_type"]
        else:
            schema_type = rel_type_str
        
        rel_config = self.schema.get_relationship_type(schema_type)
        
        if not rel_config:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                rule_name="unknown_relationship_type",
                message=f"Relationship type '{schema_type}' not in current schema",
                relationship_id=str(rel.id),
                suggested_action="Verify schema config or update relationship type"
            ))
            return issues
        
        source_entity = self.session.query(Entity).filter(Entity.id == rel.source_id).first()
        target_entity = self.session.query(Entity).filter(Entity.id == rel.target_id).first()
        
        if not source_entity:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                rule_name="missing_source",
                message=f"Source entity not found for relationship",
                relationship_id=str(rel.id),
                suggested_action="Delete orphaned relationship or restore source entity"
            ))
            return issues
        
        if not target_entity:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                rule_name="missing_target",
                message=f"Target entity not found for relationship",
                relationship_id=str(rel.id),
                suggested_action="Delete orphaned relationship or restore target entity"
            ))
            return issues
        
        source_type = source_entity.entity_type if source_entity.entity_type else ""
        target_type = target_entity.entity_type if target_entity.entity_type else ""
        
        if not rel_config.is_valid_source(source_type):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                rule_name="invalid_source_type",
                message=f"Invalid source type {source_type} for {schema_type}. "
                       f"Valid: {rel_config.source_types}",
                relationship_id=str(rel.id),
                suggested_action="Change relationship type or source entity type"
            ))
        
        if not rel_config.is_valid_target(target_type):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                rule_name="invalid_target_type",
                message=f"Invalid target type {target_type} for {schema_type}. "
                       f"Valid: {rel_config.target_types}",
                relationship_id=str(rel.id),
                suggested_action="Change relationship type or target entity type"
            ))
        
        if rel.confidence is not None and rel.confidence < 0.7:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                rule_name="low_confidence",
                message=f"Relationship has low confidence ({rel.confidence:.2f})",
                relationship_id=str(rel.id),
                suggested_action="Review source and verify relationship"
            ))
        
        return issues
    
    def _check_cardinality_violations(self, staging_relationships: List[Relationship]) -> List[ValidationIssue]:
        """
        Check for cardinality violations across all relationships.
        
        For many-to-one relationships (e.g., OWNS, CAUSED_BY), verify that:
        - Each source has at most one target (in combined STAGING + TRUSTED)
        
        Note: Relationship types are now stored as VARCHAR strings (not enums).
        Schema-specific types are validated via _schema_type property in relationships.
        """
        issues = []
        
        for rel_type in self.many_to_one_types:
            existing_targets = {}
            
            trusted_rels = self.session.query(Relationship).filter(
                Relationship.relationship_type == rel_type.upper(),
                Relationship.lifecycle_state == LifecycleState.TRUSTED
            ).all()
            
            for rel in trusted_rels:
                source_key = str(rel.source_id)
                if source_key in existing_targets:
                    pass
                else:
                    existing_targets[source_key] = {
                        "target_id": str(rel.target_id),
                        "rel_id": str(rel.id),
                        "is_trusted": True
                    }
            
            for rel in staging_relationships:
                rel_type_str = rel.relationship_type if rel.relationship_type else ""
                schema_type = rel.properties.get("_schema_type", rel_type_str) if rel.properties else rel_type_str
                
                if schema_type.upper() != rel_type:
                    continue
                
                source_key = str(rel.source_id)
                
                if source_key in existing_targets:
                    existing = existing_targets[source_key]
                    
                    if existing["target_id"] != str(rel.target_id):
                        source_entity = self.session.query(Entity).filter(
                            Entity.id == rel.source_id
                        ).first()
                        source_name = source_entity.name if source_entity else "Unknown"
                        
                        target_entity = self.session.query(Entity).filter(
                            Entity.id == rel.target_id
                        ).first()
                        new_target_name = target_entity.name if target_entity else "Unknown"
                        
                        old_target = self.session.query(Entity).filter(
                            Entity.id == uuid.UUID(existing["target_id"])
                        ).first()
                        old_target_name = old_target.name if old_target else "Unknown"
                        
                        state = "TRUSTED" if existing["is_trusted"] else "STAGING"
                        
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            rule_name="cardinality_violation",
                            message=f"Cardinality violation: {source_name} already has {rel_type} "
                                   f"to {old_target_name} ({state}), cannot also have {rel_type} "
                                   f"to {new_target_name}",
                            relationship_id=str(rel.id),
                            conflicting_fact_id=existing["rel_id"],
                            suggested_action=f"Remove one relationship or use many-to-many type"
                        ))
                else:
                    existing_targets[source_key] = {
                        "target_id": str(rel.target_id),
                        "rel_id": str(rel.id),
                        "is_trusted": False
                    }
        
        return issues
    
    def _detect_and_record_conflicts(self, staging_entities: List[Entity], 
                                      staging_relationships: List[Relationship]) -> int:
        """
        Detect conflicts between STAGING facts and existing TRUSTED facts.
        Record conflicts in the conflicts table.
        
        Returns:
            Number of conflicts detected
        """
        conflicts_count = 0
        
        for entity in staging_entities:
            trusted_same_name = self.session.query(Entity).filter(
                Entity.name == entity.name,
                Entity.lifecycle_state == LifecycleState.TRUSTED,
                Entity.entity_type == entity.entity_type,
                Entity.id != entity.id
            ).first()
            
            if trusted_same_name:
                if (entity.properties and trusted_same_name.properties and 
                    entity.properties != trusted_same_name.properties):
                    
                    existing_conflict = self.session.query(Conflict).filter(
                        Conflict.fact_a_id == entity.id,
                        Conflict.fact_b_id == trusted_same_name.id,
                        Conflict.status == ConflictStatus.PENDING
                    ).first()
                    
                    if not existing_conflict:
                        conflict = Conflict(
                            id=uuid.uuid4(),
                            fact_a_id=entity.id,
                            fact_a_type="entity",
                            fact_b_id=trusted_same_name.id,
                            fact_b_type="entity",
                            conflict_type=ConflictType.VALUE_MISMATCH,
                            status=ConflictStatus.PENDING,
                            description=f"STAGING entity '{entity.name}' has different properties than TRUSTED version",
                            fact_a_summary=f"STAGING: {entity.name} - {str(entity.properties)[:100]}",
                            fact_b_summary=f"TRUSTED: {trusted_same_name.name} - {str(trusted_same_name.properties)[:100]}",
                            confidence_a=entity.confidence,
                            confidence_b=trusted_same_name.confidence,
                            source_document_id=entity.source_document_id
                        )
                        self.session.add(conflict)
                        conflicts_count += 1
                        logger.info(f"Detected conflict: entity '{entity.name}' - value mismatch")
        
        try:
            self.session.commit()
        except Exception as e:
            logger.error(f"Failed to record conflicts: {e}")
            self.session.rollback()
        
        return conflicts_count
    
    def _create_review_items(self, issues: List[ValidationIssue]) -> int:
        """
        Create review queue items for issues that need human attention.
        
        Returns:
            Number of review items created
        """
        review_count = 0
        
        for issue in issues:
            if issue.severity not in [ValidationSeverity.ERROR, ValidationSeverity.WARNING]:
                continue
            
            item_id = None
            if issue.entity_id:
                try:
                    item_id = uuid.UUID(issue.entity_id)
                except ValueError:
                    continue
            elif issue.relationship_id:
                try:
                    item_id = uuid.UUID(issue.relationship_id)
                except ValueError:
                    continue
            else:
                continue
            
            existing = self.session.query(ReviewQueue).filter(
                ReviewQueue.item_id == item_id,
                ReviewQueue.status == ReviewStatus.PENDING
            ).first()
            
            if existing:
                continue
            
            item_type = ReviewItemType.RULE_VIOLATION
            if issue.rule_name == "low_confidence":
                item_type = ReviewItemType.LOW_CONFIDENCE
            elif issue.conflicting_fact_id:
                item_type = ReviewItemType.CONFLICT
            
            priority = 30 if issue.severity == ValidationSeverity.ERROR else 50
            
            review_item = ReviewQueue(
                id=uuid.uuid4(),
                item_type=item_type,
                item_id=item_id,
                priority=priority,
                status=ReviewStatus.PENDING,
                title=f"[{issue.rule_name}] {issue.message[:100]}",
                description=issue.message,
                context={
                    "severity": issue.severity.value,
                    "rule_name": issue.rule_name,
                    "suggested_action": issue.suggested_action,
                    "conflicting_fact_id": issue.conflicting_fact_id
                }
            )
            self.session.add(review_item)
            review_count += 1
        
        try:
            self.session.commit()
        except Exception as e:
            logger.error(f"Failed to create review items: {e}")
            self.session.rollback()
            return 0
        
        return review_count
    
    def _mark_validation_status(
        self,
        entities: List[Entity],
        relationships: List[Relationship],
        issues: List[ValidationIssue],
        conflicts_count: int
    ) -> None:
        """
        Mark entities and relationships with their validation status.
        
        Status values (stored in properties._validation_status):
        - VALID: No issues found, can be promoted
        - INVALID: Has validation errors, cannot be promoted
        - CONFLICT: Conflicts with existing TRUSTED data
        """
        entity_issues: Dict[str, List[ValidationIssue]] = {}
        rel_issues: Dict[str, List[ValidationIssue]] = {}
        
        for issue in issues:
            if issue.entity_id:
                if issue.entity_id not in entity_issues:
                    entity_issues[issue.entity_id] = []
                entity_issues[issue.entity_id].append(issue)
            if issue.relationship_id:
                if issue.relationship_id not in rel_issues:
                    rel_issues[issue.relationship_id] = []
                rel_issues[issue.relationship_id].append(issue)
        
        for entity in entities:
            entity_id_str = str(entity.id)
            entity_issue_list = entity_issues.get(entity_id_str, [])
            
            if not entity.properties:
                entity.properties = {}
            
            has_conflict = any(i.conflicting_fact_id for i in entity_issue_list)
            has_error = any(i.severity == ValidationSeverity.ERROR for i in entity_issue_list)
            
            if has_conflict:
                status = "CONFLICT"
            elif has_error:
                status = "INVALID"
            else:
                status = "VALID"
            
            entity.properties["_validation_status"] = status
            entity.properties["_validation_issues"] = [
                {"rule": i.rule_name, "severity": i.severity.value, "message": i.message}
                for i in entity_issue_list
            ]
            entity.last_validated_at = datetime.utcnow()
        
        for rel in relationships:
            rel_id_str = str(rel.id)
            rel_issue_list = rel_issues.get(rel_id_str, [])
            
            if not rel.properties:
                rel.properties = {}
            
            has_conflict = any(i.conflicting_fact_id for i in rel_issue_list)
            has_error = any(i.severity == ValidationSeverity.ERROR for i in rel_issue_list)
            
            if has_conflict:
                status = "CONFLICT"
            elif has_error:
                status = "INVALID"
            else:
                status = "VALID"
            
            rel.properties["_validation_status"] = status
            rel.properties["_validation_issues"] = [
                {"rule": i.rule_name, "severity": i.severity.value, "message": i.message}
                for i in rel_issue_list
            ]
            rel.last_validated_at = datetime.utcnow()
        
        try:
            self.session.commit()
            logger.info(f"Marked validation status for {len(entities)} entities and {len(relationships)} relationships")
        except Exception as e:
            logger.error(f"Failed to mark validation status: {e}")
            self.session.rollback()
    
    def get_pending_review_items(self, limit: int = 50) -> List[Dict]:
        """Get pending review queue items."""
        items = self.session.query(ReviewQueue).filter(
            ReviewQueue.status == ReviewStatus.PENDING
        ).order_by(ReviewQueue.priority.asc()).limit(limit).all()
        
        return [item.to_dict() for item in items]
    
    def get_pending_conflicts(self, limit: int = 50) -> List[Dict]:
        """Get pending conflicts needing resolution."""
        conflicts = self.session.query(Conflict).filter(
            Conflict.status == ConflictStatus.PENDING
        ).order_by(Conflict.detected_at.desc()).limit(limit).all()
        
        return [c.to_dict() for c in conflicts]
    
    def get_schema_info(self) -> Dict:
        """Return current schema configuration."""
        return {
            "domain": self.schema.domain,
            "schema_version": self.schema.schema_version,
            "cardinality_rules": self.cardinality_constraints,
            "many_to_one_types": self.many_to_one_types,
            "validation_rules": [
                {
                    "name": r.name,
                    "applies_to": r.applies_to,
                    "description": r.description
                }
                for r in self.schema.validation_rules
            ]
        }
    
    def close(self):
        """Close database session."""
        if self.session:
            self.session.close()
