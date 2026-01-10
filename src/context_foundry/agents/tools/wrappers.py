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
        elif tool_name == "discover_relationships":
            return self._discover_relationships(arguments)
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
        """Get ALL KG relationships for entities using direct SQL.
        
        Returns comprehensive data including relationship_summary with counts by type.
        """
        from sqlalchemy import text as sql_text
        from collections import Counter
        
        query = args.get("query", "")
        entity_ids = args.get("entity_ids", [])
        
        try:
            results = []
            
            # If entity_ids provided, fetch ALL relationships (no limit)
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
                    
                    # Get ALL outgoing relationships (no limit)
                    rel_sql = sql_text("""
                        SELECT r.relationship_type, e2.name as target_name, e2.entity_type as target_type
                        FROM relationships r
                        JOIN entities e2 ON r.target_id = e2.id
                        WHERE r.source_id = :eid AND r.tenant_id = :tid
                        ORDER BY r.relationship_type, e2.name
                    """)
                    rel_rows = self.session.execute(rel_sql, {
                        "eid": entity_id, "tid": self.tenant_id
                    }).fetchall()
                    
                    relationships = [
                        {"type": r.relationship_type, "target": r.target_name, "target_type": r.target_type}
                        for r in rel_rows
                    ]
                    
                    # Create relationship_summary with counts by type
                    type_counts = Counter(r.relationship_type for r in rel_rows)
                    relationship_summary = {
                        rel_type: {
                            "count": count,
                            "targets": [r["target"] for r in relationships if r["type"] == rel_type]
                        }
                        for rel_type, count in type_counts.items()
                    }
                    
                    results.append({
                        "entity": entity_info,
                        "relationship_summary": relationship_summary,
                        "total_relationships": len(relationships),
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
        """Wrap EpisodicMemory.search_similar() with text fallback."""
        from sqlalchemy import text as sql_text
        
        query = args.get("query", "")
        limit = args.get("limit", 5)
        
        try:
            results = self.episodic_memory.search_similar(query, limit=limit)
            
            if results:
                logger.info(f"[TOOL] Vector search returned {len(results)} chunks")
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
            
            logger.info(f"[TOOL] Vector search returned 0 chunks, falling back to text search")
            import re
            words = re.findall(r'\b[a-zA-Z]+\b', query.lower())
            stopwords = {'what', 'where', 'when', 'which', 'who', 'whom', 'whose', 'that', 'this', 
                         'these', 'those', 'have', 'has', 'had', 'does', 'did', 'will', 'would', 
                         'could', 'should', 'might', 'must', 'shall', 'from', 'with', 'about',
                         'into', 'through', 'during', 'before', 'after', 'above', 'below',
                         'between', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
                         'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more', 'most',
                         'other', 'some', 'such', 'only', 'own', 'same', 'than', 'very',
                         'just', 'also', 'now', 'the', 'and', 'but', 'for', 'are', 'was', 'were',
                         'been', 'being', 'have', 'has', 'had', 'having', 'does', 'doing',
                         'would', 'could', 'should', 'might', 'many', 'much', 'any'}
            
            # Expand abbreviations to full forms for better matching
            abbreviation_expansions = {
                'ceo': 'chief executive officer',
                'cto': 'chief technology officer',
                'cfo': 'chief financial officer',
                'coo': 'chief operating officer',
                'cdo': 'chief data officer',
                'vp': 'vice president',
                'svp': 'senior vice president',
                'evp': 'executive vice president',
            }
            
            keywords = [w for w in words if len(w) >= 3 and w not in stopwords]
            
            # Separate regular keywords from abbreviation expansions
            regular_keywords = []
            abbreviation_alternatives = []  # list of (abbrev, expansion) tuples
            
            for kw in keywords:
                if kw in abbreviation_expansions:
                    abbreviation_alternatives.append((kw, abbreviation_expansions[kw]))
                    logger.info(f"[TOOL] Will expand '{kw}' to '{abbreviation_expansions[kw]}' (OR)")
                else:
                    regular_keywords.append(kw)
            
            if not regular_keywords and not abbreviation_alternatives:
                return {"query": query, "chunks": [], "fallback": "no_keywords"}
            
            # Build SQL with: (regular_keywords AND) AND (abbrev1 OR expansion1) AND (abbrev2 OR expansion2)
            params = {"tid": self.tenant_id, "lim": limit}
            
            conditions = []
            param_idx = 0
            
            # Add regular keyword conditions (AND between them)
            for kw in regular_keywords:
                conditions.append(f"LOWER(dc.text) LIKE :kw{param_idx}")
                params[f"kw{param_idx}"] = f"%{kw}%"
                param_idx += 1
            
            # Add abbreviation alternatives (abbrev OR expansion for each)
            for abbrev, expansion in abbreviation_alternatives:
                conditions.append(f"(LOWER(dc.text) LIKE :kw{param_idx} OR LOWER(dc.text) LIKE :kw{param_idx+1})")
                params[f"kw{param_idx}"] = f"%{abbrev}%"
                params[f"kw{param_idx+1}"] = f"%{expansion}%"
                param_idx += 2
            
            where_clause = " AND ".join(conditions) if conditions else "TRUE"
            
            fallback_sql = sql_text(f"""
                SELECT dc.id, dc.text
                FROM document_chunks dc
                WHERE dc.tenant_id = :tid
                AND ({where_clause})
                ORDER BY dc.created_at DESC
                LIMIT :lim
            """)
            
            rows = self.session.execute(fallback_sql, params).fetchall()
            logger.info(f"[TOOL] Text fallback returned {len(rows)} chunks for keywords: {keywords}")
            
            return {
                "query": query,
                "chunks": [
                    {
                        "text": row.text[:1500] if row.text else "",
                        "document": "Document chunk",
                        "similarity": 0.5
                    }
                    for row in rows
                ],
                "fallback": "text_search"
            }
        except Exception as e:
            logger.error(f"[TOOL] Document search failed: {e}")
            try:
                self.session.rollback()
            except:
                pass
            return {"query": query, "chunks": [], "error": str(e)}
    
    def _discover_relationships(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Discover all relationship types for an entity with counts.
        
        Returns a list of relationship types with their counts, helping the agent
        understand what data is available before making counting decisions.
        """
        from sqlalchemy import text as sql_text
        from uuid import UUID as UUID_type
        
        entity_id = args.get("entity_id", "")
        
        if not entity_id:
            return {"error": "entity_id is required. Call resolve_entities first to get the UUID.", "relationship_types": []}
        
        # Validate UUID format before running SQL
        try:
            UUID_type(entity_id)
        except (ValueError, AttributeError):
            return {
                "error": f"'{entity_id}' is not a valid UUID. You must call resolve_entities first to get the entity_id.",
                "entity_id": entity_id,
                "relationship_types": [],
                "hint": "Call resolve_entities(['name']) first, then use the returned entity_id"
            }
        
        try:
            # Get entity name for context
            entity_sql = sql_text("""
                SELECT name, entity_type FROM entities 
                WHERE id = :eid AND tenant_id = :tid
            """)
            entity_row = self.session.execute(entity_sql, {
                "eid": entity_id, "tid": self.tenant_id
            }).fetchone()
            
            entity_name = entity_row.name if entity_row else "Unknown"
            entity_type = entity_row.entity_type if entity_row else "Unknown"
            
            # Count OUTGOING relationships (entity is the source)
            outgoing_sql = sql_text("""
                SELECT relationship_type, COUNT(*) as count
                FROM relationships
                WHERE tenant_id = :tid
                  AND source_id = :eid
                  AND lifecycle_state = 'TRUSTED'
                GROUP BY relationship_type
                ORDER BY count DESC
            """)
            outgoing_rows = self.session.execute(outgoing_sql, {
                "tid": self.tenant_id, "eid": entity_id
            }).fetchall()
            
            outgoing = [
                {"type": r.relationship_type, "count": r.count}
                for r in outgoing_rows
            ]
            
            # Count INCOMING relationships (entity is the target)
            incoming_sql = sql_text("""
                SELECT relationship_type, COUNT(*) as count
                FROM relationships
                WHERE tenant_id = :tid
                  AND target_id = :eid
                  AND lifecycle_state = 'TRUSTED'
                GROUP BY relationship_type
                ORDER BY count DESC
            """)
            incoming_rows = self.session.execute(incoming_sql, {
                "tid": self.tenant_id, "eid": entity_id
            }).fetchall()
            
            incoming = [
                {"type": r.relationship_type, "count": r.count}
                for r in incoming_rows
            ]
            
            logger.info(f"[TOOL] discover_relationships for {entity_name}: outgoing={outgoing}, incoming={incoming}")
            
            return {
                "entity_id": entity_id,
                "entity_name": entity_name,
                "entity_type": entity_type,
                "outgoing": outgoing,
                "incoming": incoming,
                "total_outgoing": len(outgoing),
                "total_incoming": len(incoming)
            }
        except Exception as e:
            logger.error(f"[TOOL] discover_relationships failed: {e}")
            try:
                self.session.rollback()
            except:
                pass
            return {"entity_id": entity_id, "relationship_types": [], "error": str(e)}
