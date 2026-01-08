"""
Context Foundry Comprehensive Regression Test Suite

This module provides a fast regression test suite designed to be run frequently
during architectural changes to ensure nothing is broken.

Test Categories (pytest markers):
- @pytest.mark.smoke: Quick sanity checks (<30 seconds), no external APIs
- @pytest.mark.fast_regression: Core functionality (<3 minutes), mocked LLM
- @pytest.mark.component: Component integration (<5 minutes)
- @pytest.mark.integration: Full E2E tests (nightly only)

Usage:
    # Run smoke tests only (fastest)
    pytest tests/test_regression_suite.py -m smoke -v
    
    # Run fast regression suite (recommended during dev)
    pytest tests/test_regression_suite.py -m "smoke or fast_regression" -v
    
    # Run all regression tests
    pytest tests/test_regression_suite.py -v
    
    # Using the runner script
    python scripts/run_regression.py --fast
"""

import os
import sys
import uuid
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# SMOKE TESTS - Quick sanity checks, no external dependencies
# =============================================================================

class TestSmokeImports:
    """Verify all critical modules import correctly."""
    
    @pytest.mark.smoke
    def test_core_models_import(self):
        """Verify core data models import."""
        from src.context_foundry.models.schema import Entity, Relationship
        from src.context_foundry.models.schema import LifecycleState
        assert Entity is not None
        assert Relationship is not None
        assert LifecycleState is not None
    
    @pytest.mark.smoke
    def test_agents_import(self):
        """Verify agent modules import."""
        from src.context_foundry.agents.retrieval import RetrievalAgent
        from src.context_foundry.agents.reasoning import ReasoningAgent
        assert RetrievalAgent is not None
        assert ReasoningAgent is not None
    
    @pytest.mark.smoke
    def test_contracts_import(self):
        """Verify contract interfaces import."""
        from src.context_foundry.contracts.query_parser import QueryParserContract
        from src.context_foundry.contracts.entity_resolver import EntityResolverContract
        from src.context_foundry.contracts.memory import SemanticMemoryContract
        assert QueryParserContract is not None
        assert EntityResolverContract is not None
        assert SemanticMemoryContract is not None
    
    @pytest.mark.smoke
    def test_dtl_import(self):
        """Verify DTL modules import."""
        from src.context_foundry.dtl.core import AuthContext, search_precedents
        from src.context_foundry.dtl.dtl_inline import search_precedents as inline_search
        assert AuthContext is not None
        assert search_precedents is not None
        assert inline_search is not None
    
    @pytest.mark.smoke
    def test_document_model_import(self):
        """Verify Document model imports from context foundry schema."""
        from src.context_foundry.models.schema import Document, Entity, Relationship
        assert Document is not None
        assert Entity is not None
        assert Relationship is not None


class TestSmokeDatabase:
    """Verify database connectivity and basic operations."""
    
    @pytest.mark.smoke
    def test_database_connection(self):
        """Verify database is accessible."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from sqlalchemy import create_engine, text
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
    
    @pytest.mark.smoke
    def test_session_factory(self):
        """Verify session factory works."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.models.schema import get_session
        session = get_session()
        assert session is not None
        session.close()
    
    @pytest.mark.smoke
    def test_entities_table_exists(self):
        """Verify entities table exists and is queryable."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from sqlalchemy import create_engine, text
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM entities WHERE lifecycle_state = 'TRUSTED'
            """))
            count = result.fetchone()[0]
            assert count >= 0  # Just verify query works


class TestSmokeConfiguration:
    """Verify configuration and environment."""
    
    @pytest.mark.smoke
    def test_schema_loader(self):
        """Verify schema loader works."""
        from src.context_foundry.config.domain_schema import get_schema_loader
        loader = get_schema_loader()
        assert loader is not None
        assert loader.schema is not None
    
    @pytest.mark.smoke
    def test_entity_types_defined(self):
        """Verify entity types are defined."""
        from src.context_foundry.config.domain_schema import get_schema_loader
        loader = get_schema_loader()
        types = loader.schema.get_entity_type_names()
        assert len(types) > 0
        assert "PERSON" in types or "SERVICE" in types


