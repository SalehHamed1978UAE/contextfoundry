# Context Foundry: Query-Time Semantic Mapping Implementation

## CONTEXT

We've identified a fundamental architectural problem with Context Foundry:

**Current approach (broken):**
- Pre-extract all relationships at ingestion time
- Pre-define synonym mappings (jobs → WORKED_AT)
- Hope we anticipated every possible question

**Failures observed:**
- Document lists 11 team members, extraction only created 3 LEADS relationships
- "jobs" hardcoded to WORKED_AT, but user meant positions
- "positions held" fails, "number of positions held" works
- No INVESTED_IN relationship type, so investment queries fail
- Adding specific fixes for each case = endless whack-a-mole

**New approach (Query-Time Semantic Mapping):**
- KG stays canonical (clean, small spine with normalized types)
- LLM expands user queries at runtime to match KG types
- Documents are fallback source of truth
- No pre-defined synonym tables needed

## ARCHITECTURE OVERVIEW

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│ STAGE 1: Query Understanding (LLM)  │
│ "invested in" → [INVESTED_IN,       │
│                  FUNDED, BACKED]    │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ STAGE 2: KG Search (Deterministic)  │
│ 2a. Resolve entity                  │
│ 2b. Discover available rel types    │
│ 2c. Match LLM suggestions to KG     │
│ 2d. Count/retrieve deterministically│
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ STAGE 3: Document Fallback          │
│ (if KG doesn't have answer)         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ STAGE 4: Response Synthesis (LLM)   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ STAGE 5: Learning Loop (async)      │
│ Cache successful patterns           │
└─────────────────────────────────────┘
```

## IMPLEMENTATION TASKS

### Task 1: Create Query Parser Tool

Create `src/context_foundry/agents/tools/query_parser.py`:

```python
from typing import Optional
from pydantic import BaseModel, Field

class EntityReference(BaseModel):
    text: str = Field(description="The text from the query")
    likely_entity_types: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Likely KG entity types (e.g., PERSON, ORGANIZATION, PROJECT)"
    )

class RelationshipReference(BaseModel):
    text: str = Field(description="The relationship phrase from query")
    likely_relationship_types: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Likely KG relationship types (e.g., INVESTED_IN, WORKED_AT)"
    )

class ParsedQuery(BaseModel):
    intent: str = Field(description="Query intent: count, list, describe, or compare")
    subject: EntityReference
    relationship: Optional[RelationshipReference] = None
    object: Optional[EntityReference] = None
    
PARSE_QUERY_TOOL = {
    "name": "parse_query",
    "description": """Parse a natural language query into structured components.
    
    Use this as the FIRST step for any user query to understand:
    - What they want (count, list, describe, compare)
    - Who/what they're asking about (subject)
    - What relationship they're interested in
    - What the target is (object)
    
    The likely_types fields should contain your best guesses for what KG types
    might match the user's language. These will be matched against actual KG data.""",
    "parameters": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["count", "list", "describe", "compare"],
                "description": "What the user wants to know"
            },
            "subject": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "likely_entity_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 5,
                        "description": "e.g., PERSON, ORGANIZATION, PROJECT, FUND, EVENT"
                    }
                },
                "required": ["text"]
            },
            "relationship": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "likely_relationship_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 5,
                        "description": "e.g., INVESTED_IN, WORKED_AT, LEADS, AUTHORED, SPEAKS_AT"
                    }
                }
            },
            "object": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "likely_entity_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 5
                    }
                }
            }
        },
        "required": ["intent", "subject"]
    }
}
```

### Task 2: Create Relationship Type Expander

Create `src/context_foundry/agents/tools/type_expander.py`:

```python
EXPAND_TO_KG_TYPES_TOOL = {
    "name": "expand_to_kg_types",
    "description": """Given a user's relationship phrase and the ACTUAL relationship types 
    available in the KG for an entity, determine which KG types match the user's intent.
    
    IMPORTANT: Only return types that are in the available_types list.
    You cannot invent new types - you must match against what exists.
    
    Example:
    - user_phrase: "invested in"
    - available_types: ["INVESTED_IN", "EMPLOYS", "LOCATED_IN"]
    - Return: ["INVESTED_IN"]
    
    Example:
    - user_phrase: "jobs"
    - available_types: ["HELD_POSITION", "WORKED_AT", "EDUCATED_AT"]
    - Return: ["HELD_POSITION", "WORKED_AT"]  # both are relevant to "jobs"
    """,
    "parameters": {
        "type": "object",
        "properties": {
            "user_phrase": {
                "type": "string",
                "description": "The relationship phrase from the user's query"
            },
            "available_types": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Relationship types that actually exist in the KG for this entity"
            }
        },
        "required": ["user_phrase", "available_types"]
    }
}

