"""
Consensus Validation & Conflict Resolution

Phase 3 of the extraction pipeline: Validates consensus outputs against
ontology constraints and detects/resolves conflicts.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from datetime import datetime
from enum import Enum

from ..ontology.schema import EntityType, RelationshipType
from .entity_resolver import CanonicalEntity, CanonicalRelationship, ConsensusOutput


class IssueSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueType(Enum):
    """Types of validation issues."""
    MISSING_REQUIRED_PROPERTY = "missing_required_property"
    INVALID_PROPERTY_VALUE = "invalid_property_value"
    LOW_CONFIDENCE = "low_confidence"
    SINGLE_MODEL_ONLY = "single_model_only"
    PROPERTY_CONFLICT = "property_conflict"
    ORPHAN_RELATIONSHIP = "orphan_relationship"
    DUPLICATE_RELATIONSHIP = "duplicate_relationship"
    MISSING_EVIDENCE = "missing_evidence"
    INCOMPLETE_NAME = "incomplete_name"
    AMBIGUOUS_TYPE = "ambiguous_type"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    issue_type: IssueType
    severity: IssueSeverity
    entity_name: Optional[str]
    relationship_key: Optional[str]
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    auto_resolvable: bool = False
    resolution: Optional[str] = None


@dataclass
class ConflictInfo:
    """Information about a property conflict."""
    entity_name: str
    property_name: str
    conflicting_values: List[Any]
    source_models: List[str]
    resolution_strategy: str
    resolved_value: Optional[Any] = None


@dataclass 
class QualityScore:
    """Quality metrics for an extraction."""
    overall_score: float
    completeness_score: float
    confidence_score: float
    consistency_score: float
    multi_model_coverage: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Complete validation report for a consensus output."""
    is_valid: bool
    issues: List[ValidationIssue]
    conflicts: List[ConflictInfo]
    quality: QualityScore
    entity_count: int
    relationship_count: int
    error_count: int
    warning_count: int
    info_count: int
    validated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": [
                {
                    "issue_type": i.issue_type.value,
                    "severity": i.severity.value,
                    "entity_name": i.entity_name,
                    "relationship_key": i.relationship_key,
                    "message": i.message,
                    "details": i.details,
                    "auto_resolvable": i.auto_resolvable,
                    "resolution": i.resolution,
                }
                for i in self.issues
            ],
            "conflicts": [
                {
                    "entity_name": c.entity_name,
                    "property_name": c.property_name,
                    "conflicting_values": c.conflicting_values,
                    "source_models": c.source_models,
                    "resolution_strategy": c.resolution_strategy,
                    "resolved_value": c.resolved_value,
                }
                for c in self.conflicts
            ],
            "quality": {
                "overall_score": self.quality.overall_score,
                "completeness_score": self.quality.completeness_score,
                "confidence_score": self.quality.confidence_score,
                "consistency_score": self.quality.consistency_score,
                "multi_model_coverage": self.quality.multi_model_coverage,
                "details": self.quality.details,
            },
            "entity_count": self.entity_count,
            "relationship_count": self.relationship_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "validated_at": self.validated_at.isoformat(),
        }


class OntologyConstraints:
    """Defines required properties and constraints for entity types."""
    
    REQUIRED_PROPERTIES: Dict[EntityType, List[str]] = {
        EntityType.PERSON: [],
        EntityType.ORGANIZATION: [],
        EntityType.BUSINESS_UNIT: [],
        EntityType.PROJECT: [],
        EntityType.PRODUCT: [],
        EntityType.SERVICE: [],
        EntityType.CUSTOMER: [],
        EntityType.SUPPLIER: [],
        EntityType.PARTNER: [],
        EntityType.FINANCIAL_METRIC: ["value"],
        EntityType.LOCATION: [],
        EntityType.FACILITY: [],
        EntityType.POLICY: [],
        EntityType.TECHNOLOGY: [],
        EntityType.CONCEPT: [],
        EntityType.DOCUMENT: [],
    }
    
    RECOMMENDED_PROPERTIES: Dict[EntityType, List[str]] = {
        EntityType.PERSON: ["title", "role", "department"],
        EntityType.ORGANIZATION: ["type", "industry"],
        EntityType.BUSINESS_UNIT: ["focus_areas"],
        EntityType.PROJECT: ["budget", "timeline", "status"],
        EntityType.PRODUCT: ["description", "category"],
        EntityType.SERVICE: ["description"],
        EntityType.CUSTOMER: ["industry", "region"],
        EntityType.SUPPLIER: ["capability", "risk_level"],
        EntityType.PARTNER: ["partnership_type"],
        EntityType.FINANCIAL_METRIC: ["period", "metric_type"],
        EntityType.LOCATION: ["city", "country"],
        EntityType.FACILITY: ["location", "type"],
        EntityType.POLICY: ["category", "policy_id"],
        EntityType.TECHNOLOGY: ["description"],
    }
    
    @classmethod
    def get_required_properties(cls, entity_type: EntityType) -> List[str]:
        return cls.REQUIRED_PROPERTIES.get(entity_type, [])
    
    @classmethod
    def get_recommended_properties(cls, entity_type: EntityType) -> List[str]:
        return cls.RECOMMENDED_PROPERTIES.get(entity_type, [])


