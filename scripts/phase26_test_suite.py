#!/usr/bin/env python3
"""
Phase 26 Final Test Suite - All 5 Vaults

Runs all 49 queries across 5 vaults and reports results.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logging.getLogger().setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session
from src.context_foundry.agents.tool_agent import ToolAgent

VAULT_CONFIG = {
    "TECHVENTURES": {
        "tenant_id": "351a152a-15fb-4a40-939b-c1190cfbffe1",
        "vault_context": "TechVentures",
        "queries": [
            "Who is the CEO?",
            "What is the CEO's salary?",
            "Who is the CTO?",
            "Who is the CTO of TechVentures?",
            "What is Sarah Chen's compensation?",
            "Who reports to the CEO?",
            "What portfolio companies does TechVentures have?",
            "Tell me about CloudMatrix",
            "Tell me about HealthSync",
            "Tell me about SecureNode",
        ]
    },
    "LAW FIRM": {
        "tenant_id": "82295c1d-78c7-4048-967f-4550edb3c0c3",
        "vault_context": "Morrison & Sterling LLP",
        "queries": [
            "Who is the Managing Partner?",
            "What is the Managing Partner's compensation?",
            "Who is the CFO?",
            "Who is the COO?",
            "Who reports to Amanda Foster?",
            "What practice groups does the firm have?",
            "Tell me about the litigation practice",
            "Who are the Tier 1 clients?",
            "What is Richard Sterling's compensation?",
        ]
    },
    "HOSPITAL": {
        "tenant_id": "8d02fa60-6f2f-424f-a1ed-65b7f98fec31",
        "vault_context": "Riverside Medical Center",
        "queries": [
            "Who is the CEO?",
            "What is the CEO's salary?",
            "Who is the CMO?",
            "Who is the CIO?",
            "What is the CIO's compensation?",
            "Who reports to the CEO?",
            "What departments does the hospital have?",
            "Tell me about the cardiac initiative",
            "Who leads the oncology department?",
            "Who leads the cardiology department?",
        ]
    },
    "MANUFACTURING": {
        "tenant_id": "3e858604-a86e-46f4-b2a2-f75d96cb43ef",
        "vault_context": "Orion Manufacturing",
        "queries": [
            "Who is the CEO?",
            "What is the CEO's compensation?",
            "Who is the COO?",
            "Who is the CTO?",
            "Who reports to the CEO?",
            "Who manages the Detroit plant?",
            "What is the Detroit plant manager's compensation?",
            "What plants does the company have?",
            "Tell me about the automation initiative",
            "Who leads quality assurance?",
        ]
    },
    "ACCELERATOR": {
        "tenant_id": "aae9fb11-bf8b-4b6d-b7fb-49179fb7160f",
        "vault_context": "San Francisco",
        "queries": [
            "Who is the Managing Partner?",
            "What is the Managing Partner's compensation?",
            "Who are the General Partners?",
            "Who reports to Alexandra Kim?",
            "What portfolio companies are in Cohort 12?",
            "Tell me about CloudAI",
            "Tell me about NeuralBox",
            "What is David Park's compensation?",
            "Who leads the Healthcare investments?",
            "What is the accelerator program structure?",
        ]
    }
}


@dataclass
class QueryResult:
    vault: str
    query: str
    answer: str
    confidence: float
    passed: bool
    error: Optional[str] = None
    duration_ms: float = 0


def run_query(session, tenant_id: str, vault_context: str, query: str) -> Tuple[str, float, Optional[str]]:
    """Run a single query and return (answer, confidence, error)."""
    try:
        session.execute(text("SELECT platform.set_current_tenant(:tid)"), {'tid': tenant_id})
        session.commit()
        
        agent = ToolAgent(session, tenant_id)
        result = agent.query(query, vault_context=vault_context)
        
        answer = result.get('answer', 'No answer')
        confidence = result.get('confidence', 0)
        
        if len(answer) > 200:
            answer = answer[:200] + "..."
        
        return answer, confidence, None
        
    except Exception as e:
        return "", 0, str(e)


def evaluate_result(query: str, answer: str, confidence: float) -> bool:
    """Evaluate if a result passes - has meaningful answer with reasonable confidence."""
    if not answer or answer == "No answer":
        return False
    
    fail_phrases = [
        "don't have information",
        "no information",
        "not found",
        "cannot find",
        "doesn't exist",
        "does not exist",
        "i don't know",
        "unable to find",
        "no data",
        "no entity"
    ]
    
    answer_lower = answer.lower()
    for phrase in fail_phrases:
        if phrase in answer_lower:
            return False
    
    if confidence < 0.3:
        return False
    
    return True


def run_vault_tests(vault_name: str, config: dict) -> List[QueryResult]:
    """Run all tests for a single vault."""
    results = []
    session = get_session()
    
    print(f"\n{'='*80}")
    print(f" {vault_name} ({len(config['queries'])} queries)")
    print(f"{'='*80}")
    
    for i, query in enumerate(config['queries'], 1):
        start_time = time.time()
        
        answer, confidence, error = run_query(
            session, 
            config['tenant_id'], 
            config['vault_context'],
            query
        )
        
        duration_ms = (time.time() - start_time) * 1000
        passed = evaluate_result(query, answer, confidence) if not error else False
        
        result = QueryResult(
            vault=vault_name,
            query=query,
            answer=answer,
            confidence=confidence,
            passed=passed,
            error=error,
            duration_ms=duration_ms
        )
        results.append(result)
        
        status = "PASS" if passed else "FAIL"
        conf_str = f"{confidence*100:.0f}%" if confidence else "0%"
        
        if error:
            print(f"[{status}] {vault_name}: {query}")
            print(f"       ERROR: {error[:100]}")
        else:
            short_answer = answer[:80] + "..." if len(answer) > 80 else answer
            print(f"[{status}] {vault_name}: {query}")
            print(f"       → {short_answer} ({conf_str})")
    
    session.close()
    return results


def main():
    print("\n" + "="*80)
    print(" PHASE 26 FINAL TEST SUITE - ALL 5 VAULTS")
    print(" " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*80)
    
    all_results = []
    vault_summaries = {}
    
    for vault_name, config in VAULT_CONFIG.items():
        results = run_vault_tests(vault_name, config)
        all_results.extend(results)
        
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        vault_summaries[vault_name] = (passed, total)
    
    total_passed = sum(1 for r in all_results if r.passed)
    total_queries = len(all_results)
    pct = (total_passed / total_queries * 100) if total_queries > 0 else 0
    
    print("\n" + "="*80)
    print(" SUMMARY")
    print("="*80)
    print()
    
    for vault_name, (passed, total) in vault_summaries.items():
        pct_vault = (passed / total * 100) if total > 0 else 0
        print(f"  {vault_name}: {passed}/{total} ({pct_vault:.0f}%)")
    
    print()
    print(f"  TOTAL: {total_passed}/{total_queries} passed ({pct:.1f}%)")
    print()
    
    output_file = "phase26_final_test_results.txt"
    with open(output_file, 'w') as f:
        f.write("PHASE 26 FINAL TEST SUITE - ALL 5 VAULTS\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        
        for vault_name in VAULT_CONFIG.keys():
            f.write(f"\n{vault_name}\n")
            f.write("-" * len(vault_name) + "\n")
            
            vault_results = [r for r in all_results if r.vault == vault_name]
            for r in vault_results:
                status = "PASS" if r.passed else "FAIL"
                conf_str = f"{r.confidence*100:.0f}%" if r.confidence else "0%"
                f.write(f"[{status}] {r.query}\n")
                if r.error:
                    f.write(f"    ERROR: {r.error[:100]}\n")
                else:
                    f.write(f"    → {r.answer[:150]}{'...' if len(r.answer) > 150 else ''} ({conf_str})\n")
                f.write("\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("SUMMARY\n")
        f.write("="*80 + "\n\n")
        
        for vault_name, (passed, total) in vault_summaries.items():
            pct_vault = (passed / total * 100) if total > 0 else 0
            f.write(f"{vault_name}: {passed}/{total} ({pct_vault:.0f}%)\n")
        
        f.write(f"\nTOTAL: {total_passed}/{total_queries} passed ({pct:.1f}%)\n")
    
    print(f"Results exported to: {output_file}")
    
    return total_passed, total_queries


if __name__ == "__main__":
    passed, total = main()
    sys.exit(0 if passed == total else 1)
