"""
Aggregation Definitions Seed Data

Registers semantic contracts for domain concepts so the system knows
what "jobs", "incidents", "exceptions", etc. mean.

Run this after migration to populate agg_definitions table.

Usage:
    from aggregation.seed_definitions import seed_all_definitions
    seed_all_definitions(session, tenant_id)
"""

import json
import logging
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =============================================================================
# Domain-specific aggregation definitions
# =============================================================================

DEFINITIONS: List[Dict[str, Any]] = [
    # =========================================================================
    # EMPLOYMENT / JOBS (for "How many jobs has X had?")
    # =========================================================================
    {
        "concept_key": "job",
        "synonyms": ["jobs", "role", "roles", "position", "positions", "employment", "employments", "gig", "gigs"],
        "candidates": [
            {
                "name": "Distinct employment records by organization and start date",
                "description": "Counts unique employment positions. Same company at different times = multiple jobs.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT"],
                "target": {
                    "source": "KG_RELATIONSHIP",
                    "relationship_type": "WORKED_AT",
                    "anchor_entity_type": "Person",
                    "target_entity_type": "Organization"
                },
                "aggregation": {
                    "op": "COUNT_DISTINCT",
                    "grouping_key": ["rel.target_entity_id", "rel.attributes->>'start_date'"]
                },
                "filters": [
                    {"sql": "rel.attributes->>'status' != 'deleted'", "required": False}
                ],
                "time": {
                    "supported": True,
                    "default_mode": "valid_time",
                    "fields": {
                        "event_time": "rel.created_at",
                        "valid_time": "rel.attributes->>'start_date'"
                    }
                },
                "dedup_policy": "TEMPORAL_MERGE",
                "closure_policy": "AUTHORITATIVE",
                "confidence_baseline": 0.85,
                "disambiguation_hints": {
                    "boost": ["role", "position", "worked"],
                    "lower": ["company", "organization"]
                }
            },
            {
                "name": "Distinct companies worked at",
                "description": "Counts unique organizations, regardless of multiple stints.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT"],
                "target": {
                    "source": "KG_RELATIONSHIP",
                    "relationship_type": "WORKED_AT",
                    "anchor_entity_type": "Person",
                    "target_entity_type": "Organization"
                },
                "aggregation": {
                    "op": "COUNT_DISTINCT",
                    "grouping_key": ["rel.target_entity_id"]
                },
                "filters": [],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "AUTHORITATIVE",
                "confidence_baseline": 0.90,
                "disambiguation_hints": {
                    "boost": ["company", "companies", "organization", "organizations", "employer"],
                    "lower": ["role", "position", "title"]
                }
            }
        ]
    },
    
    # =========================================================================
    # INCIDENTS (IT Ops - "How many incidents last quarter?")
    # =========================================================================
    {
        "concept_key": "incident",
        "synonyms": ["incidents", "issue", "issues", "outage", "outages", "problem", "problems", "ticket", "tickets"],
        "candidates": [
            {
                "name": "IT incidents from incident table",
                "description": "Counts incidents from the authoritative incident tracking system.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT", "AVG", "SUM", "GROUP_BY", "TREND"],
                "target": {
                    "source": "ENTITY_TABLE",
                    "entity_type": "Incident"
                },
                "aggregation": {
                    "op": "COUNT",
                    "grouping_key": ["id"],
                    "value_expr": "EXTRACT(EPOCH FROM (resolved_at - created_at))/3600"
                },
                "filters": [
                    {"path": "status", "op": "!=", "value": "deleted", "required": False}
                ],
                "time": {
                    "supported": True,
                    "default_mode": "event_time",
                    "fields": {
                        "event_time": "created_at",
                        "valid_time": "created_at",
                        "resolved_time": "resolved_at"
                    }
                },
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "AUTHORITATIVE",
                "confidence_baseline": 0.95,
                "disambiguation_hints": {
                    "boost": ["incident", "outage", "severity", "resolved", "MTTR"],
                    "lower": []
                }
            }
        ]
    },
    
    # =========================================================================
    # EXCEPTIONS / APPROVALS (DTL - "How many exceptions granted?")
    # =========================================================================
    {
        "concept_key": "exception",
        "synonyms": ["exceptions", "exemption", "exemptions", "waiver", "waivers", "override", "overrides"],
        "candidates": [
            {
                "name": "Policy exceptions from DTL",
                "description": "Counts exception decisions granted via governance process.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT", "GROUP_BY", "TREND"],
                "target": {
                    "source": "DTL_DECISION",
                    "entity_type": "exception"
                },
                "aggregation": {
                    "op": "COUNT",
                    "grouping_key": ["decision_id"]
                },
                "filters": [
                    {"path": "outcome", "op": "=", "value": "granted", "required": True}
                ],
                "time": {
                    "supported": True,
                    "default_mode": "event_time",
                    "fields": {
                        "event_time": "created_at",
                        "valid_time": "valid_from"
                    }
                },
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "AUTHORITATIVE",
                "confidence_baseline": 0.95,
                "disambiguation_hints": {
                    "boost": ["granted", "approved", "policy", "waiver"],
                    "lower": ["denied", "rejected"]
                }
            }
        ]
    },
    {
        "concept_key": "approval",
        "synonyms": ["approvals", "approved", "sign-off", "sign-offs", "authorization", "authorizations"],
        "candidates": [
            {
                "name": "Approvals from DTL",
                "description": "Counts approval decisions from governance process.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT", "GROUP_BY", "TREND"],
                "target": {
                    "source": "DTL_DECISION",
                    "entity_type": "approval"
                },
                "aggregation": {
                    "op": "COUNT",
                    "grouping_key": ["decision_id"]
                },
                "filters": [
                    {"path": "outcome", "op": "=", "value": "approved", "required": True}
                ],
                "time": {
                    "supported": True,
                    "default_mode": "event_time",
                    "fields": {"event_time": "created_at"}
                },
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "AUTHORITATIVE",
                "confidence_baseline": 0.95,
                "disambiguation_hints": {
                    "boost": ["approved", "authorized", "signed off"],
                    "lower": ["pending", "rejected"]
                }
            }
        ]
    },
    
    # =========================================================================
    # VENDORS (Procurement - "How many vendors in each category?")
    # =========================================================================
    {
        "concept_key": "vendor",
        "synonyms": ["vendors", "supplier", "suppliers", "contractor", "contractors", "provider", "providers"],
        "candidates": [
            {
                "name": "Active vendors",
                "description": "Counts distinct vendor organizations.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT", "GROUP_BY"],
                "target": {
                    "source": "ENTITY_TABLE",
                    "entity_type": "Vendor"
                },
                "aggregation": {
                    "op": "COUNT_DISTINCT",
                    "grouping_key": ["id"]
                },
                "filters": [
                    {"path": "status", "op": "=", "value": "active", "required": False}
                ],
                "time": {
                    "supported": True,
                    "default_mode": "valid_time",
                    "fields": {"valid_time": "contract_start_date"}
                },
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "AUTHORITATIVE",
                "confidence_baseline": 0.90,
                "disambiguation_hints": {
                    "boost": ["vendor", "supplier", "category", "contract"],
                    "lower": []
                }
            }
        ]
    },
    
    # =========================================================================
    # SYSTEMS / SERVICES (Dependencies - "How many systems depend on X?")
    # =========================================================================
    {
        "concept_key": "system",
        "synonyms": ["systems", "service", "services", "application", "applications", "app", "apps", "component", "components"],
        "candidates": [
            {
                "name": "Systems with dependency relationship",
                "description": "Counts systems via DEPENDS_ON relationship traversal.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT", "GRAPH_COUNT"],
                "target": {
                    "source": "KG_RELATIONSHIP",
                    "relationship_type": "DEPENDS_ON",
                    "anchor_entity_type": "Service",
                    "target_entity_type": "Service"
                },
                "aggregation": {
                    "op": "COUNT_DISTINCT",
                    "grouping_key": ["target_entity_id"]
                },
                "filters": [],
                "graph": {
                    "direction": "incoming",
                    "max_hops": 3,
                    "dedup_nodes": True
                },
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.80,
                "disambiguation_hints": {
                    "boost": ["depend", "dependency", "downstream", "upstream", "impact"],
                    "lower": []
                }
            }
        ]
    },
    
    # =========================================================================
    # DOCUMENTS MENTIONING (Provenance - "How many docs mention X?")
    # =========================================================================
    {
        "concept_key": "document",
        "synonyms": ["documents", "doc", "docs", "file", "files", "report", "reports", "page", "pages"],
        "candidates": [
            {
                "name": "Documents mentioning entity (from index)",
                "description": "Counts documents via doc_entity_mentions index. EXACT only if index populated.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT", "PROVENANCE_COUNT"],
                "target": {
                    "source": "DOCUMENT_MENTION",
                    "entity_type": "Document"
                },
                "aggregation": {
                    "op": "COUNT_DISTINCT",
                    "grouping_key": ["doc_id"]
                },
                "filters": [],
                "time": {
                    "supported": True,
                    "default_mode": "event_time",
                    "fields": {"event_time": "first_seen_at"}
                },
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "AUTHORITATIVE",
                "confidence_baseline": 0.95,
                "disambiguation_hints": {
                    "boost": ["mention", "reference", "appear", "contain"],
                    "lower": []
                }
            }
        ]
    },
    
    # =========================================================================
    # PORTFOLIO COMPANIES (ADQ specific)
    # =========================================================================
    {
        "concept_key": "portfolio_company",
        "synonyms": ["portfolio companies", "portco", "portcos", "subsidiary", "subsidiaries", "holding", "holdings"],
        "candidates": [
            {
                "name": "Portfolio companies",
                "description": "Counts companies in ADQ portfolio.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT", "GROUP_BY"],
                "target": {
                    "source": "ENTITY_TABLE",
                    "entity_type": "PortfolioCompany"
                },
                "aggregation": {
                    "op": "COUNT_DISTINCT",
                    "grouping_key": ["id"]
                },
                "filters": [
                    {"path": "status", "op": "=", "value": "active", "required": False}
                ],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "AUTHORITATIVE",
                "confidence_baseline": 0.95,
                "disambiguation_hints": {
                    "boost": ["portfolio", "sector", "holding", "investment"],
                    "lower": []
                }
            }
        ]
    },
    
    # =========================================================================
    # PROJECTS
    # =========================================================================
    {
        "concept_key": "project",
        "synonyms": ["projects", "initiative", "initiatives", "program", "programs", "workstream", "workstreams"],
        "candidates": [
            {
                "name": "Active projects",
                "description": "Counts distinct projects.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT", "GROUP_BY"],
                "target": {
                    "source": "ENTITY_TABLE",
                    "entity_type": "Project"
                },
                "aggregation": {
                    "op": "COUNT_DISTINCT",
                    "grouping_key": ["id"]
                },
                "filters": [],
                "time": {
                    "supported": True,
                    "default_mode": "valid_time",
                    "fields": {
                        "event_time": "created_at",
                        "valid_time": "start_date"
                    }
                },
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.85,
                "disambiguation_hints": {
                    "boost": ["project", "initiative", "status", "milestone"],
                    "lower": []
                }
            }
        ]
    },
    
    # =========================================================================
    # PEOPLE / CONTRIBUTORS
    # =========================================================================
    {
        "concept_key": "person",
        "synonyms": ["people", "contributor", "contributors", "employee", "employees", "team member", "team members", "staff"],
        "candidates": [
            {
                "name": "People/contributors",
                "description": "Counts distinct people.",
                "intent_kinds": ["COUNT", "COUNT_DISTINCT", "GROUP_BY"],
                "target": {
                    "source": "ENTITY_TABLE",
                    "entity_type": "Person"
                },
                "aggregation": {
                    "op": "COUNT_DISTINCT",
                    "grouping_key": ["id"]
                },
                "filters": [],
                "dedup_policy": "CANONICAL_ID",
                "closure_policy": "PARTIAL",
                "confidence_baseline": 0.80,
                "disambiguation_hints": {
                    "boost": ["person", "contributor", "team", "assigned"],
                    "lower": []
                }
            }
        ]
    },
]


