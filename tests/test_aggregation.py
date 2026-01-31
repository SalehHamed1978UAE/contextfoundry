"""
Unit tests for aggregation planner and executor.
Tests the AggregationPlanner plan generation and AggregationExecutor execution.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.context_foundry.aggregation.planner import (
    AggregationPlanner,
    ExecutionPlan,
    ExecutionStrategy,
)
from src.context_foundry.aggregation.executor import (
    AggregationExecutor,
    RawAggregationResult,
    SourceEvidence,
)
from src.context_foundry.aggregation.models import (
    CAT,
    IntentKind,
    TargetSource,
    TargetSpec,
    AggregationSpec,
    AnchorEntity,
    Filter,
    TimeWindow,
    TimeMode,
    GraphConfig,
    ClosurePolicy,
    EvidenceEnvelope,
)


class TestAggregationPlanner:
    """Unit tests for AggregationPlanner."""
    
    @pytest.fixture
    def planner(self):
        return AggregationPlanner()
    
    @pytest.fixture
    def tenant_id(self):
        return uuid4()
    
    def test_build_count_plan(self, planner, tenant_id):
        """Test COUNT plan generation."""
        cat = CAT(
            tenant_id=tenant_id,
            anchor=None,
            target=TargetSpec(source=TargetSource.ENTITY_TABLE, entity_type="PERSON"),
            aggregation=AggregationSpec(op=IntentKind.COUNT),
        )
        
        plan = planner.build_plan(cat)
        
        assert plan.strategy == ExecutionStrategy.SQL_AGG
        assert "COUNT(*)" in plan.sql
        assert "tenant_id" in plan.params
        assert plan.params["tenant_id"] == str(tenant_id)
        assert plan.plan_hash != ""
    
    def test_build_sum_plan(self, planner, tenant_id):
        """Test SUM plan generation."""
        cat = CAT(
            tenant_id=tenant_id,
            anchor=None,
            target=TargetSpec(source=TargetSource.ENTITY_TABLE, entity_type="ORDER"),
            aggregation=AggregationSpec(op=IntentKind.SUM, value_expr="amount"),
        )
        
        plan = planner.build_plan(cat)
        
        assert plan.strategy == ExecutionStrategy.SQL_AGG
        assert "SUM" in plan.sql
        assert "amount" in plan.sql
        assert plan.params["tenant_id"] == str(tenant_id)
    
    def test_build_avg_plan(self, planner, tenant_id):
        """Test AVG plan generation with sample_size."""
        cat = CAT(
            tenant_id=tenant_id,
            anchor=None,
            target=TargetSpec(source=TargetSource.ENTITY_TABLE, entity_type="RATING"),
            aggregation=AggregationSpec(op=IntentKind.AVG, value_expr="score"),
        )
        
        plan = planner.build_plan(cat)
        
        assert plan.strategy == ExecutionStrategy.SQL_AGG
        assert "AVG" in plan.sql
        assert "sample_size" in plan.sql
        assert "score" in plan.sql
    
    def test_build_min_max_plans(self, planner, tenant_id):
        """Test MIN and MAX plan generation."""
        for intent in [IntentKind.MIN, IntentKind.MAX]:
            cat = CAT(
                tenant_id=tenant_id,
                anchor=None,
                target=TargetSpec(source=TargetSource.ENTITY_TABLE),
                aggregation=AggregationSpec(op=intent, value_expr="price"),
            )
            
            plan = planner.build_plan(cat)
            
            assert plan.strategy == ExecutionStrategy.SQL_AGG
            assert intent.value in plan.sql
    
    def test_build_relationship_plan_with_anchor(self, planner, tenant_id):
        """Test relationship aggregation with anchor entity."""
        anchor_id = uuid4()
        cat = CAT(
            tenant_id=tenant_id,
            anchor=AnchorEntity(entity_id=anchor_id, entity_type="PERSON", name="Alice"),
            target=TargetSpec(
                source=TargetSource.KG_RELATIONSHIP,
                relationship_type="WORKS_AT"
            ),
            aggregation=AggregationSpec(op=IntentKind.COUNT),
        )
        
        plan = planner.build_plan(cat)
        
        assert plan.strategy == ExecutionStrategy.SQL_AGG
        assert "relationships" in plan.sql
        assert "source_id" in plan.sql
        assert plan.params["anchor_id"] == str(anchor_id)
        assert plan.params["rel_type"] == "WORKS_AT"
    
    def test_build_graph_traversal_plan(self, planner, tenant_id):
        """Test graph traversal plan with recursive CTE."""
        anchor_id = uuid4()
        cat = CAT(
            tenant_id=tenant_id,
            anchor=AnchorEntity(entity_id=anchor_id, entity_type="TEAM"),
            target=TargetSpec(
                source=TargetSource.KG_RELATIONSHIP,
                relationship_type="MEMBER_OF"
            ),
            aggregation=AggregationSpec(op=IntentKind.GRAPH_COUNT),
            graph=GraphConfig(max_hops=3, direction="outgoing"),
        )
        
        plan = planner.build_plan(cat)
        
        assert plan.strategy == ExecutionStrategy.GRAPH_TRAVERSAL
        assert "WITH RECURSIVE" in plan.sql
        assert plan.max_depth == 3
        assert plan.params["start_entity_id"] == str(anchor_id)
        assert plan.params["relationship_type"] == "MEMBER_OF"
    
    def test_graph_plan_requires_anchor(self, planner, tenant_id):
        """Graph traversal should fail without anchor entity."""
        cat = CAT(
            tenant_id=tenant_id,
            anchor=None,
            target=TargetSpec(source=TargetSource.KG_RELATIONSHIP),
            aggregation=AggregationSpec(op=IntentKind.GRAPH_COUNT),
        )
        
        with pytest.raises(ValueError, match="anchor"):
            planner.build_plan(cat)
    
    def test_build_dtl_plan(self, planner, tenant_id):
        """Test DTL decision aggregation plan."""
        cat = CAT(
            tenant_id=tenant_id,
            anchor=None,
            target=TargetSpec(
                source=TargetSource.DTL_DECISION,
                entity_type="exception"
            ),
            aggregation=AggregationSpec(op=IntentKind.COUNT),
            filters=[Filter(path="outcome", op="=", value="granted")],
        )
        
        plan = planner.build_plan(cat)
        
        assert plan.strategy == ExecutionStrategy.SQL_AGG
        assert "dtl_decisions" in plan.sql
        assert plan.params["decision_type"] == "exception"
    
    def test_build_doc_mentions_plan(self, planner, tenant_id):
        """Test document mentions aggregation plan."""
        entity_id = uuid4()
        cat = CAT(
            tenant_id=tenant_id,
            anchor=AnchorEntity(entity_id=entity_id, entity_type="PERSON"),
            target=TargetSpec(source=TargetSource.DOCUMENT_MENTION),
            aggregation=AggregationSpec(op=IntentKind.COUNT),
        )
        
        plan = planner.build_plan(cat)
        
        assert plan.strategy == ExecutionStrategy.SQL_AGG
        assert "doc_entity_mentions" in plan.sql
        assert plan.params["entity_id"] == str(entity_id)
    
    def test_doc_mentions_requires_anchor(self, planner, tenant_id):
        """Document mention count should fail without anchor entity."""
        cat = CAT(
            tenant_id=tenant_id,
            anchor=None,
            target=TargetSpec(source=TargetSource.DOCUMENT_MENTION),
            aggregation=AggregationSpec(op=IntentKind.COUNT),
        )
        
        with pytest.raises(ValueError, match="anchor"):
            planner.build_plan(cat)
    
    def test_filters_applied_to_plan(self, planner, tenant_id):
        """Test that filters are applied to SQL plan."""
        cat = CAT(
            tenant_id=tenant_id,
            anchor=None,
            target=TargetSpec(source=TargetSource.ENTITY_TABLE, entity_type="PERSON"),
            aggregation=AggregationSpec(op=IntentKind.COUNT),
            filters=[
                Filter(path="status", op="=", value="active"),
                Filter(path="department", op="IN", value=["Engineering", "Sales"]),
            ],
        )
        
        plan = planner.build_plan(cat)
        
        assert "status" in plan.sql or "filter_0" in plan.params
        assert "filter_0" in plan.params or "filter_1" in plan.params
    
    def test_time_window_applied_to_plan(self, planner, tenant_id):
        """Test that time window is applied to SQL plan."""
        cat = CAT(
            tenant_id=tenant_id,
            anchor=None,
            target=TargetSpec(source=TargetSource.ENTITY_TABLE),
            aggregation=AggregationSpec(op=IntentKind.COUNT),
            time=TimeWindow(
                start=datetime(2024, 1, 1),
                end=datetime(2024, 12, 31),
                field="created_at",
                mode=TimeMode.EVENT_TIME,
            ),
        )
        
        plan = planner.build_plan(cat)
        
        assert "time_start" in plan.params or "created_at" in plan.sql
    
    def test_plan_hash_is_deterministic(self, planner, tenant_id):
        """Same CAT should produce same plan hash."""
        cat = CAT(
            tenant_id=tenant_id,
            anchor=None,
            target=TargetSpec(source=TargetSource.ENTITY_TABLE),
            aggregation=AggregationSpec(op=IntentKind.COUNT),
        )
        
        plan1 = planner.build_plan(cat)
        plan2 = planner.build_plan(cat)
        
        assert plan1.plan_hash == plan2.plan_hash
    
    def test_cache_key_generated(self, planner, tenant_id):
        """Verify cache key is generated for plan."""
        cat = CAT(
            tenant_id=tenant_id,
            anchor=None,
            target=TargetSpec(source=TargetSource.ENTITY_TABLE),
            aggregation=AggregationSpec(op=IntentKind.COUNT),
        )
        
        plan = planner.build_plan(cat)
        
        assert plan.cache_key is not None
        assert len(plan.cache_key) == 16


class TestAggregationExecutor:
    """Unit tests for AggregationExecutor."""
    
    @pytest.fixture
    def tenant_id(self):
        return uuid4()
    
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.execute = MagicMock()
        session.rollback = MagicMock()
        return session
    
    @pytest.fixture
    def executor(self, mock_session, tenant_id):
        return AggregationExecutor(session=mock_session, tenant_id=tenant_id)
    
    def test_execute_sql_aggregation(self, executor, mock_session):
        """Test SQL aggregation execution returns result."""
        mock_row = MagicMock()
        mock_row.result = 42
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) as result FROM entities WHERE tenant_id = :tenant_id",
            params={"tenant_id": str(executor.tenant_id)},
        )
        
        result, evidence = executor.execute(plan)
        
        assert result.value == 42
        assert isinstance(evidence, EvidenceEnvelope)
        assert evidence.plan_hash == plan.plan_hash
    
    def test_execute_sql_with_mapping(self, executor, mock_session):
        """Test SQL execution handles row _mapping."""
        mock_row = MagicMock()
        mock_row._mapping = {"result": 100}
        del mock_row.result
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) as result FROM entities",
            params={"tenant_id": str(executor.tenant_id)},
        )
        
        result, evidence = executor.execute(plan)
        
        assert result.value == 100
    
    def test_execute_sql_null_result(self, executor, mock_session):
        """Test SQL execution handles null result."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result
        
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) as result FROM entities",
            params={"tenant_id": str(executor.tenant_id)},
        )
        
        result, evidence = executor.execute(plan)
        
        assert result.value == 0
    
    def test_execute_graph_traversal(self, executor, mock_session):
        """Test graph traversal execution."""
        mock_row = MagicMock()
        mock_row.result = 15
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.GRAPH_TRAVERSAL,
            sql="WITH RECURSIVE reachable AS (...) SELECT COUNT(*) as result",
            params={"tenant_id": str(executor.tenant_id)},
            max_depth=3,
        )
        
        result, evidence = executor.execute(plan)
        
        assert result.value == 15
        assert result.metadata.get("max_depth") == 3
    
    def test_cache_strategy_raises_error(self, executor):
        """CACHE strategy should raise ValueError (not yet implemented)."""
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.CACHE,
            sql="",
            params={},
            cache_key="test_key",
        )
        
        with pytest.raises(ValueError, match="Caching is not yet implemented"):
            executor.execute(plan)
    
    def test_unsupported_strategy_raises_error(self, executor):
        """Unsupported strategy should raise ValueError."""
        plan = ExecutionPlan(
            strategy="UNKNOWN_STRATEGY",
            sql="",
            params={},
        )
        
        with pytest.raises(ValueError, match="Unsupported strategy"):
            executor.execute(plan)
    
    def test_sets_tenant_context(self, executor, mock_session, tenant_id):
        """Verify tenant context is set for RLS."""
        mock_row = MagicMock()
        mock_row.result = 1
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) as result",
            params={"tenant_id": str(tenant_id)},
        )
        
        executor.execute(plan)
        
        assert mock_session.execute.call_count >= 3, "Should call execute at least 3 times (tenant, timeout, query)"
    
    def test_sets_statement_timeout(self, executor, mock_session):
        """Verify statement timeout is set (executor uses 10s timeout)."""
        mock_row = MagicMock()
        mock_row.result = 1
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) as result",
            params={"tenant_id": str(executor.tenant_id)},
        )
        
        executor.execute(plan)
        
        assert executor.STATEMENT_TIMEOUT_MS == 10000, "Default timeout should be 10000ms"
        assert mock_session.execute.call_count >= 3, "Should call execute at least 3 times"
    
    def test_execution_error_handling(self, executor, mock_session):
        """Test that execution errors are propagated."""
        mock_session.execute.side_effect = Exception("Database error")
        
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) as result",
            params={"tenant_id": str(executor.tenant_id)},
        )
        
        with pytest.raises(Exception, match="Database error"):
            executor.execute(plan)


