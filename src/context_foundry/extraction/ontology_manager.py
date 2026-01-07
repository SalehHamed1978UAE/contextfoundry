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
            RelationshipTypeSchema("HELD_POSITION", "Person held a job title at an organization", ["PERSON"], ["JOB_TITLE"]),
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
