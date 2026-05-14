"""Unit tests for Property Plane hook (Stage 3A M3).

Uses the _stub_session pattern from test_document_evidence_fallback.py.
No database required — all SQL is intercepted via MagicMock.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.context_foundry.retrieval.property_plane import (
    ANSWER_SOURCE_TRUSTED_PROPERTY,
    ANSWER_SOURCE_STAGING_PROPERTY,
    PropertyResult,
    apply_to_agent_result,
    attempt_property_lookup,
    extract_query_parameters,
    format_property_answer,
    is_superlative_or_comparison,
)


# ---------------------------------------------------------------------------
# Helpers (matching test_document_evidence_fallback.py pattern)
# ---------------------------------------------------------------------------

class _Row:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _stub_session(rows=None):
    """Create a MagicMock session that returns `rows` on execute().fetchall()."""
    session = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = rows or []
    session.execute.return_value = result
    return session


def _fact_row(
    id="f1",
    entity_name="Nexus Industries",
    entity_type="FINANCIAL_METRIC",
    lifecycle_state="TRUSTED",
    attribute_name="revenue",
    attribute_value="$8.45 billion",
    numeric_value=8450000000.0,
    unit="USD",
    value_type="CURRENCY",
    period="FY2025",
    fiscal_year="2025",
    confidence=0.9,
):
    return _Row(
        id=id,
        entity_name=entity_name,
        entity_type=entity_type,
        lifecycle_state=lifecycle_state,
        attribute_name=attribute_name,
        attribute_value=attribute_value,
        numeric_value=numeric_value,
        unit=unit,
        value_type=value_type,
        period=period,
        fiscal_year=fiscal_year,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Tests: non-attribute queries return None
# ---------------------------------------------------------------------------

def test_non_attribute_query_returns_none():
    """Non-attribute queries (e.g. 'Who is the CEO?') must not trigger property lookup."""
    session = _stub_session([_fact_row()])
    result = attempt_property_lookup(
        session, "t-1", "Who is the CEO of Nexus Industries?"
    )
    assert result is None
    # No SQL should be executed for non-attribute queries
    session.execute.assert_not_called()


def test_relationship_query_returns_none():
    """Relationship queries must not trigger property lookup."""
    session = _stub_session([_fact_row()])
    result = attempt_property_lookup(
        session, "t-1", "Does Nexus Industries partner with Boeing?"
    )
    assert result is None


# ---------------------------------------------------------------------------
# Tests: attribute query with matching fact returns PropertyResult
# ---------------------------------------------------------------------------

def test_attribute_query_with_fact_returns_result():
    """Attribute query with a matching fact should return a PropertyResult."""
    session = _stub_session([_fact_row()])
    result = attempt_property_lookup(
        session, "t-1", "What is Nexus Industries' revenue?"
    )
    assert result is not None
    assert isinstance(result, PropertyResult)
    assert result.answer_source == ANSWER_SOURCE_TRUSTED_PROPERTY
    assert result.attribute_name == "revenue"
    assert "8.45 billion" in result.answer


def test_budget_query_returns_result():
    """Budget queries should match the budget attribute."""
    session = _stub_session([_fact_row(
        attribute_name="budget",
        attribute_value="$2.3 billion",
        numeric_value=2.3e9,
        entity_name="Quantum Shield",
        entity_type="PROJECT",
    )])
    result = attempt_property_lookup(
        session, "t-1", "What is the Quantum Shield budget?"
    )
    assert result is not None
    assert "2.3 billion" in result.answer


def test_qubits_query_returns_result():
    """Spec queries (qubits) should return property results."""
    session = _stub_session([_fact_row(
        attribute_name="qubits",
        attribute_value="127 qubits",
        numeric_value=127.0,
        unit="qubits",
        value_type="SPEC",
        entity_name="Quantum Computing Platform",
        entity_type="PRODUCT",
    )])
    result = attempt_property_lookup(
        session, "t-1", "How many qubits does the quantum computing platform have?"
    )
    assert result is not None
    assert "127" in result.answer


# ---------------------------------------------------------------------------
# Tests: property overrides confident KG answer (critical — unlike DocEv)
# ---------------------------------------------------------------------------

def test_property_overrides_kg_answer():
    """Property plane should REPLACE a KG answer (unlike DocEv which defers)."""
    session = _stub_session([_fact_row()])
    result = attempt_property_lookup(
        session, "t-1",
        "What is Nexus Industries' revenue?",
        kg_answer="Revenue was approximately $7 billion.",
        kg_answer_source="TRUSTED_GRAPH_FACT",
    )
    # Property plane should still fire — it overrides KG answers
    assert result is not None
    assert result.answer_source == ANSWER_SOURCE_TRUSTED_PROPERTY


def test_apply_replaces_agent_result_answer():
    """apply_to_agent_result should mutate agent_result with property answer."""
    session = _stub_session([_fact_row()])
    agent_result = {
        "answer": "Revenue was approximately $7 billion.",
        "answer_source": "TRUSTED_GRAPH_FACT",
    }
    out = apply_to_agent_result(
        agent_result, session=session, tenant_id="t-1",
        query="What is Nexus Industries' revenue?"
    )
    assert out["answer_source"] == ANSWER_SOURCE_TRUSTED_PROPERTY
    assert "8.45 billion" in out["answer"]
    assert out["property_plane_diagnostics"]["hit"] is True


# ---------------------------------------------------------------------------
# Tests: no facts match → return None (fall-through to DocEv)
# ---------------------------------------------------------------------------

def test_no_matching_facts_returns_none():
    """When no property facts match, return None for fall-through."""
    session = _stub_session([])  # empty results
    result = attempt_property_lookup(
        session, "t-1", "What is Nexus Industries' revenue?"
    )
    assert result is None


def test_apply_preserves_answer_when_no_facts():
    """apply_to_agent_result should not change answer when no facts match."""
    session = _stub_session([])
    agent_result = {"answer": "I don't know.", "extra": {}}
    out = apply_to_agent_result(
        agent_result, session=session, tenant_id="t-1",
        query="What is Nexus Industries' revenue?"
    )
    assert out["answer"] == "I don't know."
    assert out["property_plane_diagnostics"]["hit"] is False


# ---------------------------------------------------------------------------
# Tests: tenant scoping
# ---------------------------------------------------------------------------

def test_tenant_id_passed_to_sql():
    """Every SQL query must include tenant_id."""
    session = _stub_session([_fact_row()])
    attempt_property_lookup(
        session, "tenant-ABC-123", "What is Nexus Industries' revenue?"
    )
    assert session.execute.called
    call_args = session.execute.call_args
    params = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs
    assert params["tid"] == "tenant-ABC-123"


# ---------------------------------------------------------------------------
# Tests: read-only invariant
# ---------------------------------------------------------------------------

def test_lookup_does_not_mutate_session():
    """Property plane lookups must never call add/commit/delete/merge/flush."""
    session = _stub_session([_fact_row()])
    attempt_property_lookup(
        session, "t-1", "What is Nexus Industries' revenue?"
    )
    for method in ("add", "add_all", "commit", "delete", "merge", "flush"):
        assert not getattr(session, method).called, (
            f"session.{method}() must not be called during lookup"
        )


def test_apply_does_not_mutate_session():
    """apply_to_agent_result must not mutate the session."""
    session = _stub_session([_fact_row()])
    agent_result = {"answer": "old", "extra": {}}
    apply_to_agent_result(
        agent_result, session=session, tenant_id="t-1",
        query="What is Nexus Industries' revenue?"
    )
    for method in ("add", "add_all", "commit", "delete", "merge", "flush"):
        assert not getattr(session, method).called, (
            f"session.{method}() must not be called by apply helper"
        )


# ---------------------------------------------------------------------------
# Tests: format_property_answer
# ---------------------------------------------------------------------------

def test_format_currency_answer():
    fact = _fact_row(value_type="CURRENCY")
    answer = format_property_answer("What is revenue?", fact, {})
    assert "Nexus Industries" in answer
    assert "$8.45 billion" in answer


def test_format_spec_answer():
    fact = _fact_row(
        entity_name="Quantum Platform",
        attribute_name="qubits",
        attribute_value="127 qubits",
        value_type="SPEC",
        period=None,
    )
    answer = format_property_answer("How many qubits?", fact, {})
    assert "127 qubits" in answer


def test_format_date_answer():
    fact = _fact_row(
        entity_name="Project Titan",
        attribute_name="end_date",
        attribute_value="2026-12-31",
        value_type="DATE",
        period=None,
    )
    answer = format_property_answer("What is the target date?", fact, {})
    assert "2026-12-31" in answer


def test_format_count_answer():
    fact = _fact_row(
        entity_name="Nexus Industries",
        attribute_name="headcount",
        attribute_value="12,500",
        value_type="COUNT",
        period="FY2025",
    )
    answer = format_property_answer("What is the headcount?", fact, {})
    assert "12,500" in answer
    assert "Nexus Industries" in answer


# ---------------------------------------------------------------------------
# Tests: extract_query_parameters
# ---------------------------------------------------------------------------

def test_extract_revenue_query():
    params = extract_query_parameters("What is Nexus Industries' revenue?", "money")
    assert params["attribute_name"] == "revenue"


def test_extract_budget_query():
    params = extract_query_parameters("What is the Quantum Shield budget?", "money")
    assert params["attribute_name"] == "budget"


def test_extract_qubits_query():
    params = extract_query_parameters(
        "How many qubits does the quantum computing platform have?", "spec"
    )
    assert params["attribute_name"] == "qubits"


def test_extract_fiscal_year():
    params = extract_query_parameters(
        "What is Nexus Industries' revenue in FY2025?", "money"
    )
    assert params["fiscal_year"] == "2025"


def test_extract_what_was_entity():
    """'What was' must extract entity name just like 'What is'."""
    params = extract_query_parameters(
        "What was Nexus Industries' revenue in FY2025?", "money"
    )
    assert params["entity_name"] == "Nexus Industries"
    assert params["attribute_name"] == "revenue"
    assert params["fiscal_year"] == "2025"


# ---------------------------------------------------------------------------
# Tests: answer_source correctness
# ---------------------------------------------------------------------------

def test_trusted_fact_gives_trusted_source():
    session = _stub_session([_fact_row(lifecycle_state="TRUSTED")])
    result = attempt_property_lookup(
        session, "t-1", "What is Nexus Industries' revenue?"
    )
    assert result is not None
    assert result.answer_source == ANSWER_SOURCE_TRUSTED_PROPERTY


def test_staging_fact_gives_staging_source():
    session = _stub_session([_fact_row(lifecycle_state="STAGING")])
    result = attempt_property_lookup(
        session, "t-1", "What is Nexus Industries' revenue?"
    )
    assert result is not None
    assert result.answer_source == ANSWER_SOURCE_STAGING_PROPERTY


# ---------------------------------------------------------------------------
# Tests: DocEv gate respects property sources
# ---------------------------------------------------------------------------

def test_docev_gate_respects_trusted_property():
    """DocEv's classify_agent_kg_source must treat TRUSTED_PROPERTY as authoritative."""
    from src.context_foundry.retrieval.document_evidence_fallback import (
        ANSWER_SOURCE_TRUSTED_GRAPH,
        classify_agent_kg_source,
    )
    agent_result = {
        "answer": "$8.45 billion",
        "answer_source": "TRUSTED_PROPERTY",
    }
    assert classify_agent_kg_source(agent_result) == ANSWER_SOURCE_TRUSTED_GRAPH


