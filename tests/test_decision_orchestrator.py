#!/usr/bin/env python3
"""
Test the Decision Orchestrator integration.

Validates:
1. Single integration hook pattern
2. 300ms timeout with no-block fallback
3. Metrics tracking (call rate, latency, citation vs deviation rates)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.decision_trace_layer.decision_orchestrator import (
    DecisionOrchestrator,
    DecisionType,
    OrchestratorConfig,
    create_orchestrator_for_tenant
)
from src.decision_trace_layer.precedent_middleware import PrecedentMiddleware

def print_test(name):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)

def print_pass(msg):
    print(f"[PASS] {msg}")

def print_fail(msg):
    print(f"[FAIL] {msg}")

def print_info(msg):
    print(f"[INFO] {msg}")


def test_orchestrator_creation():
    """Test basic orchestrator creation"""
    print_test("1. Orchestrator Creation")
    
    api_key = os.environ.get("CF_API_KEY")
    base_url = os.environ.get("DTL_BASE_URL", "http://localhost:3000")
    
    if not api_key:
        print_info("No API key, testing disabled mode")
        config = OrchestratorConfig(enable_precedent_lookup=False)
        orch = DecisionOrchestrator(
            tenant_id="test-tenant",
            decision_maker_id="test-agent",
            config=config
        )
        print_pass("Orchestrator created in disabled mode")
        return True
    
    config = OrchestratorConfig(
        precedent_timeout_seconds=0.3,
        strong_precedent_threshold=0.7,
        auto_log_decisions=True,
        enable_precedent_lookup=True
    )
    
    orch = DecisionOrchestrator(
        tenant_id="test-tenant",
        decision_maker_id="test-agent",
        api_key=api_key,
        base_url=base_url,
        config=config
    )
    
    print_pass("Orchestrator created successfully")
    return True


def test_make_decision():
    """Test making a decision with precedent lookup"""
    print_test("2. Make Decision")
    
    api_key = os.environ.get("CF_API_KEY")
    base_url = os.environ.get("DTL_BASE_URL", "http://localhost:3000")
    
    if not api_key:
        print_info("Skipping - no API key")
        return True
    
    orch = create_orchestrator_for_tenant("test-tenant")
    
    def decide_fn(precedents):
        if precedents and precedents[0].score >= 0.7:
            return {
                "choice": {"action": "follow", "value": precedents[0].choice},
                "rationale": "Following strong precedent",
                "followed_precedent_id": precedents[0].precedent_id
            }
        return {
            "choice": {"action": "default", "value": "tier1"},
            "rationale": "No strong precedent available"
        }
    
    result = orch.make_decision(
        decision_type=DecisionType.QUERY_ROUTING,
        situation="Complex query about service dependencies",
        decide_fn=decide_fn
    )
    
    print_info(f"Decision ID: {result.decision_id}")
    print_info(f"Lookup status: {result.precedent_lookup_status}")
    print_info(f"Latency: {result.precedent_lookup_latency_ms:.0f}ms")
    print_info(f"Precedents considered: {result.precedents_considered}")
    print_pass("Decision made successfully")
    return True


def test_timeout_behavior():
    """Test that timeout doesn't block"""
    print_test("3. Timeout Behavior (300ms)")
    
    api_key = os.environ.get("CF_API_KEY")
    base_url = os.environ.get("DTL_BASE_URL", "http://localhost:3000")
    
    if not api_key:
        print_info("Skipping - no API key")
        return True
    
    config = OrchestratorConfig(
        precedent_timeout_seconds=0.3,
        enable_precedent_lookup=True
    )
    
    orch = DecisionOrchestrator(
        tenant_id="test-tenant",
        decision_maker_id="test-agent",
        api_key=api_key,
        base_url=base_url,
        config=config
    )
    
    start_time = time.time()
    result = orch.make_decision(
        decision_type=DecisionType.TIER_SELECTION,
        situation="Test query for timeout behavior",
        decide_fn=lambda prec: {"choice": {"tier": "tier1"}, "rationale": "default"}
    )
    elapsed = (time.time() - start_time) * 1000
    
    print_info(f"Total elapsed: {elapsed:.0f}ms")
    print_info(f"Lookup latency: {result.precedent_lookup_latency_ms:.0f}ms")
    print_info(f"Lookup status: {result.precedent_lookup_status}")
    
    if result.precedent_lookup_latency_ms <= 350:
        print_pass(f"Lookup latency {result.precedent_lookup_latency_ms:.0f}ms within 300ms (+50ms buffer)")
        return True
    else:
        print_fail(f"Lookup latency too high: {result.precedent_lookup_latency_ms:.0f}ms (max 350ms)")
        return False


