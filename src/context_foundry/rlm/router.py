"""
Query Complexity Router - Routes queries to appropriate processing tier.

Analyzes query complexity signals to decide between:
- Tier 1: Simple single-hop queries (existing RetrievalAgent pipeline)
- Tier 2: Complex multi-hop queries requiring RLM iterative reasoning
"""

import os
import re
from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class QueryTier(Enum):
    """Query processing tier."""
    TIER1_SIMPLE = "tier1"
    TIER2_RLM = "tier2"


@dataclass
class ComplexitySignals:
    """Signals used to assess query complexity."""
    token_count: int
    conjunction_count: int
    comparison_keywords: int
    temporal_keywords: int
    aggregation_keywords: int
    causal_keywords: int
    multi_entity_references: int
    nested_questions: int
    
    @property
    def complexity_score(self) -> float:
        """Calculate weighted complexity score (0.0 - 1.0)."""
        weights = {
            'token_count': 0.05 if self.token_count > 20 else 0,
            'conjunction': 0.15 * min(self.conjunction_count / 3, 1.0),
            'comparison': 0.20 * min(self.comparison_keywords / 2, 1.0),
            'temporal': 0.10 * min(self.temporal_keywords / 2, 1.0),
            'aggregation': 0.15 * min(self.aggregation_keywords / 2, 1.0),
            'causal': 0.20 * min(self.causal_keywords / 2, 1.0),
            'multi_entity': 0.10 * min(self.multi_entity_references / 2, 1.0),
            'nested': 0.05 * min(self.nested_questions, 1.0),
        }
        return min(sum(weights.values()), 1.0)


CONJUNCTION_PATTERNS = [
    r'\band\b', r'\bor\b', r'\bbut\b', r'\balso\b', r'\bas well as\b',
    r'\bin addition\b', r'\bmoreover\b', r'\bfurthermore\b'
]

COMPARISON_PATTERNS = [
    r'\bcompare\b', r'\bdifference\b', r'\bsimilar\b', r'\bversus\b', r'\bvs\.?\b',
    r'\bcontrast\b', r'\bunlike\b', r'\bmore than\b', r'\bless than\b',
    r'\bbetter\b', r'\bworse\b', r'\bhigher\b', r'\blower\b'
]

TEMPORAL_PATTERNS = [
    r'\bbefore\b', r'\bafter\b', r'\bduring\b', r'\bwhile\b', r'\bwhen\b',
    r'\bhistory\b', r'\bover time\b', r'\bchanged\b', r'\bevolved\b',
    r'\bpreviously\b', r'\brecently\b', r'\btrend\b'
]

AGGREGATION_PATTERNS = [
    r'\bhow many\b', r'\btotal\b', r'\bcount\b', r'\blist all\b', r'\bsummarize\b',
    r'\boverview\b', r'\ball\b', r'\bevery\b', r'\beach\b', r'\baverage\b',
    r'\bmost\b', r'\bleast\b', r'\btop\b', r'\bbottom\b'
]

CAUSAL_PATTERNS = [
    r'\bwhy\b', r'\bhow does\b', r'\bcause\b', r'\beffect\b', r'\bresult\b',
    r'\blead to\b', r'\bimpact\b', r'\binfluence\b', r'\bconsequence\b',
    r'\bbecause\b', r'\bdue to\b', r'\btherefore\b'
]

MULTI_HOP_INDICATORS = [
    r'\brelated to\b', r'\bconnected\b', r'\blink\b', r'\bassociated\b',
    r'\bdepends on\b', r'\baffects\b', r'\binvolves\b', r'\bpath\b',
    r'\brelationship between\b', r'\bhow.+relates?\b', r'\bdependencies\b',
    r'\bbetween\b.+\band\b', r'\bimpacted?\b', r'\bdownstream\b', r'\bupstream\b',
    r'\broot cause\b', r'\baffected by\b', r'\bincidents?\b'
]

NESTED_PATTERNS = [
    r'\?.*\?', r'\bwhich.+that\b', r'\bwhat.+where\b', r'\bwho.+how\b'
]


