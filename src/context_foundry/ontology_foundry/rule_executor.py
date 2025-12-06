"""
SHACL-Inspired Rule Executor for Ontology Foundry

Executes declarative validation rules stored in ontology.rules table.
Rules are data, not code - enables dynamic rule management.
"""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class RuleResult:
    """Result of executing a single rule against a target."""
    rule_name: str
    rule_type: str
    severity: str
    passed: bool
    message: Optional[str] = None
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Aggregate result of all rules executed against a target."""
    passed: bool
    errors: List[RuleResult] = field(default_factory=list)
    warnings: List[RuleResult] = field(default_factory=list)
    info: List[RuleResult] = field(default_factory=list)
    
    @property
    def error_count(self) -> int:
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        return len(self.warnings)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'passed': self.passed,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'errors': [r.__dict__ for r in self.errors],
            'warnings': [r.__dict__ for r in self.warnings],
            'info': [r.__dict__ for r in self.info],
        }


class RuleExecutor:
    """
    Executes SHACL-inspired validation rules against ontology types/relations.
    
    Rules are stored in ontology.rules table with:
    - rule_type: HIERARCHY_DEPTH, NAMING_PATTERN, PROPERTY_REQUIRED, etc.
    - target_type: TYPE, RELATION, ENTITY
    - constraint_definition: JSONB with rule parameters
    - severity: ERROR, WARNING, INFO
    """
    
    def __init__(self, session: Session):
        self.session = session
        self._rules_cache: Optional[List[Dict]] = None
    
    def load_rules(self, target_type: str = 'TYPE', status: str = 'ACTIVE') -> List[Dict]:
        """Load rules from database for given target type."""
        result = self.session.execute(text("""
            SELECT id, rule_name, rule_type, target_type, target_filter,
                   constraint_definition, severity, status
            FROM ontology.rules
            WHERE target_type = :target_type AND status = :status
        """), {'target_type': target_type, 'status': status})
        
        rules = []
        for row in result:
            rules.append({
                'id': str(row.id),
                'rule_name': row.rule_name,
                'rule_type': row.rule_type,
                'target_type': row.target_type,
                'target_filter': row.target_filter,
                'constraint_definition': row.constraint_definition,
                'severity': row.severity,
            })
        
        logger.info(f"Loaded {len(rules)} rules for target_type={target_type}")
        return rules
    
    def validate_type(self, type_data: Dict[str, Any], rules: Optional[List[Dict]] = None) -> ValidationResult:
        """
        Validate an ontology type against all applicable rules.
        
        Args:
            type_data: Dictionary with type fields (id, type_name, layer, parent_type_id, etc.)
            rules: Optional list of rules (loads from DB if not provided)
            
        Returns:
            ValidationResult with errors, warnings, and info
        """
        if rules is None:
            rules = self.load_rules(target_type='TYPE')
        
        errors = []
        warnings = []
        info = []
        
        for rule in rules:
            if not self._matches_filter(type_data, rule.get('target_filter')):
                continue
                
            result = self._execute_rule(rule, type_data)
            
            if not result.passed:
                if result.severity == 'ERROR':
                    errors.append(result)
                elif result.severity == 'WARNING':
                    warnings.append(result)
                else:
                    info.append(result)
        
        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            info=info
        )
    
    def _matches_filter(self, target: Dict, target_filter: Optional[Dict]) -> bool:
        """Check if target matches optional filter criteria."""
        if not target_filter:
            return True
        
        for key, value in target_filter.items():
            if target.get(key) != value:
                return False
        return True
    
    def _execute_rule(self, rule: Dict, target: Dict) -> RuleResult:
        """Execute a single rule against a target."""
        rule_type = rule['rule_type']
        constraint = rule['constraint_definition']
        
        try:
            if rule_type == 'HIERARCHY_DEPTH':
                passed, message = self._check_hierarchy_depth(target, constraint)
            elif rule_type == 'NAMING_PATTERN':
                passed, message = self._check_naming_pattern(target, constraint)
            elif rule_type == 'PROPERTY_REQUIRED':
                passed, message = self._check_property_required(target, constraint)
            elif rule_type == 'PROPERTY_TYPE':
                passed, message = self._check_property_type(target, constraint)
            elif rule_type == 'NAMESPACE_ALLOCATION':
                passed, message = self._check_namespace_allocation(target, constraint)
            elif rule_type == 'NO_ORPHANS':
                passed, message = self._check_no_orphans(target, constraint)
            elif rule_type == 'NO_COLLISIONS':
                passed, message = self._check_no_collisions(target, constraint)
            else:
                passed, message = True, None
                logger.warning(f"Unknown rule type: {rule_type}")
        except Exception as e:
            passed = False
            message = f"Rule execution error: {str(e)}"
            logger.error(f"Error executing rule {rule['rule_name']}: {e}")
        
        return RuleResult(
            rule_name=rule['rule_name'],
            rule_type=rule_type,
            severity=rule['severity'],
            passed=passed,
            message=message if not passed else None,
            target_id=str(target.get('id', '')),
            target_name=target.get('type_name', ''),
        )
    
    def _check_hierarchy_depth(self, target: Dict, constraint: Dict) -> tuple:
        """Check that type has minimum hierarchy depth."""
        min_depth = constraint.get('value', 3)
        
        depth = self._compute_hierarchy_depth(target)
        
        if depth < min_depth:
            return False, f"{constraint.get('message', f'Hierarchy depth {depth} < {min_depth}')}"
        return True, None
    
    def _compute_hierarchy_depth(self, target: Dict) -> int:
        """Compute depth from Layer 1 to this type."""
        parent_id = target.get('parent_type_id')
        if not parent_id:
            return 1
        
        depth = 1
        current_parent = parent_id
        max_iterations = 10
        
        while current_parent and depth < max_iterations:
            result = self.session.execute(text("""
                SELECT parent_type_id, layer FROM ontology.types WHERE id = :id
            """), {'id': current_parent})
            row = result.fetchone()
            
            if not row:
                break
            
            depth += 1
            if row.layer <= 1:
                break
            current_parent = row.parent_type_id
        
        return depth
    
    def _check_naming_pattern(self, target: Dict, constraint: Dict) -> tuple:
        """Check that field matches naming pattern."""
        field_name = constraint.get('field', 'type_name')
        pattern = constraint.get('regex', r'^[A-Z][a-zA-Z0-9]*$')
        
        value = target.get(field_name, '')
        if not value:
            return False, f"Field '{field_name}' is empty"
        
        if not re.match(pattern, value):
            return False, constraint.get('message', f"'{value}' doesn't match pattern {pattern}")
        return True, None
    
    def _check_property_required(self, target: Dict, constraint: Dict) -> tuple:
        """Check that required property exists and is not empty."""
        field_name = constraint.get('field')
        allow_empty = constraint.get('allowEmpty', False)
        
        value = target.get(field_name)
        
        if value is None:
            return False, constraint.get('message', f"Required field '{field_name}' is missing")
        
        if not allow_empty and (value == '' or value == [] or value == {}):
            return False, constraint.get('message', f"Required field '{field_name}' is empty")
        
        return True, None
    
    def _check_property_type(self, target: Dict, constraint: Dict) -> tuple:
        """Check property type validity (e.g., valid JSON schema)."""
        field_name = constraint.get('field')
        value = target.get(field_name)
        
        if constraint.get('constraint') == 'jsonSchema':
            if value is None:
                return False, constraint.get('message', f"Field '{field_name}' is missing")
            
            if isinstance(value, str):
                try:
                    json.loads(value)
                except json.JSONDecodeError:
                    return False, constraint.get('message', f"Field '{field_name}' is not valid JSON")
            elif not isinstance(value, dict):
                return False, constraint.get('message', f"Field '{field_name}' must be JSON object")
        
        return True, None
    
    def _check_namespace_allocation(self, target: Dict, constraint: Dict) -> tuple:
        """Check UUID follows namespace allocation rules."""
        target_id = str(target.get('id', ''))
        layer = target.get('layer', 2)
        
        patterns = constraint.get('patterns', {})
        
        if layer == 0 and not target_id.startswith('00000000'):
            return False, constraint.get('message', 'Layer 0 types must use 00000000-* namespace')
        if layer == 1 and not target_id.startswith('10000000'):
            return False, constraint.get('message', 'Layer 1 types must use 10000000-* namespace')
        if layer == 2:
            if not target_id.startswith('20000000'):
                return False, constraint.get('message', 'Layer 2 types must use 20000000-* namespace')
        
        return True, None
    
    def _check_no_orphans(self, target: Dict, constraint: Dict) -> tuple:
        """Check type participates in at least N relationships."""
        min_relationships = constraint.get('value', 1)
        target_id = target.get('id')
        
        if not target_id:
            return True, None
        
        result = self.session.execute(text("""
            SELECT COUNT(*) as cnt FROM ontology.relations
            WHERE (source_type_id = :id OR target_type_id = :id)
              AND status = 'ACTIVE'
        """), {'id': target_id})
        row = result.fetchone()
        
        count = row.cnt if row else 0
        
        if count < min_relationships:
            return False, constraint.get('message', f'Type has {count} relationships (min: {min_relationships})')
        return True, None
    
    def _check_no_collisions(self, target: Dict, constraint: Dict) -> tuple:
        """Check for name/UUID collisions with existing types."""
        type_name = target.get('type_name')
        target_id = target.get('id')
        
        result = self.session.execute(text("""
            SELECT id, type_name FROM ontology.types
            WHERE (type_name = :name OR id = :id)
              AND status != 'DEPRECATED'
        """), {'name': type_name, 'id': target_id})
        
        collisions = result.fetchall()
        
        if collisions:
            existing = collisions[0]
            if str(existing.id) != str(target_id):
                return False, f"Collision detected: type_name '{type_name}' already exists"
        
        return True, None
