"""
Schema Validation Utilities for Context Foundry Ontology

Validates that extracted entities and relationships conform to the ontology schema.
"""

from typing import List, Tuple, Optional
from .schema import (
    EntityType,
    RelationshipType,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionOutput,
    VALID_RELATIONSHIP_SOURCES,
    VALID_RELATIONSHIP_TARGETS,
    ENTITY_PROPERTY_MAP,
)


class ValidationError:
    """Represents a schema validation error."""
    
    def __init__(self, error_type: str, message: str, entity_or_rel: Optional[str] = None):
        self.error_type = error_type
        self.message = message
        self.entity_or_rel = entity_or_rel
    
    def __repr__(self):
        return f"ValidationError({self.error_type}: {self.message})"


class OntologyValidator:
    """Validates extraction outputs against the ontology schema."""
    
    def __init__(self, strict: bool = False):
        self.strict = strict
        self.valid_entity_types = set(e.value for e in EntityType)
        self.valid_relationship_types = set(r.value for r in RelationshipType)
    
    def validate_entity(self, entity: ExtractedEntity) -> List[ValidationError]:
        """Validate a single entity against the schema."""
        errors = []
        
        if not entity.name or not entity.name.strip():
            errors.append(ValidationError(
                "missing_name",
                "Entity name is required and cannot be empty",
                entity.name
            ))
        
        entity_type_str = entity.entity_type if isinstance(entity.entity_type, str) else entity.entity_type.value
        if entity_type_str not in self.valid_entity_types:
            errors.append(ValidationError(
                "invalid_entity_type",
                f"Entity type '{entity_type_str}' is not in the ontology schema",
                entity.name
            ))
        
        if not 0.0 <= entity.confidence <= 1.0:
            errors.append(ValidationError(
                "invalid_confidence",
                f"Confidence {entity.confidence} must be between 0.0 and 1.0",
                entity.name
            ))
        
        return errors
    
    def validate_relationship(self, rel: ExtractedRelationship) -> List[ValidationError]:
        """Validate a single relationship against the schema."""
        errors = []
        
        if not rel.source_entity or not rel.source_entity.strip():
            errors.append(ValidationError(
                "missing_source",
                "Relationship source entity is required",
                f"{rel.source_entity} -> {rel.target_entity}"
            ))
        
        if not rel.target_entity or not rel.target_entity.strip():
            errors.append(ValidationError(
                "missing_target",
                "Relationship target entity is required",
                f"{rel.source_entity} -> {rel.target_entity}"
            ))
        
        rel_type_str = rel.relationship_type if isinstance(rel.relationship_type, str) else rel.relationship_type.value
        if rel_type_str not in self.valid_relationship_types:
            errors.append(ValidationError(
                "invalid_relationship_type",
                f"Relationship type '{rel_type_str}' is not in the ontology schema",
                f"{rel.source_entity} -[{rel_type_str}]-> {rel.target_entity}"
            ))
        
        if self.strict:
            errors.extend(self._validate_relationship_constraints(rel))
        
        if not 0.0 <= rel.confidence <= 1.0:
            errors.append(ValidationError(
                "invalid_confidence",
                f"Confidence {rel.confidence} must be between 0.0 and 1.0",
                f"{rel.source_entity} -> {rel.target_entity}"
            ))
        
        return errors
    
    def _validate_relationship_constraints(self, rel: ExtractedRelationship) -> List[ValidationError]:
        """Validate that relationship source/target types are valid per schema."""
        errors = []
        
        try:
            rel_type = RelationshipType(rel.relationship_type) if isinstance(rel.relationship_type, str) else rel.relationship_type
        except ValueError:
            return errors
        
        source_type_str = rel.source_type if isinstance(rel.source_type, str) else rel.source_type.value
        target_type_str = rel.target_type if isinstance(rel.target_type, str) else rel.target_type.value
        
        try:
            source_type = EntityType(source_type_str)
            target_type = EntityType(target_type_str)
        except ValueError:
            return errors
        
        if rel_type in VALID_RELATIONSHIP_SOURCES:
            valid_sources = VALID_RELATIONSHIP_SOURCES[rel_type]
            if source_type not in valid_sources:
                errors.append(ValidationError(
                    "invalid_source_type",
                    f"Relationship {rel_type.value} cannot have source of type {source_type.value}. "
                    f"Valid sources: {[t.value for t in valid_sources]}",
                    f"{rel.source_entity} -[{rel_type.value}]-> {rel.target_entity}"
                ))
        
        if rel_type in VALID_RELATIONSHIP_TARGETS:
            valid_targets = VALID_RELATIONSHIP_TARGETS[rel_type]
            if target_type not in valid_targets:
                errors.append(ValidationError(
                    "invalid_target_type",
                    f"Relationship {rel_type.value} cannot have target of type {target_type.value}. "
                    f"Valid targets: {[t.value for t in valid_targets]}",
                    f"{rel.source_entity} -[{rel_type.value}]-> {rel.target_entity}"
                ))
        
        return errors
    
    def validate_extraction_output(self, output: ExtractionOutput) -> Tuple[bool, List[ValidationError]]:
        """Validate a complete extraction output."""
        all_errors = []
        
        for entity in output.entities:
            all_errors.extend(self.validate_entity(entity))
        
        for rel in output.relationships:
            all_errors.extend(self.validate_relationship(rel))
        
        is_valid = len(all_errors) == 0
        return is_valid, all_errors
    
    def validate_and_filter(self, output: ExtractionOutput) -> ExtractionOutput:
        """Validate and return only valid entities/relationships."""
        valid_entities = []
        valid_relationships = []
        
        for entity in output.entities:
            errors = self.validate_entity(entity)
            if not errors:
                valid_entities.append(entity)
        
        for rel in output.relationships:
            errors = self.validate_relationship(rel)
            if not errors:
                valid_relationships.append(rel)
        
        return ExtractionOutput(
            document_id=output.document_id,
            document_path=output.document_path,
            model_name=output.model_name,
            extracted_at=output.extracted_at,
            entities=valid_entities,
            relationships=valid_relationships,
            metadata={
                **output.metadata,
                "filtered_entities": len(output.entities) - len(valid_entities),
                "filtered_relationships": len(output.relationships) - len(valid_relationships),
            }
        )


