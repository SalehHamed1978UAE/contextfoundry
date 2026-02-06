import datetime

from context_foundry.metrics import (
    MetricRecord,
    normalize_period,
    temporal_relationship,
    canonicalize_metric_name,
    METRIC_HIERARCHY,
    is_child_metric,
)


def test_metric_schema_fields():
    record = MetricRecord(
        metric_name="Revenue",
        value=12.5,
        unit="B",
        currency="USD",
        time_period="FY2024",
        source_date=datetime.date(2025, 2, 1),
        reporting_period="FY2024",
        scope="Nexus Industries",
        measurement_basis="annual",
        target_vs_actual="actual",
    )
    assert record.metric_name == "Revenue"
    assert record.value == 12.5
    assert record.reporting_period == "FY2024"


def test_temporal_normalization_quarter():
    period = normalize_period("Q1 2024")
    assert period is not None
    assert period.start == datetime.date(2024, 1, 1)
    assert period.end == datetime.date(2024, 3, 31)

    period2 = normalize_period("first quarter of 2024")
    assert period2 is not None
    assert period2.start == datetime.date(2024, 1, 1)
    assert period2.end == datetime.date(2024, 3, 31)

    assert temporal_relationship(period, period2) == "IDENTICAL"


def test_temporal_normalization_fy_and_half():
    fy = normalize_period("FY 2023")
    assert fy is not None
    assert fy.start == datetime.date(2023, 1, 1)
    assert fy.end == datetime.date(2023, 12, 31)

    h1 = normalize_period("H1 2025")
    assert h1 is not None
    assert h1.start == datetime.date(2025, 1, 1)
    assert h1.end == datetime.date(2025, 6, 30)


def test_canonical_metric_mapping():
    assert canonicalize_metric_name("net sales") == "REVENUE"
    assert canonicalize_metric_name("contract value") == "CONTRACT_VALUE"
    assert canonicalize_metric_name("relationship value") == "RELATIONSHIP_VALUE"
    assert canonicalize_metric_name("commercial revenue") == "REVENUE.COMMERCIAL"


def test_metric_hierarchy():
    assert "REVENUE" in METRIC_HIERARCHY
    assert is_child_metric("REVENUE", "REVENUE.DEFENSE")
