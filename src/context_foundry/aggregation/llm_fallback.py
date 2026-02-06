from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .fact_classifier import FactRelation


@dataclass
class LLMClassificationResult:
    relation: FactRelation
    confidence: float


def classify_with_llm(
    prompt: str,
    llm_fn: Callable[[str], LLMClassificationResult],
    confidence_threshold: float = 0.75,
) -> Optional[FactRelation]:
    result = llm_fn(prompt)
    if result.confidence >= confidence_threshold:
        return result.relation
    return None
