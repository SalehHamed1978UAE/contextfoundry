"""PropertyExtractor — extracts structured property facts from document chunks (Stage 3B).

Reads chunks from the DB for each entity, uses gpt-4o-mini to extract
structured property facts (attribute_name, attribute_value, period, confidence, unit),
ground-checks them against the source chunk, and writes to property_facts via PropertyStore.

Reuses:
  - _tokenize pattern from retrieval/document_evidence_fallback.py
  - parse_numeric / detect_value_type / detect_unit from adapters/property_adapter.py
  - OpenAI client init pattern from agents/graph_builder.py
  - PropertyStore.upsert_fact() from memory/property_store.py
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text

logger = logging.getLogger(__name__)

# Stopwords for tokenization (matches document_evidence_fallback.py)
_STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "did",
    "for", "from", "has", "have", "had", "he", "her", "his", "how",
    "i", "in", "is", "it", "its", "of", "on", "or", "she", "that", "the",
    "their", "them", "they", "this", "to", "was", "we", "were", "what",
    "when", "where", "which", "who", "whom", "whose", "why", "will",
    "with", "you", "your", "about", "into",
}

# LLM extraction prompt
_SYSTEM_PROMPT = """\
You are a property extraction system. Given a document chunk and an entity, \
extract all quantitative and qualitative properties of that entity mentioned in the chunk.

Return a JSON array of objects. Each object has these fields:
- "attribute_name": snake_case name of the property (e.g. "revenue", "headcount", "budget", "capacity")
- "attribute_value": the exact value as stated in the text (e.g. "$8.45 billion", "12,500 employees")
- "period": the time period if mentioned (e.g. "FY2025", "Q3 2025", null if not stated)
- "confidence": float 0.0-1.0 for how confident you are this property belongs to the entity
- "unit": the unit if applicable (e.g. "USD", "%", "kg/hr", "qubits", null if not applicable)

Rules:
- Only extract properties explicitly stated in the text for the given entity.
- Do not infer or calculate values.
- Use the exact value string from the text.
- If no properties are found, return an empty array [].
- Return ONLY the JSON array, no other text."""

_USER_PROMPT_TEMPLATE = """\
Entity: {entity_name}
Entity Type: {entity_type}

Document chunk:
{chunk_text}

Extract all properties of "{entity_name}" from this chunk as a JSON array."""


def _tokenize(text_in: str) -> List[str]:
    """Tokenize text for ILIKE chunk retrieval (matches DocEv pattern)."""
    raw = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\.]+", (text_in or "").lower())
    return [t for t in raw if t not in _STOPWORDS and len(t) > 1]


def _strip_json_fences(content: str) -> str:
    """Strip markdown JSON fences from LLM output (matches graph_builder pattern)."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r'^```(?:json)?\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
    return content