# =============================================================================
# Seeding functions
# =============================================================================

def seed_definition(
    session: Session,
    tenant_id: UUID,
    definition: Dict[str, Any],
) -> bool:
    """
    Seed a single aggregation definition.
    
    Upserts to avoid duplicates on re-run.
    """
    try:
        session.execute(
            text("""
                INSERT INTO agg_definitions 
                    (tenant_id, concept_key, synonyms, candidates, status)
                VALUES 
                    (:tenant_id, :concept_key, :synonyms, :candidates, 'active')
                ON CONFLICT (tenant_id, concept_key, version)
                DO UPDATE SET
                    synonyms = :synonyms,
                    candidates = :candidates,
                    updated_at = now()
            """),
            {
                "tenant_id": str(tenant_id),
                "concept_key": definition["concept_key"],
                "synonyms": definition["synonyms"],
                "candidates": json.dumps(definition["candidates"]),
            }
        )
        return True
    except Exception as e:
        logger.error(f"Failed to seed '{definition['concept_key']}': {e}")
        return False


def seed_all_definitions(
    session: Session,
    tenant_id: UUID,
    definitions: List[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """
    Seed all aggregation definitions for a tenant.
    
    Args:
        session: SQLAlchemy session
        tenant_id: Tenant UUID
        definitions: Optional custom definitions (uses DEFINITIONS if None)
        
    Returns:
        Stats dict: {seeded, failed}
    """
    defs = definitions or DEFINITIONS
    stats = {"seeded": 0, "failed": 0}
    
    for definition in defs:
        if seed_definition(session, tenant_id, definition):
            stats["seeded"] += 1
            logger.info(f"Seeded: {definition['concept_key']}")
        else:
            stats["failed"] += 1
    
    logger.info(f"Seed complete: {stats}")
    return stats


def list_definitions(session: Session, tenant_id: UUID) -> List[Dict[str, Any]]:
    """List all registered definitions for a tenant."""
    result = session.execute(
        text("""
            SELECT concept_key, synonyms, candidates, status, updated_at
            FROM agg_definitions
            WHERE tenant_id = :tenant_id
            ORDER BY concept_key
        """),
        {"tenant_id": str(tenant_id)}
    )
    
    return [
        {
            "concept_key": row.concept_key,
            "synonyms": row.synonyms,
            "candidates": row.candidates,
            "status": row.status,
            "updated_at": row.updated_at,
        }
        for row in result.fetchall()
    ]


# =============================================================================
# CLI helper
# =============================================================================

if __name__ == "__main__":
    """
    Run directly to seed definitions:
    
        python -m aggregation.seed_definitions --tenant-id <UUID>
    """
    import argparse
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    parser = argparse.ArgumentParser(description="Seed aggregation definitions")
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    parser.add_argument("--db-url", default=os.environ.get("DATABASE_URL"), help="Database URL")
    args = parser.parse_args()
    
    engine = create_engine(args.db_url)
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        # Set tenant context for RLS
        session.execute(text(f"SET app.current_tenant = '{args.tenant_id}'"))
        
        stats = seed_all_definitions(session, UUID(args.tenant_id))
        print(f"Done: {stats}")
        
        session.commit()
