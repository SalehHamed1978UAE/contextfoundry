"""
Data Gates - The "refuse to hallucinate" implementation.

This is CF's core differentiator. When we don't have the information,
we say so instead of guessing.

Three levels of "I Don't Know":
1. ENTITY_NOT_FOUND - The thing being asked about doesn't exist in our KG
2. NO_RELEVANT_CHUNKS - We have the entity but no documents mention it
3. ANSWER_NOT_GROUNDED - The LLM made up an answer not in the sources

Part of the tri-memory thesis validation.
"""

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DataGateResult(Enum):
    """Result of data gate evaluation."""
    PASS = "pass"                          # Answer is grounded, proceed
    ENTITY_NOT_FOUND = "entity_not_found"  # Query subject not in KG
    NO_RELEVANT_CHUNKS = "no_relevant_chunks"  # Entity exists but no docs
    ANSWER_NOT_GROUNDED = "not_grounded"   # Answer fabricated
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
        r"there\s+(?:is|are)\s+no\s+(?:specific\s+)?(?:information|data|mention)",
        r"(?:i\s+)?couldn't\s+find",
        r"no\s+(?:specific\s+)?(?:information|data)\s+(?:is\s+)?available",
    ]

    # Keywords that suggest the answer is made up
    FABRICATION_INDICATORS = [
        r"typically",
        r"generally",
        r"usually",
        r"in\s+most\s+cases",
        r"common(?:ly)?",
        r"standard\s+(?:practice|procedure)",
        r"(?:it\s+)?(?:is\s+)?(?:often|frequently)",
        r"tends?\s+to",
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

        # Pattern: "of X" at end
        of_match = re.search(
            r"of\s+([A-Z][a-zA-Z\s]+?)(?:\?|$)",
            query, re.IGNORECASE
        )
        if of_match:
            subjects.append(of_match.group(1).strip())

        # Capitalized proper nouns as fallback
        proper_nouns = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query)
        subjects.extend([n for n in proper_nouns if len(n) > 2])

        # Clean and dedupe
        cleaned = []
        for s in subjects:
            s = s.strip()
            if s and s not in cleaned and len(s) > 1:
                cleaned.append(s)

        return cleaned

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
            elif any(word in combined_chunks for word in subject_lower.split() if len(word) > 3):
                found += 0.5  # Partial match

        return found / len(subjects) if subjects else 1.0

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

        return grounded / len(claims) if claims else 0.8

    def _extract_claims(self, answer: str) -> List[str]:
        """Extract factual claims from an answer."""
        claims = []

        # Numbers with context
        number_claims = re.findall(
            r'(\d+(?:\.\d+)?(?:%|\s*(?:million|billion|days?|years?|employees?|customers?|people|members?)))',
            answer, re.IGNORECASE
        )
        claims.extend(number_claims)

        # Dollar amounts
        dollar_claims = re.findall(
            r'(\$[\d,.]+(?:\s*(?:million|billion|M|B))?)',
            answer, re.IGNORECASE
        )
        claims.extend(dollar_claims)

        # Named entities with attributes
        attr_claims = re.findall(
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:is|are|has|have|was|were)\s+([^.!?]{5,40})',
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

        # Check for key terms (words > 4 chars)
        key_terms = [t for t in claim_lower.split() if len(t) > 4]
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
                logger.debug(f"[DATA_GATES] Hedging detected: {pattern}")
                return True

        return False

    def _detect_fabrication(self, answer: str, chunks: List[str]) -> bool:
        """Detect if answer contains likely fabricated content."""
        answer_lower = answer.lower()
        combined_chunks = ' '.join(chunks).lower() if chunks else ""

        fabrication_count = 0

        # Check for fabrication indicators not present in source
        for pattern in self.FABRICATION_INDICATORS:
            if re.search(pattern, answer_lower):
                # Only flag if not in source
                if not re.search(pattern, combined_chunks):
                    fabrication_count += 1

        # If multiple fabrication indicators, likely fabricated
        if fabrication_count >= 2:
            logger.debug(f"[DATA_GATES] Fabrication indicators: {fabrication_count}")
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
        subject_list = ', '.join(subjects[:3]) if subjects else "the requested information"
        return DataGateEvaluation(
            result=DataGateResult.NO_RELEVANT_CHUNKS,
            confidence=0.1,
            should_answer=False,
            alternative_response=(
                f"I found documents but they don't contain information about "
                f"{subject_list}. This information may not be in the available documents."
            ),
            explanation="Retrieved chunks don't mention query subjects",
            evidence={
                "subjects": subjects,
                "chunk_count": len(chunks) if chunks else 0,
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
                "answer_preview": answer[:100] if answer else "",
                "chunk_count": len(chunks) if chunks else 0,
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
            evidence={"answer_preview": answer[:100] if answer else "", "query": query}
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
            evidence={"answer_preview": answer[:100] if answer else "", "query": query}
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