class QueryComplexityRouter:
    """
    Routes queries to appropriate processing tier based on complexity analysis.
    
    Tier 1 (Simple): Direct retrieval queries
    - "What is the status of Service X?"
    - "Who is the owner of Project Y?"
    - "When was Document Z uploaded?"
    
    Tier 2 (RLM): Complex multi-hop queries
    - "Compare the dependencies of Service A and Service B"
    - "What services were affected by the last 3 incidents?"
    - "How does change in System X impact downstream services?"
    """
    
    FORCE_RLM_PATTERNS = [
        r'affected by.*triggered',
        r'triggered by.*affected',
        r'depend(?:s|ing)? on.*and',
        r'trace.*from.*to',
        r'chain.*from.*to',
        r'what.*incidents.*services',
        r'which.*services.*incidents',
        r'compare.*across',
        r'all.*that.*have',
        r'services.*connected.*to',
        r'related.*to.*incident',
        r'impact.*of.*on',
        # EXPERIMENT 1: Force RLM for Q58/Q59 interpretation tests
        r'customer retention rate',
        r'target.*new customers',
    ]
    
    def __init__(self, complexity_threshold: float = 0.10):
        """
        Initialize router.
        
        Args:
            complexity_threshold: Score threshold for RLM routing (default 0.10)
        """
        self.complexity_threshold = complexity_threshold
    
    def analyze_complexity(self, query: str) -> ComplexitySignals:
        """
        Analyze query complexity signals.
        
        Args:
            query: The query string
        
        Returns:
            ComplexitySignals with all detected signals
        """
        query_lower = query.lower()
        
        token_count = len(query.split())
        
        conjunction_count = sum(
            len(re.findall(pattern, query_lower, re.IGNORECASE))
            for pattern in CONJUNCTION_PATTERNS
        )
        
        comparison_keywords = sum(
            len(re.findall(pattern, query_lower, re.IGNORECASE))
            for pattern in COMPARISON_PATTERNS
        )
        
        temporal_keywords = sum(
            len(re.findall(pattern, query_lower, re.IGNORECASE))
            for pattern in TEMPORAL_PATTERNS
        )
        
        aggregation_keywords = sum(
            len(re.findall(pattern, query_lower, re.IGNORECASE))
            for pattern in AGGREGATION_PATTERNS
        )
        
        causal_keywords = sum(
            len(re.findall(pattern, query_lower, re.IGNORECASE))
            for pattern in CAUSAL_PATTERNS
        )
        
        multi_entity_references = sum(
            len(re.findall(pattern, query_lower, re.IGNORECASE))
            for pattern in MULTI_HOP_INDICATORS
        )
        
        nested_questions = sum(
            len(re.findall(pattern, query_lower, re.IGNORECASE))
            for pattern in NESTED_PATTERNS
        )
        
        return ComplexitySignals(
            token_count=token_count,
            conjunction_count=conjunction_count,
            comparison_keywords=comparison_keywords,
            temporal_keywords=temporal_keywords,
            aggregation_keywords=aggregation_keywords,
            causal_keywords=causal_keywords,
            multi_entity_references=multi_entity_references,
            nested_questions=nested_questions
        )
    
    def route(self, query: str) -> Tuple[QueryTier, ComplexitySignals]:
        """
        Route query to appropriate tier.
        
        Checks forced RLM patterns first, then falls back to complexity scoring.
        
        Args:
            query: The query string
        
        Returns:
            Tuple of (tier, complexity_signals)
        """
        signals = self.analyze_complexity(query)
        query_lower = query.lower()
        
        for pattern in self.FORCE_RLM_PATTERNS:
            if re.search(pattern, query_lower):
                return QueryTier.TIER2_RLM, signals
        
        if signals.complexity_score >= self.complexity_threshold:
            return QueryTier.TIER2_RLM, signals
        else:
            return QueryTier.TIER1_SIMPLE, signals
    
    def should_use_rlm(self, query: str) -> bool:
        """
        Quick check if query should use RLM.
        
        Args:
            query: The query string
        
        Returns:
            True if RLM should be used
        """
        tier, _ = self.route(query)
        return tier == QueryTier.TIER2_RLM
    
    def get_routing_explanation(self, query: str) -> Dict[str, Any]:
        """
        Get detailed explanation of routing decision.
        
        Args:
            query: The query string
        
        Returns:
            Dict with tier, score, signals, and explanation
        """
        signals = self.analyze_complexity(query)
        tier = QueryTier.TIER2_RLM if signals.complexity_score >= self.complexity_threshold else QueryTier.TIER1_SIMPLE
        
        reasons = []
        if signals.comparison_keywords > 0:
            reasons.append(f"Comparison query ({signals.comparison_keywords} keywords)")
        if signals.causal_keywords > 0:
            reasons.append(f"Causal reasoning ({signals.causal_keywords} keywords)")
        if signals.aggregation_keywords > 0:
            reasons.append(f"Aggregation needed ({signals.aggregation_keywords} keywords)")
        if signals.multi_entity_references > 0:
            reasons.append(f"Multi-entity references ({signals.multi_entity_references} found)")
        if signals.temporal_keywords > 0:
            reasons.append(f"Temporal analysis ({signals.temporal_keywords} keywords)")
        if signals.conjunction_count >= 2:
            reasons.append(f"Multiple clauses ({signals.conjunction_count} conjunctions)")
        if signals.token_count > 25:
            reasons.append(f"Long query ({signals.token_count} tokens)")
        
        if not reasons and tier == QueryTier.TIER1_SIMPLE:
            reasons.append("Simple direct query - single entity lookup")
        
        return {
            "query": query,
            "tier": tier.value,
            "tier_name": "RLM (Complex)" if tier == QueryTier.TIER2_RLM else "Simple (Tier 1)",
            "complexity_score": round(signals.complexity_score, 3),
            "threshold": self.complexity_threshold,
            "signals": {
                "tokens": signals.token_count,
                "conjunctions": signals.conjunction_count,
                "comparisons": signals.comparison_keywords,
                "temporal": signals.temporal_keywords,
                "aggregations": signals.aggregation_keywords,
                "causal": signals.causal_keywords,
                "multi_entity": signals.multi_entity_references,
                "nested": signals.nested_questions
            },
            "reasons": reasons
        }


router = QueryComplexityRouter()


def route_query(query: str) -> QueryTier:
    """Convenience function to route a query."""
    tier, _ = router.route(query)
    return tier


def should_use_rlm(query: str) -> bool:
    """Convenience function to check if RLM should be used."""
    return router.should_use_rlm(query)


EXAMPLE_QUERIES = {
    "tier1": [
        "What is the status of the Payment Service?",
        "Who owns the Customer Database?",
        "When was the API Gateway last updated?",
        "What type of entity is John Smith?",
        "Show me the properties of Order Processing.",
    ],
    "tier2": [
        "Compare the dependencies between Payment Service and Order Service and explain the differences",
        "How does a change in the Authentication Service impact downstream services and what is the root cause path?",
        "List all services that depend on the Customer Database and explain their relationships",
        "What is the root cause path from the Network Outage to the checkout failures and which services were affected?",
        "Summarize the relationships between all teams involved in the incident and how they are connected",
        "Why did the API Gateway failure cause downstream services to fail and what is the impact path?",
    ]
}