def expand_to_kg_types(llm, user_phrase: str, available_types: list[str]) -> list[str]:
    """
    Use LLM to match user's phrase against available KG types.
    Returns only types from available_types that semantically match.
    """
    if not available_types:
        return []
    
    prompt = f"""Given the user's phrase "{user_phrase}", which of these relationship types are relevant?

Available types: {available_types}

Return ONLY types from the available list that semantically match what the user is asking about.
Return as a JSON array of strings. If none match, return empty array.

Examples:
- "invested in" with ["INVESTED_IN", "EMPLOYS"] → ["INVESTED_IN"]
- "jobs" with ["HELD_POSITION", "WORKED_AT"] → ["HELD_POSITION", "WORKED_AT"]
- "education" with ["INVESTED_IN", "EMPLOYS"] → []
"""
    
    response = llm.generate(prompt, response_format={"type": "json_array"})
    
    # Validate response only contains available types
    matched = [t for t in response if t in available_types]
    
    # Cap at 5
    return matched[:5]
```

### Task 3: Create Pattern Cache Table

Run this migration:

```sql
-- Query pattern cache for learning loop
CREATE TABLE IF NOT EXISTS query_pattern_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    phrase TEXT NOT NULL,  -- normalized lowercase
    kg_type TEXT NOT NULL,
    success_count INT DEFAULT 1,
    confidence FLOAT DEFAULT 0.5,
    last_used TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, phrase, kg_type)
);

CREATE INDEX idx_pattern_cache_lookup 
ON query_pattern_cache (tenant_id, phrase);

ALTER TABLE query_pattern_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY pattern_cache_tenant_isolation 
ON query_pattern_cache
USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Ontology proposals from document fallback
CREATE TABLE IF NOT EXISTS ontology_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    source TEXT NOT NULL,  -- 'document_fallback', 'extraction', etc.
    query TEXT,
    inferred_type TEXT NOT NULL,
    type_category TEXT NOT NULL,  -- 'entity' or 'relationship'
    evidence_chunk_id UUID,
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE ontology_proposals ENABLE ROW LEVEL SECURITY;

CREATE POLICY ontology_proposals_tenant_isolation 
ON ontology_proposals
USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

### Task 4: Create Query-Time Semantic Agent

Create `src/context_foundry/agents/semantic_agent.py`:

