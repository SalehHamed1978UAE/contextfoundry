"""
Ontology Manager for Context Foundry.

Manages per-tenant, per-document-type ontologies that grow organically
from document processing.
"""
import os
import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from sqlalchemy import text
from openai import OpenAI

from ..utils.logger import logger


@dataclass
class EntityTypeSchema:
    name: str
    definition: str
    
    def to_dict(self) -> Dict:
        return {"name": self.name, "definition": self.definition}


@dataclass
class RelationshipTypeSchema:
    name: str
    definition: str
    source_types: List[str] = field(default_factory=list)
    target_types: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "definition": self.definition,
            "source_types": self.source_types,
            "target_types": self.target_types
        }


@dataclass
class ReferenceOntology:
    id: Optional[str]
    tenant_id: str
    document_type: str
    entity_types: List[EntityTypeSchema]
    relationship_types: List[RelationshipTypeSchema]
    usage_count: int = 1
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "document_type": self.document_type,
            "entity_types": [et.to_dict() for et in self.entity_types],
            "relationship_types": [rt.to_dict() for rt in self.relationship_types],
            "usage_count": self.usage_count
        }


DEFAULT_ONTOLOGIES = {
    "resume": ReferenceOntology(
        id=None,
        tenant_id="",
        document_type="resume",
        entity_types=[
            EntityTypeSchema("PERSON", "A human individual, typically the resume subject or a reference"),
            EntityTypeSchema("ORGANIZATION", "A company, university, or institution"),
            EntityTypeSchema("SKILL", "A technical or professional capability"),
            EntityTypeSchema("CERTIFICATION", "A professional certification or license"),
            EntityTypeSchema("DEGREE", "An educational degree or qualification"),
            EntityTypeSchema("LOCATION", "A city, country, or region"),
            EntityTypeSchema("DATE", "A date or time period"),
            EntityTypeSchema("PROJECT", "A work project or initiative"),
            EntityTypeSchema("JOB_TITLE", "A professional role or position"),
        ],
        relationship_types=[
            RelationshipTypeSchema("WORKED_AT", "Employment relationship between person and organization", ["PERSON"], ["ORGANIZATION"]),
            RelationshipTypeSchema("EDUCATED_AT", "Educational relationship between person and institution", ["PERSON"], ["ORGANIZATION"]),
            RelationshipTypeSchema("HAS_SKILL", "Person possesses a skill or competency", ["PERSON"], ["SKILL"]),
            RelationshipTypeSchema("HOLDS_CERTIFICATION", "Person holds a professional certification", ["PERSON"], ["CERTIFICATION"]),
            RelationshipTypeSchema("HAS_DEGREE", "Person holds an educational degree", ["PERSON"], ["DEGREE"]),
            RelationshipTypeSchema("LOCATED_IN", "Entity is located in a place", ["ORGANIZATION", "PERSON"], ["LOCATION"]),
            RelationshipTypeSchema("HOLDS_POSITION", "Person holds a job title at an organization", ["PERSON"], ["JOB_TITLE", "ROLE"]),
            RelationshipTypeSchema("WORKED_ON", "Person worked on a project", ["PERSON"], ["PROJECT"]),
        ]
    ),
    "incident_report": ReferenceOntology(
        id=None,
        tenant_id="",
        document_type="incident_report",
        entity_types=[
            EntityTypeSchema("INCIDENT", "A service disruption or outage event"),
            EntityTypeSchema("SERVICE", "A software service or system component"),
            EntityTypeSchema("PERSON", "A team member or on-call responder"),
            EntityTypeSchema("TEAM", "A group of people responsible for a service"),
            EntityTypeSchema("ROOT_CAUSE", "The underlying cause of an incident"),
            EntityTypeSchema("ACTION_ITEM", "A follow-up task or remediation item"),
            EntityTypeSchema("METRIC", "A measurement or indicator"),
            EntityTypeSchema("TIME_PERIOD", "A duration or timestamp"),
        ],
        relationship_types=[
            RelationshipTypeSchema("AFFECTED", "Incident affected a service", ["INCIDENT"], ["SERVICE"]),
            RelationshipTypeSchema("CAUSED_BY", "Incident was caused by a root cause", ["INCIDENT"], ["ROOT_CAUSE"]),
            RelationshipTypeSchema("RESPONDED_TO", "Person responded to an incident", ["PERSON"], ["INCIDENT"]),
            RelationshipTypeSchema("OWNS", "Team owns a service", ["TEAM"], ["SERVICE"]),
            RelationshipTypeSchema("DEPENDS_ON", "Service depends on another service", ["SERVICE"], ["SERVICE"]),
            RelationshipTypeSchema("RESULTED_IN", "Incident resulted in an action item", ["INCIDENT"], ["ACTION_ITEM"]),
            RelationshipTypeSchema("ASSIGNED_TO", "Action item assigned to a person", ["ACTION_ITEM"], ["PERSON"]),
        ]
    ),
    "it_infrastructure": ReferenceOntology(
        id=None,
        tenant_id="",
        document_type="it_infrastructure",
        entity_types=[
            EntityTypeSchema("SERVICE", "A software service or application"),
            EntityTypeSchema("SERVER", "A physical or virtual server"),
            EntityTypeSchema("DATABASE", "A database system"),
            EntityTypeSchema("NETWORK", "A network segment or component"),
            EntityTypeSchema("TEAM", "An operational team"),
            EntityTypeSchema("CONFIGURATION", "A configuration setting or parameter"),
            EntityTypeSchema("PROCESS", "A business or technical process"),
        ],
        relationship_types=[
            RelationshipTypeSchema("DEPLOYED_ON", "Service is deployed on infrastructure", ["SERVICE"], ["SERVER"]),
            RelationshipTypeSchema("CONNECTS_TO", "Component connects to another", ["SERVICE", "SERVER"], ["SERVICE", "SERVER", "DATABASE"]),
            RelationshipTypeSchema("MANAGED_BY", "Resource is managed by a team", ["SERVICE", "SERVER"], ["TEAM"]),
            RelationshipTypeSchema("USES", "Service uses a database or resource", ["SERVICE"], ["DATABASE", "SERVICE"]),
            RelationshipTypeSchema("RUNS_ON", "Process runs on infrastructure", ["PROCESS"], ["SERVER"]),
        ]
    ),
    "runbook": ReferenceOntology(
        id=None,
        tenant_id="",
        document_type="runbook",
        entity_types=[
            EntityTypeSchema("PROCEDURE", "A step-by-step operational procedure"),
            EntityTypeSchema("SERVICE", "A software service or system"),
            EntityTypeSchema("COMMAND", "A CLI command or script"),
            EntityTypeSchema("TOOL", "A software tool or utility"),
            EntityTypeSchema("CONDITION", "A trigger condition or check"),
            EntityTypeSchema("OUTCOME", "An expected result or state"),
        ],
        relationship_types=[
            RelationshipTypeSchema("APPLIES_TO", "Procedure applies to a service", ["PROCEDURE"], ["SERVICE"]),
            RelationshipTypeSchema("USES", "Procedure uses a tool or command", ["PROCEDURE"], ["TOOL", "COMMAND"]),
            RelationshipTypeSchema("TRIGGERS", "Condition triggers a procedure", ["CONDITION"], ["PROCEDURE"]),
            RelationshipTypeSchema("RESULTS_IN", "Procedure results in an outcome", ["PROCEDURE"], ["OUTCOME"]),
            RelationshipTypeSchema("PREREQUISITE_FOR", "Procedure is prerequisite for another", ["PROCEDURE"], ["PROCEDURE"]),
        ]
    ),
    "customer_profile": ReferenceOntology(
        id=None,
        tenant_id="",
        document_type="customer_profile",
        entity_types=[
            EntityTypeSchema("PERSON", "A human individual mentioned in the document"),
            EntityTypeSchema("ORGANIZATION", "A company or institution mentioned in the document"),
            EntityTypeSchema("DIVISION", "A specific branch or segment of an organization"),
            EntityTypeSchema("CONTRACT", "A formal agreement between parties regarding services or products"),
            EntityTypeSchema("PRODUCT", "An item or service offered by an organization"),
            EntityTypeSchema("REVENUE", "The income generated from business activities"),
            EntityTypeSchema("LOCATION", "A geographical place associated with an organization"),
            EntityTypeSchema("TITLE", "The position or role of a person within an organization"),
            EntityTypeSchema("OPPORTUNITY", "A potential business deal or project"),
            EntityTypeSchema("KEY_CONTACT", "An important individual for communication within a business"),
            EntityTypeSchema("ROLE", "A job title, position, or functional role held by a person"),
            EntityTypeSchema("SPECIFICATION", "A technical standard, tolerance, certification, or requirement"),
            EntityTypeSchema("MATERIAL", "A raw material, alloy, composite, or substance used in a product"),
            EntityTypeSchema("PROJECT", "A program, initiative, or named project"),
        ],
        relationship_types=[
            RelationshipTypeSchema("WORKS_AT", "Person is employed at an organization", ["PERSON"], ["ORGANIZATION"]),
            RelationshipTypeSchema("HAS_DIVISION", "Organization has a division", ["ORGANIZATION"], ["DIVISION"]),
            RelationshipTypeSchema("HAS_CONTRACT", "Organization holds a contract", ["ORGANIZATION"], ["CONTRACT"]),
            RelationshipTypeSchema("OFFERS_PRODUCT", "Organization offers a product", ["ORGANIZATION"], ["PRODUCT"]),
            RelationshipTypeSchema("GENERATES_REVENUE", "Organization or division generates revenue", ["ORGANIZATION", "DIVISION"], ["REVENUE"]),
            RelationshipTypeSchema("LOCATED_IN", "Organization or person is located somewhere", ["ORGANIZATION", "PERSON"], ["LOCATION"]),
            RelationshipTypeSchema("HAS_KEY_CONTACT", "Organization has a key contact person", ["ORGANIZATION"], ["KEY_CONTACT", "PERSON"]),
            RelationshipTypeSchema("AFFILIATED_WITH", "Person is affiliated with an organization (non-employment)", ["PERSON"], ["ORGANIZATION"]),
            RelationshipTypeSchema("HOLDS_POSITION", "Person holds a job title at an organization", ["PERSON"], ["ROLE", "TITLE"]),
            # NEW types added per accuracy fix:
            RelationshipTypeSchema("HOLDS_ROLE", "Person holds a specific named role or position. Use whenever a person's role/title/function is identified (e.g. 'Account Manager', 'VP Sales', 'CFO'). Same semantics as HOLDS_POSITION; prefer HOLDS_ROLE.", ["PERSON"], ["ROLE", "TITLE"]),
            RelationshipTypeSchema("HAS_SPEC", "Product, material, or component has a technical specification, standard, tolerance, or certification (e.g. 'ASTM B265', 'AS9100D', 'MIL-STD-810')", ["PRODUCT", "MATERIAL", "ORGANIZATION"], ["SPECIFICATION"]),
            RelationshipTypeSchema("USES_MATERIAL", "Product, project, or program uses or is made of a material (e.g. titanium, CFRP, aluminum alloy)", ["PRODUCT", "PROJECT", "ORGANIZATION", "DIVISION"], ["MATERIAL"]),
            RelationshipTypeSchema("INVOLVES", "Project, program, opportunity, or contract involves a person, organization, product, or material", ["PROJECT", "OPPORTUNITY", "CONTRACT", "ORGANIZATION"], ["PERSON", "ORGANIZATION", "PRODUCT", "MATERIAL"]),
            RelationshipTypeSchema("MEETS_SPEC", "Product or material conforms to / meets / is certified to a specification", ["PRODUCT", "MATERIAL"], ["SPECIFICATION"]),
        ]
    ),
    "technical_spec": ReferenceOntology(
        id=None,
        tenant_id="",
        document_type="technical_spec",
        entity_types=[
            EntityTypeSchema("PERSON", "A human individual mentioned in the document"),
            EntityTypeSchema("ORGANIZATION", "A company or institution"),
            EntityTypeSchema("FACILITY", "A physical location where a process or production takes place"),
            EntityTypeSchema("EQUIPMENT", "Machinery or tools used in the process"),
            EntityTypeSchema("PRODUCT", "An output product, component, or assembly"),
            EntityTypeSchema("LOCATION", "A geographical place"),
            EntityTypeSchema("PROCESS", "A series of steps or procedure"),
            EntityTypeSchema("SPECIFICATION", "A technical specification, standard, tolerance, or requirement"),
            EntityTypeSchema("PARAMETER", "A measurable parameter or characteristic"),
            EntityTypeSchema("DATE", "A date or time period"),
            EntityTypeSchema("MATERIAL", "A raw material, alloy, composite, or substance"),
            EntityTypeSchema("ROLE", "A job title or functional role"),
            EntityTypeSchema("PROJECT", "A project or program the spec belongs to"),
        ],
        relationship_types=[
            RelationshipTypeSchema("OWNS", "Organization owns a product or facility", ["ORGANIZATION", "PERSON"], ["ORGANIZATION", "PRODUCT", "FACILITY"]),
            RelationshipTypeSchema("LOCATED_IN", "Facility is located somewhere", ["FACILITY", "ORGANIZATION"], ["LOCATION"]),
            RelationshipTypeSchema("USES", "Process uses equipment", ["PROCESS"], ["EQUIPMENT"]),
            RelationshipTypeSchema("PRODUCES", "Facility or process produces a product", ["FACILITY", "PROCESS", "ORGANIZATION"], ["PRODUCT"]),
            RelationshipTypeSchema("SPECIFIED_BY", "Product is specified by a specification document", ["PRODUCT"], ["SPECIFICATION"]),
            RelationshipTypeSchema("HAS_PARAMETER", "Process or product has a measured parameter", ["PROCESS", "PRODUCT"], ["PARAMETER"]),
            RelationshipTypeSchema("AUTHORED_BY", "Document authored by a person", ["PRODUCT", "SPECIFICATION"], ["PERSON"]),
            RelationshipTypeSchema("DELIVERS_TO", "Product delivered to organization", ["PRODUCT"], ["ORGANIZATION"]),
            RelationshipTypeSchema("SUPPLIES_TO", "Organization supplies product to another organization", ["ORGANIZATION"], ["ORGANIZATION"]),
            RelationshipTypeSchema("MEETS_SPEC", "Product or material meets a specification", ["PRODUCT", "MATERIAL"], ["SPECIFICATION"]),
            # NEW types added per accuracy fix:
            RelationshipTypeSchema("HOLDS_ROLE", "Person holds a specific named role on this product/spec/program", ["PERSON"], ["ROLE"]),
            RelationshipTypeSchema("HAS_SPEC", "Product, material, or component has an associated technical specification, standard, or tolerance. Use this whenever a spec ID, standard, or numeric tolerance is attached to a thing.", ["PRODUCT", "MATERIAL", "EQUIPMENT"], ["SPECIFICATION"]),
            RelationshipTypeSchema("USES_MATERIAL", "Product or process uses a material", ["PRODUCT", "PROCESS", "EQUIPMENT"], ["MATERIAL"]),
            RelationshipTypeSchema("INVOLVES", "Project, process, or product involves a person, organization, or material", ["PROJECT", "PROCESS", "PRODUCT"], ["PERSON", "ORGANIZATION", "MATERIAL"]),
        ]
    ),
    "project_plan": ReferenceOntology(
        id=None,
        tenant_id="",
        document_type="project_plan",
        entity_types=[
            EntityTypeSchema("PERSON", "A human individual mentioned in the document"),
            EntityTypeSchema("ORGANIZATION", "A company or institution"),
            EntityTypeSchema("PROGRAM", "A specific program or initiative"),
            EntityTypeSchema("PROJECT", "A project (often used interchangeably with program)"),
            EntityTypeSchema("BUDGET", "Financial allocations and expenditures"),
            EntityTypeSchema("MILESTONE", "Key events or targets within the timeline"),
            EntityTypeSchema("SUPPLIER", "A supplier or vendor"),
            EntityTypeSchema("ROLE", "A specific position or function held by a person"),
            EntityTypeSchema("PHASE", "A stage in the program lifecycle"),
            EntityTypeSchema("CUSTOMER", "An entity receiving products or services"),
            EntityTypeSchema("SPECIFICATION", "A technical spec, standard, or requirement"),
            EntityTypeSchema("MATERIAL", "A raw material, alloy, composite, or substance"),
            EntityTypeSchema("PRODUCT", "A product or deliverable"),
        ],
        relationship_types=[
            RelationshipTypeSchema("MANAGES", "Person manages a program/project", ["PERSON"], ["PROGRAM", "PROJECT"]),
            RelationshipTypeSchema("WORKS_FOR", "Person works for an organization", ["PERSON"], ["ORGANIZATION"]),
            RelationshipTypeSchema("SUPPLIES", "Supplier supplies the program", ["SUPPLIER", "ORGANIZATION"], ["PROGRAM", "PROJECT", "ORGANIZATION"]),
            RelationshipTypeSchema("HAS_BUDGET", "Program has a budget", ["PROGRAM", "PROJECT"], ["BUDGET"]),
            RelationshipTypeSchema("HAS_MILESTONE", "Program has a milestone", ["PROGRAM", "PROJECT"], ["MILESTONE"]),
            RelationshipTypeSchema("PART_OF_PHASE", "Program is in a phase", ["PROGRAM", "PROJECT"], ["PHASE"]),
            RelationshipTypeSchema("SERVES_CUSTOMER", "Program serves a customer", ["PROGRAM", "PROJECT"], ["CUSTOMER", "ORGANIZATION"]),
            RelationshipTypeSchema("BELONGS_TO", "Program belongs to organization", ["PROGRAM", "PROJECT"], ["ORGANIZATION"]),
            RelationshipTypeSchema("MEMBER_OF", "Person is member of program team", ["PERSON"], ["PROGRAM", "PROJECT", "ORGANIZATION"]),
            # NEW types added per accuracy fix:
            RelationshipTypeSchema("HOLDS_ROLE", "Person holds a specific named role on this project (e.g. 'Project Director', 'Lead Engineer'). PREFER THIS over generic ALLOCATED_TO when a person/role is identified.", ["PERSON"], ["ROLE"]),
            RelationshipTypeSchema("HAS_SPEC", "Product, material, or deliverable has a technical specification, standard, or requirement", ["PRODUCT", "MATERIAL", "PROGRAM", "PROJECT"], ["SPECIFICATION"]),
            RelationshipTypeSchema("USES_MATERIAL", "Project, program, or product uses or specifies a material", ["PROJECT", "PROGRAM", "PRODUCT"], ["MATERIAL"]),
            RelationshipTypeSchema("INVOLVES", "Project or program involves a person, organization, supplier, or material. Use this for stakeholders / participants in a project.", ["PROJECT", "PROGRAM"], ["PERSON", "ORGANIZATION", "SUPPLIER", "MATERIAL", "PRODUCT"]),
            RelationshipTypeSchema("MEETS_SPEC", "Product or material meets a specification", ["PRODUCT", "MATERIAL"], ["SPECIFICATION"]),
        ]
    ),
    "org_chart": ReferenceOntology(
        id=None,
        tenant_id="",
        document_type="org_chart",
        entity_types=[
            EntityTypeSchema("PERSON", "A human individual"),
            EntityTypeSchema("ORGANIZATION", "A company or institution"),
            EntityTypeSchema("DIVISION", "A business unit or division"),
            EntityTypeSchema("PRODUCT", "A product or service offered"),
            EntityTypeSchema("CUSTOMER", "An entity that purchases products or services"),
            EntityTypeSchema("LOCATION", "A geographical place"),
            EntityTypeSchema("REVENUE", "Financial earnings"),
            EntityTypeSchema("STRATEGIC_PRIORITY", "A goal or objective"),
            EntityTypeSchema("FOCUS_AREA", "A key area of business or technology"),
            EntityTypeSchema("EMPLOYEE", "A person who works for the organization"),
            EntityTypeSchema("ROLE", "A job title or functional role"),
            EntityTypeSchema("SPECIFICATION", "A technical spec or requirement"),
            EntityTypeSchema("MATERIAL", "A material used by a division or product"),
            EntityTypeSchema("PROJECT", "A program or named project"),
        ],
        relationship_types=[
            RelationshipTypeSchema("WORKS_AT", "Person works at an organization", ["PERSON", "EMPLOYEE"], ["ORGANIZATION"]),
            RelationshipTypeSchema("HAS_DIVISION", "Organization has a division", ["ORGANIZATION"], ["DIVISION"]),
            RelationshipTypeSchema("OFFERS_PRODUCT", "Division offers a product", ["DIVISION", "ORGANIZATION"], ["PRODUCT"]),
            RelationshipTypeSchema("SERVES_CUSTOMER", "Division serves a customer", ["DIVISION"], ["CUSTOMER"]),
            RelationshipTypeSchema("LOCATED_IN", "Division is located somewhere", ["DIVISION", "ORGANIZATION"], ["LOCATION"]),
            RelationshipTypeSchema("GENERATES_REVENUE", "Division generates revenue", ["DIVISION"], ["REVENUE"]),
            RelationshipTypeSchema("FOCUSES_ON", "Division focuses on an area", ["DIVISION"], ["FOCUS_AREA"]),
            RelationshipTypeSchema("EMPLOYS", "Organization employs a person", ["ORGANIZATION"], ["EMPLOYEE", "PERSON"]),
            RelationshipTypeSchema("REPORTS_TO", "Person reports to another person", ["PERSON"], ["PERSON"]),
            RelationshipTypeSchema("PRESIDENT_OF", "Person is president of a division", ["PERSON"], ["DIVISION", "ORGANIZATION"]),
            # NEW types added per accuracy fix:
            RelationshipTypeSchema("HOLDS_ROLE", "Person holds a specific named role/title (e.g. 'CEO', 'CFO', 'CTO', 'VP Sales', 'Account Manager'). Use whenever a person's title or position is mentioned. PREFER THIS over generic WORKS_AT or PRESIDENT_OF when both apply.", ["PERSON"], ["ROLE"]),
            RelationshipTypeSchema("HAS_SPEC", "Product or division has a technical specification or standard", ["PRODUCT", "DIVISION"], ["SPECIFICATION"]),
            RelationshipTypeSchema("USES_MATERIAL", "Division or product uses a material", ["DIVISION", "PRODUCT"], ["MATERIAL"]),
            RelationshipTypeSchema("INVOLVES", "Division, project, or program involves a person or organization", ["DIVISION", "PROJECT", "ORGANIZATION"], ["PERSON", "ORGANIZATION", "PRODUCT"]),
        ]
    ),
    "architecture_doc": ReferenceOntology(
        id=None,
        tenant_id="",
        document_type="architecture_doc",
        entity_types=[
            EntityTypeSchema("PERSON", "A human individual"),
            EntityTypeSchema("ORGANIZATION", "A company or institution"),
            EntityTypeSchema("PRODUCT", "A product, system, component, or design (e.g. 'Solid State Battery NX-3000')"),
            EntityTypeSchema("COMPONENT", "A subsystem, part, or component (e.g. 'cathode', 'electrolyte separator')"),
            EntityTypeSchema("PARAMETER", "A measured parameter or characteristic"),
            EntityTypeSchema("MATERIAL", "A raw material, alloy, composite, or substance (e.g. 'lithium', 'NMC-811', 'graphene')"),
            EntityTypeSchema("SPECIFICATION", "A technical specification, standard, tolerance, or numeric target (e.g. '350 Wh/kg', 'IEC 62660-2')"),
            EntityTypeSchema("INTERFACE", "An interface between components"),
            EntityTypeSchema("MISSION_PROFILE", "A use-case or operating profile"),
            EntityTypeSchema("ROLE", "A job title or functional role on the design team"),
            EntityTypeSchema("PROJECT", "A program or named project the architecture serves"),
            EntityTypeSchema("LOCATION", "A geographical place"),
        ],
        relationship_types=[
            RelationshipTypeSchema("AUTHORED_BY", "Document authored by a person", ["PRODUCT"], ["PERSON"]),
            RelationshipTypeSchema("OWNS", "Organization owns the product/architecture", ["ORGANIZATION", "PERSON"], ["PRODUCT"]),
            RelationshipTypeSchema("PART_OF", "Component is part of a product", ["COMPONENT"], ["PRODUCT"]),
            RelationshipTypeSchema("HAS_PARAMETER", "Product or component has a parameter", ["PRODUCT", "COMPONENT"], ["PARAMETER"]),
            RelationshipTypeSchema("HAS_MISSION_PROFILE", "Product has a mission profile", ["PRODUCT"], ["MISSION_PROFILE"]),
            RelationshipTypeSchema("USES_INTERFACE", "Component uses an interface", ["COMPONENT", "PRODUCT"], ["INTERFACE"]),
            RelationshipTypeSchema("MADE_OF", "Component or product is made of a material", ["COMPONENT", "PRODUCT"], ["MATERIAL"]),
            RelationshipTypeSchema("DESCRIBES", "Document describes a product", ["PRODUCT"], ["PRODUCT"]),
            RelationshipTypeSchema("HAS_SPECIFICATION", "Product has a specification", ["PRODUCT", "COMPONENT"], ["SPECIFICATION"]),
            RelationshipTypeSchema("CLASSIFIED_AS", "Document is classified as a category", ["PRODUCT"], ["SPECIFICATION"]),
            # NEW types added per accuracy fix (HAS_SPEC is alias of HAS_SPECIFICATION; USES_MATERIAL is alias of MADE_OF):
            RelationshipTypeSchema("HOLDS_ROLE", "Person holds a specific named role on the design or program (e.g. 'Lead Architect', 'Principal Engineer')", ["PERSON"], ["ROLE"]),
            RelationshipTypeSchema("HAS_SPEC", "Product, component, or material has a technical specification, standard, tolerance, or numeric target. Use this whenever a spec ID, standard, or numeric value (e.g. '350 Wh/kg', 'cycle life 5000') is attached to a thing.", ["PRODUCT", "COMPONENT", "MATERIAL"], ["SPECIFICATION"]),
            RelationshipTypeSchema("USES_MATERIAL", "Product or component uses or is made of a material. Use this WHENEVER a component/product mentions any material it contains.", ["PRODUCT", "COMPONENT"], ["MATERIAL"]),
            RelationshipTypeSchema("INVOLVES", "Project or product involves a person, organization, component, or material", ["PROJECT", "PRODUCT"], ["PERSON", "ORGANIZATION", "COMPONENT", "MATERIAL"]),
            RelationshipTypeSchema("MEETS_SPEC", "Product or component meets a specification", ["PRODUCT", "COMPONENT", "MATERIAL"], ["SPECIFICATION"]),
        ]
    ),
    "GENERAL": ReferenceOntology(
        id=None,
        tenant_id="",
        document_type="GENERAL",
        entity_types=[
            EntityTypeSchema("PERSON", "A human individual mentioned in the document"),
            EntityTypeSchema("ORGANIZATION", "A company, institution, or business entity"),
            EntityTypeSchema("PROJECT", "A business project, initiative, or program"),
            EntityTypeSchema("ROLE", "A job title or position"),
            EntityTypeSchema("DEPARTMENT", "An organizational unit or team"),
            EntityTypeSchema("LOCATION", "A geographic location, city, or region"),
            EntityTypeSchema("DATE", "A date, time period, or deadline"),
            EntityTypeSchema("METRIC", "A quantitative measurement or KPI"),
            EntityTypeSchema("REVENUE", "Revenue, sales, or income amount"),
            EntityTypeSchema("BUDGET", "Budget, cost, or financial allocation"),
            EntityTypeSchema("AGREEMENT", "A contract, deal, or business agreement"),
            EntityTypeSchema("SUPPLIER", "A vendor, supplier, or partner organization"),
            EntityTypeSchema("TECHNOLOGY", "A technology, system, or platform"),
        ],
        relationship_types=[
            # Role and organizational relationships
            RelationshipTypeSchema("LEADS", "Person leads or is CEO of an organization", ["PERSON"], ["ORGANIZATION", "DEPARTMENT"]),
            RelationshipTypeSchema("CEO_OF", "Person is CEO of an organization", ["PERSON"], ["ORGANIZATION"]),
            RelationshipTypeSchema("CFO_OF", "Person is CFO of an organization", ["PERSON"], ["ORGANIZATION"]),
            RelationshipTypeSchema("CTO_OF", "Person is CTO of an organization", ["PERSON"], ["ORGANIZATION"]),
            RelationshipTypeSchema("COO_OF", "Person is COO of an organization", ["PERSON"], ["ORGANIZATION"]),
            RelationshipTypeSchema("CHAIRS", "Person chairs or leads a team/department", ["PERSON"], ["DEPARTMENT", "ORGANIZATION"]),
            RelationshipTypeSchema("MANAGES", "Person manages a department or project", ["PERSON"], ["DEPARTMENT", "PROJECT"]),
            RelationshipTypeSchema("HOLDS_POSITION", "Person holds a role at an organization", ["PERSON"], ["ROLE"]),
            RelationshipTypeSchema("WORKS_AT", "Person works at an organization", ["PERSON"], ["ORGANIZATION"]),
            RelationshipTypeSchema("PROJECT_DIRECTOR_OF", "Person is director of a project", ["PERSON"], ["PROJECT"]),

            # Financial and metric relationships (NEW - for tree retrieval)
            RelationshipTypeSchema("HAS_REVENUE", "Organization has revenue or sales amount", ["ORGANIZATION", "PROJECT"], ["REVENUE", "METRIC"]),
            RelationshipTypeSchema("HAS_BUDGET", "Organization or project has budget allocation", ["ORGANIZATION", "PROJECT"], ["BUDGET", "METRIC"]),
            RelationshipTypeSchema("HAS_AGREEMENT", "Organization has agreement or contract", ["ORGANIZATION"], ["AGREEMENT", "SUPPLIER"]),
            RelationshipTypeSchema("HAS_METRIC", "Entity has associated metric or measurement", ["ORGANIZATION", "PROJECT", "DEPARTMENT"], ["METRIC"]),
            RelationshipTypeSchema("SUPPLIES_TO", "Supplier provides goods/services to organization", ["SUPPLIER"], ["ORGANIZATION"]),

            # Project and business relationships
            RelationshipTypeSchema("OWNS", "Organization owns a project or initiative", ["ORGANIZATION"], ["PROJECT"]),
            RelationshipTypeSchema("LAUNCHES", "Organization launches a project or product", ["ORGANIZATION"], ["PROJECT"]),
            RelationshipTypeSchema("USES", "Organization uses a technology or system", ["ORGANIZATION", "PROJECT"], ["TECHNOLOGY"]),
            RelationshipTypeSchema("LOCATED_IN", "Entity is located in a place", ["ORGANIZATION", "PERSON"], ["LOCATION"]),
            RelationshipTypeSchema("PART_OF", "Department is part of organization", ["DEPARTMENT"], ["ORGANIZATION"]),
        ]
    ),
}


