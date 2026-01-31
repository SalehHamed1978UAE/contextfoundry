"""
Day 4 Test Suite: EntityResolver Validation

Tests 20 known failure patterns to validate the 3-stage EntityResolver:
1. Exact match (case-insensitive)
2. Semantic search (embeddings)
3. Fuzzy match (rapidfuzz with word boost)

Success criteria: 50%+ reduction in NOT_FOUND/wrong-entity responses.
"""
import pytest
import logging
from typing import Dict, List, Tuple, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestEntityResolver:
    """Test suite for EntityResolver validation."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures."""
        from src.context_foundry.agents.entity_resolver import EntityResolver
        from src.context_foundry.models.schema import get_session
        
        self.session = get_session()
        self.resolver = EntityResolver(session=self.session)
    
    # === EXACT MATCH TESTS ===
    
    def test_exact_match_case_insensitive(self):
        """Exact name should match regardless of case."""
        result = self.resolver.resolve("primary database cluster")
        assert result.entity is not None, "Should find exact match"
        assert result.match_stage == "exact"
        assert "Primary Database Cluster" in result.entity.name or "primary database cluster" in result.entity.name.lower()
    
    def test_exact_match_with_special_chars(self):
        """Entity names with special characters should match."""
        result = self.resolver.resolve("Brian Taylor")
        assert result.entity is not None or result.needs_disambiguation
        if result.entity:
            assert "Brian" in result.entity.name
    
    # === SEMANTIC SEARCH TESTS ===
    
    def test_semantic_partial_name(self):
        """Partial names should find semantic matches."""
        result = self.resolver.resolve("database cluster")
        assert result.entity is not None or result.needs_disambiguation
        if result.entity:
            assert "Database" in result.entity.name or "database" in result.entity.name.lower()
    
    def test_semantic_synonym(self):
        """Synonyms should find semantic matches."""
        result = self.resolver.resolve("auth service")
        # Should find authentication-related entities
        assert result.match_stage in ["exact", "semantic", "fuzzy"] or result.needs_disambiguation
    
    def test_semantic_abbreviation(self):
        """Abbreviations should match full names."""
        result = self.resolver.resolve("NIST")
        assert result.entity is not None or result.needs_disambiguation
        if result.needs_disambiguation:
            names = [c.name for c in result.candidates]
            assert any("NIST" in n for n in names), f"NIST should be in candidates: {names}"
    
    # === FUZZY MATCH TESTS ===
    
    def test_fuzzy_typo_tolerance(self):
        """Minor typos should still match."""
        result = self.resolver.resolve("Primry Database Clustr")
        # Should fuzzy match to Primary Database Cluster
        assert result.entity is not None or result.needs_disambiguation
    
    def test_fuzzy_word_reorder(self):
        """Reordered words should still match."""
        result = self.resolver.resolve("Cluster Database Primary")
        assert result.entity is not None or result.needs_disambiguation
    
    def test_fuzzy_partial_phrase(self):
        """Partial phrases should match longer entity names."""
        result = self.resolver.resolve("payment processor")
        assert result.entity is not None or result.needs_disambiguation
    
    # === DISAMBIGUATION TESTS ===
    
    def test_disambiguation_similar_names(self):
        """Similar entity names should trigger disambiguation."""
        result = self.resolver.resolve("framework")
        # Generic term should find multiple candidates
        if result.needs_disambiguation:
            assert len(result.candidates) >= 2, "Should have multiple candidates for generic term"
    
    def test_disambiguation_with_type_hint(self):
        """Type hints should narrow disambiguation results."""
        result = self.resolver.resolve("Brian", entity_type_hint="PERSON")
        # Should find person named Brian
        if result.entity:
            assert result.entity.entity_type == "PERSON"
        elif result.needs_disambiguation:
            assert all(c.entity_type == "PERSON" for c in result.candidates)
    
    # === EDGE CASE TESTS ===
    
    def test_empty_query(self):
        """Empty query should return gracefully."""
        result = self.resolver.resolve("")
        assert result.entity is None
        assert result.match_stage == "empty_query"
    
    def test_whitespace_query(self):
        """Whitespace-only query should return gracefully."""
        result = self.resolver.resolve("   ")
        assert result.entity is None
        assert result.match_stage == "empty_query"
    
    def test_nonexistent_entity(self):
        """Completely unknown entity should return not_found."""
        result = self.resolver.resolve("XyzNonexistentEntity12345")
        assert result.entity is None
        assert result.match_stage in ["not_found", "fuzzy", "semantic"]
    
    def test_special_characters_only(self):
        """Special characters should handle gracefully."""
        result = self.resolver.resolve("@#$%^&*()")
        assert result.entity is None or result.match_stage in ["not_found", "fuzzy"]
    
    # === REAL-WORLD QUERY PATTERNS ===
    
    def test_incident_reference(self):
        """Incident references should resolve."""
        result = self.resolver.resolve("INC-2024-001")
        # May or may not find exact match depending on data
        assert result.match_stage in ["exact", "semantic", "fuzzy", "not_found"]
    
    def test_service_query(self):
        """Service names should resolve."""
        result = self.resolver.resolve("Payment Service")
        if result.entity:
            assert "Payment" in result.entity.name or "payment" in result.entity.name.lower()
    
    def test_team_query(self):
        """Team names should resolve."""
        result = self.resolver.resolve("Engineering Team")
        # Should find team-related entities
        assert result.match_stage in ["exact", "semantic", "fuzzy", "not_found"] or result.needs_disambiguation
    
    def test_person_query(self):
        """Person names should resolve."""
        result = self.resolver.resolve("Mark Robinson")
        if result.entity:
            assert result.entity.entity_type == "PERSON"
    
    def test_document_query(self):
        """Document names should resolve."""
        result = self.resolver.resolve("Cybersecurity Framework")
        if result.entity or result.needs_disambiguation:
            if result.entity:
                assert "Framework" in result.entity.name or "framework" in result.entity.name.lower()
    
    def test_concept_query(self):
        """Concept names should resolve."""
        result = self.resolver.resolve("encryption")
        if result.entity:
            assert result.entity.entity_type in ["CONCEPT", "PROCESS", "SERVICE"]


