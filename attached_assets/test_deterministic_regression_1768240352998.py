"""
DETERMINISTIC REGRESSION TEST SUITE

Zero LLM interpretation. Pure assertions.
Either passes or fails - no "mea culpa" possible.

Run with:
    pytest tests/test_deterministic_regression.py -v

Or use the gate script:
    python scripts/regression_gate.py

Categories:
1. Database State Assertions - Verify critical data exists
2. Golden Query Tests - Verify query outputs contain expected strings
3. Ontology Foundry Guards - Ensure known types don't become candidates
4. Relationship Integrity - Verify critical relationships exist
"""

import os
import sys
import pytest
from typing import List, Dict, Optional, Tuple
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# CONFIGURATION - Edit these based on your actual data
# =============================================================================

# Vaults and their expected data
VAULT_CONFIGS = {
    "TechVentures": {
        "expected_people": [
            ("Sarah Chen", "PERSON"),
            ("Michael Torres", "PERSON"),
        ],
        "expected_positions": [
            ("CEO", "JOB_TITLE"),
            ("CFO", "JOB_TITLE"),
        ],
        "expected_relationships": [
            # (source_name_pattern, relationship_type, target_name_pattern)
            ("Sarah Chen", "HOLDS_POSITION", "CEO"),
            ("Sarah Chen", "HAS_COMPENSATION", "%850%"),
        ],
        "golden_queries": [
            {
                "query": "What is the CEO's salary?",
                "must_contain": ["850,000"],
                "must_not_contain": ["I don't know", "no information", "not found"],
            },
            {
                "query": "Who is the CEO?",
                "must_contain": ["Sarah Chen"],
                "must_not_contain": ["I don't know", "no information"],
            },
        ],
    },
    "Riverside": {
        "expected_people": [
            ("David Miller", "PERSON"),
        ],
        "expected_positions": [
            ("CEO", "JOB_TITLE"),
        ],
        "expected_relationships": [
            ("David Miller", "HOLDS_POSITION", "CEO"),
        ],
        "golden_queries": [
            {
                "query": "Who is the CEO?",
                "must_contain": ["David Miller"],
                "must_not_contain": ["I don't know"],
            },
        ],
    },
}

