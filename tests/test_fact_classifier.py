from datetime import date

from context_foundry.metrics.temporal import NormalizedPeriod
from context_foundry.aggregation.fact_classifier import classify_fact_pair, FactRelation


def test_classifier_conflict_same_entity_same_period():
    p = NormalizedPeriod(start=date(2024,1,1), end=date(2024,12,31), label="FY2024")
    rel = classify_fact_pair("Org", "Org", "REVENUE", "REVENUE", p, p, None, None)
    assert rel == FactRelation.CONFLICT


def test_classifier_complement_cross_entity():
    p = NormalizedPeriod(start=date(2024,1,1), end=date(2024,12,31), label="FY2024")
    rel = classify_fact_pair("A", "B", "REVENUE", "REVENUE", p, p, None, None)
    assert rel == FactRelation.COMPLEMENT_CROSS_ENTITY


def test_classifier_hierarchical():
    p = NormalizedPeriod(start=date(2024,1,1), end=date(2024,12,31), label="FY2024")
    rel = classify_fact_pair("Org", "Org", "REVENUE", "REVENUE.COMMERCIAL", p, p, None, None)
    assert rel == FactRelation.HIERARCHICAL
