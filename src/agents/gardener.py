"""
Gardener Agent

Responsible for:
1. Promoting entities from STAGING to TRUSTED
2. Demoting entities from TRUSTED to ARCHIVED
3. Detecting and resolving conflicts
4. Maintaining graph health
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from src.config import settings
from src.models.schemas import LifecycleState


class GardenerAgent:
    """Manages knowledge graph lifecycle and health"""

    def __init__(self, db_manager):
        self.db = db_manager

    async def promote_entity(
        self,
        entity_id: str,
        reason: str = "manual_promotion"
    ) -> Dict[str, Any]:
        """
        Promote a single entity from STAGING to TRUSTED

        Args:
            entity_id: UUID of entity to promote
            reason: Reason for promotion

        Returns:
            Dictionary with success status and details
        """

        async with self.db.get_postgres_connection() as conn:
            # Check current state
            current_state = await conn.fetchrow(
                "SELECT lifecycle_state, confidence FROM graph_lifecycle WHERE entity_id = $1",
                entity_id
            )

            if not current_state:
                return {
                    "success": False,
                    "error": f"Entity {entity_id} not found"
                }

            if current_state["lifecycle_state"] != LifecycleState.STAGING.value:
                return {
                    "success": False,
                    "error": f"Entity is in {current_state['lifecycle_state']}, not STAGING"
                }

            # Promote to TRUSTED
            await conn.execute("""
                UPDATE graph_lifecycle
                SET lifecycle_state = $1,
                    promoted_at = $2,
                    updated_at = $2
                WHERE entity_id = $3
            """, LifecycleState.TRUSTED.value, datetime.utcnow(), entity_id)

            return {
                "success": True,
                "entity_id": entity_id,
                "previous_state": current_state["lifecycle_state"],
                "new_state": LifecycleState.TRUSTED.value,
                "reason": reason
            }

    async def promote_all_staging(
        self,
        min_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Promote all STAGING entities above confidence threshold to TRUSTED.
        Simple bulk promotion — use promote_with_evidence for stricter rules.

        Args:
            min_confidence: Minimum confidence score required for promotion

        Returns:
            Dictionary with promotion statistics
        """

        async with self.db.get_postgres_connection() as conn:
            # Promote entities
            result = await conn.execute("""
                UPDATE graph_lifecycle
                SET lifecycle_state = $1,
                    promoted_at = $2,
                    updated_at = $2
                WHERE lifecycle_state = $3
                AND confidence >= $4
            """,
                LifecycleState.TRUSTED.value,
                datetime.utcnow(),
                LifecycleState.STAGING.value,
                min_confidence
            )

            # Extract count from result
            promoted_count = int(result.split()[-1]) if result else 0

            # Promote relationships where both entities are TRUSTED
            rel_result = await conn.execute("""
                UPDATE relationship_metadata rm
                SET lifecycle_state = $1,
                    updated_at = $2
                FROM graph_lifecycle source, graph_lifecycle target
                WHERE rm.source_entity_id = source.entity_id
                AND rm.target_entity_id = target.entity_id
                AND source.lifecycle_state = $1
                AND target.lifecycle_state = $1
                AND rm.lifecycle_state = $3
            """,
                LifecycleState.TRUSTED.value,
                datetime.utcnow(),
                LifecycleState.STAGING.value
            )

            rel_promoted_count = int(rel_result.split()[-1]) if rel_result else 0

            return {
                "promoted_count": promoted_count,
                "relationships_promoted": rel_promoted_count,
                "min_confidence": min_confidence,
                "timestamp": datetime.utcnow().isoformat()
            }

    async def promote_with_evidence(
        self,
        min_confidence: float = 0.70,
        min_sources: int = 1
    ) -> Dict[str, Any]:
        """
        Evidence-based promotion from STAGING to TRUSTED.

        Promotion criteria:
        1. Confidence >= min_confidence
        2. Entity must appear in at least min_sources distinct documents
        3. Relationships only promoted when both endpoints are TRUSTED

        Args:
            min_confidence: Minimum confidence threshold (default 0.70)
            min_sources: Minimum number of distinct source documents (default 1)

        Returns:
            Dictionary with promotion statistics and skipped entities
        """

        promoted_entities = 0
        promoted_relationships = 0
        skipped_low_confidence = 0
        skipped_insufficient_sources = 0

        async with self.db.get_postgres_connection() as conn:
            # Get all STAGING entities grouped by canonical name
            candidates = await conn.fetch("""
                SELECT
                    entity_id,
                    entity_type,
                    confidence,
                    COALESCE(extracted_text, source_sentence) AS canonical_name,
                    source_document_id
                FROM graph_lifecycle
                WHERE lifecycle_state = $1
                ORDER BY confidence DESC
            """, LifecycleState.STAGING.value)

            # Group by canonical_name + entity_type to count sources
            name_groups: Dict[str, List] = {}
            for row in candidates:
                key = f"{row['entity_type']}::{(row['canonical_name'] or '').lower()}"
                name_groups.setdefault(key, []).append(row)

            for key, group in name_groups.items():
                # Count distinct documents
                distinct_docs = len(set(
                    row['source_document_id'] for row in group
                    if row['source_document_id']
                ))

                # Best confidence in the group
                best_confidence = max(float(row['confidence']) for row in group)

                if best_confidence < min_confidence:
                    skipped_low_confidence += len(group)
                    continue

                if distinct_docs < min_sources:
                    skipped_insufficient_sources += len(group)
                    continue

                # Promote the highest-confidence entity in this group
                # (others should have been merged by dedup already)
                for row in group:
                    await conn.execute("""
                        UPDATE graph_lifecycle
                        SET lifecycle_state = $1,
                            promoted_at = $2,
                            updated_at = $2
                        WHERE entity_id = $3
                        AND lifecycle_state = $4
                    """,
                        LifecycleState.TRUSTED.value,
                        datetime.utcnow(),
                        row['entity_id'],
                        LifecycleState.STAGING.value
                    )
                    promoted_entities += 1

            # Promote relationships where both endpoints are now TRUSTED
            rel_result = await conn.execute("""
                UPDATE relationship_metadata rm
                SET lifecycle_state = $1,
                    updated_at = $2
                FROM graph_lifecycle source, graph_lifecycle target
                WHERE rm.source_entity_id = source.entity_id
                AND rm.target_entity_id = target.entity_id
                AND source.lifecycle_state = $1
                AND target.lifecycle_state = $1
                AND rm.lifecycle_state = $3
            """,
                LifecycleState.TRUSTED.value,
                datetime.utcnow(),
                LifecycleState.STAGING.value
            )

            promoted_relationships = int(rel_result.split()[-1]) if rel_result else 0

        return {
            "promoted_entities": promoted_entities,
            "promoted_relationships": promoted_relationships,
            "skipped_low_confidence": skipped_low_confidence,
            "skipped_insufficient_sources": skipped_insufficient_sources,
            "min_confidence": min_confidence,
            "min_sources": min_sources,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def demote_entity(
        self,
        entity_id: str,
        reason: str = "manual_demotion"
    ) -> Dict[str, Any]:
        """
        Demote entity from TRUSTED to ARCHIVED

        Args:
            entity_id: UUID of entity to demote
            reason: Reason for demotion

        Returns:
            Dictionary with demotion status
        """

        async with self.db.get_postgres_connection() as conn:
            result = await conn.execute("""
                UPDATE graph_lifecycle
                SET lifecycle_state = $1,
                    archived_at = $2,
                    updated_at = $2
                WHERE entity_id = $3
                AND lifecycle_state = $4
            """,
                LifecycleState.ARCHIVED.value,
                datetime.utcnow(),
                entity_id,
                LifecycleState.TRUSTED.value
            )

            success = int(result.split()[-1]) > 0 if result else False

            return {
                "success": success,
                "entity_id": entity_id,
                "new_state": LifecycleState.ARCHIVED.value if success else None,
                "reason": reason
            }

    async def detect_conflicts(self) -> List[Dict[str, Any]]:
        """
        Detect conflicting facts in the knowledge graph

        Conflicts occur when:
        1. Multiple entities claim same identity (e.g., same name but different IDs)
        2. Contradictory relationships
        3. Rule violations

        Returns:
            List of detected conflicts
        """

        conflicts = []

        async with self.db.get_postgres_connection() as conn:
            # Detect duplicate names (potential entity resolution issues)
            duplicate_names = await conn.fetch("""
                SELECT
                    jsonb_agg(entity_id) as entity_ids,
                    COUNT(*) as count
                FROM (
                    SELECT entity_id,
                           entity_type,
                           jsonb_extract_path_text(properties::jsonb, 'name') as name
                    FROM graph_lifecycle
                    WHERE lifecycle_state = $1
                ) subq
                GROUP BY entity_type, name
                HAVING COUNT(*) > 1
            """, LifecycleState.TRUSTED.value)

            for row in duplicate_names:
                conflicts.append({
                    "type": "duplicate_entity",
                    "entity_ids": row["entity_ids"],
                    "count": row["count"],
                    "severity": "medium"
                })

            # Detect entities with unresolved conflicts flag
            unresolved = await conn.fetch("""
                SELECT entity_id, entity_type, conflicts
                FROM graph_lifecycle
                WHERE resolved = false
                AND lifecycle_state = $1
            """, LifecycleState.TRUSTED.value)

            for row in unresolved:
                conflicts.append({
                    "type": "unresolved_conflict",
                    "entity_id": str(row["entity_id"]),
                    "entity_type": row["entity_type"],
                    "details": row["conflicts"],
                    "severity": "high"
                })

        return conflicts

    async def get_stale_entities(
        self,
        days_threshold: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Find entities that haven't been accessed recently

        Args:
            days_threshold: Number of days without access to consider stale

        Returns:
            List of stale entities
        """

        async with self.db.get_postgres_connection() as conn:
            stale = await conn.fetch("""
                SELECT entity_id, entity_type, last_accessed, access_count
                FROM graph_lifecycle
                WHERE lifecycle_state = $1
                AND (
                    last_accessed < NOW() - INTERVAL '1 day' * $2
                    OR last_accessed IS NULL
                )
                ORDER BY access_count ASC, last_accessed ASC NULLS FIRST
                LIMIT 100
            """, LifecycleState.TRUSTED.value, days_threshold)

            return [
                {
                    "entity_id": str(row["entity_id"]),
                    "entity_type": row["entity_type"],
                    "last_accessed": row["last_accessed"].isoformat() if row["last_accessed"] else None,
                    "access_count": row["access_count"]
                }
                for row in stale
            ]

    async def increase_confidence(
        self,
        entity_id: str,
        delta: float,
        reason: str = "positive_feedback"
    ) -> Dict[str, Any]:
        """
        Increase entity confidence based on positive signals

        Args:
            entity_id: UUID of entity
            delta: Amount to increase confidence (0.0 - 1.0)
            reason: Reason for increase

        Returns:
            Updated confidence information
        """

        async with self.db.get_postgres_connection() as conn:
            result = await conn.fetchrow("""
                UPDATE graph_lifecycle
                SET confidence = LEAST(confidence + $1, 1.0),
                    updated_at = NOW()
                WHERE entity_id = $2
                RETURNING confidence
            """, delta, entity_id)

            return {
                "entity_id": entity_id,
                "new_confidence": float(result["confidence"]) if result else None,
                "delta": delta,
                "reason": reason
            }

    async def decrease_confidence(
        self,
        entity_id: str,
        delta: float,
        reason: str = "negative_feedback"
    ) -> Dict[str, Any]:
        """
        Decrease entity confidence based on negative signals

        Args:
            entity_id: UUID of entity
            delta: Amount to decrease confidence (0.0 - 1.0)
            reason: Reason for decrease

        Returns:
            Updated confidence information
        """

        async with self.db.get_postgres_connection() as conn:
            result = await conn.fetchrow("""
                UPDATE graph_lifecycle
                SET confidence = GREATEST(confidence - $1, 0.0),
                    updated_at = NOW()
                WHERE entity_id = $2
                RETURNING confidence
            """, delta, entity_id)

            # If confidence drops below threshold, consider demotion
            if result and result["confidence"] < settings.confidence_threshold_floor:
                await self.demote_entity(entity_id, reason=f"confidence_below_floor: {reason}")

            return {
                "entity_id": entity_id,
                "new_confidence": float(result["confidence"]) if result else None,
                "delta": -delta,
                "reason": reason
            }
