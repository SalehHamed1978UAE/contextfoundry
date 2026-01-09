"""
Query-Time Semantic Mapping Agent.

Uses LLM at query time to understand user intent and match against actual KG types.
No pre-defined synonym mappings required.

5-Stage Pipeline:
1. Query Understanding (LLM) - Parse query into structured form
2. KG Search (Deterministic) - Resolve entity, discover types, match, count
3. Document Fallback - When KG doesn't have answer
4. Response Synthesis (LLM) - Compose natural response
5. Learning Loop (async) - Cache successful patterns
"""
import json
import logging
import os
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from openai import OpenAI

logger = logging.getLogger(__name__)

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")


class QueryTimeSemanticAgent:
    """
    Agent that uses LLM to understand queries and match against KG at runtime.
    No pre-defined synonym mappings required.
    """
    
    def __init__(self, session, tenant_id: str, doc_searcher=None):
        self.session = session
        self.tenant_id = tenant_id
        self.doc_search = doc_searcher
        self.conversation_history: List[Dict] = []
        self.max_latency_ms = 2500
        
        self.llm_client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL,
        )
        self.model = "gpt-4o-mini"
    
    def _llm_generate(self, prompt: str) -> str:
        """Generate LLM response."""
        response = self.llm_client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    
    def query(self, user_message: str) -> dict:
        """Process query using query-time semantic mapping."""
        
        self.conversation_history.append({"role": "user", "content": user_message})
        
        try:
            parsed = self._parse_query(user_message)
            logger.info(f"[STAGE 1] Parsed: {parsed}")
            
            entity = self._resolve_entity(
                parsed["subject"]["text"],
                parsed["subject"].get("likely_entity_types", [])
            )
            
            if not entity:
                logger.info("[STAGE 2a] Entity not found, falling back to documents")
                return self._document_fallback(user_message)
            
            logger.info(f"[STAGE 2a] Resolved: {entity['name']} ({entity['type']})")
            
            available_rels = self._discover_relationships(entity["id"])
            available_types = list(set(r["type"] for r in available_rels))
            logger.info(f"[STAGE 2b] Available types: {available_types}")
            
            if not available_types:
                logger.info("[STAGE 2b] No relationships found, falling back to documents")
                return self._document_fallback(user_message)
            
            relationship_text = ""
            if parsed.get("relationship"):
                relationship_text = parsed["relationship"].get("text", "")
            
            if relationship_text:
                matched_types = self._match_relationship_types(
                    relationship_text,
                    available_types
                )
            else:
                matched_types = available_types
            
            logger.info(f"[STAGE 2c] Matched types: {matched_types}")
            
            if not matched_types:
                logger.info("[STAGE 2c] No matching types, falling back to documents")
                return self._document_fallback(user_message)
            
            results = []
            for rel_type in matched_types[:3]:
                rel_info = next((r for r in available_rels if r["type"] == rel_type), None)
                if rel_info:
                    result = self._query_relationships(
                        entity["id"],
                        rel_type,
                        rel_info["direction"]
                    )
                    results.append({
                        "type": rel_type,
                        "direction": rel_info["direction"],
                        "count": result["count"],
                        "entities": result["entities"]
                    })
            
            logger.info(f"[STAGE 2d] Results: {results}")
            
            answer = self._synthesize_response(user_message, parsed, entity, results)
            
            self._log_pattern(relationship_text, matched_types)
            
            self.conversation_history.append({"role": "assistant", "content": answer})
            
            return {
                "answer": answer,
                "confidence": 0.85 if results else 0.5,
                "sources": results,
                "method": "kg_semantic_mapping"
            }
            
        except Exception as e:
            logger.error(f"Error in semantic agent: {e}", exc_info=True)
            return self._document_fallback(user_message)
    
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
- relationship: {{"text": "relationship phrase", "likely_relationship_types": ["TYPE1", "TYPE2"]}}
- object: {{"text": "target entity", "likely_entity_types": ["TYPE1"]}} (optional)

