"""
DETERMINISTIC REGRESSION TEST SUITE

Zero LLM interpretation. Pure assertions.
Either passes or fails - no "mea culpa" possible.

Run with:
    pytest tests/test_deterministic_regression.py -v

Or use the gate script:
    python scripts/regression_gate.py

Categories:
1. Ontology Foundry Guards - Ensure known types don't become candidates
2. Relationship Integrity - Verify critical relationships exist in KG
3. Schema Consistency - Verify schema has required types
4. Extraction Pipeline - Verify imports and normalizer work
"""

import os
import sys
import pytest
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


KNOWN_TYPES_MUST_NOT_BE_CANDIDATES = [
    "WORKS_AT",
    "HOLDS_POSITION",
    "HAS_COMPENSATION",
    "REPORTS_TO",
    "FOUNDED",
    "LOCATED_IN",
    "INVESTED_IN",
    "OWNS",
    "BOARD_MEMBER_OF",
    "MANAGES",
    "MEMBER_OF",
    "PART_OF",
    "DEPENDS_ON",
    "USES",
]


@pytest.fixture(scope="session")
def db_session():
    """Get database session without RLS for regression testing."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    from src.context_foundry.models.schema import get_session
    session = get_session(use_rls_role=False)
    yield session
    session.close()


class TestOntologyFoundryGuards:
    """
    CRITICAL: Ensure known types don't end up as candidates.
    This would have caught the Ontology Foundry regression.
    """

    @pytest.mark.regression
    @pytest.mark.critical
    def test_known_types_not_in_candidates(self, db_session):
        """
        Known relationship types should NEVER appear as pending candidates.

        If this test fails, it means the dual-path routing in GraphBuilder
        is incorrectly sending known types to the candidates table instead
        of the knowledge graph.
        """
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT normalized_name, status, COUNT(*) as count
            FROM ontology_candidates
            WHERE normalized_name = ANY(:known_types)
              AND status = 'PENDING'
            GROUP BY normalized_name, status
        """), {"known_types": KNOWN_TYPES_MUST_NOT_BE_CANDIDATES})

        violations = list(result)

        assert len(violations) == 0, (
            f"REGRESSION DETECTED: Known types incorrectly stored as candidates!\n"
            f"Violations: {[(v.normalized_name, v.count) for v in violations]}\n"
            f"\nThis means the Ontology Foundry dual-path routing is broken.\n"
            f"Known types should go to the knowledge graph, not candidates table."
        )

    @pytest.mark.regression
    def test_candidates_table_exists(self, db_session):
        """Verify ontology_candidates table exists."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'ontology_candidates'
            )
        """))
        exists = result.scalar()

        assert exists, "ontology_candidates table does not exist"

    @pytest.mark.regression
    def test_pending_extractions_table_exists(self, db_session):
        """Verify pending_extractions table exists."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'pending_extractions'
            )
        """))
        exists = result.scalar()

        assert exists, "pending_extractions table does not exist"


