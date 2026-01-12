"""
Extraction Gap Detector for Context Foundry.

Phase 2.6: Extraction Hardening - Defense in Depth Layer 3.
Detects extraction gaps and flags them for review or automated fixing.

Gap Types Detected:
1. People without roles (PERSON with no HOLDS_POSITION)
2. Orphan roles (JOB_TITLE with no person holding them)
3. Missing REPORTS_TO (people without reporting relationships)
4. Compensation without role linkage (HAS_COMPENSATION but no HOLDS_POSITION)
5. Person without organization context (no WORKS_AT/EMPLOYED_BY)
6. Invalid relationship targets (e.g., INVESTED_IN → "75th percentile" instead of ORGANIZATION)

This is a GENERALIZED solution that works for ANY domain.

RELATIONSHIP_TARGET_CONSTRAINTS defines valid target types for each relationship:
- INVESTED_IN must target ORGANIZATION/COMPANY
- HOLDS_POSITION must target JOB_TITLE/ROLE
- REPORTS_TO must target PERSON
- etc.

This prevents garbage data like "TechVentures INVESTED_IN 75th percentile".
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import text, func

from ..models.schema import Entity, Relationship, LifecycleState
from ..utils.logger import logger


class GapSeverity(str, Enum):
    """Severity of extraction gap."""
    CRITICAL = "critical"  # Definitely missing, should be fixed
    WARNING = "warning"  # Possibly missing, needs review
    INFO = "info"  # Minor gap, optional to fix


class GapType(str, Enum):
    """Types of extraction gaps."""
    PERSON_WITHOUT_ROLE = "person_without_role"
    ORPHAN_ROLE = "orphan_role"
    MISSING_REPORTS_TO = "missing_reports_to"
    COMPENSATION_WITHOUT_ROLE = "compensation_without_role"
    ROLE_WITHOUT_ORGANIZATION = "role_without_organization"
    PERSON_WITHOUT_ORGANIZATION = "person_without_organization"
    INVALID_RELATIONSHIP_TARGET = "invalid_relationship_target"  # Target entity type doesn't match expected


# =============================================================================
# RELATIONSHIP TARGET CONSTRAINTS
# =============================================================================
# Defines valid target entity types for each relationship type.
# Prevents garbage like "INVESTED_IN → 75th percentile"

RELATIONSHIP_TARGET_CONSTRAINTS = {
    # Investment relationships - target must be an organization
    "INVESTED_IN": ["ORGANIZATION", "COMPANY", "STARTUP", "PORTFOLIO_COMPANY"],
    "HAS_INVESTMENT": ["ORGANIZATION", "COMPANY", "STARTUP", "PORTFOLIO_COMPANY"],

    # Role relationships - target must be a job title/role
    "HOLDS_POSITION": ["JOB_TITLE", "ROLE", "POSITION"],
    "HAS_ROLE": ["JOB_TITLE", "ROLE", "POSITION"],

    # Reporting relationships - target must be a person
    "REPORTS_TO": ["PERSON", "EMPLOYEE", "EXECUTIVE"],
    "MANAGED_BY": ["PERSON", "EMPLOYEE", "EXECUTIVE"],
    "SUPERVISED_BY": ["PERSON", "EMPLOYEE", "EXECUTIVE"],

    # Employment relationships - target must be an organization
    "WORKS_AT": ["ORGANIZATION", "COMPANY", "DEPARTMENT", "TEAM"],
    "EMPLOYED_BY": ["ORGANIZATION", "COMPANY", "DEPARTMENT", "TEAM"],
    "MEMBER_OF": ["ORGANIZATION", "COMPANY", "DEPARTMENT", "TEAM", "BOARD", "COMMITTEE"],

    # Ownership relationships - target should be ownable entity
    "OWNS": ["ORGANIZATION", "COMPANY", "SERVICE", "PRODUCT", "ASSET", "DEPARTMENT"],
    "MANAGES": ["ORGANIZATION", "COMPANY", "SERVICE", "PRODUCT", "TEAM", "DEPARTMENT"],

    # Dependency relationships - target should be a service/system
    "DEPENDS_ON": ["SERVICE", "SYSTEM", "DATABASE", "API", "COMPONENT"],
    "USES": ["SERVICE", "SYSTEM", "DATABASE", "API", "COMPONENT", "TECHNOLOGY"],

    # Location relationships
    "LOCATED_IN": ["LOCATION", "OFFICE", "BUILDING", "CITY", "REGION", "COUNTRY"],
    "HEADQUARTERED_IN": ["LOCATION", "CITY", "REGION", "COUNTRY"],

    # Compensation - target should be monetary or compensation entity
    "RECEIVES_COMPENSATION": ["COMPENSATION", "SALARY", "MONETARY_VALUE"],
    "HAS_COMPENSATION": ["COMPENSATION", "SALARY", "MONETARY_VALUE"],

    # Part-of relationships
    "PART_OF": ["ORGANIZATION", "COMPANY", "DEPARTMENT", "TEAM", "SYSTEM"],
    "SUBSIDIARY_OF": ["ORGANIZATION", "COMPANY"],
}


@dataclass
class ExtractionGap:
    """A detected gap in extraction."""
    gap_type: GapType
    severity: GapSeverity
    entity_id: str
    entity_name: str
    entity_type: str
    description: str
    suggested_fix: str = ""
    detected_at: datetime = field(default_factory=datetime.utcnow)
    document_id: Optional[str] = None
    fixable: bool = False
    fix_confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "gap_type": self.gap_type.value,
            "severity": self.severity.value,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "description": self.description,
            "suggested_fix": self.suggested_fix,
            "detected_at": self.detected_at.isoformat(),
            "document_id": self.document_id,
            "fixable": self.fixable,
            "fix_confidence": round(self.fix_confidence, 2)
        }


@dataclass
class GapDetectionResult:
    """Result of gap detection analysis."""
    gaps: List[ExtractionGap] = field(default_factory=list)
    entities_analyzed: int = 0
    relationships_analyzed: int = 0
    detection_time_ms: float = 0.0

    @property
    def critical_count(self) -> int:
        return sum(1 for g in self.gaps if g.severity == GapSeverity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for g in self.gaps if g.severity == GapSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for g in self.gaps if g.severity == GapSeverity.INFO)

    def to_dict(self) -> Dict:
        return {
            "gaps": [g.to_dict() for g in self.gaps],
            "entities_analyzed": self.entities_analyzed,
            "relationships_analyzed": self.relationships_analyzed,
            "detection_time_ms": round(self.detection_time_ms, 2),
            "summary": {
                "total": len(self.gaps),
                "critical": self.critical_count,
                "warning": self.warning_count,
                "info": self.info_count
            }
        }


class ExtractionGapDetector:
    """
    Detects extraction gaps in the knowledge graph.

    Runs after extraction to identify missing relationships that
    should exist based on the data we have.
    """

    def __init__(
        self,
        session: Session,
        tenant_id: Optional[str] = None
    ):
        self.session = session
        self.tenant_id = tenant_id

    def detect_all(
        self,
        document_id: Optional[str] = None,
        include_trusted: bool = False
    ) -> GapDetectionResult:
        """
        Detect all extraction gaps.

        Args:
            document_id: Optional - limit to entities from specific document
            include_trusted: Whether to include TRUSTED entities (default False for staging-only)

        Returns:
            GapDetectionResult with all detected gaps
        """
        import time
        start = time.time()

        result = GapDetectionResult()

        # Get entities to analyze
        entities = self._get_entities(document_id, include_trusted)
        relationships = self._get_relationships(document_id, include_trusted)

        result.entities_analyzed = len(entities)
        result.relationships_analyzed = len(relationships)

        # Build lookup structures
        entity_by_id = {str(e.id): e for e in entities}
        person_ids = {str(e.id) for e in entities if e.entity_type == "PERSON"}
        role_ids = {str(e.id) for e in entities if e.entity_type == "JOB_TITLE"}
        org_ids = {str(e.id) for e in entities if e.entity_type in ("ORGANIZATION", "COMPANY")}

        # Build relationship lookups
        holds_position_by_person = {}  # person_id -> list of role_ids
        holds_position_by_role = {}  # role_id -> list of person_ids
        reports_to_by_person = {}  # person_id -> list of manager_ids
        has_compensation_by_person = {}  # person_id -> list of compensation entities
        employed_by_person = {}  # person_id -> list of org_ids

        for rel in relationships:
            source_id = str(rel.source_id)
            target_id = str(rel.target_id)
            rel_type = rel.relationship_type

            if rel_type == "HOLDS_POSITION":
                holds_position_by_person.setdefault(source_id, []).append(target_id)
                holds_position_by_role.setdefault(target_id, []).append(source_id)

            elif rel_type == "REPORTS_TO":
                reports_to_by_person.setdefault(source_id, []).append(target_id)

            elif rel_type == "HAS_COMPENSATION":
                has_compensation_by_person.setdefault(source_id, []).append(target_id)

            elif rel_type in ("EMPLOYED_BY", "WORKS_AT", "MEMBER_OF"):
                employed_by_person.setdefault(source_id, []).append(target_id)

        # CHECK 1: People without roles
        for person_id in person_ids:
            if person_id not in holds_position_by_person:
                entity = entity_by_id.get(person_id)
                if entity:
                    gap = ExtractionGap(
                        gap_type=GapType.PERSON_WITHOUT_ROLE,
                        severity=GapSeverity.WARNING,
                        entity_id=person_id,
                        entity_name=entity.name,
                        entity_type=entity.entity_type,
                        description=f"Person '{entity.name}' has no HOLDS_POSITION relationship",
                        suggested_fix="Re-scan source document for role mentions",
                        document_id=str(entity.source_document_id) if entity.source_document_id else None
                    )
                    result.gaps.append(gap)

        # CHECK 2: Orphan roles (JOB_TITLE with no holder)
        for role_id in role_ids:
            if role_id not in holds_position_by_role:
                entity = entity_by_id.get(role_id)
                if entity:
                    gap = ExtractionGap(
                        gap_type=GapType.ORPHAN_ROLE,
                        severity=GapSeverity.INFO,
                        entity_id=role_id,
                        entity_name=entity.name,
                        entity_type=entity.entity_type,
                        description=f"Role '{entity.name}' has no person holding it",
                        suggested_fix="Check if role is mentioned without explicit person",
                        document_id=str(entity.source_document_id) if entity.source_document_id else None
                    )
                    result.gaps.append(gap)

        # CHECK 3: Missing REPORTS_TO for people with roles
        for person_id in person_ids:
            if person_id in holds_position_by_person and person_id not in reports_to_by_person:
                entity = entity_by_id.get(person_id)
                if entity:
                    # Check if this person might be at the top of hierarchy
                    role_ids_held = holds_position_by_person[person_id]
                    roles = [entity_by_id.get(rid) for rid in role_ids_held if entity_by_id.get(rid)]
                    role_names = [r.name.upper() for r in roles if r]

                    # C-level executives might not have REPORTS_TO
                    is_top_exec = any(
                        "CEO" in name or
                        "CHIEF EXECUTIVE" in name or
                        "PRESIDENT" in name or
                        "MANAGING PARTNER" in name or
                        "CHAIRMAN" in name
                        for name in role_names
                    )

                    if not is_top_exec:
                        gap = ExtractionGap(
                            gap_type=GapType.MISSING_REPORTS_TO,
                            severity=GapSeverity.INFO,
                            entity_id=person_id,
                            entity_name=entity.name,
                            entity_type=entity.entity_type,
                            description=f"Person '{entity.name}' has role but no REPORTS_TO relationship",
                            suggested_fix="Determine reporting structure from org chart",
                            document_id=str(entity.source_document_id) if entity.source_document_id else None
                        )
                        result.gaps.append(gap)

        # CHECK 4: Compensation without role
        for person_id, comp_list in has_compensation_by_person.items():
            if person_id not in holds_position_by_person:
                entity = entity_by_id.get(person_id)
                if entity:
                    gap = ExtractionGap(
                        gap_type=GapType.COMPENSATION_WITHOUT_ROLE,
                        severity=GapSeverity.WARNING,
                        entity_id=person_id,
                        entity_name=entity.name,
                        entity_type=entity.entity_type,
                        description=f"Person '{entity.name}' has compensation but no role",
                        suggested_fix="Link compensation to role, not just person",
                        document_id=str(entity.source_document_id) if entity.source_document_id else None
                    )
                    result.gaps.append(gap)

        # CHECK 5: Person without organization
        for person_id in person_ids:
            if person_id not in employed_by_person:
                entity = entity_by_id.get(person_id)
                if entity and org_ids:  # Only flag if there are orgs in the graph
                    gap = ExtractionGap(
                        gap_type=GapType.PERSON_WITHOUT_ORGANIZATION,
                        severity=GapSeverity.INFO,
                        entity_id=person_id,
                        entity_name=entity.name,
                        entity_type=entity.entity_type,
                        description=f"Person '{entity.name}' not linked to any organization",
                        suggested_fix="Add EMPLOYED_BY or WORKS_AT relationship",
                        document_id=str(entity.source_document_id) if entity.source_document_id else None
                    )
                    result.gaps.append(gap)

        # CHECK 6: Invalid relationship targets
        # Validates that relationship targets have the expected entity type
        # e.g., INVESTED_IN should target ORGANIZATION, not "75th percentile"
        for rel in relationships:
            rel_type = rel.relationship_type.upper()
            target_id = str(rel.target_id)
            target_entity = entity_by_id.get(target_id)

            if not target_entity:
                continue

            # Check if this relationship type has constraints
            valid_target_types = RELATIONSHIP_TARGET_CONSTRAINTS.get(rel_type)
            if not valid_target_types:
                continue  # No constraints defined for this relationship type

            # Check if target entity type is valid
            target_type = target_entity.entity_type.upper() if target_entity.entity_type else "UNKNOWN"
            valid_types_upper = [t.upper() for t in valid_target_types]

            if target_type not in valid_types_upper:
                source_entity = entity_by_id.get(str(rel.source_id))
                source_name = source_entity.name if source_entity else "Unknown"

                gap = ExtractionGap(
                    gap_type=GapType.INVALID_RELATIONSHIP_TARGET,
                    severity=GapSeverity.CRITICAL,  # This is a data quality issue
                    entity_id=target_id,
                    entity_name=target_entity.name,
                    entity_type=target_entity.entity_type or "UNKNOWN",
                    description=(
                        f"Relationship '{source_name}' --[{rel_type}]--> '{target_entity.name}' "
                        f"has invalid target type '{target_type}'. "
                        f"Expected one of: {', '.join(valid_target_types)}"
                    ),
                    suggested_fix=f"Re-extract or manually fix: {rel_type} should target {'/'.join(valid_target_types[:3])}",
                    document_id=str(rel.source_document_id) if hasattr(rel, 'source_document_id') and rel.source_document_id else None,
                    fixable=True,
                    fix_confidence=0.0  # Needs manual review
                )
                result.gaps.append(gap)

        result.detection_time_ms = (time.time() - start) * 1000

        if result.gaps:
            logger.info(f"[GapDetector] Found {len(result.gaps)} gaps: "
                       f"{result.critical_count} critical, "
                       f"{result.warning_count} warning, "
                       f"{result.info_count} info")

        return result

    def _get_entities(
        self,
        document_id: Optional[str],
        include_trusted: bool
    ) -> List[Entity]:
        """Get entities to analyze."""
        try:
            states = [LifecycleState.STAGING]
            if include_trusted:
                states.append(LifecycleState.TRUSTED)

            query = self.session.query(Entity).filter(
                Entity.lifecycle_state.in_(states)
            )

            if self.tenant_id:
                query = query.filter(Entity.tenant_id == self.tenant_id)

            if document_id:
                query = query.filter(Entity.source_document_id == document_id)

            return query.all()

        except Exception as e:
            logger.error(f"[GapDetector] Failed to load entities: {e}")
            return []

    def _get_relationships(
        self,
        document_id: Optional[str],
        include_trusted: bool
    ) -> List[Relationship]:
        """Get relationships to analyze."""
        try:
            states = [LifecycleState.STAGING]
            if include_trusted:
                states.append(LifecycleState.TRUSTED)

            query = self.session.query(Relationship).filter(
                Relationship.lifecycle_state.in_(states)
            )

            if self.tenant_id:
                query = query.filter(Relationship.tenant_id == self.tenant_id)

            if document_id:
                query = query.filter(Relationship.source_document_id == document_id)

            return query.all()

        except Exception as e:
            logger.error(f"[GapDetector] Failed to load relationships: {e}")
            return []


# =============================================================================
# RELATIONSHIP TYPE STANDARDIZATION
# =============================================================================

# Single source of truth for relationship types
# Maps common variations to standard forms
RELATIONSHIP_TYPE_MAPPINGS = {
    # Role relationships
    "HELD_POSITION": "HOLDS_POSITION",
    "HOLD_POSITION": "HOLDS_POSITION",
    "HAS_POSITION": "HOLDS_POSITION",
    "HAS_ROLE": "HOLDS_POSITION",
    "IN_ROLE": "HOLDS_POSITION",

    # Reporting relationships
    "REPORTS_TO": "REPORTS_TO",
    "MANAGED_BY": "REPORTS_TO",
    "SUPERVISED_BY": "REPORTS_TO",

    # Employment relationships
    "WORKS_AT": "EMPLOYED_BY",
    "WORKS_FOR": "EMPLOYED_BY",
    "MEMBER_OF": "EMPLOYED_BY",

    # Ownership relationships
    "MANAGES": "OWNS",
    "RESPONSIBLE_FOR": "OWNS",
}


def standardize_relationship_type(rel_type: str) -> str:
    """
    Standardize a relationship type to its canonical form.

    This is the single source of truth for relationship type naming.
    All extraction code should use this function.
    """
    rel_upper = rel_type.upper().strip()
    return RELATIONSHIP_TYPE_MAPPINGS.get(rel_upper, rel_upper)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_gap_detector(session: Session, tenant_id: Optional[str] = None) -> ExtractionGapDetector:
    """Get a configured gap detector instance."""
    return ExtractionGapDetector(session, tenant_id)


def detect_gaps_for_document(
    session: Session,
    document_id: str,
    tenant_id: Optional[str] = None
) -> GapDetectionResult:
    """Convenience function to detect gaps for a specific document."""
    detector = ExtractionGapDetector(session, tenant_id)
    return detector.detect_all(document_id=document_id)