def test_docev_gate_respects_staging_property():
    """DocEv's classify_agent_kg_source must treat STAGING_PROPERTY as authoritative."""
    from src.context_foundry.retrieval.document_evidence_fallback import (
        ANSWER_SOURCE_TRUSTED_GRAPH,
        classify_agent_kg_source,
    )
    agent_result = {
        "answer": "$8.45 billion",
        "answer_source": "STAGING_PROPERTY",
    }
    assert classify_agent_kg_source(agent_result) == ANSWER_SOURCE_TRUSTED_GRAPH


# ---------------------------------------------------------------------------
# Tests: web_app.py wiring
# ---------------------------------------------------------------------------

def test_property_plane_wiring_in_web_app():
    """web_app.py must invoke the property plane hook."""
    web_app_path = os.path.join(os.path.dirname(__file__), "..", "..", "web_app.py")
    with open(web_app_path) as f:
        body = f.read()
    assert "property_plane" in body, "web_app.py must reference property_plane module"
    assert "_apply_prop_plane" in body, "web_app.py must invoke property plane helper"
    assert "STAGE 3A" in body, "web_app.py wiring must be tagged STAGE 3A"


# ---------------------------------------------------------------------------
# Tests: superlative / comparison rejection (Fix 3)
# ---------------------------------------------------------------------------

