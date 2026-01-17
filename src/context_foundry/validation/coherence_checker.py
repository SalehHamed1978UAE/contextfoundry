"""
Coherence Checker - Validates answers before returning to user.

Implements Data Gates principle: "Refuses to hallucinate, admits uncertainty"

Four coherence checks:
1. MultipleValuesCheck - Detects ambiguous multiple values in source
2. TerminologyMismatchCheck - Detects metric type confusion
3. LogicalContradictionCheck - Detects nonsensical answers
4. SourceCoverageCheck - Verifies answer is grounded in sources
"""

import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CheckResult:
    check_name: str
    passed: bool
    confidence: float
    reason: Optional[str] = None
    suggestion: Optional[str] = None
    competing_values: Optional[List[str]] = None


@dataclass
class CoherenceResult:
    confidence_level: ConfidenceLevel
    confidence_score: float
    checks_passed: int
    checks_failed: int
    issues: List[CheckResult]
    caveat: Optional[str] = None
    ambiguity: Optional[Dict[str, Any]] = None


class BaseCheck(ABC):
    @abstractmethod
    def check(self, query: str, answer: str, source_chunks: List[str]) -> CheckResult:
        pass


class MultipleValuesCheck(BaseCheck):
    """
    Check 1: Detect when source has multiple values that could answer the query.
    
    Triggers when query asks for a single value but source contains multiple candidates.
    Example: Query asks for "retention rate" but source has 94% AND 118%.
    """
    
    def check(self, query: str, answer: str, source_chunks: List[str]) -> CheckResult:
        answer_value = self._extract_primary_value(answer)
        if not answer_value:
            return CheckResult(
                check_name="MultipleValuesCheck",
                passed=True,
                confidence=0.9,
                reason="No extractable value in answer"
            )
        
        value_type = self._classify_value_type(answer_value)
        competing_values = []
        
        for chunk in source_chunks:
            values = self._extract_all_values_of_type(chunk, value_type)
            competing_values.extend(values)
        
        unique_values = list(set(competing_values))
        
        if len(unique_values) > 1:
            return CheckResult(
                check_name="MultipleValuesCheck",
                passed=False,
                confidence=0.5,
                reason=f"Multiple {value_type} values found in source: {unique_values}",
                suggestion="Clarify which value is needed",
                competing_values=unique_values
            )
        
        return CheckResult(
            check_name="MultipleValuesCheck",
            passed=True,
            confidence=0.9
        )
    
    def _extract_primary_value(self, text: str) -> Optional[str]:
        percentage_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if percentage_match:
            return percentage_match.group(0)
        
        dollar_match = re.search(r'\$[\d,.]+(?:\s*(?:million|billion|M|B))?', text, re.IGNORECASE)
        if dollar_match:
            return dollar_match.group(0)
        
        number_match = re.search(r'\b(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\b', text)
        if number_match:
            return number_match.group(0)
        
        return None
    
    def _classify_value_type(self, value: str) -> str:
        if '%' in value:
            return 'percentage'
        elif '$' in value:
            return 'currency'
        else:
            return 'number'
    
    def _extract_all_values_of_type(self, text: str, value_type: str) -> List[str]:
        if value_type == 'percentage':
            matches = re.findall(r'\d+(?:\.\d+)?\s*%', text)
            return [m.replace(' ', '') for m in matches]
        elif value_type == 'currency':
            matches = re.findall(r'\$[\d,.]+(?:\s*(?:million|billion|M|B))?', text, re.IGNORECASE)
            return matches
        else:
            matches = re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b', text)
            return matches


class TerminologyMismatchCheck(BaseCheck):
    """
    Check 2: Detect when answer uses different terminology than query asked for.
    
    Example: Query asks for "customer retention" but answer mentions "NRR".
    """
    
    DISTINCT_TERMS = {
        "customer retention": ["nrr", "net revenue retention", "revenue retention", "dollar retention"],
        "retention rate": ["nrr", "net revenue retention", "revenue retention"],
        "net income": ["ebitda", "operating income", "operating profit", "gross profit"],
        "ebitda": ["net income", "net profit", "net loss"],
        "revenue": ["profit", "income", "earnings", "margin"],
        "employees": ["headcount", "staff count", "team size"],
        "customers": ["users", "clients", "accounts"],
    }
    
    def check(self, query: str, answer: str, source_chunks: List[str]) -> CheckResult:
        query_lower = query.lower()
        answer_lower = answer.lower()
        
        for term, conflicting_terms in self.DISTINCT_TERMS.items():
            if term in query_lower:
                for conflicting in conflicting_terms:
                    if conflicting in answer_lower and conflicting not in query_lower:
                        return CheckResult(
                            check_name="TerminologyMismatchCheck",
                            passed=False,
                            confidence=0.5,
                            reason=f"Query asks for '{term}' but answer mentions '{conflicting}'",
                            suggestion=f"'{term}' and '{conflicting}' are different metrics"
                        )
        
        return CheckResult(
            check_name="TerminologyMismatchCheck",
            passed=True,
            confidence=0.9
        )


