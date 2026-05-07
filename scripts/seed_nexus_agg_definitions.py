"""
C.4.5: Seed aggregation definitions (CATs) for Nexus vault so superlative
queries like "Which division has the highest TRIR?" resolve to a CAT and
trigger AggregationService.handle_query() with proper grouping/aggregation.

Concepts seeded:
  - division (employee count, revenue, TRIR, headcount)
  - project  (budget, capex)
  - revenue, budget, employees, trir (as standalone synonyms)
"""

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_VAULT_ID = "176a4fb2-0bb4-4da3-9068-0e26268fca71"

DEFINITIONS = [
    {
        "concept_key": "division",
        "synonyms": ["divisions", "business unit", "business units", "segment", "segments", "department", "departments"],
        "candidates": [
            {
                "name": "Division by employee count",
                "description": "Compare divisions by employee count / headcount.",
                "intent_kinds": ["MAX", "MIN", "TOP_K", "GROUP_BY", "COUNT"],
                "target": {
                    "source": "ENTITY_TABLE",
                    "entity_type": "ORGANIZATION_UNIT",
                    "value_attr": "employee_count",
                },
                "aggregation": {"op": "MAX", "grouping_key": ["entity.name"], "value_expr": "(entity.attributes->>'employee_count')::numeric"},
                "filters": [],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.85,
                "disambiguation_hints": {"boost": ["employees", "headcount", "people", "staff"], "lower": ["revenue", "budget", "incident"]},
            },
            {
                "name": "Division by revenue",
                "description": "Compare divisions by revenue.",
                "intent_kinds": ["MAX", "MIN", "TOP_K", "GROUP_BY", "SUM"],
                "target": {
                    "source": "KG_RELATIONSHIP",
                    "relationship_type": "HAS_REVENUE",
                    "anchor_entity_type": "ORGANIZATION_UNIT",
                },
                "aggregation": {"op": "MAX", "grouping_key": ["source.name"], "value_expr": "(rel.attributes->>'value')::numeric"},
                "filters": [],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.85,
                "disambiguation_hints": {"boost": ["revenue", "sales", "income"], "lower": ["employees", "incident", "trir"]},
            },
            {
                "name": "Division by safety rate (TRIR)",
                "description": "Compare divisions by safety incident rate (TRIR).",
                "intent_kinds": ["MAX", "MIN", "TOP_K", "GROUP_BY"],
                "target": {
                    "source": "ENTITY_TABLE",
                    "entity_type": "METRIC",
                    "value_attr": "trir",
                },
                "aggregation": {"op": "MAX", "grouping_key": ["entity.name"], "value_expr": "(entity.attributes->>'trir')::numeric"},
                "filters": [{"sql": "entity.name ILIKE '%trir%' OR entity.attributes->>'metric_type' = 'TRIR'", "required": False}],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.80,
                "disambiguation_hints": {"boost": ["trir", "safety", "incident", "rate"], "lower": ["revenue", "budget", "employees"]},
            },
        ],
    },
    {
        "concept_key": "project",
        "synonyms": ["projects", "initiative", "initiatives", "program", "programs"],
        "candidates": [
            {
                "name": "Project by budget",
                "description": "Compare projects by budget.",
                "intent_kinds": ["MAX", "MIN", "TOP_K", "GROUP_BY", "SUM"],
                "target": {
                    "source": "KG_RELATIONSHIP",
                    "relationship_type": "HAS_BUDGET",
                    "anchor_entity_type": "PROJECT",
                },
                "aggregation": {"op": "MAX", "grouping_key": ["source.name"], "value_expr": "(rel.attributes->>'value')::numeric"},
                "filters": [],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.85,
                "disambiguation_hints": {"boost": ["budget", "cost", "capex", "investment"], "lower": ["revenue", "employees"]},
            },
        ],
    },
    {
        "concept_key": "trir",
        "synonyms": ["safety rate", "safety incident rate", "incident rate", "total recordable incident rate"],
        "candidates": [
            {
                "name": "TRIR by division",
                "description": "Total Recordable Incident Rate per division.",
                "intent_kinds": ["MAX", "MIN", "TOP_K", "GROUP_BY", "AVG"],
                "target": {"source": "ENTITY_TABLE", "entity_type": "METRIC"},
                "aggregation": {"op": "MAX", "grouping_key": ["entity.name"], "value_expr": "(entity.attributes->>'value')::numeric"},
                "filters": [{"sql": "entity.name ILIKE '%trir%' OR entity.name ILIKE '%incident rate%'", "required": False}],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.80,
                "disambiguation_hints": {"boost": ["trir", "safety", "incident"], "lower": []},
            }
        ],
    },
    {
        "concept_key": "budget",
        "synonyms": ["budgets", "capex", "capital expenditure", "spend", "spending"],
        "candidates": [
            {
                "name": "Budget by project",
                "description": "Project budgets in $ amount.",
                "intent_kinds": ["MAX", "MIN", "TOP_K", "GROUP_BY", "SUM"],
                "target": {"source": "KG_RELATIONSHIP", "relationship_type": "HAS_BUDGET", "anchor_entity_type": "PROJECT"},
                "aggregation": {"op": "MAX", "grouping_key": ["source.name"], "value_expr": "(rel.attributes->>'value')::numeric"},
                "filters": [],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.85,
                "disambiguation_hints": {"boost": ["budget", "capex", "cost"], "lower": ["revenue"]},
            }
        ],
    },
    {
        "concept_key": "revenue",
        "synonyms": ["revenues", "sales", "income", "turnover"],
        "candidates": [
            {
                "name": "Revenue by division",
                "description": "Revenue per business unit / division.",
                "intent_kinds": ["MAX", "MIN", "TOP_K", "GROUP_BY", "SUM"],
                "target": {"source": "KG_RELATIONSHIP", "relationship_type": "HAS_REVENUE", "anchor_entity_type": "ORGANIZATION_UNIT"},
                "aggregation": {"op": "MAX", "grouping_key": ["source.name"], "value_expr": "(rel.attributes->>'value')::numeric"},
                "filters": [],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.85,
                "disambiguation_hints": {"boost": ["revenue", "sales", "income"], "lower": []},
            }
        ],
    },
    {
        "concept_key": "employees",
        "synonyms": ["employee", "headcount", "head count", "staff", "workforce", "people"],
        "candidates": [
            {
                "name": "Employees by division",
                "description": "Employee headcount per division.",
                "intent_kinds": ["MAX", "MIN", "TOP_K", "GROUP_BY", "COUNT", "SUM"],
                "target": {"source": "ENTITY_TABLE", "entity_type": "ORGANIZATION_UNIT"},
                "aggregation": {"op": "MAX", "grouping_key": ["entity.name"], "value_expr": "(entity.attributes->>'employee_count')::numeric"},
                "filters": [],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.85,
                "disambiguation_hints": {"boost": ["employees", "headcount", "staff"], "lower": []},
            }
        ],
    },
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vault-id", default=DEFAULT_VAULT_ID)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("SET app.role = 'admin'")

    # Verify table exists
    cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='agg_definitions')")
    if not cur.fetchone()[0]:
        logger.error("agg_definitions table does not exist — aggregation framework not migrated")
        sys.exit(1)

    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_name='agg_definitions' ORDER BY ordinal_position""")
    cols = [r[0] for r in cur.fetchall()]
    logger.info(f"agg_definitions columns: {cols}")

    seeded = 0
    for d in DEFINITIONS:
        try:
            cur.execute(
                """INSERT INTO agg_definitions (tenant_id, concept_key, synonyms, candidates, status)
                   VALUES (%s::uuid, %s, %s, %s::jsonb, 'active')
                   ON CONFLICT (tenant_id, concept_key, version)
                   DO UPDATE SET candidates=EXCLUDED.candidates,
                                 synonyms=EXCLUDED.synonyms,
                                 updated_at=now()""",
                (args.vault_id, d["concept_key"], d["synonyms"], json.dumps(d["candidates"])),
            )
            logger.info(f"  + seeded: {d['concept_key']} ({len(d['candidates'])} candidates, {len(d['synonyms'])} synonyms)")
            seeded += 1
        except Exception as e:
            logger.error(f"  X failed {d['concept_key']}: {e}")
            conn.rollback()
            sys.exit(1)

    if args.dry_run:
        conn.rollback()
        logger.info(f"\n[DRY-RUN] would have seeded {seeded} definitions")
    else:
        conn.commit()
        logger.info(f"\n[DONE] Seeded {seeded} aggregation definitions for vault {args.vault_id}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
