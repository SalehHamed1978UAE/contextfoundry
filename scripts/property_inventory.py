#!/usr/bin/env python3
"""M0 — Property Fact Inventory.

Queries the entities table, parses `properties` JSON blobs, and maps to the
16 failing PROPERTY-plane questions from the Nexus 100Q benchmark.

Usage:
    python scripts/property_inventory.py --tenant-id <uuid>
    python scripts/property_inventory.py --tenant-id <uuid> --output report.json

Output: JSON report confirming which of the 16 failing questions have matching
data in entity.properties vs. needing chunk extraction.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger(__name__)

# ── The 16 failing PROPERTY-plane questions (Stage 2F analysis) ──────────

FAILING_PROPERTY_QUESTIONS = [
    {"id": "Q1", "query": "What is Nexus Industries' total revenue?", "attribute": "revenue", "entity_type": "FINANCIAL_METRIC"},
    {"id": "Q2", "query": "What is the total company backlog?", "attribute": "backlog", "entity_type": "FINANCIAL_METRIC"},
    {"id": "Q3", "query": "What is the EBITDA margin?", "attribute": "ebitda_margin", "entity_type": "FINANCIAL_METRIC"},
    {"id": "Q4", "query": "What is the Quantum Shield budget?", "attribute": "budget", "entity_type": "PROJECT"},
    {"id": "Q5", "query": "What is Project Titan's budget?", "attribute": "budget", "entity_type": "PROJECT"},
    {"id": "Q6", "query": "What is the Green Horizon Initiative budget?", "attribute": "budget", "entity_type": "PROJECT"},
    {"id": "Q7", "query": "How many qubits does the quantum computing platform have?", "attribute": "qubits", "entity_type": "PRODUCT"},
    {"id": "Q8", "query": "What is the energy density of the solid-state batteries?", "attribute": "energy_density", "entity_type": "PRODUCT"},
    {"id": "Q9", "query": "What is the throughput of the advanced manufacturing line?", "attribute": "throughput", "entity_type": "FACILITY"},
    {"id": "Q10", "query": "What is the Austin facility capacity?", "attribute": "capacity", "entity_type": "FACILITY"},
    {"id": "Q11", "query": "What is the contract value for the DOD partnership?", "attribute": "contract_value", "entity_type": "CUSTOMER"},
    {"id": "Q12", "query": "What is the annual revenue growth rate?", "attribute": "growth_rate", "entity_type": "FINANCIAL_METRIC"},
    {"id": "Q13", "query": "What is the R&D spending as a percentage of revenue?", "attribute": "rd_percentage", "entity_type": "FINANCIAL_METRIC"},
    {"id": "Q14", "query": "What is the market share for quantum computing?", "attribute": "market_share", "entity_type": "PRODUCT"},
    {"id": "Q15", "query": "What is the headcount for Nexus Industries?", "attribute": "headcount", "entity_type": "FINANCIAL_METRIC"},
    {"id": "Q16", "query": "What is the target completion date for Project Titan?", "attribute": "target_date", "entity_type": "PROJECT"},
]

# ── Property key aliases (entity.properties keys → normalized attribute) ──

PROPERTY_KEY_MAP: Dict[str, List[str]] = {
    "revenue": ["revenue", "total_revenue", "annual_revenue", "value"],
    "backlog": ["backlog", "total_backlog", "order_backlog", "value"],
    "budget": ["budget", "budget_value", "total_budget", "value"],
    "ebitda_margin": ["ebitda_margin", "ebitda", "margin", "value"],
    "qubits": ["qubits", "qubit_count", "capacity", "value"],
    "energy_density": ["energy_density", "density", "value"],
    "throughput": ["throughput", "production_rate", "capacity", "value"],
    "capacity": ["capacity", "production_capacity", "value"],
    "contract_value": ["contract_value", "value", "deal_value"],
    "growth_rate": ["growth_rate", "revenue_growth", "value"],
    "rd_percentage": ["rd_percentage", "rd_spend", "r_and_d", "value"],
    "market_share": ["market_share", "share", "value"],
    "headcount": ["headcount", "employee_count", "employees", "value"],
    "target_date": ["target_date", "end_date", "completion_date", "deadline", "value"],
}


def get_session():
    """Create a DB session using the same env vars as the main app."""
    from src.context_foundry.models.schema import get_session as _get_session
    return _get_session()


def fetch_entities_by_type(session, tenant_id: str) -> Dict[str, List[Dict]]:
    """Fetch all entities grouped by entity_type for the given tenant."""
    sql = """
        SELECT id::text, name, entity_type, properties, lifecycle_state,
               source_document_id, confidence
        FROM entities
        WHERE tenant_id = :tid
        ORDER BY entity_type, name
    """
    rows = session.execute(text(sql), {"tid": tenant_id}).fetchall()
    by_type: Dict[str, List[Dict]] = defaultdict(list)
    for r in rows:
        props = r.properties if isinstance(r.properties, dict) else {}
        by_type[r.entity_type].append({
            "id": r.id,
            "name": r.name,
            "entity_type": r.entity_type,
            "properties": props,
            "lifecycle_state": r.lifecycle_state,
            "source_document_id": r.source_document_id,
            "confidence": r.confidence,
        })
    return dict(by_type)


def find_property_value(props: Dict, aliases: List[str]) -> Optional[str]:
    """Try to resolve a value from properties using alias keys."""
    for key in aliases:
        if key in props and props[key] is not None:
            val = str(props[key]).strip()
            if val and val.lower() not in ("none", "null", "n/a", ""):
                return val
    return None


def check_question_coverage(
    question: Dict, entities_by_type: Dict[str, List[Dict]]
) -> Dict[str, Any]:
    """Check if a failing question has matching data in entity properties."""
    attr = question["attribute"]
    etype = question["entity_type"]
    aliases = PROPERTY_KEY_MAP.get(attr, [attr])

    candidates = entities_by_type.get(etype, [])
    matches = []
    for ent in candidates:
        val = find_property_value(ent["properties"], aliases)
        if val:
            matches.append({
                "entity_id": ent["id"],
                "entity_name": ent["name"],
                "lifecycle_state": ent["lifecycle_state"],
                "matched_value": val,
                "property_keys": list(ent["properties"].keys()),
            })

    return {
        "question_id": question["id"],
        "query": question["query"],
        "attribute": attr,
        "entity_type": etype,
        "covered": len(matches) > 0,
        "match_count": len(matches),
        "matches": matches[:5],  # top 5 for readability
    }


def run_inventory(tenant_id: str) -> Dict[str, Any]:
    """Run the full inventory and return a JSON-serializable report."""
    session = get_session()
    try:
        from src.context_foundry.models.schema import set_tenant_context
        set_tenant_context(session, tenant_id)
    except Exception as e:
        logger.warning(f"set_tenant_context failed (non-fatal): {e}")

    entities_by_type = fetch_entities_by_type(session, tenant_id)

    # Type summary
    type_summary = {t: len(ents) for t, ents in sorted(entities_by_type.items())}

    # Property coverage per question
    coverage = []
    for q in FAILING_PROPERTY_QUESTIONS:
        coverage.append(check_question_coverage(q, entities_by_type))

    covered = sum(1 for c in coverage if c["covered"])
    uncovered = [c["question_id"] for c in coverage if not c["covered"]]

    # Property key inventory per entity type
    key_inventory: Dict[str, Dict[str, int]] = {}
    for etype, ents in entities_by_type.items():
        key_counts: Dict[str, int] = defaultdict(int)
        for ent in ents:
            for k in (ent["properties"] or {}).keys():
                key_counts[k] += 1
        if key_counts:
            key_inventory[etype] = dict(sorted(key_counts.items(), key=lambda x: -x[1]))

    report = {
        "tenant_id": tenant_id,
        "entity_type_counts": type_summary,
        "total_entities": sum(type_summary.values()),
        "failing_questions_total": len(FAILING_PROPERTY_QUESTIONS),
        "covered_by_properties": covered,
        "uncovered_questions": uncovered,
        "coverage_ratio": f"{covered}/{len(FAILING_PROPERTY_QUESTIONS)}",
        "question_coverage": coverage,
        "property_key_inventory": key_inventory,
    }

    session.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="M0 — Property Fact Inventory")
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    report = run_inventory(args.tenant_id)

    output = json.dumps(report, indent=2, default=str)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report written to {args.output}")
    else:
        print(output)

    print(f"\n=== Coverage: {report['coverage_ratio']} ===")
    if report["uncovered_questions"]:
        print(f"Uncovered: {', '.join(report['uncovered_questions'])}")


if __name__ == "__main__":
    main()
