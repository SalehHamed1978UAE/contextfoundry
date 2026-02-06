from context_foundry.aggregation.llm_fallback import classify_with_llm, LLMClassificationResult
from context_foundry.aggregation.fact_classifier import FactRelation


def test_llm_fallback_threshold():
    def fake_llm(_prompt: str):
        return LLMClassificationResult(relation=FactRelation.CONFLICT, confidence=0.8)

    assert classify_with_llm("x", fake_llm) == FactRelation.CONFLICT

    def low_conf(_prompt: str):
        return LLMClassificationResult(relation=FactRelation.CONFLICT, confidence=0.5)

    assert classify_with_llm("x", low_conf) is None
