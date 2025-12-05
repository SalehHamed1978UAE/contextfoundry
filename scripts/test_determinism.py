"""
Test script to verify deterministic query responses.
Runs the same query 5 times and checks for consistent results.
Now uses structured blast_radius_entities field for determinism.
"""
import requests
import json
import time
import sys

API_URL = "http://localhost:5000/api/query"

# Test queries using ACTUAL entity names from the database
TEST_QUERIES = [
    "What services are affected if Auth Service goes down?",
    "What is the blast radius if Primary Database Cluster fails?",
]

def run_query(query):
    """Run a single query and return the response."""
    try:
        resp = requests.post(API_URL, json={"query": query}, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            
            return {
                "response": data.get("answer", ""),
                "confidence": data.get("confidence", 0),
                "evidence_count": len(data.get("evidence_chain", [])),
                # Use structured blast_radius_entities for determinism check
                "blast_radius_entities": data.get("blast_radius_entities", []),
                "blast_radius_complete": data.get("blast_radius_complete", True),
            }
        else:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def test_determinism():
    """Test that queries return consistent results."""
    print("=" * 60)
    print("DETERMINISM VERIFICATION TEST (using blast_radius_entities)")
    print("=" * 60)
    
    all_passed = True
    
    for query in TEST_QUERIES:
        print(f"\nQuery: {query}")
        print("-" * 60)
        
        results = []
        for i in range(5):
            print(f"  Run {i+1}...", end=" ", flush=True)
            result = run_query(query)
            results.append(result)
            
            if "error" in result:
                print(f"ERROR: {result['error'][:80]}")
            else:
                br_count = len(result["blast_radius_entities"])
                print(f"blast_radius={br_count}, confidence={result['confidence']:.2f}, evidence={result['evidence_count']}")
            
            time.sleep(1)  # Brief pause between requests
        
        # Check consistency
        valid_results = [r for r in results if "error" not in r]
        
        if len(valid_results) < 5:
            print(f"  FAIL: Only {len(valid_results)}/5 queries succeeded")
            all_passed = False
            continue
        
        # PRIMARY CHECK: Compare blast_radius_entities (DETERMINISTIC)
        blast_radius_sets = [tuple(r["blast_radius_entities"]) for r in valid_results]
        if len(set(blast_radius_sets)) > 1:
            print(f"  FAIL: Blast radius entities vary across runs")
            for i, names in enumerate(blast_radius_sets):
                print(f"    Run {i+1}: {list(names)}")
            all_passed = False
        else:
            if valid_results[0]['blast_radius_entities']:
                print(f"  PASS: Blast radius entities DETERMINISTIC")
                print(f"    Affected entities: {valid_results[0]['blast_radius_entities']}")
            else:
                print(f"  NOTE: No blast_radius_entities returned (non-impact query)")
        
        # SECONDARY CHECK: Compare confidence scores
        confidences = [r["confidence"] for r in valid_results]
        if len(set(confidences)) > 1:
            print(f"  WARN: Confidence varies: {confidences}")
        else:
            print(f"  PASS: Confidence consistent ({confidences[0]:.2f})")
        
        # INFORMATIONAL: Check evidence counts
        evidence_counts = [r["evidence_count"] for r in valid_results]
        if len(set(evidence_counts)) > 1:
            print(f"  INFO: Evidence counts vary: {evidence_counts}")
        else:
            print(f"  INFO: Evidence count consistent ({evidence_counts[0]})")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("OVERALL: ALL TESTS PASSED - Impact queries are DETERMINISTIC")
        print("The blast_radius_entities field provides reliable, repeatable results.")
    else:
        print("OVERALL: SOME TESTS FAILED - Check logs above")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(test_determinism())