```python
import json
import logging
from typing import Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)

class QueryTimeSemanticAgent:
    """
    Agent that uses LLM to understand queries and match against KG at runtime.
    No pre-defined synonym mappings required.
    """
    
    def __init__(self, session, tenant_id: str, llm_client, doc_searcher):
        self.session = session
        self.tenant_id = tenant_id
        self.llm = llm_client
        self.doc_search = doc_searcher
        self.conversation_history = []
        self.max_latency_ms = 2500  # Target latency budget
    
    def query(self, user_message: str) -> dict:
        """Process query using query-time semantic mapping."""
        
        # Add to conversation history for pronoun resolution
        self.conversation_history.append({"role": "user", "content": user_message})
        
        try:
            # STAGE 1: Parse query
            parsed = self._parse_query(user_message)
            logger.info(f"[STAGE 1] Parsed: {parsed}")
            
            # STAGE 2a: Resolve entity
            entity = self._resolve_entity(
                parsed["subject"]["text"],
                parsed["subject"].get("likely_entity_types", [])
            )
            
            if not entity:
                logger.info("[STAGE 2a] Entity not found, falling back to documents")
                return self._document_fallback(user_message)
            
            logger.info(f"[STAGE 2a] Resolved: {entity['name']} ({entity['type']})")
            
            # STAGE 2b: Discover relationships (both directions)
            available_rels = self._discover_relationships(entity["id"])
            available_types = list(set(r["type"] for r in available_rels))
            logger.info(f"[STAGE 2b] Available types: {available_types}")
            
            if not available_types:
                logger.info("[STAGE 2b] No relationships found, falling back to documents")
                return self._document_fallback(user_message)
            
            # STAGE 2c: Match relationship types
            relationship_text = parsed.get("relationship", {}).get("text", "")
            if relationship_text:
                matched_types = self._match_relationship_types(
                    relationship_text,
                    available_types
                )
            else:
                # No specific relationship mentioned, use all available
                matched_types = available_types
            
            logger.info(f"[STAGE 2c] Matched types: {matched_types}")
            
            if not matched_types:
                logger.info("[STAGE 2c] No matching types, falling back to documents")
                return self._document_fallback(user_message)
            
            # STAGE 2d: Query KG deterministically
            results = []
            for rel_type in matched_types[:3]:  # Limit to top 3 matches
                # Find the direction for this type
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
            
            # STAGE 4: Synthesize response
            answer = self._synthesize_response(user_message, parsed, entity, results)
            
            # STAGE 5: Log successful pattern (async)
            self._log_pattern(relationship_text, matched_types)
            
            # Add to conversation history
            self.conversation_history.append({"role": "assistant", "content": answer})
            
            return {
                "answer": answer,
                "confidence": 0.85 if results else 0.5,
                "sources": results,
                "method": "kg_semantic_mapping"
            }
            
        except Exception as e:
            logger.error(f"Error in semantic agent: {e}")
            return self._document_fallback(user_message)
    
    def _parse_query(self, query: str) -> dict:
        """STAGE 1: Use LLM to parse query into structured form."""
        
        # Check cache first for common patterns
        cached = self._check_pattern_cache(query)
        if cached:
            logger.info(f"[CACHE HIT] Using cached pattern for '{query}'")
            # Still need to parse, but cache gives hints
        
        # Build context from conversation history for pronoun resolution
        context = ""
        if len(self.conversation_history) > 1:
            recent = self.conversation_history[-4:]  # Last 2 exchanges
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

        response = self.llm.generate(prompt)
        
        try:
            # Clean and parse JSON
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: minimal parse
            return {
                "intent": "describe",
                "subject": {"text": query, "likely_entity_types": []},
                "relationship": {"text": "", "likely_relationship_types": []}
            }
    
    def _resolve_entity(self, name: str, type_hints: list[str] = None) -> Optional[dict]:
        """STAGE 2a: Resolve entity name flexibly."""
        
        # Try exact match
        result = self.session.execute(
            text("""
                SELECT id, name, entity_type, attributes
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
        
        # Try fuzzy match
        result = self.session.execute(
            text("""
                SELECT id, name, entity_type, attributes,
                       similarity(LOWER(name), LOWER(:name)) as sim
                FROM entities
                WHERE tenant_id = :tenant_id
                AND LOWER(name) ILIKE :pattern
                AND lifecycle_state = 'TRUSTED'
                ORDER BY sim DESC
                LIMIT 1
            """),
            {"tenant_id": self.tenant_id, "name": name, "pattern": f"%{name}%"}
        ).fetchone()
        
        if result and result.sim > 0.3:
            return {
                "id": str(result.id),
                "name": result.name,
                "type": result.entity_type
            }
        
        return None
    
    def _discover_relationships(self, entity_id: str) -> list[dict]:
        """STAGE 2b: Discover all relationship types (both directions)."""
        
        results = self.session.execute(
            text("""
                SELECT relationship_type as type, 'outgoing' as direction, COUNT(*) as count
                FROM relationships
                WHERE tenant_id = :tenant_id
                AND source_entity_id = :entity_id
                AND lifecycle_state = 'TRUSTED'
                GROUP BY relationship_type
                
                UNION ALL
                
                SELECT relationship_type as type, 'incoming' as direction, COUNT(*) as count
                FROM relationships
                WHERE tenant_id = :tenant_id
                AND target_entity_id = :entity_id
                AND lifecycle_state = 'TRUSTED'
                GROUP BY relationship_type
            """),
            {"tenant_id": self.tenant_id, "entity_id": entity_id}
        ).fetchall()
        
        return [{"type": r.type, "direction": r.direction, "count": r.count} for r in results]
    
    def _match_relationship_types(self, user_phrase: str, available_types: list[str]) -> list[str]:
        """STAGE 2c: Use LLM to match user phrase against available KG types."""
        
        # Check cache first
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

        response = self.llm.generate(prompt)
        
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1].replace("json", "").strip()
            matched = json.loads(cleaned)
            
            # Validate
            matched = [t for t in matched if t in available_types]
            return matched[:5]  # Cap at 5
        except:
            # Fallback: simple string matching
            user_lower = user_phrase.lower()
            return [t for t in available_types if user_lower in t.lower() or t.lower() in user_lower]
    
    def _query_relationships(self, entity_id: str, rel_type: str, direction: str) -> dict:
        """STAGE 2d: Query relationships deterministically."""
        
        if direction == "outgoing":
            results = self.session.execute(
                text("""
                    SELECT e.name, e.entity_type, r.attributes
                    FROM relationships r
                    JOIN entities e ON e.id = r.target_entity_id
                    WHERE r.tenant_id = :tenant_id
                    AND r.source_entity_id = :entity_id
                    AND r.relationship_type = :rel_type
                    AND r.lifecycle_state = 'TRUSTED'
                """),
                {"tenant_id": self.tenant_id, "entity_id": entity_id, "rel_type": rel_type}
            ).fetchall()
        else:
            results = self.session.execute(
                text("""
                    SELECT e.name, e.entity_type, r.attributes
                    FROM relationships r
                    JOIN entities e ON e.id = r.source_entity_id
                    WHERE r.tenant_id = :tenant_id
                    AND r.target_entity_id = :entity_id
                    AND r.relationship_type = :rel_type
                    AND r.lifecycle_state = 'TRUSTED'
                """),
                {"tenant_id": self.tenant_id, "entity_id": entity_id, "rel_type": rel_type}
            ).fetchall()
        
        return {
            "count": len(results),
            "entities": [{"name": r.name, "type": r.entity_type} for r in results]
        }
    
    def _synthesize_response(self, query: str, parsed: dict, entity: dict, results: list) -> str:
        """STAGE 4: Use LLM to compose natural response."""
        
        prompt = f"""Compose a natural answer to this query.

Query: "{query}"
Subject: {entity['name']} ({entity['type']})

Data found:
{json.dumps(results, indent=2)}

Rules:
- Be concise but complete
- List ALL entities found (don't summarize or truncate)
- If multiple relationship types matched, explain both
- Use natural language, not technical jargon
- Don't mention "KG" or "relationships" - just answer naturally

Your answer:"""

        return self.llm.generate(prompt)
    
    def _document_fallback(self, query: str) -> dict:
        """STAGE 3: Fall back to document search when KG doesn't have answer."""
        
        logger.info(f"[STAGE 3] Document fallback for: {query}")
        
        # Search documents
        results = self.doc_search.search(query, limit=5)
        
        if not results:
            return {
                "answer": "I don't have enough information to answer this question.",
                "confidence": 0.2,
                "sources": [],
                "method": "document_fallback_empty"
            }
        
        # Use LLM to extract answer from documents
        context = "\n\n".join([r.get("content", r.get("text", "")) for r in results[:3]])
        
        prompt = f"""Answer this question based on the following document excerpts.

Question: "{query}"

Documents:
{context}

If the documents contain the answer, provide it. If not, say you don't have enough information.

Your answer:"""

        answer = self.llm.generate(prompt)
        
        # Log as potential ontology proposal
        self._log_ontology_proposal(query, results)
        
        return {
            "answer": answer,
            "confidence": 0.6,
            "sources": [{"type": "document", "chunk_id": r.get("id")} for r in results[:3]],
            "method": "document_fallback"
        }
    
    def _check_pattern_cache(self, query: str) -> Optional[list[str]]:
        """Check if we have cached patterns for this query."""
        # Simplified - just check for key phrases
        return None  # TODO: Implement full cache lookup
    
    def _check_type_cache(self, phrase: str) -> Optional[list[str]]:
        """Check if we have cached type mappings for this phrase."""
        
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
        return None
    
    def _log_pattern(self, phrase: str, matched_types: list[str]):
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
            except Exception as e:
                logger.warning(f"Failed to log pattern: {e}")
    
    def _log_ontology_proposal(self, query: str, results: list):
        """Log document fallback as potential ontology proposal."""
        
        try:
            self.session.execute(
                text("""
                    INSERT INTO ontology_proposals 
                    (tenant_id, source, query, inferred_type, type_category, evidence_chunk_id)
                    VALUES (:tenant_id, 'document_fallback', :query, 'UNKNOWN', 'relationship', :chunk_id)
                """),
                {
                    "tenant_id": self.tenant_id,
                    "query": query,
                    "chunk_id": results[0].get("id") if results else None
                }
            )
        except Exception as e:
            logger.warning(f"Failed to log ontology proposal: {e}")
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
```