def test_superlative_highest_rejected():
    assert is_superlative_or_comparison("Which project has the highest budget?") is True


def test_superlative_largest_rejected():
    assert is_superlative_or_comparison("What is the largest contract value?") is True


def test_comparison_vs_rejected():
    assert is_superlative_or_comparison("Boeing vs Airbus — which has more revenue?") is True


def test_variance_rejected():
    assert is_superlative_or_comparison("What is the variance between Q3 and Q4 revenue?") is True


def test_combined_aggregate_rejected():
    assert is_superlative_or_comparison("What is the total revenue across all divisions?") is True


def test_simple_attribute_not_rejected():
    assert is_superlative_or_comparison("What is Nexus Industries' revenue?") is False


def test_superlative_query_returns_none_from_lookup():
    """Superlative queries must return None even if facts exist."""
    session = _stub_session([_fact_row()])
    result = attempt_property_lookup(
        session, "t-1", "Which project has the highest budget?"
    )
    assert result is None


# ---------------------------------------------------------------------------
# Tests: value-shaped entity name filtering (Fix 1)
# ---------------------------------------------------------------------------

def test_value_shaped_entity_filtered_from_results():
    """Property facts with value-shaped entity names must be filtered out."""
    rows = [
        _fact_row(entity_name="71 billion USD", attribute_value="71 billion USD"),
        _fact_row(entity_name="Nexus Industries", attribute_value="$8.45 billion"),
    ]
    session = _stub_session(rows)
    result = attempt_property_lookup(
        session, "t-1", "What is Nexus Industries' revenue?"
    )
    assert result is not None
    assert result.entity_name == "Nexus Industries"


