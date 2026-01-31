#!/usr/bin/env python3
"""
DTL Validation Pack - Phase 3: Retrieval Query Testing

Runs 20 retrieval queries against the precedent search function
and scores usefulness based on relevance of returned results.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.decision_trace_layer.precedent_search import PrecedentSearchClient
from src.context_foundry.models.schema import get_session

TENANT_A_ID = "8eee325b-ba3b-447e-9ee7-6d66085ead5f"

RETRIEVAL_QUERIES = [
    {
        "id": "Q01",
        "query": "How did we handle previous authentication service outages?",
        "expected_domain": "ops_incident_response",
        "expected_keywords": ["auth", "outage", "bypass", "load balancer"],
    },
    {
        "id": "Q02",
        "query": "What's our policy for enterprise discount approvals?",
        "expected_domain": "commercial_approval",
        "expected_keywords": ["discount", "enterprise", "approval"],
    },
    {
        "id": "Q03",
        "query": "When have we rolled back deployments in the past?",
        "expected_domain": "ops_incident_response",
        "expected_keywords": ["rollback", "deployment", "500 error"],
    },
    {
        "id": "Q04",
        "query": "How do we handle SLA penalty waiver requests?",
        "expected_domain": "commercial_approval",
        "expected_keywords": ["SLA", "penalty", "waiver"],
    },
    {
        "id": "Q05",
        "query": "What happened when we had cache poisoning issues?",
        "expected_domain": "ops_incident_response",
        "expected_keywords": ["cache", "CDN", "bypass"],
    },
    {
        "id": "Q06",
        "query": "Have we ever granted extended payment terms?",
        "expected_domain": "commercial_approval",
        "expected_keywords": ["payment", "terms", "90-day"],
    },
    {
        "id": "Q07",
        "query": "How do we handle security vulnerability deployments?",
        "expected_domain": "ops_incident_response",
        "expected_keywords": ["security", "vulnerability", "scan", "reject"],
    },
    {
        "id": "Q08",
        "query": "What's the precedent for startup pricing requests?",
        "expected_domain": "commercial_approval",
        "expected_keywords": ["startup", "YC", "pricing"],
    },
    {
        "id": "Q09",
        "query": "When have we switched to degraded mode?",
        "expected_domain": "ops_incident_response",
        "expected_keywords": ["degraded", "mode", "elasticsearch", "cache"],
    },
    {
        "id": "Q10",
        "query": "How do we handle refund requests for used services?",
        "expected_domain": "commercial_approval",
        "expected_keywords": ["refund", "denied", "usage"],
    },
    {
        "id": "Q11",
        "query": "Precedent for kernel security patching during business hours",
        "expected_domain": "ops_incident_response",
        "expected_keywords": ["kernel", "security", "drain", "node"],
    },
    {
        "id": "Q12",
        "query": "Education institution discount approvals",
        "expected_domain": "commercial_approval",
        "expected_keywords": ["education", "university", "discount"],
    },
    {
        "id": "Q13",
        "query": "When have we enabled debug logging for troubleshooting?",
        "expected_domain": "ops_incident_response",
        "expected_keywords": ["debug", "logging", "intermittent"],
    },
    {
        "id": "Q14",
        "query": "Volume discount precedent for reseller partners",
        "expected_domain": "commercial_approval",
        "expected_keywords": ["volume", "reseller", "partner"],
    },
    {
        "id": "Q15",
        "query": "Feature flag toggles during incidents",
        "expected_domain": "ops_incident_response",
        "expected_keywords": ["feature", "flag", "checkout"],
    },
    {
        "id": "Q16",
        "query": "Contract restructuring for downsizing customers",
        "expected_domain": "commercial_approval",
        "expected_keywords": ["restructure", "downsizing"],
    },
    {
        "id": "Q17",
        "query": "SOC2 audit exceptions granted",
        "expected_domain": "ops_incident_response",
        "expected_keywords": ["SOC2", "audit", "exception", "risk"],
    },
    {
        "id": "Q18",
        "query": "Early termination requests handling",
        "expected_domain": "commercial_approval",
        "expected_keywords": ["early", "termination", "penalty"],
    },
    {
        "id": "Q19",
        "query": "API timeout adjustments history",
        "expected_domain": "ops_incident_response",
        "expected_keywords": ["timeout", "API", "increase"],
    },
    {
        "id": "Q20",
        "query": "Payment deferral approvals during customer hardship",
        "expected_domain": "commercial_approval",
        "expected_keywords": ["payment", "deferral", "cash flow"],
    },
]


def score_result(result, expected_keywords, expected_domain):
    """Score a single result based on keyword matches and domain relevance."""
    score = 0.0
    summary = (result.summary or "").lower()
    rationale = (result.rationale_summary or "").lower()
    decision_type = result.decision_type or ""
    combined_text = f"{summary} {rationale}"
    
    keyword_matches = sum(1 for kw in expected_keywords if kw.lower() in combined_text)
    keyword_score = keyword_matches / len(expected_keywords) if expected_keywords else 0
    score += keyword_score * 0.6
    
    if decision_type == expected_domain:
        score += 0.4
    
    return score


def run_retrieval_tests():
    """Run all 20 retrieval queries and score results."""
    print("=" * 70)
    print("DTL VALIDATION PACK - PHASE 3: RETRIEVAL QUERY TESTING")
    print("=" * 70)
    
    session = get_session(use_rls_role=True)
    client = PrecedentSearchClient(session, TENANT_A_ID)
    
    results_summary = []
    total_score = 0.0
    queries_with_results = 0
    
    for q in RETRIEVAL_QUERIES:
        print(f"\n--- {q['id']}: {q['query'][:50]}...")
        
        try:
            results = client.search(
                query=q["query"],
                limit=5
            )
            
            if results:
                queries_with_results += 1
                best_score = 0.0
                
                for i, r in enumerate(results[:3]):
                    result_score = score_result(r, q["expected_keywords"], q["expected_domain"])
                    best_score = max(best_score, result_score)
                    outcome_status = r.outcome_status or "unknown"
                    print(f"  [{i+1}] {r.decision_human_id[:16]}... "
                          f"score={result_score:.2f} outcome={outcome_status}")
                
                total_score += best_score
                results_summary.append({
                    "query_id": q["id"],
                    "results_count": len(results),
                    "best_score": best_score,
                    "status": "PASS" if best_score >= 0.5 else "MARGINAL" if best_score >= 0.3 else "FAIL"
                })
            else:
                print("  [!] No results returned")
                results_summary.append({
                    "query_id": q["id"],
                    "results_count": 0,
                    "best_score": 0.0,
                    "status": "FAIL"
                })
                
        except Exception as e:
            print(f"  [!] Error: {e}")
            results_summary.append({
                "query_id": q["id"],
                "results_count": 0,
                "best_score": 0.0,
                "status": "ERROR"
            })
    
    session.close()
    
    print("\n" + "=" * 70)
    print("PHASE 3 RESULTS SUMMARY")
    print("=" * 70)
    
    pass_count = sum(1 for r in results_summary if r["status"] == "PASS")
    marginal_count = sum(1 for r in results_summary if r["status"] == "MARGINAL")
    fail_count = sum(1 for r in results_summary if r["status"] in ("FAIL", "ERROR"))
    
    print(f"\nQueries with results: {queries_with_results}/20")
    print(f"Average best score: {total_score / len(RETRIEVAL_QUERIES):.2%}")
    print(f"\nGrade distribution:")
    print(f"  PASS (>=0.5):     {pass_count}/20")
    print(f"  MARGINAL (0.3-0.5): {marginal_count}/20")
    print(f"  FAIL (<0.3):      {fail_count}/20")
    
    usefulness_score = (pass_count + (marginal_count * 0.5)) / len(RETRIEVAL_QUERIES)
    print(f"\nOverall Usefulness Score: {usefulness_score:.1%}")
    
    if usefulness_score >= 0.7:
        print("\n[PASS] DTL precedent search is demonstrably useful!")
    elif usefulness_score >= 0.5:
        print("\n[MARGINAL] DTL shows promise but needs tuning.")
    else:
        print("\n[NEEDS WORK] DTL retrieval quality needs improvement.")
    
    return results_summary


if __name__ == "__main__":
    run_retrieval_tests()