class ConsensusValidator:
    """Validates consensus outputs and detects issues."""
    
    LOW_CONFIDENCE_THRESHOLD = 0.5
    VERY_LOW_CONFIDENCE_THRESHOLD = 0.3
    
    def __init__(self):
        self.constraints = OntologyConstraints()
    
    def validate(self, consensus: ConsensusOutput) -> ValidationReport:
        """Validate a consensus output and return a report."""
        issues: List[ValidationIssue] = []
        conflicts: List[ConflictInfo] = []
        
        entity_names = {e.canonical_name for e in consensus.entities}
        
        for entity in consensus.entities:
            entity_issues, entity_conflicts = self._validate_entity(entity)
            issues.extend(entity_issues)
            conflicts.extend(entity_conflicts)
        
        for rel in consensus.relationships:
            rel_issues = self._validate_relationship(rel, entity_names)
            issues.extend(rel_issues)
        
        quality = self._compute_quality_score(consensus, issues)
        
        error_count = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        info_count = sum(1 for i in issues if i.severity == IssueSeverity.INFO)
        
        is_valid = error_count == 0
        
        return ValidationReport(
            is_valid=is_valid,
            issues=issues,
            conflicts=conflicts,
            quality=quality,
            entity_count=len(consensus.entities),
            relationship_count=len(consensus.relationships),
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
        )
    
    def _validate_entity(
        self, 
        entity: CanonicalEntity
    ) -> Tuple[List[ValidationIssue], List[ConflictInfo]]:
        """Validate a single entity."""
        issues = []
        conflicts = []
        
        required = self.constraints.get_required_properties(entity.entity_type)
        for prop in required:
            if prop not in entity.properties or entity.properties[prop] is None:
                issues.append(ValidationIssue(
                    issue_type=IssueType.MISSING_REQUIRED_PROPERTY,
                    severity=IssueSeverity.ERROR,
                    entity_name=entity.canonical_name,
                    relationship_key=None,
                    message=f"Missing required property '{prop}' for {entity.entity_type.value}",
                    details={"property": prop, "entity_type": entity.entity_type.value},
                ))
        
        recommended = self.constraints.get_recommended_properties(entity.entity_type)
        missing_recommended = [
            p for p in recommended 
            if p not in entity.properties or entity.properties[p] is None
        ]
        if missing_recommended:
            issues.append(ValidationIssue(
                issue_type=IssueType.MISSING_REQUIRED_PROPERTY,
                severity=IssueSeverity.INFO,
                entity_name=entity.canonical_name,
                relationship_key=None,
                message=f"Missing recommended properties: {', '.join(missing_recommended)}",
                details={"properties": missing_recommended},
                auto_resolvable=False,
            ))
        
        for prop_name, prop_value in entity.properties.items():
            if isinstance(prop_value, list) and len(prop_value) > 1:
                conflict = ConflictInfo(
                    entity_name=entity.canonical_name,
                    property_name=prop_name,
                    conflicting_values=prop_value,
                    source_models=entity.source_models,
                    resolution_strategy="keep_all",
                    resolved_value=prop_value,
                )
                conflicts.append(conflict)
                
                issues.append(ValidationIssue(
                    issue_type=IssueType.PROPERTY_CONFLICT,
                    severity=IssueSeverity.WARNING,
                    entity_name=entity.canonical_name,
                    relationship_key=None,
                    message=f"Conflicting values for '{prop_name}': {prop_value}",
                    details={"property": prop_name, "values": prop_value},
                    auto_resolvable=True,
                    resolution="Kept all values in list",
                ))
        
        if entity.confidence < self.VERY_LOW_CONFIDENCE_THRESHOLD:
            issues.append(ValidationIssue(
                issue_type=IssueType.LOW_CONFIDENCE,
                severity=IssueSeverity.WARNING,
                entity_name=entity.canonical_name,
                relationship_key=None,
                message=f"Very low confidence ({entity.confidence:.2f})",
                details={"confidence": entity.confidence},
            ))
        elif entity.confidence < self.LOW_CONFIDENCE_THRESHOLD:
            issues.append(ValidationIssue(
                issue_type=IssueType.LOW_CONFIDENCE,
                severity=IssueSeverity.INFO,
                entity_name=entity.canonical_name,
                relationship_key=None,
                message=f"Low confidence ({entity.confidence:.2f})",
                details={"confidence": entity.confidence},
            ))
        
        if len(entity.source_models) == 1:
            issues.append(ValidationIssue(
                issue_type=IssueType.SINGLE_MODEL_ONLY,
                severity=IssueSeverity.INFO,
                entity_name=entity.canonical_name,
                relationship_key=None,
                message=f"Only extracted by {entity.source_models[0]}",
                details={"source_models": entity.source_models},
            ))
        
        if entity.entity_type == EntityType.PERSON:
            name_parts = entity.canonical_name.split()
            if len(name_parts) < 2:
                issues.append(ValidationIssue(
                    issue_type=IssueType.INCOMPLETE_NAME,
                    severity=IssueSeverity.INFO,
                    entity_name=entity.canonical_name,
                    relationship_key=None,
                    message="Person name may be incomplete (single word)",
                    details={"name": entity.canonical_name},
                ))
        
        return issues, conflicts
    
    def _validate_relationship(
        self,
        rel: CanonicalRelationship,
        entity_names: Set[str],
    ) -> List[ValidationIssue]:
        """Validate a single relationship."""
        issues = []
        
        rel_key = f"{rel.source_entity} -[{rel.relationship_type.value}]-> {rel.target_entity}"
        
        if rel.source_entity not in entity_names:
            issues.append(ValidationIssue(
                issue_type=IssueType.ORPHAN_RELATIONSHIP,
                severity=IssueSeverity.WARNING,
                entity_name=None,
                relationship_key=rel_key,
                message=f"Source entity '{rel.source_entity}' not in entity list",
                details={"missing_entity": rel.source_entity, "role": "source"},
            ))
        
        if rel.target_entity not in entity_names:
            issues.append(ValidationIssue(
                issue_type=IssueType.ORPHAN_RELATIONSHIP,
                severity=IssueSeverity.WARNING,
                entity_name=None,
                relationship_key=rel_key,
                message=f"Target entity '{rel.target_entity}' not in entity list",
                details={"missing_entity": rel.target_entity, "role": "target"},
            ))
        
        if not rel.evidence:
            issues.append(ValidationIssue(
                issue_type=IssueType.MISSING_EVIDENCE,
                severity=IssueSeverity.INFO,
                entity_name=None,
                relationship_key=rel_key,
                message="Relationship has no evidence/source excerpt",
                details={},
            ))
        
        if rel.confidence < self.LOW_CONFIDENCE_THRESHOLD:
            issues.append(ValidationIssue(
                issue_type=IssueType.LOW_CONFIDENCE,
                severity=IssueSeverity.INFO,
                entity_name=None,
                relationship_key=rel_key,
                message=f"Low confidence relationship ({rel.confidence:.2f})",
                details={"confidence": rel.confidence},
            ))
        
        return issues
    
    def _compute_quality_score(
        self,
        consensus: ConsensusOutput,
        issues: List[ValidationIssue],
    ) -> QualityScore:
        """Compute quality metrics for the extraction."""
        if not consensus.entities:
            return QualityScore(
                overall_score=0.0,
                completeness_score=0.0,
                confidence_score=0.0,
                consistency_score=0.0,
                multi_model_coverage=0.0,
            )
        
        total_recommended = 0
        found_recommended = 0
        for entity in consensus.entities:
            recommended = self.constraints.get_recommended_properties(entity.entity_type)
            total_recommended += len(recommended)
            for prop in recommended:
                if prop in entity.properties and entity.properties[prop] is not None:
                    found_recommended += 1
        
        completeness = found_recommended / total_recommended if total_recommended > 0 else 1.0
        
        avg_confidence = sum(e.confidence for e in consensus.entities) / len(consensus.entities)
        
        error_count = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        total_items = len(consensus.entities) + len(consensus.relationships)
        issue_penalty = (error_count * 0.1 + warning_count * 0.02) / max(total_items, 1)
        consistency = max(0.0, 1.0 - issue_penalty)
        
        multi_model = sum(
            1 for e in consensus.entities if len(e.source_models) > 1
        ) / len(consensus.entities)
        
        overall = (
            completeness * 0.2 +
            avg_confidence * 0.3 +
            consistency * 0.3 +
            multi_model * 0.2
        )
        
        return QualityScore(
            overall_score=round(overall, 3),
            completeness_score=round(completeness, 3),
            confidence_score=round(avg_confidence, 3),
            consistency_score=round(consistency, 3),
            multi_model_coverage=round(multi_model, 3),
            details={
                "total_recommended_properties": total_recommended,
                "found_recommended_properties": found_recommended,
                "error_count": error_count,
                "warning_count": warning_count,
            },
        )


