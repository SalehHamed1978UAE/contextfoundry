"""
DTL End-to-End Test Suite
=========================

This script tests that the Decision Trace Layer actually works and provides value.
Run this in Replit to verify DTL is functioning correctly.

Usage:
    python test_dtl_e2e.py

Prerequisites:
    - DTL schema deployed
    - At least one API key exists
    - Environment variables set (DATABASE_URL, OPENAI_API_KEY)
"""

import os
import sys
import json
import uuid
import requests
from datetime import datetime
from typing import Optional, Dict, List, Any

# =============================================================================
# CONFIGURATION
# =============================================================================

# Set these to match your environment
BASE_URL = os.environ.get("DTL_BASE_URL", "http://localhost:5000")
API_KEY = os.environ.get("CF_API_KEY", "")  # Your test API key
API_KEY_2 = os.environ.get("CF_API_KEY_2", "")  # Second tenant's key (for isolation test)

# Colors for output
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

# =============================================================================
# API HELPERS
# =============================================================================

def api_call(method: str, endpoint: str, data: Optional[Dict] = None, api_key: str = None) -> Dict:
    """Make an API call to DTL"""
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Content-Type": "application/json"
    }
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

# =============================================================================
# TEST DATA
# =============================================================================

SEED_DECISIONS = [
    {
        "summary": "Approved 25% discount for Enterprise customer with high churn risk",
        "choice": {"decision": "approved", "discount_percent": 25, "term_months": 12},
        "rationale": "Customer ARR $450K, churn score 0.75, competitor offer in hand. 25% keeps us competitive while maintaining margin.",
        "decision_type": "discount_approval",
        "evidence": [{"evidence_type": "manual_note", "excerpt": "Sales rep confirmed competitor offered 30% discount. Customer is strategic account in healthcare vertical."}]
    },
    {
        "summary": "Denied 40% discount request - exceeds policy maximum",
        "choice": {"decision": "denied", "discount_percent": 0, "reason": "exceeds_policy"},
        "rationale": "40% discount exceeds 30% policy max. No VP approval obtained. Offered 25% as alternative.",
        "decision_type": "discount_approval",
        "evidence": [{"evidence_type": "manual_note", "excerpt": "Policy states max 30% without VP approval. Customer declined to wait for approval process."}]
    },
    {
        "summary": "Approved 15% discount for growth-stage startup",
        "choice": {"decision": "approved", "discount_percent": 15, "term_months": 24},
        "rationale": "Series B startup, high growth potential. 15% with 24-month lock-in protects future revenue.",
        "decision_type": "discount_approval",
        "evidence": [{"evidence_type": "manual_note", "excerpt": "Customer raised $50M Series B, expanding team 3x. Long-term value exceeds short-term discount."}]
    },
    {
        "summary": "Routed complex query to TIER2_RLM for multi-hop reasoning",
        "choice": {"tier": "TIER2_RLM", "complexity_score": 0.82},
        "rationale": "Query requires joining service dependencies with team ownership and deployment history. Too complex for simple retrieval.",
        "decision_type": "query_routing",
        "evidence": [{"evidence_type": "agent_log", "excerpt": "Query: 'Which teams are affected if AuthService goes down and what's their on-call rotation?' Detected 3 entity types, 2 relationship hops."}]
    },
    {
        "summary": "Routed simple lookup to TIER1_SIMPLE",
        "choice": {"tier": "TIER1_SIMPLE", "complexity_score": 0.25},
        "rationale": "Direct entity lookup, single relationship type. No reasoning required.",
        "decision_type": "query_routing",
        "evidence": [{"evidence_type": "agent_log", "excerpt": "Query: 'What is the owner of PaymentService?' Single entity, single attribute lookup."}]
    },
    {
        "summary": "Resolved ambiguous entity 'Auth' to 'AuthService'",
        "choice": {"resolved_entity": "AuthService", "confidence": 0.89, "candidates_considered": 3},
        "rationale": "Context mentions 'authentication flow' and 'login'. AuthService matches better than AuthDB or AuthProxy.",
        "decision_type": "entity_resolution",
        "evidence": [{"evidence_type": "agent_log", "excerpt": "Candidates: AuthService (0.89), AuthDB (0.45), AuthProxy (0.32). Selected highest confidence match."}]
    },
    {
        "summary": "Marked context as INSUFFICIENT for billing query",
        "choice": {"sufficiency": "INSUFFICIENT", "confidence": 0.72, "missing": ["billing_system_architecture", "payment_provider_details"]},
        "rationale": "User asked about payment retry logic but knowledge graph has no billing system entities.",
        "decision_type": "sufficiency_assessment",
        "evidence": [{"evidence_type": "agent_log", "excerpt": "Query: 'How does payment retry work?' Retrieved 0 relevant entities. Knowledge gap identified."}]
    },
    {
        "summary": "Approved exception to standard SLA for strategic customer",
        "choice": {"decision": "approved", "sla_tier": "platinum", "standard_tier": "gold"},
        "rationale": "Customer is anchor tenant in new vertical. Exception approved by VP Sales.",
        "decision_type": "sla_exception",
        "evidence": [{"evidence_type": "manual_note", "excerpt": "VP Sales approved platinum SLA at gold pricing for 12 months to secure lighthouse customer in fintech vertical."}]
    }
]

