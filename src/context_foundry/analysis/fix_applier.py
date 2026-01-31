"""
Fix Applier for Context Foundry.

Takes targeted extraction results and applies them to the knowledge graph.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker, Session

from ..models.schema import Entity, Relationship, LifecycleState, ValidationStatus

logger = logging.getLogger(__name__)


@dataclass
class FixResult:
    """Result of a fix operation."""
    category: str
    entities_created: int = 0
    entities_updated: int = 0
    relationships_created: int = 0
    relationships_updated: int = 0
    properties_added: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    applied_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "entities_created": self.entities_created,
            "entities_updated": self.entities_updated,
            "relationships_created": self.relationships_created,
            "relationships_updated": self.relationships_updated,
            "properties_added": self.properties_added,
            "errors": self.errors,
            "warnings": self.warnings,
            "applied_at": self.applied_at.isoformat()
        }


class FixApplier:
    """
    Applies fixes from targeted extraction to the knowledge graph.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.tenant_id = self.config.get("tenant_id")
        
        self._session: Optional[Session] = None
        self._init_db()

    def _init_db(self):
        """Initialize database connection."""
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            try:
                engine = create_engine(database_url)
                Session = sessionmaker(bind=engine)
                self._session = Session()
                logger.info("Database connection initialized for FixApplier")
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                self._session = None

    def apply_all(self, category: str, extractions: List[Dict]) -> FixResult:
        """
        Apply all extractions for a given category.

        Args:
            category: The extraction category
            extractions: List of extraction results

        Returns:
            FixResult with counts and any errors
        """
        result = FixResult(category=category)

        if not self._session:
            result.errors.append("No database connection available")
            return result

        handler = self._get_handler(category)
        if not handler:
            result.errors.append(f"No handler for category: {category}")
            return result

        for extraction in extractions:
            try:
                handler(extraction, result)
            except Exception as e:
                result.errors.append(f"Error applying extraction: {e}")
                logger.error(f"Fix application error: {e}")

        try:
            self._session.commit()
            logger.info(f"Committed fixes for {category}")
        except Exception as e:
            self._session.rollback()
            result.errors.append(f"Failed to commit: {e}")
            logger.error(f"Commit failed: {e}")

        return result

    def _get_handler(self, category: str):
        """Get the appropriate handler for a category."""
        handlers = {
            "PERSON_RESPONSIBILITIES": self._apply_person_responsibilities,
            "PROJECT_OWNERSHIP": self._apply_project_ownership,
            "BU_FOCUS_AREAS": self._apply_bu_focus_areas,
            "CUSTOMER_RELATIONSHIPS": self._apply_customer_relationships,
            "SUPPLIER_RELATIONSHIPS": self._apply_supplier_relationships,
            "PARTNER_RELATIONSHIPS": self._apply_partner_relationships,
            "PROJECT_BUDGETS": self._apply_project_budgets,
            "PROJECT_INFO": self._apply_project_info,
            "PERSON_INFO": self._apply_person_info,
        }
        return handlers.get(category)

    def _apply_person_responsibilities(self, extraction: Dict, result: FixResult):
        """Apply person responsibilities as entity properties."""
        people = extraction.get("people", [])
        source_doc = extraction.get("_source_document", "targeted_extraction")

        for person_data in people:
            name = person_data.get("name")
            title = person_data.get("title")
            responsibilities = person_data.get("responsibilities", [])

            if not name:
                continue

            entity = self._find_or_create_entity(
                name=name,
                entity_type="PERSON",
                source_doc=source_doc,
                result=result
            )

            if entity:
                props = entity.properties or {}
                if title:
                    props["title"] = title
                if responsibilities:
                    existing_resp = props.get("responsibilities", [])
                    if isinstance(existing_resp, str):
                        existing_resp = [existing_resp]
                    combined = list(set(existing_resp + responsibilities))
                    props["responsibilities"] = combined
                    result.properties_added += len(responsibilities)
                
                entity.properties = props
                entity.updated_at = datetime.utcnow()

    def _apply_project_ownership(self, extraction: Dict, result: FixResult):
        """Apply project ownership as OWNS relationships."""
        ownership = extraction.get("ownership", [])
        source_doc = extraction.get("_source_document", "targeted_extraction")

        for item in ownership:
            project_name = item.get("project")
            bu_name = item.get("business_unit")

            if not project_name or not bu_name:
                continue

            project_entity = self._find_or_create_entity(
                name=project_name,
                entity_type="PROJECT",
                source_doc=source_doc,
                result=result
            )

            bu_entity = self._find_or_create_entity(
                name=bu_name,
                entity_type="BUSINESS_UNIT",
                source_doc=source_doc,
                result=result
            )

            if project_entity and bu_entity:
                self._create_relationship(
                    source=bu_entity,
                    target=project_entity,
                    rel_type="OWNS",
                    source_doc=source_doc,
                    evidence=item.get("evidence"),
                    result=result
                )

    def _apply_bu_focus_areas(self, extraction: Dict, result: FixResult):
        """Apply business unit focus areas as FOCUSES_ON relationships."""
        focus_data = extraction.get("focus_areas", [])
        source_doc = extraction.get("_source_document", "targeted_extraction")

        for item in focus_data:
            bu_name = item.get("business_unit")
            areas = item.get("focus_areas", [])

            if not bu_name or not areas:
                continue

            bu_entity = self._find_or_create_entity(
                name=bu_name,
                entity_type="BUSINESS_UNIT",
                source_doc=source_doc,
                result=result
            )

            if bu_entity:
                props = bu_entity.properties or {}
                existing_focus = props.get("focus_areas", [])
                if isinstance(existing_focus, str):
                    existing_focus = [existing_focus]
                combined = list(set(existing_focus + areas))
                props["focus_areas"] = combined
                bu_entity.properties = props
                result.properties_added += len(areas)

                for area in areas:
                    concept_entity = self._find_or_create_entity(
                        name=area,
                        entity_type="CONCEPT",
                        source_doc=source_doc,
                        result=result
                    )

                    if concept_entity:
                        self._create_relationship(
                            source=bu_entity,
                            target=concept_entity,
                            rel_type="FOCUSES_ON",
                            source_doc=source_doc,
                            result=result
                        )

    def _apply_customer_relationships(self, extraction: Dict, result: FixResult):
        """Apply customer relationships."""
        customers = extraction.get("customers", [])
        source_doc = extraction.get("_source_document", "targeted_extraction")

        for item in customers:
            customer_name = item.get("customer_name")
            supplier = item.get("supplier", "Manus Orion Group")

            if not customer_name:
                continue

            customer_entity = self._find_or_create_entity(
                name=customer_name,
                entity_type="CUSTOMER",
                source_doc=source_doc,
                result=result
            )

            supplier_entity = self._find_or_create_entity(
                name=supplier,
                entity_type="ORGANIZATION",
                source_doc=source_doc,
                result=result
            )

            if customer_entity and supplier_entity:
                self._create_relationship(
                    source=customer_entity,
                    target=supplier_entity,
                    rel_type="CUSTOMER_OF",
                    source_doc=source_doc,
                    properties={
                        "product_or_service": item.get("product_or_service"),
                        "contract_value": item.get("contract_value")
                    },
                    evidence=item.get("evidence"),
                    result=result
                )

    def _apply_supplier_relationships(self, extraction: Dict, result: FixResult):
        """Apply supplier relationships."""
        suppliers = extraction.get("suppliers", [])
        source_doc = extraction.get("_source_document", "targeted_extraction")

        for item in suppliers:
            supplier_name = item.get("supplier_name")
            customer = item.get("customer", "Manus Orion Group")

            if not supplier_name:
                continue

            supplier_entity = self._find_or_create_entity(
                name=supplier_name,
                entity_type="SUPPLIER",
                source_doc=source_doc,
                result=result
            )

            customer_entity = self._find_or_create_entity(
                name=customer,
                entity_type="ORGANIZATION",
                source_doc=source_doc,
                result=result
            )

            if supplier_entity and customer_entity:
                self._create_relationship(
                    source=supplier_entity,
                    target=customer_entity,
                    rel_type="SUPPLIER_OF",
                    source_doc=source_doc,
                    properties={
                        "what_they_supply": item.get("what_they_supply"),
                        "risk_level": item.get("risk_level")
                    },
                    evidence=item.get("evidence"),
                    result=result
                )

    def _apply_partner_relationships(self, extraction: Dict, result: FixResult):
        """Apply partner relationships."""
        partners = extraction.get("partners", [])
        source_doc = extraction.get("_source_document", "targeted_extraction")

        for item in partners:
            partner_name = item.get("partner_name")

            if not partner_name:
                continue

            partner_entity = self._find_or_create_entity(
                name=partner_name,
                entity_type="PARTNER",
                source_doc=source_doc,
                result=result
            )

            org_entity = self._find_or_create_entity(
                name="Manus Orion Group",
                entity_type="ORGANIZATION",
                source_doc=source_doc,
                result=result
            )

            if partner_entity and org_entity:
                self._create_relationship(
                    source=partner_entity,
                    target=org_entity,
                    rel_type="PARTNER_OF",
                    source_doc=source_doc,
                    properties={
                        "partnership_type": item.get("partnership_type"),
                        "scope": item.get("scope")
                    },
                    evidence=item.get("evidence"),
                    result=result
                )

    def _apply_project_budgets(self, extraction: Dict, result: FixResult):
        """Apply project budget information."""
        budgets = extraction.get("budgets", [])
        source_doc = extraction.get("_source_document", "targeted_extraction")

        for item in budgets:
            project_name = item.get("project")
            budget = item.get("budget")

            if not project_name or not budget:
                continue

            project_entity = self._find_or_create_entity(
                name=project_name,
                entity_type="PROJECT",
                source_doc=source_doc,
                result=result
            )

            if project_entity:
                props = project_entity.properties or {}
                props["budget"] = budget
                props["budget_type"] = item.get("budget_type", "total")
                if item.get("fiscal_year"):
                    props["fiscal_year"] = item.get("fiscal_year")
                project_entity.properties = props
                result.properties_added += 1

    def _apply_project_info(self, extraction: Dict, result: FixResult):
        """Apply general project information."""
        projects = extraction.get("projects", [])
        source_doc = extraction.get("_source_document", "targeted_extraction")

        for item in projects:
            name = item.get("name")
            if not name:
                continue

            entity = self._find_or_create_entity(
                name=name,
                entity_type="PROJECT",
                source_doc=source_doc,
                result=result
            )

            if entity:
                props = entity.properties or {}
                for key in ["status", "start_date", "end_date", "objectives", "budget"]:
                    if item.get(key):
                        props[key] = item.get(key)
                        result.properties_added += 1
                entity.properties = props

    def _apply_person_info(self, extraction: Dict, result: FixResult):
        """Apply general person information."""
        people = extraction.get("people", [])
        source_doc = extraction.get("_source_document", "targeted_extraction")

        for item in people:
            name = item.get("name")
            if not name:
                continue

            entity = self._find_or_create_entity(
                name=name,
                entity_type="PERSON",
                source_doc=source_doc,
                result=result
            )

            if entity:
                props = entity.properties or {}
                for key in ["title", "department", "responsibilities", "background"]:
                    if item.get(key):
                        props[key] = item.get(key)
                        result.properties_added += 1
                entity.properties = props

                if item.get("reports_to"):
                    manager = self._find_or_create_entity(
                        name=item.get("reports_to"),
                        entity_type="PERSON",
                        source_doc=source_doc,
                        result=result
                    )
                    if manager:
                        self._create_relationship(
                            source=entity,
                            target=manager,
                            rel_type="REPORTS_TO",
                            source_doc=source_doc,
                            result=result
                        )

    def _find_or_create_entity(
        self,
        name: str,
        entity_type: str,
        source_doc: str,
        result: FixResult
    ) -> Optional[Entity]:
        """Find an existing entity or create a new one."""
        if not self._session:
            return None

        query = self._session.query(Entity).filter(
            Entity.name == name,
            Entity.entity_type == entity_type
        )
        if self.tenant_id:
            query = query.filter(Entity.tenant_id == self.tenant_id)

        existing = query.first()

        if existing:
            return existing

        new_entity = Entity(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            name=name,
            entity_type=entity_type,
            lifecycle_state=LifecycleState.STAGING,
            validation_status=ValidationStatus.VALID,
            properties={},
            confidence=0.8,
            source_document_id=source_doc,
            extraction_method="targeted_extraction",
            extracted_at=datetime.utcnow()
        )
        self._session.add(new_entity)
        self._session.flush()
        result.entities_created += 1

        return new_entity

    def _create_relationship(
        self,
        source: Entity,
        target: Entity,
        rel_type: str,
        source_doc: str,
        result: FixResult,
        properties: Optional[Dict] = None,
        evidence: Optional[str] = None
    ) -> Optional[Relationship]:
        """Create a relationship if it doesn't exist."""
        if not self._session:
            return None

        query = self._session.query(Relationship).filter(
            Relationship.source_id == source.id,
            Relationship.target_id == target.id,
            Relationship.relationship_type == rel_type
        )
        if self.tenant_id:
            query = query.filter(Relationship.tenant_id == self.tenant_id)

        existing = query.first()

        if existing:
            if properties:
                existing_props = existing.properties or {}
                existing_props.update({k: v for k, v in properties.items() if v})
                existing.properties = existing_props
                result.relationships_updated += 1
            return existing

        rel_props = properties or {}
        if evidence:
            rel_props["evidence"] = evidence

        new_rel = Relationship(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            source_id=source.id,
            target_id=target.id,
            relationship_type=rel_type,
            lifecycle_state=LifecycleState.STAGING,
            validation_status=ValidationStatus.VALID,
            properties=rel_props,
            confidence=0.8,
            source_document_id=source_doc,
            extracted_at=datetime.utcnow()
        )
        self._session.add(new_rel)
        self._session.flush()
        result.relationships_created += 1

        return new_rel

    def close(self):
        """Close the database session."""
        if self._session:
            self._session.close()