class PropertyExtractor:
    """Extracts property facts from document chunks for a given tenant.

    Flow per entity:
    1. Load entity + aliases from entities + entity_aliases tables
    2. Find chunks mentioning entity via ILIKE
    3. For each chunk, call gpt-4o-mini to extract structured properties
    4. Ground-check: extracted value must appear in chunk text
    5. Subject resolution: entity name must be mentioned in chunk
    6. Parse numerics, classify value types, detect units
    7. Write to property_facts via PropertyStore.upsert_fact()
    """

    def __init__(self, session, tenant_id: str, *, dry_run: bool = False):
        self.session = session
        self.tenant_id = tenant_id
        self.dry_run = dry_run
        self._init_openai_client()

    def _init_openai_client(self):
        """Initialize OpenAI client (same pattern as graph_builder.py)."""
        try:
            from openai import OpenAI
        except ImportError:
            logger.warning("[PROP_EX] openai package not installed")
            self.client = None
            return

        ai_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
        ai_base = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        fallback_key = os.environ.get("OPENAI_API_KEY")

        if ai_key and ai_base:
            self.client = OpenAI(api_key=ai_key, base_url=ai_base)
        elif ai_key:
            self.client = OpenAI(api_key=ai_key)
        elif fallback_key:
            self.client = OpenAI(api_key=fallback_key)
        else:
            logger.warning("[PROP_EX] No OpenAI API key available")
            self.client = None

    def extract_all(self, batch_size: int = 50) -> Dict[str, int]:
        """Extract property facts for all entities in the tenant.

        Returns a summary dict: {entity_type: facts_written_count, ...}
        plus "_total_entities", "_total_facts_extracted", "_total_facts_written".
        """
        from ..adapters.property_adapter import is_value_shaped_name
        from ..memory.property_store import PropertyStore

        entities = self._load_entities()
        logger.info(f"[PROP_EX] Loaded {len(entities)} entities for tenant {self.tenant_id}")

        store = PropertyStore(self.session, self.tenant_id) if not self.dry_run else None

        report: Dict[str, int] = {}
        total_extracted = 0
        total_written = 0

        for i, entity in enumerate(entities):
            if is_value_shaped_name(entity["name"]):
                continue

            facts = self.extract_for_entity(entity)
            total_extracted += len(facts)

            etype = entity["entity_type"]
            written = 0
            for fact in facts:
                if not self.dry_run and store is not None:
                    try:
                        store.upsert_fact(fact)
                        written += 1
                    except Exception as e:
                        logger.warning(f"[PROP_EX] Upsert failed for {entity['name']}: {e}")
                else:
                    written += 1  # count as "would write" in dry_run

            report[etype] = report.get(etype, 0) + written
            total_written += written

            if (i + 1) % batch_size == 0:
                logger.info(f"[PROP_EX] Progress: {i + 1}/{len(entities)} entities processed")

        report["_total_entities"] = len(entities)
        report["_total_facts_extracted"] = total_extracted
        report["_total_facts_written"] = total_written
        return report

    def extract_for_entity(self, entity: Dict[str, Any]) -> List[Dict]:
        """Extract property facts for a single entity from matching chunks.

        Returns a list of fact dicts ready for PropertyStore.upsert_fact().
        """
        from ..adapters.property_adapter import (
            detect_unit,
            detect_value_type,
            parse_numeric,
        )

        entity_name = entity["name"]
        entity_type = entity.get("entity_type", "UNKNOWN")
        entity_id = entity["id"]
        aliases = entity.get("aliases", [])

        chunks = self._find_chunks_for_entity(entity_name, aliases)
        if not chunks:
            return []

        all_facts = []
        for chunk in chunks:
            chunk_text = chunk.text if hasattr(chunk, "text") else chunk.get("text", "")
            chunk_doc_id = (
                chunk.document_id if hasattr(chunk, "document_id") else chunk.get("document_id")
            )

            if not self._resolve_subject(entity_name, chunk_text):
                continue

            raw_props = self._extract_properties_from_chunk(chunk_text, entity_name, entity_type)

            for prop in raw_props:
                attr_value = prop.get("attribute_value", "")
                if not attr_value:
                    continue

                if not self._ground_check(attr_value, chunk_text):
                    continue

                confidence = float(prop.get("confidence", 0.7))
                if confidence < 0.6:
                    continue  # rejected

                if confidence >= 0.85:
                    lifecycle_state = "TRUSTED"
                else:
                    lifecycle_state = "STAGING"

                attr_name = prop.get("attribute_name", "value")
                numeric_val = parse_numeric(str(attr_value))
                unit = prop.get("unit") or detect_unit(str(attr_value), attr_name)
                value_type = detect_value_type(str(attr_value), attr_name)
                period = prop.get("period")
                fiscal_year = _extract_fiscal_year(period)

                fact = {
                    "id": str(uuid.uuid4()),
                    "entity_id": entity_id,
                    "entity_name": entity_name,
                    "entity_type": entity_type,
                    "lifecycle_state": lifecycle_state,
                    "attribute_name": attr_name,
                    "attribute_value": str(attr_value),
                    "numeric_value": numeric_val,
                    "unit": unit,
                    "value_type": value_type,
                    "period": period,
                    "fiscal_year": fiscal_year,
                    "source_document_id": chunk_doc_id,
                    "source_entity_properties": {},
                    "confidence": confidence,
                }
                all_facts.append(fact)

        return all_facts

    def _load_entities(self) -> List[Dict[str, Any]]:
        """Load all entities + aliases for the tenant."""
        sql = """
            SELECT e.id::text, e.name, e.entity_type,
                   COALESCE(
                       array_agg(DISTINCT ea.alias) FILTER (WHERE ea.alias IS NOT NULL),
                       ARRAY[]::text[]
                   ) AS aliases
            FROM entities e
            LEFT JOIN entity_aliases ea ON ea.entity_id = e.id AND ea.tenant_id = e.tenant_id
            WHERE e.tenant_id = :tid
            GROUP BY e.id, e.name, e.entity_type
            ORDER BY e.name ASC
        """
        rows = self.session.execute(text(sql), {"tid": self.tenant_id}).fetchall()
        entities = []
        for r in rows:
            aliases = list(r.aliases) if r.aliases else []
            entities.append({
                "id": r.id,
                "name": r.name,
                "entity_type": r.entity_type,
                "aliases": aliases,
            })
        return entities

    def _find_chunks_for_entity(self, entity_name: str, aliases: List[str]) -> List:
        """Find document chunks mentioning the entity via ILIKE token overlap.

        Searches for chunks containing the entity name or any of its aliases.
        """
        search_terms = [entity_name] + (aliases or [])

        or_clauses = []
        params: Dict[str, Any] = {"tid": self.tenant_id}
        idx = 0

        for term in search_terms:
            tokens = _tokenize(term)
            if not tokens:
                continue
            # Build AND clause: all tokens of a name must appear in chunk
            and_parts = []
            for tok in tokens:
                key = f"t{idx}"
                and_parts.append(f"dc.text ILIKE :{key}")
                params[key] = f"%{tok}%"
                idx += 1
            if and_parts:
                or_clauses.append("(" + " AND ".join(and_parts) + ")")

        if not or_clauses:
            return []

        sql = f"""
            SELECT dc.id::text AS chunk_id,
                   dc.document_id::text AS document_id,
                   dc.text AS text
            FROM document_chunks dc
            WHERE dc.tenant_id = :tid
              AND ({" OR ".join(or_clauses)})
            ORDER BY dc.id ASC
            LIMIT 200
        """
        rows = self.session.execute(text(sql), params).fetchall()
        return rows

    def _extract_properties_from_chunk(
        self, chunk_text: str, entity_name: str, entity_type: str
    ) -> List[Dict]:
        """Call gpt-4o-mini to extract property facts from a chunk.

        Returns a list of raw property dicts from the LLM JSON response.
        """
        if not self.client:
            return []

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            entity_name=entity_name,
            entity_type=entity_type,
            chunk_text=chunk_text,
        )

        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=1000,
            )
            content = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning(f"[PROP_EX] LLM call failed for entity={entity_name}: {e}")
            return []

        content = _strip_json_fences(content)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"[PROP_EX] JSON parse failed for entity={entity_name}")
            return []

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        return []

    def _ground_check(self, value: str, chunk_text: str) -> bool:
        """Verify that the extracted value appears in the source chunk.

        Substring match (case-insensitive). Rejects fabricated values.
        """
        if not value or not chunk_text:
            return False
        return value.lower() in chunk_text.lower()

    def _resolve_subject(self, entity_name: str, chunk_text: str) -> bool:
        """Verify that the entity is explicitly mentioned in the chunk.

        Case-insensitive substring check. Rejects chunks that don't reference
        the entity (avoids attributing properties to the wrong entity).
        """
        if not entity_name or not chunk_text:
            return False
        return entity_name.lower() in chunk_text.lower()


def _extract_fiscal_year(period: Optional[str]) -> Optional[str]:
    """Extract a 4-digit fiscal year from a period string.

    Examples:
        "FY2025" → "2025"
        "Q3 2025" → "2025"
        "2025" → "2025"
        None → None
    """
    if not period:
        return None
    m = re.search(r"(20\d{2})", period)
    return m.group(1) if m else None
