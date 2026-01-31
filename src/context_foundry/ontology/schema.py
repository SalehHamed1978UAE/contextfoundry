"""
Ontology Schema for Context Foundry Knowledge Graph

This module defines the canonical entity and relationship types for the knowledge graph.
All extraction and ingestion must conform to these definitions.

Guardrail: No hardcoded business facts. Only schema definitions.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime


class EntityType(str, Enum):
    """Canonical entity types for the knowledge graph."""
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    BUSINESS_UNIT = "BUSINESS_UNIT"
    PROJECT = "PROJECT"
    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"
    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"
    PARTNER = "PARTNER"
    FINANCIAL_METRIC = "FINANCIAL_METRIC"
    LOCATION = "LOCATION"
    DOCUMENT = "DOCUMENT"
    POLICY = "POLICY"
    FACILITY = "FACILITY"
    TECHNOLOGY = "TECHNOLOGY"
    CONCEPT = "CONCEPT"


class RelationshipType(str, Enum):
    """Canonical relationship types for the knowledge graph."""
    OWNS = "OWNS"
    OWNED_BY = "OWNED_BY"
    FOCUSES_ON = "FOCUSES_ON"
    CUSTOMER_OF = "CUSTOMER_OF"
    SUPPLIER_OF = "SUPPLIER_OF"
    PARTNER_OF = "PARTNER_OF"
    LEADS = "LEADS"
    MANAGES = "MANAGES"
    WORKS_FOR = "WORKS_FOR"
    WORKS_AT = "WORKS_AT"
    REPORTS_TO = "REPORTS_TO"
    FUNDED_BY = "FUNDED_BY"
    DEPENDS_ON = "DEPENDS_ON"
    RELATED_TO = "RELATED_TO"
    MENTIONED_IN = "MENTIONED_IN"
    HAS_ROLE = "HAS_ROLE"
    HOLDS_POSITION = "HOLDS_POSITION"
    LOCATED_AT = "LOCATED_AT"
    PRODUCES = "PRODUCES"
    USES = "USES"
    PART_OF = "PART_OF"
    PROVIDES = "PROVIDES"
    REQUIRES = "REQUIRES"


class ValueType(str, Enum):
    """Types for financial metric values."""
    CURRENCY = "CURRENCY"
    PERCENTAGE = "PERCENTAGE"
    COUNT = "COUNT"
    RATIO = "RATIO"
    DURATION = "DURATION"


class EntityProperties(BaseModel):
    """Base properties common to all entities."""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Extraction confidence score")
    source_document: Optional[str] = Field(default=None, description="Source document ID")
    source_model: Optional[str] = Field(default=None, description="Model that extracted this entity")
    extracted_at: Optional[datetime] = Field(default=None, description="Extraction timestamp")
    aliases: List[str] = Field(default_factory=list, description="Known aliases for this entity")


class PersonProperties(EntityProperties):
    """Properties specific to PERSON entities."""
    name: str
    title: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class OrganizationProperties(EntityProperties):
    """Properties specific to ORGANIZATION entities."""
    name: str
    org_type: Optional[str] = None
    industry: Optional[str] = None
    headquarters: Optional[str] = None
    founded: Optional[str] = None


class BusinessUnitProperties(EntityProperties):
    """Properties specific to BUSINESS_UNIT entities."""
    name: str
    focus_areas: List[str] = Field(default_factory=list)
    industries: List[str] = Field(default_factory=list)
    parent_org: Optional[str] = None


class ProjectProperties(EntityProperties):
    """Properties specific to PROJECT entities."""
    name: str
    budget: Optional[str] = None
    budget_value: Optional[float] = None
    timeline: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    owner: Optional[str] = None


class ProductProperties(EntityProperties):
    """Properties specific to PRODUCT/SERVICE entities."""
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    market_share: Optional[str] = None
    revenue: Optional[str] = None


class CustomerProperties(EntityProperties):
    """Properties specific to CUSTOMER entities."""
    name: str
    industry: Optional[str] = None
    region: Optional[str] = None
    contract_value: Optional[str] = None
    relationship_status: Optional[str] = None


class SupplierProperties(EntityProperties):
    """Properties specific to SUPPLIER/PARTNER entities."""
    name: str
    capability: Optional[str] = None
    risk_level: Optional[str] = None
    category: Optional[str] = None
    contract_type: Optional[str] = None


class FinancialMetricProperties(EntityProperties):
    """Properties specific to FINANCIAL_METRIC entities."""
    metric_name: str
    value: str
    value_type: ValueType = ValueType.CURRENCY
    period: Optional[str] = None
    fiscal_year: Optional[str] = None
    unit: Optional[str] = None


class LocationProperties(EntityProperties):
    """Properties specific to LOCATION entities."""
    name: str
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    facility_type: Optional[str] = None


class FacilityProperties(EntityProperties):
    """Properties specific to FACILITY entities."""
    name: str
    location: Optional[str] = None
    facility_type: Optional[str] = None
    capacity: Optional[str] = None
    function: Optional[str] = None


class PolicyProperties(EntityProperties):
    """Properties specific to POLICY entities."""
    name: str
    policy_id: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    effective_date: Optional[str] = None


ENTITY_PROPERTY_MAP = {
    EntityType.PERSON: PersonProperties,
    EntityType.ORGANIZATION: OrganizationProperties,
    EntityType.BUSINESS_UNIT: BusinessUnitProperties,
    EntityType.PROJECT: ProjectProperties,
    EntityType.PRODUCT: ProductProperties,
    EntityType.SERVICE: ProductProperties,
    EntityType.CUSTOMER: CustomerProperties,
    EntityType.SUPPLIER: SupplierProperties,
    EntityType.PARTNER: SupplierProperties,
    EntityType.FINANCIAL_METRIC: FinancialMetricProperties,
    EntityType.LOCATION: LocationProperties,
    EntityType.FACILITY: FacilityProperties,
    EntityType.POLICY: PolicyProperties,
}


class ExtractedEntity(BaseModel):
    """An entity extracted from a document."""
    name: str = Field(description="Primary name of the entity")
    entity_type: EntityType = Field(description="Type from EntityType enum")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Entity-specific properties")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Extraction confidence")
    source_document: Optional[str] = Field(default=None, description="Source document path/ID")
    source_excerpt: Optional[str] = Field(default=None, description="Text excerpt supporting extraction")
    aliases: List[str] = Field(default_factory=list, description="Alternate names/spellings")

    class Config:
        use_enum_values = True


class ExtractedRelationship(BaseModel):
    """A relationship extracted from a document."""
    source_entity: str = Field(description="Name of the source entity")
    source_type: EntityType = Field(description="Type of the source entity")
    relationship_type: RelationshipType = Field(description="Type from RelationshipType enum")
    target_entity: str = Field(description="Name of the target entity")
    target_type: EntityType = Field(description="Type of the target entity")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Relationship properties")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Extraction confidence")
    source_document: Optional[str] = Field(default=None, description="Source document path/ID")
    evidence: Optional[str] = Field(default=None, description="Text excerpt supporting relationship")

    class Config:
        use_enum_values = True


class ExtractionOutput(BaseModel):
    """Complete extraction output from a single model pass."""
    document_id: str = Field(description="Unique identifier for the source document")
    document_path: Optional[str] = Field(default=None, description="Path to the source document")
    model_name: str = Field(description="Name of the model that performed extraction")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    entities: List[ExtractedEntity] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional extraction metadata")

    class Config:
        use_enum_values = True


VALID_RELATIONSHIP_SOURCES = {
    RelationshipType.OWNS: [EntityType.ORGANIZATION, EntityType.BUSINESS_UNIT, EntityType.PERSON],
    RelationshipType.OWNED_BY: [EntityType.PROJECT, EntityType.BUSINESS_UNIT, EntityType.ORGANIZATION],
    RelationshipType.LEADS: [EntityType.PERSON],
    RelationshipType.MANAGES: [EntityType.PERSON],
    RelationshipType.WORKS_FOR: [EntityType.PERSON],
    RelationshipType.WORKS_AT: [EntityType.PERSON],
    RelationshipType.REPORTS_TO: [EntityType.PERSON],
    RelationshipType.CUSTOMER_OF: [EntityType.CUSTOMER, EntityType.ORGANIZATION],
    RelationshipType.SUPPLIER_OF: [EntityType.SUPPLIER, EntityType.ORGANIZATION],
    RelationshipType.PARTNER_OF: [EntityType.PARTNER, EntityType.ORGANIZATION],
    RelationshipType.FUNDED_BY: [EntityType.PROJECT],
    RelationshipType.LOCATED_AT: [EntityType.ORGANIZATION, EntityType.FACILITY, EntityType.PROJECT],
    RelationshipType.PRODUCES: [EntityType.ORGANIZATION, EntityType.BUSINESS_UNIT, EntityType.FACILITY],
    RelationshipType.USES: [EntityType.PROJECT, EntityType.ORGANIZATION],
    RelationshipType.PART_OF: [EntityType.BUSINESS_UNIT, EntityType.PERSON, EntityType.PROJECT],
}

VALID_RELATIONSHIP_TARGETS = {
    RelationshipType.OWNS: [EntityType.PROJECT, EntityType.BUSINESS_UNIT, EntityType.ORGANIZATION],
    RelationshipType.OWNED_BY: [EntityType.ORGANIZATION, EntityType.BUSINESS_UNIT],
    RelationshipType.LEADS: [EntityType.ORGANIZATION, EntityType.BUSINESS_UNIT, EntityType.PROJECT],
    RelationshipType.MANAGES: [EntityType.PROJECT, EntityType.BUSINESS_UNIT, EntityType.FACILITY],
    RelationshipType.WORKS_FOR: [EntityType.ORGANIZATION, EntityType.BUSINESS_UNIT],
    RelationshipType.WORKS_AT: [EntityType.ORGANIZATION, EntityType.FACILITY, EntityType.LOCATION],
    RelationshipType.REPORTS_TO: [EntityType.PERSON],
    RelationshipType.CUSTOMER_OF: [EntityType.ORGANIZATION],
    RelationshipType.SUPPLIER_OF: [EntityType.ORGANIZATION, EntityType.PROJECT],
    RelationshipType.PARTNER_OF: [EntityType.ORGANIZATION, EntityType.PROJECT],
    RelationshipType.FUNDED_BY: [EntityType.ORGANIZATION],
    RelationshipType.LOCATED_AT: [EntityType.LOCATION, EntityType.FACILITY],
    RelationshipType.PRODUCES: [EntityType.PRODUCT, EntityType.SERVICE],
    RelationshipType.USES: [EntityType.TECHNOLOGY, EntityType.PRODUCT, EntityType.SERVICE],
    RelationshipType.PART_OF: [EntityType.ORGANIZATION, EntityType.BUSINESS_UNIT],
}
