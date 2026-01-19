"""
Symbolic Override Engine - Enforces rules that override semantic retrieval.

This is the implementation of "Symbolic > Semantic > Episodic" precedence.
When a rule applies, its answer takes precedence over whatever semantic
memory would have returned.

Part of the tri-memory thesis validation.
"""

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy.orm import Session

from ..models.schema import Rule, RuleType, Entity

logger = logging.getLogger(__name__)


class OverrideType(Enum):
    """Types of symbolic override."""
    NONE = "none"              # No override, use semantic
    CONSTRAINT = "constraint"  # Apply constraint to answer
    REPLACE = "replace"        # Replace answer entirely
    PROHIBIT = "prohibit"      # Refuse to answer
    AUGMENT = "augment"        # Add caveat to answer


@dataclass
class RuleMatch:
    """Result of matching a rule to a query."""
    rule_id: str
    rule_name: str
    override_type: OverrideType
    confidence: float
    match_reason: str
    override_answer: Optional[str] = None
    constraint_text: Optional[str] = None


@dataclass
class SymbolicOverrideResult:
    """Result of symbolic override evaluation."""
    should_override: bool
    override_type: OverrideType
    override_answer: Optional[str]
    matched_rules: List[RuleMatch]
    explanation: str


class SymbolicOverrideEngine:
    """
    Evaluates whether symbolic rules should override semantic retrieval.

    This is the key implementation of the tri-memory precedence:
    Symbolic > Semantic > Episodic

    Usage:
        engine = SymbolicOverrideEngine(session)
        result = engine.evaluate(query, semantic_answer, context)

        if result.should_override:
            final_answer = result.override_answer
        else:
            final_answer = semantic_answer
    """

    # Patterns that indicate specific query types
    QUERY_PATTERNS = {
        'compensation': [
            r'\bsalary\b', r'\bcompensation\b', r'\bpay\b', r'\bwage\b',
            r'\bbonus\b', r'\bstock\b', r'\bequity\b'
        ],
        'pto': [
            r'\bpto\b', r'\bvacation\b', r'\btime\s*off\b', r'\bleave\b',
            r'\bholiday\b'
        ],
        'confidential': [
            r'\bconfidential\b', r'\bsecret\b', r'\bprivate\b',
            r'\brestricted\b', r'\bclassified\b'
        ],
        'policy': [
            r'\bpolicy\b', r'\brule\b', r'\bregulation\b', r'\bcompliance\b',
            r'\brequirement\b'
        ],
        'executive': [
            r'\bceo\b', r'\bcfo\b', r'\bcoo\b', r'\bcto\b', r'\bexecutive\b',
            r'\bc-level\b', r'\bchief\b', r'\bvp\b', r'\bvice\s*president\b'
        ],
    }

    def __init__(self, session: Session, tenant_id: str = None):
        self.session = session
        self.tenant_id = tenant_id

    def evaluate(
        self,
        query: str,
        semantic_answer: str,
        context: Dict[str, Any]
    ) -> SymbolicOverrideResult:
        """
        Evaluate whether symbolic rules should override the semantic answer.

        Args:
            query: The user's query
            semantic_answer: The answer from semantic memory
            context: Additional context (entities found, query type, etc.)

        Returns:
            SymbolicOverrideResult with override decision and explanation
        """
        # 1. Classify the query
        query_categories = self._classify_query(query)

        # 2. Find applicable rules
        applicable_rules = self._find_applicable_rules(query_categories, context)

        if not applicable_rules:
            return SymbolicOverrideResult(
                should_override=False,
                override_type=OverrideType.NONE,
                override_answer=None,
                matched_rules=[],
                explanation="No symbolic rules apply to this query"
            )

        # 3. Evaluate each rule
        rule_matches = []
        for rule in applicable_rules:
            match = self._evaluate_rule(rule, query, semantic_answer, context)
            if match:
                rule_matches.append(match)

        if not rule_matches:
            return SymbolicOverrideResult(
                should_override=False,
                override_type=OverrideType.NONE,
                override_answer=None,
                matched_rules=[],
                explanation="Rules found but none triggered"
            )

        # 4. Determine override action (highest priority rule wins)
        rule_matches.sort(key=lambda m: m.confidence, reverse=True)
        primary_match = rule_matches[0]

        # 5. Generate override answer
        override_answer = self._generate_override_answer(
            primary_match, semantic_answer, context
        )

        return SymbolicOverrideResult(
            should_override=primary_match.override_type != OverrideType.NONE,
            override_type=primary_match.override_type,
            override_answer=override_answer,
            matched_rules=rule_matches,
            explanation=f"Rule '{primary_match.rule_name}' triggered: {primary_match.match_reason}"
        )

    def _classify_query(self, query: str) -> List[str]:
        """Classify query into categories based on patterns."""
        query_lower = query.lower()
        categories = []

        for category, patterns in self.QUERY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    categories.append(category)
                    break

        return categories

    def _find_applicable_rules(
        self,
        query_categories: List[str],
        context: Dict[str, Any]
    ) -> List[Rule]:
        """Find rules that might apply to this query."""
        # Get all active rules
        rules = self.session.query(Rule).filter(
            Rule.is_active == True
        ).order_by(Rule.priority.desc()).all()

        applicable = []
        entity_types = context.get('entity_types', [])

        for rule in rules:
            # Check if rule applies to query categories
            rule_categories = self._extract_rule_categories(rule)
            if rule_categories & set(query_categories):
                applicable.append(rule)
                continue

            # Check if rule applies to entity types in context
            if rule.entity_types:
                if set(rule.entity_types) & set(entity_types):
                    applicable.append(rule)
                    continue

        return applicable

    def _extract_rule_categories(self, rule: Rule) -> set:
        """Extract categories that a rule applies to from its metadata."""
        categories = set()

        rule_text = f"{rule.name} {rule.description} {rule.condition}".lower()

        for category, patterns in self.QUERY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, rule_text):
                    categories.add(category)
                    break

        return categories

    def _evaluate_rule(
        self,
        rule: Rule,
        query: str,
        semantic_answer: str,
        context: Dict[str, Any]
    ) -> Optional[RuleMatch]:
        """
        Evaluate if a rule should trigger for this query.

        This is the REAL implementation (not stubbed).
        """
        condition_lower = rule.condition.lower() if rule.condition else ""
        query_lower = query.lower()
        action_lower = rule.action.lower() if rule.action else ""

        triggered = False
        match_reason = ""
        override_type = OverrideType.NONE
        constraint_text = None

        # Pattern: "IF entity_type IS X THEN constraint"
        entity_type_match = re.search(
            r'if\s+(?:entity[_\s]?type|type)\s+(?:is|=)\s+["\']?(\w+)["\']?',
            condition_lower
        )
        if entity_type_match:
            required_type = entity_type_match.group(1).upper()
            if required_type in context.get('entity_types', []):
                triggered = True
                match_reason = f"Entity type {required_type} matches"

        # Pattern: "IF role IS executive THEN minimum X"
        role_match = re.search(
            r'if\s+role\s+(?:is|=|contains)\s+["\']?(\w+)["\']?',
            condition_lower
        )
        if role_match:
            required_role = role_match.group(1).lower()
            target_entity = context.get('target_entity', {})
            entity_props = target_entity.get('properties', {}) if isinstance(target_entity, dict) else {}
            entity_role = str(entity_props.get('role', '')).lower()

            if required_role in entity_role or required_role in query_lower:
                triggered = True
                match_reason = f"Role '{required_role}' detected"

        # Pattern: Keywords in query match rule condition
        condition_keywords = re.findall(r'\b(\w{4,})\b', condition_lower)
        query_keywords = re.findall(r'\b(\w{4,})\b', query_lower)
        keyword_overlap = set(condition_keywords) & set(query_keywords)
        if len(keyword_overlap) >= 2:
            triggered = True
            match_reason = f"Keywords match: {keyword_overlap}"

        # Pattern: "minimum X" or "at least X" constraint
        minimum_match = re.search(
            r'(?:minimum|at\s+least|min)\s+(\d+)',
            action_lower
        )
        if minimum_match and triggered:
            override_type = OverrideType.CONSTRAINT
            min_value = minimum_match.group(1)
            constraint_text = f"Minimum value: {min_value}"

            # Check if semantic answer violates the constraint
            answer_numbers = re.findall(r'\b(\d+)\b', semantic_answer)
            for num in answer_numbers:
                try:
                    if int(num) < int(min_value):
                        match_reason += f" | Semantic answer ({num}) violates minimum ({min_value})"
                except ValueError:
                    pass

        # Pattern: "never disclose" or "do not reveal"
        prohibit_match = re.search(
            r'(?:never|do\s+not|don\'t|cannot)\s+(?:disclose|reveal|share|tell|provide)',
            condition_lower
        )
        if prohibit_match:
            # Check if query is asking for prohibited information
            prohibited_terms = re.findall(r'(?:salary|compensation|confidential|private|secret)', condition_lower)
            for term in prohibited_terms:
                if term in query_lower:
                    triggered = True
                    override_type = OverrideType.PROHIBIT
                    match_reason = f"Query asks for prohibited information: {term}"

        # Pattern: Always answer with specific text
        always_match = re.search(
            r'always\s+(?:answer|respond|reply|say)\s+(?:with\s+)?["\'](.+?)["\']',
            action_lower
        )
        if always_match and triggered:
            override_type = OverrideType.REPLACE

        if not triggered:
            return None

        return RuleMatch(
            rule_id=str(rule.id),
            rule_name=rule.name,
            override_type=override_type if override_type != OverrideType.NONE else OverrideType.AUGMENT,
            confidence=rule.priority / 100.0 if rule.priority else 0.5,
            match_reason=match_reason,
            constraint_text=constraint_text
        )

    def _generate_override_answer(
        self,
        match: RuleMatch,
        semantic_answer: str,
        context: Dict[str, Any]
    ) -> str:
        """Generate the override answer based on the rule match."""
        rule = self.session.query(Rule).get(match.rule_id)

        if match.override_type == OverrideType.PROHIBIT:
            return (
                "I cannot provide this information. "
                f"Reason: {rule.description if rule else 'Policy restriction'}"
            )

        if match.override_type == OverrideType.REPLACE:
            return rule.action if rule else semantic_answer

        if match.override_type == OverrideType.CONSTRAINT:
            # Apply constraint to semantic answer
            if match.constraint_text:
                # Extract the minimum value
                min_match = re.search(r'(\d+)', match.constraint_text)
                if min_match:
                    min_value = int(min_match.group(1))

                    # Replace any lower values in the answer
                    def replace_if_lower(m):
                        try:
                            if int(m.group(0)) < min_value:
                                return f"{min_value} (minimum per policy)"
                        except ValueError:
                            pass
                        return m.group(0)

                    modified = re.sub(r'\b(\d+)\b', replace_if_lower, semantic_answer)
                    if modified != semantic_answer:
                        return modified

            return f"{semantic_answer}\n\n[Policy Note: {match.constraint_text}]"

        if match.override_type == OverrideType.AUGMENT:
            caveat = rule.description if rule else match.match_reason
            return f"{semantic_answer}\n\n[Note: {caveat}]"

        return semantic_answer


def check_symbolic_override(
    session: Session,
    query: str,
    semantic_answer: str,
    context: Dict[str, Any],
    tenant_id: str = None
) -> Tuple[bool, str, str]:
    """
    Check if symbolic rules should override the semantic answer.

    Convenience function for use in query pipeline.

    Returns:
        Tuple of (should_override, final_answer, explanation)
    """
    engine = SymbolicOverrideEngine(session, tenant_id)
    result = engine.evaluate(query, semantic_answer, context)

    if result.should_override:
        return True, result.override_answer, result.explanation
    else:
        return False, semantic_answer, "No override"
