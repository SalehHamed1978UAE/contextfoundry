"""
Deduplication and Entity Merging Agent

Handles:
1. Detecting duplicate entities from overlapping chunks (same canonical_name + entity_type)
2. Merging duplicates: keep highest confidence, combine provenance
3. Detecting duplicate relationships (same source + target + type)
4. Cross-document entity resolution (same entity mentioned in multiple documents)

Runs after extraction, before promotion to TRUSTED.
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime

from src.config import settings
from src.models.schemas import LifecycleState


class DeduplicationAgent:
    """Deduplicates and merges extracted entities and relationships"""

    def __init__(self, db_manager):
        self.db = db_manager

    # ------------------------------------------------------------------
    # In-memory dedup (runs on extraction output before DB insertion)
    # ------------------------------------------------------------------

    def dedup_entities(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate entities by canonical_name + entity_type.
        Keeps the highest-confidence version and merges provenance.

        Args:
            entities: Raw extracted entities (may contain duplicates)

        Returns:
            Deduplicated entity list
        """
        seen: Dict[str, Dict[str, Any]] = {}

        for entity in entities:
            key = self._entity_key(entity)

            if key not in seen:
                # First occurrence — store with provenance list
                entity["provenance"] = [{
                    "document_id": entity.get("document_id"),
                    "chunk_index": entity.get("chunk_index"),
                    "confidence": entity.get("confidence", 0.0),
                    "source_sentence": entity.get("source_sentence", ""),
                }]
                entity["extraction_count"] = 1
                seen[key] = entity
            else:
                # Duplicate — merge into existing
                existing = seen[key]
                existing["extraction_count"] = existing.get("extraction_count", 1) + 1

                # Track provenance from this extraction
                existing.setdefault("provenance", []).append({
                    "document_id": entity.get("document_id"),
                    "chunk_index": entity.get("chunk_index"),
                    "confidence": entity.get("confidence", 0.0),
                    "source_sentence": entity.get("source_sentence", ""),
                })

                # Keep highest confidence
                if entity.get("confidence", 0.0) > existing.get("confidence", 0.0):
                    existing["confidence"] = entity["confidence"]
                    existing["source_sentence"] = entity["source_sentence"]

        deduped = list(seen.values())
        removed = len(entities) - len(deduped)

        if removed > 0:
            print(f"    → Dedup: {len(entities)} → {len(deduped)} entities ({removed} duplicates merged)")

        return deduped

    def dedup_relationships(
        self,
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate relationships by source_name + target_name + relationship_type.
        Keeps the highest-confidence version.

        Args:
            relationships: Raw extracted relationships (may contain duplicates)

        Returns:
            Deduplicated relationship list
        """
        seen: Dict[str, Dict[str, Any]] = {}

        for rel in relationships:
            key = self._relationship_key(rel)

            if key not in seen:
                rel["extraction_count"] = 1
                seen[key] = rel
            else:
                existing = seen[key]
                existing["extraction_count"] = existing.get("extraction_count", 1) + 1

                if rel.get("confidence", 0.0) > existing.get("confidence", 0.0):
                    existing["confidence"] = rel["confidence"]
                    existing["source_sentence"] = rel["source_sentence"]

        deduped = list(seen.values())
        removed = len(relationships) - len(deduped)

        if removed > 0:
            print(f"    → Dedup: {len(relationships)} → {len(deduped)} relationships ({removed} duplicates merged)")

        return deduped

    # ------------------------------------------------------------------
    # Database-level dedup (merges STAGING entities across documents)
    # ------------------------------------------------------------------

    async def merge_staging_duplicates(self) -> Dict[str, Any]:
        """
        Find and merge duplicate entities already in STAGING.
        Duplicates are entities with the same canonical_name (stored in
        source_sentence column) and entity_type.

        Returns:
            Dictionary with merge statistics
        """
        merged_count = 0
        errors = []

        async with self.db.get_postgres_connection() as conn:
            # Find duplicates: same name + type in STAGING
            # canonical_name is in extracted_text (new) or source_sentence (legacy)
            duplicates = await conn.fetch("""
                SELECT
                    LOWER(COALESCE(extracted_text, source_sentence)) AS canonical_name,
                    entity_type,
                    array_agg(entity_id ORDER BY confidence DESC) AS entity_ids,
                    array_agg(confidence ORDER BY confidence DESC) AS confidences,
                    array_agg(source_document_id) AS document_ids,
                    COUNT(*) AS count
                FROM graph_lifecycle
                WHERE lifecycle_state = $1
                GROUP BY LOWER(COALESCE(extracted_text, source_sentence)), entity_type
                HAVING COUNT(*) > 1
            """, LifecycleState.STAGING.value)

            for dup_group in duplicates:
                try:
                    entity_ids = dup_group["entity_ids"]
                    canonical_name = dup_group["canonical_name"]
                    entity_type = dup_group["entity_type"]

                    # Keep the first (highest confidence) as the survivor
                    survivor_id = str(entity_ids[0])
                    duplicate_ids = [str(eid) for eid in entity_ids[1:]]

                    # Boost survivor confidence based on extraction count
                    # More independent extractions = higher confidence
                    extraction_count = len(entity_ids)
                    confidence_boost = min(0.05 * (extraction_count - 1), 0.10)
                    max_confidence = float(dup_group["confidences"][0])
                    new_confidence = min(max_confidence + confidence_boost, 1.0)

                    await conn.execute("""
                        UPDATE graph_lifecycle
                        SET confidence = $1,
                            extraction_confidence = $1
                        WHERE entity_id = $2
                    """, new_confidence, entity_ids[0])

                    # Re-point relationships from duplicates to survivor
                    for dup_id in duplicate_ids:
                        await conn.execute("""
                            UPDATE relationship_metadata
                            SET source_entity_id = $1
                            WHERE source_entity_id = $2
                        """, entity_ids[0], dup_id)

                        await conn.execute("""
                            UPDATE relationship_metadata
                            SET target_entity_id = $1
                            WHERE target_entity_id = $2
                        """, entity_ids[0], dup_id)

                    # Archive duplicates (don't delete — keep audit trail)
                    for dup_id in duplicate_ids:
                        await conn.execute("""
                            UPDATE graph_lifecycle
                            SET lifecycle_state = $1,
                                archived_at = $2,
                                conflicts = conflicts || $3::jsonb
                            WHERE entity_id = $4
                        """,
                            LifecycleState.ARCHIVED.value,
                            datetime.utcnow(),
                            f'{{"merged_into": "{survivor_id}", "reason": "dedup_merge"}}',
                            dup_id
                        )

                    # Merge in AGE graph
                    await self._merge_age_nodes(conn, survivor_id, canonical_name, entity_type, duplicate_ids)

                    merged_count += len(duplicate_ids)
                    print(f"    → Merged {len(duplicate_ids)} duplicate(s) of '{canonical_name}' ({entity_type})")

                except Exception as e:
                    errors.append(f"Merge error for {dup_group['canonical_name']}: {str(e)}")

        return {
            "duplicate_groups_found": len(duplicates) if duplicates else 0,
            "entities_merged": merged_count,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _merge_age_nodes(
        self,
        conn,
        survivor_id: str,
        canonical_name: str,
        entity_type: str,
        duplicate_ids: List[str]
    ):
        """Merge duplicate nodes in Apache AGE graph"""
        try:
            await conn.execute("LOAD 'age'")
            await conn.execute("SET search_path = ag_catalog, '$user', public")

            # Remove duplicate nodes from AGE (relationships already re-pointed in metadata)
            for dup_id in duplicate_ids:
                try:
                    cypher = f"""
                    SELECT * FROM cypher('{settings.graph_name}', $$
                        MATCH (n {{id: '{dup_id}'}})
                        DETACH DELETE n
                    $$) as (result agtype)
                    """
                    await conn.execute(cypher)
                except Exception:
                    # Node may not exist in AGE graph
                    pass

        except Exception as e:
            print(f"    ⚠ AGE merge warning: {str(e)}")

    # ------------------------------------------------------------------
    # Cross-document entity resolution
    # ------------------------------------------------------------------

    async def find_cross_document_matches(self) -> List[Dict[str, Any]]:
        """
        Find entities in STAGING that match existing TRUSTED entities.
        These should be linked rather than creating new nodes.

        Returns:
            List of match pairs (staging_id, trusted_id, canonical_name)
        """
        matches = []

        async with self.db.get_postgres_connection() as conn:
            # Find STAGING entities that match TRUSTED by name + type
            # canonical_name is in extracted_text (new) or source_sentence (legacy)
            cross_matches = await conn.fetch("""
                SELECT
                    s.entity_id AS staging_id,
                    COALESCE(s.extracted_text, s.source_sentence) AS staging_name,
                    s.entity_type AS staging_type,
                    s.confidence AS staging_confidence,
                    t.entity_id AS trusted_id,
                    COALESCE(t.extracted_text, t.source_sentence) AS trusted_name,
                    t.confidence AS trusted_confidence
                FROM graph_lifecycle s
                JOIN graph_lifecycle t
                    ON LOWER(COALESCE(s.extracted_text, s.source_sentence)) = LOWER(COALESCE(t.extracted_text, t.source_sentence))
                    AND s.entity_type = t.entity_type
                WHERE s.lifecycle_state = $1
                AND t.lifecycle_state = $2
                AND s.entity_id != t.entity_id
            """, LifecycleState.STAGING.value, LifecycleState.TRUSTED.value)

            for match in cross_matches:
                matches.append({
                    "staging_id": str(match["staging_id"]),
                    "staging_name": match["staging_name"],
                    "trusted_id": str(match["trusted_id"]),
                    "trusted_name": match["trusted_name"],
                    "entity_type": match["staging_type"],
                    "staging_confidence": float(match["staging_confidence"]),
                    "trusted_confidence": float(match["trusted_confidence"]),
                })

        if matches:
            print(f"    → Found {len(matches)} cross-document matches with TRUSTED entities")

        return matches

    async def resolve_cross_document_matches(
        self,
        matches: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Resolve cross-document matches by:
        1. Boosting TRUSTED entity confidence (more evidence)
        2. Re-pointing relationships from STAGING to TRUSTED entity
        3. Archiving the STAGING duplicate

        Args:
            matches: List from find_cross_document_matches()

        Returns:
            Resolution statistics
        """
        resolved = 0
        errors = []

        async with self.db.get_postgres_connection() as conn:
            for match in matches:
                try:
                    staging_id = match["staging_id"]
                    trusted_id = match["trusted_id"]

                    # Boost TRUSTED confidence (new evidence from different document)
                    confidence_boost = 0.03
                    await conn.execute("""
                        UPDATE graph_lifecycle
                        SET confidence = LEAST(confidence + $1, 1.0)
                        WHERE entity_id = $2
                    """, confidence_boost, trusted_id)

                    # Re-point relationships
                    await conn.execute("""
                        UPDATE relationship_metadata
                        SET source_entity_id = $1
                        WHERE source_entity_id = $2
                    """, trusted_id, staging_id)

                    await conn.execute("""
                        UPDATE relationship_metadata
                        SET target_entity_id = $1
                        WHERE target_entity_id = $2
                    """, trusted_id, staging_id)

                    # Archive the STAGING duplicate
                    await conn.execute("""
                        UPDATE graph_lifecycle
                        SET lifecycle_state = $1,
                            archived_at = $2,
                            conflicts = conflicts || $3::jsonb
                        WHERE entity_id = $4
                    """,
                        LifecycleState.ARCHIVED.value,
                        datetime.utcnow(),
                        f'{{"merged_into": "{trusted_id}", "reason": "cross_doc_resolution"}}',
                        staging_id
                    )

                    resolved += 1

                except Exception as e:
                    errors.append(f"Resolution error for {match['staging_name']}: {str(e)}")

        return {
            "resolved": resolved,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _entity_key(self, entity: Dict[str, Any]) -> str:
        """Generate dedup key for an entity"""
        name = entity.get("canonical_name", "").lower().strip()
        etype = entity.get("entity_type", "").lower().strip()
        return f"{etype}::{name}"

    def _relationship_key(self, rel: Dict[str, Any]) -> str:
        """Generate dedup key for a relationship"""
        source = rel.get("source_name", "").lower().strip()
        target = rel.get("target_name", "").lower().strip()
        rtype = rel.get("relationship_type", "").upper().strip()
        return f"{source}::{rtype}::{target}"
