"""
HierarchyEnforcer Agent for Ontology Foundry

Validates ontology type hierarchy:
- Minimum depth >= 3 (no direct Layer 1 inheritance for concrete types)
- Valid parent type exists
- No circular references
- Layer progression is valid (child.layer >= parent.layer)

This agent runs after TypeValidator, before CollisionDetector.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Set
from sqlalchemy import text
from sqlalchemy.orm import Session

from .rule_executor import RuleExecutor, ValidationResult, RuleResult

logger = logging.getLogger(__name__)


@dataclass
class HierarchyInfo:
    """Information about a type's position in the hierarchy."""
    type_id: str
    type_name: str
    layer: int
    depth: int
    parent_chain: List[str]
    is_abstract: bool


class HierarchyEnforcer:
    """
    Enforces ontology hierarchy rules.
    
    Responsibilities:
    - Ensure hierarchy depth >= 3 for concrete types
    - Detect circular parent references
    - Validate layer progression
    - Ensure parent types exist and are valid
    
    Architecture Standard Requirements:
    - Layer 0: Meta-ontology (immutable)
    - Layer 1: Core primitives (Asset, Event, Person, etc.)
    - Layer 2+: Domain-specific types with intermediate abstracts
    """
    
    MIN_DEPTH_FOR_CONCRETE = 3
    MAX_HIERARCHY_DEPTH = 10
    
    def __init__(self, session: Session):
        self.session = session
        self.rule_executor = RuleExecutor(session)
    
    def validate(self, type_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate type against hierarchy rules.
        
        Returns ValidationResult with errors/warnings.
        """
        type_name = type_data.get('type_name', 'unknown')
        logger.info(f"Enforcing hierarchy rules for: {type_name}")
        
        errors = []
        warnings = []
        
        hierarchy = self._compute_hierarchy(type_data)
        
        circular_result = self._check_circular_reference(type_data, hierarchy)
        if not circular_result.passed:
            errors.append(circular_result)
        
        depth_result = self._check_hierarchy_depth(type_data, hierarchy)
        if not depth_result.passed:
            if depth_result.severity == 'ERROR':
                errors.append(depth_result)
            else:
                warnings.append(depth_result)
        
        layer_result = self._check_layer_progression(type_data)
        if not layer_result.passed:
            errors.append(layer_result)
        
        passed = len(errors) == 0
        
        if passed:
            logger.info(f"Type {type_name} passed hierarchy enforcement (depth={hierarchy.depth})")
        else:
            logger.warning(f"Type {type_name} failed hierarchy enforcement: {len(errors)} errors")
        
        return ValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
        )
    
    def _compute_hierarchy(self, type_data: Dict) -> HierarchyInfo:
        """Compute hierarchy information for a type."""
        type_id = str(type_data.get('id', ''))
        type_name = type_data.get('type_name', 'unknown')
        layer = type_data.get('layer', 2)
        
        parent_chain = []
        depth = 1
        current_parent = type_data.get('parent_type_id')
        visited: Set[str] = {type_id}
        
        while current_parent and depth < self.MAX_HIERARCHY_DEPTH:
            if str(current_parent) in visited:
                break
            
            visited.add(str(current_parent))
            
            result = self.session.execute(text("""
                SELECT id, type_name, parent_type_id, layer 
                FROM ontology.types WHERE id = :id
            """), {'id': current_parent})
            row = result.fetchone()
            
            if not row:
                break
            
            parent_chain.append(row.type_name)
            depth += 1
            
            if row.layer <= 1:
                break
            
            current_parent = row.parent_type_id
        
        return HierarchyInfo(
            type_id=type_id,
            type_name=type_name,
            layer=layer,
            depth=depth,
            parent_chain=parent_chain,
            is_abstract=type_name.endswith('Facility') or type_name.endswith('Asset'),
        )
    
    def _check_circular_reference(self, type_data: Dict, hierarchy: HierarchyInfo) -> RuleResult:
        """Check for circular parent references."""
        type_id = str(type_data.get('id', ''))
        parent_id = type_data.get('parent_type_id')
        
        if not parent_id:
            return RuleResult(
                rule_name='no_circular_reference',
                rule_type='HIERARCHY_DEPTH',
                severity='ERROR',
                passed=True,
            )
        
        current = parent_id
        visited = {type_id}
        depth = 0
        
        while current and depth < self.MAX_HIERARCHY_DEPTH:
            if str(current) in visited:
                return RuleResult(
                    rule_name='no_circular_reference',
                    rule_type='HIERARCHY_DEPTH',
                    severity='ERROR',
                    passed=False,
                    message=f"Circular reference detected: {type_data.get('type_name')} -> ... -> {type_data.get('type_name')}",
                    target_id=type_id,
                    target_name=type_data.get('type_name'),
                )
            
            visited.add(str(current))
            
            result = self.session.execute(text("""
                SELECT parent_type_id FROM ontology.types WHERE id = :id
            """), {'id': current})
            row = result.fetchone()
            
            if not row:
                break
            
            current = row.parent_type_id
            depth += 1
        
        return RuleResult(
            rule_name='no_circular_reference',
            rule_type='HIERARCHY_DEPTH',
            severity='ERROR',
            passed=True,
        )
    
    def _check_hierarchy_depth(self, type_data: Dict, hierarchy: HierarchyInfo) -> RuleResult:
        """Check that type has minimum hierarchy depth."""
        layer = type_data.get('layer', 2)
        
        if layer <= 1:
            return RuleResult(
                rule_name='hierarchy_minimum_depth',
                rule_type='HIERARCHY_DEPTH',
                severity='INFO',
                passed=True,
                message="Layer 0-1 types exempt from depth requirement",
            )
        
        if hierarchy.is_abstract:
            min_depth = 2
        else:
            min_depth = self.MIN_DEPTH_FOR_CONCRETE
        
        if hierarchy.depth < min_depth:
            return RuleResult(
                rule_name='hierarchy_minimum_depth',
                rule_type='HIERARCHY_DEPTH',
                severity='ERROR',
                passed=False,
                message=f"Hierarchy depth {hierarchy.depth} < {min_depth}. Chain: {' -> '.join(hierarchy.parent_chain) or 'None'}",
                target_id=hierarchy.type_id,
                target_name=hierarchy.type_name,
                details={
                    'depth': hierarchy.depth,
                    'min_depth': min_depth,
                    'parent_chain': hierarchy.parent_chain,
                }
            )
        
        return RuleResult(
            rule_name='hierarchy_minimum_depth',
            rule_type='HIERARCHY_DEPTH',
            severity='ERROR',
            passed=True,
        )
    
    def _check_layer_progression(self, type_data: Dict) -> RuleResult:
        """Check that child layer >= parent layer."""
        parent_id = type_data.get('parent_type_id')
        child_layer = type_data.get('layer', 2)
        
        if not parent_id:
            return RuleResult(
                rule_name='layer_progression',
                rule_type='HIERARCHY_DEPTH',
                severity='ERROR',
                passed=True,
            )
        
        result = self.session.execute(text("""
            SELECT layer FROM ontology.types WHERE id = :id
        """), {'id': parent_id})
        row = result.fetchone()
        
        if not row:
            return RuleResult(
                rule_name='layer_progression',
                rule_type='HIERARCHY_DEPTH',
                severity='ERROR',
                passed=False,
                message=f"Parent type {parent_id} not found",
                target_id=str(type_data.get('id')),
                target_name=type_data.get('type_name'),
            )
        
        parent_layer = row.layer
        
        if child_layer < parent_layer:
            return RuleResult(
                rule_name='layer_progression',
                rule_type='HIERARCHY_DEPTH',
                severity='ERROR',
                passed=False,
                message=f"Child layer ({child_layer}) < parent layer ({parent_layer})",
                target_id=str(type_data.get('id')),
                target_name=type_data.get('type_name'),
            )
        
        return RuleResult(
            rule_name='layer_progression',
            rule_type='HIERARCHY_DEPTH',
            severity='ERROR',
            passed=True,
        )
    
    def get_hierarchy_tree(self, root_type_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the full hierarchy tree from a root type.
        
        If root_type_id is None, returns forest of all root types.
        """
        if root_type_id:
            return self._build_subtree(root_type_id)
        
        result = self.session.execute(text("""
            SELECT id, type_name FROM ontology.types
            WHERE parent_type_id IS NULL AND status = 'ACTIVE'
            ORDER BY layer, type_name
        """))
        
        roots = []
        for row in result:
            roots.append(self._build_subtree(str(row.id)))
        
        return {'roots': roots}
    
    def _build_subtree(self, type_id: str) -> Dict[str, Any]:
        """Build subtree for a single type."""
        result = self.session.execute(text("""
            SELECT id, type_name, layer, status FROM ontology.types WHERE id = :id
        """), {'id': type_id})
        row = result.fetchone()
        
        if not row:
            return {}
        
        children_result = self.session.execute(text("""
            SELECT id, type_name FROM ontology.types
            WHERE parent_type_id = :id AND status = 'ACTIVE'
            ORDER BY type_name
        """), {'id': type_id})
        
        children = []
        for child in children_result:
            children.append(self._build_subtree(str(child.id)))
        
        return {
            'id': str(row.id),
            'type_name': row.type_name,
            'layer': row.layer,
            'status': row.status,
            'children': children,
        }
