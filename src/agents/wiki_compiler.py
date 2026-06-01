"""
Wiki Compiler — generates human-readable markdown pages from graph entities.

Pure SQL + string formatting, no LLM required.
Aggregates TRUSTED entities and their relationships into wiki-style pages.
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


class WikiCompiler:
    """Compiles entity data into markdown wiki pages."""

    def __init__(self, db_manager):
        self.db = db_manager

    async def ensure_table(self) -> None:
        """Create the wiki_pages table if it doesn't exist."""
        async with self.db.get_postgres_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS wiki_pages (
                    id UUID PRIMARY KEY,
                    entity_type VARCHAR(50) NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    markdown TEXT NOT NULL,
                    entity_ids UUID[] NOT NULL,
                    source_document_ids TEXT[],
                    confidence_avg FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(entity_type, title)
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_wiki_entity_type
                ON wiki_pages(entity_type)
            """)

    async def compile_entity_page(
        self, entity_type: str, entity_name: str
    ) -> Dict:
        """
        Compile a wiki page for a single entity.

        Queries TRUSTED entities matching the name, gathers relationships,
        and builds a markdown page.
        """
        async with self.db.get_postgres_connection() as conn:
            # 1. Find all TRUSTED entities matching the name
            entities = await conn.fetch(
                """SELECT entity_id, entity_type, confidence,
                          extracted_text, source_document_id, source_sentence
                   FROM graph_lifecycle
                   WHERE lifecycle_state = 'TRUSTED'
                     AND entity_type = $1
                     AND extracted_text ILIKE $2
                   ORDER BY confidence DESC""",
                entity_type,
                entity_name,
            )

            if not entities:
                return {"compiled": False, "reason": "no matching entities"}

            entity_ids = [r["entity_id"] for r in entities]
            avg_confidence = sum(float(r["confidence"]) for r in entities) / len(entities)
            source_doc_ids = list(
                {r["source_document_id"] for r in entities if r["source_document_id"]}
            )

            # 2. Find relationships involving these entities
            relationships = await conn.fetch(
                """SELECT rm.relationship_type, rm.confidence,
                          src.extracted_text AS source_name,
                          src.entity_type AS source_type,
                          tgt.extracted_text AS target_name,
                          tgt.entity_type AS target_type,
                          rm.source_entity_id, rm.target_entity_id
                   FROM relationship_metadata rm
                   JOIN graph_lifecycle src ON rm.source_entity_id = src.entity_id
                   JOIN graph_lifecycle tgt ON rm.target_entity_id = tgt.entity_id
                   WHERE (rm.source_entity_id = ANY($1::uuid[])
                          OR rm.target_entity_id = ANY($1::uuid[]))
                     AND rm.lifecycle_state = 'TRUSTED'
                   ORDER BY rm.confidence DESC""",
                entity_ids,
            )

            # 3. Build markdown
            best_entity = entities[0]
            title = best_entity["extracted_text"]

            lines = [
                f"# {title} ({entity_type})",
                f"**Confidence**: {avg_confidence:.0%}  |  **Sources**: {len(source_doc_ids)} document(s)",
                "",
                "## Overview",
            ]

            if best_entity["source_sentence"]:
                lines.append(best_entity["source_sentence"])
            else:
                lines.append(f"{title} is a {entity_type} entity in the knowledge graph.")
            lines.append("")

            # Relationships section
            if relationships:
                lines.append("## Relationships")
                for rel in relationships:
                    rel_conf = float(rel["confidence"])
                    if rel["source_entity_id"] in entity_ids:
                        lines.append(
                            f"- **{rel['relationship_type']}** -> "
                            f"{rel['target_name']} ({rel['target_type']}) "
                            f"(confidence: {rel_conf:.0%})"
                        )
                    else:
                        lines.append(
                            f"- **{rel['relationship_type']}** <- "
                            f"{rel['source_name']} ({rel['source_type']}) "
                            f"(confidence: {rel_conf:.0%})"
                        )
                lines.append("")

            # Source documents section
            if source_doc_ids:
                lines.append("## Source Documents")
                for doc_id in source_doc_ids:
                    # Try to get document title
                    doc_row = await conn.fetchrow(
                        """SELECT DISTINCT document_title
                           FROM document_embeddings
                           WHERE document_id = $1
                           LIMIT 1""",
                        doc_id,
                    )
                    doc_title = doc_row["document_title"] if doc_row else doc_id
                    lines.append(f"- {doc_id}: {doc_title}")
                lines.append("")

            markdown = "\n".join(lines)

            # 4. Upsert into wiki_pages
            await conn.execute(
                """INSERT INTO wiki_pages
                       (id, entity_type, title, markdown, entity_ids,
                        source_document_ids, confidence_avg, updated_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (entity_type, title) DO UPDATE
                   SET markdown = EXCLUDED.markdown,
                       entity_ids = EXCLUDED.entity_ids,
                       source_document_ids = EXCLUDED.source_document_ids,
                       confidence_avg = EXCLUDED.confidence_avg,
                       updated_at = EXCLUDED.updated_at""",
                uuid4(),
                entity_type,
                title,
                markdown,
                entity_ids,
                source_doc_ids,
                avg_confidence,
                datetime.utcnow(),
            )

        return {
            "compiled": True,
            "title": title,
            "entity_type": entity_type,
            "entities_count": len(entities),
            "relationships_count": len(relationships),
            "confidence_avg": avg_confidence,
        }

    async def compile_all(self, entity_type: str = None) -> Dict:
        """
        Compile wiki pages for all distinct TRUSTED entities.

        Args:
            entity_type: Optional filter by entity type.

        Returns:
            Stats on compiled pages.
        """
        async with self.db.get_postgres_connection() as conn:
            if entity_type:
                rows = await conn.fetch(
                    """SELECT DISTINCT entity_type, extracted_text
                       FROM graph_lifecycle
                       WHERE lifecycle_state = 'TRUSTED'
                         AND entity_type = $1
                         AND extracted_text IS NOT NULL
                       ORDER BY entity_type, extracted_text""",
                    entity_type,
                )
            else:
                rows = await conn.fetch(
                    """SELECT DISTINCT entity_type, extracted_text
                       FROM graph_lifecycle
                       WHERE lifecycle_state = 'TRUSTED'
                         AND extracted_text IS NOT NULL
                       ORDER BY entity_type, extracted_text"""
                )

        compiled = 0
        skipped = 0
        for row in rows:
            result = await self.compile_entity_page(
                row["entity_type"], row["extracted_text"]
            )
            if result.get("compiled"):
                compiled += 1
            else:
                skipped += 1

        return {
            "total_candidates": len(rows),
            "compiled": compiled,
            "skipped": skipped,
        }

    async def get_page(
        self, entity_type: str, title: str
    ) -> Optional[Dict]:
        """Retrieve a compiled wiki page."""
        async with self.db.get_postgres_connection() as conn:
            row = await conn.fetchrow(
                """SELECT id, entity_type, title, markdown, entity_ids,
                          source_document_ids, confidence_avg,
                          created_at, updated_at
                   FROM wiki_pages
                   WHERE entity_type = $1 AND title = $2""",
                entity_type,
                title,
            )
            if not row:
                return None
            return {
                "id": str(row["id"]),
                "entity_type": row["entity_type"],
                "title": row["title"],
                "markdown": row["markdown"],
                "entity_ids": [str(eid) for eid in row["entity_ids"]],
                "source_document_ids": row["source_document_ids"],
                "confidence_avg": float(row["confidence_avg"]) if row["confidence_avg"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }

    async def list_pages(
        self, entity_type: str = None, limit: int = 50, offset: int = 0
    ) -> Dict:
        """List compiled wiki pages with optional type filter."""
        async with self.db.get_postgres_connection() as conn:
            if entity_type:
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM wiki_pages WHERE entity_type = $1",
                    entity_type,
                )
                rows = await conn.fetch(
                    """SELECT id, entity_type, title, confidence_avg, updated_at
                       FROM wiki_pages
                       WHERE entity_type = $1
                       ORDER BY title
                       LIMIT $2 OFFSET $3""",
                    entity_type,
                    limit,
                    offset,
                )
            else:
                total = await conn.fetchval("SELECT COUNT(*) FROM wiki_pages")
                rows = await conn.fetch(
                    """SELECT id, entity_type, title, confidence_avg, updated_at
                       FROM wiki_pages
                       ORDER BY entity_type, title
                       LIMIT $1 OFFSET $2""",
                    limit,
                    offset,
                )

        return {
            "pages": [
                {
                    "id": str(r["id"]),
                    "entity_type": r["entity_type"],
                    "title": r["title"],
                    "confidence_avg": float(r["confidence_avg"]) if r["confidence_avg"] else None,
                    "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                }
                for r in rows
            ],
            "total": total or 0,
            "limit": limit,
            "offset": offset,
        }
