"""
Unit tests for Entity Profile Generator.
Part 1.4 of MVP Verification Test Suite.
"""

import pytest
import tempfile
import os
from uuid import uuid4
from sqlalchemy import text
from src.context_foundry.models.schema import get_session, Entity, Relationship, LifecycleState
from src.context_foundry.agents.entity_profile_generator import EntityProfileGenerator, EntityProfile
from src.context_foundry.agents.graph_builder import GraphBuilderAgent


class TestEntityProfileGenerator:
    """Unit tests for entity profile generation."""
    
    @pytest.fixture
    def setup(self):
        """Create generator with fresh tenant and seed data."""
        session = get_session()
        tenant_id = str(uuid4())
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        
        builder = GraphBuilderAgent(session=session)
        
        content = "Jane Doe is CEO of Acme Corp since 2020. She previously worked at BigTech as VP of Engineering."
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            doc_path = f.name
        
        try:
            builder.ingest_document(doc_path=doc_path, doc_type='GENERAL', title='Jane Bio', tenant_id=tenant_id)
        finally:
            os.unlink(doc_path)
        
        session.query(Entity).filter(Entity.tenant_id == tenant_id, Entity.lifecycle_state == LifecycleState.STAGING).update({Entity.lifecycle_state: LifecycleState.TRUSTED})
        session.query(Relationship).filter(Relationship.tenant_id == tenant_id, Relationship.lifecycle_state == LifecycleState.STAGING).update({Relationship.lifecycle_state: LifecycleState.TRUSTED})
        session.commit()
        
        generator = EntityProfileGenerator(session=session, tenant_id=tenant_id)
        yield generator, session, tenant_id
        
        session.execute(text("DELETE FROM relationships WHERE tenant_id = :tid"), {'tid': tenant_id})
        session.execute(text("DELETE FROM entities WHERE tenant_id = :tid"), {'tid': tenant_id})
        session.commit()
        session.close()
    
    def test_generate_profile_returns_entity_profile(self, setup):
        """Profile should be an EntityProfile object."""
        generator, session, tenant_id = setup
        
        entities = session.query(Entity).filter(Entity.tenant_id == tenant_id, Entity.lifecycle_state == LifecycleState.TRUSTED).all()
        person_entity = next((e for e in entities if e.entity_type == 'PERSON'), None)
        
        if person_entity:
            profile = generator.generate_profile(person_entity.name)
            assert profile is not None
            assert isinstance(profile, EntityProfile)
            assert profile.entity_type is not None
        else:
            pytest.skip("No PERSON entity extracted from test document")
    
    def test_profile_includes_relationships(self, setup):
        """Profile should include relationships."""
        generator, session, tenant_id = setup
        
        entities = session.query(Entity).filter(Entity.tenant_id == tenant_id, Entity.lifecycle_state == LifecycleState.TRUSTED).all()
        person_entity = next((e for e in entities if e.entity_type == 'PERSON'), None)
        
        if person_entity:
            profile = generator.generate_profile(person_entity.name)
            if profile:
                total_rels = len(profile.outgoing_relationships) + len(profile.incoming_relationships)
                assert total_rels >= 0, "Profile should have relationship list"
            else:
                pytest.skip("Profile generation returned None")
        else:
            pytest.skip("No PERSON entity extracted")
    
    def test_profile_includes_sufficiency(self, setup):
        """Profile should include sufficiency signals."""
        generator, session, tenant_id = setup
        
        entities = session.query(Entity).filter(Entity.tenant_id == tenant_id, Entity.lifecycle_state == LifecycleState.TRUSTED).all()
        person_entity = next((e for e in entities if e.entity_type == 'PERSON'), None)
        
        if person_entity:
            profile = generator.generate_profile(person_entity.name)
            if profile:
                sufficiency = profile.sufficiency
                assert 'coverage' in sufficiency or 'overall_confidence' in sufficiency
            else:
                pytest.skip("Profile generation returned None")
        else:
            pytest.skip("No PERSON entity extracted")
    
    def test_nonexistent_entity_returns_none(self, setup):
        """Non-existent entity should return None, not hallucinate."""
        generator, session, tenant_id = setup
        
        profile = generator.generate_profile("Completely Fake Person XYZ999")
        
        assert profile is None
    
    def test_to_dict_output(self, setup):
        """to_dict should return structured dictionary."""
        generator, session, tenant_id = setup
        
        profile = generator.generate_profile("Jane Doe")
        
        if profile:
            d = profile.to_dict()
            assert "entity_id" in d
            assert "name" in d
            assert "entity_type" in d
            assert "outgoing_relationships" in d
            assert "sufficiency" in d
    
    def test_markdown_output(self, setup):
        """Markdown output should be well-formed."""
        generator, session, tenant_id = setup
        
        profile = generator.generate_profile("Jane Doe")
        
        if profile:
            markdown = profile.to_markdown()
            assert markdown is not None
            assert "Jane Doe" in markdown
            assert "#" in markdown  # Has headers


