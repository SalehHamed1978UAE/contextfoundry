"""Property Plane — structured fact lookup for scalar attribute answers.

Queries the property_facts table for scalar attribute answers (revenue,
budget, capacity, qubits, etc.). Inserted between the QA Verifier and
DocEv fallback in the answer path.

Architecture:
  1. LLM-based query parsing (gpt-4o-mini, temperature 0): extracts entity_name,
     attribute_name, and fiscal_year from the user's question. Handles any
     phrasing — no brittle regex patterns.
  2. SQL lookup in property_facts: deterministic, tenant-scoped.
  3. Template-based answer formatting: no hallucination risk.
  4. Override guard: only replaces KG answers when PP has a confident,
     entity-matched result.

answer_source: TRUSTED_PROPERTY | STAGING_PROPERTY
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Set

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
# Query parameter extraction (LLM-based)
# ---------------------------------------------------------------------------

# Reuse the attribute trigger detection from DocEv (cheap regex gate —
# if the question isn't about an attribute at all, skip the LLM call)
from src.context_foundry.retrieval.document_evidence_fallback import (
    is_attribute_query,
)

# LLM prompt for structured query parsing
_PARSE_SYSTEM_PROMPT = """\
You are a query parser for a structured facts database. Given a user question,
extract these fields as JSON:

- "entity_name": The specific named entity being asked about (company, project,
  facility, product, person, division, etc.). Use the exact name from the question.
  If no specific entity is named, set to null.
- "attribute_name": The property/metric being asked about, in snake_case
  (e.g. "revenue", "headcount", "budget", "capacity", "energy_density",
  "founded_year", "contract_value", "operating_margin", "backlog").
  If no clear attribute, set to null.
- "fiscal_year": A 4-digit year if mentioned (e.g. "2025" from "FY2025").
  Set to null if not mentioned.
- "is_comparison": true if the question compares multiple entities or asks
  for rankings/superlatives (highest, lowest, which has more, etc.).
  These cannot be answered from a single fact.

Return ONLY a JSON object, no other text.

Examples:
- "What was Nexus Industries' revenue in FY2025?"
  → {"entity_name": "Nexus Industries", "attribute_name": "revenue", "fiscal_year": "2025", "is_comparison": false}
- "How many employees does Nexus Industries have?"
  → {"entity_name": "Nexus Industries", "attribute_name": "headcount", "fiscal_year": null, "is_comparison": false}
- "What is the total company backlog?"
  → {"entity_name": "Nexus Industries", "attribute_name": "backlog", "fiscal_year": null, "is_comparison": false}
- "Which division has the highest revenue?"
  → {"entity_name": null, "attribute_name": "revenue", "fiscal_year": null, "is_comparison": true}
- "When was Nexus Industries founded?"
  → {"entity_name": "Nexus Industries", "attribute_name": "founded_year", "fiscal_year": null, "is_comparison": false}
- "What is the budget for Project Quantum Shield?"
  → {"entity_name": "Quantum Shield", "attribute_name": "budget", "fiscal_year": null, "is_comparison": false}"""


def _get_openai_client():
    """Initialize OpenAI client (same pattern as graph_builder.py)."""
    try:
        from openai import OpenAI
    except ImportError:
        return None

    ai_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
    ai_base = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    fallback_key = os.environ.get("OPENAI_API_KEY")

    if ai_key and ai_base:
        return OpenAI(api_key=ai_key, base_url=ai_base)
    elif ai_key:
        return OpenAI(api_key=ai_key)
    elif fallback_key:
        return OpenAI(api_key=fallback_key)
    return None


# Module-level client (lazy init)
_client = None


def _ensure_client():
    global _client
    if _client is None:
        _client = _get_openai_client()
    return _client


def _strip_json_fences(content: str) -> str:
    """Strip markdown JSON fences from LLM output."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r'^```(?:json)?\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
    return content