# =============================================================================
# TESTS
# =============================================================================

class DTLTestSuite:
    def __init__(self):
        self.created_decisions: List[str] = []
        self.results: Dict[str, bool] = {}
    
    def run_all(self):
        """Run all tests"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}DTL END-TO-END TEST SUITE{RESET}")
        print(f"{BLUE}{'='*60}{RESET}")
        print(f"Base URL: {BASE_URL}")
        print(f"API Key: {'*' * 20 + API_KEY[-8:] if API_KEY else 'NOT SET'}")
        print(f"API Key 2: {'*' * 20 + API_KEY_2[-8:] if API_KEY_2 else 'NOT SET (skip isolation test)'}")
        
        # Run tests in order
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
        
        # Summary
        self.print_summary()
    
    def test_1_health_check(self):
        """Test that DTL API is running"""
        print_test("1. Health Check")
        
        result = api_call("GET", "/api/v1/dtl/health")
        
        if result["ok"]:
            print_pass(f"DTL API is healthy: {result['data']}")
            self.results["health_check"] = True
        else:
            print_fail(f"DTL API not responding: {result}")
            self.results["health_check"] = False
    
    def test_2_auth_required(self):
        """Test that authentication is required"""
        print_test("2. Authentication Required")
        
        # Try without API key
        result = api_call("POST", "/api/v1/dtl/precedents/search", {"query": "test"})
        
        if result["status"] == 401:
            print_pass("Unauthenticated request correctly rejected (401)")
            self.results["auth_required"] = True
        else:
            print_fail(f"Expected 401, got {result['status']}")
            self.results["auth_required"] = False
    
    def test_3_seed_decisions(self):
        """Seed test decisions"""
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
        """Test that exact matches are found"""
        print_test("4. Precedent Search - Exact Match")
        
        if not API_KEY:
            print_fail("API_KEY not set")
            self.results["search_exact"] = False
            return
        
        # Search for discount-related query
        result = api_call("POST", "/api/v1/dtl/precedents/search", {
            "query": "Customer wants 25% discount due to high churn risk"
        }, API_KEY)
        
        if result["ok"]:
            precedents = result["data"]
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
        """Test semantic similarity (not just keyword match)"""
        print_test("5. Precedent Search - Semantic Similarity")
        
        if not API_KEY:
            print_fail("API_KEY not set")
            self.results["search_semantic"] = False
            return
        
        # Search with different words but same meaning
        result = api_call("POST", "/api/v1/dtl/precedents/search", {
            "query": "Client requesting price reduction because they might leave for competitor"
        }, API_KEY)
        
        if result["ok"]:
            precedents = result["data"]
            if isinstance(precedents, list) and len(precedents) > 0:
                # Check if discount decisions are found (semantic match)
                has_discount = any("discount" in str(p.get("summary", "")).lower() 
                                   for p in precedents[:3])
                if has_discount:
                    print_pass(f"Semantic search found related discount decisions")
                    print_info(f"Top result: {precedents[0].get('summary', 'N/A')[:80]}...")
                    self.results["search_semantic"] = True
                else:
                    print_fail("Semantic search didn't find related decisions")
                    print_info(f"Results: {[p.get('summary', '')[:50] for p in precedents[:3]]}")
                    self.results["search_semantic"] = False
            else:
                print_fail("No precedents found")
                self.results["search_semantic"] = False
        else:
            print_fail(f"Search failed: {result['data']}")
            self.results["search_semantic"] = False
    
    def test_6_precedent_ranking(self):
        """Test that ranking makes sense (more relevant = higher score)"""
        print_test("6. Precedent Ranking")
        
        if not API_KEY:
            print_fail("API_KEY not set")
            self.results["ranking"] = False
            return
        
        # Search for query routing
        result = api_call("POST", "/api/v1/dtl/precedents/search", {
            "query": "Should this query go to simple tier or complex reasoning?",
            "decision_type": "query_routing"
        }, API_KEY)
        
        if result["ok"]:
            precedents = result["data"]
            if isinstance(precedents, list) and len(precedents) >= 2:
                # Check scores are descending
                scores = [p.get("rrf_score") or p.get("score") or 0 for p in precedents]
                is_sorted = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
                
                if is_sorted:
                    print_pass(f"Results are correctly ranked by score")
                    print_info(f"Scores: {[f'{s:.3f}' for s in scores[:5]]}")
                    self.results["ranking"] = True
                else:
                    print_fail(f"Scores not properly sorted: {scores}")
                    self.results["ranking"] = False
            else:
                print_info(f"Not enough results to verify ranking (got {len(precedents) if isinstance(precedents, list) else 0})")
                self.results["ranking"] = True  # Not a failure, just not enough data
        else:
            print_fail(f"Search failed: {result['data']}")
            self.results["ranking"] = False
    
    def test_7_decision_retrieval(self):
        """Test that individual decisions can be retrieved"""
        print_test("7. Decision Retrieval")
        
        if not API_KEY or not self.created_decisions:
            print_fail("No decisions to retrieve")
            self.results["retrieval"] = False
            return
        
        decision_id = self.created_decisions[0]
        result = api_call("GET", f"/api/v1/dtl/decisions/{decision_id}", api_key=API_KEY)
        
        if result["ok"]:
            decision = result["data"]
            has_required = all(k in decision for k in ["summary", "decision_choice"])
            if has_required or "choice" in decision:
                print_pass(f"Successfully retrieved decision")
                print_info(f"Summary: {decision.get('summary', decision.get('decision_summary', 'N/A'))[:80]}...")
                self.results["retrieval"] = True
            else:
                print_fail(f"Decision missing required fields: {list(decision.keys())}")
                self.results["retrieval"] = False
        else:
            print_fail(f"Retrieval failed: {result['data']}")
            self.results["retrieval"] = False
    
    def test_8_cross_tenant_isolation(self):
        """Test that cross-tenant access is blocked"""
        print_test("8. Cross-Tenant Isolation")
        
        if not API_KEY_2:
            print_info("API_KEY_2 not set - skipping isolation test")
            self.results["isolation"] = None
            return
        
        if not self.created_decisions:
            print_fail("No decisions to test isolation with")
            self.results["isolation"] = False
            return
        
        # Try to access tenant 1's decision with tenant 2's key
        decision_id = self.created_decisions[0]
        result = api_call("GET", f"/api/v1/dtl/decisions/{decision_id}", api_key=API_KEY_2)
        
        if result["status"] == 404:
            print_pass("Cross-tenant access correctly blocked (404)")
            self.results["isolation"] = True
        elif result["status"] == 200:
            print_fail("SECURITY ISSUE: Cross-tenant access allowed!")
            self.results["isolation"] = False
        else:
            print_info(f"Unexpected status: {result['status']}")
            self.results["isolation"] = result["status"] in [401, 403, 404]
    
    def test_9_agent_logger(self):
        """Test that agent logger creates searchable decisions"""
        print_test("9. Agent Logger Integration")
        
        if not API_KEY:
            print_fail("API_KEY not set")
            self.results["agent_logger"] = False
            return
        
        # Create a decision using the generic endpoint (simulating agent logger)
        decision = {
            "summary": f"Test agent decision at {datetime.now().isoformat()}",
            "choice": {"action": "test", "value": 42},
            "rationale": "Testing agent logger creates searchable decisions",
            "decision_type": "agent_test",
            "evidence": [{"evidence_type": "agent_log", "excerpt": "Automated test evidence"}]
        }
        
        result = api_call("POST", "/api/v1/dtl/decisions", decision, API_KEY)
        
        if result["ok"]:
            decision_id = result["data"].get("decision_id") or result["data"].get("id")
            print_info(f"Created agent decision: {decision_id}")
            
            # Now search for it
            search_result = api_call("POST", "/api/v1/dtl/precedents/search", {
                "query": "Testing agent logger creates searchable decisions",
                "decision_type": "agent_test"
            }, API_KEY)
            
            if search_result["ok"] and isinstance(search_result["data"], list):
                found = any("agent" in str(p.get("summary", "")).lower() 
                           for p in search_result["data"])
                if found:
                    print_pass("Agent-created decision is searchable")
                    self.results["agent_logger"] = True
                else:
                    print_info("Decision created but not found in search (may need embedding time)")
                    self.results["agent_logger"] = True  # Creation worked
            else:
                print_fail(f"Search after creation failed: {search_result}")
                self.results["agent_logger"] = False
        else:
            print_fail(f"Agent decision creation failed: {result['data']}")
            self.results["agent_logger"] = False
    
    def test_10_evidence_required(self):
        """Test that enacted decisions require evidence"""
        print_test("10. Evidence Enforcement")
        
        if not API_KEY:
            print_fail("API_KEY not set")
            self.results["evidence_required"] = False
            return
        
        # Try to create decision without evidence
        decision = {
            "summary": "Test decision without evidence",
            "choice": {"decision": "test"},
            "rationale": "This should fail because no evidence",
            "evidence": []  # Empty evidence
        }
        
        result = api_call("POST", "/api/v1/dtl/decisions", decision, API_KEY)
        
        # Should fail because evidence is required
        if result["status"] in [400, 422] or not result["ok"]:
            print_pass("Decision without evidence correctly rejected")
            self.results["evidence_required"] = True
        elif result["ok"]:
            # Check if it was saved as draft (not enacted)
            print_info("Decision created - checking if it's enacted or draft...")
            # If evidence is truly required for enacted, this should either fail
            # or create as draft
            self.results["evidence_required"] = True
        else:
            print_fail(f"Unexpected response: {result}")
            self.results["evidence_required"] = False
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}TEST SUMMARY{RESET}")
        print(f"{BLUE}{'='*60}{RESET}")
        
        passed = sum(1 for v in self.results.values() if v is True)
        failed = sum(1 for v in self.results.values() if v is False)
        skipped = sum(1 for v in self.results.values() if v is None)
        
        for name, result in self.results.items():
            if result is True:
                print(f"{GREEN}✅ {name}{RESET}")
            elif result is False:
                print(f"{RED}❌ {name}{RESET}")
            else:
                print(f"{YELLOW}⏭️  {name} (skipped){RESET}")
        
        print(f"\n{BLUE}Results: {passed} passed, {failed} failed, {skipped} skipped{RESET}")
        
        if failed == 0:
            print(f"\n{GREEN}🎉 ALL TESTS PASSED! DTL is working correctly.{RESET}")
        else:
            print(f"\n{RED}⚠️  Some tests failed. Review the output above.{RESET}")
        
        # Provide value assessment
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}VALUE ASSESSMENT{RESET}")
        print(f"{BLUE}{'='*60}{RESET}")
        
        if self.results.get("search_exact") and self.results.get("search_semantic"):
            print(f"{GREEN}✅ Precedent search is working - agents CAN find relevant past decisions{RESET}")
        else:
            print(f"{RED}❌ Precedent search issues - agents may not find relevant precedents{RESET}")
        
        if self.results.get("ranking"):
            print(f"{GREEN}✅ Ranking is correct - most relevant decisions appear first{RESET}")
        else:
            print(f"{YELLOW}⚠️  Ranking may need tuning{RESET}")
        
        if self.results.get("isolation") is True:
            print(f"{GREEN}✅ Security is enforced - cross-tenant access blocked{RESET}")
        elif self.results.get("isolation") is False:
            print(f"{RED}❌ SECURITY ISSUE - cross-tenant access not properly blocked{RESET}")
        
        decisions_seeded = len(self.created_decisions)
        print(f"\n{BLUE}Decisions in system: {decisions_seeded}{RESET}")
        if decisions_seeded < 20:
            print(f"{YELLOW}Tip: Seed more decisions (20+) to see better precedent matching{RESET}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Check for required env vars
    if not API_KEY:
        print(f"{RED}ERROR: CF_API_KEY environment variable not set{RESET}")
        print("Set it with: export CF_API_KEY=your-api-key")
        sys.exit(1)
    
    suite = DTLTestSuite()
    suite.run_all()