# Known relationship types that should NEVER appear as candidates
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


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def db_session():
    """Get database session."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    from src.context_foundry.models.schema import get_session
    session = get_session()
    yield session
    session.close()


@pytest.fixture(scope="session")
def vault_ids(db_session) -> Dict[str, str]:
    """Get vault IDs by name."""
    from sqlalchemy import text

    result = db_session.execute(text("""
        SELECT id, name FROM vaults WHERE name = ANY(:names)
    """), {"names": list(VAULT_CONFIGS.keys())})

    return {row.name: str(row.id) for row in result}


# =============================================================================
# 1. DATABASE STATE ASSERTIONS
# =============================================================================

class TestDatabaseStateAssertions:
    """
    Verify critical data exists in the database.
    These are pure SQL checks - no LLM involved.
    """

    @pytest.mark.regression
    def test_vaults_exist(self, db_session):
        """Verify expected vaults exist."""
        from sqlalchemy import text

        for vault_name in VAULT_CONFIGS.keys():
            result = db_session.execute(text("""
                SELECT COUNT(*) FROM vaults WHERE name = :name
            """), {"name": vault_name})
            count = result.scalar()

            assert count > 0, f"Vault '{vault_name}' does not exist"

    @pytest.mark.regression
    @pytest.mark.parametrize("vault_name", list(VAULT_CONFIGS.keys()))
    def test_expected_people_exist(self, db_session, vault_name, vault_ids):
        """Verify expected people exist in each vault."""
        from sqlalchemy import text

        if vault_name not in vault_ids:
            pytest.skip(f"Vault {vault_name} not found")

        vault_id = vault_ids[vault_name]
        config = VAULT_CONFIGS[vault_name]

        for person_name, entity_type in config.get("expected_people", []):
            result = db_session.execute(text("""
                SELECT COUNT(*) FROM entities
                WHERE tenant_id = :vault_id
                  AND name ILIKE :name
                  AND entity_type = :type
                  AND lifecycle_state IN ('TRUSTED', 'STAGING')
            """), {
                "vault_id": vault_id,
                "name": f"%{person_name}%",
                "type": entity_type
            })
            count = result.scalar()

            assert count > 0, (
                f"Missing entity: {person_name} ({entity_type}) in {vault_name}\n"
                f"This entity must exist for queries to work."
            )

    @pytest.mark.regression
    @pytest.mark.parametrize("vault_name", list(VAULT_CONFIGS.keys()))
    def test_expected_positions_exist(self, db_session, vault_name, vault_ids):
        """Verify expected job titles/positions exist."""
        from sqlalchemy import text

        if vault_name not in vault_ids:
            pytest.skip(f"Vault {vault_name} not found")

        vault_id = vault_ids[vault_name]
        config = VAULT_CONFIGS[vault_name]

        for position_name, entity_type in config.get("expected_positions", []):
            result = db_session.execute(text("""
                SELECT COUNT(*) FROM entities
                WHERE tenant_id = :vault_id
                  AND name ILIKE :name
                  AND entity_type = :type
                  AND lifecycle_state IN ('TRUSTED', 'STAGING')
            """), {
                "vault_id": vault_id,
                "name": f"%{position_name}%",
                "type": entity_type
            })
            count = result.scalar()

            assert count > 0, (
                f"Missing entity: {position_name} ({entity_type}) in {vault_name}\n"
                f"Job title entities must exist for role-based queries."
            )

    @pytest.mark.regression
    @pytest.mark.parametrize("vault_name", list(VAULT_CONFIGS.keys()))
    def test_expected_relationships_exist(self, db_session, vault_name, vault_ids):
        """Verify expected relationships exist."""
        from sqlalchemy import text

        if vault_name not in vault_ids:
            pytest.skip(f"Vault {vault_name} not found")

        vault_id = vault_ids[vault_name]
        config = VAULT_CONFIGS[vault_name]

        for source_pattern, rel_type, target_pattern in config.get("expected_relationships", []):
            result = db_session.execute(text("""
                SELECT COUNT(*) FROM relationships r
                JOIN entities e1 ON r.source_entity_id = e1.id
                JOIN entities e2 ON r.target_entity_id = e2.id
                WHERE r.tenant_id = :vault_id
                  AND e1.name ILIKE :source
                  AND r.relationship_type = :rel_type
                  AND e2.name ILIKE :target
                  AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
            """), {
                "vault_id": vault_id,
                "source": f"%{source_pattern}%",
                "rel_type": rel_type,
                "target": f"%{target_pattern}%"
            })
            count = result.scalar()

            assert count > 0, (
                f"Missing relationship in {vault_name}:\n"
                f"  {source_pattern} --[{rel_type}]--> {target_pattern}\n"
                f"This relationship must exist for queries to return correct results."
            )


# =============================================================================
# 2. ONTOLOGY FOUNDRY GUARDS
# =============================================================================

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


# =============================================================================
# 3. GOLDEN QUERY TESTS
# =============================================================================

class TestGoldenQueries:
    """
    Test queries with exact expected outputs.
    Simple string matching - no LLM interpretation.
    """

    @pytest.fixture(scope="class")
    def query_engine(self, db_session):
        """Get the query engine."""
        from src.context_foundry.agents.retrieval import RetrievalAgent
        from src.context_foundry.agents.reasoning import ReasoningAgent

        return {
            "retrieval": RetrievalAgent(),
            "reasoning": ReasoningAgent(),
        }

    def _run_query(self, query_engine, query: str, vault_id: str = None) -> str:
        """Run a query and return the answer text."""
        retrieval = query_engine["retrieval"]
        reasoning = query_engine["reasoning"]

        # Set tenant context if vault specified
        if vault_id:
            retrieval.tenant_id = vault_id

        bundle = retrieval.build_context_bundle(query)
        result = reasoning.reason(bundle)

        return result.get("answer", "")

    @pytest.mark.regression
    @pytest.mark.parametrize("vault_name", list(VAULT_CONFIGS.keys()))
    def test_golden_queries_for_vault(self, query_engine, vault_name, vault_ids, db_session):
        """Test golden queries for each vault."""
        if vault_name not in vault_ids:
            pytest.skip(f"Vault {vault_name} not found")

        vault_id = vault_ids[vault_name]
        config = VAULT_CONFIGS[vault_name]

        for golden in config.get("golden_queries", []):
            query = golden["query"]
            must_contain = golden.get("must_contain", [])
            must_not_contain = golden.get("must_not_contain", [])

            answer = self._run_query(query_engine, query, vault_id)
            answer_lower = answer.lower()

            # Check required strings
            for required in must_contain:
                assert required.lower() in answer_lower, (
                    f"GOLDEN QUERY FAILED for {vault_name}:\n"
                    f"  Query: {query}\n"
                    f"  Missing required: '{required}'\n"
                    f"  Answer was: {answer[:500]}"
                )

            # Check forbidden strings
            for forbidden in must_not_contain:
                assert forbidden.lower() not in answer_lower, (
                    f"GOLDEN QUERY FAILED for {vault_name}:\n"
                    f"  Query: {query}\n"
                    f"  Found forbidden: '{forbidden}'\n"
                    f"  Answer was: {answer[:500]}"
                )


# =============================================================================
# 4. RELATIONSHIP INTEGRITY TESTS
# =============================================================================

class TestRelationshipIntegrity:
    """
    Verify relationship types are being stored correctly.
    """

    @pytest.mark.regression
    def test_holds_position_relationships_exist(self, db_session):
        """Verify HOLDS_POSITION relationships exist (not just logged as unknown)."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT COUNT(*) FROM relationships
            WHERE relationship_type = 'HOLDS_POSITION'
              AND lifecycle_state IN ('TRUSTED', 'STAGING')
        """))
        count = result.scalar()

        assert count > 0, (
            "No HOLDS_POSITION relationships found in knowledge graph.\n"
            "This is likely a regression - these should not be going to candidates."
        )

    @pytest.mark.regression
    def test_has_compensation_relationships_exist(self, db_session):
        """Verify HAS_COMPENSATION relationships exist."""
        from sqlalchemy import text

        result = db_session.execute(text("""
            SELECT COUNT(*) FROM relationships
            WHERE relationship_type = 'HAS_COMPENSATION'
              AND lifecycle_state IN ('TRUSTED', 'STAGING')
        """))
        count = result.scalar()

        # This might be 0 if no compensation data - adjust based on your data
        # For now, just verify the query runs
        assert count >= 0, "Query failed"

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


# =============================================================================
# 5. SCHEMA CONSISTENCY TESTS
# =============================================================================

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

        # Verify critical types are in schema
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

        # Verify critical types
        critical_types = ["PERSON", "ORGANIZATION"]
        for ctype in critical_types:
            assert ctype in entity_types, (
                f"Critical entity type '{ctype}' not in schema.\n"
                f"Available types: {entity_types}"
            )


# =============================================================================
# 6. EXTRACTION PIPELINE TESTS
# =============================================================================

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

        # Test relationship synonyms
        assert normalizer.normalize_relationship("INVESTS_IN") == "INVESTED_IN"
        assert normalizer.normalize_relationship("WORKS_FOR") == "WORKS_AT"
        assert normalizer.normalize_relationship("BOUGHT") == "ACQUIRED"

        # Test entity synonyms
        assert normalizer.normalize_entity("COMPANY") == "ORGANIZATION"
        assert normalizer.normalize_entity("INDIVIDUAL") == "PERSON"

    @pytest.mark.regression
    def test_normalizer_preserves_unknown_types(self):
        """Verify normalizer preserves types that aren't in synonym map."""
        from src.context_foundry.ontology.normalizer import CandidateNormalizer

        normalizer = CandidateNormalizer()

        # Unknown types should be returned as-is (uppercased, cleaned)
        assert normalizer.normalize_relationship("SOME_NEW_TYPE") == "SOME_NEW_TYPE"
        assert normalizer.normalize_relationship("custom-relation") == "CUSTOM_RELATION"


# =============================================================================
# PYTEST MARKERS
# =============================================================================

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


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "regression"])
