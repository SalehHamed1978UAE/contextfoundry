"""
Piece 0.5 — strict domain filter on OntologyRepository.
Piece 0.6 — governed disposition of foundational organizational relations (2026-05-10).

Verifies that get_all_types/get_all_relations(domain_id=...) returns only rows
where domain_id matches exactly, NOT rows with domain_id IS NULL. The previous
behaviour leaked 834 NULL-domain type rows into every domain-scoped query.

Counts are anchored to the deterministic Piece 0 backfill plus Piece 0.6 mutation:
  - core types:       25 type rows  (00_shared_ontology.sql)
  - finance types:    28 type rows  (06_finance_ontology.sql)
  - healthcare types: 26 type rows  (03_health_ontology.sql)
  - aviation types:   27 type rows  (05_aviation_ontology.sql)
  - get_all_types() (no filter, ACTIVE only): 1033 rows

Piece 0.6 (ADR-011, mutation 2026-05-10):
  - core relations:    17 deterministic + 4 from Piece 0.6 = 21
  - finance relations: 27 deterministic + 1 from Piece 0.6 = 28
  - HAS_COMPENSATION (PERSON → CONCEPT) is DEPRECATED (mis-targeted), excluded
    from default ACTIVE-only calls and present only when include_deprecated=True.
"""
import os
import pytest

from src.context_foundry.ontology.repository import OntologyRepository


@pytest.fixture(scope="module")
def repo():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set; ontology repository tests require live DB")
    return OntologyRepository()


def test_core_returns_exactly_25(repo):
    rows = repo.get_all_types(domain_id="core")
    assert len(rows) == 25, f"expected 25 core types, got {len(rows)}"
    for r in rows:
        assert r.domain_id == "core"


def test_finance_returns_exactly_28(repo):
    rows = repo.get_all_types(domain_id="finance")
    assert len(rows) == 28, f"expected 28 finance types, got {len(rows)}"
    for r in rows:
        assert r.domain_id == "finance"


def test_healthcare_returns_exactly_26(repo):
    rows = repo.get_all_types(domain_id="healthcare")
    assert len(rows) == 26
    for r in rows:
        assert r.domain_id == "healthcare"


def test_no_filter_returns_full_active_set(repo):
    rows = repo.get_all_types()  # include_deprecated default False
    # 1037 total rows; 4 are non-ACTIVE (2 PROPOSED + 2 APPROVED), so default returns 1033
    assert len(rows) == 1033, f"expected 1033 ACTIVE types, got {len(rows)}"


def test_null_domain_rows_excluded_from_domain_scoped_lookup(repo):
    # NULL-domain rows include the 24 layer-1 foundational types (Person, Event, etc.)
    # and 803 layer-2 ad-hoc UPPER_SNAKE types. None should appear under any of the
    # eight canonical domains.
    canonical = ["core", "it_infrastructure", "supply_chain", "healthcare",
                 "manufacturing", "aviation", "finance", "construction"]
    for d in canonical:
        rows = repo.get_all_types(domain_id=d)
        for r in rows:
            assert r.domain_id == d, (
                f"NULL-domain row leaked into {d} lookup: id={r.id} type_name={r.type_name} "
                f"actual_domain={r.domain_id!r}"
            )


def test_relations_strict_filter_core(repo):
    rows = repo.get_all_relations(domain_id="core")
    # 17 deterministic seed-file UUIDs from 00_shared_ontology.sql,
    # PLUS 4 governed by Piece 0.6 mutation (ADR-011, 2026-05-10):
    #   HOLDS_POSITION (PERSON→JOB_TITLE), HOLDS_POSITION (PERSON→ORGANIZATION),
    #   WORKS_AT (PERSON→ORGANIZATION), REPORTS_TO (PERSON→PERSON).
    # See docs/architecture.md Gap 5 (RESOLVED) and the Piece 0.6 prerequisite section.
    assert len(rows) == 21, f"expected 21 core relations (17 + 4 from Piece 0.6), got {len(rows)}"
    for r in rows:
        assert r.domain_id == "core"