class OntologyManager:
    """
    Manages reference ontologies per tenant and document type.
    
    - Loads existing ontologies from database
    - Generates new ontologies via LLM when none exists
    - Updates ontologies as new types are discovered
    """
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self._cache: Dict[str, ReferenceOntology] = {}
        self.client = OpenAI(
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        )
    
    def get_or_create_ontology(
        self, 
        document_type: str, 
        sample_text: Optional[str] = None
    ) -> ReferenceOntology:
        """
        Load reference ontology or generate new one.
        
        Args:
            document_type: Type of document (e.g., 'resume', 'incident_report')
            sample_text: Sample document text for generating new ontology
            
        Returns:
            ReferenceOntology for this document type
        """
        cache_key = f"{self.tenant_id}:{document_type}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        ontology = self._load_from_database(document_type)
        if ontology:
            self._cache[cache_key] = ontology
            return ontology
        
        if document_type in DEFAULT_ONTOLOGIES:
            ontology = self._create_from_default(document_type)
        else:
            ontology = self._generate_ontology(document_type, sample_text or "")
        
        self._save_to_database(ontology)
        self._cache[cache_key] = ontology
        
        logger.info(f"[OntologyManager] Created ontology for '{document_type}': "
                   f"{len(ontology.entity_types)} entity types, {len(ontology.relationship_types)} relationship types")
        
        return ontology
    
    def _load_from_database(self, document_type: str) -> Optional[ReferenceOntology]:
        """Load ontology from database."""
        try:
            result = self.session.execute(
                text("""
                    SELECT id, entity_types, relationship_types, usage_count
                    FROM ontology.reference_ontologies
                    WHERE tenant_id = :tenant_id AND document_type = :doc_type
                """),
                {"tenant_id": self.tenant_id, "doc_type": document_type}
            ).fetchone()
            
            if not result:
                return None
            
            entity_types = [
                EntityTypeSchema(et["name"], et.get("definition", ""))
                for et in (result.entity_types or [])
            ]
            
            relationship_types = [
                RelationshipTypeSchema(
                    rt["name"],
                    rt.get("definition", ""),
                    rt.get("source_types", []),
                    rt.get("target_types", [])
                )
                for rt in (result.relationship_types or [])
            ]
            
            return ReferenceOntology(
                id=str(result.id),
                tenant_id=self.tenant_id,
                document_type=document_type,
                entity_types=entity_types,
                relationship_types=relationship_types,
                usage_count=result.usage_count
            )
            
        except Exception as e:
            logger.error(f"[OntologyManager] Failed to load ontology: {e}")
            return None
    
    def _create_from_default(self, document_type: str) -> ReferenceOntology:
        """Create ontology from default template."""
        default = DEFAULT_ONTOLOGIES[document_type]
        return ReferenceOntology(
            id=None,
            tenant_id=self.tenant_id,
            document_type=document_type,
            entity_types=default.entity_types.copy(),
            relationship_types=default.relationship_types.copy(),
            usage_count=1
        )
    
    def _generate_ontology(self, document_type: str, sample_text: str) -> ReferenceOntology:
        """Generate new ontology via LLM."""
        prompt = f"""This is a {document_type} document.

Based on this document, what entity types and relationship types would you expect to find?

Return JSON:
{{
  "entity_types": [
    {{"name": "PERSON", "definition": "A human individual mentioned in the document"}},
    ...
  ],
  "relationship_types": [
    {{"name": "WORKS_AT", "definition": "Employment relationship between person and organization", 
      "source_types": ["PERSON"], "target_types": ["ORGANIZATION"]}},
    ...
  ]
}}

Include 5-10 entity types and 5-10 relationship types that would be most relevant.
Use UPPERCASE_UNDERSCORE names.

DOCUMENT SAMPLE:
{sample_text[:3000]}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0
            )
            
            data = json.loads(response.choices[0].message.content)
            
            entity_types = [
                EntityTypeSchema(et["name"].upper(), et.get("definition", ""))
                for et in data.get("entity_types", [])
            ]
            
            relationship_types = [
                RelationshipTypeSchema(
                    rt["name"].upper().replace(" ", "_"),
                    rt.get("definition", ""),
                    rt.get("source_types", []),
                    rt.get("target_types", [])
                )
                for rt in data.get("relationship_types", [])
            ]
            
            return ReferenceOntology(
                id=None,
                tenant_id=self.tenant_id,
                document_type=document_type,
                entity_types=entity_types or [EntityTypeSchema("CONCEPT", "A general concept")],
                relationship_types=relationship_types or [RelationshipTypeSchema("RELATED_TO", "General relationship", [], [])],
                usage_count=1
            )
            
        except Exception as e:
            logger.error(f"[OntologyManager] Failed to generate ontology: {e}")
            return ReferenceOntology(
                id=None,
                tenant_id=self.tenant_id,
                document_type=document_type,
                entity_types=[
                    EntityTypeSchema("PERSON", "A human individual"),
                    EntityTypeSchema("ORGANIZATION", "A company or institution"),
                    EntityTypeSchema("CONCEPT", "A general concept"),
                ],
                relationship_types=[
                    RelationshipTypeSchema("RELATED_TO", "General relationship", [], []),
                ],
                usage_count=1
            )
    
    def _save_to_database(self, ontology: ReferenceOntology) -> None:
        """Save ontology to database."""
        try:
            self.session.execute(
                text("""
                    INSERT INTO ontology.reference_ontologies 
                    (id, tenant_id, document_type, entity_types, relationship_types, usage_count)
                    VALUES (:id, :tenant_id, :doc_type, :entity_types, :rel_types, :usage_count)
                    ON CONFLICT (tenant_id, document_type) 
                    DO UPDATE SET 
                        entity_types = :entity_types,
                        relationship_types = :rel_types,
                        usage_count = reference_ontologies.usage_count + 1,
                        updated_at = NOW()
                """),
                {
                    "id": str(uuid.uuid4()),
                    "tenant_id": self.tenant_id,
                    "doc_type": ontology.document_type,
                    "entity_types": json.dumps([et.to_dict() for et in ontology.entity_types]),
                    "rel_types": json.dumps([rt.to_dict() for rt in ontology.relationship_types]),
                    "usage_count": ontology.usage_count
                }
            )
            self.session.commit()
        except Exception as e:
            logger.error(f"[OntologyManager] Failed to save ontology: {e}")
            self.session.rollback()
    
    def update_ontology(
        self,
        document_type: str,
        new_entity_types: List[EntityTypeSchema],
        new_relationship_types: List[RelationshipTypeSchema]
    ) -> None:
        """
        Update reference ontology with discovered types.
        
        Args:
            document_type: Type of document
            new_entity_types: New entity types to add
            new_relationship_types: New relationship types to add
        """
        ontology = self.get_or_create_ontology(document_type)
        
        existing_entity_names = {et.name for et in ontology.entity_types}
        existing_rel_names = {rt.name for rt in ontology.relationship_types}
        
        added_entities = 0
        for et in new_entity_types:
            if et.name not in existing_entity_names:
                ontology.entity_types.append(et)
                existing_entity_names.add(et.name)
                added_entities += 1
        
        added_rels = 0
        for rt in new_relationship_types:
            if rt.name not in existing_rel_names:
                ontology.relationship_types.append(rt)
                existing_rel_names.add(rt.name)
                added_rels += 1
        
        if added_entities > 0 or added_rels > 0:
            self._save_to_database(ontology)
            logger.info(f"[OntologyManager] Updated '{document_type}': "
                       f"+{added_entities} entity types, +{added_rels} relationship types")
        
        cache_key = f"{self.tenant_id}:{document_type}"
        self._cache[cache_key] = ontology
    
    def get_entity_type_names(self, document_type: str) -> List[str]:
        """Get list of entity type names for a document type."""
        ontology = self.get_or_create_ontology(document_type)
        return [et.name for et in ontology.entity_types]
    
    def get_relationship_type_names(self, document_type: str) -> List[str]:
        """Get list of relationship type names for a document type."""
        ontology = self.get_or_create_ontology(document_type)
        return [rt.name for rt in ontology.relationship_types]
    
    def format_for_extraction_prompt(self, document_type: str) -> str:
        """Format ontology for use in extraction prompt."""
        ontology = self.get_or_create_ontology(document_type)
        
        entity_section = "ENTITY TYPES (use these when they fit, create new ones if needed):\n"
        for et in ontology.entity_types:
            entity_section += f"  - {et.name}: {et.definition}\n"
        
        rel_section = "\nRELATIONSHIP TYPES (use these when they fit, create new ones if needed):\n"
        for rt in ontology.relationship_types:
            sources = ", ".join(rt.source_types) if rt.source_types else "any"
            targets = ", ".join(rt.target_types) if rt.target_types else "any"
            rel_section += f"  - {rt.name}: {rt.definition} (from {sources} to {targets})\n"
        
        return entity_section + rel_section
