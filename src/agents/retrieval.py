"""
Retrieval Agent

Responsible for building ContextBundles by querying all three memory layers:
1. Semantic Memory (Knowledge Graph)
2. Episodic Memory (Vector Search + Session)
3. Symbolic Memory (Rules)
"""

import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import settings
from src.models.schemas import (
    ContextBundle,
    UncertaintyReport,
    UncertainItem,
    Recommendation,
    LifecycleState
)
from src.utils.embeddings import DocumentEmbedder


class RetrievalAgent:
    """Builds context bundles from tri-memory architecture"""

    def __init__(self, db_manager, document_embedder: DocumentEmbedder):
        self.db = db_manager
        self.embedder = document_embedder

    async def build_context_bundle(
        self,
        query: str,
        session_id: Optional[str] = None
    ) -> ContextBundle:
        """
        Build a complete context bundle from all memory layers

        Args:
            query: User query
            session_id: Optional session ID for session context

        Returns:
            ContextBundle with all retrieved context and uncertainty report
        """

        start_time = datetime.utcnow()

        # Extract key entities from query (simple keyword extraction for MVP)
        keywords = self._extract_keywords(query)

        # 1. Query Semantic Memory (Graph)
        semantic_entities = await self._query_graph_entities(keywords)
        semantic_relationships = await self._query_graph_relationships(keywords)

        # 2. Query Episodic Memory (Vectors)
        episodic_documents = await self._query_similar_documents(query)

        # 3. Query Symbolic Memory (Rules)
        symbolic_rules = await self._query_applicable_rules(semantic_entities)

        # 4. Query Session Memory (if session_id provided)
        session_context = []
        if session_id:
            session_context = await self._query_session_context(session_id)

        # 5. Build Uncertainty Report
        uncertainty = self._build_uncertainty_report(
            semantic_entities,
            semantic_relationships,
            episodic_documents,
            keywords
        )

        # Calculate latency
        latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return ContextBundle(
            query_text=query,
            session_id=uuid.UUID(session_id) if session_id else None,
            semantic_entities=semantic_entities,
            semantic_relationships=semantic_relationships,
            episodic_documents=episodic_documents,
            symbolic_rules_applied=symbolic_rules,
            session_context=session_context,
            uncertainty=uncertainty,
            retrieval_latency_ms=latency_ms
        )

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract keywords from query for entity matching

        Simple implementation for MVP - just lowercase and split
        """

        # Remove common stop words
        stop_words = {
            'what', 'which', 'who', 'where', 'when', 'how', 'is', 'are',
            'the', 'a', 'an', 'does', 'do', 'did', 'has', 'have', 'had',
            'for', 'to', 'from', 'on', 'with', 'by', 'in', 'of', 'at'
        }

        words = query.lower().split()
        keywords = [w.strip('?.,!') for w in words if w.lower() not in stop_words]

        return keywords

    async def _query_graph_entities(
        self,
        keywords: List[str],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query graph for entities matching keywords

        Args:
            keywords: Search keywords
            limit: Max entities to return

        Returns:
            List of entity dictionaries
        """

        if not keywords:
            return []

        entities = []

        async with self.db.get_postgres_connection() as conn:
            # For MVP, use simple SQL search on entity names
            # In production, would use full-text search or graph query

            for keyword in keywords[:5]:  # Limit keyword explosion
                results = await conn.fetch("""
                    SELECT
                        gl.entity_id,
                        gl.entity_type,
                        gl.lifecycle_state,
                        gl.confidence,
                        gl.source_document_id,
                        COALESCE(gl.extracted_text, gl.source_sentence) AS canonical_name,
                        gl.source_sentence
                    FROM graph_lifecycle gl
                    WHERE gl.lifecycle_state = $1
                    AND (
                        COALESCE(gl.extracted_text, '') ILIKE $2
                        OR COALESCE(gl.source_sentence, '') ILIKE $2
                    )
                    ORDER BY gl.confidence DESC, gl.access_count DESC
                    LIMIT $3
                """, LifecycleState.TRUSTED.value, f'%{keyword}%', limit)

                for row in results:
                    entity_dict = {
                        "entity_id": str(row["entity_id"]),
                        "entity_type": row["entity_type"],
                        "canonical_name": row["canonical_name"],
                        "lifecycle_state": row["lifecycle_state"],
                        "confidence": float(row["confidence"]),
                        "source_document_id": row["source_document_id"],
                        "source_sentence": row["source_sentence"]
                    }

                    # Avoid duplicates
                    if not any(e["entity_id"] == entity_dict["entity_id"] for e in entities):
                        entities.append(entity_dict)

                    # Update access stats
                    await conn.execute("""
                        UPDATE graph_lifecycle
                        SET access_count = access_count + 1,
                            last_accessed = NOW()
                        WHERE entity_id = $1
                    """, row["entity_id"])

        return entities[:limit]

    async def _query_graph_relationships(
        self,
        keywords: List[str],
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Query graph for relationships involving keyword-matching entities

        Args:
            keywords: Search keywords
            limit: Max relationships to return

        Returns:
            List of relationship dictionaries
        """

        if not keywords:
            return []

        relationships = []

        async with self.db.get_postgres_connection() as conn:
            for keyword in keywords[:5]:
                results = await conn.fetch("""
                    SELECT DISTINCT
                        rm.relationship_id,
                        rm.source_entity_id,
                        rm.target_entity_id,
                        rm.relationship_type,
                        rm.confidence,
                        source.entity_type as source_type,
                        COALESCE(source.extracted_text, source.source_sentence) as source_name,
                        target.entity_type as target_type,
                        COALESCE(target.extracted_text, target.source_sentence) as target_name
                    FROM relationship_metadata rm
                    JOIN graph_lifecycle source ON rm.source_entity_id = source.entity_id
                    JOIN graph_lifecycle target ON rm.target_entity_id = target.entity_id
                    WHERE rm.lifecycle_state = $1
                    AND (
                        COALESCE(source.extracted_text, source.source_sentence, '') ILIKE $2
                        OR COALESCE(target.extracted_text, target.source_sentence, '') ILIKE $2
                    )
                    ORDER BY rm.confidence DESC
                    LIMIT $3
                """, LifecycleState.TRUSTED.value, f'%{keyword}%', limit)

                for row in results:
                    rel_dict = {
                        "relationship_id": str(row["relationship_id"]),
                        "source_entity_id": str(row["source_entity_id"]),
                        "target_entity_id": str(row["target_entity_id"]),
                        "relationship_type": row["relationship_type"],
                        "confidence": float(row["confidence"]),
                        "source_type": row["source_type"],
                        "source_name": row["source_name"],  # NEW: Include names
                        "target_type": row["target_type"],
                        "target_name": row["target_name"]   # NEW: Include names
                    }

                    if not any(r["relationship_id"] == rel_dict["relationship_id"] for r in relationships):
                        relationships.append(rel_dict)

        return relationships[:limit]

    async def _query_similar_documents(
        self,
        query: str,
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Query episodic memory for similar documents

        Args:
            query: Search query
            top_k: Number of results (default from settings)

        Returns:
            List of similar document chunks
        """

        if top_k is None:
            top_k = settings.vector_search_top_k

        return await self.embedder.search_similar(query, top_k=top_k)

    async def _query_applicable_rules(
        self,
        entities: List[Dict[str, Any]],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query symbolic rules applicable to retrieved entities

        Args:
            entities: Retrieved entities
            limit: Max rules to return

        Returns:
            List of applicable rules
        """

        if not entities:
            return []

        entity_types = list(set(e["entity_type"] for e in entities))

        async with self.db.get_postgres_connection() as conn:
            results = await conn.fetch("""
                SELECT
                    id,
                    rule_name,
                    rule_type,
                    rule_expression,
                    rule_description,
                    priority,
                    applies_to_entity_types
                FROM symbolic_rules
                WHERE enabled = true
                AND (
                    applies_to_entity_types && $1::varchar[]
                    OR applies_to_entity_types IS NULL
                    OR array_length(applies_to_entity_types, 1) IS NULL
                )
                ORDER BY priority DESC
                LIMIT $2
            """, entity_types, limit)

            return [
                {
                    "rule_id": str(row["id"]),
                    "rule_name": row["rule_name"],
                    "rule_type": row["rule_type"],
                    "expression": row["rule_expression"],
                    "description": row["rule_description"],
                    "priority": row["priority"]
                }
                for row in results
            ]

    async def _query_session_context(
        self,
        session_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query session memory for recent conversation context

        Args:
            session_id: Session identifier
            limit: Max context items to return

        Returns:
            List of recent queries and responses
        """

        async with self.db.get_postgres_connection() as conn:
            results = await conn.fetch("""
                SELECT query_text, response_text, created_at
                FROM session_memory
                WHERE session_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, uuid.UUID(session_id), limit)

            return [
                {
                    "query": row["query_text"],
                    "response": row["response_text"],
                    "timestamp": row["created_at"].isoformat()
                }
                for row in reversed(list(results))  # Return in chronological order
            ]

    def _build_uncertainty_report(
        self,
        entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        documents: List[Dict[str, Any]],
        keywords: List[str]
    ) -> UncertaintyReport:
        """
        Build uncertainty report based on retrieved context

        Args:
            entities: Retrieved entities
            relationships: Retrieved relationships
            documents: Retrieved documents
            keywords: Query keywords

        Returns:
            UncertaintyReport with confidence assessment
        """

        high_conf_facts = 0
        medium_conf_facts = 0
        low_conf_facts = 0
        low_conf_items = []
        uncertainty_reasons = []

        # Analyze entity confidence
        for entity in entities:
            conf = entity.get("confidence", 0.5)

            if conf >= settings.confidence_threshold_high:
                high_conf_facts += 1
            elif conf >= settings.confidence_threshold_medium:
                medium_conf_facts += 1
            else:
                low_conf_facts += 1
                low_conf_items.append(UncertainItem(
                    fact=f"Entity: {entity.get('entity_type')} (ID: {entity.get('entity_id')})",
                    confidence=conf,
                    reason="Low entity confidence score",
                    impact="May affect answer accuracy"
                ))

        # Analyze relationship confidence
        for rel in relationships:
            conf = rel.get("confidence", 0.5)

            if conf >= settings.confidence_threshold_high:
                high_conf_facts += 1
            elif conf >= settings.confidence_threshold_medium:
                medium_conf_facts += 1
            else:
                low_conf_facts += 1

        # Check for missing context
        if len(entities) == 0:
            uncertainty_reasons.append("No matching entities found in knowledge graph")

        if len(relationships) == 0 and len(entities) > 0:
            uncertainty_reasons.append("Entities found but no relationships - limited context")

        if len(documents) == 0:
            uncertainty_reasons.append("No similar documents found in episodic memory")

        # Calculate overall confidence
        total_facts = high_conf_facts + medium_conf_facts + low_conf_facts

        if total_facts == 0:
            overall_confidence = 0.0
            recommendation = Recommendation.INSUFFICIENT_CONTEXT
        else:
            # Weighted average
            overall_confidence = (
                (high_conf_facts * 0.9) +
                (medium_conf_facts * 0.7) +
                (low_conf_facts * 0.4)
            ) / total_facts

            if overall_confidence >= settings.confidence_threshold_high:
                recommendation = Recommendation.PROCEED
            elif overall_confidence >= settings.confidence_threshold_low:
                recommendation = Recommendation.CAUTION
            else:
                recommendation = Recommendation.INSUFFICIENT_CONTEXT

        return UncertaintyReport(
            overall_confidence=overall_confidence,
            recommendation=recommendation,
            high_confidence_facts=high_conf_facts,
            medium_confidence_facts=medium_conf_facts,
            low_confidence_facts=low_conf_facts,
            low_confidence_items=low_conf_items[:5],  # Top 5
            unresolved_entities=[],  # TODO: Implement entity resolution
            missing_relationships=[],
            stale_facts=[],
            uncertainty_reasons=uncertainty_reasons
        )
