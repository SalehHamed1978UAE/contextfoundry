"""
Config-Driven Query Intent Detector

Detects query intent (relationship vs attribute) from natural language queries.
Uses YAML config for indicators - add new patterns without code changes.

Fixes three bug categories:
1. REPORTS_TO with person names (not just roles)
2. Compensation queries for any role (not just CEO)
3. Department lead queries (LEADS relationship)
"""

import re
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.context_foundry.utils.logger import logger


@dataclass
class QueryIntent:
    """Structured intent from query analysis."""
    intent_type: str
    relationship_type: Optional[str] = None
    attribute_type: Optional[str] = None
    target_entity: Optional[str] = None
    target_entity_id: Optional[str] = None
    direction: str = "outbound"
    search_terms: List[str] = field(default_factory=list)
    target_types: List[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "intent_type": self.intent_type,
            "relationship_type": self.relationship_type,
            "attribute_type": self.attribute_type,
            "target_entity": self.target_entity,
            "target_entity_id": self.target_entity_id,
            "direction": self.direction,
            "search_terms": self.search_terms,
            "target_types": self.target_types,
            "confidence": self.confidence
        }


class QueryIntentDetector:
    """
    Config-driven query intent detection.
    
    Detects:
    - Relationship intents (REPORTS_TO, LEADS, INVESTED_IN)
    - Attribute intents (COMPENSATION, LOCATION, TENURE)
    - Extracts target entity from query text
    """
    
    PERSON_NAME_PATTERN = re.compile(
        r'(?:to|for|by|of|about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        re.IGNORECASE
    )
    
    DEPARTMENT_PATTERN = re.compile(
        r'(?:leads?|heads?|runs?|chairs?|in charge of)\s+(?:the\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?:\s+department|\s+team|\s+division)?(?:\s|$|\?)',
        re.IGNORECASE
    )
    
    def __init__(self, session: Session, tenant_id: str, config_path: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.config = self._load_config(config_path)
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load query intent config from YAML with validation and fallback."""
        if config_path is None:
            config_path = "config/query_intents.yaml"
        
        path = Path(config_path)
        config = None
        
        if path.exists():
            try:
                with open(path) as f:
                    config = yaml.safe_load(f)
                    logger.info(f"[INTENT] Loaded config from {config_path}")
            except Exception as e:
                logger.warning(f"[INTENT] Failed to load config: {e}, using defaults")
                config = None
        
        if config is None:
            logger.warning(f"[INTENT] Config not found at {config_path}, using defaults")
            return self._default_config()
        
        validated = self._validate_config(config)
        return validated
    
    def _validate_config(self, config: Dict) -> Dict:
        """Validate config structure and add defaults for missing keys."""
        defaults = self._default_config()
        
        if not isinstance(config, dict):
            return defaults
        
        if 'relationship_queries' not in config or not isinstance(config.get('relationship_queries'), dict):
            config['relationship_queries'] = defaults['relationship_queries']
        else:
            for rel_type, rel_config in config['relationship_queries'].items():
                if not isinstance(rel_config, dict):
                    continue
                if 'indicators' not in rel_config:
                    rel_config['indicators'] = []
                if 'inverse_indicators' not in rel_config:
                    rel_config['inverse_indicators'] = []
                if 'entity_position' not in rel_config:
                    rel_config['entity_position'] = 'target'
        
        if 'attribute_queries' not in config or not isinstance(config.get('attribute_queries'), dict):
            config['attribute_queries'] = defaults['attribute_queries']
        else:
            for attr_type, attr_config in config['attribute_queries'].items():
                if not isinstance(attr_config, dict):
                    continue
                if 'indicators' not in attr_config:
                    attr_config['indicators'] = []
                if 'search_terms' not in attr_config:
                    attr_config['search_terms'] = [attr_type.lower()]
        
        return config
    
    def _default_config(self) -> Dict:
        """Default config if YAML not found."""
        return {
            'relationship_queries': {
                'REPORTS_TO': {
                    'indicators': ['reports to', 'managed by', 'works for'],
                    'inverse_indicators': ['manages', 'supervises'],
                    'entity_position': 'target'
                },
                'LEADS': {
                    'indicators': ['leads', 'heads', 'runs', 'in charge of'],
                    'inverse_indicators': ['led by', 'headed by'],
                    'entity_position': 'source',
                    'target_types': ['DEPARTMENT', 'TEAM']
                }
            },
            'attribute_queries': {
                'COMPENSATION': {
                    'indicators': ['compensation', 'salary', 'pay', 'bonus'],
                    'search_terms': ['compensation', 'salary', 'bonus']
                }
            }
        }
    
    def detect(self, query: str, resolved_entity: Optional[str] = None) -> QueryIntent:
        """
        Detect query intent from natural language.
        
        Args:
            query: The user's query
            resolved_entity: Entity already resolved (from role resolution)
            
        Returns:
            QueryIntent with structured intent information
        """
        query_lower = query.lower()
        
        rel_intent = self._detect_relationship_intent(query_lower)
        if rel_intent:
            entity = resolved_entity or self._extract_entity(query, rel_intent.relationship_type)
            entity_id = self._resolve_entity_id(entity) if entity else None
            rel_intent.target_entity = entity
            rel_intent.target_entity_id = entity_id
            logger.info(f"[INTENT] Detected relationship: {rel_intent.relationship_type}, entity={entity}, direction={rel_intent.direction}")
            return rel_intent
        
        attr_intent = self._detect_attribute_intent(query_lower)
        if attr_intent:
            entity = resolved_entity or self._extract_entity(query, None)
            entity_id = self._resolve_entity_id(entity) if entity else None
            attr_intent.target_entity = entity
            attr_intent.target_entity_id = entity_id
            logger.info(f"[INTENT] Detected attribute: {attr_intent.attribute_type}, entity={entity}")
            return attr_intent
        
        logger.info("[INTENT] No specific intent detected, returning general")
        return QueryIntent(
            intent_type="general",
            target_entity=resolved_entity,
            confidence=0.3
        )
    
    def _detect_relationship_intent(self, query: str) -> Optional[QueryIntent]:
        """Detect relationship type from query indicators."""
        rel_config = self.config.get('relationship_queries', {})
        
        for rel_type, config in rel_config.items():
            for indicator in config.get('inverse_indicators', []):
                if indicator in query:
                    return QueryIntent(
                        intent_type="relationship",
                        relationship_type=rel_type,
                        direction="outbound",
                        target_types=config.get('target_types', []),
                        confidence=0.85
                    )
            
            for indicator in config.get('indicators', []):
                if indicator in query:
                    entity_pos = config.get('entity_position', 'target')
                    direction = "inbound" if entity_pos == "target" else "outbound"
                    return QueryIntent(
                        intent_type="relationship",
                        relationship_type=rel_type,
                        direction=direction,
                        target_types=config.get('target_types', []),
                        confidence=0.85
                    )
        
        return None
    
    def _detect_attribute_intent(self, query: str) -> Optional[QueryIntent]:
        """Detect attribute type from query indicators."""
        attr_config = self.config.get('attribute_queries', {})
        
        for attr_type, config in attr_config.items():
            for indicator in config.get('indicators', []):
                if indicator in query:
                    return QueryIntent(
                        intent_type="attribute",
                        attribute_type=attr_type,
                        search_terms=config.get('search_terms', []),
                        confidence=0.85
                    )
        
        return None
    
    def _extract_entity(self, query: str, relationship_type: Optional[str]) -> Optional[str]:
        """Extract entity name from query text."""
        if relationship_type == 'LEADS':
            match = self.DEPARTMENT_PATTERN.search(query)
            if match:
                dept = match.group(1).strip()
                logger.info(f"[INTENT] Extracted department: {dept}")
                return dept
        
        match = self.PERSON_NAME_PATTERN.search(query)
        if match:
            name = match.group(1).strip()
            logger.info(f"[INTENT] Extracted person name: {name}")
            return name
        
        return None
    
    def _resolve_entity_id(self, entity_name: str) -> Optional[str]:
        """Look up entity ID from database."""
        if not entity_name:
            return None
        
        try:
            query = text("""
                SELECT id, name, entity_type
                FROM entities
                WHERE tenant_id = :tenant_id
                AND LOWER(name) LIKE :name_pattern
                ORDER BY confidence DESC
                LIMIT 1
            """)
            
            result = self.session.execute(query, {
                "tenant_id": self.tenant_id,
                "name_pattern": f"%{entity_name.lower()}%"
            }).fetchone()
            
            if result:
                logger.info(f"[INTENT] Resolved entity '{entity_name}' -> {result.id}")
                return str(result.id)
        except Exception as e:
            logger.error(f"[INTENT] Entity resolution failed: {e}")
        
        return None


class DirectedRelationshipRetriever:
    """
    Retrieves relationships with direction awareness.
    
    Handles:
    - "Who reports to X?" → inbound REPORTS_TO where target=X
    - "Who does X manage?" → outbound REPORTS_TO where source=X
    """
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def retrieve(
        self,
        intent: QueryIntent,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relationships based on intent direction.
        
        Args:
            intent: QueryIntent with relationship_type, direction, target_entity
            limit: Max results
            
        Returns:
            List of relationship dicts
        """
        if not intent.relationship_type:
            return []
        
        if intent.relationship_type == "LEADS" and intent.target_entity:
            results = self._retrieve_by_entity_name(intent, limit)
            if results:
                return results
        
        if intent.target_entity_id:
            results = self._retrieve_by_entity_id(intent, limit)
            if results:
                return results
            if intent.target_entity:
                return self._retrieve_by_entity_name(intent, limit)
            return []
        elif intent.target_entity:
            return self._retrieve_by_entity_name(intent, limit)
        else:
            return self._retrieve_all_of_type(intent, limit)
    
    def _retrieve_by_entity_id(self, intent: QueryIntent, limit: int) -> List[Dict]:
        """Retrieve relationships for specific entity ID."""
        if intent.direction == "inbound":
            query = text("""
                SELECT 
                    r.id, r.relationship_type, r.confidence, r.provenance_text,
                    src.name as source_name, src.entity_type as source_type,
                    tgt.name as target_name, tgt.entity_type as target_type
                FROM relationships r
                JOIN entities src ON r.source_id = src.id
                JOIN entities tgt ON r.target_id = tgt.id
                WHERE r.tenant_id = :tenant_id
                AND r.relationship_type = :rel_type
                AND r.target_id = :entity_id
                ORDER BY r.confidence DESC
                LIMIT :limit
            """)
        else:
            query = text("""
                SELECT 
                    r.id, r.relationship_type, r.confidence, r.provenance_text,
                    src.name as source_name, src.entity_type as source_type,
                    tgt.name as target_name, tgt.entity_type as target_type
                FROM relationships r
                JOIN entities src ON r.source_id = src.id
                JOIN entities tgt ON r.target_id = tgt.id
                WHERE r.tenant_id = :tenant_id
                AND r.relationship_type = :rel_type
                AND r.source_id = :entity_id
                ORDER BY r.confidence DESC
                LIMIT :limit
            """)
        
        try:
            results = self.session.execute(query, {
                "tenant_id": self.tenant_id,
                "rel_type": intent.relationship_type,
                "entity_id": intent.target_entity_id,
                "limit": limit
            }).fetchall()
            
            return [
                {
                    "id": str(r.id),
                    "type": r.relationship_type,
                    "source": r.source_name,
                    "source_type": r.source_type,
                    "target": r.target_name,
                    "target_type": r.target_type,
                    "confidence": r.confidence,
                    "provenance": r.provenance_text
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"[DIRECTED_RETRIEVER] Query failed: {e}")
            return []
    
    def _retrieve_by_entity_name(self, intent: QueryIntent, limit: int) -> List[Dict]:
        """Retrieve relationships by entity name match."""
        if intent.relationship_type == "LEADS" and intent.target_types:
            query = text("""
                SELECT 
                    r.id, r.relationship_type, r.confidence, r.provenance_text,
                    src.name as source_name, src.entity_type as source_type,
                    tgt.name as target_name, tgt.entity_type as target_type
                FROM relationships r
                JOIN entities src ON r.source_id = src.id
                JOIN entities tgt ON r.target_id = tgt.id
                WHERE r.tenant_id = :tenant_id
                AND (
                    (r.relationship_type = :rel_type AND LOWER(tgt.name) LIKE :entity_pattern)
                    OR (r.relationship_type IN ('HOLD_POSITION', 'HOLDS_POSITION', 'HELD_POSITION') 
                        AND tgt.entity_type = 'ROLE' 
                        AND LOWER(tgt.name) LIKE :entity_pattern)
                    OR (r.relationship_type ILIKE '%LEAD%' AND LOWER(tgt.name) LIKE :entity_pattern)
                    OR (r.relationship_type ILIKE '%HEAD%' AND LOWER(tgt.name) LIKE :entity_pattern)
                    OR (r.relationship_type ILIKE '%CHAIR%' AND LOWER(tgt.name) LIKE :entity_pattern)
                )
                ORDER BY r.confidence DESC
                LIMIT :limit
            """)
        elif intent.direction == "inbound":
            query = text("""
                SELECT 
                    r.id, r.relationship_type, r.confidence, r.provenance_text,
                    src.name as source_name, src.entity_type as source_type,
                    tgt.name as target_name, tgt.entity_type as target_type
                FROM relationships r
                JOIN entities src ON r.source_id = src.id
                JOIN entities tgt ON r.target_id = tgt.id
                WHERE r.tenant_id = :tenant_id
                AND r.relationship_type = :rel_type
                AND LOWER(tgt.name) LIKE :entity_pattern
                ORDER BY r.confidence DESC
                LIMIT :limit
            """)
        else:
            query = text("""
                SELECT 
                    r.id, r.relationship_type, r.confidence, r.provenance_text,
                    src.name as source_name, src.entity_type as source_type,
                    tgt.name as target_name, tgt.entity_type as target_type
                FROM relationships r
                JOIN entities src ON r.source_id = src.id
                JOIN entities tgt ON r.target_id = tgt.id
                WHERE r.tenant_id = :tenant_id
                AND r.relationship_type = :rel_type
                AND LOWER(src.name) LIKE :entity_pattern
                ORDER BY r.confidence DESC
                LIMIT :limit
            """)
        
        try:
            results = self.session.execute(query, {
                "tenant_id": self.tenant_id,
                "rel_type": intent.relationship_type,
                "entity_pattern": f"%{intent.target_entity.lower()}%",
                "limit": limit
            }).fetchall()
            
            return [
                {
                    "id": str(r.id),
                    "type": r.relationship_type,
                    "source": r.source_name,
                    "source_type": r.source_type,
                    "target": r.target_name,
                    "target_type": r.target_type,
                    "confidence": r.confidence,
                    "provenance": r.provenance_text
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"[DIRECTED_RETRIEVER] Query failed: {e}")
            return []
    
    def _retrieve_all_of_type(self, intent: QueryIntent, limit: int) -> List[Dict]:
        """Retrieve all relationships of a type (fallback)."""
        query = text("""
            SELECT 
                r.id, r.relationship_type, r.confidence, r.provenance_text,
                src.name as source_name, src.entity_type as source_type,
                tgt.name as target_name, tgt.entity_type as target_type
            FROM relationships r
            JOIN entities src ON r.source_id = src.id
            JOIN entities tgt ON r.target_id = tgt.id
            WHERE r.tenant_id = :tenant_id
            AND r.relationship_type = :rel_type
            ORDER BY r.confidence DESC
            LIMIT :limit
        """)
        
        try:
            results = self.session.execute(query, {
                "tenant_id": self.tenant_id,
                "rel_type": intent.relationship_type,
                "limit": limit
            }).fetchall()
            
            return [
                {
                    "id": str(r.id),
                    "type": r.relationship_type,
                    "source": r.source_name,
                    "source_type": r.source_type,
                    "target": r.target_name,
                    "target_type": r.target_type,
                    "confidence": r.confidence,
                    "provenance": r.provenance_text
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"[DIRECTED_RETRIEVER] Query failed: {e}")
            return []


class DirectedAttributeRetriever:
    """
    Retrieves attribute values using config-defined search terms.
    
    Handles:
    - "What is the CIO's compensation?" → search for Robert Thompson + compensation terms
    - "What is Sarah Chen's salary?" → search for Sarah Chen + salary terms
    """
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def retrieve(
        self,
        intent: QueryIntent,
        resolved_name: Optional[str] = None,
        original_role: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve attribute values from documents.
        
        Args:
            intent: QueryIntent with attribute_type and search_terms
            resolved_name: Resolved person name (from role resolution)
            original_role: Original role/title term (e.g., "CIO") for additional search
            limit: Max results
            
        Returns:
            List of document chunks with attribute data
        """
        if not intent.attribute_type:
            return []
        
        entity_name = resolved_name or intent.target_entity
        if not entity_name:
            logger.warning("[ATTR_RETRIEVER] No entity name for attribute lookup")
            return []
        
        search_terms = intent.search_terms
        if not search_terms:
            search_terms = [intent.attribute_type.lower()]
        
        all_chunks = []
        
        search_entities = [entity_name]
        if original_role and original_role.lower() != entity_name.lower():
            search_entities.append(original_role)
        
        for entity in search_entities:
            for term in search_terms[:2]:
                search_query = f"{entity} {term}"
                chunks = self._search_documents(search_query, limit=limit)
                all_chunks.extend(chunks)
                
                if len(all_chunks) >= limit * 2:
                    break
            if len(all_chunks) >= limit * 2:
                break
        
        seen_ids = set()
        unique_chunks = []
        for chunk in all_chunks:
            if chunk['id'] not in seen_ids:
                seen_ids.add(chunk['id'])
                unique_chunks.append(chunk)
        
        logger.info(f"[ATTR_RETRIEVER] Found {len(unique_chunks)} chunks for {entity_name}/{original_role} + {intent.attribute_type}")
        return unique_chunks[:limit]
    
    def _search_documents(self, query: str, limit: int = 5) -> List[Dict]:
        """Search document chunks."""
        from src.context_foundry.search.document_searcher import DocumentSearcher
        
        try:
            searcher = DocumentSearcher(self.session, self.tenant_id)
            results = searcher.search(query, limit=limit, use_vector=True)
            
            return [
                {
                    "id": r.get("id", ""),
                    "text": r.get("text", ""),
                    "document": r.get("document_name", "Unknown"),
                    "similarity": r.get("similarity", 0.6)
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"[ATTR_RETRIEVER] Search failed: {e}")
            return []