class TestEvidenceEnvelope:
    """Test evidence envelope generation."""
    
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.execute = MagicMock()
        session.rollback = MagicMock()
        return session
    
    def test_evidence_contains_plan_hash(self, mock_session):
        """Evidence should contain plan hash."""
        tenant_id = uuid4()
        executor = AggregationExecutor(session=mock_session, tenant_id=tenant_id)
        
        mock_row = MagicMock()
        mock_row.result = 5
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) as result",
            params={"tenant_id": str(tenant_id)},
        )
        
        result, evidence = executor.execute(plan)
        
        assert evidence.plan_hash == plan.plan_hash
    
    def test_evidence_contains_sql(self, mock_session):
        """Evidence should contain executed SQL."""
        tenant_id = uuid4()
        executor = AggregationExecutor(session=mock_session, tenant_id=tenant_id)
        
        mock_row = MagicMock()
        mock_row.result = 5
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        sql = "SELECT COUNT(*) as result FROM entities"
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql=sql,
            params={"tenant_id": str(tenant_id)},
        )
        
        result, evidence = executor.execute(plan)
        
        assert evidence.sql == sql
    
    def test_evidence_contains_params(self, mock_session):
        """Evidence should contain query params as strings."""
        tenant_id = uuid4()
        executor = AggregationExecutor(session=mock_session, tenant_id=tenant_id)
        
        mock_row = MagicMock()
        mock_row.result = 5
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) as result",
            params={"tenant_id": tenant_id, "filter": 123},
        )
        
        result, evidence = executor.execute(plan)
        
        assert "tenant_id" in evidence.params
        assert isinstance(evidence.params["tenant_id"], str)
    
    def test_evidence_has_snapshot_time(self, mock_session):
        """Evidence should have snapshot timestamp."""
        tenant_id = uuid4()
        executor = AggregationExecutor(session=mock_session, tenant_id=tenant_id)
        
        mock_row = MagicMock()
        mock_row.result = 5
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) as result",
            params={"tenant_id": str(tenant_id)},
        )
        
        before = datetime.utcnow()
        result, evidence = executor.execute(plan)
        after = datetime.utcnow()
        
        assert before <= evidence.snapshot_time <= after


