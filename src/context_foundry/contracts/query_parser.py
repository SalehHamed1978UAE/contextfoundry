"""
QueryParser Contract - Defines the interface for query intent classification.

The QueryParser is responsible for:
1. Classifying query type (impact, dependency, ownership, entity, rule, analysis, general)
2. Extracting target entity names from queries
3. Identifying query modifiers (temporal, property filters, etc.)

KNOWN BUG FIX: The previous implementation incorrectly parsed "What was affected by X" 
as having entity name "affected by X". The correct parse should be:
- query_type: IMPACT
- target_entity: "X"
- intent: Find entities affected by X (downstream impact)
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class QueryType(str, Enum):
    """Classification of query intent."""
    IMPACT = "impact"
    DEPENDENCY = "dependency"
    OWNERSHIP = "ownership"
    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    RULE = "rule"
    ANALYSIS = "analysis"
    EXISTENCE = "existence"
    LISTING = "listing"
    GENERAL = "general"


@dataclass
class QueryIntent:
    """
    Structured representation of parsed query intent.
    
    This is the output contract for the QueryParser. All parsers must
    produce a QueryIntent that satisfies these invariants:
    
    Invariants:
    1. query_type is never None
    2. If query_type is IMPACT, target_entity should be the entity being impacted
    3. Entity names should never include intent keywords (affected, depends, etc.)
    4. raw_query preserves the original query text
    """
    query_type: QueryType
    target_entity: Optional[str] = None
    secondary_entities: List[str] = field(default_factory=list)
    relationship_type: Optional[str] = None
    entity_type_filter: Optional[str] = None
    temporal_modifier: Optional[str] = None
    property_filters: Dict[str, Any] = field(default_factory=dict)
    traversal_depth: int = 3
    raw_query: str = ""
    confidence: float = 1.0
    
    def __post_init__(self):
        if self.query_type is None:
            raise ValueError("query_type cannot be None")
        if self.target_entity:
            self._validate_entity_name(self.target_entity)
    
    def _validate_entity_name(self, name: str):
        """Validate that entity name doesn't contain intent keywords."""
        intent_keywords = [
            'affected', 'affects', 'impacted', 'impacts',
            'depends on', 'depended on', 'dependency',
            'owned by', 'manages', 'reports to',
            'what was', 'what is', 'what are', 'which',
            'who is', 'who are', 'how does', 'how do',
        ]
        name_lower = name.lower()
        for kw in intent_keywords:
            if name_lower.startswith(kw):
                raise ValueError(
                    f"Entity name '{name}' starts with intent keyword '{kw}'. "
                    f"This suggests a parsing error."
                )


class QueryParserContract(ABC):
    """
    Abstract contract for query parsing.
    
    Implementations must correctly classify query intent and extract
    entity names without conflating intent keywords with entity names.
    """
    
    @abstractmethod
    def parse(self, query_text: str) -> QueryIntent:
        """
        Parse a natural language query into structured QueryIntent.
        
        Args:
            query_text: The raw query string from the user
            
        Returns:
            QueryIntent with classified type and extracted entities
            
        Contract:
            - Must never return None
            - Must correctly classify impact queries
            - Must extract entity names without intent keywords
            - Must preserve raw_query in the result
        """
        pass
    
    @abstractmethod
    def is_impact_query(self, query_text: str) -> bool:
        """
        Determine if query is asking about blast radius/impact.
        
        Impact queries ask "what breaks if X fails?" and require
        traversing INCOMING DEPENDS_ON relationships.
        
        Args:
            query_text: The raw query string
            
        Returns:
            True if this is an impact/blast radius query
        """
        pass
    
    @abstractmethod
    def extract_target_entity(self, query_text: str) -> Optional[str]:
        """
        Extract the primary target entity from a query.
        
        For "What was affected by Payment Service failure?":
        - Should return "Payment Service", NOT "affected by Payment Service"
        
        Args:
            query_text: The raw query string
            
        Returns:
            The entity name or None if no clear target
        """
        pass


