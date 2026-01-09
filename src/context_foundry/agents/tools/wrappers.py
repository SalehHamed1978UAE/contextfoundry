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
                "evidence": result.evidence.to_dict() if result.evidence and hasattr(result.evidence, 'to_dict') else None,
                "counted_entities": result.counted_entities if hasattr(result, 'counted_entities') else None
            }
        except Exception as e:
            logger.error(f"[TOOL] Aggregation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_knowledge_bundle(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get KG relationships for entities."""
        query = args.get("query", "")
        entity_ids = args.get("entity_ids", [])
        
        try:
            entities = self.semantic_memory.search_entities(query, limit=10)
            
            entity_results = []
            for entity in entities:
                entity_dict = entity.to_dict() if hasattr(entity, 'to_dict') else {"name": str(entity)}
                
                relationships = []
                if hasattr(entity, 'id'):
                    try:
                        rels = self.semantic_memory.get_entity_relationships(entity.id, max_depth=1)
                        relationships = rels[:5] if rels else []
                    except Exception as rel_err:
                        logger.debug(f"[TOOL] Could not get relationships: {rel_err}")
                
                entity_results.append({
                    "entity": entity_dict,
                    "relationships": relationships
                })
            
            return {
                "query": query,
                "entity_ids": entity_ids,
                "results": entity_results[:10]
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
