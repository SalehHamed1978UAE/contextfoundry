#!/usr/bin/env python3
"""
Test the 3-Step Query Pipeline.

This script tests the new query interpretation → directed retrieval → synthesis pipeline.
"""

import os
import sys
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

from src.context_foundry.models.schema import get_session
from src.context_foundry.agents.query_interpreter import QueryInterpreter
from src.context_foundry.agents.directed_retriever import DirectedGraphRetriever
from src.context_foundry.agents.query_pipeline import QueryPipeline

DEMO_TENANT_ID = "8eee325b-ba3b-447e-9ee7-6d66085ead5f"

TEST_QUERIES = [
    {
        "query": "What's the blast radius if API Gateway fails?",
        "expected_direction": "inbound",
        "expected_types": ["DEPENDS_ON", "CALLS"],
        "description": "Blast radius - should find what DEPENDS_ON API Gateway"
    },
    {
        "query": "What does Order Service depend on?",
        "expected_direction": "outbound",
        "expected_types": ["DEPENDS_ON"],
        "description": "Direct dependency - should find Order Service's dependencies"
    },
    {
        "query": "Who manages the Payment Service?",
        "expected_direction": "inbound",
        "expected_types": ["MANAGES", "OWNS"],
        "description": "Ownership - should find who MANAGES/OWNS Payment Service"
    },
    {
        "query": "What was affected by incident INC-2025-1201?",
        "expected_direction": "outbound",
        "expected_types": ["AFFECTS"],
        "description": "Incident impact - should find what the incident AFFECTS"
    },
    {
        "query": "What services does API Gateway call?",
        "expected_direction": "outbound",
        "expected_types": ["CALLS"],
        "description": "Communication - should find what API Gateway CALLS"
    }
]


def test_step1_interpretation():
    """Test Step 1: Query Interpretation."""
    print("\n" + "="*60)
    print("STEP 1 TEST: Query Interpretation")
    print("="*60)
    
    interpreter = QueryInterpreter()
    
    results = []
    for test in TEST_QUERIES:
        intent = interpreter.interpret(test["query"])
        
        direction_match = intent.direction == test["expected_direction"]
        types_match = set(intent.relationship_types) & set(test["expected_types"])
        
        status = "PASS" if direction_match and types_match else "FAIL"
        
        print(f"\n[{status}] {test['description']}")
        print(f"  Query: {test['query']}")
        print(f"  Expected: direction={test['expected_direction']}, types={test['expected_types']}")
        print(f"  Got: direction={intent.direction}, types={intent.relationship_types}")
        print(f"  Entity: {intent.entity}")
        print(f"  Reasoning: {intent.reasoning}")
        
        results.append({
            "query": test["query"],
            "status": status,
            "intent": intent.to_dict()
        })
    
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n[STEP 1 SUMMARY] {passed}/{len(results)} tests passed")
    
    return results


def test_step2_retrieval():
    """Test Step 2: Directed Graph Retrieval."""
    print("\n" + "="*60)
    print("STEP 2 TEST: Directed Graph Retrieval")
    print("="*60)
    
    from sqlalchemy import text
    session = get_session()
    
    session.execute(
        text("SELECT platform.set_current_tenant(:tid)"),
        {'tid': DEMO_TENANT_ID}
    )
    
    retriever = DirectedGraphRetriever(session, DEMO_TENANT_ID)
    interpreter = QueryInterpreter()
    
    for test in TEST_QUERIES[:2]:
        print(f"\n--- Testing: {test['description']} ---")
        
        intent = interpreter.interpret(test["query"])
        print(f"Intent: entity='{intent.entity}', direction={intent.direction}, types={intent.relationship_types}")
        
        result = retriever.execute(intent)
        
        if result.entity_found:
            print(f"Entity found: {result.entity_name} ({result.entity_type})")
            print(f"Relationships found: {len(result.relationships)}")
            
            by_direction = {"inbound": 0, "outbound": 0}
            by_type = {}
            for rel in result.relationships:
                by_direction[rel.direction_relative_to_entity] += 1
                by_type[rel.relationship_type] = by_type.get(rel.relationship_type, 0) + 1
            
            print(f"  By direction: {by_direction}")
            print(f"  By type: {by_type}")
            print(f"Affected entities: {len(result.affected_entities)}")
            
            for rel in result.relationships[:5]:
                print(f"  - [{rel.direction_relative_to_entity}] {rel.source_name} --[{rel.relationship_type}]--> {rel.target_name}")
        else:
            print(f"Entity NOT found: {intent.entity}")
    
    session.close()


def test_full_pipeline():
    """Test the full 3-step pipeline."""
    print("\n" + "="*60)
    print("FULL PIPELINE TEST")
    print("="*60)
    
    from sqlalchemy import text
    session = get_session()
    
    session.execute(
        text("SELECT platform.set_current_tenant(:tid)"),
        {'tid': DEMO_TENANT_ID}
    )
    
    pipeline = QueryPipeline(session, DEMO_TENANT_ID)
    
    query = "What's the blast radius if API Gateway fails?"
    print(f"\nQuery: {query}")
    print("-" * 40)
    
    result = pipeline.execute(query)
    
    print(f"\n[STEP 1] Query Interpretation ({result.step1_duration_ms:.0f}ms)")
    if result.step1_intent:
        print(f"  Entity: {result.step1_intent.entity}")
        print(f"  Direction: {result.step1_intent.direction}")
        print(f"  Types: {result.step1_intent.relationship_types}")
        print(f"  Depth: {result.step1_intent.depth}")
        print(f"  Reasoning: {result.step1_intent.reasoning}")
    
    print(f"\n[STEP 2] Directed Retrieval ({result.step2_duration_ms:.0f}ms)")
    if result.step2_result:
        print(f"  Entity Found: {result.step2_result.entity_found}")
        print(f"  Entity: {result.step2_result.entity_name}")
        print(f"  Relationships: {len(result.step2_result.relationships)}")
        print(f"  Affected Entities: {len(result.step2_result.affected_entities)}")
        
        print("\n  Relationships retrieved:")
        for rel in result.step2_result.relationships[:10]:
            print(f"    [{rel.direction_relative_to_entity}] {rel.source_name} --[{rel.relationship_type}]--> {rel.target_name}")
    
    print(f"\n[STEP 3] Answer Synthesis ({result.step3_duration_ms:.0f}ms)")
    print(f"  Confidence: {result.step3_confidence:.2f}")
    print(f"  Answer:\n{result.step3_answer}")
    
    print(f"\n[TOTAL] {result.total_duration_ms:.0f}ms")
    
    session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test the 3-Step Query Pipeline")
    parser.add_argument("--step1", action="store_true", help="Test Step 1 only")
    parser.add_argument("--step2", action="store_true", help="Test Step 2 only")
    parser.add_argument("--full", action="store_true", help="Test full pipeline")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    if not any([args.step1, args.step2, args.full, args.all]):
        args.all = True
    
    if args.step1 or args.all:
        test_step1_interpretation()
    
    if args.step2 or args.all:
        test_step2_retrieval()
    
    if args.full or args.all:
        test_full_pipeline()
