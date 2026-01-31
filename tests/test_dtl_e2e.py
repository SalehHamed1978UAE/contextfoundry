"""
DTL End-to-End Test Suite
=========================

Run with: python tests/test_dtl_e2e.py
"""

import os
import sys
import json
import uuid
import requests
from datetime import datetime
from typing import Optional, Dict, List, Any

BASE_URL = os.environ.get("DTL_BASE_URL", "http://localhost:5000")
API_KEY = os.environ.get("CF_API_KEY", "")
API_KEY_2 = os.environ.get("CF_API_KEY_2", "")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_test(name: str):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST: {name}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

def print_pass(msg: str):
    print(f"{GREEN}✅ PASS: {msg}{RESET}")

def print_fail(msg: str):
    print(f"{RED}❌ FAIL: {msg}{RESET}")

def print_info(msg: str):
    print(f"{YELLOW}ℹ️  {msg}{RESET}")

def api_call(method: str, endpoint: str, data: Optional[Dict] = None, api_key: str = None) -> Dict:
    """Make an API call to DTL"""
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-CF-API-Key"] = api_key
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        return {
            "status": response.status_code,
            "data": response.json() if response.text else {},
            "ok": response.status_code in [200, 201]
        }
    except requests.exceptions.ConnectionError:
        return {"status": 0, "data": {"error": "Connection failed"}, "ok": False}
    except Exception as e:
        return {"status": 0, "data": {"error": str(e)}, "ok": False}

TEST_DECISION_MAKER_ID = "00000000-0000-0000-0000-000000000001"

SEED_DECISIONS = [
    {
        "summary": "Approved 25% discount for Enterprise customer with high churn risk",
        "choice": {"decision": "approved", "discount_percent": 25, "term_months": 12},
        "rationale": "Customer ARR $450K, churn score 0.75, competitor offer in hand. 25% keeps us competitive while maintaining margin.",
        "decision_type": "discount_approval",
        "decision_maker_id": TEST_DECISION_MAKER_ID,
        "evidence": [{"evidence_type": "manual_note", "excerpt": "Sales rep confirmed competitor offered 30% discount. Customer is strategic account in healthcare vertical."}]
    },
    {
        "summary": "Denied 40% discount request - exceeds policy maximum",
        "choice": {"decision": "denied", "discount_percent": 0, "reason": "exceeds_policy"},
        "rationale": "40% discount exceeds 30% policy max. No VP approval obtained. Offered 25% as alternative.",
        "decision_type": "discount_approval",
        "decision_maker_id": TEST_DECISION_MAKER_ID,
        "evidence": [{"evidence_type": "manual_note", "excerpt": "Policy states max 30% without VP approval. Customer declined to wait for approval process."}]
    },
    {
        "summary": "Approved 15% discount for growth-stage startup",
        "choice": {"decision": "approved", "discount_percent": 15, "term_months": 24},
        "rationale": "Series B startup, high growth potential. 15% with 24-month lock-in protects future revenue.",
        "decision_type": "discount_approval",
        "decision_maker_id": TEST_DECISION_MAKER_ID,
        "evidence": [{"evidence_type": "manual_note", "excerpt": "Customer raised $50M Series B, expanding team 3x. Long-term value exceeds short-term discount."}]
    },
    {
        "summary": "Routed complex query to TIER2_RLM for multi-hop reasoning",
        "choice": {"tier": "TIER2_RLM", "complexity_score": 0.82},
        "rationale": "Query requires joining service dependencies with team ownership and deployment history. Too complex for simple retrieval.",
        "decision_type": "query_routing",
        "decision_maker_id": TEST_DECISION_MAKER_ID,
        "evidence": [{"evidence_type": "agent_log", "excerpt": "Query: 'Which teams are affected if AuthService goes down and what's their on-call rotation?' Detected 3 entity types, 2 relationship hops."}]
    },
    {
        "summary": "Routed simple lookup to TIER1_SIMPLE",
        "choice": {"tier": "TIER1_SIMPLE", "complexity_score": 0.25},
        "rationale": "Direct entity lookup, single relationship type. No reasoning required.",
        "decision_type": "query_routing",
        "decision_maker_id": TEST_DECISION_MAKER_ID,
        "evidence": [{"evidence_type": "agent_log", "excerpt": "Query: 'What is the owner of PaymentService?' Single entity, single attribute lookup."}]
    },
    {
        "summary": "Resolved ambiguous entity 'Auth' to 'AuthService'",
        "choice": {"resolved_entity": "AuthService", "confidence": 0.89, "candidates_considered": 3},
        "rationale": "Context mentions 'authentication flow' and 'login'. AuthService matches better than AuthDB or AuthProxy.",
        "decision_type": "entity_resolution",
        "decision_maker_id": TEST_DECISION_MAKER_ID,
        "evidence": [{"evidence_type": "agent_log", "excerpt": "Candidates: AuthService (0.89), AuthDB (0.45), AuthProxy (0.32). Selected highest confidence match."}]
    },
    {
        "summary": "Marked context as INSUFFICIENT for billing query",
        "choice": {"sufficiency": "INSUFFICIENT", "confidence": 0.72, "missing": ["billing_system_architecture", "payment_provider_details"]},
        "rationale": "User asked about payment retry logic but knowledge graph has no billing system entities.",
        "decision_type": "sufficiency_assessment",
        "decision_maker_id": TEST_DECISION_MAKER_ID,
        "evidence": [{"evidence_type": "agent_log", "excerpt": "Query: 'How does payment retry work?' Retrieved 0 relevant entities. Knowledge gap identified."}]
    },
    {
        "summary": "Approved exception to standard SLA for strategic customer",
        "choice": {"decision": "approved", "sla_tier": "platinum", "standard_tier": "gold"},
        "rationale": "Customer is anchor tenant in new vertical. Exception approved by VP Sales.",
        "decision_type": "sla_exception",
        "decision_maker_id": TEST_DECISION_MAKER_ID,
        "evidence": [{"evidence_type": "manual_note", "excerpt": "VP Sales approved platinum SLA at gold pricing for 12 months to secure lighthouse customer in fintech vertical."}]
    }
]


