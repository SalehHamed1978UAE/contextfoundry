"""
SemanticMemoryAPI - Entity-focused memory operations for RLM REPL.

Wraps the entities table to provide entity lookup, semantic search,
and property-based queries.
"""

import os
from datetime import datetime
from typing import Optional, List
from sqlalchemy import func, or_, and_, text
from sqlalchemy.orm import Session

from ..schemas import (
    EntitySummary,
    EntityDetail,
    EntityMatch,
    LifecycleState,
    StaleEntityError,
)


class SemanticMemoryAPI:
    """
    Exposes semantic memory operations to RLM REPL environment.
    
    All methods are tenant-scoped and track accessed entity IDs
    for progress tracking.
    """
    
    def __init__(self, tenant_id: str, session: Session):
        self._tenant_id = tenant_id
        self._session = session
        self._accessed_entity_ids: List[str] = []
    
    def get_accessed_entity_ids(self) -> List[str]:
        """Returns list of entity IDs accessed during this session."""
        return list(set(self._accessed_entity_ids))
    
    def clear_access_tracking(self):
        """Clear the accessed entity tracking."""
        self._accessed_entity_ids = []
    
    def find_entities(
        self, 
        entity_type: str = None, 
        limit: int = 50,
        include_staging: bool = True
    ) -> List[EntitySummary]:
        """
        List entities, optionally filtered by type.
        
        Args:
            entity_type: Filter by type (e.g., "SERVICE", "PERSON")
            limit: Maximum entities to return (default 50)
            include_staging: Include STAGING entities (default True)
        
        Returns:
            List of EntitySummary objects
        """
        from src.context_foundry.models.schema import Entity, Relationship
        
        query = self._session.query(Entity).filter(
            Entity.tenant_id == self._tenant_id
        )
        
        if not include_staging:
            query = query.filter(Entity.lifecycle_state == LifecycleState.TRUSTED)
        else:
            query = query.filter(Entity.lifecycle_state.in_([
                LifecycleState.STAGING, 
                LifecycleState.TRUSTED
            ]))
        
        if entity_type:
            query = query.filter(Entity.entity_type == entity_type.upper())
        
        entities = query.order_by(Entity.confidence.desc()).limit(limit).all()
        
        results = []
        for e in entities:
            rel_count = self._session.query(func.count(Relationship.id)).filter(
                or_(
                    Relationship.source_id == e.id,
                    Relationship.target_id == e.id
                )
            ).scalar() or 0
            
            self._accessed_entity_ids.append(str(e.id))
            
            primary_prop = None
            if e.properties:
                for key in ['status', 'title', 'role', 'description']:
                    if key in e.properties:
                        primary_prop = f"{key}: {e.properties[key]}"
                        break
            
            results.append(EntitySummary(
                id=str(e.id),
                name=e.name,
                entity_type=e.entity_type,
                confidence=e.confidence or 0.5,
                lifecycle_state=LifecycleState(e.lifecycle_state.value),
                created_at=e.created_at or datetime.utcnow(),
                updated_at=e.updated_at or datetime.utcnow(),
                primary_property=primary_prop,
                property_count=len(e.properties) if e.properties else 0,
                relationship_count=rel_count
            ))
        
        return results
    
    def find_similar(
        self, 
        query: str, 
        k: int = 10,
        entity_type: str = None,
        min_confidence: float = 0.0,
        include_staging: bool = True
    ) -> List[EntityMatch]:
        """
        Semantic search for entities matching query.
        
        Falls back to text-based search if entities don't have embeddings.
        
        Args:
            query: Search query text
            k: Number of results (default 10)
            entity_type: Filter by type
            min_confidence: Minimum confidence threshold
            include_staging: Include STAGING entities (default True)
        
        Returns:
            List of EntityMatch objects with similarity scores
        """
        from src.context_foundry.models.schema import Entity, Relationship
        
        lifecycle_filter = [LifecycleState.TRUSTED]
        if include_staging:
            lifecycle_filter.append(LifecycleState.STAGING)
        
        lifecycle_values = ",".join(f"'{ls.value}'" for ls in lifecycle_filter)
        entity_type_clause = "AND entity_type = :entity_type" if entity_type else ""
        
        check_sql = text("""
            SELECT COUNT(*) FROM entities 
            WHERE tenant_id = :tenant_id AND name_embedding IS NOT NULL
            LIMIT 1
        """)
        has_embeddings = self._session.execute(check_sql, {"tenant_id": str(self._tenant_id)}).scalar() > 0
        
        if has_embeddings:
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=query
            )
            query_embedding = response.data[0].embedding
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            
            sql = text(f"""
                SELECT 
                    id, name, entity_type, confidence, lifecycle_state,
                    created_at, updated_at, properties, description,
                    1 - (name_embedding <=> '{embedding_str}'::vector) as similarity
                FROM entities
                WHERE tenant_id = :tenant_id
                AND lifecycle_state::text = ANY(ARRAY[{lifecycle_values}])
                AND name_embedding IS NOT NULL
                AND confidence >= :min_confidence
                {entity_type_clause}
                ORDER BY name_embedding <=> '{embedding_str}'::vector
                LIMIT :limit
            """)
        else:
            query_lower = query.lower()
            query_words = query_lower.split()
            like_conditions = " OR ".join(
                f"LOWER(name) LIKE '%{word}%'" for word in query_words if len(word) > 2
            )
            if not like_conditions:
                like_conditions = f"LOWER(name) LIKE '%{query_lower}%'"
            
            sql = text(f"""
                SELECT 
                    id, name, entity_type, confidence, lifecycle_state,
                    created_at, updated_at, properties, description,
                    CASE 
                        WHEN LOWER(name) = :query_lower THEN 1.0
                        WHEN LOWER(name) LIKE :query_prefix THEN 0.9
                        WHEN LOWER(name) LIKE :query_contains THEN 0.7
                        ELSE 0.5
                    END as similarity
                FROM entities
                WHERE tenant_id = :tenant_id
                AND lifecycle_state::text = ANY(ARRAY[{lifecycle_values}])
                AND ({like_conditions})
                AND confidence >= :min_confidence
                {entity_type_clause}
                ORDER BY similarity DESC, confidence DESC
                LIMIT :limit
            """)
        
        params = {
            "tenant_id": str(self._tenant_id),
            "min_confidence": min_confidence,
            "limit": k,
            "query_lower": query.lower(),
            "query_prefix": f"{query.lower()}%",
            "query_contains": f"%{query.lower()}%",
        }
        if entity_type:
            params["entity_type"] = entity_type.upper()
        
        rows = self._session.execute(sql, params).fetchall()
        
        results = []
        for row in rows:
            self._accessed_entity_ids.append(str(row.id))
            
            rel_count = self._session.query(func.count(Relationship.id)).filter(
                or_(
                    Relationship.source_id == row.id,
                    Relationship.target_id == row.id
                )
            ).scalar() or 0
            
            properties = row.properties or {}
            primary_prop = None
            for key in ['status', 'title', 'role', 'description']:
                if key in properties:
                    primary_prop = f"{key}: {properties[key]}"
                    break
            
            entity_summary = EntitySummary(
                id=str(row.id),
                name=row.name,
                entity_type=row.entity_type,
                confidence=row.confidence or 0.5,
                lifecycle_state=LifecycleState(row.lifecycle_state),
                created_at=row.created_at or datetime.utcnow(),
                updated_at=row.updated_at or datetime.utcnow(),
                primary_property=primary_prop,
                property_count=len(properties),
                relationship_count=rel_count
            )
            
            match_type = "semantic"
            if row.similarity >= 0.99:
                match_type = "exact"
            elif row.similarity < 0.75:
                match_type = "fuzzy"
            
            results.append(EntityMatch(
                entity=entity_summary,
                similarity_score=row.similarity,
                match_type=match_type
            ))
        
        return results
    
    def get_entity(self, entity_id: str) -> EntityDetail:
        """
        Get full entity details including properties.
        
        Args:
            entity_id: Entity UUID
        
        Returns:
            EntityDetail object
        
        Raises:
            StaleEntityError: If entity no longer exists
        """
        from src.context_foundry.models.schema import Entity
        
        entity = self._session.query(Entity).filter(
            Entity.id == entity_id,
            Entity.tenant_id == self._tenant_id
        ).first()
        
        if not entity:
            raise StaleEntityError(entity_id)
        
        self._accessed_entity_ids.append(str(entity.id))
        
        aliases = []
        if entity.properties and 'aliases' in entity.properties:
            aliases = entity.properties.get('aliases', [])
        
        source_doc_ids = []
        if entity.source_document_id:
            source_doc_ids.append(entity.source_document_id)
        
        corroboration = 1
        if entity.properties and 'corroboration_count' in entity.properties:
            corroboration = entity.properties.get('corroboration_count', 1)
        
        return EntityDetail(
            id=str(entity.id),
            name=entity.name,
            entity_type=entity.entity_type,
            confidence=entity.confidence or 0.5,
            lifecycle_state=LifecycleState(entity.lifecycle_state.value),
            created_at=entity.created_at or datetime.utcnow(),
            updated_at=entity.updated_at or datetime.utcnow(),
            properties=entity.properties or {},
            aliases=aliases,
            source_document_ids=source_doc_ids,
            extraction_method=entity.extraction_method or "unknown",
            corroboration_count=corroboration,
            last_verified_at=entity.last_validated_at,
            promoted_at=entity.promoted_at
        )
    
    def find_by_property(
        self, 
        property_name: str,
        property_value: str,
        include_staging: bool = True
    ) -> List[EntitySummary]:
        """
        Find entities with matching property values.
        
        Args:
            property_name: Property key to search
            property_value: Property value to match
            include_staging: Include STAGING entities (default True)
        
        Returns:
            List of EntitySummary objects
        """
        from src.context_foundry.models.schema import Entity, Relationship
        
        lifecycle_filter = [LifecycleState.TRUSTED]
        if include_staging:
            lifecycle_filter.append(LifecycleState.STAGING)
        
        query = self._session.query(Entity).filter(
            Entity.tenant_id == self._tenant_id,
            Entity.lifecycle_state.in_(lifecycle_filter),
            Entity.properties[property_name].astext == property_value
        )
        
        entities = query.order_by(Entity.confidence.desc()).limit(50).all()
        
        results = []
        for e in entities:
            rel_count = self._session.query(func.count(Relationship.id)).filter(
                or_(
                    Relationship.source_id == e.id,
                    Relationship.target_id == e.id
                )
            ).scalar() or 0
            
            self._accessed_entity_ids.append(str(e.id))
            
            primary_prop = f"{property_name}: {property_value}"
            
            results.append(EntitySummary(
                id=str(e.id),
                name=e.name,
                entity_type=e.entity_type,
                confidence=e.confidence or 0.5,
                lifecycle_state=LifecycleState(e.lifecycle_state.value),
                created_at=e.created_at or datetime.utcnow(),
                updated_at=e.updated_at or datetime.utcnow(),
                primary_property=primary_prop,
                property_count=len(e.properties) if e.properties else 0,
                relationship_count=rel_count
            ))
        
        return results
    
    def get_lifecycle_state(self, entity_id: str) -> str:
        """
        Returns lifecycle state of an entity.
        
        Args:
            entity_id: Entity UUID
        
        Returns:
            "STAGING", "TRUSTED", or "ARCHIVED"
        
        Raises:
            StaleEntityError: If entity no longer exists
        """
        from src.context_foundry.models.schema import Entity
        
        entity = self._session.query(Entity).filter(
            Entity.id == entity_id,
            Entity.tenant_id == self._tenant_id
        ).first()
        
        if not entity:
            raise StaleEntityError(entity_id)
        
        return entity.lifecycle_state.value
