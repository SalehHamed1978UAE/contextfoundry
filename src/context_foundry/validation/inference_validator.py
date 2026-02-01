"""
Inference Validation Layer - LLM-based answer verification.

This implements the "verification loop" concept:
1. Extract answer from knowledge base with provenance
2. Ask LLM: "Does the evidence support this answer to this question?"
3. If no: "What should we be looking for instead?"
4. Mark uncertain inferences for human review

This is a SYSTEMATIC solution that works across any corpus without
hardcoding entity names or patterns.

Why this matters (Q16 example):
- Query: "Who does Nexus have a solid-state battery JV with?"
- Extracted answer: "NextGen" (wrong - it's mentioned in the same chunk)
- Evidence: Contains both NextGen and Toyota Motor Corporation
- Without validation: Returns "NextGen" (incorrect)
- With validation: LLM checks if "NextGen" is actually the solid-state battery partner
- LLM finds: "No, Toyota Motor Corporation is the solid-state battery JV partner"
- Returns correct answer with validation metadata
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Result of inference validation."""
    CONFIRMED = "confirmed"           # Evidence strongly supports answer
    CORRECTED = "corrected"           # Evidence suggests different answer
    UNCERTAIN = "uncertain"           # Evidence insufficient to validate
    CONTRADICTED = "contradicted"     # Evidence contradicts answer


@dataclass
class InferenceValidation:
    """Result of validating an inference."""
    result: ValidationResult
    original_answer: str
    validated_answer: str
    confidence: float
    explanation: str
    correction_reason: Optional[str] = None
    suggested_search: Optional[str] = None  # "What should we look for?"
    evidence_quality: float = 0.0
    needs_human_review: bool = False