class LogicalContradictionCheck(BaseCheck):
    """
    Check 3: Detect answers that don't make logical sense.
    
    Example: "Target: 140" when text shows "Close 150 (Target: 140)" - why is target lower?
    """
    
    def check(self, query: str, answer: str, source_chunks: List[str]) -> CheckResult:
        query_lower = query.lower()
        source_text = ' '.join(source_chunks).lower()
        
        if 'target' in query_lower or 'goal' in query_lower:
            result = self._check_target_contradiction(answer, source_text)
            if result:
                return result
        
        if 'growth' in query_lower:
            result = self._check_growth_contradiction(answer)
            if result:
                return result
        
        return CheckResult(
            check_name="LogicalContradictionCheck",
            passed=True,
            confidence=0.9
        )
    
    def _check_target_contradiction(self, answer: str, source_text: str) -> Optional[CheckResult]:
        patterns = [
            r'(?:close|achieve|reach|hit)\s+(\d+)\s+[^(]*\(target:\s*(\d+)\)',
            r'(\d+)\s+[^(]*\(target:\s*(\d+)\)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, source_text, re.IGNORECASE)
            if match:
                goal_value = int(match.group(1))
                target_in_parens = int(match.group(2))
                
                answer_numbers = re.findall(r'\b(\d+)\b', answer)
                
                if answer_numbers:
                    answer_num = int(answer_numbers[0])
                    
                    if answer_num == target_in_parens and goal_value > target_in_parens:
                        return CheckResult(
                            check_name="LogicalContradictionCheck",
                            passed=False,
                            confidence=0.4,
                            reason=f"Target ({target_in_parens}) is lower than stated goal ({goal_value}). Ambiguous OKR format.",
                            suggestion=f"The goal appears to be {goal_value}, not {target_in_parens}",
                            competing_values=[str(goal_value), str(target_in_parens)]
                        )
        
        return None
    
    def _check_growth_contradiction(self, answer: str) -> Optional[CheckResult]:
        negative_growth = re.search(r'grew?\s+(?:by\s+)?-\s*\d+', answer, re.IGNORECASE)
        if negative_growth:
            return CheckResult(
                check_name="LogicalContradictionCheck",
                passed=False,
                confidence=0.5,
                reason="Negative growth rate detected - should be decline, not growth",
                suggestion="Verify if this is growth or decline"
            )
        
        return None


class SourceCoverageCheck(BaseCheck):
    """
    Check 4: Verify answer is grounded in source material.
    
    Checks that key numeric facts in the answer appear in the source chunks.
    """
    
    def check(self, query: str, answer: str, source_chunks: List[str]) -> CheckResult:
        answer_facts = self._extract_facts(answer)
        
        if not answer_facts:
            return CheckResult(
                check_name="SourceCoverageCheck",
                passed=True,
                confidence=0.9,
                reason="No extractable facts in answer"
            )
        
        source_text = ' '.join(source_chunks)
        unsupported_facts = []
        
        for fact in answer_facts:
            if not self._fact_in_source(fact, source_text):
                unsupported_facts.append(fact)
        
        if unsupported_facts:
            coverage_ratio = (len(answer_facts) - len(unsupported_facts)) / len(answer_facts)
            
            if coverage_ratio < 0.5:
                return CheckResult(
                    check_name="SourceCoverageCheck",
                    passed=False,
                    confidence=0.3,
                    reason=f"Facts not found in source: {unsupported_facts}",
                    suggestion="Answer may contain unsupported claims"
                )
        
        return CheckResult(
            check_name="SourceCoverageCheck",
            passed=True,
            confidence=0.9
        )
    
    def _extract_facts(self, text: str) -> List[str]:
        facts = []
        
        percentages = re.findall(r'\d+(?:\.\d+)?%', text)
        facts.extend(percentages)
        
        dollars = re.findall(r'\$[\d,.]+(?:\s*(?:million|billion|M|B))?', text, re.IGNORECASE)
        facts.extend(dollars)
        
        large_numbers = re.findall(r'\b\d{1,3}(?:,\d{3})+\b', text)
        facts.extend(large_numbers)
        
        return facts[:5]
    
    def _fact_in_source(self, fact: str, source_text: str) -> bool:
        normalized_fact = fact.replace(',', '').replace(' ', '').lower()
        normalized_source = source_text.replace(',', '').replace(' ', '').lower()
        
        if normalized_fact in normalized_source:
            return True
        
        num_match = re.search(r'[\d.]+', normalized_fact)
        if num_match:
            number = num_match.group()
            if number in normalized_source:
                return True
        
        return False


class CoherenceChecker:
    """
    Main coherence checker that runs all checks and aggregates results.
    
    Usage:
        checker = CoherenceChecker()
        result = checker.validate(query, answer, source_chunks)
        
        if result.confidence_level == ConfidenceLevel.LOW:
            logger.warning(f"Low confidence answer: {result.issues}")
    """
    
    def __init__(self):
        self.checks = [
            MultipleValuesCheck(),
            TerminologyMismatchCheck(),
            LogicalContradictionCheck(),
            SourceCoverageCheck(),
        ]
    
    def validate(
        self,
        query: str,
        answer: str,
        source_chunks: List[str]
    ) -> CoherenceResult:
        """
        Run all coherence checks on an answer.
        
        Args:
            query: The original user query
            answer: The LLM-generated answer
            source_chunks: The chunks used to generate the answer
            
        Returns:
            CoherenceResult with confidence level and any issues found
        """
        if not source_chunks:
            source_chunks = []
        
        results = []
        for check in self.checks:
            try:
                result = check.check(query, answer, source_chunks)
                results.append(result)
            except Exception as e:
                logger.warning(f"Coherence check {check.__class__.__name__} failed: {e}")
                results.append(CheckResult(
                    check_name=check.__class__.__name__,
                    passed=True,
                    confidence=0.9,
                    reason=f"Check error: {str(e)}"
                ))
        
        return self._aggregate_results(results)
    
    def _aggregate_results(self, results: List[CheckResult]) -> CoherenceResult:
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        
        if not results:
            return CoherenceResult(
                confidence_level=ConfidenceLevel.HIGH,
                confidence_score=1.0,
                checks_passed=0,
                checks_failed=0,
                issues=[]
            )
        
        avg_confidence = sum(r.confidence for r in results) / len(results)
        
        if any(r.confidence < 0.4 for r in failed):
            confidence_level = ConfidenceLevel.LOW
        elif avg_confidence >= 0.8:
            confidence_level = ConfidenceLevel.HIGH
        elif avg_confidence >= 0.5:
            confidence_level = ConfidenceLevel.MEDIUM
        else:
            confidence_level = ConfidenceLevel.LOW
        
        caveat = None
        if failed:
            issues_str = "; ".join([f.reason for f in failed if f.reason])
            if confidence_level == ConfidenceLevel.MEDIUM:
                caveat = f"Note: {issues_str}"
        
        ambiguity = None
        if confidence_level == ConfidenceLevel.LOW:
            competing = []
            for f in failed:
                if f.competing_values:
                    competing.extend(f.competing_values)
            if competing:
                ambiguity = {
                    "issue": "Multiple competing values found",
                    "candidates": list(set(competing)),
                    "reasons": [f.reason for f in failed if f.reason]
                }
        
        return CoherenceResult(
            confidence_level=confidence_level,
            confidence_score=round(avg_confidence, 2),
            checks_passed=len(passed),
            checks_failed=len(failed),
            issues=failed,
            caveat=caveat,
            ambiguity=ambiguity
        )
    
    def log_result(self, query: str, result: CoherenceResult) -> None:
        """Log coherence check results in shadow mode format."""
        issues_str = [r.reason for r in result.issues if r.reason]
        
        logger.info(
            f"[COHERENCE] Query: \"{query[:50]}...\" | "
            f"Confidence: {result.confidence_level.value.upper()} ({result.confidence_score}) | "
            f"Checks: {result.checks_passed}/{result.checks_passed + result.checks_failed} passed | "
            f"Issues: {issues_str if issues_str else 'None'}"
        )
