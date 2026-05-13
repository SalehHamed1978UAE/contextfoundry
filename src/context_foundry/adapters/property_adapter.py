"""Property Adapter — parses entity.properties JSON into property_facts rows (Stage 3A M2).

No re-extraction needed. Reads existing entities and their properties JSON,
normalizes them into flat PropertyFact rows, and upserts via PropertyStore.

Entity type parsers handle the known property schemas:
  - FINANCIAL_METRIC: {metric_name, value, value_type, period, fiscal_year, unit}
  - PROJECT: {budget, budget_value, capacity, start_date, end_date, status}
  - PRODUCT: {revenue, category, market_share}
  - CUSTOMER: {contract_value, region}
  - FACILITY: {capacity, facility_type}
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Numeric parser
# ---------------------------------------------------------------------------

_MULTIPLIERS = {
    "trillion": 1e12,
    "billion": 1e9,
    "million": 1e6,
    "thousand": 1e3,
    "k": 1e3,
    "m": 1e6,
    "b": 1e9,
    "t": 1e12,
}

_NUM_PATTERN = re.compile(
    r"[\$\€\£]?\s*"                     # optional currency symbol
    r"([\d,]+(?:\.\d+)?)"               # number (with commas/decimals)
    r"\s*"
    r"(trillion|billion|million|thousand)?"  # optional word multiplier
    r"\s*"
    r"(%|percent|percentage)?"          # optional percentage marker
    , re.IGNORECASE,
)


def parse_numeric(value_str: str) -> Optional[float]:
    """Parse a human-readable numeric string to a float.

    Examples:
        "$8.45 billion"  → 8450000000.0
        "$145 million"   → 145000000.0
        "127 qubits"     → 127.0
        "425 kg/hr"      → 425.0
        "23.5%"          → 23.5
        "12,500"         → 12500.0
        "Q3 2025"        → None (date-like)
        "2025-01-15"     → None (date)
    """
    if not value_str:
        return None
    s = str(value_str).strip()

    # Skip date-like strings
    if re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}", s):
        return None
    if re.match(r"^(Q[1-4]|FY)\s*\d{4}", s, re.IGNORECASE):
        return None
    # Skip pure date ranges like "Jan 2025 - Dec 2026"
    if re.match(r"^[A-Za-z]+\s+\d{4}\s*[-–]\s*[A-Za-z]+\s+\d{4}", s):
        return None

    m = _NUM_PATTERN.search(s)
    if not m:
        return None

    num_str = m.group(1).replace(",", "")
    try:
        value = float(num_str)
    except ValueError:
        return None

    multiplier_str = (m.group(2) or "").lower()
    if multiplier_str in _MULTIPLIERS:
        value *= _MULTIPLIERS[multiplier_str]

    return value


def detect_value_type(value_str: str, key: str = "") -> str:
    """Classify a value string into a type category."""
    s = str(value_str).strip().lower()
    k = key.lower()

    if "%" in s or "percent" in s or k in ("margin", "growth_rate", "market_share"):
        return "PERCENTAGE"
    if s.startswith("$") or s.startswith("€") or s.startswith("£"):
        return "CURRENCY"
    if any(w in s for w in ("billion", "million", "thousand")) and any(
        c in s for c in "$€£"
    ):
        return "CURRENCY"
    if k in ("revenue", "budget", "cost", "contract_value", "backlog", "ebitda",
             "capex", "funding", "valuation", "salary", "spend"):
        return "CURRENCY"
    if re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}", s) or k.endswith("_date"):
        return "DATE"
    if k in ("headcount", "employees", "count", "qubits", "qubit_count"):
        return "COUNT"
    return "SPEC"


def detect_unit(value_str: str, key: str = "") -> Optional[str]:
    """Extract the unit from a value string."""
    s = str(value_str).strip()
    k = key.lower()

    if s.startswith("$") or "usd" in s.lower():
        return "USD"
    if s.startswith("€"):
        return "EUR"
    if s.startswith("£"):
        return "GBP"
    if "%" in s or "percent" in s:
        return "%"
    if "kg/hr" in s.lower():
        return "kg/hr"
    if "wh/kg" in s.lower() or "watt-hour" in s.lower():
        return "Wh/kg"
    if "kwh" in s.lower():
        return "kWh"
    if "mw" in s.lower() or "megawatt" in s.lower():
        return "MW"
    if "qubit" in s.lower() or k in ("qubits", "qubit_count"):
        return "qubits"

    # Check for trailing unit after number
    m = re.search(r"\d\s+([a-zA-Z/]+)$", s)
    if m:
        return m.group(1)

    return None


# ---------------------------------------------------------------------------
# Entity type parsers
# ---------------------------------------------------------------------------

def _base_fact(entity: Dict, attribute_name: str, attribute_value: str) -> Dict[str, Any]:
    """Construct a base fact dict from an entity and attribute."""
    return {
        "entity_id": entity["id"],
        "entity_name": entity["name"],
        "entity_type": entity["entity_type"],
        "lifecycle_state": entity.get("lifecycle_state", "STAGING"),
        "attribute_name": attribute_name,
        "attribute_value": str(attribute_value),
        "numeric_value": parse_numeric(str(attribute_value)),
        "unit": detect_unit(str(attribute_value), attribute_name),
        "value_type": detect_value_type(str(attribute_value), attribute_name),
        "source_document_id": entity.get("source_document_id"),
        "source_entity_properties": entity.get("properties", {}),
        "confidence": entity.get("confidence", 0.8),
    }


def parse_financial_metric(entity: Dict) -> List[Dict[str, Any]]:
    """Parse FINANCIAL_METRIC entity properties into fact rows."""
    props = entity.get("properties") or {}
    facts = []

    # Primary value (metric_name → attribute_name, value → attribute_value)
    metric_name = props.get("metric_name") or props.get("name") or ""
    value = props.get("value")

    if value is not None and str(value).strip():
        attr_name = _normalize_metric_name(metric_name) if metric_name else "value"
        fact = _base_fact(entity, attr_name, str(value))
        fact["period"] = props.get("period")
        fact["fiscal_year"] = props.get("fiscal_year")
        if not fact["unit"] and props.get("unit"):
            fact["unit"] = props["unit"]
        if props.get("value_type"):
            fact["value_type"] = props["value_type"].upper()
        facts.append(fact)

    # Additional numeric properties that aren't the primary value
    for key in ("margin", "growth_rate", "percentage", "amount"):
        if key in props and props[key] is not None and key != "value":
            fact = _base_fact(entity, key, str(props[key]))
            fact["period"] = props.get("period")
            fact["fiscal_year"] = props.get("fiscal_year")
            facts.append(fact)

    return facts


def parse_project(entity: Dict) -> List[Dict[str, Any]]:
    """Parse PROJECT entity properties into fact rows."""
    props = entity.get("properties") or {}
    facts = []

    # Budget
    for key in ("budget", "budget_value", "total_budget"):
        if key in props and props[key] is not None:
            fact = _base_fact(entity, "budget", str(props[key]))
            fact["period"] = props.get("period")
            fact["fiscal_year"] = props.get("fiscal_year")
            facts.append(fact)
            break  # only one budget fact per entity

    # Capacity
    if "capacity" in props and props["capacity"] is not None:
        fact = _base_fact(entity, "capacity", str(props["capacity"]))
        facts.append(fact)

    # Dates
    for date_key in ("start_date", "end_date", "target_date", "completion_date"):
        if date_key in props and props[date_key] is not None:
            fact = _base_fact(entity, date_key, str(props[date_key]))
            fact["value_type"] = "DATE"
            facts.append(fact)

    # Status
    if "status" in props and props["status"] is not None:
        fact = _base_fact(entity, "status", str(props["status"]))
        fact["value_type"] = "STATUS"
        facts.append(fact)

    return facts


def parse_product(entity: Dict) -> List[Dict[str, Any]]:
    """Parse PRODUCT entity properties into fact rows."""
    props = entity.get("properties") or {}
    facts = []

    for key in ("revenue", "market_share", "category", "capacity",
                "energy_density", "qubits", "qubit_count", "throughput"):
        if key in props and props[key] is not None:
            fact = _base_fact(entity, key, str(props[key]))
            fact["period"] = props.get("period")
            fact["fiscal_year"] = props.get("fiscal_year")
            facts.append(fact)

    return facts


def parse_customer(entity: Dict) -> List[Dict[str, Any]]:
    """Parse CUSTOMER entity properties into fact rows."""
    props = entity.get("properties") or {}
    facts = []

    for key in ("contract_value", "region", "annual_revenue", "deal_value"):
        if key in props and props[key] is not None:
            fact = _base_fact(entity, key, str(props[key]))
            fact["period"] = props.get("period")
            fact["fiscal_year"] = props.get("fiscal_year")
            facts.append(fact)

    return facts


def parse_facility(entity: Dict) -> List[Dict[str, Any]]:
    """Parse FACILITY entity properties into fact rows."""
    props = entity.get("properties") or {}
    facts = []

    for key in ("capacity", "production_capacity", "throughput",
                "facility_type", "location"):
        if key in props and props[key] is not None:
            fact = _base_fact(entity, key, str(props[key]))
            facts.append(fact)

    return facts


def _normalize_metric_name(name: str) -> str:
    """Normalize a metric name to a snake_case attribute key."""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "value"


# ---------------------------------------------------------------------------
# PropertyAdapter class
# ---------------------------------------------------------------------------

ENTITY_TYPE_PARSERS = {
    "FINANCIAL_METRIC": parse_financial_metric,
    "PROJECT": parse_project,
    "PRODUCT": parse_product,
    "CUSTOMER": parse_customer,
    "FACILITY": parse_facility,
}


class PropertyAdapter:
    """Parses entity.properties JSON into PropertyFact rows.

    Usage:
        adapter = PropertyAdapter(session, tenant_id)
        report = adapter.adapt_all()
        print(report)  # {"FINANCIAL_METRIC": 384, "PROJECT": 112, ...}
    """

    def __init__(self, session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def fetch_entities(self, entity_type: str, batch_size: int = 100) -> List[Dict]:
        """Fetch entities of a given type with non-empty properties."""
        sql = """
            SELECT id::text, name, entity_type, properties, lifecycle_state,
                   source_document_id, confidence
            FROM entities
            WHERE tenant_id = :tid
              AND entity_type = :etype
              AND properties IS NOT NULL
              AND properties::text != '{}'
              AND properties::text != 'null'
            ORDER BY name ASC
        """
        rows = self.session.execute(
            text(sql), {"tid": self.tenant_id, "etype": entity_type}
        ).fetchall()

        entities = []
        for r in rows:
            props = r.properties if isinstance(r.properties, dict) else {}
            entities.append({
                "id": r.id,
                "name": r.name,
                "entity_type": r.entity_type,
                "properties": props,
                "lifecycle_state": r.lifecycle_state if hasattr(r, "lifecycle_state") else "STAGING",
                "source_document_id": r.source_document_id if hasattr(r, "source_document_id") else None,
                "confidence": r.confidence if hasattr(r, "confidence") else 0.8,
            })
        return entities

    def adapt_type(self, entity_type: str, batch_size: int = 100) -> Tuple[int, List[Dict]]:
        """Parse all entities of a type into property facts.

        Returns (entity_count, facts_list).
        """
        parser = ENTITY_TYPE_PARSERS.get(entity_type)
        if not parser:
            logger.warning(f"[PROP_ADAPTER] No parser for entity_type={entity_type}")
            return 0, []

        entities = self.fetch_entities(entity_type, batch_size)
        all_facts = []
        for ent in entities:
            try:
                facts = parser(ent)
                all_facts.extend(facts)
            except Exception as e:
                logger.warning(
                    f"[PROP_ADAPTER] Failed to parse {ent['name']} ({entity_type}): {e}"
                )

        return len(entities), all_facts

    def adapt_all(self, batch_size: int = 100) -> Dict[str, int]:
        """Parse all supported entity types. Returns per-type fact counts."""
        report: Dict[str, int] = {}
        for etype in ENTITY_TYPE_PARSERS:
            entity_count, facts = self.adapt_type(etype, batch_size)
            report[etype] = len(facts)
            logger.info(
                f"[PROP_ADAPTER] {etype}: {entity_count} entities → {len(facts)} facts"
            )
        return report

    def adapt_and_store(self, store, batch_size: int = 100) -> Dict[str, int]:
        """Parse all entity types and upsert into PropertyStore.

        Returns per-type upsert counts.
        """
        report: Dict[str, int] = {}
        for etype in ENTITY_TYPE_PARSERS:
            _, facts = self.adapt_type(etype, batch_size)
            upserted = store.bulk_upsert(facts) if facts else 0
            report[etype] = upserted
            logger.info(
                f"[PROP_ADAPTER] {etype}: {upserted} facts upserted"
            )
        return report
