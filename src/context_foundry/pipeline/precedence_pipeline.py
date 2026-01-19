"""
Precedence Pipeline - Implements Symbolic > Semantic > Episodic flow.

This is the implementation of the Bible's tri-memory precedence:
1. Symbolic rules are checked FIRST and can override everything
2. Semantic memory (KG) is the primary source of answers
3. Episodic memory (chunks) provides supporting evidence
4. Data Gates validate the final answer

This replaces the current parallel-query approach with a proper hierarchy.

Part of the tri-memory thesis validation.
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
    SYMBOLIC = "symbolic"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    REFUSED = "refused"
    UNKNOWN = "unknown"


@dataclass
class PrecedenceResult:
    """Result from the precedence pipeline."""
    answer: str
    source: AnswerSource
    confidence: float
    explanation: str
    symbolic_override: Optional[SymbolicOverrideResult]
    data_gate_result: Optional[DataGateEvaluation]
    context_bundle: Optional[ContextBundle]

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
        result = pipeline.process(query, semantic_answer, context)

        print(f"Answer: {result.answer}")
        print(f"Source: {result.source}")
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
        semantic_answer: str,
        context: Dict[str, Any],
        bundle: ContextBundle = None
    ) -> PrecedenceResult:
        """
        Process a query through the precedence pipeline.

        Args:
            query: The user's query
            semantic_answer: Answer already generated from semantic memory
            context: Query context (target_entity, entity_types, etc.)
            bundle: Optional context bundle with retrieved data

        Returns:
            PrecedenceResult with answer and metadata
        """
        logger.info(f"[PRECEDENCE] Processing: {query[:50]}...")

        logger.debug("[PRECEDENCE] Step 1: Checking symbolic rules...")

        entity_types = context.get('entity_types', [])
        if bundle and hasattr(bundle, 'focal_entities'):
            for e in bundle.focal_entities:
                if hasattr(e, 'entity_type'):
                    entity_types.append(e.entity_type)
                elif isinstance(e, dict) and 'entity_type' in e:
                    entity_types.append(e['entity_type'])

        symbolic_result = self.symbolic_engine.evaluate(
            query=query,
            semantic_answer=semantic_answer,
            context={
                **context,
                'entity_types': list(set(entity_types)),
            }
        )

        if symbolic_result.should_override:
            logger.info(f"[PRECEDENCE] Symbolic override: {symbolic_result.explanation}")
            return PrecedenceResult(
                answer=symbolic_result.override_answer,
                source=AnswerSource.SYMBOLIC,
                confidence=0.95,
                explanation=f"Answer from symbolic rule: {symbolic_result.explanation}",
                symbolic_override=symbolic_result,
                data_gate_result=None,
                context_bundle=bundle
            )

        logger.debug("[PRECEDENCE] Step 2: Checking data gates...")

        entities_found = []
        chunks_retrieved = []

        if bundle:
            if hasattr(bundle, 'focal_entities'):
                entities_found = bundle.focal_entities
            if hasattr(bundle, 'relevant_chunks'):
                chunks_retrieved = bundle.relevant_chunks
            elif hasattr(bundle, 'episodic_memory'):
                chunks_retrieved = [c.get('content', '') for c in bundle.episodic_memory] if bundle.episodic_memory else []

        gate_result = self.data_gates.evaluate(
            query=query,
            answer=semantic_answer,
            entities_found=entities_found,
            chunks_retrieved=chunks_retrieved,
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

    Args:
        session: Database session
        tenant_id: Tenant ID
        query: The user's query
        current_answer: The answer to validate/override
        bundle: Context bundle with retrieved data
        context: Additional context

    Returns:
        Tuple of (final_answer, source, confidence)
    """
    pipeline = PrecedencePipeline(session, tenant_id)
    result = pipeline.process(
        query=query,
        semantic_answer=current_answer,
        context=context,
        bundle=bundle
    )

    return (result.answer, result.source.value, result.confidence)
