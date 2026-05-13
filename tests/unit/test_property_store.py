"""Unit tests for PropertyStore (Stage 3A M1).

Uses the _stub_session pattern from test_document_evidence_fallback.py.
No database required — all SQL is intercepted via MagicMock.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, call

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.context_foundry.memory.property_store import PropertyFactRow, PropertyStore


# ---------------------------------------------------------------------------
# Helpers (matching test_document_evidence_fallback.py pattern)
# ---------------------------------------------------------------------------

class _Row:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _stub_session(rows=None):
    """Create a MagicMock session that returns `rows` on execute().fetchall().

    All execute() calls return the same result (set_tenant + lookups).
    """
    session = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = rows or []
    session.execute.return_value = result
    return session


def _fact_row(
    id="f1",
    tenant_id="t-1",
    entity_id="e-1",
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
    source_document_id="doc-1",
    confidence=0.9,
):
    return _Row(
        id=id,
        tenant_id=tenant_id,
        entity_id=entity_id,
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
        source_document_id=source_document_id,
        confidence=confidence,
    )


def _get_lookup_call(session):
    """Return the (sql_text_obj, params) of the lookup execute() call.

    The PropertyStore __init__ calls execute() for set_tenant_context first.
    The lookup is the last execute() call.
    """
    calls = session.execute.call_args_list
    # Last call is the lookup; earlier calls are tenant context setup
    last = calls[-1]
    sql_obj = last.args[0] if last.args else None
    params = last.args[1] if len(last.args) > 1 else {}
    return sql_obj, params


# ---------------------------------------------------------------------------
# Tests: tenant isolation
# ---------------------------------------------------------------------------

def test_tenant_id_passed_to_lookup_attribute():
    """Every lookup_attribute SQL must include tenant_id."""
    session = _stub_session([])
    store = PropertyStore(session, "tenant-ABC")
    store.lookup_attribute("revenue")

    _, params = _get_lookup_call(session)
    assert params["tid"] == "tenant-ABC"


def test_tenant_id_passed_to_lookup_entity_properties():
    """Every lookup_entity_properties SQL must include tenant_id."""
    session = _stub_session([])
    store = PropertyStore(session, "tenant-XYZ")
    store.lookup_entity_properties("Nexus Industries")

    _, params = _get_lookup_call(session)
    assert params["tid"] == "tenant-XYZ"


# ---------------------------------------------------------------------------
# Tests: lifecycle filtering
# ---------------------------------------------------------------------------

def test_trusted_only_default_filters_lifecycle():
    """Default trusted_only=True adds lifecycle_state = 'TRUSTED' to SQL."""
    session = _stub_session([])
    store = PropertyStore(session, "t-1")
    store.lookup_attribute("revenue")

    sql_obj, _ = _get_lookup_call(session)
    sql_str = str(sql_obj.text) if hasattr(sql_obj, 'text') else str(sql_obj)
    assert "TRUSTED" in sql_str


def test_trusted_only_false_omits_lifecycle_filter():
    """trusted_only=False should NOT filter by lifecycle_state."""
    session = _stub_session([])
    store = PropertyStore(session, "t-1")
    store.lookup_attribute("revenue", trusted_only=False)

    sql_obj, _ = _get_lookup_call(session)
    sql_str = str(sql_obj.text) if hasattr(sql_obj, 'text') else str(sql_obj)
    assert "lifecycle_state = 'TRUSTED'" not in sql_str


# ---------------------------------------------------------------------------
# Tests: lookup by attribute + entity + fiscal_year
# ---------------------------------------------------------------------------

def test_lookup_attribute_returns_facts():
    """lookup_attribute returns PropertyFactRow objects."""
    rows = [_fact_row()]
    session = _stub_session(rows)
    store = PropertyStore(session, "t-1")
    results = store.lookup_attribute("revenue")
    assert len(results) == 1
    assert isinstance(results[0], PropertyFactRow)
    assert results[0].attribute_name == "revenue"
    assert results[0].attribute_value == "$8.45 billion"
    assert results[0].numeric_value == 8450000000.0


def test_lookup_attribute_with_entity_name():
    """lookup_attribute with entity_name adds entity filter to SQL."""
    session = _stub_session([])
    store = PropertyStore(session, "t-1")
    store.lookup_attribute("revenue", entity_name="Nexus Industries")

    _, params = _get_lookup_call(session)
    assert params["ename"] == "Nexus Industries"


def test_lookup_attribute_with_fiscal_year():
    """lookup_attribute with fiscal_year adds fiscal_year filter to SQL."""
    session = _stub_session([])
    store = PropertyStore(session, "t-1")
    store.lookup_attribute("revenue", fiscal_year="2025")

    _, params = _get_lookup_call(session)
    assert params["fy"] == "2025"


def test_lookup_attribute_with_entity_type():
    """lookup_attribute with entity_type adds type filter."""
    session = _stub_session([])
    store = PropertyStore(session, "t-1")
    store.lookup_attribute("budget", entity_type="PROJECT")

    _, params = _get_lookup_call(session)
    assert params["etype"] == "PROJECT"


def test_lookup_entity_properties_returns_facts():
    """lookup_entity_properties returns all facts for an entity."""
    rows = [
        _fact_row(attribute_name="revenue", attribute_value="$8.45B"),
        _fact_row(attribute_name="headcount", attribute_value="12,500", numeric_value=12500),
    ]
    session = _stub_session(rows)
    store = PropertyStore(session, "t-1")
    results = store.lookup_entity_properties("Nexus Industries")
    assert len(results) == 2


# ---------------------------------------------------------------------------
# Tests: read-only invariant (lookups must not write)
# ---------------------------------------------------------------------------

def test_lookup_attribute_does_not_mutate_session():
    """Lookups must never call add/commit/delete/merge/flush."""
    session = _stub_session([_fact_row()])
    store = PropertyStore(session, "t-1")
    store.lookup_attribute("revenue")
    for method in ("add", "add_all", "commit", "delete", "merge", "flush"):
        assert not getattr(session, method).called, (
            f"session.{method}() must not be called during lookup"
        )


def test_lookup_entity_properties_does_not_mutate_session():
    """Lookups must never call add/commit/delete/merge/flush."""
    session = _stub_session([_fact_row()])
    store = PropertyStore(session, "t-1")
    store.lookup_entity_properties("Nexus Industries")
    for method in ("add", "add_all", "commit", "delete", "merge", "flush"):
        assert not getattr(session, method).called, (
            f"session.{method}() must not be called during lookup"
        )


# ---------------------------------------------------------------------------
# Tests: empty results
# ---------------------------------------------------------------------------

def test_lookup_attribute_returns_empty_when_no_match():
    """No matching facts -> empty list."""
    session = _stub_session([])
    store = PropertyStore(session, "t-1")
    results = store.lookup_attribute("nonexistent_attribute")
    assert results == []


def test_lookup_entity_properties_returns_empty_when_no_match():
    """No matching entity -> empty list."""
    session = _stub_session([])
    store = PropertyStore(session, "t-1")
    results = store.lookup_entity_properties("Nonexistent Corp")
    assert results == []