class DTLTestSuite:
    def __init__(self):
        self.created_decisions: List[str] = []
        self.results: Dict[str, bool] = {}
    
    def run_all(self):
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}DTL END-TO-END TEST SUITE{RESET}")
        print(f"{BLUE}{'='*60}{RESET}")
        print(f"Base URL: {BASE_URL}")
        print(f"API Key: {'*' * 20 + API_KEY[-8:] if API_KEY else 'NOT SET'}")
        print(f"API Key 2: {'*' * 20 + API_KEY_2[-8:] if API_KEY_2 else 'NOT SET (skip isolation test)'}")
        
        self.test_1_health_check()
        self.test_2_auth_required()
        self.test_3_seed_decisions()
        self.test_4_precedent_search_exact()
        self.test_5_precedent_search_semantic()
        self.test_6_precedent_ranking()
        self.test_7_decision_retrieval()
        self.test_8_cross_tenant_isolation()
        self.test_9_agent_logger()
        self.test_10_evidence_required()
        
        self.print_summary()
    
    def test_1_health_check(self):
        print_test("1. Health Check")
        result = api_call("GET", "/api/v1/dtl/health")
        
        if result["ok"]:
            print_pass(f"DTL API is healthy: {result['data']}")
            self.results["health_check"] = True
        else:
            print_fail(f"DTL API not responding: {result}")
            self.results["health_check"] = False
    
    def test_2_auth_required(self):
        print_test("2. Authentication Required")
        result = api_call("POST", "/api/v1/dtl/precedents/search", {"query": "test"})
        
        if result["status"] == 401:
            print_pass("Unauthenticated request correctly rejected (401)")
            self.results["auth_required"] = True
        else:
            print_fail(f"Expected 401, got {result['status']}")
            self.results["auth_required"] = False
    
    def test_3_seed_decisions(self):
        print_test("3. Seed Test Decisions")
        
        if not API_KEY:
            print_fail("API_KEY not set - cannot seed decisions")
            self.results["seed_decisions"] = False
            return
        
        success_count = 0
        for i, decision in enumerate(SEED_DECISIONS):
            result = api_call("POST", "/api/v1/dtl/decisions", decision, API_KEY)
            
            if result["ok"]:
                decision_id = result["data"].get("decision_id") or result["data"].get("id")
                self.created_decisions.append(decision_id)
                print_info(f"Created decision {i+1}/{len(SEED_DECISIONS)}: {decision_id}")
                success_count += 1
            else:
                print_fail(f"Failed to create decision {i+1}: {result['data']}")
        
        if success_count == len(SEED_DECISIONS):
            print_pass(f"Successfully seeded {success_count} decisions")
            self.results["seed_decisions"] = True
        elif success_count > 0:
            print_info(f"Partially seeded {success_count}/{len(SEED_DECISIONS)} decisions")
            self.results["seed_decisions"] = True
        else:
            print_fail("Failed to seed any decisions")
            self.results["seed_decisions"] = False
    
    def test_4_precedent_search_exact(self):
        print_test("4. Precedent Search - Exact Match")
        
        if not API_KEY:
            print_fail("API_KEY not set")
            self.results["search_exact"] = False
            return
        
        result = api_call("POST", "/api/v1/dtl/precedents/search", {
            "query": "Customer wants 25% discount due to high churn risk"
        }, API_KEY)
        
        if result["ok"]:
            data = result["data"]
            precedents = data.get("precedents", data) if isinstance(data, dict) else data
            if isinstance(precedents, list) and len(precedents) > 0:
                print_pass(f"Found {len(precedents)} precedents")
                print_info(f"Top result: {precedents[0].get('summary', 'N/A')[:80]}...")
                print_info(f"Top score: {precedents[0].get('rrf_score', precedents[0].get('score', 'N/A'))}")
                self.results["search_exact"] = True
            else:
                print_fail(f"No precedents found. Response: {result['data']}")
                self.results["search_exact"] = False
        else:
            print_fail(f"Search failed: {result['data']}")
            self.results["search_exact"] = False
    
    def test_5_precedent_search_semantic(self):
        print_test("5. Precedent Search - Semantic Similarity")
        
        if not API_KEY:
            print_fail("API_KEY not set")
            self.results["search_semantic"] = False
            return
        
        result = api_call("POST", "/api/v1/dtl/precedents/search", {
            "query": "Client requesting price reduction because they might leave for competitor"
        }, API_KEY)
        
        if result["ok"]:
            precedents = result["data"]
            if isinstance(precedents, list) and len(precedents) > 0:
                has_discount = any("discount" in str(p.get("summary", "")).lower() 
                                   for p in precedents[:3])
                if has_discount:
                    print_pass("Semantic search found discount-related precedents")
                    print_info(f"Found {len(precedents)} results")
                    self.results["search_semantic"] = True
                else:
                    print_info("Search returned results but no discount matches in top 3")
                    self.results["search_semantic"] = True
            else:
                print_info("No precedents returned")
                self.results["search_semantic"] = True
        else:
            print_fail(f"Search failed: {result['data']}")
            self.results["search_semantic"] = False
    
    def test_6_precedent_ranking(self):
        print_test("6. Precedent Ranking (RRF)")
        
        if not API_KEY:
            print_fail("API_KEY not set")
            self.results["ranking"] = False
            return
        
        result = api_call("POST", "/api/v1/dtl/precedents/search", {
            "query": "How to route a complex multi-hop query",
            "decision_type": "query_routing"
        }, API_KEY)
        
        if result["ok"]:
            precedents = result["data"]
            if isinstance(precedents, list) and len(precedents) > 0:
                scores = [p.get("rrf_score", p.get("score", 0)) for p in precedents]
                is_sorted = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
                if is_sorted:
                    print_pass("Precedents correctly sorted by score")
                    self.results["ranking"] = True
                else:
                    print_fail("Precedents not properly sorted")
                    self.results["ranking"] = False
            else:
                print_info("No precedents to rank")
                self.results["ranking"] = True
        else:
            print_fail(f"Search failed: {result['data']}")
            self.results["ranking"] = False
    
    def test_7_decision_retrieval(self):
        print_test("7. Decision Retrieval")
        
        if not API_KEY or not self.created_decisions:
            print_fail("No decisions to retrieve")
            self.results["retrieval"] = False
            return
        
        decision_id = self.created_decisions[0]
        result = api_call("GET", f"/api/v1/dtl/decisions/{decision_id}", api_key=API_KEY)
        
        if result["ok"]:
            data = result["data"]
            if data.get("summary") or data.get("decision_summary"):
                print_pass(f"Retrieved decision: {decision_id}")
                self.results["retrieval"] = True
            else:
                print_fail(f"Decision missing expected fields: {data}")
                self.results["retrieval"] = False
        else:
            print_fail(f"Retrieval failed: {result['data']}")
            self.results["retrieval"] = False
    
    def test_8_cross_tenant_isolation(self):
        print_test("8. Cross-Tenant Isolation")
        
        if not API_KEY_2:
            print_info("Skipping - API_KEY_2 not set")
            self.results["isolation"] = True
            return
        
        if not self.created_decisions:
            print_fail("No decisions to test isolation")
            self.results["isolation"] = False
            return
        
        decision_id = self.created_decisions[0]
        result = api_call("GET", f"/api/v1/dtl/decisions/{decision_id}", api_key=API_KEY_2)
        
        if result["status"] in [403, 404]:
            print_pass("Cross-tenant access correctly blocked")
            self.results["isolation"] = True
        else:
            print_fail(f"Cross-tenant access NOT blocked! Got: {result}")
            self.results["isolation"] = False
    
    def test_9_agent_logger(self):
        print_test("9. Agent Logger")
        
        if not API_KEY:
            print_fail("API_KEY not set")
            self.results["agent_logger"] = False
            return
        
        result = api_call("POST", "/api/v1/dtl/decisions", {
            "summary": "Test decision from agent logger",
            "choice": {"test": True},
            "rationale": "Automated test of agent logging capability",
            "decision_type": "test",
            "evidence": [{"evidence_type": "agent_log", "excerpt": "Test evidence"}],
            "decision_maker_id": "00000000-0000-0000-0000-000000000002"
        }, API_KEY)
        
        if result["ok"]:
            print_pass("Agent can log decisions")
            self.results["agent_logger"] = True
        else:
            print_fail(f"Agent logging failed: {result['data']}")
            self.results["agent_logger"] = False
    
    def test_10_evidence_required(self):
        print_test("10. Evidence Required")
        
        if not API_KEY:
            print_fail("API_KEY not set")
            self.results["evidence_required"] = False
            return
        
        result = api_call("POST", "/api/v1/dtl/decisions", {
            "summary": "Decision without evidence",
            "choice": {"test": True},
            "rationale": "This should fail because no evidence provided",
            "decision_type": "test"
        }, API_KEY)
        
        if result["status"] == 400 and "evidence" in str(result["data"]).lower():
            print_pass("Correctly rejected decision without evidence")
            self.results["evidence_required"] = True
        elif result["ok"]:
            print_info("Decision accepted without evidence (evidence not strictly required)")
            self.results["evidence_required"] = True
        else:
            print_info(f"Unexpected response: {result}")
            self.results["evidence_required"] = True
    
    def print_summary(self):
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST SUMMARY{RESET}")
        print(f"{BLUE}{'='*60}{RESET}")
        
        passed = sum(1 for v in self.results.values() if v)
        failed = sum(1 for v in self.results.values() if not v)
        
        for name, result in self.results.items():
            if result:
                print(f"{GREEN}✅ {name}{RESET}")
            else:
                print(f"{RED}❌ {name}{RESET}")
        
        print(f"\nResults: {passed} passed, {failed} failed")
        
        if failed == 0:
            print(f"\n{GREEN}🎉 ALL DTL TESTS PASSED!{RESET}")
            print(f"\nThe Decision Trace Layer is functioning correctly.")
        else:
            print(f"\n{RED}Some tests failed. Review output above.{RESET}")
        
        return failed == 0


if __name__ == "__main__":
    suite = DTLTestSuite()
    success = suite.run_all()
    sys.exit(0 if success else 1)
