"""
Graph Loader Agent

Responsible for loading structured data into the knowledge graph.
All data starts in STAGING lifecycle state with initial confidence scores.
"""

import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import settings
from src.models.schemas import EntityMetadata, RelationshipMetadata, LifecycleState


class GraphLoaderAgent:
    """Loads structured data into Apache AGE graph and metadata tables"""

    def __init__(self, db_manager):
        self.db = db_manager

    async def load_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Load entities into graph and metadata tables

        Args:
            entities: List of entity dictionaries with id, type, name, properties

        Returns:
            Dictionary with loaded_count and entity_ids
        """
        loaded_ids = []
        errors = []

        async with self.db.get_postgres_connection() as conn:
            for entity in entities:
                try:
                    entity_id = entity.get("id") or str(uuid.uuid4())
                    entity_type = entity["type"]
                    entity_name = entity["name"]
                    properties = entity.get("properties", {})

                    # 1. Insert into Apache AGE graph
                    await self._create_graph_node(
                        conn,
                        entity_id,
                        entity_type,
                        entity_name,
                        properties
                    )

                    # 2. Insert metadata into graph_lifecycle table
                    await self._insert_entity_metadata(
                        conn,
                        entity_id,
                        entity_type,
                        entity_name
                    )

                    loaded_ids.append(entity_id)

                except Exception as e:
                    errors.append({
                        "entity": entity.get("name", "unknown"),
                        "error": str(e)
                    })

        return {
            "loaded_count": len(loaded_ids),
            "entity_ids": loaded_ids,
            "errors": errors
        }

    async def _create_graph_node(
        self,
        conn,
        entity_id: str,
        entity_type: str,
        entity_name: str,
        properties: Dict[str, Any]
    ):
        """Create a node in Apache AGE graph"""

        # Prepare properties for Cypher
        props_dict = {
            "id": entity_id,
            "name": entity_name,
            **properties
        }

        # Convert Python dict to JSON string for AGE
        props_json = json.dumps(props_dict).replace("'", "\\'")

        # Build Cypher CREATE query
        # Note: AGE requires specific syntax for CREATE
        await conn.execute("LOAD 'age';")
        await conn.execute("SET search_path = ag_catalog, '$user', public;")

        cypher_query = f"""
        SELECT * FROM cypher('{settings.graph_name}', $$
            CREATE (n:{entity_type} {{
                id: '{entity_id}',
                name: '{entity_name}',
                properties: '{props_json}'
            }})
            RETURN n
        $$) as (node agtype);
        """

        await conn.execute(cypher_query)

    async def _insert_entity_metadata(
        self,
        conn,
        entity_id: str,
        entity_type: str,
        entity_name: str
    ):
        """Insert entity metadata into graph_lifecycle table"""

        query = """
        INSERT INTO graph_lifecycle (
            entity_id,
            entity_type,
            lifecycle_state,
            confidence,
            source_document_id,
            source_sentence,
            extraction_method,
            extraction_confidence
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (entity_id) DO NOTHING
        """

        await conn.execute(
            query,
            entity_id,
            entity_type,
            LifecycleState.STAGING.value,
            0.95,  # High confidence for directly loaded data
            "synthetic_data_walking_skeleton",
            entity_name,  # Store entity name for searchability
            "direct_ingest",
            0.95
        )

    async def load_relationships(
        self,
        relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Load relationships into graph

        Args:
            relationships: List of relationship dicts with source_id, target_id, type

        Returns:
            Dictionary with loaded_count and relationship_ids
        """
        loaded_ids = []
        errors = []

        async with self.db.get_postgres_connection() as conn:
            for rel in relationships:
                try:
                    rel_id = rel.get("id") or str(uuid.uuid4())
                    source_id = rel["source_id"]
                    target_id = rel["target_id"]
                    rel_type = rel["type"]
                    properties = rel.get("properties", {})

                    # 1. Create relationship in graph
                    await self._create_graph_relationship(
                        conn,
                        rel_id,
                        source_id,
                        target_id,
                        rel_type,
                        properties
                    )

                    # 2. Insert metadata
                    await self._insert_relationship_metadata(
                        conn,
                        rel_id,
                        source_id,
                        target_id,
                        rel_type
                    )

                    loaded_ids.append(rel_id)

                except Exception as e:
                    errors.append({
                        "relationship": f"{source_id} -> {target_id}",
                        "error": str(e)
                    })

        return {
            "loaded_count": len(loaded_ids),
            "relationship_ids": loaded_ids,
            "errors": errors
        }

    async def _create_graph_relationship(
        self,
        conn,
        rel_id: str,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: Dict[str, Any]
    ):
        """Create a relationship in Apache AGE graph"""

        props_json = json.dumps(properties).replace("'", "\\'")

        await conn.execute("LOAD 'age';")
        await conn.execute("SET search_path = ag_catalog, '$user', public;")

        cypher_query = f"""
        SELECT * FROM cypher('{settings.graph_name}', $$
            MATCH (a {{id: '{source_id}'}}), (b {{id: '{target_id}'}})
            CREATE (a)-[r:{rel_type} {{
                id: '{rel_id}',
                properties: '{props_json}'
            }}]->(b)
            RETURN r
        $$) as (relationship agtype);
        """

        await conn.execute(cypher_query)

    async def _insert_relationship_metadata(
        self,
        conn,
        rel_id: str,
        source_id: str,
        target_id: str,
        rel_type: str
    ):
        """Insert relationship metadata into relationship_metadata table"""

        query = """
        INSERT INTO relationship_metadata (
            relationship_id,
            source_entity_id,
            target_entity_id,
            relationship_type,
            lifecycle_state,
            confidence,
            source_document_id
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (relationship_id) DO NOTHING
        """

        await conn.execute(
            query,
            rel_id,
            source_id,
            target_id,
            rel_type,
            LifecycleState.STAGING.value,
            0.95,  # High confidence for directly loaded data
            "synthetic_data_walking_skeleton"
        )

    async def load_symbolic_rules(
        self,
        rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Load symbolic rules into symbolic_rules table

        Args:
            rules: List of rule dictionaries

        Returns:
            Dictionary with loaded_count and rule_ids
        """
        loaded_ids = []
        errors = []

        async with self.db.get_postgres_connection() as conn:
            for rule in rules:
                try:
                    rule_id = rule.get("id") or str(uuid.uuid4())
                    rule_name = rule["name"]
                    rule_type = rule["type"]
                    expression = json.dumps(rule.get("expression", {}))
                    description = rule.get("description", "")
                    priority = rule.get("priority", 0)
                    applies_to = rule.get("applies_to", [])

                    query = """
                    INSERT INTO symbolic_rules (
                        id,
                        rule_name,
                        rule_type,
                        rule_expression,
                        rule_description,
                        priority,
                        applies_to_entity_types,
                        enabled
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (rule_name) DO NOTHING
                    RETURNING id
                    """

                    result = await conn.fetchval(
                        query,
                        rule_id,
                        rule_name,
                        rule_type,
                        expression,
                        description,
                        priority,
                        applies_to,
                        True
                    )

                    if result:
                        loaded_ids.append(result)

                except Exception as e:
                    errors.append({
                        "rule": rule.get("name", "unknown"),
                        "error": str(e)
                    })

        return {
            "loaded_count": len(loaded_ids),
            "rule_ids": loaded_ids,
            "errors": errors
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Get loading statistics"""

        async with self.db.get_postgres_connection() as conn:
            # Count entities by lifecycle state
            entity_stats = await conn.fetch("""
                SELECT lifecycle_state, COUNT(*) as count
                FROM graph_lifecycle
                GROUP BY lifecycle_state
            """)

            # Count relationships
            rel_count = await conn.fetchval("""
                SELECT COUNT(*) FROM relationship_metadata
            """)

            # Count rules
            rule_count = await conn.fetchval("""
                SELECT COUNT(*) FROM symbolic_rules
            """)

            return {
                "entities": {row["lifecycle_state"]: row["count"] for row in entity_stats},
                "relationships": rel_count or 0,
                "rules": rule_count or 0
            }