class TestRawAggregationResult:
    """Test RawAggregationResult dataclass."""
    
    def test_has_multiple_sources_true(self):
        """has_multiple_sources should be True with 2+ sources."""
        result = RawAggregationResult(
            value=10,
            sources=[
                SourceEvidence(source_name="doc1", entities=["e1"], count=5),
                SourceEvidence(source_name="doc2", entities=["e2"], count=5),
            ]
        )
        
        assert result.has_multiple_sources is True
    
    def test_has_multiple_sources_false(self):
        """has_multiple_sources should be False with <2 sources."""
        result = RawAggregationResult(
            value=10,
            sources=[
                SourceEvidence(source_name="doc1", entities=["e1"], count=10),
            ]
        )
        
        assert result.has_multiple_sources is False
    
    def test_default_values(self):
        """Test default values are initialized."""
        result = RawAggregationResult(value=5)
        
        assert result.sample_ids == []
        assert result.row_count == 0
        assert result.sources == []
        assert result.metadata == {}
        assert result.counted_entities == []


class TestExecutionPlan:
    """Test ExecutionPlan dataclass."""
    
    def test_hash_is_computed(self):
        """Plan hash should be computed automatically."""
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) FROM entities",
            params={"tenant_id": "123"},
        )
        
        assert plan.plan_hash != ""
        assert len(plan.plan_hash) == 16
    
    def test_same_plan_same_hash(self):
        """Same SQL and params should produce same hash."""
        plan1 = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) FROM entities",
            params={"tenant_id": "123"},
        )
        plan2 = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) FROM entities",
            params={"tenant_id": "123"},
        )
        
        assert plan1.plan_hash == plan2.plan_hash
    
    def test_different_params_different_hash(self):
        """Different params should produce different hash."""
        plan1 = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) FROM entities",
            params={"tenant_id": "123"},
        )
        plan2 = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT COUNT(*) FROM entities",
            params={"tenant_id": "456"},
        )
        
        assert plan1.plan_hash != plan2.plan_hash
    
    def test_created_at_is_set(self):
        """created_at should be set to current time."""
        before = datetime.utcnow()
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql="SELECT 1",
            params={},
        )
        after = datetime.utcnow()
        
        assert before <= plan.created_at <= after
