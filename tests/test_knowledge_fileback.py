"""Tests for Knowledge File-back (Gap 3)."""

from uuid import uuid4

import pytest
import pytest_asyncio

from src.agents.knowledge_fileback import KnowledgeFileBack
from src.models.schemas import (
    ReasoningResponse,
    ContextBundle,
    UncertaintyReport,
    Recommendation,
    ConfidenceLevel,
)
from tests.conftest import ENTITY_1_ID, ENTITY_2_ID


def _make_bundle(entity_ids):
    """Build a minimal ContextBundle with the given entity IDs."""
    return ContextBundle(
        id=uuid4(),
        query_text="test query",
        semantic_entities=[
            {"entity_id": str(eid), "entity_type": "Service", "confidence": 0.9}
            for eid in entity_ids
        ],
        semantic_relationships=[],
        episodic_documents=[],
        symbolic_rules_applied=[],
        session_context=[],
        uncertainty=UncertaintyReport(
            overall_confidence=0.8,
            recommendation=Recommendation.PROCEED,
            high_confidence_facts=1,
            medium_confidence_facts=0,
            low_confidence_facts=0,
        ),
    )


def _make_response(confidence=0.85):
    """Build a minimal ReasoningResponse."""
    return ReasoningResponse(
        id=uuid4(),
        bundle_id=uuid4(),
        answer="test answer",
        confidence=confidence,
        confidence_level=(
            ConfidenceLevel.HIGH if confidence >= 0.85 else ConfidenceLevel.LOW
        ),
    )


@pytest_asyncio.fixture()
async def fileback(initialized_db, seed_test_data):
    return KnowledgeFileBack(initialized_db)


@pytest.mark.asyncio
async def test_boost_on_successful_query(fileback, initialized_db):
    # Record original confidence
    async with initialized_db.get_postgres_connection() as conn:
        before = await conn.fetchval(
            "SELECT confidence FROM graph_lifecycle WHERE entity_id = $1",
            ENTITY_1_ID,
        )

    bundle = _make_bundle([ENTITY_1_ID])
    response = _make_response(confidence=0.85)
    result = await fileback.process("test", response, bundle)

    assert result["entities_boosted"] == 1
    assert result["entities_demoted"] == 0

    # Confidence should have increased
    async with initialized_db.get_postgres_connection() as conn:
        after = await conn.fetchval(
            "SELECT confidence FROM graph_lifecycle WHERE entity_id = $1",
            ENTITY_1_ID,
        )
    assert float(after) > float(before)


@pytest.mark.asyncio
async def test_demote_on_low_confidence_response(fileback, initialized_db):
    async with initialized_db.get_postgres_connection() as conn:
        before = await conn.fetchval(
            "SELECT confidence FROM graph_lifecycle WHERE entity_id = $1",
            ENTITY_1_ID,
        )

    bundle = _make_bundle([ENTITY_1_ID])
    response = _make_response(confidence=0.3)  # Below 0.4 threshold
    result = await fileback.process("test", response, bundle)

    assert result["entities_demoted"] == 1
    assert result["entities_boosted"] == 0

    async with initialized_db.get_postgres_connection() as conn:
        after = await conn.fetchval(
            "SELECT confidence FROM graph_lifecycle WHERE entity_id = $1",
            ENTITY_1_ID,
        )
    assert float(after) < float(before)


@pytest.mark.asyncio
async def test_no_entities_noop(fileback):
    bundle = _make_bundle([])
    response = _make_response(confidence=0.85)
    result = await fileback.process("test", response, bundle)
    assert result["entities_boosted"] == 0
    assert result["entities_demoted"] == 0


@pytest.mark.asyncio
async def test_fileback_does_not_raise(fileback):
    """Even with bad data, process() should not raise."""
    bundle = _make_bundle([uuid4()])  # Non-existent entity
    response = _make_response(confidence=0.85)
    # Should not raise — errors are caught per-entity
    result = await fileback.process("test", response, bundle)
    # The gardener.increase_confidence will succeed (UPDATE with 0 rows matched)
    # so boosted count will be 1 (no exception raised for non-existent UUID)
    assert isinstance(result, dict)