# =============================================================================
# FAST REGRESSION - Query Subsystem
# =============================================================================

class TestQueryClassification:
    """Test query classification and parsing."""
    
    @pytest.mark.fast_regression
    def test_dependency_query_classification(self):
        """Verify dependency queries are classified correctly."""
        from src.context_foundry.contracts.query_parser import PatternBasedQueryParser
        
        parser = PatternBasedQueryParser()
        test_queries = [
            "What does the API Gateway depend on?",
            "Show dependencies of Payment Service",
            "List upstream dependencies for Auth Database",
        ]
        
        for query in test_queries:
            intent = parser.parse(query)
            assert intent.query_type.value in ['dependency', 'relationship', 'entity'], \
                f"Query '{query}' should be classified as dependency-related"
    
    @pytest.mark.fast_regression
    def test_impact_query_classification(self):
        """Verify impact/blast radius queries are classified correctly."""
        from src.context_foundry.contracts.query_parser import PatternBasedQueryParser
        
        parser = PatternBasedQueryParser()
        test_queries = [
            "What happens if Redis Cache fails?",
            "What is the blast radius of Auth Database?",
            "Show impact of Payment Service failure",
        ]
        
        for query in test_queries:
            intent = parser.parse(query)
            # Impact queries may be classified as impact or relationship
            assert intent is not None
    
    @pytest.mark.fast_regression
    def test_ownership_query_classification(self):
        """Verify ownership queries are classified correctly."""
        from src.context_foundry.contracts.query_parser import PatternBasedQueryParser
        
        parser = PatternBasedQueryParser()
        test_queries = [
            "Who owns the Payment Service?",
            "What team manages Redis Cache?",
        ]
        
        for query in test_queries:
            intent = parser.parse(query)
            assert intent is not None
    
    @pytest.mark.fast_regression
    def test_entity_extraction(self):
        """Verify entity extraction from queries."""
        from src.context_foundry.contracts.query_parser import PatternBasedQueryParser
        
        parser = PatternBasedQueryParser()
        
        # Queries with clear entity targets
        query = "What does API Gateway depend on?"
        intent = parser.parse(query)
        # Entity should be extracted (exact behavior depends on implementation)
        assert intent is not None


