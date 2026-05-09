"""
Piece 0.5 — strict domain filter on OntologyRepository.

Verifies that get_all_types/get_all_relations(domain_id=...) returns only rows
where domain_id matches exactly, NOT rows with domain_id IS NULL. The previous
behaviour leaked 834 NULL-domain type rows into every domain-scoped query.

Counts are anchored to the deterministic Piece 0 backfill:
  - core:       25 type rows  (00_shared_ontology.sql)
  - finance:    28 type rows  (06_finance_ontology.sql)
  - healthcare: 26 type rows  (03_health_ontology.sql)
  - aviation:   27 type rows  (05_aviation_ontology.sql)
  - get_all_types() (no filter, ACTIVE only): 1033 rows
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
    # 17 deterministic seed-file UUIDs from 00_shared_ontology.sql.
    # The 4 untraceable_preexisting rows (HOLDS_POSITION, HAS_COMPENSATION,
    # REPORTS_TO, WORKS_AT) were reset to NULL during Piece 0 closeout per
    # Option A's strict-determinism rule. See docs/architecture.md Gap 5
    # and the Piece 0.6 prerequisite note.
    assert len(rows) == 17, f"expected 17 core relations, got {len(rows)}"
    for r in rows:
        assert r.domain_id == "core"
