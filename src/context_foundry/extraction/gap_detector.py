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
6. Invalid relationship targets (e.g., INVESTED_IN -> "75th percentile" instead of ORGANIZATION)
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
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class GapType(str, Enum):
    """Types of extraction gaps."""
    PERSON_WITHOUT_ROLE = "person_without_role"
    ORPHAN_ROLE = "orphan_role"
    MISSING_REPORTS_TO = "missing_reports_to"
    COMPENSATION_WITHOUT_ROLE = "compensation_without_role"
    ROLE_WITHOUT_ORGANIZATION = "role_without_organization"
    PERSON_WITHOUT_ORGANIZATION = "person_without_organization"
    INVALID_RELATIONSHIP_TARGET = "invalid_relationship_target"


RELATIONSHIP_TARGET_CONSTRAINTS = {
    "INVESTED_IN": ["ORGANIZATION", "COMPANY", "STARTUP", "PORTFOLIO_COMPANY"],
    "HAS_INVESTMENT": ["ORGANIZATION", "COMPANY", "STARTUP", "PORTFOLIO_COMPANY"],
    "HOLDS_POSITION": ["JOB_TITLE", "ROLE", "POSITION"],
    "HAS_ROLE": ["JOB_TITLE", "ROLE", "POSITION"],
    "REPORTS_TO": ["PERSON", "EMPLOYEE", "EXECUTIVE"],
    "MANAGED_BY": ["PERSON", "EMPLOYEE", "EXECUTIVE"],
    "SUPERVISED_BY": ["PERSON", "EMPLOYEE", "EXECUTIVE"],
    "WORKS_AT": ["ORGANIZATION", "COMPANY", "DEPARTMENT", "TEAM"],
    "EMPLOYED_BY": ["ORGANIZATION", "COMPANY", "DEPARTMENT", "TEAM"],
    "MEMBER_OF": ["ORGANIZATION", "COMPANY", "DEPARTMENT", "TEAM", "BOARD", "COMMITTEE"],
    "OWNS": ["ORGANIZATION", "COMPANY", "SERVICE", "PRODUCT", "ASSET", "DEPARTMENT"],
    "MANAGES": ["ORGANIZATION", "COMPANY", "SERVICE", "PRODUCT", "TEAM", "DEPARTMENT"],
    "DEPENDS_ON": ["SERVICE", "SYSTEM", "DATABASE", "API", "COMPONENT"],
    "USES": ["SERVICE", "SYSTEM", "DATABASE", "API", "COMPONENT", "TECHNOLOGY"],
    "LOCATED_IN": ["LOCATION", "OFFICE", "BUILDING", "CITY", "REGION", "COUNTRY"],
    "HEADQUARTERED_IN": ["LOCATION", "CITY", "REGION", "COUNTRY"],
    "RECEIVES_COMPENSATION": ["COMPENSATION", "SALARY", "MONETARY_VALUE"],
    "HAS_COMPENSATION": ["COMPENSATION", "SALARY", "MONETARY_VALUE"],
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
    """Detects extraction gaps in the knowledge graph."""

    def __init__(self, session: Session, tenant_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id

    def detect_all(self, document_id: Optional[str] = None, include_trusted: bool = False) -> GapDetectionResult:
        """Detect all extraction gaps."""
        import time
        start = time.time()
        result = GapDetectionResult()

        entities = self._get_entities(document_id, include_trusted)
        relationships = self._get_relationships(document_id, include_trusted)

        result.entities_analyzed = len(entities)
        result.relationships_analyzed = len(relationships)

        entity_by_id = {str(e.id): e for e in entities}
        person_ids = {str(e.id) for e in entities if e.entity_type == "PERSON"}
        role_ids = {str(e.id) for e in entities if e.entity_type == "JOB_TITLE"}
        org_ids = {str(e.id) for e in entities if e.entity_type in ("ORGANIZATION", "COMPANY")}

        holds_position_by_person = {}
        holds_position_by_role = {}
        reports_to_by_person = {}
        has_compensation_by_person = {}
        employed_by_person = {}

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
                    result.gaps.append(ExtractionGap(
                        gap_type=GapType.PERSON_WITHOUT_ROLE,
                        severity=GapSeverity.WARNING,
                        entity_id=person_id,
                        entity_name=entity.name,
                        entity_type=entity.entity_type,
                        description=f"Person '{entity.name}' has no HOLDS_POSITION relationship",
                        suggested_fix="Re-scan source document for role mentions",
                        document_id=str(entity.source_document_id) if entity.source_document_id else None
                    ))

        # CHECK 2: Orphan roles
        for role_id in role_ids:
            if role_id not in holds_position_by_role:
                entity = entity_by_id.get(role_id)
                if entity:
                    result.gaps.append(ExtractionGap(
                        gap_type=GapType.ORPHAN_ROLE,
                        severity=GapSeverity.INFO,
                        entity_id=role_id,
                        entity_name=entity.name,
                        entity_type=entity.entity_type,
                        description=f"Role '{entity.name}' has no person holding it",
                        suggested_fix="Check if role is mentioned without explicit person",
                        document_id=str(entity.source_document_id) if entity.source_document_id else None
                    ))

        # CHECK 3: Missing REPORTS_TO for people with roles
        for person_id in person_ids:
            if person_id in holds_position_by_person and person_id not in reports_to_by_person:
                entity = entity_by_id.get(person_id)
                if entity:
                    role_ids_held = holds_position_by_person[person_id]
                    roles = [entity_by_id.get(rid) for rid in role_ids_held if entity_by_id.get(rid)]
                    role_names = [r.name.upper() for r in roles if r]
                    is_top_exec = any(
                        "CEO" in name or "CHIEF EXECUTIVE" in name or
                        "PRESIDENT" in name or "MANAGING PARTNER" in name or "CHAIRMAN" in name
                        for name in role_names
                    )
                    if not is_top_exec:
                        result.gaps.append(ExtractionGap(
                            gap_type=GapType.MISSING_REPORTS_TO,
                            severity=GapSeverity.INFO,
                            entity_id=person_id,
                            entity_name=entity.name,
                            entity_type=entity.entity_type,
                            description=f"Person '{entity.name}' has role but no REPORTS_TO relationship",
                            suggested_fix="Determine reporting structure from org chart",
                            document_id=str(entity.source_document_id) if entity.source_document_id else None
                        ))

        # CHECK 4: Compensation without role
        for person_id, comp_list in has_compensation_by_person.items():
            if person_id not in holds_position_by_person:
                entity = entity_by_id.get(person_id)
                if entity:
                    result.gaps.append(ExtractionGap(
                        gap_type=GapType.COMPENSATION_WITHOUT_ROLE,
                        severity=GapSeverity.WARNING,
                        entity_id=person_id,
                        entity_name=entity.name,
                        entity_type=entity.entity_type,
                        description=f"Person '{entity.name}' has compensation but no role",
                        suggested_fix="Link compensation to role, not just person",
                        document_id=str(entity.source_document_id) if entity.source_document_id else None
                    ))

        # CHECK 5: Person without organization
        for person_id in person_ids:
            if person_id not in employed_by_person:
                entity = entity_by_id.get(person_id)
                if entity and org_ids:
                    result.gaps.append(ExtractionGap(
                        gap_type=GapType.PERSON_WITHOUT_ORGANIZATION,
                        severity=GapSeverity.INFO,
                        entity_id=person_id,
                        entity_name=entity.name,
                        entity_type=entity.entity_type,
                        description=f"Person '{entity.name}' not linked to any organization",
                        suggested_fix="Add EMPLOYED_BY or WORKS_AT relationship",
                        document_id=str(entity.source_document_id) if entity.source_document_id else None
                    ))

        # CHECK 6: Invalid relationship targets
        for rel in relationships:
            rel_type = rel.relationship_type.upper()
            target_id = str(rel.target_id)
            target_entity = entity_by_id.get(target_id)
            if not target_entity:
                continue
            valid_target_types = RELATIONSHIP_TARGET_CONSTRAINTS.get(rel_type)
            if not valid_target_types:
                continue
            target_type = target_entity.entity_type.upper() if target_entity.entity_type else "UNKNOWN"
            valid_types_upper = [t.upper() for t in valid_target_types]
            if target_type not in valid_types_upper:
                source_entity = entity_by_id.get(str(rel.source_id))
                source_name = source_entity.name if source_entity else "Unknown"
                result.gaps.append(ExtractionGap(
                    gap_type=GapType.INVALID_RELATIONSHIP_TARGET,
                    severity=GapSeverity.CRITICAL,
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
                    fix_confidence=0.0
                ))

        result.detection_time_ms = (time.time() - start) * 1000
        if result.gaps:
            logger.info(f"[GapDetector] Found {len(result.gaps)} gaps: "
                       f"{result.critical_count} critical, "
                       f"{result.warning_count} warning, "
                       f"{result.info_count} info")
        return result

    def _get_entities(self, document_id: Optional[str], include_trusted: bool) -> List[Entity]:
        """Get entities to analyze."""
        try:
            states = [LifecycleState.STAGING]
            if include_trusted:
                states.append(LifecycleState.TRUSTED)
            query = self.session.query(Entity).filter(Entity.lifecycle_state.in_(states))
            if self.tenant_id:
                query = query.filter(Entity.tenant_id == self.tenant_id)
            if document_id:
                query = query.filter(Entity.source_document_id == document_id)
            return query.all()
        except Exception as e:
            logger.error(f"[GapDetector] Failed to load entities: {e}")
            return []

    def _get_relationships(self, document_id: Optional[str], include_trusted: bool) -> List[Relationship]:
        """Get relationships to analyze."""
        try:
            states = [LifecycleState.STAGING]
            if include_trusted:
                states.append(LifecycleState.TRUSTED)
            query = self.session.query(Relationship).filter(Relationship.lifecycle_state.in_(states))
            if self.tenant_id:
                query = query.filter(Relationship.tenant_id == self.tenant_id)
            if document_id:
                query = query.filter(Relationship.source_document_id == document_id)
            return query.all()
        except Exception as e:
            logger.error(f"[GapDetector] Failed to load relationships: {e}")
            return []


RELATIONSHIP_TYPE_MAPPINGS = {
    "HELD_POSITION": "HOLDS_POSITION",
    "HOLD_POSITION": "HOLDS_POSITION",
    "HAS_POSITION": "HOLDS_POSITION",
    "HAS_ROLE": "HOLDS_POSITION",
    "IN_ROLE": "HOLDS_POSITION",
    "REPORTS_TO": "REPORTS_TO",
    "MANAGED_BY": "REPORTS_TO",
    "SUPERVISED_BY": "REPORTS_TO",
    "WORKS_AT": "EMPLOYED_BY",
    "WORKS_FOR": "EMPLOYED_BY",
    "MEMBER_OF": "EMPLOYED_BY",
    "MANAGES": "OWNS",
    "RESPONSIBLE_FOR": "OWNS",
}


def standardize_relationship_type(rel_type: str) -> str:
    """Standardize a relationship type to its canonical form."""
    rel_upper = rel_type.upper().strip()
    return RELATIONSHIP_TYPE_MAPPINGS.get(rel_upper, rel_upper)


def get_gap_detector(session: Session, tenant_id: Optional[str] = None) -> ExtractionGapDetector:
    """Get a configured gap detector instance."""
    return ExtractionGapDetector(session, tenant_id)


def detect_gaps_for_document(session: Session, document_id: str, tenant_id: Optional[str] = None) -> GapDetectionResult:
    """Convenience function to detect gaps for a specific document."""
    detector = ExtractionGapDetector(session, tenant_id)
    return detector.detect_all(document_id=document_id)


# =============================================================================
# Phase 3: Ontology Coverage Analysis
# =============================================================================

@dataclass
class OntologyCoverageReport:
    """Report of ontology coverage after extraction (Phase 3)."""

    # Counts
    total_entities: int = 0
    total_relationships: int = 0

    # Type distributions
    entity_type_counts: Dict[str, int] = field(default_factory=dict)
    relationship_type_counts: Dict[str, int] = field(default_factory=dict)

    # Coverage analysis
    ontology_entity_types: List[str] = field(default_factory=list)
    ontology_relationship_types: List[str] = field(default_factory=list)
    missing_entity_types: List[str] = field(default_factory=list)
    missing_relationship_types: List[str] = field(default_factory=list)
    unknown_entity_types: List[Dict] = field(default_factory=list)

    # Coverage percentages
    entity_coverage_pct: float = 0.0
    relationship_coverage_pct: float = 0.0

    # Orphan analysis
    orphan_entity_count: int = 0
    orphan_entities_sample: List[Dict] = field(default_factory=list)

    # Recommendations
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'total_entities': self.total_entities,
            'total_relationships': self.total_relationships,
            'entity_type_counts': self.entity_type_counts,
            'relationship_type_counts': self.relationship_type_counts,
            'ontology_entity_types': self.ontology_entity_types,
            'missing_entity_types': self.missing_entity_types,
            'missing_relationship_types': self.missing_relationship_types,
            'unknown_entity_types': self.unknown_entity_types,
            'entity_coverage_pct': round(self.entity_coverage_pct, 1),
            'relationship_coverage_pct': round(self.relationship_coverage_pct, 1),
            'orphan_entity_count': self.orphan_entity_count,
            'orphan_entities_sample': self.orphan_entities_sample[:10],
            'recommendations': self.recommendations,
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 60,
            "ONTOLOGY COVERAGE REPORT (Phase 3)",
            "=" * 60,
            f"Entities: {self.total_entities} ({len(self.entity_type_counts)} types)",
            f"Relationships: {self.total_relationships} ({len(self.relationship_type_counts)} types)",
            f"Entity Coverage: {self.entity_coverage_pct:.1f}%",
            f"Relationship Coverage: {self.relationship_coverage_pct:.1f}%",
            f"Orphan Entities: {self.orphan_entity_count}",
            "",
        ]

        if self.missing_entity_types:
            lines.append(f"Missing Entity Types ({len(self.missing_entity_types)}):")
            for t in self.missing_entity_types[:10]:
                lines.append(f"  - {t}")
            if len(self.missing_entity_types) > 10:
                lines.append(f"  ... and {len(self.missing_entity_types) - 10} more")
            lines.append("")

        if self.unknown_entity_types:
            lines.append(f"Unknown Entity Types ({len(self.unknown_entity_types)}):")
            for t in self.unknown_entity_types[:5]:
                lines.append(f"  - {t.get('type', 'unknown')}: {t.get('count', 0)} entities")
            lines.append("")

        if self.recommendations:
            lines.append("Recommendations:")
            for r in self.recommendations:
                lines.append(f"  → {r}")

        lines.append("=" * 60)
        return "\n".join(lines)


class OntologyCoverageAnalyzer:
    """
    Analyzes extraction coverage against ontology schema (Phase 3).

    This complements ExtractionGapDetector by focusing on:
    - Which ontology types have instances
    - Which ontology types are missing
    - Unknown types that may need to be added to ontology
    """

    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self._ontology_entity_types: Optional[Set[str]] = None
        self._ontology_relationship_types: Optional[Set[str]] = None

    @property
    def ontology_entity_types(self) -> Set[str]:
        """Load ACTIVE entity types from ontology."""
        if self._ontology_entity_types is None:
            try:
                result = self.session.execute(text("""
                    SELECT UPPER(type_name) as type_name
                    FROM ontology.types
                    WHERE status = 'ACTIVE'
                      AND layer >= 1
                """))
                self._ontology_entity_types = {row.type_name for row in result}
            except Exception as e:
                logger.warning(f"[OntologyCoverage] Could not load ontology types: {e}")
                self._ontology_entity_types = set()
        return self._ontology_entity_types

    @property
    def ontology_relationship_types(self) -> Set[str]:
        """Load ACTIVE relationship types from ontology."""
        if self._ontology_relationship_types is None:
            try:
                result = self.session.execute(text("""
                    SELECT UPPER(relation_type) as relation_type
                    FROM ontology.relations
                    WHERE status = 'ACTIVE'
                """))
                self._ontology_relationship_types = {row.relation_type for row in result}
            except Exception as e:
                logger.warning(f"[OntologyCoverage] Could not load ontology relations: {e}")
                self._ontology_relationship_types = set()
        return self._ontology_relationship_types

    def analyze(self) -> OntologyCoverageReport:
        """Analyze ontology coverage for the tenant/vault."""
        report = OntologyCoverageReport()

        # Get entity statistics
        entity_result = self.session.execute(text("""
            SELECT UPPER(entity_type) as entity_type, COUNT(*) as count
            FROM entities
            WHERE tenant_id = :tenant_id
              AND lifecycle_state IN ('STAGING', 'TRUSTED')
            GROUP BY UPPER(entity_type)
            ORDER BY count DESC
        """), {'tenant_id': self.tenant_id})

        for row in entity_result:
            report.entity_type_counts[row.entity_type] = row.count
            report.total_entities += row.count

        # Get relationship statistics
        rel_result = self.session.execute(text("""
            SELECT UPPER(relationship_type) as relationship_type, COUNT(*) as count
            FROM relationships
            WHERE tenant_id = :tenant_id
              AND lifecycle_state IN ('STAGING', 'TRUSTED')
            GROUP BY UPPER(relationship_type)
            ORDER BY count DESC
        """), {'tenant_id': self.tenant_id})

        for row in rel_result:
            report.relationship_type_counts[row.relationship_type] = row.count
            report.total_relationships += row.count

        # Analyze ontology coverage
        report.ontology_entity_types = sorted(self.ontology_entity_types)
        report.ontology_relationship_types = sorted(self.ontology_relationship_types)

        extracted_entity_types = set(report.entity_type_counts.keys())
        extracted_rel_types = set(report.relationship_type_counts.keys())

        # Missing types (in ontology but not extracted)
        report.missing_entity_types = sorted(self.ontology_entity_types - extracted_entity_types)
        report.missing_relationship_types = sorted(self.ontology_relationship_types - extracted_rel_types)

        # Unknown types (extracted but not in ontology)
        unknown = extracted_entity_types - self.ontology_entity_types - {'SPECIFICATION'}
        report.unknown_entity_types = [
            {'type': t, 'count': report.entity_type_counts.get(t, 0)}
            for t in sorted(unknown, key=lambda x: -report.entity_type_counts.get(x, 0))
        ]

        # Coverage percentages
        if self.ontology_entity_types:
            covered = len(extracted_entity_types & self.ontology_entity_types)
            report.entity_coverage_pct = (covered / len(self.ontology_entity_types)) * 100
        if self.ontology_relationship_types:
            covered = len(extracted_rel_types & self.ontology_relationship_types)
            report.relationship_coverage_pct = (covered / len(self.ontology_relationship_types)) * 100

        # Find orphan entities
        orphan_result = self.session.execute(text("""
            SELECT COUNT(*) as count
            FROM entities e
            WHERE e.tenant_id = :tenant_id
              AND e.lifecycle_state IN ('STAGING', 'TRUSTED')
              AND NOT EXISTS (
                  SELECT 1 FROM relationships r
                  WHERE r.tenant_id = :tenant_id
                    AND (r.source_entity_id = e.id OR r.target_entity_id = e.id)
              )
        """), {'tenant_id': self.tenant_id})
        row = orphan_result.fetchone()
        report.orphan_entity_count = row.count if row else 0

        # Sample orphan entities
        if report.orphan_entity_count > 0:
            sample_result = self.session.execute(text("""
                SELECT e.canonical_name, e.entity_type
                FROM entities e
                WHERE e.tenant_id = :tenant_id
                  AND e.lifecycle_state IN ('STAGING', 'TRUSTED')
                  AND NOT EXISTS (
                      SELECT 1 FROM relationships r
                      WHERE r.tenant_id = :tenant_id
                        AND (r.source_entity_id = e.id OR r.target_entity_id = e.id)
                  )
                LIMIT 10
            """), {'tenant_id': self.tenant_id})
            report.orphan_entities_sample = [
                {'name': row.canonical_name, 'type': row.entity_type}
                for row in sample_result
            ]

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        logger.info(f"[OntologyCoverage] Analysis complete: "
                   f"{report.entity_coverage_pct:.1f}% entity coverage, "
                   f"{report.relationship_coverage_pct:.1f}% relationship coverage")

        return report

    def _generate_recommendations(self, report: OntologyCoverageReport) -> List[str]:
        """Generate actionable recommendations."""
        recs = []

        if report.entity_coverage_pct < 50:
            recs.append(f"Entity coverage is low ({report.entity_coverage_pct:.0f}%). "
                       f"Check if source documents contain expected entity types.")

        if report.orphan_entity_count > report.total_entities * 0.3:
            pct = (report.orphan_entity_count / max(1, report.total_entities)) * 100
            recs.append(f"{report.orphan_entity_count} orphan entities ({pct:.0f}%). "
                       f"Improve relationship extraction patterns.")

        key_types = {'PERSON', 'ORGANIZATION', 'SERVICE'}
        missing_key = key_types & set(report.missing_entity_types)
        if missing_key:
            recs.append(f"Key entity types missing: {', '.join(missing_key)}.")

        if report.unknown_entity_types:
            high_count_unknown = [t for t in report.unknown_entity_types if t['count'] >= 5]
            if high_count_unknown:
                types_str = ', '.join(t['type'] for t in high_count_unknown[:3])
                recs.append(f"Consider adding to ontology: {types_str}")

        if report.total_entities > 0:
            density = report.total_relationships / report.total_entities
            if density < 0.5:
                recs.append(f"Relationship density is low ({density:.2f} per entity). "
                           f"Expected at least 0.5.")

        return recs


def analyze_ontology_coverage(
    session: Session,
    tenant_id: str
) -> OntologyCoverageReport:
    """
    Convenience function to analyze ontology coverage for a vault (Phase 3).

    Args:
        session: Database session
        tenant_id: The vault/tenant to analyze

    Returns:
        OntologyCoverageReport with detailed analysis
    """
    analyzer = OntologyCoverageAnalyzer(session, tenant_id)
    return analyzer.analyze()
