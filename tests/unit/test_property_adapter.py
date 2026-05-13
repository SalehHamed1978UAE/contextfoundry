"""Unit tests for Property Adapter (Stage 3A M2).

Tests the numeric parser, entity-type parsers, and adapter plumbing.
No database required — entity dicts are constructed in-memory.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.context_foundry.adapters.property_adapter import (
    PropertyAdapter,
    detect_unit,
    detect_value_type,
    parse_customer,
    parse_facility,
    parse_financial_metric,
    parse_numeric,
    parse_product,
    parse_project,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entity(
    name="Test Entity",
    entity_type="FINANCIAL_METRIC",
    properties=None,
    lifecycle_state="TRUSTED",
    entity_id="e-1",
    source_document_id="doc-1",
    confidence=0.9,
):
    return {
        "id": entity_id,
        "name": name,
        "entity_type": entity_type,
        "properties": properties or {},
        "lifecycle_state": lifecycle_state,
        "source_document_id": source_document_id,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Tests: parse_numeric
# ---------------------------------------------------------------------------

def test_parse_numeric_dollars_billions():
    assert parse_numeric("$8.45 billion") == pytest.approx(8.45e9)


def test_parse_numeric_dollars_millions():
    assert parse_numeric("$145 million") == pytest.approx(1.45e8)


def test_parse_numeric_plain_number():
    assert parse_numeric("127") == pytest.approx(127.0)


def test_parse_numeric_number_with_commas():
    assert parse_numeric("12,500") == pytest.approx(12500.0)


def test_parse_numeric_number_with_unit():
    assert parse_numeric("425 kg/hr") == pytest.approx(425.0)


def test_parse_numeric_percentage():
    assert parse_numeric("23.5%") == pytest.approx(23.5)


def test_parse_numeric_returns_none_for_date():
    assert parse_numeric("2025-01-15") is None


def test_parse_numeric_returns_none_for_quarter():
    assert parse_numeric("Q3 2025") is None


def test_parse_numeric_returns_none_for_date_range():
    assert parse_numeric("Jan 2025 - Dec 2026") is None


def test_parse_numeric_returns_none_for_empty():
    assert parse_numeric("") is None
    assert parse_numeric(None) is None


def test_parse_numeric_currency_symbol_euro():
    assert parse_numeric("€50 million") == pytest.approx(5e7)


def test_parse_numeric_thousand():
    assert parse_numeric("$500 thousand") == pytest.approx(500000.0)


# ---------------------------------------------------------------------------
# Tests: detect_value_type
# ---------------------------------------------------------------------------

def test_detect_value_type_currency():
    assert detect_value_type("$8.45 billion") == "CURRENCY"


def test_detect_value_type_percentage():
    assert detect_value_type("23.5%") == "PERCENTAGE"


def test_detect_value_type_date():
    assert detect_value_type("2025-01-15", "start_date") == "DATE"


def test_detect_value_type_count():
    assert detect_value_type("12500", "headcount") == "COUNT"


def test_detect_value_type_spec():
    assert detect_value_type("425 kg/hr") == "SPEC"


def test_detect_value_type_currency_by_key():
    assert detect_value_type("8.45", "revenue") == "CURRENCY"


# ---------------------------------------------------------------------------
# Tests: detect_unit
# ---------------------------------------------------------------------------

def test_detect_unit_usd():
    assert detect_unit("$8.45 billion") == "USD"


def test_detect_unit_percent():
    assert detect_unit("23.5%") == "%"


def test_detect_unit_kg_hr():
    assert detect_unit("425 kg/hr") == "kg/hr"


def test_detect_unit_qubits():
    assert detect_unit("127 qubits") == "qubits"


# ---------------------------------------------------------------------------
# Tests: parse_financial_metric
# ---------------------------------------------------------------------------

def test_parse_financial_metric_basic():
    ent = _entity(
        name="Total Revenue",
        entity_type="FINANCIAL_METRIC",
        properties={
            "metric_name": "Total Revenue",
            "value": "$8.45 billion",
            "value_type": "currency",
            "period": "FY2025",
            "fiscal_year": "2025",
            "unit": "USD",
        },
    )
    facts = parse_financial_metric(ent)
    assert len(facts) >= 1
    fact = facts[0]
    assert fact["attribute_name"] == "total_revenue"
    assert fact["attribute_value"] == "$8.45 billion"
    assert fact["numeric_value"] == pytest.approx(8.45e9)
    assert fact["fiscal_year"] == "2025"
    assert fact["period"] == "FY2025"


def test_parse_financial_metric_preserves_lifecycle():
    ent = _entity(
        name="Backlog",
        entity_type="FINANCIAL_METRIC",
        properties={"metric_name": "Backlog", "value": "$12.4 billion"},
        lifecycle_state="STAGING",
    )
    facts = parse_financial_metric(ent)
    assert facts[0]["lifecycle_state"] == "STAGING"


def test_parse_financial_metric_empty_value_returns_empty():
    ent = _entity(properties={"metric_name": "Empty", "value": None})
    facts = parse_financial_metric(ent)
    assert facts == []


# ---------------------------------------------------------------------------
# Tests: parse_project
# ---------------------------------------------------------------------------

def test_parse_project_budget():
    ent = _entity(
        name="Quantum Shield",
        entity_type="PROJECT",
        properties={"budget": "$2.3 billion", "status": "Active"},
    )
    facts = parse_project(ent)
    budget_facts = [f for f in facts if f["attribute_name"] == "budget"]
    assert len(budget_facts) == 1
    assert budget_facts[0]["numeric_value"] == pytest.approx(2.3e9)


def test_parse_project_dates():
    ent = _entity(
        name="Project Titan",
        entity_type="PROJECT",
        properties={
            "start_date": "2024-01-15",
            "end_date": "2026-12-31",
        },
    )
    facts = parse_project(ent)
    date_facts = [f for f in facts if f["value_type"] == "DATE"]
    assert len(date_facts) == 2


# ---------------------------------------------------------------------------
# Tests: parse_product
# ---------------------------------------------------------------------------

def test_parse_product_with_specs():
    ent = _entity(
        name="Quantum Computing Platform",
        entity_type="PRODUCT",
        properties={"qubits": "127", "energy_density": "450 Wh/kg"},
    )
    facts = parse_product(ent)
    assert len(facts) == 2
    qubit_fact = [f for f in facts if f["attribute_name"] == "qubits"][0]
    assert qubit_fact["numeric_value"] == pytest.approx(127.0)


# ---------------------------------------------------------------------------
# Tests: parse_customer, parse_facility
# ---------------------------------------------------------------------------

def test_parse_customer_contract_value():
    ent = _entity(
        name="DOD Partnership",
        entity_type="CUSTOMER",
        properties={"contract_value": "$500 million", "region": "North America"},
    )
    facts = parse_customer(ent)
    cv_facts = [f for f in facts if f["attribute_name"] == "contract_value"]
    assert len(cv_facts) == 1
    assert cv_facts[0]["numeric_value"] == pytest.approx(5e8)


def test_parse_facility_capacity():
    ent = _entity(
        name="Austin Manufacturing",
        entity_type="FACILITY",
        properties={"capacity": "425 kg/hr", "facility_type": "Manufacturing"},
    )
    facts = parse_facility(ent)
    cap_facts = [f for f in facts if f["attribute_name"] == "capacity"]
    assert len(cap_facts) == 1
    assert cap_facts[0]["numeric_value"] == pytest.approx(425.0)


# ---------------------------------------------------------------------------
# Tests: tenant_id set on every fact
# ---------------------------------------------------------------------------

def test_facts_carry_entity_metadata():
    """Every fact must carry entity_id, entity_name, entity_type, lifecycle_state."""
    ent = _entity(
        name="Revenue Metric",
        entity_type="FINANCIAL_METRIC",
        properties={"metric_name": "Revenue", "value": "$1 billion"},
        lifecycle_state="TRUSTED",
        entity_id="ent-42",
    )
    facts = parse_financial_metric(ent)
    assert len(facts) >= 1
    for f in facts:
        assert f["entity_id"] == "ent-42"
        assert f["entity_name"] == "Revenue Metric"
        assert f["entity_type"] == "FINANCIAL_METRIC"
        assert f["lifecycle_state"] == "TRUSTED"
