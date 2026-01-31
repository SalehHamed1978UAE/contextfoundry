"""
OntologyRepository - Database access layer for ontology.types and ontology.relations.

Queries the PostgreSQL ontology schema at extraction time to dynamically
load entity types and relationship constraints.
"""

import os
from typing import Dict, List, Optional, Set
from uuid import UUID
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

from ..utils.logger import logger
from .models import OntologyType, OntologyRelation, OntologySnapshot


class OntologyRepository:
    """
    Database access layer for the ontology system.
    
    Queries ontology.types and ontology.relations tables to provide
    dynamic schema information for extraction and validation.
    """
    
    def __init__(self, database_url: Optional[str] = None, tenant_id: Optional[UUID] = None):
        """
        Initialize the repository.
        
        Args:
            database_url: PostgreSQL connection string (uses DATABASE_URL env if not provided)
            tenant_id: Optional tenant ID for multi-tenant isolation
        """
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        self.tenant_id = tenant_id
        self._connection = None
        self._snapshot_cache: Optional[OntologySnapshot] = None
        self._cache_ttl_seconds = 300
        self._cache_loaded_at: Optional[datetime] = None
    
    def _get_connection(self):
        """Get or create database connection."""
        if self._connection is None or self._connection.closed:
            self._connection = psycopg2.connect(self.database_url)
        return self._connection
    
    def _close_connection(self):
        """Close database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
            self._connection = None
    
    def get_all_types(self, include_deprecated: bool = False, domain_id: Optional[str] = None) -> List[OntologyType]:
        """
        Get all entity types from ontology.types table.
        
        Returns types from layers 0-2 (system), plus tenant extensions (layer 3)
        if tenant_id is set.
        
        Args:
            include_deprecated: Include types with status != 'ACTIVE'
            domain_id: Filter by domain_id (e.g., 'IT', 'GENERIC')
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                base_query = """
                    SELECT id, type_name, layer, display_name, description,
                           parent_type_id, properties_schema, extraction_hints,
                           status, domain_id
                    FROM ontology.types
                    WHERE valid_to IS NULL
                """
                params = []
                
                if not include_deprecated:
                    base_query += " AND status = 'ACTIVE'"
                
                if domain_id:
                    base_query += " AND (domain_id = %s OR domain_id IS NULL)"
                    params.append(domain_id)
                
                base_query += " ORDER BY layer, type_name"
                
                cur.execute(base_query, params)
                rows = cur.fetchall()
                return [OntologyType(**row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching ontology types: {e}")
            raise
    
    def get_type_by_name(self, type_name: str) -> Optional[OntologyType]:
        """Get a specific entity type by name."""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, type_name, layer, display_name, description,
                           parent_type_id, properties_schema, extraction_hints,
                           status, domain_id
                    FROM ontology.types
                    WHERE type_name = %s
                    AND status = 'ACTIVE'
                    AND valid_to IS NULL
                    LIMIT 1
                """, (type_name,))
                
                row = cur.fetchone()
                return OntologyType(**row) if row else None
        except Exception as e:
            logger.error(f"Error fetching type {type_name}: {e}")
            raise
    
    def get_type_id(self, type_name: str) -> Optional[UUID]:
        """Get UUID for a type name (fast lookup)."""
        type_obj = self.get_type_by_name(type_name)
        return type_obj.id if type_obj else None
    
    def get_all_relations(self, include_deprecated: bool = False, domain_id: Optional[str] = None) -> List[OntologyRelation]:
        """
        Get all relationship types with source/target type names resolved.
        
        Args:
            include_deprecated: Include relations with status != 'ACTIVE'
            domain_id: Filter by domain_id
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                base_query = """
                    SELECT r.id, r.relation_type, r.source_type_id, r.target_type_id,
                           s.type_name as source_type_name,
                           t.type_name as target_type_name,
                           r.cardinality, r.description,
                           r.semantics, r.extraction_hints, r.status, r.domain_id
                    FROM ontology.relations r
                    JOIN ontology.types s ON r.source_type_id = s.id
                    JOIN ontology.types t ON r.target_type_id = t.id
                    WHERE r.valid_to IS NULL
                """
                params = []
                
                if not include_deprecated:
                    base_query += " AND r.status = 'ACTIVE'"
                
                if domain_id:
                    base_query += " AND (r.domain_id = %s OR r.domain_id IS NULL)"
                    params.append(domain_id)
                
                base_query += " ORDER BY r.relation_type, s.type_name, t.type_name"
                
                cur.execute(base_query, params)
                rows = cur.fetchall()
                return [OntologyRelation(**row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching ontology relations: {e}")
            raise
    
    def get_relations_for_type_pair(
        self, 
        source_type_name: str, 
        target_type_name: str
    ) -> List[OntologyRelation]:
        """Get valid relations between two entity types."""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT r.id, r.relation_type, r.source_type_id, r.target_type_id,
                           s.type_name as source_type_name,
                           t.type_name as target_type_name,
                           r.cardinality, r.description,
                           r.semantics, r.extraction_hints, r.status, r.domain_id
                    FROM ontology.relations r
                    JOIN ontology.types s ON r.source_type_id = s.id
                    JOIN ontology.types t ON r.target_type_id = t.id
                    WHERE s.type_name = %s
                    AND t.type_name = %s
                    AND r.status = 'ACTIVE'
                    AND r.valid_to IS NULL
                """, (source_type_name, target_type_name))
                
                rows = cur.fetchall()
                return [OntologyRelation(**row) for row in rows]
        except Exception as e:
            logger.error(f"Error fetching relations for {source_type_name} -> {target_type_name}: {e}")
            raise
    
    def normalize_type_name(self, input_type: str) -> Optional[str]:
        """
        Normalize type name to match exact ontology.types.type_name.
        
        Performs case-insensitive lookup and returns the canonical type name
        from the database. This ensures all outputs match the ontology exactly.
        
        Args:
            input_type: The type name from LLM output (may be any casing)
            
        Returns:
            Canonical type_name from database, or None if not found
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT type_name
                    FROM ontology.types
                    WHERE LOWER(type_name) = LOWER(%s)
                    AND status = 'ACTIVE'
                    AND valid_to IS NULL
                    LIMIT 1
                """, (input_type.strip(),))
                
                row = cur.fetchone()
                return row["type_name"] if row else None
        except Exception as e:
            logger.error(f"Error normalizing type {input_type}: {e}")
            return None
    
    def is_valid_type(self, type_name: str) -> bool:
        """Check if a type name exists in the ontology."""
        return self.get_type_by_name(type_name) is not None
    
    def get_valid_type_names(self) -> Set[str]:
        """Get set of all valid entity type names."""
        types = self.get_all_types()
        return {t.type_name for t in types}
    
    def get_snapshot(self, force_refresh: bool = False, domain_id: Optional[str] = None) -> OntologySnapshot:
        """
        Get a cached snapshot of the ontology for extraction.
        
        Caches the ontology for _cache_ttl_seconds to avoid repeated DB queries
        during a single extraction run.
        
        Args:
            force_refresh: Force reload from database
            domain_id: Filter by domain (e.g., 'IT', 'GENERIC')
        """
        now = datetime.utcnow()
        
        if (
            not force_refresh
            and self._snapshot_cache is not None
            and self._cache_loaded_at is not None
            and (now - self._cache_loaded_at).total_seconds() < self._cache_ttl_seconds
        ):
            return self._snapshot_cache
        
        logger.info(f"Loading fresh ontology snapshot from database (domain_id={domain_id})")
        types = self.get_all_types(domain_id=domain_id)
        relations = self.get_all_relations(domain_id=domain_id)
        
        types_dict = {t.type_name: t for t in types}
        
        type_hierarchy: Dict[str, List[str]] = {}
        for t in types:
            if t.parent_type_id:
                parent = next((p for p in types if p.id == t.parent_type_id), None)
                if parent:
                    if parent.type_name not in type_hierarchy:
                        type_hierarchy[parent.type_name] = []
                    type_hierarchy[parent.type_name].append(t.type_name)
        
        self._snapshot_cache = OntologySnapshot(
            types=types_dict,
            relations=relations,
            type_hierarchy=type_hierarchy,
            loaded_at=now
        )
        self._cache_loaded_at = now
        
        logger.info(f"Ontology snapshot loaded: {len(types)} types, {len(relations)} relations")
        return self._snapshot_cache
    
    def invalidate_cache(self):
        """Force cache refresh on next access."""
        self._snapshot_cache = None
        self._cache_loaded_at = None
    
    def __del__(self):
        """Cleanup connection on destruction."""
        self._close_connection()


_default_repository: Optional[OntologyRepository] = None


def get_ontology_repository() -> OntologyRepository:
    """Get the singleton ontology repository instance."""
    global _default_repository
    if _default_repository is None:
        _default_repository = OntologyRepository()
    return _default_repository
