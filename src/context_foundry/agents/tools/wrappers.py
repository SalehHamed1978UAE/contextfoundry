"""Tool wrappers that call existing Context Foundry services."""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from ..entity_resolver import EntityResolver
from ...aggregation.service import AggregationService
from ...memory.episodic import EpisodicMemory
from ...memory.semantic import SemanticMemory
from ...models.schema import set_tenant_context

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tools by calling existing services."""
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        set_tenant_context(session, tenant_id)
        
        self.entity_resolver = EntityResolver(session=session, tenant_id=tenant_id)
        self.agg_service = AggregationService(session, UUID(tenant_id))
        self.episodic_memory = EpisodicMemory(session=session, tenant_id=tenant_id)
        self.semantic_memory = SemanticMemory(session=session, tenant_id=tenant_id)
    
    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return results."""
        logger.info(f"[TOOL] Executing {tool_name} with args: {arguments}")
        
        if tool_name == "resolve_entities":
            return self._resolve_entities(arguments)
        elif tool_name == "run_aggregation":
            return self._run_aggregation(arguments)
        elif tool_name == "get_knowledge_bundle":
            return self._get_knowledge_bundle(arguments)
        elif tool_name == "search_documents":
            return self._search_documents(arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    def _resolve_entities(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap EntityResolver.resolve()"""
        names = args.get("names", [])
        results = []
        for name in names:
            try:
                result = self.entity_resolver.resolve(name)
                results.append({
                    "query": name,
                    "resolved": result.entity.to_dict() if result.entity else None,
                    "confidence": result.confidence,
                    "needs_disambiguation": result.needs_disambiguation,
                    "candidates": [c.to_dict() for c in result.candidates[:3]]
                })
            except Exception as e:
                logger.error(f"[TOOL] Entity resolution failed for '{name}': {e}")
                results.append({
                    "query": name,
                    "resolved": None,
                    "confidence": 0.0,
                    "needs_disambiguation": False,
                    "candidates": [],
                    "error": str(e)
                })
        return {"entities": results}
    
    def _run_aggregation(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap AggregationService.handle_query()"""
        question = args.get("question", "")
        anchor_entities = args.get("anchor_entities", [])
        
        formatted_anchors = []
        for e in anchor_entities:
            if isinstance(e, dict) and e.get("resolved"):
                resolved = e["resolved"]
                formatted_anchors.append({
                    "entity_id": resolved.get("entity_id") or resolved.get("id"),
                    "name": resolved.get("name"),
                    "entity_type": resolved.get("entity_type")
                })
        
        try:
            result = self.agg_service.handle_query(
                question,
                anchor_entities=formatted_anchors if formatted_anchors else None
            )
            
            if result is None:
                return {"success": False, "message": "Not recognized as aggregation query"}
            
            return {
                "success": result.is_success,
                "result_kind": result.result_kind.value if result.result_kind else None,
                "value": result.value,
                "unit": result.unit,
                "display_text": result.display_text,
                "evidence_envelope": result.evidence_envelope.to_dict() if result.evidence_envelope and hasattr(result.evidence_envelope, 'to_dict') else None,
                "counted_entities": getattr(result, 'counted_entities', []) or []
            }
        except Exception as e:
            logger.error(f"[TOOL] Aggregation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_knowledge_bundle(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get KG relationships for entities using direct SQL."""
        from sqlalchemy import text as sql_text
        
        query = args.get("query", "")
        entity_ids = args.get("entity_ids", [])
        
        try:
            results = []
            
            # If entity_ids provided, fetch relationships directly
            for entity_id in entity_ids:
                try:
                    # Get entity info
                    entity_sql = sql_text("""
                        SELECT id, name, entity_type, description
                        FROM entities WHERE id = :eid AND tenant_id = :tid
                    """)
                    entity_row = self.session.execute(entity_sql, {
                        "eid": entity_id, "tid": self.tenant_id
                    }).fetchone()
                    
                    if not entity_row:
                        continue
                    
                    entity_info = {
                        "id": str(entity_row.id),
                        "name": entity_row.name,
                        "type": entity_row.entity_type
                    }
                    
                    # Get outgoing relationships
                    rel_sql = sql_text("""
                        SELECT r.relationship_type, e2.name as target_name, e2.entity_type as target_type
                        FROM relationships r
                        JOIN entities e2 ON r.target_id = e2.id
                        WHERE r.source_id = :eid AND r.tenant_id = :tid
                        ORDER BY r.relationship_type
                        LIMIT 20
                    """)
                    rel_rows = self.session.execute(rel_sql, {
                        "eid": entity_id, "tid": self.tenant_id
                    }).fetchall()
                    
                    relationships = [
                        {"type": r.relationship_type, "target": r.target_name, "target_type": r.target_type}
                        for r in rel_rows
                    ]
                    
                    results.append({
                        "entity": entity_info,
                        "relationships": relationships
                    })
                except Exception as ent_err:
                    logger.debug(f"[TOOL] Entity {entity_id} lookup failed: {ent_err}")
            
            # Also search by query if no entity_ids or as supplement
            if query and not results:
                try:
                    # Search for entities matching query
                    search_sql = sql_text("""
                        SELECT id, name, entity_type FROM entities
                        WHERE tenant_id = :tid AND LOWER(name) LIKE :pattern
                        LIMIT 5
                    """)
                    search_rows = self.session.execute(search_sql, {
                        "tid": self.tenant_id, "pattern": f"%{query.lower()}%"
                    }).fetchall()
                    
                    for row in search_rows:
                        rel_sql = sql_text("""
                            SELECT r.relationship_type, e2.name as target_name
                            FROM relationships r
                            JOIN entities e2 ON r.target_id = e2.id
                            WHERE r.source_id = :eid AND r.tenant_id = :tid
                            LIMIT 15
                        """)
                        rel_rows = self.session.execute(rel_sql, {
                            "eid": str(row.id), "tid": self.tenant_id
                        }).fetchall()
                        
                        results.append({
                            "entity": {"id": str(row.id), "name": row.name, "type": row.entity_type},
                            "relationships": [{"type": r.relationship_type, "target": r.target_name} for r in rel_rows]
                        })
                except Exception as search_err:
                    logger.debug(f"[TOOL] Search failed: {search_err}")
            
            return {
                "query": query,
                "entity_ids": entity_ids,
                "results": results
            }
        except Exception as e:
            logger.error(f"[TOOL] Knowledge bundle failed: {e}")
            return {"query": query, "entity_ids": entity_ids, "results": [], "error": str(e)}
    
    def _search_documents(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap EpisodicMemory.search_similar()"""
        query = args.get("query", "")
        limit = args.get("limit", 5)
        
        try:
            results = self.episodic_memory.search_similar(query, limit=limit)
            
            return {
                "query": query,
                "chunks": [
                    {
                        "text": r.get("content", r.get("text", ""))[:500],
                        "document": r.get("source_document"),
                        "similarity": r.get("similarity", 0)
                    }
                    for r in results
                ]
            }
        except Exception as e:
            logger.error(f"[TOOL] Document search failed: {e}")
            return {"query": query, "chunks": [], "error": str(e)}
