from __future__ import annotations

from datetime import date
from typing import Optional, Literal

from pydantic import BaseModel, Field

MeasurementBasis = Literal[
    "annual",
    "quarterly",
    "lifetime",
    "per-unit",
    "cumulative",
    "unknown",
]

TargetVsActual = Literal[
    "target",
    "actual",
    "forecast",
    "unknown",
]

UnitType = Literal[
    "B",
    "M",
    "K",
    "%",
    "count",
    "unknown",
]


class MetricRecord(BaseModel):
    """Canonical metric schema for extraction and normalization."""

    metric_name: str = Field(..., description="Raw metric label from source")
    value: float = Field(..., description="Numeric value")
    unit: UnitType = Field("unknown", description="Normalized unit (B, M, K, %, count)")
    currency: Optional[str] = Field(None, description="ISO 4217 currency code")

    time_period: Optional[str] = Field(
        None, description="Normalized time period label (e.g., Q1 2024, FY2024)"
    )
    source_date: Optional[date] = Field(
        None, description="Publication date of the source document"
    )
    reporting_period: Optional[str] = Field(
        None, description="Fiscal period the metric refers to (used for conflict checks)"
    )

    scope: Optional[str] = Field(
        None, description="Entity/division/segment/geography scope"
    )
    measurement_basis: MeasurementBasis = Field(
        "unknown", description="Annual, quarterly, lifetime, per-unit, cumulative"
    )
    target_vs_actual: TargetVsActual = Field(
        "unknown", description="Target, actual, forecast, or unknown"
    )

    canonical_metric: Optional[str] = Field(
        None, description="Canonical metric key after mapping"
    )

    class Config:
        use_enum_values = True
