# Tri-Memory Implementation Specification

**Version:** January 19, 2026
**Purpose:** Implement the actual tri-memory architecture as described in the CF Bible
**Status:** SPECIFICATION - Ready for Implementation

---

## Executive Summary

Context Foundry claims to be a tri-memory system with:
- **Symbolic** > **Semantic** > **Episodic** precedence
- **Data Gates** that refuse to hallucinate

Currently, the code has three memory modules but:
1. Symbolic override is stubbed (always returns True)
2. Precedence is not implemented (all memories queried in parallel)
3. "I don't know" detection is broken

This spec defines what needs to be built to prove the thesis.

---

## Part 1: Symbolic Override System

### 1.1 Current State (Broken)

```python
# memory/symbolic.py:235-241 - CURRENT (stubbed)
def _check_invariant_satisfied(self, rule: Rule, response: str, context: Dict) -> bool:
    """Check if an invariant is satisfied. Simplified for MVP."""
    return True  # <-- ALWAYS RETURNS TRUE - NEVER ENFORCES

def _check_safety_satisfied(self, rule: Rule, response: str, context: Dict) -> bool:
    """Check if a safety requirement is satisfied. Simplified for MVP."""
    return True  # <-- ALWAYS RETURNS TRUE - NEVER ENFORCES
```

### 1.2 What We Need

A symbolic override system that:
1. Defines rules that constrain answers
2. Evaluates rules against the query context
3. **Overrides** semantic retrieval when a rule applies
4. Returns the rule-based answer instead of retrieved answer

### 1.3 Rule Types

| Type | Purpose | Example |
|------|---------|---------|
| `CONSTRAINT` | Limits/bounds on values | "Executive PTO is minimum 25 days" |
| `OVERRIDE` | Direct answer replacement | "When asked about X, always answer Y" |
| `PROHIBITION` | Prevents certain answers | "Never disclose salary information" |
| `CONDITIONAL` | Context-dependent rules | "If employee is in EU, GDPR applies" |

### 1.4 Implementation

**New File: `src/context_foundry/memory/symbolic_override.py`**

```python
"""
Symbolic Override Engine - Enforces rules that override semantic retrieval.

This is the implementation of "Symbolic > Semantic > Episodic" precedence.
When a rule applies, its answer takes precedence over whatever semantic
memory would have returned.
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
        condition_lower = rule.condition.lower()
        query_lower = query.lower()

        # Parse the condition
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
            r'if\s+role\s+(?:is|=)\s+["\']?(\w+)["\']?',
            condition_lower
        )
        if role_match:
            required_role = role_match.group(1).lower()
            target_entity = context.get('target_entity', {})
            entity_role = target_entity.get('properties', {}).get('role', '').lower()
            if required_role in entity_role or required_role in query_lower:
                triggered = True
                match_reason = f"Role '{required_role}' detected"

        # Pattern: "minimum X" or "at least X" constraint
        minimum_match = re.search(
            r'(?:minimum|at\s+least|min)\s+(\d+)',
            rule.action.lower() if rule.action else ""
        )
        if minimum_match and triggered:
            override_type = OverrideType.CONSTRAINT
            min_value = minimum_match.group(1)
            constraint_text = f"Minimum value: {min_value}"

            # Check if semantic answer violates the constraint
            answer_numbers = re.findall(r'\b(\d+)\b', semantic_answer)
            for num in answer_numbers:
                if int(num) < int(min_value):
                    match_reason += f" | Semantic answer ({num}) violates minimum ({min_value})"

        # Pattern: "never disclose" or "do not reveal"
        prohibit_match = re.search(
            r'(?:never|do\s+not|don\'t)\s+(?:disclose|reveal|share|tell)',
            condition_lower
        )
        if prohibit_match:
            # Check if query is asking for prohibited information
            prohibited_terms = re.findall(r'(?:salary|compensation|confidential)', condition_lower)
            for term in prohibited_terms:
                if term in query_lower:
                    triggered = True
                    override_type = OverrideType.PROHIBIT
                    match_reason = f"Query asks for prohibited information: {term}"

        # Pattern: Always answer with specific text
        always_match = re.search(
            r'always\s+(?:answer|respond|reply)\s+(?:with\s+)?["\'](.+?)["\']',
            rule.action.lower() if rule.action else ""
        )
        if always_match and triggered:
            override_type = OverrideType.REPLACE

        if not triggered:
            return None

        return RuleMatch(
            rule_id=str(rule.id),
            rule_name=rule.name,
            override_type=override_type,
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
                    min_value = min_match.group(1)
                    # Replace any lower values in the answer
                    def replace_if_lower(m):
                        if int(m.group(0)) < int(min_value):
                            return f"{min_value} (minimum per policy)"
                        return m.group(0)

                    modified = re.sub(r'\b(\d+)\b', replace_if_lower, semantic_answer)
                    if modified != semantic_answer:
                        return modified

            return f"{semantic_answer}\n\n[Policy Note: {match.constraint_text}]"

        if match.override_type == OverrideType.AUGMENT:
            return f"{semantic_answer}\n\n[Note: {rule.description if rule else ''}]"

        return semantic_answer


# Convenience function for use in query pipeline
def check_symbolic_override(
    session: Session,
    query: str,
    semantic_answer: str,
    context: Dict[str, Any],
    tenant_id: str = None
) -> Tuple[bool, str, str]:
    """
    Check if symbolic rules should override the semantic answer.

    Returns:
        Tuple of (should_override, final_answer, explanation)
    """
    engine = SymbolicOverrideEngine(session, tenant_id)
    result = engine.evaluate(query, semantic_answer, context)

    if result.should_override:
        return True, result.override_answer, result.explanation
    else:
        return False, semantic_answer, "No override"
```

