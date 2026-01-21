"""Unit tests for FuzzyEvaluator to lock intended behavior."""
import sys
sys.path.insert(0, '.')
from src.test_runner.evaluator import FuzzyEvaluator

def test_evaluator():
    evaluator = FuzzyEvaluator()
    
    # Test cases with expected results
    test_cases = [
        # Exact match
        ("MedSync Health", "The company is MedSync Health.", True, "exact_match"),
        
        # Number matching
        ("$40 million", "Revenue was $40M last year", True, "number_match"),
        ("$40 million", "Revenue was $50M last year", False, None),
        
        # Inference match (Can be inferred)
        ("Can be inferred but not explicitly stated", "Based on the data, we found 5 clients added.", True, "inference_match"),
        
        # Time component match (parenthetical stripped)
        ("2:15 PM to 3:30 PM EST (75 minutes)", "Outage from 2:15 PM to 3:30 PM EST.", True, "component_match"),
        
        # Entity component match with markdown
        ("Green (Healthy) with 110 customers", "**Green (Healthy)**, which has **110 customers**", True, "component_match"),
        
        # Simple time in actual
        ("3 hours 45 minutes", "The failover time was 3 hours 45 minutes.", True, "exact_match"),
        
        # Boolean matching
        ("Yes", "Yes, the company operates internationally", True, "component_match"),
        
        # NO_DATA detection
        ("[not in documents]", "I cannot find this information.", True, "uncertainty_match"),
        ("[not in documents]", "The CEO is John Smith.", False, None),
        
        # Prevent false positives - expected NOT in actual should fail
        ("Maria Rodriguez", "The CFO is Jane Doe, Maria Rodri", False, None),
        ("487 employees", "We have 500 employees", False, None),
        
        # Decimal/integer number equivalence
        ("$40.0 million", "Revenue was $40 million.", True, "component_match"),
    ]
    
    passed = 0
    failed = 0
    
    for expected, actual, should_pass, expected_match_type in test_cases:
        result, match_type = evaluator.evaluate(expected, actual)
        ok = result == should_pass
        if expected_match_type and result:
            ok = ok and match_type == expected_match_type
        
        if ok:
            passed += 1
            print(f"PASS: '{expected[:30]}...' -> {result} ({match_type})")
        else:
            failed += 1
            print(f"FAIL: '{expected[:30]}...'")
            print(f"  Expected: pass={should_pass}, type={expected_match_type}")
            print(f"  Got: pass={result}, type={match_type}")
    
    print(f"\n{passed}/{passed+failed} tests passed")
    return failed == 0

if __name__ == "__main__":
    success = test_evaluator()
    exit(0 if success else 1)
