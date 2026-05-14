"""Stage 3A — Property Plane hook.

Queries the property_facts table for scalar attribute answers (revenue,
budget, capacity, qubits, etc.). Inserted between the QA Verifier and
DocEv fallback in the answer path.

Key design decisions:
  - Property plane IS the primary evidence source for scalar attribute values.
    Unlike DocEv (which never overrides confident KG answers), this hook
    REPLACES KG answers for attribute questions when a matching property fact
    exists. This addresses Bucket E failures (confident-wrong KG answers).
  - No LLM call — direct template-based formatting from structured facts.
    Faster, deterministic, no hallucination risk.
  - Read-only: never writes to property_facts/entities/etc during query.
  - Tenant-scoped: every lookup is filtered by tenant_id.

answer_source: TRUSTED_PROPERTY | STAGING_PROPERTY
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from src.context_foundry.adapters.property_adapter import is_value_shaped_name

logger = logging.getLogger(__name__)

# Answer source constants
ANSWER_SOURCE_TRUSTED_PROPERTY = "TRUSTED_PROPERTY"
ANSWER_SOURCE_STAGING_PROPERTY = "STAGING_PROPERTY"


@dataclass
class PropertyResult:
    """Returned when the property plane finds a matching fact."""
    answer: str
    answer_source: str  # TRUSTED_PROPERTY or STAGING_PROPERTY
    attribute_category: str
    entity_name: str
    attribute_name: str
    attribute_value: str
    numeric_value: Optional[float]
    unit: Optional[str]
    period: Optional[str]
    fiscal_year: Optional[str]
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Query parameter extraction (no LLM)
# ---------------------------------------------------------------------------

# Reuse the attribute trigger detection from DocEv
from src.context_foundry.retrieval.document_evidence_fallback import (
    is_attribute_query,
)

# Entity name patterns commonly found in Nexus 100Q
_ENTITY_PATTERNS = [
    # "What is/was/are Nexus Industries' revenue" → "Nexus Industries"
    re.compile(r"(?:what (?:is|was|are|were)|what's)\s+(.+?)(?:'s|')\s+", re.IGNORECASE),
    # "revenue of Nexus Industries" → "Nexus Industries"
    re.compile(r"(?:revenue|budget|backlog|capacity|cost|value|headcount|market share|ebitda|margin)\s+(?:of|for)\s+(.+?)(?:\s+in\s+|\s*\?|$)", re.IGNORECASE),
    # "the <entity> <attribute>" → "<entity>"
    re.compile(r"(?:the|for)\s+(.+?)\s+(?:revenue|budget|backlog|capacity|facility|contract)", re.IGNORECASE),
]

# Attribute name extraction patterns
_ATTRIBUTE_PATTERNS: Dict[str, List[re.Pattern]] = {
    "revenue": [
        re.compile(r"\brevenue\b", re.IGNORECASE),
        re.compile(r"\btotal revenue\b", re.IGNORECASE),
        re.compile(r"\bannual revenue\b", re.IGNORECASE),
    ],
    "backlog": [
        re.compile(r"\bbacklog\b", re.IGNORECASE),
        re.compile(r"\border backlog\b", re.IGNORECASE),
    ],
    "budget": [
        re.compile(r"\bbudget\b", re.IGNORECASE),
    ],
    "ebitda": [
        re.compile(r"\bebitda\b", re.IGNORECASE),
    ],
    "ebitda_margin": [
        re.compile(r"\bebitda\s+margin\b", re.IGNORECASE),
    ],
    "margin": [
        re.compile(r"\bmargin\b", re.IGNORECASE),
    ],
    "headcount": [
        re.compile(r"\bheadcount\b", re.IGNORECASE),
        re.compile(r"\bemployees?\b", re.IGNORECASE),
        re.compile(r"\bhow many employees\b", re.IGNORECASE),
    ],
    "capacity": [
        re.compile(r"\bcapacity\b", re.IGNORECASE),
    ],
    "throughput": [
        re.compile(r"\bthroughput\b", re.IGNORECASE),
        re.compile(r"\bproduction rate\b", re.IGNORECASE),
    ],
    "qubits": [
        re.compile(r"\bqubits?\b", re.IGNORECASE),
    ],
    "energy_density": [
        re.compile(r"\benergy density\b", re.IGNORECASE),
    ],
    "contract_value": [
        re.compile(r"\bcontract value\b", re.IGNORECASE),
        re.compile(r"\bdeal value\b", re.IGNORECASE),
    ],
    "market_share": [
        re.compile(r"\bmarket share\b", re.IGNORECASE),
    ],
    "growth_rate": [
        re.compile(r"\bgrowth rate\b", re.IGNORECASE),
        re.compile(r"\brevenue growth\b", re.IGNORECASE),
    ],
    "rd_percentage": [
        re.compile(r"\br&d\b.*\bspend", re.IGNORECASE),
        re.compile(r"\br&d\b.*\bpercentage\b", re.IGNORECASE),
        re.compile(r"\br&d\b.*\binvestment\b", re.IGNORECASE),
        re.compile(r"\bresearch and development\b", re.IGNORECASE),
    ],
    "start_date": [
        re.compile(r"\bstart date\b", re.IGNORECASE),
    ],
    "end_date": [
        re.compile(r"\bend date\b", re.IGNORECASE),
        re.compile(r"\bcompletion date\b", re.IGNORECASE),
        re.compile(r"\btarget.*(?:date|completion)\b", re.IGNORECASE),
    ],
}

# Fiscal year extraction
_FISCAL_YEAR_PATTERN = re.compile(
    r"(?:FY|fiscal\s+year\s*|in\s+)(\d{4})", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Superlative / comparison / variance rejection (Fix 3)
# ---------------------------------------------------------------------------

_SUPERLATIVE_PATTERNS = [
    re.compile(r"\bwhich\b.*\b(?:highest|lowest|largest|smallest|biggest|most|least|top|best|worst)\b", re.IGNORECASE),
    re.compile(r"\b(?:highest|lowest|largest|smallest|biggest)\b.*\b(?:revenue|budget|backlog|capacity|headcount|contract|market share)\b", re.IGNORECASE),
    re.compile(r"\brank\b|\branking\b|\bcompare\b|\bcomparison\b", re.IGNORECASE),
    re.compile(r"\bvariance\b|\bdifference between\b|\bgap between\b", re.IGNORECASE),
    re.compile(r"\b(?:more|less|greater|fewer)\s+than\b", re.IGNORECASE),
    re.compile(r"\bvs\.?\b|\bversus\b|\bor\b.*\bwhich\b", re.IGNORECASE),
    re.compile(r"\bhow (?:much|many) (?:more|less|higher|lower)\b", re.IGNORECASE),
    re.compile(r"\b(?:total|combined|aggregate|sum)\b.*\b(?:across|of all|for all)\b", re.IGNORECASE),
]


def is_superlative_or_comparison(query: str) -> bool:
    """Return True if the query is a superlative, comparison, or variance question.

    These cannot be answered from a single property fact row.
    Examples:
        "Which project has the highest budget?" → True
        "What is the variance between Q3 and Q4 revenue?" → True
        "Boeing or Airbus — which has more revenue?" → True
        "What is Nexus Industries' revenue?" → False
    """
    for pat in _SUPERLATIVE_PATTERNS:
        if pat.search(query):
            return True
    return False


def extract_query_parameters(query: str, category: str) -> Dict[str, Optional[str]]:
    """Extract entity_name, attribute_name, and fiscal_year from a query.

    Uses regex/heuristic extraction — no LLM call.
    """
    params: Dict[str, Optional[str]] = {
        "entity_name": None,
        "attribute_name": None,
        "fiscal_year": None,
    }

    # Extract entity name
    for pat in _ENTITY_PATTERNS:
        m = pat.search(query)
        if m:
            name = m.group(1).strip()
            # Remove possessive suffix properly (not rstrip which strips chars)
            if name.endswith("'s"):
                name = name[:-2]
            elif name.endswith("'"):
                name = name[:-1]
            name = name.strip()
            if len(name) > 2 and name.lower() not in ("the", "what", "how", "total"):
                params["entity_name"] = name
                break

    # Extract attribute name — try most specific first
    # Check ebitda_margin before margin, etc.
    ordered_attrs = sorted(
        _ATTRIBUTE_PATTERNS.items(),
        key=lambda x: -len(x[0]),  # longer names first
    )
    for attr_name, patterns in ordered_attrs:
        for pat in patterns:
            if pat.search(query):
                params["attribute_name"] = attr_name
                break
        if params["attribute_name"]:
            break

    # Extract fiscal year
    fy_match = _FISCAL_YEAR_PATTERN.search(query)
    if fy_match:
        params["fiscal_year"] = fy_match.group(1)

    return params


# ---------------------------------------------------------------------------
# Property lookup (raw SQL, no ORM — matches DocEv pattern)
# ---------------------------------------------------------------------------

def _lookup_property_facts(
    session,
    tenant_id: str,
    attribute_name: str,
    *,
    entity_name: Optional[str] = None,
    fiscal_year: Optional[str] = None,
) -> list:
    """Direct SQL lookup in property_facts. Returns raw rows.

    Tries both TRUSTED and STAGING lifecycle states, preferring TRUSTED.
    """
    clauses = [
        "tenant_id = :tid",
        "LOWER(attribute_name) = LOWER(:attr)",
    ]
    params: Dict[str, Any] = {"tid": tenant_id, "attr": attribute_name}

    if entity_name:
        clauses.append("LOWER(entity_name) LIKE LOWER(:ename)")
        params["ename"] = f"%{entity_name}%"

    if fiscal_year:
        clauses.append("fiscal_year = :fy")
        params["fy"] = fiscal_year

    where = " AND ".join(clauses)
    sql = f"""
        SELECT id::text, entity_name, entity_type, lifecycle_state,
               attribute_name, attribute_value, numeric_value, unit,
               value_type, period, fiscal_year, confidence
        FROM property_facts
        WHERE {where}
        ORDER BY
            CASE lifecycle_state WHEN 'TRUSTED' THEN 0 ELSE 1 END,
            confidence DESC,
            entity_name ASC
        LIMIT 5
    """
    return session.execute(text(sql), params).fetchall()


def _try_broader_lookup(
    session,
    tenant_id: str,
    attribute_name: str,
    params: Dict[str, Optional[str]],
) -> list:
    """Progressively relax filters if the strict lookup returned nothing.

    Only relaxes fiscal_year. Never drops entity_name — returning a random
    entity's data is worse than returning nothing. If the query names an
    entity and we can't find it, we should fall through to KG/DocEv rather
    than answer with the wrong entity.
    """
    # Try without fiscal_year (but keep entity_name)
    if params.get("fiscal_year"):
        rows = _lookup_property_facts(
            session, tenant_id, attribute_name,
            entity_name=params.get("entity_name"),
        )
        if rows:
            return rows

    # If no entity was specified in the query, try attribute-only lookup
    if not params.get("entity_name"):
        rows = _lookup_property_facts(session, tenant_id, attribute_name)
        return rows

    # Entity was specified but not found — return empty rather than wrong entity
    return []


# ---------------------------------------------------------------------------
# Entity disambiguation (Fix 2)
# ---------------------------------------------------------------------------

def _disambiguate_entity(rows: list, query_entity: str) -> list:
    """Prefer rows whose entity_name closely matches the query entity.

    Matching tiers (highest to lowest):
      1. Case-insensitive exact match
      2. Query entity is a substring of the row entity_name (or vice versa),
         sorted by closeness (prefer shorter entity names that still contain
         the query entity, i.e. closest to exact match)
      3. All remaining rows (loose LIKE match from SQL)

    Returns the rows from the highest non-empty tier.
    """
    qe = query_entity.lower().strip()

    exact = [r for r in rows if r.entity_name.lower().strip() == qe]
    if exact:
        return exact

    substring = [
        r for r in rows
        if qe in r.entity_name.lower() or r.entity_name.lower() in qe
    ]
    if substring:
        # Sort by name length difference from query entity (closest first)
        substring.sort(key=lambda r: abs(len(r.entity_name) - len(query_entity)))
        return substring

    # Fallback: return all rows (already filtered by LIKE in SQL)
    return rows


# ---------------------------------------------------------------------------
# Answer formatting (template-based, no LLM)
# ---------------------------------------------------------------------------

_TEMPLATES = {
    "CURRENCY": "{entity}'s {attr} {period_clause}was {value}.",
    "PERCENTAGE": "{entity}'s {attr} {period_clause}was {value}.",
    "COUNT": "{entity} {period_clause}had {value} {attr}.",
    "SPEC": "The {attr} {entity_clause}{period_clause}is {value}.",
    "DATE": "The {attr} {entity_clause}{period_clause}is {value}.",
    "STATUS": "The {attr} {entity_clause}{period_clause}is {value}.",
    "DEFAULT": "{entity}'s {attr} {period_clause}is {value}.",
}


def format_property_answer(query: str, fact, params: Dict) -> str:
    """Format a property fact into a natural-language answer.

    Template-based — no LLM call. Deterministic.
    """
    entity = fact.entity_name
    attr = fact.attribute_name.replace("_", " ")
    value = fact.attribute_value
    period = fact.period or ""
    vtype = (fact.value_type or "DEFAULT").upper()

    period_clause = f"in {period} " if period else ""
    entity_clause = f"of {entity} " if entity else ""

    template = _TEMPLATES.get(vtype, _TEMPLATES["DEFAULT"])

    answer = template.format(
        entity=entity,
        attr=attr,
        value=value,
        period_clause=period_clause,
        entity_clause=entity_clause,
    )

    # Clean up double spaces
    answer = re.sub(r"\s+", " ", answer).strip()
    return answer


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def attempt_property_lookup(
    session,
    tenant_id: str,
    query: str,
    *,
    kg_answer: Optional[str] = None,
    kg_answer_source: Optional[str] = None,
) -> Optional[PropertyResult]:
    """Attempt to answer the query from property_facts.

    Returns PropertyResult if a matching fact is found, None otherwise.
    Unlike DocEv, this DOES override confident KG answers for attribute
    questions (addresses Bucket E failures).
    """
    # 1. Is this an attribute query?
    category = is_attribute_query(query)
    if not category:
        return None

    # 1b. Reject superlative/comparison/variance queries (Fix 3)
    if is_superlative_or_comparison(query):
        logger.debug(f"[PROP_PLANE] Rejected superlative/comparison query: {query[:60]}")
        return None

    # 2. Extract query parameters
    params = extract_query_parameters(query, category)
    attr_name = params.get("attribute_name")
    if not attr_name:
        return None

    # 3. Look up property facts
    rows = _lookup_property_facts(
        session, tenant_id, attr_name,
        entity_name=params.get("entity_name"),
        fiscal_year=params.get("fiscal_year"),
    )

    # Progressive relaxation if strict lookup failed
    if not rows:
        rows = _try_broader_lookup(session, tenant_id, attr_name, params)

    if not rows:
        return None

    # 3b. Filter out value-shaped entity names from results (Fix 1)
    rows = [r for r in rows if not is_value_shaped_name(r.entity_name)]
    if not rows:
        return None

    # 3c. Entity disambiguation (Fix 2): if the query names a specific entity,
    # prefer exact/close matches over loose LIKE hits
    query_entity = params.get("entity_name")
    if query_entity:
        rows = _disambiguate_entity(rows, query_entity)
    if not rows:
        return None

    # 4. Pick the best fact (first row — already sorted by lifecycle + confidence)
    best = rows[0]

    # 5. Format the answer
    answer = format_property_answer(query, best, params)

    # 6. Determine answer_source
    answer_source = (
        ANSWER_SOURCE_TRUSTED_PROPERTY
        if best.lifecycle_state == "TRUSTED"
        else ANSWER_SOURCE_STAGING_PROPERTY
    )

    logger.info(
        f"[PROP_PLANE] Hit: attr={attr_name} entity={best.entity_name} "
        f"value={best.attribute_value} source={answer_source}"
    )

    return PropertyResult(
        answer=answer,
        answer_source=answer_source,
        attribute_category=category,
        entity_name=best.entity_name,
        attribute_name=best.attribute_name,
        attribute_value=best.attribute_value,
        numeric_value=best.numeric_value,
        unit=best.unit,
        period=best.period,
        fiscal_year=best.fiscal_year,
        confidence=best.confidence,
    )


def apply_to_agent_result(
    agent_result: Dict[str, Any],
    *,
    session,
    tenant_id: str,
    query: str,
) -> Dict[str, Any]:
    """Orchestrator matching DocEv's apply_to_agent_result pattern.

    Mutates `agent_result` in place. Always sets property_plane_diagnostics.
    Returns the same dict for ergonomic chaining.
    """
    diagnostics: Dict[str, Any] = {
        "attempted": False,
        "hit": False,
        "attribute_name": None,
        "entity_name": None,
        "answer_source": None,
    }
    agent_result["property_plane_diagnostics"] = diagnostics

    try:
        result = attempt_property_lookup(
            session,
            tenant_id,
            query,
            kg_answer=agent_result.get("answer"),
            kg_answer_source=agent_result.get("answer_source"),
        )
    except Exception as e:
        logger.warning(f"[PROP_PLANE] Lookup failed: {e}")
        diagnostics["error"] = str(e)
        return agent_result

    diagnostics["attempted"] = True

    if result is None:
        return agent_result

    # Property plane hit — replace the answer
    diagnostics["hit"] = True
    diagnostics["attribute_name"] = result.attribute_name
    diagnostics["entity_name"] = result.entity_name
    diagnostics["answer_source"] = result.answer_source

    agent_result["answer"] = result.answer
    agent_result["answer_source"] = result.answer_source
    agent_result["property_evidence"] = result.to_dict()

    return agent_result