For likely_types, suggest what KG types might match (e.g., PERSON, ORGANIZATION, INVESTED_IN, WORKED_AT).
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
        """STAGE 2a: Resolve entity name flexibly."""
        
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
                ORDER BY LENGTH(name)
                LIMIT 1
            """),
            {"tenant_id": self.tenant_id, "name": name, "pattern": f"%{name}%"}
        ).fetchone()
        
        if result:
            return {
                "id": str(result.id),
                "name": result.name,
                "type": result.entity_type
            }
        
        return None
    
    def _discover_relationships(self, entity_id: str) -> List[dict]:
        """STAGE 2b: Discover all relationship types (both directions)."""
        
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
        """STAGE 2c: Use LLM to match user phrase against available KG types."""
        
        cached = self._check_type_cache(user_phrase)
        if cached:
            matched = [t for t in cached if t in available_types]
            if matched:
                logger.info(f"[CACHE HIT] '{user_phrase}' → {matched}")
                return matched
        
        prompt = f"""Which of these relationship types match the phrase "{user_phrase}"?

Available types: {available_types}

Return ONLY types from this list that are semantically relevant.
Return as JSON array. If none match, return [].

Examples:
- "invested in" with ["INVESTED_IN", "EMPLOYS"] → ["INVESTED_IN"]
- "jobs" with ["HELD_POSITION", "WORKED_AT"] → ["HELD_POSITION", "WORKED_AT"]
- "team members" with ["WORKS_ON", "LEADS"] → ["WORKS_ON", "LEADS"]
- "wrote" with ["INVESTED_IN", "EMPLOYS"] → []

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
        """STAGE 2d: Query relationships deterministically."""
        
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
    
    def _synthesize_response(self, query: str, parsed: dict, entity: dict, results: List) -> str:
        """STAGE 4: Use LLM to compose natural response."""
        
        total_count = sum(r["count"] for r in results)
        all_entities = []
        for r in results:
            all_entities.extend([e["name"] for e in r["entities"]])
        
        prompt = f"""Compose a natural answer to this query.

Query: "{query}"
Subject: {entity['name']} ({entity['type']})

Data found:
{json.dumps(results, indent=2)}

Total count across all relationship types: {total_count}
Entity names: {all_entities}

Rules:
- Be concise but complete
- List ALL entities found (don't summarize or truncate)
- If multiple relationship types matched, explain both
- Use natural language, not technical jargon
- Don't mention "KG" or "relationships" - just answer naturally
- For count queries, give the number prominently

Your answer:"""

        return self._llm_generate(prompt)
    
    def _document_fallback(self, query: str) -> dict:
        """STAGE 3: Fall back to document search when KG doesn't have answer."""
        
        logger.info(f"[STAGE 3] Document fallback for: {query}")
        
        if not self.doc_search:
            chunks = self.session.execute(
                text("""
                    SELECT id, text, document_id
                    FROM document_chunks
                    WHERE tenant_id = :tenant_id
                    AND text ILIKE :pattern
                    LIMIT 5
                """),
                {"tenant_id": self.tenant_id, "pattern": f"%{query.split()[0] if query.split() else query}%"}
            ).fetchall()
            
            if not chunks:
                return {
                    "answer": "I don't have enough information to answer this question.",
                    "confidence": 0.2,
                    "sources": [],
                    "method": "document_fallback_empty"
                }
            
            context = "\n\n".join([row.text[:1000] for row in chunks[:3]])
        else:
            results = self.doc_search.search(query, limit=5)
            if not results:
                return {
                    "answer": "I don't have enough information to answer this question.",
                    "confidence": 0.2,
                    "sources": [],
                    "method": "document_fallback_empty"
                }
            context = "\n\n".join([r.get("content", r.get("text", ""))[:1000] for r in results[:3]])
        
        prompt = f"""Answer this question based on the following document excerpts.

Question: "{query}"

Documents:
{context}

If the documents contain the answer, provide it. If not, say you don't have enough information.

Your answer:"""

        answer = self._llm_generate(prompt)
        
        return {
            "answer": answer,
            "confidence": 0.6,
            "sources": [],
            "method": "document_fallback"
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
        """STAGE 5: Log successful pattern for learning."""
        
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