def test_relations_strict_filter_finance(repo):
    rows = repo.get_all_relations(domain_id="finance")
    # 27 deterministic seed-file UUIDs from 06_finance_ontology.sql,
    # PLUS 1 governed by Piece 0.6 mutation (ADR-011, 2026-05-10):
    #   HAS_COMPENSATION (PERSON→COMPENSATION).
    assert len(rows) == 28, f"expected 28 finance relations (27 + 1 from Piece 0.6), got {len(rows)}"
    for r in rows:
        assert r.domain_id == "finance"


def test_piece_0_6_core_relations_present(repo):
    """Piece 0.6 governed HOLDS_POSITION (both signatures), WORKS_AT, REPORTS_TO into core."""
    rows = repo.get_all_relations(domain_id="core")
    pairs = {(r.relation_type, r.source_type_name, r.target_type_name) for r in rows}
    assert ("HOLDS_POSITION", "PERSON", "JOB_TITLE") in pairs, \
        "Piece 0.6: HOLDS_POSITION (PERSON→JOB_TITLE) must be in core"
    assert ("HOLDS_POSITION", "PERSON", "ORGANIZATION") in pairs, \
        "Piece 0.6: HOLDS_POSITION (PERSON→ORGANIZATION) must be in core"
    assert ("WORKS_AT", "PERSON", "ORGANIZATION") in pairs, \
        "Piece 0.6: WORKS_AT (PERSON→ORGANIZATION) must be in core"
    assert ("REPORTS_TO", "PERSON", "PERSON") in pairs, \
        "Piece 0.6: REPORTS_TO (PERSON→PERSON) must be in core"


def test_piece_0_6_has_compensation_in_finance(repo):
    """Piece 0.6 governed HAS_COMPENSATION (PERSON→COMPENSATION) into finance."""
    rows = repo.get_all_relations(domain_id="finance")
    pairs = {(r.relation_type, r.source_type_name, r.target_type_name) for r in rows}
    assert ("HAS_COMPENSATION", "PERSON", "COMPENSATION") in pairs, \
        "Piece 0.6: HAS_COMPENSATION (PERSON→COMPENSATION) must be in finance"


def test_piece_0_6_deprecated_has_compensation_excluded_by_default(repo):
    """Piece 0.6 deprecated the mis-targeted HAS_COMPENSATION (PERSON→CONCEPT).
    It must not appear in default (status='ACTIVE') calls."""
    rows = repo.get_all_relations()  # include_deprecated=False default
    pairs = {(r.relation_type, r.source_type_name, r.target_type_name) for r in rows}
    assert ("HAS_COMPENSATION", "PERSON", "CONCEPT") not in pairs, \
        "Piece 0.6: deprecated HAS_COMPENSATION (PERSON→CONCEPT) must be excluded from default calls"


def test_piece_0_6_deprecated_has_compensation_visible_with_include_deprecated(repo):
    """The deprecated row must still be retrievable via include_deprecated=True for audit."""
    rows = repo.get_all_relations(include_deprecated=True)
    pairs = {(r.relation_type, r.source_type_name, r.target_type_name) for r in rows}
    assert ("HAS_COMPENSATION", "PERSON", "CONCEPT") in pairs, \
        "Piece 0.6: deprecated HAS_COMPENSATION (PERSON→CONCEPT) must be present when include_deprecated=True"


def test_piece_0_6_null_domain_rows_still_dont_leak_into_scoped_calls(repo):
    """Piece 0.5 invariant must hold post-Piece 0.6: no NULL-domain relation leaks
    into domain-scoped lookup."""
    canonical = ["core", "it_infrastructure", "supply_chain", "healthcare",
                 "manufacturing", "aviation", "finance", "construction"]
    for d in canonical:
        rows = repo.get_all_relations(domain_id=d)
        for r in rows:
            assert r.domain_id == d, (
                f"NULL-domain relation leaked into {d} lookup: id={r.id} "
                f"relation_type={r.relation_type} actual_domain={r.domain_id!r}"
            )