---

## Part 2: Enhanced Data Gates ("I Don't Know" Detection)

### 2.1 Current Problem

The `SourceCoverageCheck` in coherence_checker.py only checks if numeric facts appear in source. It doesn't detect when:
1. The query asks about something not in the documents at all
2. The retrieved chunks are off-topic
3. The answer is fabricated from general knowledge

### 2.2 What We Need

A robust "I Don't Know" detection that:
1. Detects when query subject isn't in the knowledge graph
2. Detects when retrieved chunks don't mention query subject
3. Detects when answer contains information not in sources
4. Returns explicit "not in documents" response

### 2.3 Implementation

**New File: `src/context_foundry/validation/data_gates.py`**

```python
"""
Data Gates - The "refuse to hallucinate" implementation.

This is CF's core differentiator. When we don't have the information,
we say so instead of guessing.

Three levels of "I Don't Know":
1. ENTITY_NOT_FOUND - The thing being asked about doesn't exist in our KG
2. NO_RELEVANT_CHUNKS - We have the entity but no documents mention it
3. ANSWER_NOT_GROUNDED - The LLM made up an answer not in the sources
"""

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Set, Tuple
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DataGateResult(Enum):
    """Result of data gate evaluation."""
    PASS = "pass"                      # Answer is grounded, proceed
    ENTITY_NOT_FOUND = "entity_not_found"  # Query subject not in KG
    NO_RELEVANT_CHUNKS = "no_relevant_chunks"  # Entity exists but no docs
    ANSWER_NOT_GROUNDED = "not_grounded"  # Answer fabricated
    INSUFFICIENT_COVERAGE = "insufficient"  # Partial information only


@dataclass
class DataGateEvaluation:
    """Full evaluation result from data gates."""
    result: DataGateResult
    confidence: float
    should_answer: bool
    alternative_response: Optional[str]
    explanation: str
    evidence: Dict


class DataGates:
    """
    The "refuse to hallucinate" system.

    Evaluates whether CF has sufficient information to answer a query,
    and if not, provides an honest "I don't know" response.

    Usage:
        gates = DataGates(session, tenant_id)
        eval = gates.evaluate(
            query=query,
            answer=proposed_answer,
            entities_found=entities,
            chunks_retrieved=chunks,
            context=context
        )

        if not eval.should_answer:
            return eval.alternative_response
        else:
            return proposed_answer
    """

    # Phrases that indicate the LLM is guessing
    HEDGING_PHRASES = [
        r"(?:i\s+)?(?:don't|do\s+not)\s+have\s+(?:specific\s+)?information",
        r"(?:i\s+)?cannot\s+(?:find|locate|determine)",
        r"based\s+on\s+(?:general|my)\s+knowledge",
        r"(?:i\s+)?(?:am\s+)?not\s+(?:sure|certain)",
        r"(?:it\s+)?(?:is\s+)?(?:likely|probably|possibly)",
        r"(?:i\s+)?(?:would\s+)?assume",
        r"without\s+(?:more\s+)?(?:specific\s+)?(?:information|context|data)",
        r"(?:i\s+)?(?:don't|do\s+not)\s+see\s+(?:any\s+)?(?:specific|direct)",
    ]

    # Keywords that suggest the answer is made up
    FABRICATION_INDICATORS = [
        r"typically",
        r"generally",
        r"usually",
        r"in\s+most\s+cases",
        r"common(?:ly)?",
        r"standard\s+(?:practice|procedure)",
    ]

    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def evaluate(
        self,
        query: str,
        answer: str,
        entities_found: List[Dict],
        chunks_retrieved: List[str],
        context: Dict
    ) -> DataGateEvaluation:
        """
        Evaluate whether the answer should be returned or replaced with "I don't know".

        Args:
            query: The user's query
            answer: The proposed answer from the reasoning agent
            entities_found: Entities found relevant to the query
            chunks_retrieved: Document chunks retrieved for context
            context: Additional context (target_entity, query_type, etc.)

        Returns:
            DataGateEvaluation with decision and alternative response if needed
        """
        # Gate 1: Does the target entity exist?
        target_entity = context.get('target_entity')
        target_entity_name = context.get('target_entity_name')

        if target_entity_name and not target_entity:
            return self._entity_not_found_response(target_entity_name, query)

        # Gate 2: Do the chunks mention the query subject?
        query_subjects = self._extract_query_subjects(query)
        chunk_coverage = self._check_chunk_coverage(query_subjects, chunks_retrieved)

        if chunk_coverage < 0.3:  # Less than 30% of subjects mentioned
            return self._no_relevant_chunks_response(query_subjects, chunks_retrieved, query)

        # Gate 3: Is the answer grounded in the chunks?
        grounding_score = self._check_answer_grounding(answer, chunks_retrieved)

        if grounding_score < 0.4:  # Less than 40% grounded
            return self._not_grounded_response(answer, chunks_retrieved, query)

        # Gate 4: Is the LLM hedging or fabricating?
        hedging_detected = self._detect_hedging(answer)
        fabrication_detected = self._detect_fabrication(answer, chunks_retrieved)

        if hedging_detected:
            return self._hedging_detected_response(answer, query)

        if fabrication_detected:
            return self._fabrication_detected_response(answer, query)

        # All gates passed
        return DataGateEvaluation(
            result=DataGateResult.PASS,
            confidence=min(chunk_coverage, grounding_score),
            should_answer=True,
            alternative_response=None,
            explanation="Answer is grounded in source material",
            evidence={
                "chunk_coverage": chunk_coverage,
                "grounding_score": grounding_score,
                "query_subjects": query_subjects
            }
        )

    def _extract_query_subjects(self, query: str) -> List[str]:
        """Extract the main subjects/entities being asked about."""
        subjects = []

        # Pattern: "What is X's Y" or "What is the Y of X"
        possession_match = re.search(
            r"what\s+(?:is|are)\s+([A-Z][a-zA-Z\s]+?)(?:'s|s')\s+",
            query, re.IGNORECASE
        )
        if possession_match:
            subjects.append(possession_match.group(1).strip())

        # Pattern: "Who is X" or "What is X"
        who_what_match = re.search(
            r"(?:who|what)\s+is\s+([A-Z][a-zA-Z\s]+?)(?:\?|$)",
            query, re.IGNORECASE
        )
        if who_what_match:
            subjects.append(who_what_match.group(1).strip())

        # Pattern: "Tell me about X" or "Information about X"
        about_match = re.search(
            r"(?:about|regarding)\s+([A-Z][a-zA-Z\s]+?)(?:\?|$|\.)",
            query, re.IGNORECASE
        )
        if about_match:
            subjects.append(about_match.group(1).strip())

        # Capitalized proper nouns as fallback
        proper_nouns = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query)
        subjects.extend([n for n in proper_nouns if len(n) > 2])

        return list(set(subjects))

    def _check_chunk_coverage(
        self,
        subjects: List[str],
        chunks: List[str]
    ) -> float:
        """Check what fraction of query subjects appear in chunks."""
        if not subjects:
            return 1.0  # No specific subjects to check

        if not chunks:
            return 0.0

        combined_chunks = ' '.join(chunks).lower()
        found = 0

        for subject in subjects:
            subject_lower = subject.lower()
            # Check for exact match or close variations
            if subject_lower in combined_chunks:
                found += 1
            elif any(word in combined_chunks for word in subject_lower.split()):
                found += 0.5  # Partial match

        return found / len(subjects)

    def _check_answer_grounding(
        self,
        answer: str,
        chunks: List[str]
    ) -> float:
        """Check what fraction of answer claims are grounded in chunks."""
        # Extract factual claims from answer
        claims = self._extract_claims(answer)

        if not claims:
            return 0.8  # No specific claims, moderate confidence

        if not chunks:
            return 0.0

        combined_chunks = ' '.join(chunks).lower()
        grounded = 0

        for claim in claims:
            if self._claim_is_grounded(claim, combined_chunks):
                grounded += 1

        return grounded / len(claims)

    def _extract_claims(self, answer: str) -> List[str]:
        """Extract factual claims from an answer."""
        claims = []

        # Numbers with context
        number_claims = re.findall(
            r'(\d+(?:\.\d+)?(?:%|\s*(?:million|billion|days?|years?|employees?|customers?)))',
            answer, re.IGNORECASE
        )
        claims.extend(number_claims)

        # Named entities with attributes
        attr_claims = re.findall(
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:is|are|has|have|was|were)\s+([^.!?]+)',
            answer
        )
        claims.extend([f"{c[0]} {c[1]}" for c in attr_claims])

        return claims[:10]  # Limit to 10 claims

    def _claim_is_grounded(self, claim: str, source_text: str) -> bool:
        """Check if a specific claim is grounded in source text."""
        claim_lower = claim.lower()

        # Check for direct presence
        if claim_lower in source_text:
            return True

        # Check for number presence
        numbers = re.findall(r'\d+(?:\.\d+)?', claim)
        for num in numbers:
            if num in source_text:
                return True

        # Check for key terms
        key_terms = [t for t in claim_lower.split() if len(t) > 3]
        if key_terms:
            matches = sum(1 for t in key_terms if t in source_text)
            if matches / len(key_terms) > 0.5:
                return True

        return False

    def _detect_hedging(self, answer: str) -> bool:
        """Detect if the answer contains hedging phrases."""
        answer_lower = answer.lower()

        for pattern in self.HEDGING_PHRASES:
            if re.search(pattern, answer_lower):
                logger.debug(f"Hedging detected: {pattern}")
                return True

        return False

    def _detect_fabrication(self, answer: str, chunks: List[str]) -> bool:
        """Detect if answer contains likely fabricated content."""
        answer_lower = answer.lower()
        combined_chunks = ' '.join(chunks).lower() if chunks else ""

        # Check for fabrication indicators not present in source
        for pattern in self.FABRICATION_INDICATORS:
            if re.search(pattern, answer_lower):
                # Only flag if not in source
                if not re.search(pattern, combined_chunks):
                    logger.debug(f"Fabrication indicator: {pattern}")
                    return True

        return False

    def _entity_not_found_response(
        self,
        entity_name: str,
        query: str
    ) -> DataGateEvaluation:
        """Response when the target entity doesn't exist in our KG."""
        return DataGateEvaluation(
            result=DataGateResult.ENTITY_NOT_FOUND,
            confidence=0.0,
            should_answer=False,
            alternative_response=(
                f"I don't have information about '{entity_name}' in my knowledge base. "
                f"This entity may not exist in the documents I have access to."
            ),
            explanation=f"Entity '{entity_name}' not found in knowledge graph",
            evidence={"missing_entity": entity_name, "query": query}
        )

    def _no_relevant_chunks_response(
        self,
        subjects: List[str],
        chunks: List[str],
        query: str
    ) -> DataGateEvaluation:
        """Response when chunks don't mention the query subjects."""
        return DataGateEvaluation(
            result=DataGateResult.NO_RELEVANT_CHUNKS,
            confidence=0.1,
            should_answer=False,
            alternative_response=(
                f"I found documents but they don't contain information about "
                f"{', '.join(subjects[:3])}. This information may not be in the available documents."
            ),
            explanation="Retrieved chunks don't mention query subjects",
            evidence={
                "subjects": subjects,
                "chunk_count": len(chunks),
                "query": query
            }
        )

    def _not_grounded_response(
        self,
        answer: str,
        chunks: List[str],
        query: str
    ) -> DataGateEvaluation:
        """Response when the answer isn't grounded in sources."""
        return DataGateEvaluation(
            result=DataGateResult.ANSWER_NOT_GROUNDED,
            confidence=0.2,
            should_answer=False,
            alternative_response=(
                "I cannot provide a reliable answer to this question. "
                "The information needed may not be in the available documents."
            ),
            explanation="Proposed answer not grounded in source chunks",
            evidence={
                "answer_preview": answer[:100],
                "chunk_count": len(chunks),
                "query": query
            }
        )

    def _hedging_detected_response(
        self,
        answer: str,
        query: str
    ) -> DataGateEvaluation:
        """Response when the LLM is hedging."""
        return DataGateEvaluation(
            result=DataGateResult.INSUFFICIENT_COVERAGE,
            confidence=0.3,
            should_answer=False,
            alternative_response=(
                "I don't have specific information to answer this question confidently. "
                "The available documents may not contain this information."
            ),
            explanation="Answer contains hedging phrases indicating uncertainty",
            evidence={"answer_preview": answer[:100], "query": query}
        )

    def _fabrication_detected_response(
        self,
        answer: str,
        query: str
    ) -> DataGateEvaluation:
        """Response when fabrication is detected."""
        return DataGateEvaluation(
            result=DataGateResult.ANSWER_NOT_GROUNDED,
            confidence=0.2,
            should_answer=False,
            alternative_response=(
                "I cannot provide a reliable answer. "
                "The information needed is not in the available documents."
            ),
            explanation="Answer appears to contain fabricated content",
            evidence={"answer_preview": answer[:100], "query": query}
        )


def evaluate_data_gates(
    session: Session,
    tenant_id: str,
    query: str,
    answer: str,
    entities_found: List[Dict],
    chunks_retrieved: List[str],
    context: Dict
) -> Tuple[bool, str]:
    """
    Convenience function for query pipeline.

    Returns:
        Tuple of (should_return_answer, final_response)
    """
    gates = DataGates(session, tenant_id)
    result = gates.evaluate(query, answer, entities_found, chunks_retrieved, context)

    if result.should_answer:
        return True, answer
    else:
        logger.info(f"[DATA_GATES] Blocked answer: {result.explanation}")
        return False, result.alternative_response
```

