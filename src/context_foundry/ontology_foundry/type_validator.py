"""
TypeValidator Agent for Ontology Foundry

Validates proposed ontology types against:
- JSON schema validity
- Required fields completeness
- Naming conventions

This agent runs on PROPOSED types before they can move to VALIDATING.
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from .rule_executor import RuleExecutor, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class TypeProposal:
    """A proposed ontology type awaiting validation."""
    id: str
    type_name: str
    layer: int
    display_name: Optional[str]
    description: Optional[str]
    parent_type_id: Optional[str]
    properties_schema: Dict[str, Any]
    extraction_hints: Optional[List[str]]
    domain_id: Optional[str]
    proposed_by: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type_name': self.type_name,
            'layer': self.layer,
            'display_name': self.display_name,
            'description': self.description,
            'parent_type_id': self.parent_type_id,
            'properties_schema': self.properties_schema,
            'extraction_hints': self.extraction_hints,
            'domain_id': self.domain_id,
            'proposed_by': self.proposed_by,
        }


class TypeValidator:
    """
    Validates proposed ontology types.
    
    Responsibilities:
    - Check JSON schema validity for properties_schema
    - Verify required fields are present
    - Validate naming conventions (PascalCase)
    - Check parent_type_id references valid type
    
    Does NOT check:
    - Hierarchy depth (HierarchyEnforcer handles this)
    - Name collisions (CollisionDetector handles this)
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.rule_executor = RuleExecutor(session)
    
    def validate(self, proposal: TypeProposal) -> ValidationResult:
        """
        Validate a type proposal.
        
        Returns ValidationResult with errors/warnings.
        """
        logger.info(f"Validating type proposal: {proposal.type_name}")
        
        type_data = proposal.to_dict()
        
        validation_result = self._validate_structure(type_data)
        
        rule_result = self.rule_executor.validate_type(
            type_data,
            rules=self._get_type_validator_rules()
        )
        
        validation_result.errors.extend(rule_result.errors)
        validation_result.warnings.extend(rule_result.warnings)
        validation_result.passed = len(validation_result.errors) == 0
        
        if validation_result.passed:
            logger.info(f"Type {proposal.type_name} passed validation")
        else:
            logger.warning(f"Type {proposal.type_name} failed validation: {len(validation_result.errors)} errors")
        
        return validation_result
    
    def _validate_structure(self, type_data: Dict) -> ValidationResult:
        """Validate basic structural requirements."""
        errors = []
        warnings = []
        
        required_fields = ['id', 'type_name', 'layer', 'properties_schema']
        for field in required_fields:
            if type_data.get(field) is None:
                from .rule_executor import RuleResult
                errors.append(RuleResult(
                    rule_name='required_field',
                    rule_type='PROPERTY_REQUIRED',
                    severity='ERROR',
                    passed=False,
                    message=f"Required field '{field}' is missing",
                    target_name=type_data.get('type_name', 'unknown'),
                ))
        
        properties_schema = type_data.get('properties_schema')
        if properties_schema:
            if isinstance(properties_schema, str):
                try:
                    json.loads(properties_schema)
                except json.JSONDecodeError as e:
                    from .rule_executor import RuleResult
                    errors.append(RuleResult(
                        rule_name='json_schema_valid',
                        rule_type='PROPERTY_TYPE',
                        severity='ERROR',
                        passed=False,
                        message=f"properties_schema is not valid JSON: {str(e)}",
                        target_name=type_data.get('type_name', 'unknown'),
                    ))
        
        parent_id = type_data.get('parent_type_id')
        if parent_id:
            if not self._parent_exists(parent_id):
                from .rule_executor import RuleResult
                errors.append(RuleResult(
                    rule_name='parent_exists',
                    rule_type='PROPERTY_REQUIRED',
                    severity='ERROR',
                    passed=False,
                    message=f"Parent type {parent_id} does not exist",
                    target_name=type_data.get('type_name', 'unknown'),
                ))
        
        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
    
    def _parent_exists(self, parent_id: str) -> bool:
        """Check if parent type exists in ontology.types."""
        result = self.session.execute(text("""
            SELECT 1 FROM ontology.types WHERE id = :id
        """), {'id': parent_id})
        return result.fetchone() is not None
    
    def _get_type_validator_rules(self) -> List[Dict]:
        """Get rules relevant to TypeValidator (naming, properties)."""
        result = self.session.execute(text("""
            SELECT id, rule_name, rule_type, target_type, target_filter,
                   constraint_definition, severity
            FROM ontology.rules
            WHERE target_type = 'TYPE'
              AND status = 'ACTIVE'
              AND rule_type IN ('NAMING_PATTERN', 'PROPERTY_REQUIRED', 'PROPERTY_TYPE')
        """))
        
        return [
            {
                'id': str(row.id),
                'rule_name': row.rule_name,
                'rule_type': row.rule_type,
                'target_type': row.target_type,
                'target_filter': row.target_filter,
                'constraint_definition': row.constraint_definition,
                'severity': row.severity,
            }
            for row in result
        ]
    
    def transition_to_validating(self, type_id: str) -> bool:
        """
        Transition a PROPOSED type to VALIDATING status.
        
        Returns True if successful.
        """
        try:
            self.session.execute(text("""
                UPDATE ontology.types
                SET status = 'VALIDATING', updated_at = NOW()
                WHERE id = :id AND status = 'PROPOSED'
            """), {'id': type_id})
            self.session.commit()
            logger.info(f"Type {type_id} transitioned to VALIDATING")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to transition type {type_id}: {e}")
            return False
    
    def transition_to_approved(self, type_id: str) -> bool:
        """
        Transition a VALIDATING type to APPROVED status.
        
        Requires all validation checks to pass.
        Returns True if successful.
        """
        try:
            self.session.execute(text("""
                UPDATE ontology.types
                SET status = 'APPROVED', updated_at = NOW()
                WHERE id = :id AND status = 'VALIDATING'
            """), {'id': type_id})
            self.session.commit()
            logger.info(f"Type {type_id} transitioned to APPROVED")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to transition type {type_id}: {e}")
            return False
