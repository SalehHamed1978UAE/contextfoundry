"""
Query-Time Semantic Mapping Agent.

Uses LLM at query time to understand user intent and match against actual KG types.
No pre-defined synonym mappings required.

Architecture:
1. Query Understanding (LLM) - Parse query into structured form
2. KG Search (Deterministic) - Resolve entity, discover types, match, query
3. Document Search (Semantic) - Search source documents in PARALLEL with KG
4. Hybrid Synthesis (LLM) - Combine KG results + document content, docs are source of truth
5. Learning Loop (async) - Cache successful patterns

Key principle: KG accelerates queries and provides structure. Documents remain source of truth.
"""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Any
from sqlalchemy import text, create_engine
from sqlalchemy.orm import Session
from openai import OpenAI

from ..shared.tenant_context import ensure_tenant_context, TenantContextError

logger = logging.getLogger(__name__)

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")


class QueryTimeSemanticAgent:
    """
    Agent that uses LLM to understand queries and match against KG at runtime.
    Runs KG query and document search in PARALLEL, then synthesizes from both.
    Documents are the source of truth when there's a conflict.
    """
    
    def __init__(self, session, tenant_id: str, doc_searcher=None):
        self.session = session
        self.tenant_id = tenant_id
        self.doc_search = doc_searcher
        self.conversation_history: List[Dict] = []
        self.max_latency_ms = 2500
        
        self._set_rls_context()
        
        self.llm_client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL,
        )
        self.model = "gpt-4o-mini"
    
    def _set_rls_context(self):
        """Set RLS tenant context on the session."""
        try:
            ensure_tenant_context(self.session, self.tenant_id)
            logger.debug(f"RLS context set for tenant: {self.tenant_id[:8]}...")
        except TenantContextError as e:
            logger.warning(f"Failed to set RLS context: {e}")
    
    def _llm_generate(self, prompt: str) -> str:
        """Generate LLM response."""
        response = self.llm_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()
    
    def query(self, user_message: str) -> dict:
        """
        Process query using hybrid KG + document approach.
        
        Flow:
        1. Parse query
        2. KG query + Doc search (PARALLEL - both execute concurrently)
        3. Synthesize from BOTH sources (docs are source of truth)
        """
        self.conversation_history.append({"role": "user", "content": user_message})
        
        try:
            parsed = self._parse_query(user_message)
            logger.info(f"[STAGE 1] Parsed: {parsed}")
            
            kg_result, doc_result = self._parallel_search(user_message, parsed)
            
            entity_name = kg_result.get('entity', {})
            entity_name = entity_name.get('name', 'none') if entity_name else 'none'
            logger.info(f"[STAGE 2] KG result: {kg_result.get('count', 0)} items, entity: {entity_name}")
            logger.info(f"[STAGE 3] Doc result: {len(doc_result.get('chunks', []))} chunks found")
            
            answer = self._hybrid_synthesis(user_message, parsed, kg_result, doc_result)
            
            if kg_result.get("relationship_text"):
                self._log_pattern(kg_result["relationship_text"], kg_result.get("matched_types", []))
            
            self.conversation_history.append({"role": "assistant", "content": answer})
            
            has_kg = kg_result.get("count", 0) > 0
            has_docs = len(doc_result.get("chunks", [])) > 0
            
            if has_kg and has_docs:
                method = "hybrid_kg_docs"
                confidence = 0.9
            elif has_kg:
                method = "kg_only"
                confidence = 0.85
            elif has_docs:
                method = "docs_only"
                confidence = 0.7
            else:
                method = "no_data"
                confidence = 0.2
            
            return {
                "answer": answer,
                "confidence": confidence,
                "sources": {
                    "kg": kg_result.get("results", []),
                    "documents": [{"chunk_id": c.get("id"), "preview": c.get("text", "")[:200]} for c in doc_result.get("chunks", [])]
                },
                "method": method
            }
            
        except Exception as e:
            logger.error(f"Error in semantic agent: {e}", exc_info=True)
            return {
                "answer": f"I encountered an error processing your query: {str(e)}",
                "confidence": 0.0,
                "sources": {},
                "method": "error"
            }
    
    def _parallel_search(self, user_message: str, parsed: dict) -> tuple:
        """
        Execute KG query and document search in PARALLEL.
        
        KG query runs on main thread (uses existing session).
        Document search runs in background thread with its own session.
        This approach is thread-safe while still achieving parallelism.
        """
        doc_result = {"chunks": []}
        
        def run_doc_search():
            try:
                db_url = os.environ.get("DATABASE_URL")
                if not db_url:
                    return {"chunks": []}
                
                engine = create_engine(db_url)
                with Session(engine) as doc_session:
                    ensure_tenant_context(doc_session, self.tenant_id)
                    return self._document_search_with_session(user_message, parsed, doc_session)
            except Exception as e:
                logger.error(f"Document search error: {e}")
                return {"chunks": []}
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            doc_future = executor.submit(run_doc_search)
            
            try:
                kg_result = self._kg_query(parsed)
            except Exception as e:
                logger.error(f"KG query error: {e}")
                kg_result = {"entity": None, "results": [], "count": 0}
            
            doc_result = doc_future.result(timeout=10)
        
        logger.debug("[PARALLEL] Both KG and doc searches completed")
        return kg_result, doc_result
    
    def _document_search_with_session(self, query: str, parsed: dict, session) -> dict:
        """Document search using provided session (for thread safety)."""
        subject_name = parsed.get("subject", {}).get("text", "")
        
        if subject_name:
            name_parts = subject_name.split()
            search_terms = name_parts[:2] if name_parts else [subject_name]
        else:
            search_terms = query.split()[:3]
        
        chunks = []
        for term in search_terms[:2]:
            if not term:
                continue
            try:
                results = session.execute(
                    text("""
                        SELECT dc.id, dc.text, dc.document_id, d.title as doc_title
                        FROM document_chunks dc
                        LEFT JOIN documents d ON d.id = dc.document_id
                        WHERE dc.tenant_id = :tenant_id
                        AND dc.text ILIKE :pattern
                        LIMIT 10
                    """),
                    {"tenant_id": self.tenant_id, "pattern": f"%{term}%"}
                ).fetchall()
                
                for row in results:
                    chunk_data = {
                        "id": str(row.id) if row.id else None,
                        "text": row.text,
                        "document_id": str(row.document_id) if row.document_id else None,
                        "doc_title": row.doc_title
                    }
                    if chunk_data not in chunks:
                        chunks.append(chunk_data)
            except Exception as e:
                logger.warning(f"Document search failed for term '{term}': {e}")
        
        seen_ids = set()
        unique_chunks = []
        for c in chunks:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                unique_chunks.append(c)
        
        return {"chunks": unique_chunks[:5]}
    
    def _kg_query(self, parsed: dict) -> dict:
        """STAGE 2: Query the knowledge graph."""
        
        entity = self._resolve_entity(
            parsed["subject"]["text"],
            parsed["subject"].get("likely_entity_types", [])
        )
        
        if not entity:
            logger.info("[STAGE 2] Entity not found in KG")
            return {"entity": None, "results": [], "count": 0}
        
        logger.info(f"[STAGE 2a] Resolved: {entity['name']} ({entity['type']})")
        
        available_rels = self._discover_relationships(entity["id"])
        available_types = list(set(r["type"] for r in available_rels))
        logger.info(f"[STAGE 2b] Available types: {available_types}")
        
        if not available_types:
            return {"entity": entity, "results": [], "count": 0}
        
        relationship_text = ""
        if parsed.get("relationship"):
            relationship_text = parsed["relationship"].get("text", "")
        
        if relationship_text:
            matched_types = self._match_relationship_types(relationship_text, available_types)
        else:
            matched_types = available_types
        
        logger.info(f"[STAGE 2c] Matched types: {matched_types}")
        
        if not matched_types:
            return {"entity": entity, "results": [], "count": 0, "relationship_text": relationship_text}
        
        results = []
        for rel_type in matched_types[:3]:
            rel_info = next((r for r in available_rels if r["type"] == rel_type), None)
            if rel_info:
                result = self._query_relationships(entity["id"], rel_type, rel_info["direction"])
                results.append({
                    "type": rel_type,
                    "direction": rel_info["direction"],
                    "count": result["count"],
                    "entities": result["entities"]
                })
        
        total_count = sum(r["count"] for r in results)
        
        return {
            "entity": entity,
            "results": results,
            "count": total_count,
            "matched_types": matched_types,
            "relationship_text": relationship_text
        }
    
    def _document_search(self, query: str, parsed: dict) -> dict:
        """STAGE 3: Search source documents for relevant content."""
        
        subject_name = parsed.get("subject", {}).get("text", "")
        
        if subject_name:
            name_parts = subject_name.split()
            search_terms = name_parts[:2] if name_parts else [subject_name]
        else:
            search_terms = query.split()[:3]
        
        chunks = []
        for term in search_terms[:2]:
            if not term:
                continue
            try:
                results = self.session.execute(
                    text("""
                        SELECT dc.id, dc.text, dc.document_id, d.title as doc_title
                        FROM document_chunks dc
                        LEFT JOIN documents d ON d.id = dc.document_id
                        WHERE dc.tenant_id = :tenant_id
                        AND dc.text ILIKE :pattern
                        LIMIT 10
                    """),
                    {"tenant_id": self.tenant_id, "pattern": f"%{term}%"}
                ).fetchall()
                
                for row in results:
                    chunk_data = {
                        "id": str(row.id) if row.id else None,
                        "text": row.text,
                        "document_id": str(row.document_id) if row.document_id else None,
                        "doc_title": row.doc_title
                    }
                    if chunk_data not in chunks:
                        chunks.append(chunk_data)
            except Exception as e:
                logger.warning(f"Document search failed for term '{term}': {e}")
        
        seen_ids = set()
        unique_chunks = []
        for c in chunks:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                unique_chunks.append(c)
        
        return {"chunks": unique_chunks[:5]}
    
    def _hybrid_synthesis(self, query: str, parsed: dict, kg_result: dict, doc_result: dict) -> str:
        """STAGE 4: Synthesize answer from BOTH KG and documents. Documents are source of truth."""
        
        kg_section = "No structured data found in knowledge graph."
        if kg_result.get("entity") and kg_result.get("results"):
            entity = kg_result["entity"]
            results = kg_result["results"]
            
            kg_lines = [f"Subject: {entity['name']} ({entity['type']})"]
            for r in results:
                entities_list = ", ".join([e["name"] for e in r["entities"]])
                kg_lines.append(f"- {r['type']}: {r['count']} items - {entities_list}")
            kg_section = "\n".join(kg_lines)
        
        doc_section = "No relevant documents found."
        if doc_result.get("chunks"):
            doc_texts = []
            for i, chunk in enumerate(doc_result["chunks"][:3], 1):
                title = chunk.get("doc_title", "Unknown document")
                text = chunk.get("text", "")[:2500]  # Increased to preserve full financial data
                doc_texts.append(f"[Document {i}: {title}]\n{text}")
            doc_section = "\n\n".join(doc_texts)
        
        prompt = f"""You are answering a question using two sources of information:
1. KNOWLEDGE GRAPH (structured data, may be incomplete)
2. SOURCE DOCUMENTS (original text, source of truth)

IMPORTANT: If the knowledge graph and documents provide different information, 
PREFER THE DOCUMENTS as they are the original source of truth.
The knowledge graph may have missed information during extraction.

Question: "{query}"

=== KNOWLEDGE GRAPH DATA ===
{kg_section}

=== SOURCE DOCUMENTS ===
{doc_section}

=== INSTRUCTIONS ===
1. Synthesize the MOST COMPLETE answer using BOTH sources
2. If documents show information not in the KG, include it (extraction may have missed it)
3. If documents contradict KG, prefer document content
4. Be specific - list all items/roles/positions found
5. Use natural language, don't mention "knowledge graph" or "documents"
6. For count questions, count ALL items found across both sources

Your answer:"""

        return self._llm_generate(prompt)
    
    def _parse_query(self, query: str) -> dict:
        """STAGE 1: Use LLM to parse query into structured form."""
        
        context = ""
        if len(self.conversation_history) > 1:
            recent = self.conversation_history[-4:]
            context = f"\nRecent conversation:\n" + "\n".join(
                f"{m['role']}: {m['content']}" for m in recent[:-1]
            )
        
        prompt = f"""Parse this query into structured components.
{context}

Query: "{query}"

Return JSON with:
- intent: "count", "list", "describe", or "compare"
- subject: {{"text": "entity name", "likely_entity_types": ["TYPE1", "TYPE2"]}}
- relationship: {{"text": "key concept being asked about", "likely_relationship_types": ["TYPE1", "TYPE2"]}}
- object: {{"text": "target entity", "likely_entity_types": ["TYPE1"]}} (optional)

IMPORTANT for relationship.text:
- Extract the KEY CONCEPT being asked about, not just verbs
- "How many jobs has X done?" -> relationship.text = "jobs" (not "has done")
- "What positions did X hold?" -> relationship.text = "positions" 
- "Who works on Project Y?" -> relationship.text = "works on"
- "What skills does X have?" -> relationship.text = "skills"

For likely_types, suggest KG relationship types (e.g., HOLDS_POSITION, WORKED_AT, HAS_SKILL, INVESTED_IN).
Resolve pronouns using conversation context (e.g., "he" → actual name from context).

Return only valid JSON."""

        response = self._llm_generate(prompt)
        
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "intent": "describe",
                "subject": {"text": query, "likely_entity_types": []},
                "relationship": {"text": "", "likely_relationship_types": []}
            }
    
    def _resolve_entity(self, name: str, type_hints: List[str] = None) -> Optional[dict]:
        """Resolve entity name flexibly."""
        
        result = self.session.execute(
            text("""
                SELECT id, name, entity_type
                FROM entities
                WHERE tenant_id = :tenant_id
                AND LOWER(name) = LOWER(:name)
                AND lifecycle_state = 'TRUSTED'
                LIMIT 1
            """),
            {"tenant_id": self.tenant_id, "name": name}
        ).fetchone()
        
        if result:
            return {
                "id": str(result.id),
                "name": result.name,
                "type": result.entity_type
            }
        
        result = self.session.execute(
            text("""
                SELECT id, name, entity_type
                FROM entities
                WHERE tenant_id = :tenant_id
                AND LOWER(name) ILIKE :pattern
                AND lifecycle_state = 'TRUSTED'
                ORDER BY 
                    CASE WHEN LOWER(name) LIKE :prefix_pattern THEN 0 ELSE 1 END,
                    LENGTH(name)
                LIMIT 1
            """),
            {
                "tenant_id": self.tenant_id, 
                "pattern": f"%{name}%",
                "prefix_pattern": f"{name.lower()}%"
            }
        ).fetchone()
        
        if result:
            return {
                "id": str(result.id),
                "name": result.name,
                "type": result.entity_type
            }
        
        return None
    
    def _discover_relationships(self, entity_id: str) -> List[dict]:
        """Discover all relationship types for an entity (both directions)."""
        
        results = self.session.execute(
            text("""
                SELECT relationship_type as type, 'outgoing' as direction, COUNT(*) as count
                FROM relationships
                WHERE tenant_id = :tenant_id
                AND source_id = :entity_id
                AND lifecycle_state = 'TRUSTED'
                GROUP BY relationship_type
                
                UNION ALL
                
                SELECT relationship_type as type, 'incoming' as direction, COUNT(*) as count
                FROM relationships
                WHERE tenant_id = :tenant_id
                AND target_id = :entity_id
                AND lifecycle_state = 'TRUSTED'
                GROUP BY relationship_type
            """),
            {"tenant_id": self.tenant_id, "entity_id": entity_id}
        ).fetchall()
        
        return [{"type": r.type, "direction": r.direction, "count": r.count} for r in results]
    
    def _match_relationship_types(self, user_phrase: str, available_types: List[str]) -> List[str]:
        """Use LLM to match user phrase against available KG types."""
        
        cached = self._check_type_cache(user_phrase)
        if cached:
            matched = [t for t in cached if t in available_types]
            if matched:
                logger.info(f"[CACHE HIT] '{user_phrase}' → {matched}")
                return matched
        
        prompt = f"""Which of these relationship types match the concept "{user_phrase}"?

Available types: {available_types}

Return ONLY types from this list that are semantically relevant.
Return as JSON array. If none match well, return [].

Semantic matching examples:
- "jobs" → HOLDS_POSITION, WORKED_AT (jobs = positions held, places worked)
- "positions" → HOLDS_POSITION (positions = roles held)
- "skills" → HAS_SKILL (skills = abilities)
- "education" → EDUCATED_AT, HAS_DEGREE (education = schools, degrees)
- "invested in" → INVESTED_IN (direct match)
- "team members" → WORKS_ON, LEADS (team = who works on something)
- "people" → WORKS_ON, LEADS (people on project = workers and leaders)
- "works on" → WORKS_ON, WORKED_ON (direct match)
- "team" → WORKS_ON, LEADS (team members)

Your answer (JSON array only):"""

        response = self._llm_generate(prompt)
        
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1].replace("json", "").strip()
            matched = json.loads(cleaned)
            matched = [t for t in matched if t in available_types]
            return matched[:5]
        except:
            user_lower = user_phrase.lower()
            return [t for t in available_types if user_lower in t.lower() or t.lower().replace("_", " ") in user_lower]
    
    def _query_relationships(self, entity_id: str, rel_type: str, direction: str) -> dict:
        """Query relationships deterministically."""
        
        if direction == "outgoing":
            results = self.session.execute(
                text("""
                    SELECT e.name, e.entity_type
                    FROM relationships r
                    JOIN entities e ON e.id = r.target_id
                    WHERE r.tenant_id = :tenant_id
                    AND r.source_id = :entity_id
                    AND r.relationship_type = :rel_type
                    AND r.lifecycle_state = 'TRUSTED'
                """),
                {"tenant_id": self.tenant_id, "entity_id": entity_id, "rel_type": rel_type}
            ).fetchall()
        else:
            results = self.session.execute(
                text("""
                    SELECT e.name, e.entity_type
                    FROM relationships r
                    JOIN entities e ON e.id = r.source_id
                    WHERE r.tenant_id = :tenant_id
                    AND r.target_id = :entity_id
                    AND r.relationship_type = :rel_type
                    AND r.lifecycle_state = 'TRUSTED'
                """),
                {"tenant_id": self.tenant_id, "entity_id": entity_id, "rel_type": rel_type}
            ).fetchall()
        
        return {
            "count": len(results),
            "entities": [{"name": r.name, "type": r.entity_type} for r in results]
        }
    
    def _check_type_cache(self, phrase: str) -> Optional[List[str]]:
        """Check if we have cached type mappings for this phrase."""
        try:
            result = self.session.execute(
                text("""
                    SELECT kg_type
                    FROM query_pattern_cache
                    WHERE tenant_id = :tenant_id
                    AND phrase = LOWER(:phrase)
                    AND success_count >= 3
                    ORDER BY success_count DESC
                    LIMIT 5
                """),
                {"tenant_id": self.tenant_id, "phrase": phrase}
            ).fetchall()
            
            if result:
                return [r.kg_type for r in result]
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
        return None
    
    def _log_pattern(self, phrase: str, matched_types: List[str]):
        """Log successful pattern for learning."""
        if not phrase or not matched_types:
            return
        
        for kg_type in matched_types:
            try:
                self.session.execute(
                    text("""
                        INSERT INTO query_pattern_cache (tenant_id, phrase, kg_type, success_count, last_used)
                        VALUES (:tenant_id, LOWER(:phrase), :kg_type, 1, now())
                        ON CONFLICT (tenant_id, phrase, kg_type)
                        DO UPDATE SET 
                            success_count = query_pattern_cache.success_count + 1,
                            last_used = now()
                    """),
                    {"tenant_id": self.tenant_id, "phrase": phrase, "kg_type": kg_type}
                )
                self.session.commit()
            except Exception as e:
                logger.warning(f"Failed to log pattern: {e}")
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
