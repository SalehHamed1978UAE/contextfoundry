"""
Schema Version Manager (RFC v2 §8)

Manages type version history and query translation for deprecated types.
Enables backward-compatible queries when types are renamed, merged, or deprecated.
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from uuid import UUID
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.context_foundry.models.schema import get_session

logger = logging.getLogger(__name__)


@dataclass
class TypeVersion:
    """Represents a single version of a type definition"""
    id: str
    type_id: str
    version: str
    schema_snapshot: Dict[str, Any]
    valid_from: datetime
    valid_until: Optional[datetime]
    migration_notes: Optional[str]
    breaking_change: bool
    created_at: datetime


@dataclass
class MigrationPath:
    """Represents a migration path between two types"""
    id: str
    source_type_id: str
    source_type_name: str
    target_type_id: str
    target_type_name: str
    migration_type: str
    mapping_rules: Optional[Dict[str, Any]]
    executed_at: Optional[datetime]
    entities_migrated: int


class SchemaVersionManager:
    """
    Manages type version history and query translation.
    
    Key responsibilities:
    1. Track version history of each type
    2. Translate deprecated type names to current active types
    3. Record type changes with schema snapshots
    4. Provide migration paths for type transitions
    """
    
    def __init__(self, session: Session = None):
        self.session = session or get_session()
    
    def get_type_lineage(self, type_name: str) -> List[TypeVersion]:
        """
        Get full version history of a type.
        
        Args:
            type_name: Name of the type to get history for
            
        Returns:
            List of TypeVersion objects ordered by valid_from (oldest first)
        """
        query = text("""
            SELECT 
                tv.id, tv.type_id, tv.version, tv.schema_snapshot,
                tv.valid_from, tv.valid_until, tv.migration_notes,
                tv.breaking_change, tv.created_at
            FROM ontology.type_versions tv
            JOIN ontology.types t ON tv.type_id = t.id
            WHERE t.type_name = :type_name
            ORDER BY tv.valid_from ASC
        """)
        
        result = self.session.execute(query, {"type_name": type_name})
        versions = []
        
        for row in result:
            versions.append(TypeVersion(
                id=str(row.id),
                type_id=str(row.type_id),
                version=row.version,
                schema_snapshot=row.schema_snapshot or {},
                valid_from=row.valid_from,
                valid_until=row.valid_until,
                migration_notes=row.migration_notes,
                breaking_change=row.breaking_change or False,
                created_at=row.created_at
            ))
        
        logger.info(f"Retrieved {len(versions)} versions for type '{type_name}'")
        return versions
    
    def translate_query(self, query_type: str) -> str:
        """
        Translate a deprecated type name to its current active replacement.
        
        Uses recursive CTE to traverse full migration chain (A → B → C).
        Works even when intermediate types are deprecated.
        
        Args:
            query_type: The type name to translate
            
        Returns:
            The current active type name, or the original if no translation exists
        """
        query = text("""
            WITH RECURSIVE migration_chain AS (
                -- Base case: start with the queried type
                SELECT 
                    t.id as type_id,
                    t.type_name,
                    t.status,
                    0 as depth
                FROM ontology.types t
                WHERE t.type_name = :type_name
                
                UNION ALL
                
                -- Recursive case: follow migration paths
                SELECT 
                    target.id,
                    target.type_name,
                    target.status,
                    mc.depth + 1
                FROM migration_chain mc
                JOIN ontology.type_migrations m ON m.source_type_id = mc.type_id
                JOIN ontology.types target ON m.target_type_id = target.id
                WHERE mc.depth < 10  -- Prevent infinite recursion
            )
            SELECT type_name, status
            FROM migration_chain
            WHERE status = 'ACTIVE'
            ORDER BY depth DESC
            LIMIT 1
        """)
        
        result = self.session.execute(query, {"type_name": query_type.upper()}).fetchone()
        
        if result:
            translated = result.type_name
            if translated != query_type.upper():
                logger.info(f"Query type translation: '{query_type}' → '{translated}'")
            return translated
        
        check_exists = text("SELECT type_name, status FROM ontology.types WHERE type_name = :name")
        exists = self.session.execute(check_exists, {"name": query_type.upper()}).fetchone()
        
        if exists and exists.status == 'ACTIVE':
            return exists.type_name
        
        return query_type.upper()
    
    def record_version(
        self,
        type_id: str,
        version: str,
        schema_snapshot: Dict[str, Any],
        migration_notes: str = None,
        breaking_change: bool = False,
        created_by: str = None
    ) -> TypeVersion:
        """
        Record a new version of a type definition.
        
        Automatically closes the previous version's valid_until timestamp.
        
        Args:
            type_id: UUID of the type
            version: Semantic version string (e.g., "1.0.0", "1.1.0")
            schema_snapshot: Full type definition at this version
            migration_notes: Human-readable description of changes
            breaking_change: Whether this requires entity migration
            created_by: UUID of the user making the change
            
        Returns:
            The newly created TypeVersion
        """
        now = datetime.utcnow()
        
        close_previous = text("""
            UPDATE ontology.type_versions 
            SET valid_until = :now
            WHERE type_id = :type_id 
              AND valid_until IS NULL
        """)
        self.session.execute(close_previous, {"type_id": type_id, "now": now})
        
        insert_query = text("""
            INSERT INTO ontology.type_versions 
                (type_id, version, schema_snapshot, valid_from, migration_notes, 
                 breaking_change, created_by)
            VALUES 
                (:type_id, :version, :schema_snapshot, :valid_from, :migration_notes,
                 :breaking_change, :created_by)
            RETURNING id, created_at
        """)
        
        result = self.session.execute(insert_query, {
            "type_id": type_id,
            "version": version,
            "schema_snapshot": json.dumps(schema_snapshot),
            "valid_from": now,
            "migration_notes": migration_notes,
            "breaking_change": breaking_change,
            "created_by": created_by
        }).fetchone()
        
        self.session.commit()
        
        new_version = TypeVersion(
            id=str(result.id),
            type_id=type_id,
            version=version,
            schema_snapshot=schema_snapshot,
            valid_from=now,
            valid_until=None,
            migration_notes=migration_notes,
            breaking_change=breaking_change,
            created_at=result.created_at
        )
        
        logger.info(f"Recorded version {version} for type {type_id} (breaking={breaking_change})")
        return new_version
    
    def get_migration_path(self, source_type: str, target_type: str) -> Optional[MigrationPath]:
        """
        Get the migration path between two types.
        
        Args:
            source_type: Name of the source type
            target_type: Name of the target type
            
        Returns:
            MigrationPath if one exists, None otherwise
        """
        query = text("""
            SELECT 
                m.id, m.source_type_id, m.target_type_id,
                m.migration_type, m.mapping_rules, 
                m.executed_at, m.entities_migrated,
                s.type_name as source_name,
                t.type_name as target_name
            FROM ontology.type_migrations m
            JOIN ontology.types s ON m.source_type_id = s.id
            JOIN ontology.types t ON m.target_type_id = t.id
            WHERE s.type_name = :source_type
              AND t.type_name = :target_type
            LIMIT 1
        """)
        
        result = self.session.execute(query, {
            "source_type": source_type.upper(),
            "target_type": target_type.upper()
        }).fetchone()
        
        if result is None:
            return None
        
        return MigrationPath(
            id=str(result.id),
            source_type_id=str(result.source_type_id),
            source_type_name=result.source_name,
            target_type_id=str(result.target_type_id),
            target_type_name=result.target_name,
            migration_type=result.migration_type,
            mapping_rules=result.mapping_rules,
            executed_at=result.executed_at,
            entities_migrated=result.entities_migrated or 0
        )
    
    def create_migration(
        self,
        source_type_id: str,
        target_type_id: str,
        migration_type: str,
        mapping_rules: Dict[str, Any] = None
    ) -> MigrationPath:
        """
        Create a new migration path between types.
        
        Args:
            source_type_id: UUID of the source type
            target_type_id: UUID of the target type
            migration_type: One of RENAME, MERGE, SPLIT, SUPERSEDE
            mapping_rules: Property transformation rules
            
        Returns:
            The created MigrationPath
        """
        if migration_type not in ['RENAME', 'MERGE', 'SPLIT', 'SUPERSEDE']:
            raise ValueError(f"Invalid migration_type: {migration_type}")
        
        query = text("""
            INSERT INTO ontology.type_migrations 
                (source_type_id, target_type_id, migration_type, mapping_rules)
            VALUES 
                (:source_id, :target_id, :migration_type, :mapping_rules)
            RETURNING id
        """)
        
        result = self.session.execute(query, {
            "source_id": source_type_id,
            "target_id": target_type_id,
            "migration_type": migration_type,
            "mapping_rules": json.dumps(mapping_rules) if mapping_rules else None
        }).fetchone()
        
        self.session.commit()
        
        names_query = text("""
            SELECT s.type_name as source_name, t.type_name as target_name
            FROM ontology.types s, ontology.types t
            WHERE s.id = :source_id AND t.id = :target_id
        """)
        names = self.session.execute(names_query, {
            "source_id": source_type_id,
            "target_id": target_type_id
        }).fetchone()
        
        logger.info(f"Created {migration_type} migration: {names.source_name} → {names.target_name}")
        
        return MigrationPath(
            id=str(result.id),
            source_type_id=source_type_id,
            source_type_name=names.source_name,
            target_type_id=target_type_id,
            target_type_name=names.target_name,
            migration_type=migration_type,
            mapping_rules=mapping_rules,
            executed_at=None,
            entities_migrated=0
        )
    
    def get_current_version(self, type_name: str) -> Optional[TypeVersion]:
        """Get the current (valid_until IS NULL) version of a type."""
        query = text("""
            SELECT 
                tv.id, tv.type_id, tv.version, tv.schema_snapshot,
                tv.valid_from, tv.valid_until, tv.migration_notes,
                tv.breaking_change, tv.created_at
            FROM ontology.type_versions tv
            JOIN ontology.types t ON tv.type_id = t.id
            WHERE t.type_name = :type_name
              AND tv.valid_until IS NULL
            LIMIT 1
        """)
        
        result = self.session.execute(query, {"type_name": type_name}).fetchone()
        
        if result is None:
            return None
        
        return TypeVersion(
            id=str(result.id),
            type_id=str(result.type_id),
            version=result.version,
            schema_snapshot=result.schema_snapshot or {},
            valid_from=result.valid_from,
            valid_until=result.valid_until,
            migration_notes=result.migration_notes,
            breaking_change=result.breaking_change or False,
            created_at=result.created_at
        )
