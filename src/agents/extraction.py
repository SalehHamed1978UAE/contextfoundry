"""
Extraction Agent

Extracts entities and relationships from document chunks using LLM.
All extractions go to STAGING with confidence scores and source provenance.

Schema-driven extraction for:
- Entities: Service, Component, Team, Person, Database, Incident
- Relationships: DEPENDS_ON, OWNS, CALLS, MEMBER_OF, SUPPORTS, CAUSED_BY
"""

import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import settings
from src.models.schemas import LifecycleState
from src.utils.llm import OllamaClient


class ExtractionAgent:
    """Extracts structured data from unstructured text"""

    # Entity type definitions
    ENTITY_TYPES = {
        "Service": "A software service or application (e.g., payment-api, user-service)",
        "Component": "Infrastructure component (e.g., database, cache, queue, load balancer)",
        "Team": "Engineering team (e.g., payments-team, platform-team)",
        "Person": "Individual person with name and role",
        "Database": "Database instance (PostgreSQL, MySQL, etc.)",
        "Cache": "Cache instance (Redis, Memcached, etc.)",
        "Queue": "Message queue (RabbitMQ, Kafka, etc.)",
        "Incident": "Incident or outage report"
    }

    # Relationship type definitions
    RELATIONSHIP_TYPES = {
        "DEPENDS_ON": "Source depends on target (e.g., payment-api DEPENDS_ON payments-db)",
        "OWNS": "Team owns a service/component (e.g., payments-team OWNS payment-api)",
        "CALLS": "Service calls another service (e.g., payment-api CALLS user-service)",
        "MEMBER_OF": "Person is member of team (e.g., Alice Chen MEMBER_OF payments-team)",
        "SUPPORTS": "Team supports a service (e.g., platform-team SUPPORTS api-gateway)",
        "CAUSED_BY": "Incident caused by another incident or issue",
        "AFFECTS": "Incident affects a service/component"
    }

    def __init__(self, db_manager):
        self.db = db_manager
        self.llm = OllamaClient()

    async def extract_from_chunk(
        self,
        chunk_text: str,
        document_id: str,
        document_type: str,
        chunk_index: int
    ) -> Dict[str, Any]:
        """
        Extract entities and relationships from a document chunk

        Args:
            chunk_text: Text to extract from
            document_id: Source document ID
            document_type: Type of document (runbook, incident, etc.)
            chunk_index: Index of chunk in document

        Returns:
            Dictionary with extracted entities and relationships
        """

        print(f"\n  Extracting from chunk {chunk_index}...")

        # Step 1: Extract entities
        entities = await self._extract_entities(chunk_text, document_id, chunk_index)
        print(f"    → Found {len(entities)} entities")

        # Step 2: Extract relationships
        relationships = await self._extract_relationships(
            chunk_text,
            entities,
            document_id,
            chunk_index
        )
        print(f"    → Found {len(relationships)} relationships")

        return {
            "entities": entities,
            "relationships": relationships,
            "chunk_index": chunk_index,
            "document_id": document_id
        }

    async def _extract_entities(
        self,
        text: str,
        document_id: str,
        chunk_index: int
    ) -> List[Dict[str, Any]]:
        """Extract entities using LLM"""

        prompt = self._build_entity_extraction_prompt(text)

        try:
            print(f"    → Entity extraction...", flush=True)

            result = await self.llm.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=1024
            )

            llm_text = result.get("text", "")

            if result.get("error"):
                print(f"    ✗ LLM error: {result['error']}")
                return []

            print(f"    → LLM response: {len(llm_text)} chars", flush=True)

            # Parse LLM response
            extracted = self._parse_entity_response(llm_text)

            # Add metadata to each entity
            for entity in extracted:
                entity["document_id"] = document_id
                entity["chunk_index"] = chunk_index
                entity["extraction_method"] = "llm_extraction"
                entity["id"] = str(uuid.uuid4())

            return extracted

        except Exception as e:
            print(f"    ✗ Entity extraction failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _extract_relationships(
        self,
        text: str,
        entities: List[Dict[str, Any]],
        document_id: str,
        chunk_index: int
    ) -> List[Dict[str, Any]]:
        """Extract relationships using LLM"""

        if not entities:
            return []

        prompt = self._build_relationship_extraction_prompt(text, entities)

        try:
            print(f"    → Relationship extraction...", flush=True)

            result = await self.llm.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=1536
            )

            response_text = result.get("text", "")

            if result.get("error"):
                print(f"    ✗ LLM error: {result['error']}")
                return []

            print(f"    → LLM response: {len(response_text)} chars", flush=True)

            if not response_text or len(response_text.strip()) < 10:
                print(f"    ✗ Empty LLM response")
                return []

            extracted = self._parse_relationship_response(response_text)

            # Add metadata to each relationship
            for rel in extracted:
                rel["document_id"] = document_id
                rel["chunk_index"] = chunk_index
                rel["id"] = str(uuid.uuid4())

            return extracted

        except Exception as e:
            print(f"    ✗ Relationship extraction failed: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"    Traceback: {traceback.format_exc()[-200:]}")
            return []

    def _build_entity_extraction_prompt(self, text: str) -> str:
        """Build prompt for entity extraction"""

        # Use up to 1200 chars per chunk for faster CPU inference
        chunk_text = text[:1200]

        return f"""Extract ALL entities from this text. Return JSON only.

TEXT: {chunk_text}

Entity types (pick ONE per entity): Service, Database, Cache, Queue, Team, Person, Incident, Component

Example output:
{{"entities": [
  {{"canonical_name": "payment-api", "entity_type": "Service", "confidence": 0.95, "source_sentence": "the payment-api handles payments"}},
  {{"canonical_name": "payments-team", "entity_type": "Team", "confidence": 0.90, "source_sentence": "owned by payments-team"}},
  {{"canonical_name": "Bob Martinez", "entity_type": "Person", "confidence": 0.85, "source_sentence": "DBA Contact: Bob Martinez"}}
]}}"""

    def _build_relationship_extraction_prompt(
        self,
        text: str,
        entities: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for relationship extraction"""

        entity_names = ", ".join([e['canonical_name'] for e in entities[:20]])  # Allow up to 20
        chunk_text = text[:1200]

        return f"""Extract ALL relationships between these entities from the text. Return JSON only.

TEXT: {chunk_text}

ENTITIES: {entity_names}

Relationship types: DEPENDS_ON, OWNS, CALLS, MEMBER_OF, SUPPORTS, CAUSED_BY, AFFECTS

Return format: {{"relationships": [{{"source_name": "entity1", "relationship_type": "DEPENDS_ON", "target_name": "entity2", "confidence": 0.9, "source_sentence": "sentence"}}]}}"""

    def _clean_llm_json(self, text: str) -> str:
        """Clean and repair JSON from LLM output"""
        text = text.strip()

        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Fix LLM escaping underscores
        text = text.replace("\\_", "_")

        # Fix trailing commas before ] or }
        import re
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)

        # Try to fix truncated JSON by closing open brackets
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')

        if open_braces > 0 or open_brackets > 0:
            # Truncated — try to salvage by closing brackets
            # First, try to find the last complete entity/relationship
            last_complete = text.rfind('}')
            if last_complete > 0:
                text = text[:last_complete + 1]
                # Re-count
                open_brackets = text.count('[') - text.count(']')
                open_braces = text.count('{') - text.count('}')
                text += ']' * open_brackets
                text += '}' * open_braces

        return text

    def _parse_entity_response(self, text: str) -> List[Dict[str, Any]]:
        """Parse LLM response for entity extraction"""

        text = self._clean_llm_json(text)

        try:
            parsed = json.loads(text)
            entities = parsed.get("entities", [])

            # Validate each entity
            validated = []
            for entity in entities:
                if self._validate_entity(entity):
                    validated.append(entity)

            return validated

        except json.JSONDecodeError as e:
            print(f"    ✗ Failed to parse entity JSON: {e}")
            print(f"    ✗ JSON text (last 200 chars): ...{text[-200:]}")
            return []

    def _parse_relationship_response(self, text: str) -> List[Dict[str, Any]]:
        """Parse LLM response for relationship extraction"""

        text = self._clean_llm_json(text)

        try:
            parsed = json.loads(text)
            relationships = parsed.get("relationships", [])

            # Validate each relationship
            validated = []
            for rel in relationships:
                if self._validate_relationship(rel):
                    validated.append(rel)

            return validated

        except json.JSONDecodeError as e:
            print(f"    ✗ Failed to parse relationship JSON: {e}")
            return []

    def _validate_entity(self, entity: Dict[str, Any]) -> bool:
        """Validate extracted entity has required fields"""

        required = ["canonical_name", "entity_type", "confidence"]

        for field in required:
            if field not in entity:
                print(f"    ✗ Entity missing field: {field}")
                return False

        # Fix entity type if model output pipe-separated options (e.g., "Team|Person")
        etype = entity["entity_type"]
        if "|" in etype:
            etype = etype.split("|")[0].strip()
            entity["entity_type"] = etype

        # Check entity type is valid
        if etype not in self.ENTITY_TYPES:
            print(f"    ✗ Invalid entity type: {etype}")
            return False

        # Fix confidence if it's an int
        entity["confidence"] = float(entity["confidence"])

        # Check confidence is in range
        if not (0.0 <= entity["confidence"] <= 1.0):
            entity["confidence"] = min(max(entity["confidence"], 0.0), 1.0)

        # Default source_sentence if missing
        if "source_sentence" not in entity:
            entity["source_sentence"] = ""

        return True

    def _validate_relationship(self, rel: Dict[str, Any]) -> bool:
        """Validate extracted relationship has required fields"""

        required = ["source_name", "relationship_type", "target_name", "confidence", "source_sentence"]

        for field in required:
            if field not in rel:
                print(f"    ✗ Relationship missing field: {field}")
                return False

        # Check relationship type is valid
        if rel["relationship_type"] not in self.RELATIONSHIP_TYPES:
            print(f"    ✗ Invalid relationship type: {rel['relationship_type']}")
            return False

        # Check confidence is in range
        if not (0.0 <= rel["confidence"] <= 1.0):
            print(f"    ✗ Invalid confidence: {rel['confidence']}")
            return False

        # Check source != target (self-loops are invalid)
        if rel["source_name"].lower().strip() == rel["target_name"].lower().strip():
            print(f"    ✗ Self-loop: {rel['source_name']} -> {rel['target_name']}")
            return False

        return True

    def validate_relationships_against_entities(
        self,
        relationships: List[Dict[str, Any]],
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter relationships to only those where both endpoints exist
        in the extracted entities list.

        Args:
            relationships: Extracted relationships
            entities: Extracted entities (already deduped)

        Returns:
            Validated relationships
        """
        entity_names = {e["canonical_name"].lower().strip() for e in entities}

        validated = []
        orphaned = 0

        for rel in relationships:
            source = rel["source_name"].lower().strip()
            target = rel["target_name"].lower().strip()

            if source in entity_names and target in entity_names:
                validated.append(rel)
            else:
                orphaned += 1
                missing = []
                if source not in entity_names:
                    missing.append(f"source '{rel['source_name']}'")
                if target not in entity_names:
                    missing.append(f"target '{rel['target_name']}'")
                print(f"    ⚠ Orphan relationship dropped: {rel['source_name']} -[{rel['relationship_type']}]-> {rel['target_name']} (missing: {', '.join(missing)})")

        if orphaned > 0:
            print(f"    → Validation: {len(validated)} valid, {orphaned} orphaned relationships dropped")

        return validated

    async def insert_extractions_to_staging(
        self,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Insert extracted entities and relationships into STAGING

        Args:
            entities: List of extracted entities
            relationships: List of extracted relationships

        Returns:
            Dictionary with insertion results
        """

        print(f"\n  Inserting extractions into STAGING...")

        inserted_entities = 0
        inserted_relationships = 0
        errors = []

        async with self.db.get_postgres_connection() as conn:
            # Insert entities into graph_lifecycle (STAGING)
            for entity in entities:
                try:
                    entity_id = entity["id"]
                    canonical_name = entity["canonical_name"]
                    entity_type = entity["entity_type"]
                    confidence = entity["confidence"]
                    source_sentence = entity["source_sentence"]
                    document_id = entity["document_id"]
                    extraction_method = entity["extraction_method"]

                    # Insert into graph_lifecycle
                    # canonical_name stored in extracted_text, source_sentence has the evidence
                    await conn.execute("""
                        INSERT INTO graph_lifecycle (
                            entity_id, entity_type, lifecycle_state, confidence,
                            source_document_id, source_sentence, extracted_text,
                            extraction_method, extraction_confidence
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (entity_id) DO NOTHING
                    """, entity_id, entity_type, LifecycleState.STAGING.value, confidence,
                         document_id, source_sentence, canonical_name,
                         extraction_method, confidence)

                    # Also insert into AGE graph
                    await conn.execute("LOAD 'age'")
                    await conn.execute("SET search_path = ag_catalog, '$user', public")

                    cypher = f"""
                    SELECT * FROM cypher('{settings.graph_name}', $$
                        MERGE (n:{entity_type} {{id: '{entity_id}', name: '{canonical_name}'}})
                        RETURN n
                    $$) as (node agtype)
                    """

                    await conn.execute(cypher)

                    inserted_entities += 1

                except Exception as e:
                    errors.append(f"Entity {entity.get('canonical_name', 'unknown')}: {str(e)}")

            print(f"    → Inserted {inserted_entities} entities")

            # Insert relationships
            for rel in relationships:
                try:
                    # Find entity IDs by name
                    source_id = await self._find_entity_id_by_name(conn, rel["source_name"])
                    target_id = await self._find_entity_id_by_name(conn, rel["target_name"])

                    if not source_id or not target_id:
                        errors.append(f"Relationship {rel['source_name']} -> {rel['target_name']}: Entity not found")
                        continue

                    rel_id = rel["id"]
                    rel_type = rel["relationship_type"]
                    confidence = rel["confidence"]
                    document_id = rel["document_id"]

                    # Insert into relationship_metadata
                    await conn.execute("""
                        INSERT INTO relationship_metadata (
                            relationship_id, source_entity_id, target_entity_id,
                            relationship_type, lifecycle_state, confidence, source_document_id
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (relationship_id) DO NOTHING
                    """, rel_id, source_id, target_id, rel_type,
                         LifecycleState.STAGING.value, confidence, document_id)

                    # Insert into AGE graph
                    await conn.execute("LOAD 'age'")
                    await conn.execute("SET search_path = ag_catalog, '$user', public")

                    cypher = f"""
                    SELECT * FROM cypher('{settings.graph_name}', $$
                        MATCH (a {{id: '{source_id}'}}), (b {{id: '{target_id}'}})
                        MERGE (a)-[r:{rel_type} {{id: '{rel_id}'}}]->(b)
                        RETURN r
                    $$) as (rel agtype)
                    """

                    await conn.execute(cypher)

                    inserted_relationships += 1

                except Exception as e:
                    errors.append(f"Relationship {rel.get('source_name', '?')} -> {rel.get('target_name', '?')}: {str(e)}")

            print(f"    → Inserted {inserted_relationships} relationships")

            if errors:
                print(f"    ✗ {len(errors)} errors occurred")
                for error in errors[:3]:
                    print(f"      - {error}")

        return {
            "inserted_entities": inserted_entities,
            "inserted_relationships": inserted_relationships,
            "errors": errors
        }

    async def rule_evolver(self) -> Dict[str, Any]:
        """
        Adjust rule priorities and enabled status based on application history.

        1. Disable rules with times_applied >= 50 AND violation_rate > 80%
        2. Increase priority by 1 for rules with times_applied >= 20 AND 0 violations
        3. Decrease priority by 1 for rules with times_applied >= 20
           AND violation_rate between 40%-80%
        """
        disabled = []
        promoted = []
        demoted = []

        async with self.db.get_postgres_connection() as conn:
            # Step 1: Disable broken rules
            rows = await conn.fetch("""
                UPDATE symbolic_rules
                SET enabled = false, updated_at = NOW()
                WHERE times_applied >= 50
                  AND times_violated::float / GREATEST(times_applied, 1) > 0.8
                  AND enabled = true
                RETURNING rule_name
            """)
            disabled = [r["rule_name"] for r in rows]

            # Step 2: Promote clean rules
            rows = await conn.fetch("""
                UPDATE symbolic_rules
                SET priority = priority + 1, updated_at = NOW()
                WHERE times_applied >= 20
                  AND times_violated = 0
                  AND enabled = true
                RETURNING rule_name
            """)
            promoted = [r["rule_name"] for r in rows]

            # Step 3: Demote noisy rules
            rows = await conn.fetch("""
                UPDATE symbolic_rules
                SET priority = GREATEST(priority - 1, 0), updated_at = NOW()
                WHERE times_applied >= 20
                  AND times_violated::float / GREATEST(times_applied, 1) BETWEEN 0.4 AND 0.8
                  AND enabled = true
                RETURNING rule_name
            """)
            demoted = [r["rule_name"] for r in rows]

        return {"disabled": disabled, "promoted": promoted, "demoted": demoted}

    async def _find_entity_id_by_name(self, conn, name: str) -> Optional[str]:
        """Find entity ID by canonical name in STAGING or TRUSTED"""

        # Search in extracted_text (new field) first, fall back to source_sentence (legacy)
        result = await conn.fetchval("""
            SELECT entity_id FROM graph_lifecycle
            WHERE (LOWER(extracted_text) = LOWER($1) OR LOWER(source_sentence) = LOWER($1))
            AND lifecycle_state IN ($2, $3)
            ORDER BY
                CASE lifecycle_state WHEN 'TRUSTED' THEN 0 ELSE 1 END,
                confidence DESC,
                created_at DESC
            LIMIT 1
        """, name, LifecycleState.STAGING.value, LifecycleState.TRUSTED.value)

        return str(result) if result else None