def extract_query_parameters(query: str, category: str) -> Dict[str, Optional[str]]:
    """Extract entity_name, attribute_name, and fiscal_year from a query.

    Uses gpt-4o-mini at temperature 0 for reliable structured extraction.
    Falls back to basic regex if LLM is unavailable.
    """
    params: Dict[str, Optional[str]] = {
        "entity_name": None,
        "attribute_name": None,
        "fiscal_year": None,
        "is_comparison": False,
    }

    client = _ensure_client()
    if not client:
        logger.warning("[PROP_PLANE] No OpenAI client, falling back to regex extraction")
        return _regex_fallback_extract(query, category)

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _PARSE_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=200,
        )
        content = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning(f"[PROP_PLANE] LLM parse failed: {e}, falling back to regex")
        return _regex_fallback_extract(query, category)

    content = _strip_json_fences(content)

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"[PROP_PLANE] JSON parse failed, falling back to regex")
        return _regex_fallback_extract(query, category)

    params["entity_name"] = data.get("entity_name") or None
    params["attribute_name"] = data.get("attribute_name") or None
    params["fiscal_year"] = str(data["fiscal_year"]) if data.get("fiscal_year") else None
    params["is_comparison"] = bool(data.get("is_comparison", False))

    return params


def _regex_fallback_extract(query: str, category: str) -> Dict[str, Optional[str]]:
    """Minimal regex fallback when LLM is unavailable (e.g. tests, no API key)."""
    params: Dict[str, Optional[str]] = {
        "entity_name": None,
        "attribute_name": None,
        "fiscal_year": None,
        "is_comparison": False,
    }

    # Basic possessive extraction: "What is X's Y"
    m = re.search(r"(?:what (?:is|was|are|were)|what's)\s+(.+?)(?:'s|')\s+", query, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        if len(name) > 2:
            params["entity_name"] = name

    # Basic attribute extraction
    attr_map = {
        "revenue": r"\brevenue\b",
        "headcount": r"\b(?:employees?|headcount|workforce)\b",
        "budget": r"\bbudget\b",
        "backlog": r"\bbacklog\b",
        "capacity": r"\bcapacity\b",
        "ebitda_margin": r"\bebitda\s+margin\b",
        "ebitda": r"\bebitda\b",
        "operating_margin": r"\boperating\s+margin\b",
        "margin": r"\bmargin\b",
        "qubits": r"\bqubits?\b",
        "contract_value": r"\bcontract\s+value\b",
        "energy_density": r"\benergy\s+density\b",
        "production_rate": r"\bproduction\s+rate\b",
        "founded_year": r"\bfounded\b",
    }
    for attr_name, pattern in attr_map.items():
        if re.search(pattern, query, re.IGNORECASE):
            params["attribute_name"] = attr_name
            break

    # Fiscal year
    fy_match = re.search(r"(?:FY|fiscal\s+year\s*|in\s+)(\d{4})", query, re.IGNORECASE)
    if fy_match:
        params["fiscal_year"] = fy_match.group(1)

    return params


# ---------------------------------------------------------------------------
# Property lookup (raw SQL, no ORM)
# ---------------------------------------------------------------------------

_FACT_ORDER_BY = """
        ORDER BY
            CASE lifecycle_state WHEN 'TRUSTED' THEN 0 ELSE 1 END,
            CASE entity_type WHEN 'ORGANIZATION' THEN 0 ELSE 1 END,
            confidence DESC,
            numeric_value DESC NULLS LAST,
            entity_name ASC
        LIMIT 5
"""


def _lookup_property_facts(
    session,
    tenant_id: str,
    attribute_name: str,
    *,
    entity_name: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    use_like: bool = False,
) -> list:
    """Direct SQL lookup in property_facts. Returns raw rows.

    Exact matching by default. Set use_like=True for broader LIKE matching.
    Prefers TRUSTED lifecycle, ORGANIZATION entity type, and larger values.
    """
    clauses = ["tenant_id = :tid"]
    params: Dict[str, Any] = {"tid": tenant_id}

    if use_like:
        clauses.append("LOWER(attribute_name) LIKE LOWER(:attr)")
        params["attr"] = f"%{attribute_name}%"
    else:
        clauses.append("LOWER(attribute_name) = LOWER(:attr)")
        params["attr"] = attribute_name

    if entity_name:
        if use_like:
            clauses.append("LOWER(entity_name) LIKE LOWER(:ename)")
            params["ename"] = f"%{entity_name}%"
        else:
            clauses.append("LOWER(entity_name) = LOWER(:ename)")
            params["ename"] = entity_name
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
        {_FACT_ORDER_BY}
    """
    return session.execute(text(sql), params).fetchall()


def _try_broader_lookup(
    session,
    tenant_id: str,
    attribute_name: str,
    params: Dict[str, Optional[str]],
) -> list:
    """Progressively relax filters if the exact lookup returned nothing.

    Relaxation order:
      1. Exact attr + exact entity, drop fiscal_year
      2. LIKE attr + exact entity (+ fiscal_year if present)
      3. LIKE attr + exact entity, drop fiscal_year
      4. LIKE attr + LIKE entity (+ fiscal_year if present)
      5. LIKE attr + LIKE entity, drop fiscal_year
    Never drops entity_name entirely — returning a random entity's data is
    worse than returning nothing.
    """
    entity_name = params.get("entity_name")
    fiscal_year = params.get("fiscal_year")

    # Step 1: exact attr + exact entity, drop fiscal_year
    if fiscal_year:
        rows = _lookup_property_facts(
            session, tenant_id, attribute_name,
            entity_name=entity_name,
        )
        if rows:
            return rows

    # Step 2: LIKE attr + exact entity (with fiscal_year)
    rows = _lookup_property_facts(
        session, tenant_id, attribute_name,
        entity_name=entity_name,
        fiscal_year=fiscal_year,
        use_like=True,
    )
    if rows:
        return rows

    # Step 3: LIKE attr + exact entity, drop fiscal_year
    if fiscal_year:
        rows = _lookup_property_facts(
            session, tenant_id, attribute_name,
            entity_name=entity_name,
            use_like=True,
        )
        if rows:
            return rows

    # If no entity was specified, try attribute-only (LIKE)
    if not entity_name:
        rows = _lookup_property_facts(
            session, tenant_id, attribute_name, use_like=True,
        )
        return rows

    # Entity was specified but not found — return empty rather than wrong entity
    return []


# ---------------------------------------------------------------------------
# Entity disambiguation (hierarchy-aware)
# ---------------------------------------------------------------------------

# Relationship types that form parent-child hierarchies.
# Convention: source_id = child, target_id = parent (MANY_TO_ONE).
_HIERARCHY_REL_TYPES = ("DIVISION_OF", "SUBSIDIARY_OF", "PART_OF")

# Attribute names that correlate with specific entity types.
# Used to prefer the right entity when multiple candidates match.
_ATTR_TYPE_AFFINITY: Dict[str, List[str]] = {
    "revenue": ["ORGANIZATION", "BUSINESS_UNIT"],
    "budget": ["ORGANIZATION", "PROJECT", "BUSINESS_UNIT"],
    "headcount": ["ORGANIZATION", "BUSINESS_UNIT"],
    "employees": ["ORGANIZATION", "BUSINESS_UNIT"],
    "operating_margin": ["ORGANIZATION", "BUSINESS_UNIT"],
    "ebitda": ["ORGANIZATION", "BUSINESS_UNIT"],
    "ebitda_margin": ["ORGANIZATION", "BUSINESS_UNIT"],
    "backlog": ["ORGANIZATION", "BUSINESS_UNIT"],
    "contract_value": ["PROJECT", "CUSTOMER"],
    "capacity": ["FACILITY", "PRODUCT"],
    "production_rate": ["FACILITY"],
    "qubits": ["PRODUCT", "TECHNOLOGY"],
    "endurance": ["PRODUCT"],
    "energy_density": ["PRODUCT", "TECHNOLOGY"],
    "founded_year": ["ORGANIZATION"],
    "certification_status": ["ORGANIZATION", "PRODUCT", "SERVICE"],
}


def _disambiguate_entity(
    rows: list,
    query_entity: str,
    session=None,
    tenant_id: Optional[str] = None,
    attribute_name: Optional[str] = None,
) -> list:
    """Prefer rows whose entity best matches the query using name, hierarchy, and type.

    Disambiguation signals (highest to lowest priority):
      1. Exact name match
      2. Hierarchy position: root/parent entities preferred for unqualified names
      3. Entity type affinity with the attribute being asked about
      4. Name closeness (substring distance)

    This works for any hierarchical domain: conglomerate divisions, geographic
    entities, organizational units, product families, etc.
    """
    if not rows:
        return rows

    qe = query_entity.lower().strip()

    # --- Tier 1: Exact name match always wins ---
    exact = [r for r in rows if r.entity_name.lower().strip() == qe]
    if exact:
        return exact

    # If we only have one candidate, no disambiguation needed
    if len(rows) == 1:
        return rows

    # --- Tier 2: Graph-aware scoring ---
    # Look up hierarchy info for each candidate entity
    hierarchy_info = {}
    if session and tenant_id:
        hierarchy_info = _get_hierarchy_info(
            session, tenant_id,
            [r.entity_name for r in rows],
        )

    # Determine preferred entity types from attribute
    preferred_types: Set[str] = set()
    if attribute_name:
        attr_key = attribute_name.lower().replace(" ", "_")
        preferred_types = set(_ATTR_TYPE_AFFINITY.get(attr_key, []))

    scored = []
    for r in rows:
        rn = r.entity_name.lower().strip()
        score = 0.0

        # Name similarity
        if qe in rn:
            # Query is a prefix/substring of entity name
            score += 0.5 - (len(rn) - len(qe)) * 0.01
        elif rn in qe:
            score += 0.4

        # Hierarchy bonus
        info = hierarchy_info.get(r.entity_name, {})
        if info.get("is_root"):
            # Root entities (have children, no parent) preferred for short names
            score += 0.3
        elif info.get("parent_name"):
            # Child entities — only prefer if query specifically names them
            if rn == qe:
                score += 0.2  # exact child match
            else:
                score -= 0.1  # penalize non-exact child matches

        # Entity type affinity with the attribute
        if preferred_types and hasattr(r, "entity_type"):
            if r.entity_type in preferred_types:
                score += 0.2

        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)

    if scored:
        best_score = scored[0][0]
        # Return all candidates within 0.05 of the best (near-ties)
        return [r for s, r in scored if s >= best_score - 0.05]

    return rows


def _get_hierarchy_info(
    session,
    tenant_id: str,
    entity_names: List[str],
) -> Dict[str, Dict[str, Any]]:
    """Look up hierarchy position for entities using the relationships table.

    Queries DIVISION_OF, SUBSIDIARY_OF, PART_OF edges to determine:
    - Whether an entity is a root (has children, no parent)
    - What its parent entity is (if any)
    - How many children it has

    Returns: {entity_name: {"parent_name": ..., "is_root": bool, "child_count": int}}
    """
    if not entity_names:
        return {}

    # Build LOWER(e.name) IN (...) clause
    placeholders = ", ".join(f":n{i}" for i in range(len(entity_names)))
    params: Dict[str, Any] = {"tid": tenant_id}
    for i, name in enumerate(entity_names):
        params[f"n{i}"] = name.lower()

    rel_types = ", ".join(f"'{rt}'" for rt in _HIERARCHY_REL_TYPES)

    # Query 1: Find parents (entity is a child → source in relationship)
    parent_sql = f"""
        SELECT e_child.name AS child_name,
               e_parent.name AS parent_name
        FROM relationships r
        JOIN entities e_child ON e_child.id = r.source_id AND e_child.tenant_id = r.tenant_id
        JOIN entities e_parent ON e_parent.id = r.target_id AND e_parent.tenant_id = r.tenant_id
        WHERE r.tenant_id = :tid
          AND LOWER(e_child.name) IN ({placeholders})
          AND r.relationship_type IN ({rel_types})
          AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
    """
    parent_rows = session.execute(text(parent_sql), params).fetchall()
    parents = {r.child_name: r.parent_name for r in parent_rows}

    # Query 2: Count children (entity is a parent → target in relationship)
    child_sql = f"""
        SELECT e_parent.name AS parent_name,
               COUNT(*) AS child_count
        FROM relationships r
        JOIN entities e_parent ON e_parent.id = r.target_id AND e_parent.tenant_id = r.tenant_id
        WHERE r.tenant_id = :tid
          AND LOWER(e_parent.name) IN ({placeholders})
          AND r.relationship_type IN ({rel_types})
          AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
        GROUP BY e_parent.name
    """
    child_rows = session.execute(text(child_sql), params).fetchall()
    child_counts = {r.parent_name: r.child_count for r in child_rows}

    result = {}
    for name in entity_names:
        parent_name = parents.get(name)
        cc = child_counts.get(name, 0)
        result[name] = {
            "parent_name": parent_name,
            "child_count": cc,
            "is_root": (cc > 0 and parent_name is None),
        }
    return result


# ---------------------------------------------------------------------------
# Entity resolution via aliases + hierarchy
# ---------------------------------------------------------------------------

def _resolve_entity_via_aliases(
    session,
    tenant_id: str,
    entity_name: str,
    attribute_name: Optional[str] = None,
) -> Optional[str]:
    """Resolve an entity name using aliases and graph hierarchy.

    When multiple entities match, uses hierarchy position and attribute-type
    affinity to pick the right one. A short name like "Nexus" resolves to
    the parent company if it has DIVISION_OF children, not to "Nexus Digital".

    Works for any hierarchical domain — conglomerates, geography, org charts,
    product families, etc.
    """
    sql = """
        SELECT DISTINCT e.name, e.entity_type
        FROM entities e
        LEFT JOIN entity_aliases ea ON ea.entity_id = e.id AND ea.tenant_id = e.tenant_id
        WHERE e.tenant_id = :tid
          AND e.lifecycle_state IN ('TRUSTED', 'STAGING')
          AND (LOWER(e.name) LIKE LOWER(:pat)
               OR LOWER(ea.alias) LIKE LOWER(:pat))
        ORDER BY
            CASE WHEN LOWER(e.name) = LOWER(:exact) THEN 0
                 WHEN LOWER(e.name) LIKE LOWER(:prefix) THEN 1
                 ELSE 2
            END,
            e.name ASC
        LIMIT 10
    """
    rows = session.execute(text(sql), {
        "tid": tenant_id,
        "pat": f"%{entity_name}%",
        "exact": entity_name,
        "prefix": f"{entity_name}%",
    }).fetchall()

    if not rows:
        return None

    # Single match — no disambiguation needed
    if len(rows) == 1:
        return rows[0].name

    # Multiple matches — use hierarchy to pick the best one
    hierarchy_info = _get_hierarchy_info(
        session, tenant_id, [r.name for r in rows],
    )

    # Determine preferred entity types from attribute
    preferred_types: Set[str] = set()
    if attribute_name:
        attr_key = attribute_name.lower().replace(" ", "_")
        preferred_types = set(_ATTR_TYPE_AFFINITY.get(attr_key, []))

    en_lower = entity_name.lower().strip()
    best_name = rows[0].name
    best_score = -1.0

    for r in rows:
        score = 0.0
        rn_lower = r.name.lower().strip()
        info = hierarchy_info.get(r.name, {})

        # Name match quality
        if rn_lower == en_lower:
            score += 1.0
        elif rn_lower.startswith(en_lower):
            score += 0.7 - (len(rn_lower) - len(en_lower)) * 0.01
        elif en_lower in rn_lower:
            score += 0.4
        else:
            score += 0.2

        # Hierarchy: root entities preferred for short/ambiguous names
        if info.get("is_root"):
            score += 0.3
        elif info.get("parent_name"):
            if rn_lower != en_lower:
                score -= 0.1  # penalize non-exact child

        # Attribute-type affinity
        if preferred_types and r.entity_type in preferred_types:
            score += 0.2

        if score > best_score:
            best_score = score
            best_name = r.name

    logger.info(
        f"[PROP_PLANE] Entity resolution: '{entity_name}' → '{best_name}' "
        f"(from {len(rows)} candidates, score={best_score:.2f})"
    )
    return best_name


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
# Superlative / comparison rejection
# ---------------------------------------------------------------------------

def is_superlative_or_comparison(query: str) -> bool:
    """Quick regex check for obvious superlative/comparison questions.

    The LLM also detects these via is_comparison, but this catches them
    before wasting an LLM call.
    """
    patterns = [
        r"\bwhich\b.*\b(?:highest|lowest|largest|smallest|biggest|most|least|more|fewer|top|best|worst)\b",
        r"\b(?:highest|lowest|largest|smallest|biggest)\b",
        r"\brank\b|\branking\b",
        r"\bhow (?:much|many) (?:more|less|higher|lower)\b",
        r"\bvs\b|\bversus\b|\bcompare\b|\bcomparison\b",
        r"\bvariance\b|\bdifference between\b",
        r"\btotal\b.*\bacross\s+all\b",
    ]
    for pat in patterns:
        if re.search(pat, query, re.IGNORECASE):
            return True
    return False


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
    """
    # 1. Is this an attribute query? (cheap regex gate)
    category = is_attribute_query(query)
    if not category:
        return None

    # 1b. Quick reject obvious superlatives (before LLM call)
    if is_superlative_or_comparison(query):
        logger.debug(f"[PROP_PLANE] Rejected superlative query: {query[:60]}")
        return None

    # 2. Extract query parameters (LLM-based)
    params = extract_query_parameters(query, category)
    attr_name = params.get("attribute_name")
    logger.info(
        f"[PROP_PLANE] Extract: query={query[:60]} → "
        f"entity={params.get('entity_name')} attr={attr_name} fy={params.get('fiscal_year')} "
        f"comparison={params.get('is_comparison')}"
    )

    # LLM detected comparison — reject
    if params.get("is_comparison"):
        logger.debug(f"[PROP_PLANE] LLM flagged as comparison: {query[:60]}")
        return None

    if not attr_name:
        return None

    # 3. Look up property facts
    entity_name = params.get("entity_name")
    rows = _lookup_property_facts(
        session, tenant_id, attr_name,
        entity_name=entity_name,
        fiscal_year=params.get("fiscal_year"),
    )

    # Progressive relaxation if strict lookup failed
    if not rows:
        rows = _try_broader_lookup(session, tenant_id, attr_name, params)

    # 3a. If still no rows and entity was specified, try alias + hierarchy resolution
    if not rows and entity_name:
        canonical = _resolve_entity_via_aliases(
            session, tenant_id, entity_name, attribute_name=attr_name,
        )
        if canonical and canonical.lower() != entity_name.lower():
            logger.info(f"[PROP_PLANE] Alias resolution: '{entity_name}' → '{canonical}'")
            # Try exact attr match with resolved entity first, then LIKE attr
            rows = _lookup_property_facts(
                session, tenant_id, attr_name,
                entity_name=canonical,
            )
            if not rows:
                rows = _lookup_property_facts(
                    session, tenant_id, attr_name,
                    entity_name=canonical,
                    use_like=True,
                )

    if not rows:
        logger.info(
            f"[PROP_PLANE] No rows found for entity={entity_name} "
            f"attr={attr_name} fy={params.get('fiscal_year')}"
        )
        return None

    # 3b. Filter out value-shaped entity names from results
    rows = [r for r in rows if not is_value_shaped_name(r.entity_name)]
    if not rows:
        return None

    # 3c. Entity disambiguation: use graph hierarchy + attribute-type affinity
    if entity_name:
        rows = _disambiguate_entity(
            rows, entity_name,
            session=session,
            tenant_id=tenant_id,
            attribute_name=attr_name,
        )
    if not rows:
        return None

    # 4. Pick the best fact (first row — sorted by lifecycle, entity_type, confidence, numeric_value)
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
        "extracted_entity": None,
        "extracted_attr": None,
        "extracted_fy": None,
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

    # Record what the PP found
    diagnostics["hit"] = True
    diagnostics["attribute_name"] = result.attribute_name
    diagnostics["entity_name"] = result.entity_name
    diagnostics["answer_source"] = result.answer_source

    # Override guard: only replace KG answer when PP result is trustworthy
    kg_source = agent_result.get("answer_source", "")
    kg_answer_text = agent_result.get("answer", "")

    # KG gave a "no data" answer — always safe to override
    kg_is_empty = (
        not kg_answer_text
        or "does not" in kg_answer_text.lower()
        or "not specified" in kg_answer_text.lower()
        or "not explicitly" in kg_answer_text.lower()
        or "unable to" in kg_answer_text.lower()
        or "no information" in kg_answer_text.lower()
    )

    if kg_is_empty:
        # KG has nothing — PP override is always safe
        agent_result["answer"] = result.answer
        agent_result["answer_source"] = result.answer_source
        agent_result["property_evidence"] = result.to_dict()
    elif result.confidence >= 0.85 and result.answer_source == ANSWER_SOURCE_TRUSTED_PROPERTY:
        # PP has a high-confidence TRUSTED fact — override KG
        agent_result["answer"] = result.answer
        agent_result["answer_source"] = result.answer_source
        agent_result["property_evidence"] = result.to_dict()
    else:
        # PP result isn't confident enough to override a non-empty KG answer
        logger.info(
            f"[PROP_PLANE] Skipping override: PP confidence={result.confidence} "
            f"state={result.answer_source}, KG has content"
        )
        diagnostics["override_skipped"] = True

    return agent_result
