"""
Deprecation Manager (RFC v2 §7)

Handles the full type deprecation lifecycle:
ACTIVE → DEPRECATED → (grace period) → ARCHIVED/MIGRATED

Supports three deprecation actions:
- MIGRATE: Move entities to a replacement type
- ARCHIVE: Mark entities as ARCHIVED (preserved but inactive)
- DELETE: Remove entities with audit trail
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.context_foundry.models.schema import get_session, Entity
from src.context_foundry.ontology_foundry.schema_version_manager import SchemaVersionManager

logger = logging.getLogger(__name__)


@dataclass
class DeprecationResult:
    """Result of initiating a deprecation"""
    deprecation_id: str
    type_id: str
    type_name: str
    action: str
    replacement_type_id: Optional[str]
    replacement_type_name: Optional[str]
    grace_period_days: int
    deadline: datetime
    affected_entity_count: int
    affected_relationship_count: int


@dataclass
class MigrationResult:
    """Result of executing a deprecation migration"""
    deprecation_id: str
    action: str
    entities_processed: int
    relationships_processed: int
    success: bool
    errors: List[str]


@dataclass
class ImpactReport:
    """Impact analysis for a potential type deprecation"""
    type_id: str
    type_name: str
    entity_count: int
    relationship_count: int
    dependent_types: List[str]
    entities_by_state: Dict[str, int]
    sample_entities: List[Dict[str, Any]]


class DeprecationManager:
    """
    Manages type deprecation lifecycle.
    
    Key responsibilities:
    1. Mark types as DEPRECATED with grace period
    2. Create migration paths to replacement types
    3. Execute migrations after grace period
    4. Provide impact analysis before deprecation
    """
    
    def __init__(self, session: Session = None):
        self.session = session or get_session()
        self.version_manager = SchemaVersionManager(self.session)
    
    def deprecate_type(
        self,
        type_id: str,
        reason: str,
        action: str,
        replacement_type_id: str = None,
        grace_period_days: int = 30,
        initiated_by: str = None
    ) -> DeprecationResult:
        """
        Initiate deprecation of a type.
        
        Args:
            type_id: UUID of the type to deprecate
            reason: Human-readable explanation
            action: One of MIGRATE, ARCHIVE, DELETE
            replacement_type_id: Required for MIGRATE action
            grace_period_days: Days before migration executes
            initiated_by: UUID of the user initiating deprecation
            
        Returns:
            DeprecationResult with details and impact counts
        """
        if action not in ['MIGRATE', 'ARCHIVE', 'DELETE']:
            raise ValueError(f"Invalid action: {action}. Must be MIGRATE, ARCHIVE, or DELETE")
        
        if action == 'MIGRATE' and not replacement_type_id:
            raise ValueError("replacement_type_id is required for MIGRATE action")
        
        type_info = self.session.execute(
            text("SELECT type_name, status FROM ontology.types WHERE id = :id"),
            {"id": type_id}
        ).fetchone()
        
        if not type_info:
            raise ValueError(f"Type {type_id} not found")
        
        if type_info.status == 'DEPRECATED':
            raise ValueError(f"Type {type_info.type_name} is already deprecated")
        
        replacement_name = None
        if replacement_type_id:
            replacement_info = self.session.execute(
                text("SELECT type_name FROM ontology.types WHERE id = :id"),
                {"id": replacement_type_id}
            ).fetchone()
            replacement_name = replacement_info.type_name if replacement_info else None
        
        impact = self.get_deprecation_impact(type_id)
        
        deadline = datetime.utcnow() + timedelta(days=grace_period_days)
        
        self.session.execute(
            text("""
                UPDATE ontology.types 
                SET status = 'DEPRECATED',
                    description = COALESCE(description, '') || 
                        E'\n\n[DEPRECATED ' || :date || ']: ' || :reason
                WHERE id = :id
            """),
            {"id": type_id, "date": datetime.utcnow().isoformat()[:10], "reason": reason}
        )
        
        self.session.execute(
            text("""
                INSERT INTO ontology.type_migrations 
                    (source_type_id, target_type_id, migration_type, mapping_rules)
                VALUES 
                    (:source_id, COALESCE(:target_id, :source_id), :migration_type, :mapping_rules::jsonb)
            """),
            {
                "source_id": type_id,
                "target_id": replacement_type_id,
                "migration_type": 'SUPERSEDE' if action == 'MIGRATE' else action,
                "mapping_rules": json.dumps({
                    "action": action,
                    "reason": reason,
                    "deadline": deadline.isoformat(),
                    "initiated_by": initiated_by
                })
            }
        )
        
        self._record_deprecation_event(
            type_id=type_id,
            action=action,
            reason=reason,
            replacement_type_id=replacement_type_id,
            deadline=deadline,
            initiated_by=initiated_by
        )
        
        self.session.commit()
        
        logger.info(
            f"Deprecated type {type_info.type_name}: action={action}, "
            f"affected={impact.entity_count} entities, deadline={deadline.isoformat()[:10]}"
        )
        
        return DeprecationResult(
            deprecation_id=type_id,
            type_id=type_id,
            type_name=type_info.type_name,
            action=action,
            replacement_type_id=replacement_type_id,
            replacement_type_name=replacement_name,
            grace_period_days=grace_period_days,
            deadline=deadline,
            affected_entity_count=impact.entity_count,
            affected_relationship_count=impact.relationship_count
        )
    
    def execute_migration(self, type_id: str) -> MigrationResult:
        """
        Execute the pending deprecation migration for a type.
        
        Should be called after the grace period expires.
        
        Args:
            type_id: UUID of the deprecated type
            
        Returns:
            MigrationResult with counts and any errors
        """
        migration = self.session.execute(
            text("""
                SELECT m.id, m.migration_type, m.mapping_rules, m.target_type_id,
                       t.type_name as target_name
                FROM ontology.type_migrations m
                JOIN ontology.types t ON m.target_type_id = t.id
                WHERE m.source_type_id = :type_id
                  AND m.executed_at IS NULL
                ORDER BY m.created_at DESC
                LIMIT 1
            """),
            {"type_id": type_id}
        ).fetchone()
        
        if not migration:
            return MigrationResult(
                deprecation_id=type_id,
                action="NONE",
                entities_processed=0,
                relationships_processed=0,
                success=False,
                errors=["No pending migration found for this type"]
            )
        
        mapping_rules = migration.mapping_rules
        if isinstance(mapping_rules, str):
            try:
                mapping_rules = json.loads(mapping_rules)
            except (json.JSONDecodeError, TypeError):
                mapping_rules = {}
        elif mapping_rules is None:
            mapping_rules = {}
        
        action = mapping_rules.get('action', 'ARCHIVE')
        errors = []
        entities_processed = 0
        relationships_processed = 0
        
        try:
            if action == 'MIGRATE':
                entities_processed = self._migrate_entities(type_id, migration.target_type_id)
                relationships_processed = self._update_relationship_types(type_id, migration.target_type_id)
            elif action == 'ARCHIVE':
                entities_processed = self._archive_entities(type_id)
            elif action == 'DELETE':
                entities_processed = self._delete_entities(type_id)
            
            self.session.execute(
                text("""
                    UPDATE ontology.type_migrations 
                    SET executed_at = NOW(), entities_migrated = :count
                    WHERE id = :id
                """),
                {"id": migration.id, "count": entities_processed}
            )
            
            if action == 'ARCHIVE':
                self.session.execute(
                    text("UPDATE ontology.types SET status = 'ARCHIVED' WHERE id = :id"),
                    {"id": type_id}
                )
            elif action in ['MIGRATE', 'DELETE']:
                self.session.execute(
                    text("UPDATE ontology.types SET status = 'ARCHIVED' WHERE id = :id"),
                    {"id": type_id}
                )
            
            self.session.commit()
            success = True
            
        except Exception as e:
            self.session.rollback()
            errors.append(str(e))
            success = False
            logger.error(f"Migration failed for type {type_id}: {e}")
        
        logger.info(
            f"Migration executed for {type_id}: action={action}, "
            f"entities={entities_processed}, relationships={relationships_processed}, success={success}"
        )
        
        return MigrationResult(
            deprecation_id=type_id,
            action=action,
            entities_processed=entities_processed,
            relationships_processed=relationships_processed,
            success=success,
            errors=errors
        )
    
    def get_deprecation_impact(self, type_id: str) -> ImpactReport:
        """
        Analyze the impact of deprecating a type.
        
        Args:
            type_id: UUID of the type to analyze
            
        Returns:
            ImpactReport with entity counts, relationships, and dependencies
        """
        type_info = self.session.execute(
            text("SELECT type_name FROM ontology.types WHERE id = :id"),
            {"id": type_id}
        ).fetchone()
        
        if not type_info:
            raise ValueError(f"Type {type_id} not found")
        
        entity_count = self.session.execute(
            text("SELECT COUNT(*) FROM public.entities WHERE entity_type = :type_name"),
            {"type_name": type_info.type_name}
        ).scalar() or 0
        
        rel_count = self.session.execute(
            text("""
                SELECT COUNT(DISTINCT r.id) FROM public.relationships r
                JOIN public.entities e_source ON r.source_id = e_source.id
                JOIN public.entities e_target ON r.target_id = e_target.id
                WHERE e_source.entity_type = :type_name 
                   OR e_target.entity_type = :type_name
            """),
            {"type_name": type_info.type_name}
        ).scalar() or 0
        
        by_state = {}
        state_result = self.session.execute(
            text("""
                SELECT lifecycle_state, COUNT(*) as cnt 
                FROM public.entities 
                WHERE entity_type = :type_name
                GROUP BY lifecycle_state
            """),
            {"type_name": type_info.type_name}
        )
        for row in state_result:
            by_state[row.lifecycle_state] = row.cnt
        
        sample_entities = []
        sample_result = self.session.execute(
            text("""
                SELECT id, name, confidence, lifecycle_state
                FROM public.entities
                WHERE entity_type = :type_name
                ORDER BY confidence DESC
                LIMIT 5
            """),
            {"type_name": type_info.type_name}
        )
        for row in sample_result:
            sample_entities.append({
                "id": str(row.id),
                "name": row.name,
                "confidence": float(row.confidence) if row.confidence else 0,
                "lifecycle_state": row.lifecycle_state
            })
        
        dependent_types = []
        dep_result = self.session.execute(
            text("""
                SELECT DISTINCT unnest_type
                FROM ontology.relations r,
                     LATERAL (
                         SELECT unnest(source_types) as unnest_type
                         UNION
                         SELECT unnest(target_types)
                     ) types
                WHERE :type_name = ANY(r.source_types) 
                   OR :type_name = ANY(r.target_types)
            """),
            {"type_name": type_info.type_name}
        )
        for row in dep_result:
            if row.unnest_type and row.unnest_type != type_info.type_name:
                dependent_types.append(row.unnest_type)
        dependent_types = list(set(dependent_types))
        
        return ImpactReport(
            type_id=type_id,
            type_name=type_info.type_name,
            entity_count=entity_count,
            relationship_count=rel_count,
            dependent_types=dependent_types,
            entities_by_state=by_state,
            sample_entities=sample_entities
        )
    
    def _migrate_entities(self, source_type_id: str, target_type_id: str) -> int:
        """Migrate entities from source type to target type."""
        source_name = self.session.execute(
            text("SELECT type_name FROM ontology.types WHERE id = :id"),
            {"id": source_type_id}
        ).scalar()
        
        target_name = self.session.execute(
            text("SELECT type_name FROM ontology.types WHERE id = :id"),
            {"id": target_type_id}
        ).scalar()
        
        result = self.session.execute(
            text("""
                UPDATE public.entities 
                SET entity_type = :target_type,
                    properties = properties || jsonb_build_object(
                        '_migrated_from', :source_type,
                        '_migrated_at', :now
                    )
                WHERE entity_type = :source_type
            """),
            {
                "source_type": source_name,
                "target_type": target_name,
                "now": datetime.utcnow().isoformat()
            }
        )
        
        return result.rowcount
    
    def _archive_entities(self, type_id: str) -> int:
        """Mark entities as ARCHIVED."""
        type_name = self.session.execute(
            text("SELECT type_name FROM ontology.types WHERE id = :id"),
            {"id": type_id}
        ).scalar()
        
        result = self.session.execute(
            text("""
                UPDATE public.entities 
                SET lifecycle_state = 'ARCHIVED',
                    properties = properties || jsonb_build_object(
                        '_archived_at', :now,
                        '_archived_reason', 'type_deprecated'
                    )
                WHERE entity_type = :type_name
                  AND lifecycle_state != 'ARCHIVED'
            """),
            {"type_name": type_name, "now": datetime.utcnow().isoformat()}
        )
        
        return result.rowcount
    
    def _delete_entities(self, type_id: str) -> int:
        """Delete entities with audit trail."""
        type_name = self.session.execute(
            text("SELECT type_name FROM ontology.types WHERE id = :id"),
            {"id": type_id}
        ).scalar()
        
        self.session.execute(
            text("""
                INSERT INTO shared.audit_log (action, entity_type, entity_id, details)
                SELECT 'DELETE', entity_type, id, 
                       jsonb_build_object('name', name, 'confidence', confidence, 'reason', 'type_deprecated')
                FROM public.entities
                WHERE entity_type = :type_name
            """),
            {"type_name": type_name}
        )
        
        result = self.session.execute(
            text("DELETE FROM public.entities WHERE entity_type = :type_name"),
            {"type_name": type_name}
        )
        
        return result.rowcount
    
    def _update_relationship_types(self, source_type_id: str, target_type_id: str) -> int:
        """Update relationships where entities were migrated from source to target type."""
        source_name = self.session.execute(
            text("SELECT type_name FROM ontology.types WHERE id = :id"),
            {"id": source_type_id}
        ).scalar()
        
        target_name = self.session.execute(
            text("SELECT type_name FROM ontology.types WHERE id = :id"),
            {"id": target_type_id}
        ).scalar()
        
        result = self.session.execute(
            text("""
                UPDATE public.relationships r
                SET properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
                    '_migrated_source_type', :source_type,
                    '_migrated_target_type', :target_type,
                    '_migrated_at', :now
                )
                FROM public.entities e
                WHERE (r.source_id = e.id OR r.target_id = e.id)
                  AND e.properties->>'_migrated_from' = :source_type
            """),
            {
                "source_type": source_name,
                "target_type": target_name,
                "now": datetime.utcnow().isoformat()
            }
        )
        
        return result.rowcount
    
    def _record_deprecation_event(
        self,
        type_id: str,
        action: str,
        reason: str,
        replacement_type_id: Optional[str],
        deadline: datetime,
        initiated_by: Optional[str]
    ):
        """Record the deprecation in the audit log."""
        details = json.dumps({
            "action": action,
            "reason": reason,
            "replacement_type_id": replacement_type_id,
            "deadline": deadline.isoformat()
        })
        
        self.session.execute(
            text("""
                INSERT INTO shared.audit_log (action, entity_type, entity_id, details, user_id)
                VALUES (
                    'TYPE_DEPRECATED',
                    'OntologyType',
                    :type_id,
                    :details::jsonb,
                    :user_id
                )
            """),
            {
                "type_id": type_id,
                "details": details,
                "user_id": initiated_by
            }
        )
    
    def get_pending_deprecations(self) -> List[Dict[str, Any]]:
        """Get all types with pending deprecation migrations."""
        result = self.session.execute(
            text("""
                SELECT 
                    t.id, t.type_name, t.status,
                    m.mapping_rules->>'deadline' as deadline,
                    m.mapping_rules->>'action' as action
                FROM ontology.types t
                JOIN ontology.type_migrations m ON t.id = m.source_type_id
                WHERE t.status = 'DEPRECATED'
                  AND m.executed_at IS NULL
                ORDER BY m.mapping_rules->>'deadline' ASC
            """)
        )
        
        pending = []
        for row in result:
            pending.append({
                "type_id": str(row.id),
                "type_name": row.type_name,
                "deadline": row.deadline,
                "action": row.action
            })
        
        return pending