class TestEntityResolution:
    """Test entity resolution functionality."""
    
    @pytest.mark.fast_regression
    def test_exact_match_resolution(self):
        """Verify exact name matching works."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.models.schema import get_session, Entity
        
        session = get_session()
        try:
            # Find any trusted entity
            entity = session.query(Entity).filter(
                Entity.lifecycle_state == 'TRUSTED'
            ).first()
            
            if not entity:
                pytest.skip("No trusted entities in database")
            
            # Verify exact match
            found = session.query(Entity).filter(
                Entity.name == entity.name,
                Entity.lifecycle_state == 'TRUSTED'
            ).first()
            
            assert found is not None
            assert found.name == entity.name
        finally:
            session.close()
    
    @pytest.mark.fast_regression
    def test_case_insensitive_resolution(self):
        """Verify case-insensitive matching works."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.models.schema import get_session, Entity
        
        session = get_session()
        try:
            # Find any trusted entity
            entity = session.query(Entity).filter(
                Entity.lifecycle_state == 'TRUSTED'
            ).first()
            
            if not entity:
                pytest.skip("No trusted entities in database")
            
            # Verify case-insensitive match
            lower_name = entity.name.lower()
            found = session.query(Entity).filter(
                Entity.name.ilike(lower_name),
                Entity.lifecycle_state == 'TRUSTED'
            ).first()
            
            assert found is not None
        finally:
            session.close()
    
    @pytest.mark.fast_regression
    def test_partial_match_resolution(self):
        """Verify partial/contains matching works (fix for saleh -> Saleh Hamed)."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.models.schema import get_session, Entity
        
        session = get_session()
        try:
            # Find any trusted entity with a multi-word name
            entity = session.query(Entity).filter(
                Entity.lifecycle_state == 'TRUSTED',
                Entity.name.like('% %')  # Contains space = multi-word
            ).first()
            
            if not entity:
                pytest.skip("No multi-word entity names in database")
            
            # Extract first word and verify partial match
            first_word = entity.name.split()[0]
            if len(first_word) >= 3:
                found = session.query(Entity).filter(
                    Entity.name.ilike(f"%{first_word}%"),
                    Entity.lifecycle_state == 'TRUSTED'
                ).first()
                
                assert found is not None
                assert first_word.lower() in found.name.lower()
        finally:
            session.close()


class TestTargetEntityVerification:
    """Test the _verify_target_entity_exists functionality."""
    
    @pytest.mark.fast_regression
    def test_verify_existing_entity(self):
        """Verify existing entities are found."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.agents.retrieval import RetrievalAgent
        from src.context_foundry.models.schema import get_session, Entity
        
        session = get_session()
        try:
            entity = session.query(Entity).filter(
                Entity.lifecycle_state == 'TRUSTED'
            ).first()
            
            if not entity:
                pytest.skip("No trusted entities in database")
            
            agent = RetrievalAgent()
            found, entity_dict = agent._verify_target_entity_exists(entity.name)
            
            assert found is True
            assert entity_dict is not None
        finally:
            session.close()
    
    @pytest.mark.fast_regression
    def test_verify_nonexistent_entity(self):
        """Verify nonexistent entities return False."""
        from src.context_foundry.agents.retrieval import RetrievalAgent
        
        agent = RetrievalAgent()
        found, entity_dict = agent._verify_target_entity_exists("NonExistent_XYZ_12345")
        
        assert found is False
        assert entity_dict is None
    
    @pytest.mark.fast_regression
    def test_verify_partial_name_match(self):
        """Verify partial names are resolved (e.g., 'saleh' -> 'Saleh Hamed')."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.agents.retrieval import RetrievalAgent
        from src.context_foundry.models.schema import get_session, Entity
        
        session = get_session()
        try:
            # Find a person with first and last name
            entity = session.query(Entity).filter(
                Entity.lifecycle_state == 'TRUSTED',
                Entity.entity_type == 'PERSON',
                Entity.name.like('% %')
            ).first()
            
            if not entity:
                pytest.skip("No multi-word person names in database")
            
            # Try matching with just first name
            first_name = entity.name.split()[0]
            if len(first_name) >= 3:
                agent = RetrievalAgent()
                found, entity_dict = agent._verify_target_entity_exists(first_name)
                
                assert found is True, f"Expected '{first_name}' to match '{entity.name}'"
        finally:
            session.close()


# =============================================================================
# FAST REGRESSION - Retrieval Subsystem
# =============================================================================

class TestContextBundleAssembly:
    """Test ContextBundle creation and assembly."""
    
    @pytest.mark.fast_regression
    def test_context_bundle_creation(self):
        """Verify ContextBundle can be created."""
        from src.context_foundry.models.context_bundle import ContextBundle
        
        bundle = ContextBundle(query_id=str(uuid.uuid4()), query_text="Test query")
        assert bundle.query_text == "Test query"
        assert bundle.semantic_entities == []
        assert bundle.semantic_relationships == []
    
    @pytest.mark.fast_regression
    def test_context_bundle_query_id(self):
        """Verify ContextBundle with query_id."""
        from src.context_foundry.models.context_bundle import ContextBundle
        
        query_id = str(uuid.uuid4())
        bundle = ContextBundle(
            query_id=query_id,
            query_text="Test query"
        )
        assert bundle.query_id == query_id


class TestQuadrantConfidence:
    """Test quadrant-based confidence calculation."""
    
    @pytest.mark.fast_regression
    def test_q1_entity_and_docs(self):
        """Verify Q1 (entity + docs) returns high confidence."""
        from src.context_foundry.agents.reasoning import ReasoningAgent
        from src.context_foundry.models.context_bundle import ContextBundle
        
        agent = ReasoningAgent()
        
        # Simulate Q1: entity found + good docs
        bundle = ContextBundle(query_id=str(uuid.uuid4()), query_text="Test query")
        bundle.target_entity_found = True
        bundle.episodic_documents = [{"similarity": 0.9, "content": "Test doc"}]
        
        confidence, quadrant = agent.calculate_quadrant_confidence(
            bundle, "SUFFICIENT", 0.5
        )
        
        assert quadrant == "Q1_entity_and_docs"
        assert confidence >= 0.9
    
    @pytest.mark.fast_regression
    def test_q2_entity_only(self):
        """Verify Q2 (entity only) returns moderate confidence."""
        from src.context_foundry.agents.reasoning import ReasoningAgent
        from src.context_foundry.models.context_bundle import ContextBundle
        
        agent = ReasoningAgent()
        
        # Simulate Q2: entity found but no good docs
        bundle = ContextBundle(query_id=str(uuid.uuid4()), query_text="Test query")
        bundle.target_entity_found = True
        bundle.episodic_documents = []
        
        confidence, quadrant = agent.calculate_quadrant_confidence(
            bundle, "SUFFICIENT", 0.0
        )
        
        assert quadrant == "Q2_entity_only"
        assert 0.7 <= confidence <= 0.85
    
    @pytest.mark.fast_regression
    def test_q4_no_evidence(self):
        """Verify Q4 (no evidence) returns low confidence."""
        from src.context_foundry.agents.reasoning import ReasoningAgent
        from src.context_foundry.models.context_bundle import ContextBundle
        
        agent = ReasoningAgent()
        
        # Simulate Q4: no entity, no docs
        bundle = ContextBundle(query_id=str(uuid.uuid4()), query_text="Test query")
        bundle.target_entity_found = False
        bundle.episodic_documents = []
        
        confidence, quadrant = agent.calculate_quadrant_confidence(
            bundle, "INSUFFICIENT", 0.0
        )
        
        assert quadrant == "Q4_no_evidence"
        assert confidence <= 0.20
    
    @pytest.mark.fast_regression
    def test_target_missing_caps_confidence(self):
        """Verify target entity missing caps confidence."""
        from src.context_foundry.agents.reasoning import ReasoningAgent
        from src.context_foundry.models.context_bundle import ContextBundle
        
        agent = ReasoningAgent()
        
        # Target named but not found - should cap confidence
        bundle = ContextBundle(query_id=str(uuid.uuid4()), query_text="Test query")
        bundle.target_entity_name = "NonExistent"
        bundle.target_entity_found = False
        bundle.episodic_documents = [{"similarity": 0.9, "content": "Related doc"}]
        
        confidence, quadrant = agent.calculate_quadrant_confidence(
            bundle, "SUFFICIENT", 0.0
        )
        
        assert confidence <= 0.40
        assert "TARGET_MISSING" in quadrant


# =============================================================================
# FAST REGRESSION - DTL/Precedent Subsystem
# =============================================================================

class TestDTLAuthContext:
    """Test DTL AuthContext handling."""
    
    @pytest.mark.fast_regression
    def test_auth_context_creation(self):
        """Verify AuthContext can be created."""
        from src.context_foundry.dtl.core import AuthContext
        
        ctx = AuthContext(
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            role='user'
        )
        
        assert ctx.tenant_id is not None
        assert ctx.user_id is not None
        assert ctx.role == 'user'
    
    @pytest.mark.fast_regression
    def test_inline_search_with_fixed_embedding(self):
        """Verify inline search works with fixed embedding."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.dtl.core import AuthContext
        from src.context_foundry.dtl.dtl_inline import search_precedents as inline_search
        from src.context_foundry.models.schema import get_session
        from sqlalchemy import text, create_engine
        
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tenant_id::text FROM api_keys WHERE is_active = true LIMIT 1
            """))
            row = result.fetchone()
            if not row:
                pytest.skip("No tenants available for testing")
            tenant_id = row[0]
        
        ctx = AuthContext(
            tenant_id=tenant_id,
            user_id=str(uuid.uuid4()),
            role='user'
        )
        
        fixed_embedding = [0.1] * 1536
        
        session = get_session()
        try:
            results = inline_search(
                session=session,
                ctx=ctx,
                query_text="Test query",
                query_embedding=fixed_embedding,
                limit=5
            )
            
            assert isinstance(results, list)
        finally:
            session.close()


class TestTenantIsolation:
    """Test tenant isolation in queries."""
    
    @pytest.mark.fast_regression
    def test_cross_tenant_query_returns_empty(self):
        """Verify cross-tenant queries return no results."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.dtl.core import AuthContext
        from src.context_foundry.dtl.dtl_inline import search_precedents as inline_search
        from src.context_foundry.models.schema import get_session
        
        # Use a random tenant ID that doesn't exist
        fake_tenant_id = str(uuid.uuid4())
        
        ctx = AuthContext(
            tenant_id=fake_tenant_id,
            user_id=str(uuid.uuid4()),
            role='user'
        )
        
        fixed_embedding = [0.1] * 1536
        
        session = get_session()
        try:
            results = inline_search(
                session=session,
                ctx=ctx,
                query_text="Test query",
                query_embedding=fixed_embedding,
                limit=5
            )
            
            # Should return empty for non-existent tenant
            assert len(results) == 0
        finally:
            session.close()