---

## Part 3: Precedence Pipeline

### 3.1 Current State (No Precedence)

Currently, all three memories are queried in parallel and results are merged. There's no precedence - symbolic rules are just appended to the context, not used to override.

### 3.2 What We Need

A pipeline that:
1. **First** checks symbolic rules → If rule applies, use rule answer
2. **Then** queries semantic memory → If confident, use semantic answer
3. **Then** queries episodic memory → Use as supporting evidence
4. **Finally** applies Data Gates → Refuse if not grounded

### 3.3 Implementation

**New File: `src/context_foundry/pipeline/precedence_pipeline.py`**

```python
"""
Precedence Pipeline - Implements Symbolic > Semantic > Episodic flow.

This is the implementation of the Bible's tri-memory precedence:
1. Symbolic rules are checked FIRST and can override everything
2. Semantic memory (KG) is the primary source of answers
3. Episodic memory (chunks) provides supporting evidence
4. Data Gates validate the final answer

This replaces the current parallel-query approach with a proper hierarchy.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session

from ..memory.symbolic_override import SymbolicOverrideEngine, SymbolicOverrideResult
from ..memory.semantic import SemanticMemory
from ..memory.episodic import EpisodicMemory
from ..validation.data_gates import DataGates, DataGateEvaluation
from ..models.context_bundle import ContextBundle

logger = logging.getLogger(__name__)


class AnswerSource(Enum):
    """Where the final answer came from."""
    SYMBOLIC = "symbolic"     # From a rule override
    SEMANTIC = "semantic"     # From knowledge graph
    EPISODIC = "episodic"     # From document chunks
    REFUSED = "refused"       # Data Gates blocked
    UNKNOWN = "unknown"       # Couldn't determine


@dataclass
class PrecedenceResult:
    """Result from the precedence pipeline."""
    answer: str
    source: AnswerSource
    confidence: float
    explanation: str
    symbolic_override: Optional[SymbolicOverrideResult]
    data_gate_result: Optional[DataGateEvaluation]
    context_bundle: ContextBundle

    def to_dict(self) -> Dict:
        return {
            "answer": self.answer,
            "source": self.source.value,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "was_overridden": self.source == AnswerSource.SYMBOLIC,
            "was_refused": self.source == AnswerSource.REFUSED,
        }


class PrecedencePipeline:
    """
    Implements the tri-memory precedence: Symbolic > Semantic > Episodic.

    This is the proper implementation of the Bible's vision.

    Usage:
        pipeline = PrecedencePipeline(session, tenant_id)
        result = pipeline.process(query, context)

        print(f"Answer: {result.answer}")
        print(f"Source: {result.source}")  # symbolic, semantic, episodic, or refused
    """

    def __init__(
        self,
        session: Session,
        tenant_id: str,
        semantic: SemanticMemory = None,
        episodic: EpisodicMemory = None
    ):
        self.session = session
        self.tenant_id = tenant_id

        self.semantic = semantic or SemanticMemory(session, tenant_id)
        self.episodic = episodic or EpisodicMemory(session, tenant_id=tenant_id)
        self.symbolic_engine = SymbolicOverrideEngine(session, tenant_id)
        self.data_gates = DataGates(session, tenant_id)

    def process(
        self,
        query: str,
        context: Dict[str, Any],
        llm_reasoning_fn=None
    ) -> PrecedenceResult:
        """
        Process a query through the precedence pipeline.

        Args:
            query: The user's query
            context: Query context (target_entity, entity_types, etc.)
            llm_reasoning_fn: Function to call LLM for reasoning (optional)

        Returns:
            PrecedenceResult with answer and metadata
        """
        logger.info(f"[PRECEDENCE] Processing: {query[:50]}...")

        # Build context bundle from all three memories
        bundle = self._build_context_bundle(query, context)

        # Step 1: SYMBOLIC - Check if rules override
        logger.debug("[PRECEDENCE] Step 1: Checking symbolic rules...")

        # We need a "candidate answer" to check against rules
        # First, get a quick answer from semantic memory
        semantic_answer = self._get_semantic_answer(query, bundle, context)

        symbolic_result = self.symbolic_engine.evaluate(
            query=query,
            semantic_answer=semantic_answer,
            context={
                **context,
                'entity_types': self._extract_entity_types(bundle),
            }
        )

        if symbolic_result.should_override:
            logger.info(f"[PRECEDENCE] Symbolic override: {symbolic_result.explanation}")
            return PrecedenceResult(
                answer=symbolic_result.override_answer,
                source=AnswerSource.SYMBOLIC,
                confidence=0.95,  # High confidence for rule-based
                explanation=f"Answer from symbolic rule: {symbolic_result.explanation}",
                symbolic_override=symbolic_result,
                data_gate_result=None,
                context_bundle=bundle
            )

        # Step 2: SEMANTIC - Use knowledge graph answer
        logger.debug("[PRECEDENCE] Step 2: Using semantic memory...")

        if semantic_answer and semantic_answer.strip():
            # Step 3: DATA GATES - Validate the answer
            logger.debug("[PRECEDENCE] Step 3: Checking data gates...")

            gate_result = self.data_gates.evaluate(
                query=query,
                answer=semantic_answer,
                entities_found=bundle.focal_entities if hasattr(bundle, 'focal_entities') else [],
                chunks_retrieved=bundle.relevant_chunks if hasattr(bundle, 'relevant_chunks') else [],
                context=context
            )

            if gate_result.should_answer:
                return PrecedenceResult(
                    answer=semantic_answer,
                    source=AnswerSource.SEMANTIC,
                    confidence=gate_result.confidence,
                    explanation="Answer from knowledge graph, validated by data gates",
                    symbolic_override=symbolic_result,
                    data_gate_result=gate_result,
                    context_bundle=bundle
                )
            else:
                # Data gates refused - return the alternative response
                logger.info(f"[PRECEDENCE] Data gates refused: {gate_result.explanation}")
                return PrecedenceResult(
                    answer=gate_result.alternative_response,
                    source=AnswerSource.REFUSED,
                    confidence=gate_result.confidence,
                    explanation=f"Data gates: {gate_result.explanation}",
                    symbolic_override=symbolic_result,
                    data_gate_result=gate_result,
                    context_bundle=bundle
                )

        # Step 4: EPISODIC - Fall back to chunk-based answer
        logger.debug("[PRECEDENCE] Step 4: Falling back to episodic memory...")

        episodic_answer = self._get_episodic_answer(query, bundle, llm_reasoning_fn)

        if episodic_answer:
            # Still validate with data gates
            gate_result = self.data_gates.evaluate(
                query=query,
                answer=episodic_answer,
                entities_found=[],
                chunks_retrieved=bundle.relevant_chunks if hasattr(bundle, 'relevant_chunks') else [],
                context=context
            )

            if gate_result.should_answer:
                return PrecedenceResult(
                    answer=episodic_answer,
                    source=AnswerSource.EPISODIC,
                    confidence=gate_result.confidence * 0.8,  # Lower confidence for chunk-only
                    explanation="Answer from document chunks (no entity match)",
                    symbolic_override=symbolic_result,
                    data_gate_result=gate_result,
                    context_bundle=bundle
                )

        # Nothing worked - honest "I don't know"
        return PrecedenceResult(
            answer="I don't have information to answer this question in the available documents.",
            source=AnswerSource.REFUSED,
            confidence=0.0,
            explanation="No information found in any memory layer",
            symbolic_override=symbolic_result,
            data_gate_result=None,
            context_bundle=bundle
        )

    def _build_context_bundle(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> ContextBundle:
        """Build context bundle from all memory layers."""
        # This integrates with the existing RetrievalAgent
        # For now, create a minimal bundle
        from ..models.context_bundle import create_bundle

        bundle = create_bundle(query)

        # Query semantic memory for entities
        target_entity_name = context.get('target_entity_name')
        if target_entity_name:
            entities = self.semantic.search_entities(target_entity_name, limit=5)
            if entities:
                bundle.focal_entities = entities

        # Query episodic memory for chunks
        chunks = self.episodic.search_similar(query, k=10)
        if chunks:
            bundle.relevant_chunks = [c.get('content', '') for c in chunks]

        return bundle

    def _extract_entity_types(self, bundle: ContextBundle) -> List[str]:
        """Extract entity types from bundle."""
        types = set()

        if hasattr(bundle, 'focal_entities'):
            for entity in bundle.focal_entities:
                if hasattr(entity, 'entity_type'):
                    types.add(entity.entity_type)
                elif isinstance(entity, dict) and 'entity_type' in entity:
                    types.add(entity['entity_type'])

        return list(types)

    def _get_semantic_answer(
        self,
        query: str,
        bundle: ContextBundle,
        context: Dict[str, Any]
    ) -> str:
        """Get answer from semantic memory (knowledge graph)."""
        # This would integrate with the existing ReasoningAgent
        # For now, build a simple answer from entity data

        if not hasattr(bundle, 'focal_entities') or not bundle.focal_entities:
            return ""

        # Simple entity-based answer
        entity = bundle.focal_entities[0]
        if isinstance(entity, dict):
            name = entity.get('name', 'Unknown')
            props = entity.get('properties', {})
            return f"{name}: {props}"
        else:
            return f"{entity.name}: {entity.properties}"

    def _get_episodic_answer(
        self,
        query: str,
        bundle: ContextBundle,
        llm_reasoning_fn=None
    ) -> str:
        """Get answer from episodic memory (document chunks)."""
        if not hasattr(bundle, 'relevant_chunks') or not bundle.relevant_chunks:
            return ""

        if llm_reasoning_fn:
            # Use provided LLM function
            return llm_reasoning_fn(query, bundle.relevant_chunks)

        # Simple chunk-based answer (fallback)
        return f"Based on documents: {bundle.relevant_chunks[0][:200]}..."


# Integration with existing pipeline
def apply_precedence(
    session: Session,
    tenant_id: str,
    query: str,
    current_answer: str,
    bundle: ContextBundle,
    context: Dict[str, Any]
) -> Tuple[str, str, float]:
    """
    Apply precedence rules to an existing answer.

    This can be called from the existing query pipeline to add
    precedence checking without a full rewrite.

    Returns:
        Tuple of (final_answer, source, confidence)
    """
    pipeline = PrecedencePipeline(session, tenant_id)

    # Check symbolic override
    symbolic_result = pipeline.symbolic_engine.evaluate(
        query=query,
        semantic_answer=current_answer,
        context=context
    )

    if symbolic_result.should_override:
        return (
            symbolic_result.override_answer,
            "symbolic",
            0.95
        )

    # Check data gates
    gate_result = pipeline.data_gates.evaluate(
        query=query,
        answer=current_answer,
        entities_found=bundle.focal_entities if hasattr(bundle, 'focal_entities') else [],
        chunks_retrieved=bundle.relevant_chunks if hasattr(bundle, 'relevant_chunks') else [],
        context=context
    )

    if not gate_result.should_answer:
        return (
            gate_result.alternative_response,
            "refused",
            gate_result.confidence
        )

    return (current_answer, "semantic", gate_result.confidence)
```