class PatternBasedQueryParser(QueryParserContract):
    """
    Production implementation of QueryParser using regex patterns.
    
    This parser correctly handles the "What was affected by X" pattern
    by recognizing impact keywords before attempting entity extraction.
    """
    
    IMPACT_PATTERNS = [
        r'\bblast radius\b',
        r'\bimpact(?:ed|s)?\b',
        r'\baffect(?:ed|s)?\b',
        r'\bgoes down\b',
        r'\bbecomes unavailable\b',
        r'\bfail(?:s|ure|ed)?\b',
        r'\bbreak(?:s|ing)?\b',
        r'\bcrash(?:es|ed)?\b',
        r'\bis down\b',
        r'\bis corrupted\b',
        r'\bis unavailable\b',
        r'\bwhat services\b',
        r'\bwhich services\b',
        r'\bwhat depends\b',
        r'\bwhat breaks\b',
        r'\bdownstream\b',
        r'\bcascade\b',
        r'\bripple effect\b',
    ]
    
    DEPENDENCY_PATTERNS = [
        r'\bdepends? on\b',
        r'\bdependencies of\b',
        r'\bwhat does .+ depend on\b',
        r'\bupstream\b',
        r'\brequires?\b',
        r'\bneeds?\b',
        r'\brel(?:y|ies) on\b',
    ]
    
    OWNERSHIP_PATTERNS = [
        r'\bowned by\b',
        r'\bowner of\b',
        r'\bwho owns\b',
        r'\bwho manages\b',
        r'\bwho is responsible\b',
        r'\breports to\b',
        r'\bmanages\b',
    ]
    
    RULE_PATTERNS = [
        r'\bwhat is the process\b',
        r'\bwhat\'s the process\b',
        r'\bescalation\b',
        r'\bpolicy\b',
        r'\bprocedure\b',
        r'\brunbook\b',
        r'\bplaybook\b',
        r'\bsev[12]\b',
        r'\bseverity [12]\b',
        r'\bincident response\b',
    ]
    
    ANALYSIS_PATTERNS = [
        r'\bwhat patterns\b',
        r'\bany patterns\b',
        r'\bany trends\b',
        r'\b(common|frequent|recurring) (issues?|problems?|causes?)\b',
        r'\bmost (common|frequent)\b',
        r'\bhow many\b',
        r'\bstatistics\b',
        r'\bsummary of\b',
    ]
    
    EXISTENCE_PATTERNS = [
        r'\bexist\b',
        r'\bis there\b',
        r'\bdo we have\b',
        r'\bare there any\b',
    ]
    
    LISTING_PATTERNS = [
        r'\blist all\b',
        r'\bshow all\b',
        r'\bdisplay all\b',
        r'\bget all\b',
        r'\bfind all\b',
    ]
    
    ENTITY_EXTRACTION_PATTERNS = [
        (r'(?:what|which|who) (?:was |were |is |are )?(?:affected|impacted|broken) (?:by|when|if) (.+?)(?:\s+(?:fails?|breaks?|goes down|is down|crashes?))?$', 1),
        (r'(?:blast radius|impact) (?:of|for) (.+?)(?:\s+(?:failure|outage))?$', 1),
        (r'(?:if|when) (.+?) (?:fails?|breaks?|goes down|is down|crashes?)', 1),
        (r'(?:what|which) depends on (.+?)$', 1),
        (r'(?:dependencies|dependents) of (.+?)$', 1),
        (r'(?:who|what) owns (.+?)$', 1),
        (r'(?:owner|owners) of (.+?)$', 1),
        (r'(?:tell me about|describe|explain|what is|what\'s) (.+?)$', 1),
    ]
    
    ENTITY_SUFFIXES = r'(?:Service|Database|Team|System|Gateway|API|Server|Cluster|Queue|Cache)'
    
    def parse(self, query_text: str) -> QueryIntent:
        """Parse query into structured intent."""
        query_type = self._classify_query_type(query_text)
        target_entity = self.extract_target_entity(query_text)
        
        return QueryIntent(
            query_type=query_type,
            target_entity=target_entity,
            raw_query=query_text,
        )
    
    def _classify_query_type(self, query_text: str) -> QueryType:
        """Classify the query type based on patterns.
        
        Priority order matters:
        1. ANALYSIS first (most specific - 'how many', 'patterns', etc.)
        2. DEPENDENCY second (specific keywords like 'rely on', 'depends on')
        3. IMPACT third (more generic like 'what services', 'affected')
        4. OWNERSHIP, RULE, etc. follow
        """
        query_lower = query_text.lower()
        
        # Check ANALYSIS first - most specific (how many, patterns, etc.)
        if self._matches_patterns(query_lower, self.ANALYSIS_PATTERNS):
            return QueryType.ANALYSIS
        # Check DEPENDENCY second - specific keywords
        if self._matches_patterns(query_lower, self.DEPENDENCY_PATTERNS):
            return QueryType.DEPENDENCY
        if self._matches_patterns(query_lower, self.IMPACT_PATTERNS):
            return QueryType.IMPACT
        if self._matches_patterns(query_lower, self.OWNERSHIP_PATTERNS):
            return QueryType.OWNERSHIP
        if self._matches_patterns(query_lower, self.RULE_PATTERNS):
            return QueryType.RULE
        if self._matches_patterns(query_lower, self.EXISTENCE_PATTERNS):
            return QueryType.EXISTENCE
        if self._matches_patterns(query_lower, self.LISTING_PATTERNS):
            return QueryType.LISTING
        
        return QueryType.GENERAL
    
    def _matches_patterns(self, text: str, patterns: List[str]) -> bool:
        """Check if text matches any of the patterns."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def is_impact_query(self, query_text: str) -> bool:
        """Check if this is an impact/blast radius query."""
        return self._matches_patterns(query_text.lower(), self.IMPACT_PATTERNS)
    
    def extract_target_entity(self, query_text: str) -> Optional[str]:
        """
        Extract the target entity from the query.
        
        This method correctly handles "What was affected by X" by:
        1. First checking for impact query patterns
        2. Using capture groups to extract entity AFTER intent keywords
        3. Cleaning the extracted entity name
        """
        query_clean = query_text.strip()
        
        for pattern, group_idx in self.ENTITY_EXTRACTION_PATTERNS:
            match = re.search(pattern, query_clean, re.IGNORECASE)
            if match:
                entity = match.group(group_idx).strip()
                entity = self._clean_entity_name(entity)
                if entity:
                    return entity
        
        entity = self._extract_by_suffix(query_clean)
        if entity:
            return entity
        
        return None
    
    def _clean_entity_name(self, name: str) -> Optional[str]:
        """Clean extracted entity name by removing trailing noise."""
        trailing_noise = [
            r'\s+(fails?|failure|breaks?|crashes?|goes down|is down|outage).*$',
            r'\s+(if|when|then).*$',
            r'\s*\?+$',
            r'\s*[.,;:]$',
        ]
        
        cleaned = name.strip()
        for pattern in trailing_noise:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        leading_noise = [
            r'^(the|a|an)\s+',
        ]
        for pattern in leading_noise:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        cleaned = cleaned.strip()
        
        if len(cleaned) < 2:
            return None
        if cleaned.lower() in ['it', 'this', 'that', 'what', 'which', 'who', 'how']:
            return None
        
        return cleaned.title() if cleaned else None
    
    def _extract_by_suffix(self, query_text: str) -> Optional[str]:
        """Extract entity by looking for common suffixes like 'Service', 'Database'."""
        pattern = rf'\b([A-Za-z][a-zA-Z0-9]*(?:\s+[A-Za-z][a-zA-Z0-9]*)*\s+{self.ENTITY_SUFFIXES})\b'
        matches = re.findall(pattern, query_text, re.IGNORECASE)
        
        false_positives = {'what', 'who', 'where', 'when', 'how', 'which', 'the', 'are', 'does', 'can', 'is', 'of', 'a', 'an'}
        filtered = [m for m in matches if m.split()[0].lower() not in false_positives]
        
        if filtered:
            return sorted(filtered, key=len, reverse=True)[0].title()
        
        return None