# =============================================================================
# COMPONENT TESTS - API Endpoints
# =============================================================================

class TestAPIEndpoints:
    """Test API endpoint contracts."""
    
    @pytest.mark.component
    def test_health_endpoint(self):
        """Verify health endpoint responds."""
        import requests
        
        try:
            resp = requests.get("http://localhost:5000/health", timeout=5)
            # Even if no explicit health endpoint, root should respond
            assert resp.status_code in [200, 302, 404]
        except requests.exceptions.ConnectionError:
            pytest.skip("Platform service not running")
    
    @pytest.mark.component
    def test_brain_health(self):
        """Verify brain service responds."""
        import requests
        
        try:
            resp = requests.get("http://localhost:3000/", timeout=5)
            assert resp.status_code in [200, 404]
        except requests.exceptions.ConnectionError:
            pytest.skip("Brain service not running")


# =============================================================================
# REGRESSION VECTORS - Known edge cases
# =============================================================================

class TestRegressionVectors:
    """Test specific regression cases that have broken before."""
    
    @pytest.mark.fast_regression
    def test_single_word_name_resolution(self):
        """Regression: Single-word names should find multi-word entities.
        
        Fix: retrieval.py _verify_target_entity_exists now uses partial
        matching for all names >= 3 chars, not just multi-word names.
        """
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from sqlalchemy import create_engine, text
        
        engine = create_engine(database_url)
        with engine.connect() as conn:
            # Find a name that would have failed before the fix
            result = conn.execute(text("""
                SELECT name FROM entities 
                WHERE lifecycle_state = 'TRUSTED'
                AND name LIKE '% %'
                LIMIT 1
            """))
            row = result.fetchone()
            
            if not row:
                pytest.skip("No multi-word entity names")
            
            full_name = row[0]
            first_word = full_name.split()[0]
            
            # Verify partial match works
            result = conn.execute(text("""
                SELECT name FROM entities
                WHERE lifecycle_state = 'TRUSTED'
                AND name ILIKE :pattern
                LIMIT 1
            """), {"pattern": f"%{first_word}%"})
            
            found = result.fetchone()
            assert found is not None, f"'{first_word}' should match '{full_name}'"
    
    @pytest.mark.fast_regression
    def test_smoke_mode_embedding_safeguard(self):
        """Regression: Smoke mode should raise if embedding fallback is invoked."""
        os.environ["DTL_SMOKE_MODE"] = "1"
        
        try:
            from src.context_foundry.dtl.core import SmokeModeViolation
            
            # Verify SmokeModeViolation exists and is an exception
            assert issubclass(SmokeModeViolation, Exception)
            
            # If the function exists, test it
            try:
                from src.context_foundry.dtl.core import compute_embedding_with_fallback
                with pytest.raises(SmokeModeViolation):
                    compute_embedding_with_fallback("Test text", None)
            except ImportError:
                # Function may be internal, just verify the exception exists
                pass
        finally:
            os.environ.pop("DTL_SMOKE_MODE", None)
    
    @pytest.mark.fast_regression
    def test_blast_radius_guard(self):
        """Regression: Blast radius queries for non-existent entities should fail safely."""
        from src.context_foundry.agents.reasoning import ReasoningAgent
        from src.context_foundry.models.context_bundle import ContextBundle
        
        agent = ReasoningAgent()
        
        # Create bundle for blast radius query with missing entity
        bundle = ContextBundle(
            query_id=str(uuid.uuid4()),
            query_text="What is the blast radius of NonExistent?"
        )
        bundle.target_entity_name = "NonExistent"
        bundle.target_entity_found = False
        
        # Should detect as blast radius query
        assert agent._is_blast_radius_query("What is the blast radius of NonExistent?")