### Task 5: Wire Into API Endpoint

Update the chat endpoint to use the new agent:

```python
# In your API router

@router.post("/api/vault/chat")
async def vault_chat(request: ChatRequest):
    # Get or create agent
    agent = QueryTimeSemanticAgent(
        session=get_session(),
        tenant_id=get_tenant_id(),
        llm_client=get_llm(),
        doc_searcher=get_doc_searcher()
    )
    
    # Load conversation history if session_id provided
    if request.session_id:
        agent.conversation_history = load_conversation_history(request.session_id)
    
    # Process query
    result = agent.query(request.query)
    
    # Save conversation history
    if request.session_id:
        save_conversation_history(request.session_id, agent.conversation_history)
    
    return {
        "response": result["answer"],
        "confidence": result["confidence"],
        "sources": result.get("sources", []),
        "method": result.get("method", "unknown")
    }
```

### Task 6: Update Agent System Prompt

If keeping the existing tool-calling agent, update its system prompt:

```python
SYSTEM_PROMPT = """You are Context Foundry, an AI assistant with access to a knowledge graph and documents.

QUERY FLOW:
1. PARSE the query to understand intent, subject, and relationship
2. RESOLVE the subject entity (case-insensitive)
3. DISCOVER what relationship types exist for that entity
4. MATCH the user's language against available types
5. QUERY deterministically for counts/lists
6. If KG doesn't have the answer, SEARCH documents

IMPORTANT RULES:
- Never assume what relationship types exist - always discover first
- Match user language to available types, don't guess
- For ambiguous terms like "jobs", check BOTH HELD_POSITION and WORKED_AT
- Always check both incoming and outgoing relationships
- If no KG match, fall back to document search
- Resolve pronouns using conversation history

TOOLS:
- resolve_entities: Find entity by name
- discover_relationships: See what relationship types exist (both directions!)
- expand_to_kg_types: Match user phrase to available KG types
- count_by_relationship_type: Get deterministic count
- search_documents: Fallback when KG doesn't have answer

Example flow for "How many companies has Horizon invested in?":
1. Parse: intent=count, subject="Horizon", relationship="invested in"
2. Resolve: "Horizon" → Horizon Ventures (FUND)
3. Discover: [INVESTED_IN(10), EMPLOYS(4)]
4. Match: "invested in" → INVESTED_IN
5. Count: 10 companies
6. Answer: "Horizon Ventures has invested in 10 companies: ..."
"""
```

