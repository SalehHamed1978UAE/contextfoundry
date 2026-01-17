"""
Query Intent Classifier - Understand query type before retrieval.

Classifies queries into intent categories to enable proper entity type routing.
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

from src.context_foundry.utils.logger import logger


class QueryIntent(Enum):
    PERSON = "person"
    METRIC = "metric"
    POLICY = "policy"
    TEMPORAL = "temporal"
    RELATIONSHIP = "relationship"
    DEFINITION = "definition"
    LIST = "list"
    UNKNOWN = "unknown"


INTENT_PATTERNS: Dict[QueryIntent, List[str]] = {
    QueryIntent.PERSON: [
        r'^who\s+is\s+(?:the\s+)?',
        r'^who\s+(?:are|were)\s+',
        r'^who\s+',
        r'(?:ceo|cto|cfo|cro|coo|cio|chro|cmo)\b',
        r'\b(?:vp|vice\s+president|director|manager|head\s+of)\b',
        r'reports?\s+to',
        r'board\s+members?',
        r'(?:founder|co-founder|executive)',
    ],
    QueryIntent.METRIC: [
        r'(?:revenue|income|profit|loss|margin|growth|percentage|rate|ratio|budget|cost|salary|earnings)',
        r'\$[\d,]+',
        r'\d+(?:\.\d+)?\s*%',
        r'(?:how\s+many|how\s+much|what\s+percentage|what\s+was\s+the)',
        r'(?:cagr|yoy|ltv|cac|nrr|arr|mrr|roi|rto|rpo)\b',
        r'(?:quota|commission|bonus|stipend|reimbursement)',
        r'(?:employees?|customers?|headcount)',
        r'(?:funding|valuation|investment)',
        r'(?:market\s+share|nps|net\s+promoter)',
    ],
    QueryIntent.POLICY: [
        r'^(?:is|are|can|do|does)\s+.*(?:required|allowed|permitted|mandatory|necessary)',
        r'(?:policy|policies|requirement|compliance|procedure|rule|guideline)',
        r'(?:mfa|multi-factor|authentication|security|access|permission|authorization)',
        r'(?:gdpr|hipaa|sox|pci|iso\s*27001|soc\s*2)',
        r'(?:certified|certification|compliant|compliance)',
        r'(?:encryption|tls|ssl|vpn)',
        r'(?:backup|disaster\s+recovery|rto|rpo)',
        r'(?:remote\s+work|work\s+from|wi-fi|wifi)',
    ],
    QueryIntent.TEMPORAL: [
        r'^when\s+',
        r'(?:founded|established|started|launched|released)',
        r'(?:deadline|timeline|schedule|date)',
        r'(?:expire|expiration|contract\s+term)',
        r'(?:beta|ga|general\s+availability)\s+(?:launch|release)',
    ],
    QueryIntent.DEFINITION: [
        r'^what\s+is\s+(?:the\s+)?(?:name|flagship|product)',
        r'^what\s+(?:are|is)\s+.*(?:called|named)',
        r'^describe\s+',
        r'^explain\s+',
        r'(?:what\s+industry|what\s+sector)',
        r'headquarters|location|located',
    ],
    QueryIntent.LIST: [
        r'^list\s+',
        r'^enumerate\s+',
        r'(?:what\s+are\s+the\s+(?:three|four|five|\d+))',
        r'(?:how\s+many\s+(?:core\s+values|products|services))',
    ],
    QueryIntent.RELATIONSHIP: [
        r'(?:reports?\s+to|managed\s+by|works?\s+(?:for|at|with))',
        r'(?:led\s+by|headed\s+by)',
        r'(?:partner|investor|customer|client)',
    ],
}

FISCAL_YEAR_PATTERN = re.compile(r'(?:fy|fiscal\s+year)\s*(\d{4}|\d{2})', re.IGNORECASE)
YEAR_PATTERN = re.compile(r'\b(20\d{2})\b')
QUARTER_PATTERN = re.compile(r'\bq([1-4])\s*(\d{4}|\d{2})?\b', re.IGNORECASE)
ORG_PATTERN = re.compile(r'(?:of|at|for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)', re.IGNORECASE)


@dataclass
class ClassifiedQuery:
    original_query: str
    primary_intent: QueryIntent
    secondary_intent: Optional[QueryIntent] = None
    confidence: float = 0.0
    extracted_constraints: Dict[str, Any] = field(default_factory=dict)
    matched_patterns: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_query": self.original_query,
            "primary_intent": self.primary_intent.value,
            "secondary_intent": self.secondary_intent.value if self.secondary_intent else None,
            "confidence": self.confidence,
            "extracted_constraints": self.extracted_constraints,
            "matched_patterns": self.matched_patterns,
        }


class QueryIntentClassifier:
    """Classifies queries into intent categories."""
    
    def __init__(self):
        self.compiled_patterns: Dict[QueryIntent, List[re.Pattern]] = {}
        for intent, patterns in INTENT_PATTERNS.items():
            self.compiled_patterns[intent] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def classify(self, query: str) -> ClassifiedQuery:
        """
        Classify a query into an intent category.
        
        Returns ClassifiedQuery with intent, confidence, and extracted constraints.
        """
        query_lower = query.lower().strip()
        
        intent_scores: Dict[QueryIntent, float] = {}
        matched_patterns: Dict[QueryIntent, List[str]] = {}
        
        for intent, patterns in self.compiled_patterns.items():
            score = 0.0
            matches = []
            for pattern in patterns:
                if pattern.search(query_lower):
                    score += 1.0
                    matches.append(pattern.pattern)
            if score > 0:
                intent_scores[intent] = score
                matched_patterns[intent] = matches
        
        if not intent_scores:
            return ClassifiedQuery(
                original_query=query,
                primary_intent=QueryIntent.UNKNOWN,
                confidence=0.0,
                extracted_constraints=self._extract_constraints(query),
            )
        
        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        primary_intent = sorted_intents[0][0]
        primary_score = sorted_intents[0][1]
        
        secondary_intent = None
        if len(sorted_intents) > 1:
            secondary_intent = sorted_intents[1][0]
        
        total_patterns = sum(len(p) for p in INTENT_PATTERNS.values())
        confidence = min(1.0, primary_score / 3.0)
        
        constraints = self._extract_constraints(query)
        
        result = ClassifiedQuery(
            original_query=query,
            primary_intent=primary_intent,
            secondary_intent=secondary_intent,
            confidence=confidence,
            extracted_constraints=constraints,
            matched_patterns=matched_patterns.get(primary_intent, []),
        )
        
        logger.info(f"[INTENT_CLASSIFIER] Query: '{query[:50]}...' → {primary_intent.value} (confidence: {confidence:.2f})")
        if constraints:
            logger.info(f"[INTENT_CLASSIFIER] Constraints: {constraints}")
        
        return result
    
    def _extract_constraints(self, query: str) -> Dict[str, Any]:
        """Extract temporal and organizational constraints from query."""
        constraints = {}
        
        fy_match = FISCAL_YEAR_PATTERN.search(query)
        if fy_match:
            year = fy_match.group(1)
            if len(year) == 2:
                year = f"20{year}"
            constraints["fiscal_year"] = f"FY{year}"
        
        if "fiscal_year" not in constraints:
            year_match = YEAR_PATTERN.search(query)
            if year_match:
                constraints["year"] = year_match.group(1)
        
        quarter_match = QUARTER_PATTERN.search(query)
        if quarter_match:
            q = quarter_match.group(1)
            y = quarter_match.group(2)
            if y:
                if len(y) == 2:
                    y = f"20{y}"
                constraints["quarter"] = f"Q{q} {y}"
            else:
                constraints["quarter"] = f"Q{q}"
        
        org_match = ORG_PATTERN.search(query)
        if org_match:
            org = org_match.group(1)
            if org.lower() not in ['the', 'a', 'an', 'this', 'that']:
                constraints["organization"] = org
        
        return constraints


_classifier_instance: Optional[QueryIntentClassifier] = None


def get_intent_classifier() -> QueryIntentClassifier:
    """Get singleton classifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = QueryIntentClassifier()
    return _classifier_instance


def classify_query(query: str) -> ClassifiedQuery:
    """Convenience function to classify a query."""
    return get_intent_classifier().classify(query)
