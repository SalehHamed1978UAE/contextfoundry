"""
CollisionDetector Agent for Ontology Foundry

Detects collisions and conflicts:
- Name collisions (same type_name in different domains)
- UUID collisions (duplicate IDs)
- Semantic duplicates (similar types that should be merged)

This agent runs after TypeValidator and HierarchyEnforcer.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from .rule_executor import ValidationResult, RuleResult

logger = logging.getLogger(__name__)


@dataclass
class Collision:
    """Detected collision between types."""
    collision_type: str
    proposed_type_id: str
    proposed_type_name: str
    existing_type_id: str
    existing_type_name: str
    existing_domain: Optional[str]
    resolution: Optional[str] = None


class CollisionDetector:
    """
    Detects collisions between proposed and existing types.
    
    Collision Types:
    - NAME_COLLISION: Same type_name already exists
    - UUID_COLLISION: Same UUID already assigned
    - SEMANTIC_DUPLICATE: Very similar type (potential merge candidate)
    
    Resolution Options:
    - RENAME: Proposer renames their type
    - MERGE: Merge into existing type
    - SUPERSEDE: New type supersedes old (with deprecation)
    - NAMESPACE: Move to domain-specific namespace
    """
    
    SIMILARITY_THRESHOLD = 0.8
    
    def __init__(self, session: Session):
        self.session = session
    
    def detect(self, type_data: Dict[str, Any]) -> ValidationResult:
        """
        Detect collisions for a proposed type.
        
        Returns ValidationResult with collision errors.
        """
        type_name = type_data.get('type_name', 'unknown')
        logger.info(f"Detecting collisions for: {type_name}")
        
        errors = []
        warnings = []
        
        collisions = self._find_all_collisions(type_data)
        
        for collision in collisions:
            result = self._collision_to_rule_result(collision)
            if result.severity == 'ERROR':
                errors.append(result)
            else:
                warnings.append(result)
        
        passed = len(errors) == 0
        
        if passed:
            logger.info(f"No collisions detected for {type_name}")
        else:
            logger.warning(f"Detected {len(errors)} collisions for {type_name}")
        
        return ValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
        )
    
    def _find_all_collisions(self, type_data: Dict) -> List[Collision]:
        """Find all types that collide with the proposed type."""
        collisions = []
        
        name_collision = self._check_name_collision(type_data)
        if name_collision:
            collisions.append(name_collision)
        
        uuid_collision = self._check_uuid_collision(type_data)
        if uuid_collision:
            collisions.append(uuid_collision)
        
        semantic_duplicates = self._check_semantic_duplicates(type_data)
        collisions.extend(semantic_duplicates)
        
        return collisions
    
    def _check_name_collision(self, type_data: Dict) -> Optional[Collision]:
        """Check if type_name already exists."""
        type_name = type_data.get('type_name', '')
        type_id = str(type_data.get('id', ''))
        
        result = self.session.execute(text("""
            SELECT id, type_name, domain_id, status
            FROM ontology.types
            WHERE type_name = :name
              AND id != :id
              AND status NOT IN ('DEPRECATED')
        """), {'name': type_name, 'id': type_id})
        
        row = result.fetchone()
        if row:
            return Collision(
                collision_type='NAME_COLLISION',
                proposed_type_id=type_id,
                proposed_type_name=type_name,
                existing_type_id=str(row.id),
                existing_type_name=row.type_name,
                existing_domain=row.domain_id,
            )
        
        return None
    
    def _check_uuid_collision(self, type_data: Dict) -> Optional[Collision]:
        """Check if UUID already exists."""
        type_id = str(type_data.get('id', ''))
        type_name = type_data.get('type_name', '')
        
        if not type_id:
            return None
        
        result = self.session.execute(text("""
            SELECT id, type_name, domain_id
            FROM ontology.types
            WHERE id = :id
              AND type_name != :name
        """), {'id': type_id, 'name': type_name})
        
        row = result.fetchone()
        if row:
            return Collision(
                collision_type='UUID_COLLISION',
                proposed_type_id=type_id,
                proposed_type_name=type_name,
                existing_type_id=str(row.id),
                existing_type_name=row.type_name,
                existing_domain=row.domain_id,
            )
        
        return None
    
    def _check_semantic_duplicates(self, type_data: Dict) -> List[Collision]:
        """Check for semantically similar types."""
        type_name = type_data.get('type_name', '')
        type_id = str(type_data.get('id', ''))
        
        duplicates = []
        
        result = self.session.execute(text("""
            SELECT id, type_name, domain_id, description
            FROM ontology.types
            WHERE id != :id
              AND status = 'ACTIVE'
              AND layer = :layer
        """), {'id': type_id, 'layer': type_data.get('layer', 2)})
        
        for row in result:
            similarity = self._compute_name_similarity(type_name, row.type_name)
            
            if similarity >= self.SIMILARITY_THRESHOLD:
                duplicates.append(Collision(
                    collision_type='SEMANTIC_DUPLICATE',
                    proposed_type_id=type_id,
                    proposed_type_name=type_name,
                    existing_type_id=str(row.id),
                    existing_type_name=row.type_name,
                    existing_domain=row.domain_id,
                    resolution=f"Similarity: {similarity:.2f} - Consider merging",
                ))
        
        return duplicates
    
    def _compute_name_similarity(self, name1: str, name2: str) -> float:
        """Compute similarity between two type names."""
        n1 = name1.lower()
        n2 = name2.lower()
        
        if n1 == n2:
            return 1.0
        
        if n1 in n2 or n2 in n1:
            return 0.85
        
        words1 = set(self._split_camel_case(name1))
        words2 = set(self._split_camel_case(name2))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def _split_camel_case(self, name: str) -> List[str]:
        """Split PascalCase into words."""
        import re
        words = re.findall(r'[A-Z][a-z]*|[a-z]+', name)
        return [w.lower() for w in words]
    
    def _collision_to_rule_result(self, collision: Collision) -> RuleResult:
        """Convert collision to RuleResult."""
        if collision.collision_type == 'NAME_COLLISION':
            return RuleResult(
                rule_name='no_name_collision',
                rule_type='NO_COLLISIONS',
                severity='ERROR',
                passed=False,
                message=f"Name collision: '{collision.proposed_type_name}' already exists (ID: {collision.existing_type_id})",
                target_id=collision.proposed_type_id,
                target_name=collision.proposed_type_name,
                details={
                    'collision_type': collision.collision_type,
                    'existing_type_id': collision.existing_type_id,
                    'existing_domain': collision.existing_domain,
                }
            )
        elif collision.collision_type == 'UUID_COLLISION':
            return RuleResult(
                rule_name='no_uuid_collision',
                rule_type='NO_COLLISIONS',
                severity='ERROR',
                passed=False,
                message=f"UUID collision: ID {collision.proposed_type_id} already assigned to '{collision.existing_type_name}'",
                target_id=collision.proposed_type_id,
                target_name=collision.proposed_type_name,
                details={
                    'collision_type': collision.collision_type,
                    'existing_type_name': collision.existing_type_name,
                }
            )
        else:
            return RuleResult(
                rule_name='no_semantic_duplicate',
                rule_type='NO_COLLISIONS',
                severity='WARNING',
                passed=False,
                message=f"Semantic duplicate: '{collision.proposed_type_name}' similar to '{collision.existing_type_name}'",
                target_id=collision.proposed_type_id,
                target_name=collision.proposed_type_name,
                details={
                    'collision_type': collision.collision_type,
                    'existing_type_name': collision.existing_type_name,
                    'resolution_hint': collision.resolution,
                }
            )
    
    def find_similar_types(self, type_name: str, threshold: float = 0.6) -> List[Dict]:
        """
        Find types similar to a given name.
        
        Useful for suggesting merges or identifying potential conflicts.
        """
        result = self.session.execute(text("""
            SELECT id, type_name, domain_id, description, status
            FROM ontology.types
            WHERE status IN ('ACTIVE', 'APPROVED')
        """))
        
        similar = []
        for row in result:
            similarity = self._compute_name_similarity(type_name, row.type_name)
            if similarity >= threshold:
                similar.append({
                    'id': str(row.id),
                    'type_name': row.type_name,
                    'domain_id': row.domain_id,
                    'similarity': similarity,
                    'status': row.status,
                })
        
        similar.sort(key=lambda x: x['similarity'], reverse=True)
        return similar
    
    def transition_to_contested(self, type_id: str, collision: Collision) -> bool:
        """
        Transition a type to CONTESTED status due to collision.
        
        Returns True if successful.
        """
        try:
            self.session.execute(text("""
                UPDATE ontology.types
                SET status = 'CONTESTED',
                    updated_at = NOW()
                WHERE id = :id AND status IN ('PROPOSED', 'VALIDATING')
            """), {'id': type_id})
            self.session.commit()
            logger.info(f"Type {type_id} transitioned to CONTESTED: {collision.collision_type}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to transition type {type_id} to CONTESTED: {e}")
            return False