## TESTING

After implementation, test these queries WITHOUT any code changes:

| # | Query | Expected Behavior |
|---|-------|-------------------|
| 1 | "How many jobs has Saleh done?" | Discovers HELD_POSITION + WORKED_AT, returns both |
| 2 | "how many jobs has saleh done?" | Same as #1 (case insensitive) |
| 3 | "What roles did he have?" | Resolves "he" from context, lists positions |
| 4 | "How many companies has Horizon invested in?" | Matches INVESTED_IN, counts correctly |
| 5 | "How many people are on Project Phoenix?" | Discovers incoming WORKS_ON + LEADS |
| 6 | "How many authors on the federated learning paper?" | Matches AUTHORED |
| 7 | "How many speakers at the Global AI Summit?" | Matches SPEAKS_AT |
| 8 | "What is Horizon's investment philosophy?" | Falls back to document search |

## SUCCESS CRITERIA

- [ ] All 8 test queries work without code changes
- [ ] Latency ≤2.5s for 90th percentile
- [ ] No hardcoded synonym mappings
- [ ] Document fallback works when KG doesn't have answer
- [ ] Learning loop caches successful patterns
- [ ] Conversation history enables follow-ups

## CONFIGURATION

```python
# config.py
SEMANTIC_AGENT_CONFIG = {
    "max_latency_ms": 2500,
    "max_type_suggestions": 5,
    "max_relationship_matches": 3,
    "cache_min_success_count": 3,  # Require 3 successes before using cache
    "cache_ttl_days": 30,
    "enable_learning_loop": True,
    "enable_ontology_proposals": True,
}
```

## ROLLOUT

1. Implement behind feature flag: `?semantic_agent=true`
2. Test with 5 diverse documents
3. Compare latency and accuracy vs old agent
4. If successful, make default
5. Remove old aggregation framework code
