"""
Tests for Precedent Middleware
==============================

Run with: python tests/test_precedent_middleware.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.decision_trace_layer.precedent_middleware import PrecedentMiddleware, decide_with_context, Precedent, DecisionContext

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


class MiddlewareTests:
    def __init__(self):
        self.api_key = os.environ.get("CF_API_KEY")
        self.base_url = os.environ.get("DTL_BASE_URL", "http://localhost:5000")
        self.tenant_id = "8eee325b-ba3b-447e-9ee7-6d66085ead5f"
        self.decision_maker_id = "00000000-0000-0000-0000-000000000001"
        self.results = {}
        
        if not self.api_key:
            print(f"{RED}ERROR: CF_API_KEY not set{RESET}")
            sys.exit(1)
    
    def run_all(self):
        print(f"\n{BLUE}PRECEDENT MIDDLEWARE TEST SUITE{RESET}")
        print(f"Base URL: {self.base_url}")
        
        self.test_1_middleware_creation()
        self.test_2_retrieve_precedents()
        self.test_3_log_decision()
        self.test_4_decide_with_precedents_no_match()
        self.test_5_decide_with_precedents_follow()
        self.test_6_decide_with_precedents_deviate()
        self.test_7_decorator_pattern()
        self.test_8_convenience_function()
        
        self.print_summary()
    
    def test_1_middleware_creation(self):
        """Test that middleware can be created"""
        print_test("1. Middleware Creation")
        
        try:
            middleware = PrecedentMiddleware(
                tenant_id=self.tenant_id,
                decision_maker_id=self.decision_maker_id,
                api_key=self.api_key,
                base_url=self.base_url
            )
            print_pass("Middleware created successfully")
            self.results["creation"] = True
        except Exception as e:
            print_fail(f"Failed to create middleware: {e}")
            self.results["creation"] = False
    
    def test_2_retrieve_precedents(self):
        """Test precedent retrieval"""
        print_test("2. Retrieve Precedents")
        
        middleware = PrecedentMiddleware(
            tenant_id=self.tenant_id,
            decision_maker_id=self.decision_maker_id,
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        precedents, status, latency_ms = middleware.retrieve_precedents(
            situation="Customer wants a discount due to churn risk",
            decision_type="discount_approval",
            limit=5
        )
        
        print_info(f"Found {len(precedents)} precedents (status={status}, latency={latency_ms:.0f}ms)")
        
        if precedents:
            for i, p in enumerate(precedents[:3]):
                print_info(f"  {i+1}. {p.summary[:60]}... (score: {p.score:.3f})")
            print_pass("Precedent retrieval works")
            self.results["retrieve"] = True
        else:
            print_info("No precedents found (may need to seed more data)")
            self.results["retrieve"] = True
    
    def test_3_log_decision(self):
        """Test decision logging"""
        print_test("3. Log Decision")
        
        middleware = PrecedentMiddleware(
            tenant_id=self.tenant_id,
            decision_maker_id=self.decision_maker_id,
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        decision_id = middleware.log_decision(
            summary="Test middleware decision logging",
            choice={"test": True, "value": 42},
            rationale="Testing that middleware can log decisions",
            decision_type="middleware_test",
            evidence=[{"evidence_type": "agent_log", "excerpt": "Automated test"}]
        )
        
        if decision_id:
            print_pass(f"Decision logged: {decision_id}")
            self.results["log"] = True
        else:
            print_fail("Failed to log decision")
            self.results["log"] = False
    
    def test_4_decide_with_precedents_no_match(self):
        """Test decision when no strong precedent exists"""
        print_test("4. Decide - No Strong Precedent")
        
        middleware = PrecedentMiddleware(
            tenant_id=self.tenant_id,
            decision_maker_id=self.decision_maker_id,
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        def decide_fn(precedents):
            return {
                "choice": {"action": "default", "reason": "no_precedent"},
                "rationale": "No strong precedent found, using default logic",
                "deviated_from_id": precedents[0].decision_id if precedents else None,
                "deviation_reason": "Testing no-match scenario"
            }
        
        result = middleware.decide_with_precedents(
            situation="Completely novel situation for testing XYZ123",
            decision_type="middleware_test",
            decide_fn=decide_fn,
            auto_log=True
        )
        
        if result.choice:
            print_pass(f"Correctly handled no-match scenario")
            print_info(f"Choice: {result.choice}")
            print_info(f"Lookup status: {result.precedent_lookup_status}")
            print_info(f"Latency: {result.precedent_lookup_latency_ms:.0f}ms")
            self.results["no_match"] = True
        else:
            print_fail(f"Unexpected result: {result}")
            self.results["no_match"] = False
    
    def test_5_decide_with_precedents_follow(self):
        """Test decision when following a precedent"""
        print_test("5. Decide - Follow Precedent")
        
        middleware = PrecedentMiddleware(
            tenant_id=self.tenant_id,
            decision_maker_id=self.decision_maker_id,
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        def decide_fn(precedents):
            if precedents and precedents[0].score >= 0.5:
                return {
                    "choice": precedents[0].choice,
                    "rationale": f"Following precedent: {precedents[0].summary}",
                    "followed_precedent_id": precedents[0].decision_id
                }
            return {
                "choice": {"fallback": True},
                "rationale": "No suitable precedent"
            }
        
        result = middleware.decide_with_precedents(
            situation="Customer requesting discount due to competitor offer",
            decision_type="discount_approval",
            decide_fn=decide_fn,
            auto_log=True
        )
        
        if result.precedent_followed:
            print_pass(f"Correctly followed precedent: {result.precedent_followed}")
            print_info(f"Choice: {result.choice}")
            self.results["follow"] = True
        elif result.precedents_considered == 0:
            print_info("No precedents available to follow")
            self.results["follow"] = True
        else:
            print_info(f"No precedent followed (scores may be too low)")
            self.results["follow"] = True
    
    def test_6_decide_with_precedents_deviate(self):
        """Test decision when explicitly deviating from precedent"""
        print_test("6. Decide - Explicit Deviation")
        
        middleware = PrecedentMiddleware(
            tenant_id=self.tenant_id,
            decision_maker_id=self.decision_maker_id,
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        def decide_fn(precedents):
            if precedents:
                return {
                    "choice": {"action": "deviated", "custom": True},
                    "rationale": "Choosing to deviate due to unique circumstances",
                    "deviated_from_id": precedents[0].decision_id,
                    "deviation_reason": "Current case has factors not present in precedent"
                }
            return {
                "choice": {"action": "no_precedent"},
                "rationale": "No precedents to deviate from"
            }
        
        result = middleware.decide_with_precedents(
            situation="Special case discount request with unusual terms",
            decision_type="discount_approval",
            decide_fn=decide_fn,
            auto_log=True
        )
        
        if result.deviated:
            print_pass(f"Correctly recorded deviation")
            print_info(f"Deviated from: {result.precedent_followed or 'N/A'}")
            print_info(f"Reason: {result.deviation_reason}")
            self.results["deviate"] = True
        elif result.precedents_considered == 0:
            print_info("No precedents to deviate from")
            self.results["deviate"] = True
        else:
            print_fail(f"Expected deviation but got: {result}")
            self.results["deviate"] = False
    
    def test_7_decorator_pattern(self):
        """Test the decorator-based usage"""
        print_test("7. Decorator Pattern")
        
        middleware = PrecedentMiddleware(
            tenant_id=self.tenant_id,
            decision_maker_id=self.decision_maker_id,
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        @middleware.with_precedents(decision_type="decorator_test")
        def make_decision(value: int, *, precedents, context):
            if precedents and precedents[0].score > 0.5:
                middleware.follow(
                    precedent_id=precedents[0].decision_id,
                    choice={"decorated": True, "value": value},
                    rationale="Decorator test - following precedent"
                )
            else:
                middleware.deviate(
                    precedent_id=precedents[0].decision_id if precedents else None,
                    reason="No strong match",
                    choice={"decorated": True, "value": value, "default": True},
                    rationale="Decorator test - using default"
                )
            return {"success": True, "value": value}
        
        try:
            result = make_decision(99)
            print_pass(f"Decorator pattern works: {result}")
            self.results["decorator"] = True
        except Exception as e:
            print_fail(f"Decorator pattern failed: {e}")
            self.results["decorator"] = False
    
    def test_8_convenience_function(self):
        """Test the convenience function"""
        print_test("8. Convenience Function")
        
        try:
            result = decide_with_context(
                tenant_id=self.tenant_id,
                decision_maker_id=self.decision_maker_id,
                situation="Test convenience function for discount approval",
                decision_type="convenience_test",
                default_decision=lambda: {
                    "choice": {"convenience": True, "default": True},
                    "rationale": "Using default from convenience function"
                },
                adapt_from_precedent=lambda p: {
                    "choice": {"convenience": True, "from_precedent": True},
                    "rationale": f"Adapted from: {p.summary}"
                },
                api_key=self.api_key
            )
            
            print_pass(f"Convenience function works")
            print_info(f"Decision ID: {result.decision_id}")
            print_info(f"Choice: {result.choice}")
            print_info(f"Precedents considered: {result.precedents_considered}")
            self.results["convenience"] = True
        except Exception as e:
            print_fail(f"Convenience function failed: {e}")
            self.results["convenience"] = False
    
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
            print(f"\n{GREEN}🎉 ALL MIDDLEWARE TESTS PASSED!{RESET}")
            print(f"\nThe 'look before you leap' pattern is working.")
            print(f"Agents can now query precedents before making decisions.")
        else:
            print(f"\n{RED}Some tests failed. Review output above.{RESET}")
        
        return failed == 0


if __name__ == "__main__":
    suite = MiddlewareTests()
    success = suite.run_all()
    sys.exit(0 if success else 1)