class TestRelationshipIntegrity:
    """
    Verify relationship types are being stored correctly.
    """

    @pytest.mark.regression
    def test_position_relationships_exist(self, db_session):
        """Verify position-related relationships exist in the KG."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT COUNT(*) FROM relationships
            WHERE relationship_type IN ('HOLDS_POSITION', 'HOLD_POSITION', 'HAS_POSITION', 'HAS_ROLE')
              AND lifecycle_state IN ('TRUSTED', 'STAGING')
        """))
        count = result.scalar()

        assert count > 0, (
            "No position relationships found in knowledge graph.\n"
            "Expected one of: HOLDS_POSITION, HOLD_POSITION, HAS_POSITION, HAS_ROLE"
        )

    @pytest.mark.regression
    def test_compensation_relationships_exist(self, db_session):
        """Verify compensation-related relationships exist in the KG."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT COUNT(*) FROM relationships
            WHERE relationship_type IN ('HAS_COMPENSATION', 'RECEIVES_COMPENSATION', 'HAS_SALARY')
              AND lifecycle_state IN ('TRUSTED', 'STAGING')
        """))
        count = result.scalar()

        assert count > 0, (
            "No compensation relationships found in knowledge graph.\n"
            "Expected one of: HAS_COMPENSATION, RECEIVES_COMPENSATION, HAS_SALARY"
        )

    @pytest.mark.regression
    def test_works_at_relationships_exist(self, db_session):
        """Verify WORKS_AT relationships exist."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT COUNT(*) FROM relationships
            WHERE relationship_type = 'WORKS_AT'
              AND lifecycle_state IN ('TRUSTED', 'STAGING')
        """))
        count = result.scalar()

        assert count > 0, (
            "No WORKS_AT relationships found in knowledge graph.\n"
            "This is a critical relationship type that should always be extracted."
        )

    @pytest.mark.regression
    def test_reports_to_relationships_exist(self, db_session):
        """Verify REPORTS_TO relationships exist."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT COUNT(*) FROM relationships
            WHERE relationship_type = 'REPORTS_TO'
              AND lifecycle_state IN ('TRUSTED', 'STAGING')
        """))
        count = result.scalar()

        assert count > 0, (
            "No REPORTS_TO relationships found in knowledge graph."
        )


class TestSchemaConsistency:
    """
    Verify schema configuration is consistent.
    """

    @pytest.mark.regression
    def test_schema_loader_has_relationship_types(self):
        """Verify schema loader returns relationship types."""
        from src.context_foundry.config.domain_schema import get_schema_loader

        loader = get_schema_loader()
        rel_types = loader.schema.get_relationship_type_names()

        assert len(rel_types) > 0, "Schema has no relationship types defined"

        critical_types = ["WORKS_AT", "HOLDS_POSITION", "REPORTS_TO"]
        for ctype in critical_types:
            assert ctype in rel_types, (
                f"Critical relationship type '{ctype}' not in schema.\n"
                f"Available types: {rel_types}"
            )

    @pytest.mark.regression
    def test_schema_loader_has_entity_types(self):
        """Verify schema loader returns entity types."""
        from src.context_foundry.config.domain_schema import get_schema_loader

        loader = get_schema_loader()
        entity_types = loader.schema.get_entity_type_names()

        assert len(entity_types) > 0, "Schema has no entity types defined"

        critical_types = ["PERSON", "ORGANIZATION"]
        for ctype in critical_types:
            assert ctype in entity_types, (
                f"Critical entity type '{ctype}' not in schema.\n"
                f"Available types: {entity_types}"
            )

    @pytest.mark.regression
    def test_schema_has_compensation_type(self):
        """Verify HAS_COMPENSATION is in the schema."""
        from src.context_foundry.config.domain_schema import get_schema_loader

        loader = get_schema_loader()
        rel_types = loader.schema.get_relationship_type_names()

        assert "HAS_COMPENSATION" in rel_types, (
            "HAS_COMPENSATION not in schema - compensation queries will fail"
        )