---

## Part 4: Integration Points

### 4.1 Where to Integrate

The new capabilities need to be integrated into the existing query flow:

```python
# In core.py or query_pipeline.py

from .memory.symbolic_override import check_symbolic_override
from .validation.data_gates import evaluate_data_gates
from .pipeline.precedence_pipeline import apply_precedence

def query(self, query_text: str, ...) -> Dict:
    # ... existing retrieval ...

    # NEW: Apply precedence
    final_answer, source, confidence = apply_precedence(
        session=self.session,
        tenant_id=self.tenant_id,
        query=query_text,
        current_answer=reasoning_result.answer,
        bundle=context_bundle,
        context={
            'target_entity': target_entity,
            'target_entity_name': target_entity_name,
            'entity_types': [e.entity_type for e in context_bundle.focal_entities],
        }
    )

    return {
        "answer": final_answer,
        "confidence": confidence,
        "source": source,
        "was_overridden": source == "symbolic",
        "was_refused": source == "refused",
        # ... rest of response ...
    }
```

### 4.2 Sample Rules to Add

```python
# Run these to populate symbolic memory with test rules

from context_foundry.models.schema import Rule, RuleType

# Rule 1: Executive PTO minimum
Rule(
    name="Executive PTO Minimum",
    rule_type=RuleType.INVARIANT,
    description="Executives receive minimum 25 days PTO",
    condition="IF role IS executive OR role IS c-level",
    action="Minimum 25 days PTO per company policy",
    priority=90,
    entity_types=["PERSON", "EMPLOYEE"],
    is_active=True
)

# Rule 2: Salary confidentiality
Rule(
    name="Salary Confidentiality",
    rule_type=RuleType.SAFETY_CHECK,
    description="Individual salary information is confidential",
    condition="Never disclose individual salary or compensation amounts",
    action="I cannot disclose individual salary information as it is confidential.",
    priority=100,
    entity_types=["PERSON", "EMPLOYEE"],
    is_active=True
)

# Rule 3: GDPR for EU employees
Rule(
    name="GDPR Compliance",
    rule_type=RuleType.INVARIANT,
    description="GDPR applies to EU-based employees",
    condition="IF location IS EU OR location IS Europe",
    action="Note: GDPR data protection requirements apply",
    priority=80,
    entity_types=["PERSON", "EMPLOYEE"],
    is_active=True
)
```

