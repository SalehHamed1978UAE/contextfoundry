"""Tool wrappers that call existing Context Foundry services."""
import logging
import re
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from ..entity_resolver import EntityResolver
from ...aggregation.service import AggregationService
from ...memory.episodic import EpisodicMemory
from ...memory.semantic import SemanticMemory
from ...models.schema import set_tenant_context

logger = logging.getLogger(__name__)


def extract_person_names(text: str) -> List[str]:
    """
    Extract person names from a query string using regex patterns.
    
    Handles:
    - Possessive form: "Jennifer Lee's department" → "Jennifer Lee"
    - Capitalized names: "What department does Jennifer Lee work in?" → "Jennifer Lee"
    - Multiple word names: "Sarah Jane Smith" → "Sarah Jane Smith"
    
    Returns:
        List of extracted person names (without possessive suffixes)
    """
    names = []
    
    # Words that should never start a person name
    excluded_first_words = {
        'what', 'how', 'who', 'when', 'where', 'why', 'which',
        'tell', 'show', 'give', 'find', 'get', 'does', 'do', 'is', 'are',
        'the', 'this', 'that', 'these', 'those', 'a', 'an',
        'compare', 'list', 'describe', 'explain', 'about',
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    }
    
    # Words that indicate NON-person entities (projects, systems, platforms, etc.)
    # These should never be part of a person's name
    excluded_non_person_words = {
        # Technical/System terms
        'system', 'systems', 'platform', 'platforms', 'program', 'programs',
        'project', 'projects', 'network', 'networks', 'hub', 'hubs',
        'lab', 'labs', 'laboratory', 'center', 'centres', 'facility', 'facilities',
        'initiative', 'initiatives', 'service', 'services', 'software', 'solution', 'solutions',
        'technology', 'technologies', 'infrastructure', 'database', 'api', 'framework',
        # Business terms
        'corporation', 'corp', 'company', 'companies', 'enterprise', 'enterprises',
        'group', 'groups', 'division', 'divisions', 'unit', 'units', 'department', 'departments',
        'logistics', 'aerospace', 'energy', 'manufacturing', 'dynamics', 'industries',
        # Location/Facility terms
        'campus', 'plant', 'office', 'headquarters', 'branch', 'site',
        # Product/Project names
        'falcon', 'helios', 'nexgen', 'autonav', 'urbanmesh', 'skylink', 'quantum',
        'uav', 'iot', 'satellite', 'battery', 'storage', 'chain', 'supply',
    }
    
    # Pattern 1: Possessive form - "Name's" or "Names'"
    # Matches: "Jennifer Lee's", "John Smith's", "Sarah O'Brien's"
    possessive_pattern = r"\b([A-Z][a-z]+(?:\s+(?:[A-Z][a-z]+|O'[A-Z][a-z]+))+)(?:'s?|')\b"
    possessive_matches = re.findall(possessive_pattern, text)
    for match in possessive_matches:
        clean_name = match.strip()
        words = clean_name.split()
        # Filter out if first word is excluded
        if len(words) >= 2 and words[0].lower() not in excluded_first_words:
            names.append(clean_name)
    
    # Pattern 2: "does {Name} {verb}" pattern  
    # Matches: "does Jennifer Lee work", "does John Smith have"
    does_pattern = r"\bdoes\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+\w+"
    does_matches = re.findall(does_pattern, text, re.IGNORECASE)
    for match in does_matches:
        clean_name = match.strip()
        words = clean_name.split()
        # Filter out if first word is excluded (like "Does" itself)
        if len(words) >= 2:
            # Skip excluded words at start
            start_idx = 0
            while start_idx < len(words) and words[start_idx].lower() in excluded_first_words:
                start_idx += 1
            if start_idx < len(words) - 1:  # Need at least 2 words remaining
                clean_name = ' '.join(words[start_idx:])
                if all(w[0].isupper() for w in clean_name.split() if w):
                    if clean_name not in names:
                        names.append(clean_name)
    
    # Pattern 3: General capitalized multi-word names (First Last or First Middle Last)
    # Matches: "Jennifer Lee", "Sarah Jane Smith", "John Paul Jones"
    general_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
    general_matches = re.findall(general_pattern, text)
    
    for match in general_matches:
        clean_name = match.strip()
        words = clean_name.split()
        # Must be at least 2 words
        if len(words) < 2:
            continue
        # Skip excluded words at start
        start_idx = 0
        while start_idx < len(words) and words[start_idx].lower() in excluded_first_words:
            start_idx += 1
        if start_idx < len(words) - 1:  # Need at least 2 words remaining
            clean_name = ' '.join(words[start_idx:])
            # Check if it looks like a person name (all words capitalized, reasonable length)
            name_words = clean_name.split()
            if len(name_words) >= 2 and all(w[0].isupper() and len(w) >= 2 for w in name_words):
                if clean_name not in names:
                    names.append(clean_name)
    
    # Helper function to check if a name contains non-person words
    def is_likely_person_name(name: str) -> bool:
        """Check if name is likely a person name (not a project/system/etc.)."""
        words = name.lower().split()
        # Reject if ANY word is in the non-person blocklist
        for word in words:
            if word in excluded_non_person_words:
                logger.debug(f"[NAME_EXTRACT] Rejected '{name}' - contains non-person word: '{word}'")
                return False
        return True
    
    # Clean up: remove any possessive suffixes and filter non-person names
    cleaned_names = []
    for name in names:
        # Remove trailing 's or ' 
        clean = re.sub(r"['']s?$", "", name).strip()
        if clean and clean not in cleaned_names:
            # Filter out non-person entities (projects, systems, platforms, etc.)
            if is_likely_person_name(clean):
                cleaned_names.append(clean)
    
    logger.debug(f"[NAME_EXTRACT] From '{text}' extracted names: {cleaned_names}")
    return cleaned_names


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
    
    def _fetch_entity_properties(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch entity properties from database for graph-only entities (e.g., from spreadsheets)."""
        if not entity_id:
            return None
        try:
            from sqlalchemy import text as sql_text
            sql = sql_text("""
                SELECT properties FROM entities
                WHERE id = :eid AND tenant_id = :tid
            """)
            row = self.session.execute(sql, {"eid": entity_id, "tid": self.tenant_id}).fetchone()
            if row and row.properties:
                props = row.properties
                if isinstance(props, str):
                    import json
                    props = json.loads(props)
                return props
        except Exception as e:
            logger.debug(f"[TOOL] Failed to fetch entity properties: {e}")
        return None
    
    def _resolve_entities(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap EntityResolver.resolve() with person name extraction fallback.
        
        If the input looks like a full query (contains question words or is long),
        attempts to extract person names before resolution.
        Also fetches entity properties for graph-only entities (e.g., from spreadsheet extraction).
        """
        names = args.get("names", [])
        results = []
        
        for name in names:
            try:
                # First, try direct resolution
                result = self.entity_resolver.resolve(name)
                
                # Check if resolution succeeded
                if result.entity and result.confidence >= 0.5:
                    entity_dict = result.entity.to_dict() if result.entity else None
                    # Fetch and include entity properties (for spreadsheet-extracted entities)
                    if entity_dict and entity_dict.get("entity_id"):
                        props = self._fetch_entity_properties(entity_dict["entity_id"])
                        if props:
                            entity_dict["properties"] = props
                            logger.info(f"[TOOL] Entity properties found: {list(props.keys())}")
                    results.append({
                        "query": name,
                        "resolved": entity_dict,
                        "confidence": result.confidence,
                        "needs_disambiguation": result.needs_disambiguation,
                        "candidates": [c.to_dict() for c in result.candidates[:3]]
                    })
                    continue
                
                # Resolution failed - check if input looks like a full query
                # Indicators: contains question words, long text, or has possessive form
                is_query_like = (
                    len(name.split()) > 4 or
                    any(qw in name.lower() for qw in ['what', 'who', 'where', 'which', 'how', 'does', 'is']) or
                    "'s" in name or "'" in name
                )
                
                if is_query_like:
                    # Try to extract person names from the query
                    extracted_names = extract_person_names(name)
                    logger.info(f"[TOOL] Query-like input detected, extracted names: {extracted_names}")
                    
                    # Try resolving each extracted name
                    best_result = None
                    best_confidence = 0.0
                    
                    for extracted_name in extracted_names:
                        try:
                            extracted_result = self.entity_resolver.resolve(extracted_name)
                            if extracted_result.entity and extracted_result.confidence > best_confidence:
                                best_result = extracted_result
                                best_confidence = extracted_result.confidence
                                logger.info(f"[TOOL] Extracted name '{extracted_name}' resolved to '{extracted_result.entity.name}' (conf={best_confidence:.2f})")
                        except Exception as extract_err:
                            logger.debug(f"[TOOL] Failed to resolve extracted name '{extracted_name}': {extract_err}")
                    
                    if best_result and best_result.entity:
                        entity_dict = best_result.entity.to_dict()
                        # Fetch and include entity properties
                        if entity_dict and entity_dict.get("entity_id"):
                            props = self._fetch_entity_properties(entity_dict["entity_id"])
                            if props:
                                entity_dict["properties"] = props
                                logger.info(f"[TOOL] Entity properties found (extracted): {list(props.keys())}")
                        results.append({
                            "query": name,
                            "extracted_name": extracted_names[0] if extracted_names else None,
                            "resolved": entity_dict,
                            "confidence": best_result.confidence,
                            "needs_disambiguation": best_result.needs_disambiguation,
                            "candidates": [c.to_dict() for c in best_result.candidates[:3]]
                        })
                        continue
                
                # Neither direct nor extracted resolution worked
                entity_dict = result.entity.to_dict() if result.entity else None
                # Fetch properties for fallback case as well
                if entity_dict and entity_dict.get("entity_id"):
                    props = self._fetch_entity_properties(entity_dict["entity_id"])
                    if props:
                        entity_dict["properties"] = props
                results.append({
                    "query": name,
                    "resolved": entity_dict,
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
                    # Get entity info including properties
                    entity_sql = sql_text("""
                        SELECT id, name, entity_type, description, properties
                        FROM entities WHERE id = :eid AND tenant_id = :tid
                    """)
                    entity_row = self.session.execute(entity_sql, {
                        "eid": entity_id, "tid": self.tenant_id
                    }).fetchone()
                    
                    if not entity_row:
                        continue
                    
                    # Parse properties JSON
                    props = entity_row.properties or {}
                    if isinstance(props, str):
                        import json
                        try:
                            props = json.loads(props)
                        except:
                            props = {}
                    
                    entity_info = {
                        "id": str(entity_row.id),
                        "name": entity_row.name,
                        "type": entity_row.entity_type,
                        "properties": props
                    }
                    
                    # Get ALL outgoing relationships (no limit), including source document
                    rel_sql = sql_text("""
                        SELECT r.relationship_type, e2.name as target_name, e2.entity_type as target_type,
                               COALESCE(d.original_filename, d.name, r.source_document_id::text) as source_document
                        FROM relationships r
                        JOIN entities e2 ON r.target_id = e2.id
                        LEFT JOIN platform.documents d ON r.source_document_id::text = d.id::text AND d.tenant_id = :tid
                        WHERE r.source_id = :eid AND r.tenant_id = :tid
                        ORDER BY r.relationship_type, e2.name
                    """)
                    rel_rows = self.session.execute(rel_sql, {
                        "eid": entity_id, "tid": self.tenant_id
                    }).fetchall()
                    
                    relationships = [
                        {"type": r.relationship_type, "target": r.target_name, "target_type": r.target_type,
                         "source_document": r.source_document}
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
                    # Search for entities matching query (include properties)
                    search_sql = sql_text("""
                        SELECT id, name, entity_type, properties FROM entities
                        WHERE tenant_id = :tid AND LOWER(name) LIKE :pattern
                        LIMIT 5
                    """)
                    search_rows = self.session.execute(search_sql, {
                        "tid": self.tenant_id, "pattern": f"%{query.lower()}%"
                    }).fetchall()
                    
                    for row in search_rows:
                        rel_sql = sql_text("""
                            SELECT r.relationship_type, e2.name as target_name,
                                   COALESCE(d.original_filename, d.name, r.source_document_id::text) as source_document
                            FROM relationships r
                            JOIN entities e2 ON r.target_id = e2.id
                            LEFT JOIN platform.documents d ON r.source_document_id::text = d.id::text AND d.tenant_id = :tid
                            WHERE r.source_id = :eid AND r.tenant_id = :tid
                            LIMIT 15
                        """)
                        rel_rows = self.session.execute(rel_sql, {
                            "eid": str(row.id), "tid": self.tenant_id
                        }).fetchall()
                        
                        # Parse properties
                        row_props = row.properties or {}
                        if isinstance(row_props, str):
                            import json
                            try:
                                row_props = json.loads(row_props)
                            except:
                                row_props = {}
                        
                        results.append({
                            "entity": {"id": str(row.id), "name": row.name, "type": row.entity_type, "properties": row_props},
                            "relationships": [{"type": r.relationship_type, "target": r.target_name, "source_document": r.source_document} for r in rel_rows]
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
        """Search documents using unified DocumentSearcher with metric-aware reranking."""
        from ...search.document_searcher import DocumentSearcher
        from ..retrieval_router import rerank_chunks_by_metric
        
        query = args.get("query", "")
        limit = args.get("limit", 5)
        
        try:
            searcher = DocumentSearcher(self.session, self.tenant_id)
            # Fetch more results for reranking
            results = searcher.search(query, limit=limit * 2, use_vector=True)
            
            # Convert to chunks format for reranking
            chunks = [
                {
                    "text": r.get("text", ""),
                    "document": r.get("document_name", "Unknown document"),
                    "similarity": r.get("similarity", 0.6)
                }
                for r in results
            ]
            
            # Apply metric-based reranking (boosts net income, demotes EBITDA, etc.)
            chunks = rerank_chunks_by_metric(chunks, query)
            
            logger.info(f"[TOOL] DocumentSearcher returned {len(results)} chunks, reranked for query")
            
            return {
                "query": query,
                "chunks": [
                    {
                        "text": c.get("text", "")[:2500],  # Increased from 1500 to preserve full chunks
                        "document": c.get("document", "Unknown document"),
                        "similarity": c.get("similarity", 0.6)
                    }
                    for c in chunks[:limit]
                ]
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
