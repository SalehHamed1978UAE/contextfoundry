"""
Regression test suite for Context Foundry query system.

Tests key queries to ensure hybrid retrieval and confidence calibration work correctly.
Run with: python tests/regression_queries.py
"""
import sys
sys.path.insert(0, '/home/runner/workspace')
import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.WARNING)

from sqlalchemy import text
from src.context_foundry.models.schema import get_session, set_tenant_context
from src.context_foundry.agents.retrieval import RetrievalAgent
from src.context_foundry.agents.reasoning import ReasoningAgent


@dataclass
class TestResult:
    query: str
    confidence: float
    expected_confidence: float
    entity_found: bool
    entity_name: Optional[str]
    quadrant: str
    sufficiency: str
    passed: bool
    failure_reason: Optional[str] = None


TEST_QUERIES = [
    {
        "query": "What is Context Foundry?",
        "expected_confidence": 0.80,
        "expected_entities": ["Context Foundry"],
        "expected_source": "Context_Foundry_A_Cognitive_Operating_System.pdf"
    },
    {
        "query": "What are the three types of memory in Context Foundry?",
        "expected_confidence": 0.50,
        "expected_entities": ["Semantic Memory", "Episodic Memory", "Symbolic Memory"]
    },
    {
        "query": "What is the Tri-Memory System?",
        "expected_confidence": 0.50,
        "expected_entities": ["Tri-Memory System"]
    },
]


def run_regression_tests(tenant_id: str) -> List[TestResult]:
    """Run all regression tests and return results."""
    session = get_session()
    set_tenant_context(session, tenant_id)
    
    retriever = RetrievalAgent(session, tenant_id)
    reasoner = ReasoningAgent()
    
    results = []
    
    for test in TEST_QUERIES:
        query = test["query"]
        expected_confidence = test.get("expected_confidence", 0.5)
        
        try:
            bundle = retriever.build_context_bundle(query)
            
            entity_density, _ = reasoner.calculate_entity_density(bundle.episodic_documents)
            context_str = bundle.to_llm_context()[:4000]
            sufficiency, details = reasoner.check_sufficiency(query, context_str)
            confidence, quadrant = reasoner.calculate_quadrant_confidence(bundle, sufficiency, entity_density)
            
            passed = confidence >= expected_confidence
            failure_reason = None
            if not passed:
                failure_reason = f"Confidence {confidence:.2f} < expected {expected_confidence:.2f}"
            
            results.append(TestResult(
                query=query,
                confidence=confidence,
                expected_confidence=expected_confidence,
                entity_found=bundle.target_entity_found,
                entity_name=bundle.target_entity_name,
                quadrant=quadrant,
                sufficiency=sufficiency,
                passed=passed,
                failure_reason=failure_reason
            ))
        except Exception as e:
            results.append(TestResult(
                query=query,
                confidence=0.0,
                expected_confidence=expected_confidence,
                entity_found=False,
                entity_name=None,
                quadrant="ERROR",
                sufficiency="ERROR",
                passed=False,
                failure_reason=str(e)
            ))
    
    session.close()
    return results


def print_results(results: List[TestResult]):
    """Print test results in a readable format."""
    print("\n" + "=" * 70)
    print("REGRESSION TEST RESULTS")
    print("=" * 70)
    
    passed_count = sum(1 for r in results if r.passed)
    total = len(results)
    
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"\n[{status}] {r.query}")
        print(f"  Confidence: {r.confidence*100:.0f}% (expected >= {r.expected_confidence*100:.0f}%)")
        print(f"  Entity: {r.entity_name or 'None'} (found: {r.entity_found})")
        print(f"  Quadrant: {r.quadrant}, Sufficiency: {r.sufficiency}")
        if r.failure_reason:
            print(f"  Reason: {r.failure_reason}")
    
    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed_count}/{total} tests passed")
    print("=" * 70)
    
    return passed_count == total


def check_entity_duplicates(tenant_id: str):
    """Check for duplicate entities by name."""
    from sqlalchemy import create_engine
    
    DATABASE_URL = os.environ.get("DATABASE_URL")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        duplicates = conn.execute(text("""
            SELECT name, COUNT(*) as cnt
            FROM entities 
            WHERE tenant_id = :tid AND lifecycle_state IN ('STAGING', 'TRUSTED')
            GROUP BY name 
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            LIMIT 10
        """), {"tid": tenant_id}).fetchall()
        
        if duplicates:
            print("\nWARNING: Duplicate entities found:")
            for name, cnt in duplicates:
                print(f"  {name}: {cnt} instances")
            return False
        else:
            print("\nNo duplicate entities found.")
            return True


if __name__ == "__main__":
    TENANT_ID = "7627d577-e07c-484f-893a-ed2f464d28b9"
    
    print("Running regression tests...")
    results = run_regression_tests(TENANT_ID)
    all_passed = print_results(results)
    
    print("\nChecking for duplicate entities...")
    no_duplicates = check_entity_duplicates(TENANT_ID)
    
    if all_passed and no_duplicates:
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed or duplicates found.")
        sys.exit(1)