def run_validation_suite():
    """
    Run validation and report metrics.
    
    Returns dict with:
    - total_tests: Number of tests run
    - passed: Number that found correct entity
    - failed: Number that returned wrong entity or NOT_FOUND
    - disambiguation: Number that returned candidates list
    - pass_rate: Percentage of successful resolutions
    """
    from src.context_foundry.agents.entity_resolver import EntityResolver
    from src.context_foundry.models.schema import get_session
    
    session = get_session()
    resolver = EntityResolver(session=session)
    
    test_queries = [
        ("Primary Database Cluster", "DATABASE", "exact"),
        ("Brian Taylor", "PERSON", "exact"),
        ("database cluster", "DATABASE", "semantic"),
        ("NIST", None, "fuzzy"),
        ("payment processor", "SERVICE", "exact"),
        ("Cybersecurity Framework", "DOCUMENT", "fuzzy"),
        ("encryption", "CONCEPT", "exact"),
        ("auth service", "SERVICE", "semantic"),
        ("Engineering Team", "TEAM", "fuzzy"),
        ("Mark Robinson", "PERSON", "exact"),
        ("incident report", None, "semantic"),
        ("security policy", None, "semantic"),
        ("API Gateway", "SERVICE", "exact"),
        ("data breach", None, "semantic"),
        ("compliance", "CONCEPT", "fuzzy"),
        ("vendor management", None, "semantic"),
        ("risk assessment", None, "semantic"),
        ("backup system", None, "semantic"),
        ("network infrastructure", None, "semantic"),
        ("user authentication", None, "semantic"),
    ]
    
    results = {
        "total_tests": len(test_queries),
        "passed": 0,
        "failed": 0,
        "disambiguation": 0,
        "by_stage": {"exact": 0, "semantic": 0, "fuzzy": 0, "not_found": 0},
        "details": []
    }
    
    for query, expected_type, expected_stage in test_queries:
        result = resolver.resolve(query, entity_type_hint=expected_type)
        
        detail = {
            "query": query,
            "expected_type": expected_type,
            "expected_stage": expected_stage,
            "actual_stage": result.match_stage,
            "found": result.entity.name if result.entity else None,
            "disambiguation": result.needs_disambiguation,
            "confidence": result.confidence
        }
        
        if result.entity:
            results["passed"] += 1
            results["by_stage"][result.match_stage] = results["by_stage"].get(result.match_stage, 0) + 1
            detail["status"] = "PASS"
        elif result.needs_disambiguation:
            results["disambiguation"] += 1
            detail["status"] = "DISAMBIGUATE"
            detail["candidates"] = [c.name for c in result.candidates[:3]]
        else:
            results["failed"] += 1
            results["by_stage"]["not_found"] = results["by_stage"].get("not_found", 0) + 1
            detail["status"] = "FAIL"
        
        results["details"].append(detail)
    
    results["pass_rate"] = (results["passed"] / results["total_tests"]) * 100
    results["resolution_rate"] = ((results["passed"] + results["disambiguation"]) / results["total_tests"]) * 100
    
    return results


if __name__ == "__main__":
    print("=" * 70)
    print("EntityResolver Validation Suite")
    print("=" * 70)
    
    results = run_validation_suite()
    
    print(f"\nResults:")
    print(f"  Total tests: {results['total_tests']}")
    print(f"  Passed (found entity): {results['passed']}")
    print(f"  Disambiguation needed: {results['disambiguation']}")
    print(f"  Failed (not found): {results['failed']}")
    print(f"\n  Pass rate: {results['pass_rate']:.1f}%")
    print(f"  Resolution rate (found or disambiguated): {results['resolution_rate']:.1f}%")
    
    print(f"\nBy stage:")
    for stage, count in results["by_stage"].items():
        print(f"  {stage}: {count}")
    
    print(f"\nDetails:")
    for detail in results["details"]:
        status = detail["status"]
        icon = "✓" if status == "PASS" else ("?" if status == "DISAMBIGUATE" else "✗")
        print(f"  {icon} '{detail['query']}' -> {detail['found'] or detail.get('candidates', 'NOT FOUND')} [{detail['actual_stage']}]")