def test_all_value_shaped_entities_filtered_returns_none():
    """If ALL results have value-shaped entity names, return None."""
    rows = [
        _fact_row(entity_name="71 billion USD", attribute_value="71 billion USD"),
        _fact_row(entity_name="$8.45 billion", attribute_value="$8.45 billion"),
    ]
    session = _stub_session(rows)
    result = attempt_property_lookup(
        session, "t-1", "What is Nexus Industries' revenue?"
    )
    assert result is None


# ---------------------------------------------------------------------------
# Tests: entity disambiguation (Fix 2)
# ---------------------------------------------------------------------------

def test_exact_entity_match_preferred():
    """When multiple entities match, prefer the exact match."""
    rows = [
        _fact_row(entity_name="Nexus Industries Subsidiary", attribute_value="$2 billion"),
        _fact_row(entity_name="Nexus Industries", attribute_value="$8.45 billion"),
    ]
    session = _stub_session(rows)
    result = attempt_property_lookup(
        session, "t-1", "What is Nexus Industries' revenue?"
    )
    assert result is not None
    assert result.entity_name == "Nexus Industries"
    assert "8.45 billion" in result.answer


# ---------------------------------------------------------------------------
# Tests: broader lookup never returns wrong entity (Fix A)
# ---------------------------------------------------------------------------

def test_broader_lookup_does_not_drop_entity():
    """When query names an entity that doesn't exist, return None — not a random entity."""
    # First call (strict) returns empty, second call (broader) also returns empty
    # because broader lookup should NOT drop entity_name
    session = _stub_session([])  # no matches at all
    result = attempt_property_lookup(
        session, "t-1", "What is the Falcon X budget?"
    )
    # Should be None rather than returning some random entity's budget
    assert result is None


def test_q4_fy2025_revenue_filtered():
    """Entity name 'Q4 FY2025 Revenue' is value-shaped and must be filtered."""
    rows = [_fact_row(entity_name="Q4 FY2025 Revenue", attribute_value="$8.45B")]
    session = _stub_session(rows)
    result = attempt_property_lookup(
        session, "t-1", "What is Nexus Industries' revenue in FY2025?"
    )
    assert result is None


def test_revenue_target_2026_filtered():
    """Entity name 'Revenue Target 2026' is value-shaped and must be filtered."""
    rows = [_fact_row(entity_name="Revenue Target 2026", attribute_value="$9.5-9.8 billion")]
    session = _stub_session(rows)
    result = attempt_property_lookup(
        session, "t-1", "What was Nexus Industries' revenue in FY2025?"
    )
    assert result is None
