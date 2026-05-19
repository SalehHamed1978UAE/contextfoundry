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
    Prefers ORGANIZATION entity type and larger numeric values.
    """
    clauses = [
        "tenant_id = :tid",
        "LOWER(attribute_name) LIKE LOWER(:attr)",
    ]
    params: Dict[str, Any] = {"tid": tenant_id, "attr": f"%{attribute_name}%"}

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
            CASE entity_type WHEN 'ORGANIZATION' THEN 0 ELSE 1 END,
            confidence DESC,
            numeric_value DESC NULLS LAST,
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
    entity's data is worse than returning nothing.
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
# Entity disambiguation
# ---------------------------------------------------------------------------

def _disambiguate_entity(rows: list, query_entity: str) -> list:
    """Prefer rows whose entity_name closely matches the query entity.

    Matching tiers (highest to lowest):
      1. Case-insensitive exact match
      2. Query entity is a substring of the row entity_name (or vice versa),
         sorted by closeness
      3. All remaining rows (loose LIKE match from SQL)
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
        substring.sort(key=lambda r: abs(len(r.entity_name) - len(query_entity)))
        return substring

    return rows


# ---------------------------------------------------------------------------
# Entity resolution via aliases
# ---------------------------------------------------------------------------

def _resolve_entity_via_aliases(
    session,
    tenant_id: str,
    entity_name: str,
) -> Optional[str]:
    """Look up entity_name in the entities + entity_aliases tables.

    If the query entity doesn't directly match a property_facts entity_name,
    try to find it via aliases. Returns the canonical entity name if found.
    """
    sql = """
        SELECT DISTINCT e.name
        FROM entities e
        LEFT JOIN entity_aliases ea ON ea.entity_id = e.id AND ea.tenant_id = e.tenant_id
        WHERE e.tenant_id = :tid
          AND (LOWER(e.name) LIKE LOWER(:pat)
               OR LOWER(ea.alias) LIKE LOWER(:pat))
        ORDER BY e.name ASC
        LIMIT 3
    """
    rows = session.execute(text(sql), {
        "tid": tenant_id,
        "pat": f"%{entity_name}%",
    }).fetchall()

    if rows:
        return rows[0].name
    return None


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

    # 3a. If still no rows and entity was specified, try alias resolution
    if not rows and entity_name:
        canonical = _resolve_entity_via_aliases(session, tenant_id, entity_name)
        if canonical and canonical.lower() != entity_name.lower():
            logger.info(f"[PROP_PLANE] Alias resolution: '{entity_name}' → '{canonical}'")
            rows = _lookup_property_facts(
                session, tenant_id, attr_name,
                entity_name=canonical,
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

    # 3c. Entity disambiguation: if the query names a specific entity,
    # prefer exact/close matches over loose LIKE hits
    if entity_name:
        rows = _disambiguate_entity(rows, entity_name)
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