def normalize_entity_type(raw_type: str) -> Optional[EntityType]:
    """Normalize a raw entity type string to a canonical EntityType."""
    raw_upper = raw_type.upper().replace(" ", "_").replace("-", "_")
    
    aliases = {
        "COMPANY": EntityType.ORGANIZATION,
        "CORP": EntityType.ORGANIZATION,
        "CORPORATION": EntityType.ORGANIZATION,
        "FIRM": EntityType.ORGANIZATION,
        "ENTERPRISE": EntityType.ORGANIZATION,
        "BU": EntityType.BUSINESS_UNIT,
        "DIVISION": EntityType.BUSINESS_UNIT,
        "DEPARTMENT": EntityType.BUSINESS_UNIT,
        "TEAM": EntityType.BUSINESS_UNIT,
        "INITIATIVE": EntityType.PROJECT,
        "PROGRAM": EntityType.PROJECT,
        "CAMPAIGN": EntityType.PROJECT,
        "INDIVIDUAL": EntityType.PERSON,
        "EMPLOYEE": EntityType.PERSON,
        "EXECUTIVE": EntityType.PERSON,
        "MANAGER": EntityType.PERSON,
        "CLIENT": EntityType.CUSTOMER,
        "ACCOUNT": EntityType.CUSTOMER,
        "VENDOR": EntityType.SUPPLIER,
        "PROVIDER": EntityType.SUPPLIER,
        "ALLY": EntityType.PARTNER,
        "SITE": EntityType.FACILITY,
        "PLANT": EntityType.FACILITY,
        "OFFICE": EntityType.FACILITY,
        "HQ": EntityType.FACILITY,
        "HEADQUARTERS": EntityType.FACILITY,
        "PLACE": EntityType.LOCATION,
        "CITY": EntityType.LOCATION,
        "COUNTRY": EntityType.LOCATION,
        "REGION": EntityType.LOCATION,
        "KPI": EntityType.FINANCIAL_METRIC,
        "METRIC": EntityType.FINANCIAL_METRIC,
        "MEASURE": EntityType.FINANCIAL_METRIC,
        "RULE": EntityType.POLICY,
        "REGULATION": EntityType.POLICY,
        "GUIDELINE": EntityType.POLICY,
        "ITEM": EntityType.PRODUCT,
        "OFFERING": EntityType.SERVICE,
    }
    
    if raw_upper in aliases:
        return aliases[raw_upper]
    
    try:
        return EntityType(raw_upper)
    except ValueError:
        return None


