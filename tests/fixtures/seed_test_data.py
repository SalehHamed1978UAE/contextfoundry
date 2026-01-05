"""
Test Data Seeder - Seeds canonical IT service architecture for E2E tests.

Week 4 Stabilization: Provides deterministic test data for E2E tests
that would otherwise skip when entities don't exist.

Usage:
    from tests.fixtures.seed_test_data import seed_canonical_test_data, cleanup_test_data
    
    # In pytest fixture:
    @pytest.fixture
    def seeded_data(db_session):
        data = seed_canonical_test_data(db_session, tenant_id=TEST_TENANT_ID)
        yield data
        cleanup_test_data(db_session, data)

NOTE: This requires a valid tenant context or RLS bypass for seeding.
If RLS is enforced, tests should skip gracefully.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
import os

from sqlalchemy.orm import Session
from sqlalchemy import text

from tests.fixtures.knowledge_graph import (
    CANONICAL_ENTITIES,
    CANONICAL_RELATIONSHIPS,
    STAGING_ENTITY,
    STAGING_RELATIONSHIP,
    TEST_TENANT_ID,
)


class TestDataSeeder:
    """Handles seeding and cleanup of canonical test data."""
    
    def __init__(self, session: Session, tenant_id: str = TEST_TENANT_ID):
        self.session = session
        self.tenant_id = tenant_id
        self.tenant_uuid = UUID(tenant_id)
        self.seeded_entity_ids = []
        self.seeded_relationship_ids = []
    
    def seed(self, include_staging: bool = False) -> Dict[str, Any]:
        """
        Seed canonical test data to the database.
        
        Returns:
            Dict with seeded entities and relationships
            
        Raises:
            Exception if RLS prevents seeding
        """
        from src.context_foundry.models.schema import Entity, Relationship, LifecycleState
        
        entities_by_fixture_id = {}
        relationships_by_fixture_id = {}
        
        for te in CANONICAL_ENTITIES:
            existing = self.session.query(Entity).filter(
                Entity.name == te.name,
                Entity.tenant_id == self.tenant_uuid
            ).first()
            
            if existing:
                entities_by_fixture_id[te.id] = existing
                continue
            
            entity = Entity(
                name=te.name,
                entity_type=te.entity_type,
                description=te.description,
                confidence=te.confidence,
                lifecycle_state=LifecycleState(te.lifecycle_state),
                tenant_id=self.tenant_uuid,
                properties={},
            )
            self.session.add(entity)
            self.session.flush()
            entities_by_fixture_id[te.id] = entity
            self.seeded_entity_ids.append(str(entity.id))
        
        if include_staging:
            te = STAGING_ENTITY
            existing = self.session.query(Entity).filter(
                Entity.name == te.name,
                Entity.tenant_id == self.tenant_uuid
            ).first()
            
            if not existing:
                entity = Entity(
                    name=te.name,
                    entity_type=te.entity_type,
                    description=te.description,
                    confidence=te.confidence,
                    lifecycle_state=LifecycleState(te.lifecycle_state),
                    tenant_id=self.tenant_uuid,
                    properties={},
                )
                self.session.add(entity)
                self.session.flush()
                entities_by_fixture_id[te.id] = entity
                self.seeded_entity_ids.append(str(entity.id))
            else:
                entities_by_fixture_id[te.id] = existing
        
        for tr in CANONICAL_RELATIONSHIPS:
            source = entities_by_fixture_id.get(tr.source_id)
            target = entities_by_fixture_id.get(tr.target_id)
            
            if not source or not target:
                continue
            
            existing = self.session.query(Relationship).filter(
                Relationship.source_id == source.id,
                Relationship.target_id == target.id,
                Relationship.relationship_type == tr.relationship_type,
                Relationship.tenant_id == self.tenant_uuid
            ).first()
            
            if existing:
                relationships_by_fixture_id[tr.id] = existing
                continue
            
            rel = Relationship(
                source_id=source.id,
                target_id=target.id,
                relationship_type=tr.relationship_type,
                confidence=tr.confidence,
                lifecycle_state=LifecycleState(tr.lifecycle_state),
                tenant_id=self.tenant_uuid,
                properties={},
            )
            self.session.add(rel)
            self.session.flush()
            relationships_by_fixture_id[tr.id] = rel
            self.seeded_relationship_ids.append(str(rel.id))
        
        if include_staging:
            tr = STAGING_RELATIONSHIP
            source = entities_by_fixture_id.get(tr.source_id)
            target = entities_by_fixture_id.get(tr.target_id)
            
            if source and target:
                existing = self.session.query(Relationship).filter(
                    Relationship.source_id == source.id,
                    Relationship.target_id == target.id,
                    Relationship.relationship_type == tr.relationship_type,
                    Relationship.tenant_id == self.tenant_uuid
                ).first()
                
                if not existing:
                    rel = Relationship(
                        source_id=source.id,
                        target_id=target.id,
                        relationship_type=tr.relationship_type,
                        confidence=tr.confidence,
                        lifecycle_state=LifecycleState(tr.lifecycle_state),
                        tenant_id=self.tenant_uuid,
                        properties={},
                    )
                    self.session.add(rel)
                    self.session.flush()
                    relationships_by_fixture_id[tr.id] = rel
                    self.seeded_relationship_ids.append(str(rel.id))
        
        return {
            "tenant_id": self.tenant_id,
            "entities": entities_by_fixture_id,
            "relationships": relationships_by_fixture_id,
            "seeded_entity_ids": self.seeded_entity_ids,
            "seeded_relationship_ids": self.seeded_relationship_ids,
        }
    
    def cleanup(self):
        """Remove seeded test data from database."""
        from src.context_foundry.models.schema import Entity, Relationship
        
        if self.seeded_relationship_ids:
            for rid in self.seeded_relationship_ids:
                try:
                    rel = self.session.query(Relationship).filter(
                        Relationship.id == UUID(rid)
                    ).first()
                    if rel:
                        self.session.delete(rel)
                except Exception:
                    pass
        
        if self.seeded_entity_ids:
            for eid in self.seeded_entity_ids:
                try:
                    entity = self.session.query(Entity).filter(
                        Entity.id == UUID(eid)
                    ).first()
                    if entity:
                        self.session.delete(entity)
                except Exception:
                    pass
        
        try:
            self.session.flush()
        except Exception:
            self.session.rollback()


def seed_canonical_test_data(
    session: Session,
    tenant_id: str = TEST_TENANT_ID,
    include_staging: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Seed canonical test data for E2E tests.
    
    Args:
        session: SQLAlchemy session
        tenant_id: Tenant UUID string
        include_staging: Include staging entities/relationships
        
    Returns:
        Dict with seeded data, or None if seeding failed
    """
    try:
        seeder = TestDataSeeder(session, tenant_id)
        return seeder.seed(include_staging=include_staging)
    except Exception as e:
        session.rollback()
        if "row-level security" in str(e).lower() or "insufficientprivilege" in str(e).lower():
            return None
        raise


def cleanup_test_data(session: Session, seeded_data: Dict[str, Any]):
    """Clean up seeded test data after tests."""
    if not seeded_data:
        return
    
    seeder = TestDataSeeder(session, seeded_data.get("tenant_id", TEST_TENANT_ID))
    seeder.seeded_entity_ids = seeded_data.get("seeded_entity_ids", [])
    seeder.seeded_relationship_ids = seeded_data.get("seeded_relationship_ids", [])
    seeder.cleanup()


def check_canonical_entities_exist(
    session: Session,
    tenant_id: str = None
) -> Dict[str, bool]:
    """
    Check which canonical entities exist in the database.
    
    Returns dict mapping entity names to existence status.
    """
    from src.context_foundry.models.schema import Entity
    
    results = {}
    for te in CANONICAL_ENTITIES:
        query = session.query(Entity).filter(Entity.name == te.name)
        if tenant_id:
            query = query.filter(Entity.tenant_id == UUID(tenant_id))
        exists = query.first() is not None
        results[te.name] = exists
    
    return results