def test_metrics_tracking():
    """Test metrics collection"""
    print_test("4. Metrics Tracking")
    
    DecisionOrchestrator.reset_metrics()
    
    api_key = os.environ.get("CF_API_KEY")
    if not api_key:
        print_info("Skipping - no API key")
        return True
    
    orch = create_orchestrator_for_tenant("test-tenant")
    
    for i in range(3):
        orch.make_decision(
            decision_type=DecisionType.QUERY_ROUTING,
            situation=f"Test query {i}",
            decide_fn=lambda p: {"choice": {"test": i}, "rationale": "test"}
        )
    
    metrics = DecisionOrchestrator.get_metrics()
    print_info(f"Total calls: {metrics.total_calls}")
    print_info(f"Successful calls: {metrics.successful_calls}")
    print_info(f"Timeout calls: {metrics.timeout_calls}")
    print_info(f"Mean latency: {metrics.mean_latency_ms:.1f}ms")
    print_info(f"P95 latency: {metrics.p95_latency_ms:.1f}ms")
    print_info(f"Call rate: {metrics.call_rate:.1f}%")
    print_info(f"Citation rate: {metrics.citation_rate:.1f}%")
    print_info(f"Deviation rate: {metrics.deviation_rate:.1f}%")
    
    if metrics.total_calls >= 3:
        print_pass("Metrics tracked across calls")
        return True
    else:
        print_fail(f"Expected 3+ calls, got {metrics.total_calls}")
        return False


def test_factory_function():
    """Test the factory function"""
    print_test("5. Factory Function")
    
    orch = create_orchestrator_for_tenant(
        tenant_id="test-tenant-123",
        decision_maker_id="cf-agent",
        enabled=False
    )
    
    result = orch.make_decision(
        decision_type=DecisionType.ENTITY_RESOLUTION,
        situation="Test with disabled lookup",
        decide_fn=lambda p: {"choice": {"entity": "test"}, "rationale": "test"}
    )
    
    if result.precedent_lookup_status == "disabled":
        print_pass("Factory function works, lookup disabled as expected")
        return True
    else:
        print_fail(f"Expected disabled, got {result.precedent_lookup_status}")
        return False


def test_decision_types():
    """Test all decision type enums"""
    print_test("6. Decision Types")
    
    expected = [
        "query_routing",
        "entity_resolution", 
        "sufficiency_assessment",
        "tier_selection",
        "confidence_threshold",
        "custom"
    ]
    
    for dt in DecisionType:
        if dt.value in expected:
            print_info(f"Found: {dt.name} = {dt.value}")
        else:
            print_fail(f"Unexpected type: {dt.value}")
            return False
    
    print_pass("All decision types valid")
    return True


def main():
    results = {}
    
    print("\n" + "="*60)
    print("DECISION ORCHESTRATOR TEST SUITE")
    print("="*60)
    
    results["creation"] = test_orchestrator_creation()
    results["decision"] = test_make_decision()
    results["timeout"] = test_timeout_behavior()
    results["metrics"] = test_metrics_tracking()
    results["factory"] = test_factory_function()
    results["types"] = test_decision_types()
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\nAll orchestrator tests passed!")
        return 0
    else:
        print("\nSome tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