def normalize_relationship_type(raw_type: str) -> Optional[RelationshipType]:
    """Normalize a raw relationship type string to a canonical RelationshipType."""
    raw_upper = raw_type.upper().replace(" ", "_").replace("-", "_")
    
    aliases = {
        "EMPLOYS": RelationshipType.WORKS_FOR,
        "EMPLOYED_BY": RelationshipType.WORKS_FOR,
        "IS_EMPLOYEE_OF": RelationshipType.WORKS_FOR,
        "WORKS_IN": RelationshipType.WORKS_AT,
        "BASED_AT": RelationshipType.LOCATED_AT,
        "HEADQUARTERED_AT": RelationshipType.LOCATED_AT,
        "IN": RelationshipType.LOCATED_AT,
        "SUPERVISES": RelationshipType.MANAGES,
        "OVERSEES": RelationshipType.MANAGES,
        "HEADS": RelationshipType.LEADS,
        "RUNS": RelationshipType.LEADS,
        "DIRECTS": RelationshipType.LEADS,
        "CHAIRS": RelationshipType.LEADS,
        "OWNS_PROJECT": RelationshipType.OWNS,
        "HAS": RelationshipType.OWNS,
        "CONTROLS": RelationshipType.OWNS,
        "IS_CUSTOMER": RelationshipType.CUSTOMER_OF,
        "BUYS_FROM": RelationshipType.CUSTOMER_OF,
        "PURCHASES_FROM": RelationshipType.CUSTOMER_OF,
        "IS_SUPPLIER": RelationshipType.SUPPLIER_OF,
        "SUPPLIES": RelationshipType.SUPPLIER_OF,
        "SELLS_TO": RelationshipType.SUPPLIER_OF,
        "IS_PARTNER": RelationshipType.PARTNER_OF,
        "PARTNERS_WITH": RelationshipType.PARTNER_OF,
        "COLLABORATES_WITH": RelationshipType.PARTNER_OF,
        "FINANCES": RelationshipType.FUNDED_BY,
        "SPONSORS": RelationshipType.FUNDED_BY,
        "INVESTS_IN": RelationshipType.FUNDED_BY,
        "REQUIRES_TECHNOLOGY": RelationshipType.USES,
        "UTILIZES": RelationshipType.USES,
        "LEVERAGES": RelationshipType.USES,
        "NEEDS": RelationshipType.REQUIRES,
        "MEMBER_OF": RelationshipType.PART_OF,
        "BELONGS_TO": RelationshipType.PART_OF,
        "WITHIN": RelationshipType.PART_OF,
        "CONNECTED_TO": RelationshipType.RELATED_TO,
        "LINKED_TO": RelationshipType.RELATED_TO,
        "ASSOCIATED_WITH": RelationshipType.RELATED_TO,
        "REFERENCED_IN": RelationshipType.MENTIONED_IN,
        "CITED_IN": RelationshipType.MENTIONED_IN,
        "APPEARS_IN": RelationshipType.MENTIONED_IN,
    }
    
    if raw_upper in aliases:
        return aliases[raw_upper]
    
    try:
        return RelationshipType(raw_upper)
    except ValueError:
        return None