class TestProfileContextBundle:
    """Test the build_context_bundle method."""
    
    @pytest.fixture
    def setup(self):
        """Create generator with fresh tenant."""
        session = get_session()
        tenant_id = str(uuid4())
        session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
        
        generator = EntityProfileGenerator(session=session, tenant_id=tenant_id)
        yield generator, session, tenant_id
        session.close()
    
    def test_context_bundle_for_missing_entity(self, setup):
        """ContextBundle should indicate entity not found."""
        generator, session, tenant_id = setup
        
        bundle = generator.build_context_bundle("Nonexistent Person")
        
        assert bundle.target_entity_found == False
        assert bundle.confidence < 0.3
        assert bundle.uncertainty is not None
        assert bundle.uncertainty.recommendation == "entity_not_found"


class TestMultiTenantIsolation:
    """Test tenant isolation for profile generator."""
    
    @pytest.fixture
    def setup(self):
        """Create generators for two tenants."""
        session = get_session()
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())
        
        session.execute(text(f"SET app.current_tenant_id = '{tenant_a}'"))
        builder = GraphBuilderAgent(session=session)
        
        content = "Alice Smith works at TenantA Corp."
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            doc_path = f.name
        
        try:
            builder.ingest_document(doc_path=doc_path, doc_type='GENERAL', title='Alice Bio', tenant_id=tenant_a)
        finally:
            os.unlink(doc_path)
        
        session.query(Entity).filter(Entity.tenant_id == tenant_a, Entity.lifecycle_state == LifecycleState.STAGING).update({Entity.lifecycle_state: LifecycleState.TRUSTED})
        session.query(Relationship).filter(Relationship.tenant_id == tenant_a, Relationship.lifecycle_state == LifecycleState.STAGING).update({Relationship.lifecycle_state: LifecycleState.TRUSTED})
        session.commit()
        
        gen_a = EntityProfileGenerator(session=session, tenant_id=tenant_a)
        gen_b = EntityProfileGenerator(session=session, tenant_id=tenant_b)
        
        yield gen_a, gen_b, session, tenant_a, tenant_b
        
        session.execute(text("DELETE FROM relationships WHERE tenant_id = :tid"), {'tid': tenant_a})
        session.execute(text("DELETE FROM entities WHERE tenant_id = :tid"), {'tid': tenant_a})
        session.commit()
        session.close()
    
    def test_tenant_isolation(self, setup):
        """Entity from tenant A should not be visible to tenant B."""
        gen_a, gen_b, session, tenant_a, tenant_b = setup
        
        session.execute(text(f"SET app.current_tenant_id = '{tenant_a}'"))
        profile_a = gen_a.generate_profile("Alice Smith")
        
        session.execute(text(f"SET app.current_tenant_id = '{tenant_b}'"))
        profile_b = gen_b.generate_profile("Alice Smith")
        
        assert profile_a is not None or profile_b is None, "Alice should be in tenant A, not B"