class TestExtractionPipeline:
    """
    Verify the extraction pipeline is working correctly.
    """

    @pytest.mark.regression
    def test_staging_loader_imports(self):
        """Verify StagingLoader can be imported."""
        from src.context_foundry.extraction.staging_loader import StagingLoader
        assert StagingLoader is not None

    @pytest.mark.regression
    def test_candidate_store_imports(self):
        """Verify CandidateStore can be imported."""
        from src.context_foundry.ontology.candidate_store import CandidateStore
        assert CandidateStore is not None

    @pytest.mark.regression
    def test_candidate_normalizer_imports(self):
        """Verify CandidateNormalizer can be imported."""
        from src.context_foundry.ontology.normalizer import CandidateNormalizer
        assert CandidateNormalizer is not None

    @pytest.mark.regression
    def test_normalizer_maps_synonyms_correctly(self):
        """Verify normalizer maps synonyms to canonical forms."""
        from src.context_foundry.ontology.normalizer import CandidateNormalizer

        normalizer = CandidateNormalizer()

        assert normalizer.normalize_relationship("INVESTS_IN") == "INVESTED_IN"
        assert normalizer.normalize_relationship("WORKS_FOR") == "WORKS_AT"
        assert normalizer.normalize_relationship("BOUGHT") == "ACQUIRED"

        assert normalizer.normalize_entity("COMPANY") == "ORGANIZATION"
        assert normalizer.normalize_entity("INDIVIDUAL") == "PERSON"

    @pytest.mark.regression
    def test_normalizer_preserves_unknown_types(self):
        """Verify normalizer preserves types that aren't in synonym map."""
        from src.context_foundry.ontology.normalizer import CandidateNormalizer

        normalizer = CandidateNormalizer()

        assert normalizer.normalize_relationship("SOME_NEW_TYPE") == "SOME_NEW_TYPE"
        assert normalizer.normalize_relationship("custom-relation") == "CUSTOM_RELATION"

    @pytest.mark.regression
    def test_compensation_normalizations(self):
        """Verify compensation-related synonyms normalize correctly."""
        from src.context_foundry.ontology.normalizer import CandidateNormalizer

        normalizer = CandidateNormalizer()

        assert normalizer.normalize_relationship("RECEIVES_COMPENSATION") == "HAS_COMPENSATION"
        assert normalizer.normalize_relationship("HAS_SALARY") == "HAS_COMPENSATION"
        assert normalizer.normalize_relationship("HAS_TOTAL_COMPENSATION") == "HAS_COMPENSATION"

    @pytest.mark.regression
    def test_position_normalizations(self):
        """Verify position-related synonyms normalize correctly."""
        from src.context_foundry.ontology.normalizer import CandidateNormalizer

        normalizer = CandidateNormalizer()

        assert normalizer.normalize_relationship("HOLD_POSITION") == "HOLDS_POSITION"
        assert normalizer.normalize_relationship("HAS_POSITION") == "HOLDS_POSITION"
        assert normalizer.normalize_relationship("HAS_ROLE") == "HOLDS_POSITION"


class TestDatabaseIntegrity:
    """
    Basic database integrity checks.
    """

    @pytest.mark.regression
    def test_entities_table_accessible(self, db_session):
        """Verify entities table is accessible."""
        from sqlalchemy import text

        result = db_session.execute(text("SELECT COUNT(*) FROM entities"))
        count = result.scalar()

        assert count >= 0, "entities table not accessible"

    @pytest.mark.regression
    def test_relationships_table_accessible(self, db_session):
        """Verify relationships table is accessible."""
        from sqlalchemy import text

        result = db_session.execute(text("SELECT COUNT(*) FROM relationships"))
        count = result.scalar()

        assert count >= 0, "relationships table not accessible"

    @pytest.mark.regression
    def test_person_entities_exist(self, db_session):
        """Verify PERSON entities exist in the database."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT COUNT(*) FROM entities
            WHERE entity_type = 'PERSON'
              AND lifecycle_state IN ('TRUSTED', 'STAGING')
        """))
        count = result.scalar()

        assert count > 0, "No PERSON entities found - extraction may have failed"

    @pytest.mark.regression
    def test_organization_entities_exist(self, db_session):
        """Verify ORGANIZATION entities exist in the database."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT COUNT(*) FROM entities
            WHERE entity_type = 'ORGANIZATION'
              AND lifecycle_state IN ('TRUSTED', 'STAGING')
        """))
        count = result.scalar()

        assert count > 0, "No ORGANIZATION entities found - extraction may have failed"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "regression: mark test as regression test (run frequently)"
    )
    config.addinivalue_line(
        "markers",
        "critical: mark test as critical (must pass for deployment)"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "regression"])
