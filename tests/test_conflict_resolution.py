from context_foundry.conflict import Fact, FactEvidence, detect_conflicts, resolve_conflict


def test_detect_conflict_one_to_one():
    facts = [
        Fact(subject="Org", predicate="CEO_OF", obj="Alice"),
        Fact(subject="Org", predicate="CEO_OF", obj="Bob"),
    ]
    conflicts = detect_conflicts(facts)
    assert len(conflicts) == 1


def test_resolve_conflict_prefers_higher_trust():
    facts = [
        Fact(
            subject="Org",
            predicate="CEO_OF",
            obj="Alice",
            confidence=0.6,
            evidence=FactEvidence(source_type="annual_report"),
        ),
        Fact(
            subject="Org",
            predicate="CEO_OF",
            obj="Bob",
            confidence=0.9,
            evidence=FactEvidence(source_type="email"),
        ),
    ]
    group = detect_conflicts(facts)[0]
    result = resolve_conflict(group)
    assert result.selected is not None
    assert result.selected.obj == "Alice"
