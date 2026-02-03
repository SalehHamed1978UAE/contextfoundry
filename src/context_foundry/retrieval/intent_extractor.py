"""
Query Intent Extraction

Extracts structured intent from natural language queries to guide tree-based retrieval.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.context_foundry.utils.logger import logger


@dataclass
class QueryIntent:
    """
    Structured representation of what a query is asking for.

    Used by TreeBasedRetriever to determine:
    - What entity types to look for
    - What relationships to traverse
    - What properties to filter by
    - How to rank results
    """

    # What type of entity are we looking for?
    target_entity_types: List[str]

    # What relationships should we traverse?
    relationship_types: List[str]

    # What properties should entities have?
    property_filters: Dict[str, Any]

    # What's the question type?
    question_type: str  # 'who', 'what', 'when', 'how_many', 'which'

    # Semantic context for ranking
    semantic_keywords: List[str]

    # Does this require aggregation (count, sum, max)?
    requires_aggregation: bool = False

    # Original query type from classifier
    query_type: str = "UNKNOWN"


class IntentExtractor:
    """
    Extracts structured intent from natural language queries.

    Maps query patterns to entity types, relationships, and filters
    that guide graph traversal.
    """

    # Query type patterns and their corresponding intent templates
    QUERY_TYPE_PATTERNS = {
        'ROLE': {
            'patterns': [
                r'who is the',
                r'who (?:leads|manages|heads|chairs)',
                r'name of the',
                r'who (?:will be|is) (?:the )?(?:CEO|CFO|CTO|COO|President|Director|VP)',
            ],
            'entity_types': ['PERSON'],
            'relationship_types': ['LEADS', 'MANAGES', 'HAS_ROLE', 'HOLDS_POSITION', 'HAS_EXECUTIVE',
                                  'HAS_OFFICER', 'CHAIRS', 'DIRECTS', 'CEO_OF', 'PROJECT_DIRECTOR_OF'],
            'question_type': 'who'
        },

        'METRIC': {
            'patterns': [
                r'what is the (?:revenue|budget|capacity|cost|value|price|salary)',
                r'how much (?:is|does|will)',
                r'what (?:is|are) the (?:total|annual|monthly)',
            ],
            'entity_types': ['METRIC', 'FINANCIAL_DATA', 'SPECIFICATION', 'NUMBER'],
            'relationship_types': ['HAS_REVENUE', 'HAS_BUDGET', 'HAS_METRIC', 'HAS_SPEC',
                                  'HAS_CAPACITY', 'HAS_VALUE', 'HAS_COST'],
            'question_type': 'what'
        },

        'PROJECT': {
            'patterns': [
                r'when is .* launching',
                r'what is the .* (?:project|program|initiative)',
                r'when (?:is|will|did) .* (?:launch|start|complete)',
            ],
            'entity_types': ['PROJECT', 'INITIATIVE', 'PROGRAM', 'PRODUCT'],
            'relationship_types': ['HAS_PROJECT', 'MANAGES', 'WORKS_ON', 'LAUNCHES',
                                  'HAS_MILESTONE', 'STARTED_ON'],
            'question_type': 'when'
        },

        'RELATIONSHIP': {
            'patterns': [
                r'who (?:supplies|provides|manufactures)',
                r'which (?:company|organization|supplier)',
                r'what (?:company|organization) (?:supplies|provides)',
            ],
            'entity_types': ['ORGANIZATION', 'COMPANY', 'SUPPLIER'],
            'relationship_types': ['SUPPLIER_OF', 'SUPPLIES_TO', 'PROVIDES', 'MANUFACTURES',
                                  'PARTNERED_WITH', 'CUSTOMER_OF'],
            'question_type': 'who'
        },

        'AGGREGATION': {
            'patterns': [
                r'how many',
                r'total (?:value|count|number)',
                r'which has the (?:most|largest|highest|lowest|smallest)',
                r'what is the (?:total|sum|average)',
            ],
            'entity_types': ['*'],  # Any type
            'relationship_types': ['*'],  # Any relationship
            'question_type': 'how_many',
            'requires_aggregation': True
        },

        'COMPARISON': {
            'patterns': [
                r'which (?:division|department|project) has',
                r'who has the (?:highest|lowest|most|least)',
                r'compare .* (?:to|with|and)',
            ],
            'entity_types': ['*'],
            'relationship_types': ['*'],
            'question_type': 'which',
            'requires_aggregation': True
        },

        'TEMPORAL': {
            'patterns': [
                r'when (?:did|was|will)',
                r'what (?:date|time|year)',
                r'when is .* expected',
            ],
            'entity_types': ['DATE', 'MILESTONE', 'EVENT'],
            'relationship_types': ['STARTED_ON', 'ENDED_ON', 'SCHEDULED_FOR', 'EXPECTED_ON'],
            'question_type': 'when'
        },

        'SPECIFICATION': {
            'patterns': [
                r'what is the (?:energy density|capacity|range|temperature)',
                r'(?:technical|performance) (?:spec|specification)',
                r'what (?:material|technology|component)',
            ],
            'entity_types': ['SPECIFICATION', 'TECHNICAL_SPEC'],
            'relationship_types': ['HAS_SPEC', 'USES_MATERIAL', 'USES_TECHNOLOGY'],
            'question_type': 'what'
        }
    }

    # Common property extraction patterns
    PROPERTY_PATTERNS = {
        'fiscal_year': r'FY\s?(\d{4})|fiscal year\s?(\d{4})',
        'year': r'\b(20\d{2})\b',
        'month': r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b',
        'role': r'\b(CEO|CFO|CTO|COO|President|Director|VP|Vice President|Chief|Manager)\b',
        'metric_type': r'\b(revenue|budget|capacity|cost|value|price)\b',
    }

    # Question word detection
    QUESTION_WORDS = {
        'who': r'^who\b',
        'what': r'^what\b',
        'when': r'^when\b',
        'where': r'^where\b',
        'how_many': r'^how many\b',
        'how_much': r'^how much\b',
        'which': r'^which\b',
        'why': r'^why\b',
    }

    def extract(self, query: str, query_type: str = "UNKNOWN") -> QueryIntent:
        """
        Extract structured intent from a query.

        Args:
            query: Natural language question
            query_type: Pre-classified query type (ROLE, METRIC, etc.) or UNKNOWN

        Returns:
            QueryIntent with entity types, relationships, and filters
        """
        query_lower = query.lower()

        logger.info(f"[INTENT] Extracting intent for: {query}")
        logger.info(f"[INTENT] Classified query type: {query_type}")

        # If query_type is not UNKNOWN, use it; otherwise detect
        if query_type == "UNKNOWN":
            query_type = self._detect_query_type(query_lower)
            logger.info(f"[INTENT] Detected query type: {query_type}")

        # Get base patterns for this query type
        patterns = self.QUERY_TYPE_PATTERNS.get(query_type, {})

        # Extract components
        target_entity_types = patterns.get('entity_types', ['*'])
        relationship_types = patterns.get('relationship_types', ['*'])
        requires_aggregation = patterns.get('requires_aggregation', False)
        question_type = patterns.get('question_type', self._extract_question_type(query_lower))

        # Extract property filters
        property_filters = self._extract_property_filters(query)

        # Extract semantic keywords
        semantic_keywords = self._extract_keywords(query)

        intent = QueryIntent(
            target_entity_types=target_entity_types,
            relationship_types=relationship_types,
            property_filters=property_filters,
            question_type=question_type,
            semantic_keywords=semantic_keywords,
            requires_aggregation=requires_aggregation,
            query_type=query_type
        )

        logger.info(f"[INTENT] Extracted intent: entity_types={target_entity_types}, "
                   f"rel_types={relationship_types[:3]}..., filters={property_filters}")

        return intent

    def _detect_query_type(self, query_lower: str) -> str:
        """
        Detect query type by matching against patterns.

        Returns query type string or 'UNKNOWN'.
        """
        for query_type, config in self.QUERY_TYPE_PATTERNS.items():
            patterns = config.get('patterns', [])
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return query_type

        return 'UNKNOWN'

    def _extract_question_type(self, query_lower: str) -> str:
        """Extract the question word (who, what, when, etc.)."""
        for q_type, pattern in self.QUESTION_WORDS.items():
            if re.search(pattern, query_lower):
                return q_type

        return 'what'  # Default

    def _extract_property_filters(self, query: str) -> Dict[str, Any]:
        """
        Extract property filters from query.

        Examples:
        - "FY2026 revenue" → {'fiscal_year': '2026'}
        - "CFO of Nexus" → {'role': 'CFO'}
        """
        filters = {}

        for prop_name, pattern in self.PROPERTY_PATTERNS.items():
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # Get first non-None group
                value = next((g for g in match.groups() if g), None)
                if value:
                    filters[prop_name] = value

        return filters

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract semantic keywords for ranking.

        Removes stopwords and extracts meaningful terms.
        """
        stopwords = {
            'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'should', 'could', 'can', 'of', 'in', 'on', 'at', 'to', 'for',
            'with', 'by', 'from', 'a', 'an', 'and', 'or', 'but', 'what',
            'who', 'when', 'where', 'how', 'which', 'that', 'this', 'these',
            'those'
        }

        # Tokenize and clean
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 2]

        return keywords
