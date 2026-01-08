"""
AnswerFormatter - Composes user-visible aggregation responses.

Per v1.3 spec §8, formats responses with:
- Prominent number (bold)
- Definition used
- Explicit language for bounds ("at least N", "between N and M")
- Confidence label + rationale
- Drill-down handle
"""

import logging
from typing import Any, Dict, Optional

from .models import (
    CAT,
    AggregationResult,
    ResultKind,
    SufficiencyDecision,
    EvidenceEnvelope,
    BoundedCount,
)
from .executor import RawAggregationResult

logger = logging.getLogger(__name__)


class AnswerFormatter:
    """
    Formats aggregation results for user consumption.
    """
    
    # Confidence label thresholds
    CONFIDENCE_LABELS = [
        (0.85, "High"),
        (0.65, "Medium"),
        (0.45, "Low"),
        (0.0, "Very Low"),
    ]
    
    def format(
        self,
        cat: CAT,
        raw_result: RawAggregationResult,
        sufficiency: SufficiencyDecision,
        evidence: EvidenceEnvelope,
        question: str,
    ) -> AggregationResult:
        """
        Format raw result into user-facing AggregationResult.
        """
        # Determine unit from user's question, not CAT entity type
        unit = self._infer_unit_from_question(question, cat)
        
        # Get value or bounds
        value = None
        bounds = sufficiency.bounds
        
        if sufficiency.result_kind == ResultKind.EXACT:
            value = raw_result.value
        elif sufficiency.result_kind == ResultKind.LOWER_BOUND:
            value = raw_result.value
        elif sufficiency.result_kind == ResultKind.RANGE:
            value = sufficiency.bounds.expected if sufficiency.bounds else raw_result.value
        
        # Build definition dict
        definition = self._build_definition(cat)
        
        # Build citations from evidence
        citations = self._build_citations(evidence)
        
        return AggregationResult(
            result_kind=sufficiency.result_kind,
            value=value,
            bounds=bounds,
            unit=unit,
            confidence=sufficiency.confidence,
            confidence_label=self._get_confidence_label(sufficiency.confidence),
            confidence_components=sufficiency.confidence_components,
            definition=definition,
            assumptions=sufficiency.assumptions,
            evidence_envelope=evidence,
            citations=citations,
            cat=cat,
            raw_query=question,
            counted_entities=raw_result.counted_entities if raw_result.counted_entities else [],
        )
    
    def format_display_text(self, result: AggregationResult) -> str:
        """
        Generate human-readable display text.
        
        Examples:
        - EXACT: "4 jobs"
        - LOWER_BOUND: "At least 4 jobs"
        - RANGE: "Between 4 and 7 jobs"
        - INSUFFICIENT: "Cannot determine count"
        """
        unit = result.unit or "items"
        
        if result.result_kind == ResultKind.EXACT:
            return f"**{result.value}** {unit}"
        
        elif result.result_kind == ResultKind.LOWER_BOUND:
            lower = result.bounds.lower if result.bounds else result.value
            return f"**At least {lower}** {unit}"
        
        elif result.result_kind == ResultKind.RANGE:
            if result.bounds:
                return f"**Between {result.bounds.lower} and {result.bounds.upper}** {unit}"
            return f"**~{result.value}** {unit} (estimate)"
        
        else:
            return "Cannot determine count"
    
    def format_full_response(self, result: AggregationResult) -> Dict[str, Any]:
        """
        Generate full API response per §8.1.
        """
        return {
            "answer": self._compose_answer_text(result),
            "result": {
                "kind": result.result_kind.value,
                "value": result.value,
                "bounds": {
                    "lower": result.bounds.lower if result.bounds else None,
                    "upper": result.bounds.upper if result.bounds else None,
                    "expected": result.bounds.expected if result.bounds else None,
                    "method": result.bounds.method if result.bounds else None,
                } if result.bounds else None,
                "unit": result.unit,
            },
            "confidence": {
                "score": round(result.confidence, 2),
                "label": result.confidence_label,
                "components": {
                    "semantic_clarity": round(result.confidence_components.semantic_clarity, 2),
                    "coverage": round(result.confidence_components.coverage, 2),
                    "conflict_penalty": round(result.confidence_components.conflict_penalty, 2),
                    "closure_factor": round(result.confidence_components.closure_factor, 2),
                } if result.confidence_components else None,
            },
            "definition": result.definition,
            "assumptions": result.assumptions,
            "citations": result.citations,
            "drilldown": {
                "rowset_handle": result.evidence_envelope.rowset_handle if result.evidence_envelope else None,
                "sample_ids": result.evidence_envelope.sample_ids if result.evidence_envelope else [],
            },
            "alternatives": result.alternatives,
        }
    
    def _compose_answer_text(self, result: AggregationResult) -> str:
        """Compose natural language answer text."""
        display = self.format_display_text(result)
        
        if result.result_kind == ResultKind.INSUFFICIENT:
            return (
                f"I cannot provide a reliable count. "
                f"Reason: {result.assumptions[0] if result.assumptions else 'Insufficient data'}."
            )
        
        # Build definition clause
        if result.definition:
            grouping = result.definition.get("grouping_key", [])
            if grouping:
                def_clause = f" (counted as distinct {', '.join(grouping)})"
            else:
                def_clause = ""
        else:
            def_clause = ""
        
        return f"{display}{def_clause}."
    
    def _infer_unit_from_question(self, question: str, cat: CAT) -> str:
        """Infer unit label from user's question subject phrase."""
        import re
        
        # Extract subject from common aggregation patterns
        # "how many X" -> X, "count of X" -> X, "number of X" -> X
        patterns = [
            r'how many\s+(\w+)',
            r'count\s+(?:of\s+)?(\w+)',
            r'number\s+of\s+(\w+)',
            r'total\s+(\w+)',
        ]
        
        question_lower = question.lower()
        for pattern in patterns:
            match = re.search(pattern, question_lower)
            if match:
                subject = match.group(1)
                # Ensure it's plural
                if not subject.endswith('s'):
                    subject += 's'
                return subject
        
        # Fallback to CAT entity type if pattern extraction fails
        if cat.target.entity_type:
            entity = cat.target.entity_type.lower()
            if not entity.endswith("s"):
                entity += "s"
            return entity
        
        if cat.target.relationship_type:
            return cat.target.relationship_type.lower().replace("_", " ") + "s"
        
        return "items"
    
    def _build_definition(self, cat: CAT) -> Dict[str, Any]:
        """Build definition dict from CAT."""
        return {
            "concept_key": cat.target.entity_type or cat.target.relationship_type,
            "grouping_key": cat.aggregation.grouping_key,
            "filters": [f"{f.path} {f.op} {f.value}" for f in cat.filters if f.path],
            "closure_policy": cat.closure_policy.value,
            "time_window": {
                "start": str(cat.time.start) if cat.time and cat.time.start else None,
                "end": str(cat.time.end) if cat.time and cat.time.end else None,
            } if cat.time else None,
        }
    
    def _build_citations(self, evidence: EvidenceEnvelope) -> list:
        """Build citation list from evidence."""
        citations = []
        
        for source_id in evidence.source_ids[:5]:  # Limit citations
            citations.append({
                "evidence_id": source_id,
                "title": f"Source {source_id[:8]}...",
            })
        
        return citations
    
    def _get_confidence_label(self, confidence: float) -> str:
        """Get human-readable confidence label."""
        for threshold, label in self.CONFIDENCE_LABELS:
            if confidence >= threshold:
                return label
        return "Unknown"