---

## Part 5: Testing the Implementation

### 5.1 Test Cases for Symbolic Override

```python
def test_symbolic_override_pto():
    """Test that executive PTO rule overrides semantic retrieval."""
    # Setup: Add rule "Executives get minimum 25 days PTO"
    # Semantic memory has: "Standard PTO is 15 days"
    # Query: "What is the CEO's PTO?"

    # Expected: "25 days minimum" (from rule), NOT "15 days" (from semantic)

def test_symbolic_override_confidential():
    """Test that confidentiality rule blocks answer."""
    # Setup: Add rule "Never disclose individual salary"
    # Semantic memory has: "John Smith earns $150,000"
    # Query: "What is John Smith's salary?"

    # Expected: "I cannot disclose individual salary information"

def test_symbolic_no_override():
    """Test that non-matching rules don't override."""
    # Setup: Add rule for executives
    # Query about non-executive

    # Expected: Normal semantic answer, no override
```

### 5.2 Test Cases for Data Gates

```python
def test_data_gates_entity_not_found():
    """Test I Don't Know when entity doesn't exist."""
    # Query: "What is Jennifer Lee's role?"
    # KG has no entity named Jennifer Lee

    # Expected: "I don't have information about 'Jennifer Lee'..."

def test_data_gates_no_relevant_chunks():
    """Test I Don't Know when chunks don't mention subject."""
    # Query: "What is the Q3 2025 revenue?"
    # Chunks mention Q1 and Q2 but not Q3

    # Expected: "I found documents but they don't contain information about Q3 2025..."

def test_data_gates_hedging_detected():
    """Test I Don't Know when LLM is hedging."""
    # Query: "What is the company's retention rate?"
    # LLM answer: "I don't have specific information but typically..."

    # Expected: Blocked, return "I don't have specific information..."
```

