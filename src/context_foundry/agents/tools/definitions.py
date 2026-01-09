"""
OpenAI function calling schema definitions for Context Foundry tools.

These tools enable the agent to:
1. resolve_entities - Resolve entity names to canonical IDs
2. run_aggregation - Get deterministic counts/sums from knowledge graph
3. get_knowledge_bundle - Get KG relationships and context for entities
4. search_documents - Search uploaded documents via vector similarity
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "resolve_entities",
            "description": "Resolve entity names to canonical IDs. ALWAYS use before any KG operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Entity names to resolve"
                    }
                },
                "required": ["names"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_aggregation",
            "description": "Get deterministic counts/sums from knowledge graph. MUST use for any numeric answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The counting/aggregation question"
                    },
                    "anchor_entities": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Resolved entities from resolve_entities"
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_knowledge_bundle",
            "description": "Get KG relationships and context for entities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query describing what information to retrieve"
                    },
                    "entity_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Entity IDs to get relationships for"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search uploaded documents for information not in knowledge graph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for document retrieval"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 5,
                        "description": "Maximum number of results to return"
                    }
                },
                "required": ["query"]
            }
        }
    }
]
