"""
Query Classifier and Data Sufficiency Checker

Implements query classification for intelligent routing:
- Classify queries by type (RELATIONSHIP, ATTRIBUTE, AGGREGATION, EXPLORATION)
- Detect role references (CEO, CTO, CFO) that need resolution
- Detect list queries that expect multiple results
- Check data sufficiency before routing to LLM
- Gate queries that lack sufficient data for safe answering
"""

import json
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from openai import OpenAI

from src.context_foundry.utils.logger import logger


@dataclass
class QueryClassification:
    """Result of query classification for intelligent routing."""
    query_type: str              # RELATIONSHIP | ATTRIBUTE | AGGREGATION | EXPLORATION
    retrieval_strategy: str      # GRAPH_ONLY | DOCS_ONLY | HYBRID
    target_entity: Optional[str] # Entity mentioned in query
    has_role_reference: bool     # Does query reference a role (CEO, CTO)?
    role_referenced: Optional[str]  # The role if referenced (CEO, CTO, etc.)
    expects_list: bool           # Does query expect multiple results?
    confidence: float
    reasoning: str
    
    def to_dict(self) -> dict:
        return {
            "query_type": self.query_type,
            "retrieval_strategy": self.retrieval_strategy,
            "target_entity": self.target_entity,
            "has_role_reference": self.has_role_reference,
            "role_referenced": self.role_referenced,
            "expects_list": self.expects_list,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


class QueryClassifier:
    """Classifies queries for intelligent routing."""
    
    ROLE_KEYWORDS = {
        'ceo', 'cto', 'cfo', 'coo', 'cdo', 'cmo', 'cio', 'ciso',
        'chief executive officer', 'chief technology officer', 
        'chief financial officer', 'chief operating officer',
        'chief data officer', 'chief marketing officer',
        'president', 'vp', 'vice president', 'director',
        'general counsel', 'controller', 'treasurer'
    }
    
    LIST_INDICATORS = {
        'portfolio companies', 'companies', 'who reports', 'reports to',
        'list all', 'what are the', 'which teams', 'how many',
        'employees', 'members', 'executives', 'investments'
    }
    
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.llm_client = OpenAI()
        self.llm_model = llm_model
        # Pre-compile regex patterns for person-role and org-unit queries
        # These patterns check for proper names (capitalized words) to avoid false positives
        import re
        
        # Person-role patterns - looking for proper names (First Last) with role keywords
        self._person_role_re = [
            # "What is [Name]'s role/position/title/job?"
            re.compile(r"what is ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'s (?:role|position|title|job)", re.IGNORECASE),
            # "[Name]'s role/position/title/job/responsibilities"
            re.compile(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)'s (?:role|position|title|job|responsibilities)", re.IGNORECASE),
            # "What does [Name] do?"
            re.compile(r"what does ([A-Z][a-z]+\s+[A-Z][a-z]+) do\b", re.IGNORECASE),
            # "Who is [Name]?" - but NOT "Who is the CEO?"
            re.compile(r"who is ([A-Z][a-z]+\s+[A-Z][a-z]+)\??$", re.IGNORECASE),
            # "What is/are the responsibilities of [Name]?"
            re.compile(r"what (?:are|is) the (?:responsibilities|duties) of ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", re.IGNORECASE),
        ]
        
        # Org-unit patterns - business unit/division queries
        self._org_unit_re = [
            re.compile(r"what (?:are|is) the (?:four |main |primary )?business units?\b", re.IGNORECASE),
            re.compile(r"(?:main|primary|key) business (?:units|areas|segments)\b", re.IGNORECASE),
            re.compile(r"what does (?:Orion|the) [\w\s]+ (?:focus on|specialize in)\??$", re.IGNORECASE),
            re.compile(r"tell me about (?:the )?[\w\s]+ (?:division|business unit|department)\b", re.IGNORECASE),
        ]
    
    def _quick_role_check(self, query: str) -> tuple:
        """Fast regex-free check for role references."""
        query_lower = query.lower()
        for role in self.ROLE_KEYWORDS:
            if role in query_lower:
                return True, role.upper()
        return False, None
    
    def _quick_list_check(self, query: str) -> bool:
        """Fast check for list query indicators."""
        query_lower = query.lower()
        for indicator in self.LIST_INDICATORS:
            if indicator in query_lower:
                return True
        return False
    
    def _is_proper_name(self, text: str) -> bool:
        """Check if text looks like a proper name (First Last format with capitalization)."""
        if not text:
            return False
        # Proper names have capitalized words (Sarah Chen, Evelyn Reed)
        # Exclude patterns like "the CEO", "the company", etc.
        words = text.strip().split()
        if len(words) < 2:
            return False
        # Each word should start with uppercase and rest lowercase (typical name format)
        for word in words:
            if not word[0].isupper():  # First letter must be uppercase
                return False
            if len(word) > 1 and word[1:].lower() != word[1:]:  # Rest should be lowercase
                return False
        return True
    
    def _should_use_graph_first(self, query: str) -> tuple:
        """
        Check if query should prioritize Knowledge Graph over document search.
        
        Returns: (should_use_kg, reason)
        
        These patterns indicate the answer likely lives in the KG:
        - Person-role queries (What is Sarah Chen's role?)
        - Business unit definitions (What are the business units?)
        - Organizational structure queries
        """
        # Check person-role patterns and validate that matched name is a proper name
        for pattern in self._person_role_re:
            match = pattern.search(query)
            if match:
                # Patterns capture the name in group 1 - validate it's a proper name
                name = match.group(1) if match.lastindex else None
                if name and self._is_proper_name(name):
                    logger.info(f"[CLASSIFIER] Person-role pattern detected for '{name}': prioritizing KG")
                    return True, "person_role_query"
        
        for pattern in self._org_unit_re:
            if pattern.search(query):
                logger.info(f"[CLASSIFIER] Org-unit pattern detected: prioritizing KG")
                return True, "org_unit_query"
        
        return False, None
    
    def classify(self, query: str) -> QueryClassification:
        """Classify a query and determine retrieval strategy."""
        
        has_role, role_name = self._quick_role_check(query)
        expects_list = self._quick_list_check(query)
        
        prompt = f"""Classify this query for a knowledge retrieval system.

QUERY: "{query}"

Analyze and return:

1. QUERY_TYPE:
   - RELATIONSHIP: Questions about connections (who owns, founded, depends on, reports to)
   - ATTRIBUTE: Questions about specific facts/properties (salary, revenue, date, count)
   - AGGREGATION: Questions requiring counts/sums (how many, total, count of)
   - EXPLORATION: Open-ended questions (tell me about, describe, what is)

2. RETRIEVAL_STRATEGY:
   - GRAPH_ONLY: Relationships stored in knowledge graph (ownership, dependencies, org structure)
   - DOCS_ONLY: Specific values likely only in documents (numbers, dates, detailed descriptions)
   - HYBRID: Need both, or exploration queries

3. TARGET_ENTITY: The main entity being asked about (company name, person name, etc.)

4. HAS_ROLE_REFERENCE: Does the query reference a job role/title instead of a person's name?
   - true if: "CEO's salary", "what does the CTO do", "who reports to CFO"
   - false if: "Sarah Chen's salary", "what does Marcus do"

5. ROLE_REFERENCED: If has_role_reference is true, what role? (CEO, CTO, CFO, President, etc.)

6. EXPECTS_LIST: Does the query expect multiple items in response?
   - true if: "what companies", "who reports to", "list all", "what are the", "which teams"
   - false if: "who is the CEO", "what is the revenue", "when was it founded"

RESPOND WITH JSON ONLY:
{{
    "query_type": "RELATIONSHIP | ATTRIBUTE | AGGREGATION | EXPLORATION",
    "retrieval_strategy": "GRAPH_ONLY | DOCS_ONLY | HYBRID",
    "target_entity": "entity name or null",
    "has_role_reference": true | false,
    "role_referenced": "role name or null",
    "expects_list": true | false,
    "confidence": 0.0-1.0,
    "reasoning": "one sentence explanation"
}}"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=300
            )
            
            content = response.choices[0].message.content.strip()
            
            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        content = part
                        break
            
            result = json.loads(content)
            
            llm_has_role = result.get("has_role_reference", False)
            llm_role = result.get("role_referenced")
            llm_expects_list = result.get("expects_list", False)
            
            final_expects_list = expects_list or llm_expects_list
            
            strategy = result.get("retrieval_strategy", "HYBRID")
            if final_expects_list and strategy == "GRAPH_ONLY":
                logger.info(f"[CLASSIFIER] Overriding GRAPH_ONLY → HYBRID for list query (KG coverage uncertain)")
                strategy = "HYBRID"
            
            # Override: Person-role and org-unit queries should use HYBRID (KG-first with doc fallback)
            # These patterns indicate data likely lives in KG, but use HYBRID to allow doc fallback
            should_graph_first, graph_reason = self._should_use_graph_first(query)
            if should_graph_first and strategy == "DOCS_ONLY":
                logger.info(f"[CLASSIFIER] Overriding DOCS_ONLY → HYBRID for {graph_reason} (KG-first with doc fallback)")
                strategy = "HYBRID"
            
            classification = QueryClassification(
                query_type=result.get("query_type", "EXPLORATION"),
                retrieval_strategy=strategy,
                target_entity=result.get("target_entity"),
                has_role_reference=has_role or llm_has_role,
                role_referenced=role_name or llm_role,
                expects_list=final_expects_list,
                confidence=result.get("confidence", 0.5),
                reasoning=result.get("reasoning", "")
            )
            
            logger.info(f"[CLASSIFIER] Query: '{query[:50]}...' if len(query) > 50 else '{query}'")
            logger.info(f"[CLASSIFIER] Type: {classification.query_type}, Strategy: {classification.retrieval_strategy}")
            logger.info(f"[CLASSIFIER] Role ref: {classification.has_role_reference} ({classification.role_referenced}), List: {classification.expects_list}")
            
            return classification
            
        except Exception as e:
            logger.error(f"[CLASSIFIER] Classification failed: {e}")
            return QueryClassification(
                query_type="EXPLORATION",
                retrieval_strategy="HYBRID",
                target_entity=None,
                has_role_reference=has_role,
                role_referenced=role_name,
                expects_list=expects_list,
                confidence=0.0,
                reasoning=f"Classification failed: {e}"
            )


def classify_query(query: str) -> str:
    """
    Classify query type for routing decisions.
    
    IMPORTANT: Check most specific patterns first (impact, relationship) 
    before generic patterns (existence) to avoid false positives.
    
    Returns one of: 'existence', 'relationship', 'impact', 'general'
    """
    query_lower = query.lower()
    
    impact_keywords = [
        'blast', 'radius', 'impact', 'affects', 'affected',
        'fail', 'fails', 'failure', 'outage',
        'cascade', 'cascading', 'downstream impact',
        'what happens if', 'what breaks',
        'go down', 'goes down', 'went down'
    ]
    if any(w in query_lower for w in impact_keywords):
        return 'impact'
    
    relationship_keywords = [
        'depend', 'depends on', 'dependency', 'dependencies',
        'owner', 'owns', 'owned by', 'who owns',
        'manages', 'managed by', 'manager',
        'connects', 'connected to', 'connection',
        'related', 'relationship', 'upstream', 'downstream',
        'talks to', 'calls', 'uses', 'used by',
        'reports to', 'escalate', 'escalation'
    ]
    if any(w in query_lower for w in relationship_keywords):
        return 'relationship'
    
    existence_keywords = ['exist', 'is there', 'do we have', 'do you know']
    if any(w in query_lower for w in existence_keywords):
        return 'existence'
    
    return 'general'


def get_data_sufficiency(session: Session, entity_id: str) -> dict:
    """
    Check if entity has enough data for different query types.
    
    Uses raw SQL for efficiency - this is called on every query.
    
    Returns:
        {
            'level': 'empty' | 'sparse' | 'adequate' | 'rich',
            'relationship_count': int,
            'outgoing_count': int,
            'incoming_count': int,
            'can_answer_relationship': bool,
            'can_answer_impact': bool
        }
    """
    result = session.execute(text("""
        SELECT 
            COUNT(*) FILTER (WHERE source_id = :entity_id) as outgoing,
            COUNT(*) FILTER (WHERE target_id = :entity_id) as incoming
        FROM relationships
        WHERE lifecycle_state = 'TRUSTED'
          AND (source_id = :entity_id OR target_id = :entity_id)
    """), {'entity_id': entity_id}).fetchone()
    
    outgoing = result[0] if result else 0
    incoming = result[1] if result else 0
    rel_count = outgoing + incoming
    
    if rel_count == 0:
        level = 'empty'
    elif rel_count < 3:
        level = 'sparse'
    elif rel_count < 6:
        level = 'adequate'
    else:
        level = 'rich'
    
    return {
        'level': level,
        'relationship_count': rel_count,
        'outgoing_count': outgoing,
        'incoming_count': incoming,
        'can_answer_relationship': rel_count > 0,
        'can_answer_impact': rel_count >= 2
    }


def format_no_relationships_response(entity_name: str, query_type: str, entity_type: Optional[str] = None) -> str:
    """
    Format response for entities with no documented relationships.
    This is a GROUNDED response - we are certain about the data gap.
    """
    type_info = f" (type: {entity_type})" if entity_type else ""
    base = f"Entity '{entity_name}'{type_info} exists in the knowledge graph."
    
    if query_type == 'impact':
        return (
            f"{base}\n\n"
            f"GROUNDED:\n"
            f"- Entity exists in the knowledge graph\n\n"
            f"GAPS:\n"
            f"- No dependency relationships documented for this entity\n"
            f"- Cannot assess blast radius or downstream impact without relationship data\n"
            f"- Impact of a failure would be limited to the entity itself based on current documentation"
        )
    elif query_type == 'relationship':
        return (
            f"{base}\n\n"
            f"GROUNDED:\n"
            f"- Entity exists in the knowledge graph\n\n"
            f"GAPS:\n"
            f"- No dependency relationships documented\n"
            f"- No ownership information documented\n"
            f"- No connection data available"
        )
    else:
        return (
            f"{base}\n\n"
            f"GROUNDED:\n"
            f"- Entity exists in the knowledge graph\n\n"
            f"GAPS:\n"
            f"- No relationship data available for this entity"
        )


def format_sparse_response(entity_name: str, entity_type: str, relationships: list, sufficiency: dict) -> str:
    """
    Format response for entities with sparse data (1-2 relationships).
    Uses simple formatting, not full LLM reasoning.
    """
    response = f"Entity '{entity_name}' (type: {entity_type}) has limited documentation.\n\n"
    response += "GROUNDED:\n"
    response += f"- Entity exists in the knowledge graph\n"
    
    if relationships:
        for rel in relationships:
            source_name = rel.get('source_name', 'Unknown')
            target_name = rel.get('target_name', 'Unknown')
            rel_type = rel.get('relationship_type', 'RELATED_TO')
            rel_id = rel.get('id', 'N/A')
            response += f"- {source_name} {rel_type} {target_name} [REL-{rel_id}]\n"
    
    response += f"\nGAPS:\n"
    response += f"- Only {sufficiency['relationship_count']} relationship(s) documented\n"
    response += f"- Additional relationships may exist but are not in the knowledge graph\n"
    
    if sufficiency['outgoing_count'] == 0:
        response += f"- No outgoing dependencies documented\n"
    if sufficiency['incoming_count'] == 0:
        response += f"- No incoming dependencies documented\n"
    
    return response


def should_gate_query(query_type: str, sufficiency: dict) -> tuple[bool, str]:
    """
    Determine if query should be gated (answered without LLM).
    
    Returns:
        (should_gate: bool, gate_reason: str)
    """
    if query_type in ['relationship', 'impact']:
        if sufficiency['relationship_count'] == 0:
            return True, 'no_relationships'
        if query_type == 'impact' and sufficiency['relationship_count'] < 2:
            return True, 'insufficient_for_impact'
    
    if sufficiency['level'] == 'sparse':
        return True, 'sparse_data'
    
    return False, ''
