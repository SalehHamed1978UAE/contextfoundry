from context_foundry.aggregation.structured_compute import ComponentValue, structured_sum, compute_top_n


def test_structured_sum_with_expected_count():
    comps = [
        ComponentValue(entity="A", value=10.0, metric="REVENUE"),
        ComponentValue(entity="B", value=5.0, metric="REVENUE"),
    ]
    result = structured_sum(comps, expected_count=3)
    assert result.total == 15.0
    assert result.coverage_percent == 2/3


def test_compute_top_n():
    comps = [
        ComponentValue(entity="A", value=10.0, metric="REVENUE"),
        ComponentValue(entity="B", value=5.0, metric="REVENUE"),
        ComponentValue(entity="C", value=7.0, metric="REVENUE"),
    ]
    top = compute_top_n(comps, 2)
    assert [c.entity for c in top] == ["A", "C"]