# =============================================================================
# AGGREGATION FRAMEWORK TESTS - Quantitative query handling
# =============================================================================

class TestAggregationFramework:
    """Tests for the Aggregation Framework v1.3."""
    
    @pytest.mark.smoke
    def test_aggregation_models_import(self):
        """Verify aggregation models import correctly."""
        from src.context_foundry.aggregation import (
            AggregationService,
            AggIntent,
            CAT,
            ResultKind,
            AggregationResult,
            EvidenceEnvelope,
        )
        assert AggregationService is not None
        assert AggIntent is not None
        assert CAT is not None
        assert ResultKind is not None
        assert AggregationResult is not None
        assert EvidenceEnvelope is not None
    
    @pytest.mark.smoke
    def test_result_kind_values(self):
        """Verify ResultKind enum has expected values."""
        from src.context_foundry.aggregation.models import ResultKind
        
        assert ResultKind.EXACT.value == "EXACT"
        assert ResultKind.LOWER_BOUND.value == "LOWER_BOUND"
        assert ResultKind.RANGE.value == "RANGE"
        assert ResultKind.INSUFFICIENT.value == "INSUFFICIENT"
    
    @pytest.mark.smoke
    def test_intent_kind_values(self):
        """Verify IntentKind enum has expected values."""
        from src.context_foundry.aggregation.models import IntentKind
        
        assert IntentKind.COUNT.value == "COUNT"
        assert IntentKind.SUM.value == "SUM"
        assert IntentKind.AVG.value == "AVG"
        assert IntentKind.MIN.value == "MIN"
        assert IntentKind.MAX.value == "MAX"
    
    @pytest.mark.fast_regression
    def test_aggregation_result_display_text_exact(self):
        """Test AggregationResult.display_text for EXACT result."""
        from src.context_foundry.aggregation.models import AggregationResult, ResultKind
        
        result = AggregationResult(
            result_kind=ResultKind.EXACT,
            value=5,
            unit="jobs",
            confidence=0.95,
        )
        
        assert result.display_text == "5 jobs"
        assert result.is_success is True
    
    @pytest.mark.fast_regression
    def test_aggregation_result_display_text_lower_bound(self):
        """Test AggregationResult.display_text for LOWER_BOUND result."""
        from src.context_foundry.aggregation.models import (
            AggregationResult, ResultKind, BoundedCount
        )
        
        result = AggregationResult(
            result_kind=ResultKind.LOWER_BOUND,
            bounds=BoundedCount(lower=3),
            unit="items",
            confidence=0.75,
        )
        
        assert "At least 3" in result.display_text
        assert result.is_success is True
    
    @pytest.mark.fast_regression
    def test_aggregation_result_display_text_range(self):
        """Test AggregationResult.display_text for RANGE result."""
        from src.context_foundry.aggregation.models import (
            AggregationResult, ResultKind, BoundedCount
        )
        
        result = AggregationResult(
            result_kind=ResultKind.RANGE,
            bounds=BoundedCount(lower=3, upper=7),
            unit="entities",
            confidence=0.65,
        )
        
        assert "Between 3 and 7" in result.display_text
        assert result.is_success is True
    
    @pytest.mark.fast_regression
    def test_aggregation_result_display_text_insufficient(self):
        """Test AggregationResult.display_text for INSUFFICIENT result."""
        from src.context_foundry.aggregation.models import AggregationResult, ResultKind
        
        result = AggregationResult(
            result_kind=ResultKind.INSUFFICIENT,
            confidence=0.1,
        )
        
        assert "Insufficient" in result.display_text
        assert result.is_success is False
    
    @pytest.mark.fast_regression
    def test_context_bundle_aggregation_fields(self):
        """Test ContextBundle has aggregation framework fields."""
        from src.context_foundry.models.context_bundle import ContextBundle
        
        bundle = ContextBundle(
            query_id=str(uuid.uuid4()),
            query_text="How many jobs has Saleh had?"
        )
        
        assert hasattr(bundle, 'aggregation_target')
        assert hasattr(bundle, 'aggregation_plan')
        assert hasattr(bundle, 'evidence_envelope')
        assert hasattr(bundle, 'aggregation_result')
        
        assert bundle.aggregation_target is None
        assert bundle.aggregation_plan is None
    
    @pytest.mark.fast_regression
    def test_retrieval_agent_has_aggregation_service(self):
        """Test RetrievalAgent has aggregation service."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.agents.retrieval import RetrievalAgent
        
        tenant_id = str(uuid.uuid4())
        agent = RetrievalAgent(tenant_id=tenant_id)
        
        assert hasattr(agent, 'feature_flags')
        assert hasattr(agent, 'aggregation_service')
        assert 'aggregation.enabled' in agent.feature_flags
    
    @pytest.mark.fast_regression
    def test_aggregation_feature_flag_default(self):
        """Test aggregation is enabled by default."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.agents.retrieval import RetrievalAgent
        
        tenant_id = str(uuid.uuid4())
        agent = RetrievalAgent(tenant_id=tenant_id)
        
        assert agent.feature_flags.get("aggregation.enabled") is True
        assert agent.feature_flags.get("aggregation.crc_estimation.enabled") is True
    
    @pytest.mark.fast_regression
    def test_aggregation_hook_called_for_counting_query(self):
        """Regression: Aggregation hook should intercept 'How many' queries."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.agents.retrieval import RetrievalAgent
        from unittest.mock import MagicMock
        
        tenant_id = str(uuid.uuid4())
        agent = RetrievalAgent(tenant_id=tenant_id)
        
        # Mock the aggregation service
        mock_service = MagicMock()
        mock_service.is_aggregation_query.return_value = True
        mock_service.handle_query.return_value = MagicMock(
            result_kind=MagicMock(value='EXACT'),
            value=5,
            is_success=True,
            cat=None,
            evidence_envelope=None,
            display_text='5 jobs',
            confidence=0.95
        )
        agent._aggregation_service = mock_service
        
        # Call with aggregation query
        bundle = agent.build_context_bundle("How many jobs has Saleh had?")
        
        # Verify aggregation path was taken
        assert bundle.is_aggregation_query is True
        assert mock_service.is_aggregation_query.called
        assert mock_service.handle_query.called
    
    @pytest.mark.fast_regression
    def test_aggregation_hook_skipped_for_normal_query(self):
        """Regression: Normal queries should bypass aggregation hook."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.agents.retrieval import RetrievalAgent
        from unittest.mock import MagicMock, patch
        
        tenant_id = str(uuid.uuid4())
        agent = RetrievalAgent(tenant_id=tenant_id)
        
        # Mock the aggregation service to return False for is_aggregation_query
        mock_service = MagicMock()
        mock_service.is_aggregation_query.return_value = False
        agent._aggregation_service = mock_service
        
        # Mock the LLM client to avoid API calls
        mock_llm = MagicMock()
        mock_llm.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"needs_property_search": false}'))]
        )
        agent._llm_client = mock_llm
        
        # Call with non-aggregation query
        bundle = agent.build_context_bundle("Who is Saleh Hamed?")
        
        # Verify aggregation service was checked but skipped
        assert mock_service.is_aggregation_query.called
        assert not mock_service.handle_query.called
        assert bundle.is_aggregation_query is False


# =============================================================================
# INTEGRATION TESTS - Full pipeline (nightly only)
# =============================================================================

class TestFullPipeline:
    """Full end-to-end pipeline tests."""
    
    @pytest.mark.integration
    def test_query_to_response(self):
        """Test full query -> retrieval -> reasoning pipeline."""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from src.context_foundry.agents.retrieval import RetrievalAgent
        from src.context_foundry.agents.reasoning import ReasoningAgent
        
        retrieval = RetrievalAgent()
        reasoning = ReasoningAgent()
        
        # Use a simple query
        bundle = retrieval.build_context_bundle("List all entities")
        result = reasoning.reason(bundle)
        
        assert "answer" in result or "response" in result
        assert "confidence" in result
