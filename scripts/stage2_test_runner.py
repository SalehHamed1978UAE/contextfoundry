#!/usr/bin/env python3
"""
Stage 2 Test Runner: Context-Attached Knowledge Validation

Tests 20 contextual questions that require relationship context fields 
(temporal validity, provenance text, event context, qualifiers) to answer correctly.

Success criteria: 16/20 (80%) answered correctly using context fields (NOT document fallback).
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session, Entity, Relationship
from src.context_foundry.memory.temporal import get_relationships_at_time, get_entity_history
from datetime import datetime
import json

TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"

TEST_QUESTIONS = [
    {
        "id": 1,
        "question": "What position did Saleh Hamed hold in August 2005?",
        "answer_pattern": "Systems Engineer",
        "requires": "temporal_query",
        "query_date": "2005-08-01"
    },
    {
        "id": 2,
        "question": "What position did Saleh Hamed hold in September 2010?",
        "answer_pattern": "Manager, Systems Design",
        "requires": "temporal_query",
        "query_date": "2010-09-01"
    },
    {
        "id": 3,
        "question": "When did Saleh Hamed's role as Systems Engineer end?",
        "answer_pattern": "2008-09|September 2008",
        "requires": "valid_to"
    },
    {
        "id": 4,
        "question": "What was the event context for Saleh's first position?",
        "answer_pattern": "Early career|ENEC",
        "requires": "event_context"
    },
    {
        "id": 5,
        "question": "What position did Saleh hold in 2020?",
        "answer_pattern": "Executive Director, Operations",
        "requires": "temporal_query",
        "query_date": "2020-01-01"
    },
    {
        "id": 6,
        "question": "When did Horizon Ventures invest in TechStart Inc?",
        "answer_pattern": "2020-03|March 2020",
        "requires": "valid_from"
    },
    {
        "id": 7,
        "question": "What was the investment round context for TechStart?",
        "answer_pattern": "Series A",
        "requires": "event_context"
    },
    {
        "id": 8,
        "question": "Is Horizon's investment in GreenEnergy still active?",
        "answer_pattern": "yes|active|null|None|ongoing",
        "requires": "valid_to"
    },
    {
        "id": 9,
        "question": "When did Horizon exit CloudNine?",
        "answer_pattern": "2021-12|December 2021",
        "requires": "valid_to"
    },
    {
        "id": 10,
        "question": "What context describes the CloudNine investment?",
        "answer_pattern": "Exit|exit phase",
        "requires": "event_context"
    },
    {
        "id": 11,
        "question": "How many positions has Saleh held in total?",
        "answer_pattern": "6|six",
        "requires": "timeline_count"
    },
    {
        "id": 12,
        "question": "Did Saleh work at ENEC in January 2015?",
        "answer_pattern": "yes|Yes|Director",
        "requires": "temporal_query",
        "query_date": "2015-01-01"
    },
    {
        "id": 13,
        "question": "What position came after Systems Engineer for Saleh?",
        "answer_pattern": "Manager|Design|Strategic",
        "requires": "timeline_order"
    },
    {
        "id": 14,
        "question": "When did Saleh transition from ENEC to DGE?",
        "answer_pattern": "2022|August 2022",
        "requires": "timeline_transition"
    },
    {
        "id": 15,
        "question": "What organization is Horizon Ventures investing in during the scaling phase?",
        "answer_pattern": "HealthFirst|health",
        "requires": "event_context"
    },
    {
        "id": 16,
        "question": "What was Saleh's final role at ENEC?",
        "answer_pattern": "Executive Director, Operations",
        "requires": "timeline_last"
    },
    {
        "id": 17,
        "question": "Is Saleh's current position at QData still active?",
        "answer_pattern": "yes|active|present|ongoing",
        "requires": "valid_to"
    },
    {
        "id": 18,
        "question": "How long was Saleh a Systems Engineer?",
        "answer_pattern": "5 years|five|2003.*2008",
        "requires": "duration"
    },
    {
        "id": 19,
        "question": "What companies has Horizon invested in since 2020?",
        "answer_pattern": "TechStart|HealthFirst|DataFlow",
        "requires": "temporal_filter"
    },
    {
        "id": 20,
        "question": "Which investment has valid_to = null (still active)?",
        "answer_pattern": "GreenEnergy|TechStart|HealthFirst|DataFlow",
        "requires": "valid_to_null"
    }
]


def run_temporal_query(session, entity_name, query_date, tenant_id):
    """Run a temporal query to find relationships at a specific time."""
    entity = session.query(Entity).filter(
        Entity.name.ilike(f"%{entity_name}%"),
        Entity.tenant_id == tenant_id
    ).first()
    
    if not entity:
        return {"error": f"Entity not found: {entity_name}"}
    
    dt = datetime.strptime(query_date, "%Y-%m-%d")
    
    relationships = get_relationships_at_time(
        session=session,
        tenant_id=str(tenant_id),
        entity_id=str(entity.id),
        at_time=dt
    )
    
    return relationships


def get_all_relationships_for_entity(session, entity_name, tenant_id):
    """Get all relationships for an entity."""
    from sqlalchemy import func
    
    entity = session.query(Entity).filter(
        func.lower(Entity.name).contains(entity_name.lower()),
        Entity.tenant_id == tenant_id
    ).first()
    
    if not entity:
        return []
    
    rels = session.query(Relationship).filter(
        Relationship.tenant_id == tenant_id,
        Relationship.source_id == entity.id
    ).order_by(Relationship.valid_from).all()
    
    return rels


def evaluate_question(session, question, tenant_id):
    """Evaluate a single question against the knowledge graph."""
    import re
    import uuid
    
    tenant_uuid = uuid.UUID(tenant_id)
    result = {
        "id": question["id"],
        "question": question["question"],
        "expected_pattern": question["answer_pattern"],
        "requires": question["requires"],
        "passed": False,
        "actual_answer": None,
        "evidence": None
    }
    
    try:
        if question["requires"] == "temporal_query":
            entity_name = "Saleh" if "Saleh" in question["question"] else "Horizon"
            rels = run_temporal_query(session, entity_name, question.get("query_date", "2020-01-01"), tenant_uuid)
            
            if rels and not isinstance(rels, dict):
                answers = [r.get("other_entity", {}).get("name", "") for r in rels]
                result["actual_answer"] = ", ".join(answers)
                result["evidence"] = f"Found {len(rels)} relationships at {question.get('query_date')}"
            else:
                result["actual_answer"] = "No relationships found"
                
        elif question["requires"] in ["valid_from", "valid_to", "event_context"]:
            entity_name = "Saleh" if "Saleh" in question["question"] else ("Horizon" if "Horizon" in question["question"] else "CloudNine")
            
            if "TechStart" in question["question"]:
                entity_name = "Horizon"
            elif "CloudNine" in question["question"]:
                entity_name = "Horizon"
            elif "GreenEnergy" in question["question"]:
                entity_name = "Horizon"
            
            rels = get_all_relationships_for_entity(session, entity_name, tenant_uuid)
            
            context_data = []
            for rel in rels:
                target = session.query(Entity).filter(Entity.id == rel.target_id).first()
                target_name = target.name if target else "?"
                context_data.append({
                    "target": target_name,
                    "valid_from": str(rel.valid_from) if rel.valid_from else None,
                    "valid_to": str(rel.valid_to) if rel.valid_to else None,
                    "event_context": rel.event_context
                })
            
            relevant = context_data
            if "TechStart" in question["question"]:
                relevant = [c for c in context_data if "TechStart" in c["target"]]
            elif "CloudNine" in question["question"]:
                relevant = [c for c in context_data if "CloudNine" in c["target"]]
            elif "GreenEnergy" in question["question"]:
                relevant = [c for c in context_data if "GreenEnergy" in c["target"]]
            elif "first position" in question["question"]:
                relevant = context_data[:1] if context_data else []
            
            if relevant:
                if question["requires"] == "valid_from":
                    result["actual_answer"] = relevant[0].get("valid_from", "None")
                elif question["requires"] == "valid_to":
                    result["actual_answer"] = str(relevant[0].get("valid_to", "None"))
                elif question["requires"] == "event_context":
                    result["actual_answer"] = relevant[0].get("event_context", "None")
                result["evidence"] = json.dumps(relevant[:3], default=str)
            else:
                result["actual_answer"] = "No matching data"
                
        elif question["requires"] == "timeline_count":
            entity_name = "Saleh" if "Saleh" in question["question"] else "Horizon"
            rels = get_all_relationships_for_entity(session, entity_name, tenant_uuid)
            result["actual_answer"] = str(len(rels))
            result["evidence"] = f"Found {len(rels)} relationships"
            
        elif question["requires"] in ["timeline_order", "timeline_last", "timeline_transition"]:
            entity_name = "Saleh" if "Saleh" in question["question"] else "Horizon"
            rels = get_all_relationships_for_entity(session, entity_name, tenant_uuid)
            
            if rels:
                if question["requires"] == "timeline_order" and len(rels) > 1:
                    target = session.query(Entity).filter(Entity.id == rels[1].target_id).first()
                    result["actual_answer"] = target.name if target else "?"
                elif question["requires"] == "timeline_last":
                    last_at_enec = None
                    for rel in rels:
                        target = session.query(Entity).filter(Entity.id == rel.target_id).first()
                        if target and rel.event_context and "ENEC" in rel.event_context:
                            last_at_enec = target.name
                    result["actual_answer"] = last_at_enec or "?"
                elif question["requires"] == "timeline_transition":
                    transition_dates = []
                    for rel in rels:
                        if rel.valid_to:
                            transition_dates.append(str(rel.valid_to))
                    result["actual_answer"] = ", ".join(transition_dates[-2:]) if transition_dates else "?"
                    
                result["evidence"] = f"Timeline has {len(rels)} entries"
                
        elif question["requires"] == "duration":
            entity_name = "Saleh"
            rels = get_all_relationships_for_entity(session, entity_name, tenant_uuid)
            
            for rel in rels:
                target = session.query(Entity).filter(Entity.id == rel.target_id).first()
                if target and "Systems Engineer" in target.name:
                    if rel.valid_from and rel.valid_to:
                        years = (rel.valid_to - rel.valid_from).days / 365
                        result["actual_answer"] = f"{years:.1f} years ({rel.valid_from.year} - {rel.valid_to.year})"
                    break
            
        elif question["requires"] == "temporal_filter":
            rels = get_all_relationships_for_entity(session, "Horizon", tenant_uuid)
            
            since_2020 = []
            for rel in rels:
                if rel.valid_from and rel.valid_from.year >= 2020:
                    target = session.query(Entity).filter(Entity.id == rel.target_id).first()
                    if target:
                        since_2020.append(target.name)
            
            result["actual_answer"] = ", ".join(since_2020)
            result["evidence"] = f"Found {len(since_2020)} investments since 2020"
            
        elif question["requires"] == "valid_to_null":
            rels = get_all_relationships_for_entity(session, "Horizon", tenant_uuid)
            
            active = []
            for rel in rels:
                if rel.valid_to is None:
                    target = session.query(Entity).filter(Entity.id == rel.target_id).first()
                    if target:
                        active.append(target.name)
            
            result["actual_answer"] = ", ".join(active)
            result["evidence"] = f"Found {len(active)} active investments (valid_to=null)"
        
        pattern = question["answer_pattern"]
        if result["actual_answer"] and re.search(pattern, str(result["actual_answer"]), re.IGNORECASE):
            result["passed"] = True
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


def main():
    print("=" * 70)
    print("Stage 2 Test Runner: Context-Attached Knowledge Validation")
    print("=" * 70)
    print(f"Testing {len(TEST_QUESTIONS)} contextual questions")
    print(f"Target: 16/20 (80%) using relationship context fields")
    print("=" * 70)
    
    session = get_session()
    session.execute(text(f"SET app.current_tenant_id = '{TEST_TENANT_ID}'"))
    
    passed = 0
    failed = 0
    
    for q in TEST_QUESTIONS:
        result = evaluate_question(session, q, TEST_TENANT_ID)
        
        status = "PASS" if result["passed"] else "FAIL"
        print(f"\n[{result['id']:02d}] {status}: {result['question']}")
        print(f"     Expected: {result['expected_pattern']}")
        print(f"     Actual: {result['actual_answer']}")
        if result.get("evidence"):
            print(f"     Evidence: {result['evidence'][:100]}...")
        if result.get("error"):
            print(f"     Error: {result['error']}")
        
        if result["passed"]:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{len(TEST_QUESTIONS)} passed ({100*passed/len(TEST_QUESTIONS):.0f}%)")
    print("=" * 70)
    
    if passed >= 16:
        print("SUCCESS: Stage 2 validation PASSED! Context-attached knowledge works.")
    else:
        print(f"NEEDS IMPROVEMENT: Target is 16/20 (80%), got {passed}/20")
    
    session.close()
    return 0 if passed >= 16 else 1


if __name__ == "__main__":
    sys.exit(main())