class InferenceValidator:
    """
    Validates extracted answers against their evidence.

    This is the core of the verification loop:
    1. Takes an answer and its evidence
    2. Asks LLM if the evidence supports the answer
    3. If not, asks what the correct answer should be
    4. Returns validated result with confidence

    This replaces hardcoded patterns with systematic LLM validation.
    """

    # Validation prompt template
    VALIDATION_PROMPT = """You are validating whether an extracted answer correctly answers a question based on the provided evidence.

QUESTION: {question}

EXTRACTED ANSWER: {answer}

EVIDENCE (from knowledge base):
{evidence}

TASK: Determine if the evidence supports the extracted answer.

Consider:
1. Does the evidence actually say "{answer}" is the answer to "{question}"?
2. Could the extracted answer be from a different context mentioned in the same evidence?
3. Is there a more accurate answer in the evidence?

Respond in this EXACT format:
VALIDATION: [CONFIRMED|CORRECTED|UNCERTAIN|CONTRADICTED]
CONFIDENCE: [0.0-1.0]
CORRECT_ANSWER: [the actual answer from evidence, or same as extracted if confirmed]
EXPLANATION: [brief explanation of your reasoning]
LOOK_FOR: [if uncertain/contradicted, what specific information would help]
"""

    def __init__(self, llm_client=None):
        """
        Initialize validator.

        Args:
            llm_client: LLM client for validation calls. If None, uses default.
        """
        self.llm_client = llm_client
        self._validation_cache = {}  # Cache to avoid repeated validations

    def validate(
        self,
        question: str,
        answer: str,
        evidence: List[Dict[str, Any]],
        context: Optional[Dict] = None
    ) -> InferenceValidation:
        """
        Validate an answer against its evidence.

        Args:
            question: The original question
            answer: The extracted/generated answer
            evidence: List of evidence chunks (dicts with 'content' or 'text' keys)
            context: Optional additional context (entity types, etc.)

        Returns:
            InferenceValidation with result and corrected answer if needed
        """
        # Format evidence for the prompt
        evidence_text = self._format_evidence(evidence)

        # Skip validation for empty or trivial cases
        if not answer or not evidence_text:
            return InferenceValidation(
                result=ValidationResult.UNCERTAIN,
                original_answer=answer,
                validated_answer=answer,
                confidence=0.3,
                explanation="Insufficient evidence for validation",
                needs_human_review=True
            )

        # Check cache
        cache_key = f"{question}::{answer}::{hash(evidence_text[:500])}"
        if cache_key in self._validation_cache:
            return self._validation_cache[cache_key]

        # Build and execute validation prompt
        prompt = self.VALIDATION_PROMPT.format(
            question=question,
            answer=answer,
            evidence=evidence_text[:4000]  # Limit evidence length
        )

        try:
            response = self._call_llm(prompt)
            validation = self._parse_validation_response(response, answer)

            # Cache result
            self._validation_cache[cache_key] = validation

            logger.info(f"[INFERENCE_VALIDATOR] {validation.result.value}: "
                       f"'{answer}' -> '{validation.validated_answer}' "
                       f"(confidence: {validation.confidence:.2f})")

            return validation

        except Exception as e:
            logger.error(f"[INFERENCE_VALIDATOR] Validation failed: {e}")
            return InferenceValidation(
                result=ValidationResult.UNCERTAIN,
                original_answer=answer,
                validated_answer=answer,
                confidence=0.5,
                explanation=f"Validation error: {str(e)}",
                needs_human_review=True
            )

    def _format_evidence(self, evidence: List[Dict[str, Any]]) -> str:
        """Format evidence chunks into readable text."""
        formatted = []
        for i, chunk in enumerate(evidence[:5], 1):  # Limit to 5 chunks
            content = chunk.get('content') or chunk.get('text') or chunk.get('chunk_text', '')
            source = chunk.get('source') or chunk.get('doc_name', 'Unknown source')
            formatted.append(f"[Evidence {i} - {source}]\n{content}")
        return "\n\n".join(formatted)

    def _call_llm(self, prompt: str) -> str:
        """Call LLM for validation."""
        if self.llm_client:
            return self.llm_client.complete(prompt)

        # Use default Claude client
        try:
            from anthropic import Anthropic
            client = Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",  # Fast model for validation
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _parse_validation_response(self, response: str, original_answer: str) -> InferenceValidation:
        """Parse LLM validation response into structured result."""
        # Default values
        result = ValidationResult.UNCERTAIN
        confidence = 0.5
        validated_answer = original_answer
        explanation = "Could not parse validation response"
        look_for = None

        # Parse VALIDATION field
        validation_match = re.search(r'VALIDATION:\s*(\w+)', response, re.IGNORECASE)
        if validation_match:
            val_str = validation_match.group(1).upper()
            if val_str == "CONFIRMED":
                result = ValidationResult.CONFIRMED
            elif val_str == "CORRECTED":
                result = ValidationResult.CORRECTED
            elif val_str == "CONTRADICTED":
                result = ValidationResult.CONTRADICTED
            else:
                result = ValidationResult.UNCERTAIN

        # Parse CONFIDENCE field
        conf_match = re.search(r'CONFIDENCE:\s*([\d.]+)', response, re.IGNORECASE)
        if conf_match:
            try:
                confidence = float(conf_match.group(1))
                confidence = min(1.0, max(0.0, confidence))
            except ValueError:
                pass

        # Parse CORRECT_ANSWER field
        answer_match = re.search(r'CORRECT_ANSWER:\s*(.+?)(?:\n|$)', response, re.IGNORECASE)
        if answer_match:
            validated_answer = answer_match.group(1).strip()

        # Parse EXPLANATION field
        exp_match = re.search(r'EXPLANATION:\s*(.+?)(?:\n|LOOK_FOR:|$)', response, re.IGNORECASE | re.DOTALL)
        if exp_match:
            explanation = exp_match.group(1).strip()

        # Parse LOOK_FOR field
        look_match = re.search(r'LOOK_FOR:\s*(.+?)(?:\n|$)', response, re.IGNORECASE)
        if look_match:
            look_for = look_match.group(1).strip()

        return InferenceValidation(
            result=result,
            original_answer=original_answer,
            validated_answer=validated_answer,
            confidence=confidence,
            explanation=explanation,
            correction_reason=explanation if result == ValidationResult.CORRECTED else None,
            suggested_search=look_for,
            evidence_quality=confidence,
            needs_human_review=(result in [ValidationResult.UNCERTAIN, ValidationResult.CONTRADICTED])
        )


def validate_inference(
    question: str,
    answer: str,
    evidence: List[Dict],
    context: Optional[Dict] = None
) -> InferenceValidation:
    """
    Convenience function to validate an inference.

    Usage:
        validation = validate_inference(
            question="Who does Nexus partner with for solid-state batteries?",
            answer="NextGen",
            evidence=[{"content": "Toyota Motor Corporation joint venture..."}]
        )

        if validation.result == ValidationResult.CORRECTED:
            answer = validation.validated_answer  # "Toyota Motor Corporation"
    """
    validator = InferenceValidator()
    return validator.validate(question, answer, evidence, context)