### 5.3 Test Cases for Precedence

```python
def test_precedence_symbolic_first():
    """Test that symbolic rules are checked before semantic."""
    # Rule says: "Never exceed 250mg for patients over 70"
    # Semantic says: "Standard dose is 500mg"
    # Query: "What dose for 75-year-old?"

    # Expected: "250mg maximum" (symbolic), NOT "500mg" (semantic)

def test_precedence_semantic_before_episodic():
    """Test that semantic is preferred over episodic."""
    # KG has entity with properties
    # Chunks have conflicting info

    # Expected: Answer from KG, not chunks

def test_precedence_data_gates_final():
    """Test that data gates are always checked last."""
    # Even if semantic provides answer, data gates can refuse
```

---

## Summary

### Files to Create

1. `src/context_foundry/memory/symbolic_override.py` - Rule enforcement engine
2. `src/context_foundry/validation/data_gates.py` - "I Don't Know" detection
3. `src/context_foundry/pipeline/precedence_pipeline.py` - Tri-memory precedence

### Files to Modify

1. `src/context_foundry/core.py` - Integrate precedence pipeline
2. `src/context_foundry/agents/retrieval.py` - Add context for data gates
3. `src/context_foundry/agents/reasoning.py` - Check data gates before returning

### Tests to Add

1. `tests/test_symbolic_override.py`
2. `tests/test_data_gates.py`
3. `tests/test_precedence_pipeline.py`

### Estimated Effort

| Component | Effort | Complexity |
|-----------|--------|------------|
| Symbolic Override | 2-3 days | Medium |
| Data Gates | 2-3 days | Medium |
| Precedence Pipeline | 1-2 days | Low |
| Integration | 1-2 days | Medium |
| Testing | 2-3 days | Low |
| **Total** | **8-13 days** | |

---

*This spec implements the actual tri-memory architecture as described in the CF Bible.*