class ConflictResolver:
    """Resolves conflicts in extraction outputs."""
    
    def __init__(self):
        pass
    
    def resolve_property_conflict(
        self,
        entity: CanonicalEntity,
        property_name: str,
        values: List[Any],
    ) -> Tuple[Any, str]:
        """
        Resolve a property conflict.
        Returns (resolved_value, strategy_used).
        """
        if not values:
            return None, "empty"
        
        if len(values) == 1:
            return values[0], "single_value"
        
        if all(isinstance(v, (int, float)) for v in values):
            return sum(values) / len(values), "average"
        
        value_counts: Dict[Any, int] = {}
        for v in values:
            v_str = str(v).lower().strip()
            value_counts[v_str] = value_counts.get(v_str, 0) + 1
        
        max_count = max(value_counts.values())
        if max_count > len(values) / 2:
            for v in values:
                if value_counts.get(str(v).lower().strip()) == max_count:
                    return v, "majority"
        
        longest = max(values, key=lambda x: len(str(x)) if x else 0)
        return longest, "most_specific"
    
    def auto_resolve_conflicts(
        self,
        consensus: ConsensusOutput,
        conflicts: List[ConflictInfo],
    ) -> ConsensusOutput:
        """
        Auto-resolve conflicts where possible.
        Returns a new ConsensusOutput with resolved conflicts.
        """
        resolved_entities = []
        
        for entity in consensus.entities:
            new_props = dict(entity.properties)
            
            for conflict in conflicts:
                if conflict.entity_name == entity.canonical_name:
                    prop_name = conflict.property_name
                    if prop_name in new_props and isinstance(new_props[prop_name], list):
                        resolved_value, strategy = self.resolve_property_conflict(
                            entity, prop_name, new_props[prop_name]
                        )
                        new_props[prop_name] = resolved_value
                        conflict.resolution_strategy = strategy
                        conflict.resolved_value = resolved_value
            
            resolved_entity = CanonicalEntity(
                canonical_name=entity.canonical_name,
                entity_type=entity.entity_type,
                properties=new_props,
                confidence=entity.confidence,
                source_models=entity.source_models,
                name_variants=entity.name_variants,
                aliases=entity.aliases,
                source_documents=entity.source_documents,
                consensus_metadata=entity.consensus_metadata,
            )
            resolved_entities.append(resolved_entity)
        
        return ConsensusOutput(
            entities=resolved_entities,
            relationships=consensus.relationships,
            metadata={
                **consensus.metadata,
                "conflicts_resolved": len(conflicts),
            },
        )


def validate_consensus(consensus: ConsensusOutput) -> ValidationReport:
    """Validate a consensus output and return a report."""
    validator = ConsensusValidator()
    return validator.validate(consensus)


def resolve_conflicts(
    consensus: ConsensusOutput,
    report: ValidationReport,
) -> ConsensusOutput:
    """Resolve conflicts in a consensus output."""
    resolver = ConflictResolver()
    return resolver.auto_resolve_conflicts(consensus, report.conflicts)
