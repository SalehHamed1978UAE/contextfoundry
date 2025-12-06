"""
Shadow Mode Adapter - Runs legacy and constrained extraction in parallel.

When SHADOW mode is enabled, this adapter:
1. Runs the legacy extraction pipeline (writes to entities)
2. Runs the constrained extraction pipeline (writes to entities_v2)
3. Logs comparison metrics for cutover decision

This enables zero-downtime migration validation.
"""

from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
from uuid import UUID

from ..config.feature_flags import (
    get_extraction_mode,
    ExtractionMode,
    is_shadow_mode,
    is_constrained_mode
)
from ..monitoring.shadow_metrics import ShadowMetrics
from ..utils.logger import logger
from .constrained_extractor import ConstrainedExtractor
from .models import ExtractionResult as ConstrainedExtractionResult


class ShadowAdapter:
    """
    Adapter that runs both extraction pipelines in shadow mode.
    
    Provides a unified interface that:
    - In LEGACY mode: Runs only legacy extraction
    - In SHADOW mode: Runs both and logs comparison
    - In CONSTRAINED mode: Runs only constrained extraction
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0
    ):
        """
        Initialize the shadow adapter.
        
        Args:
            model: OpenAI model to use
            temperature: LLM temperature
        """
        self.model = model
        self.temperature = temperature
        self._constrained_extractor: Optional[ConstrainedExtractor] = None
    
    @property
    def constrained_extractor(self) -> ConstrainedExtractor:
        """Get constrained extractor (lazy initialization)."""
        if self._constrained_extractor is None:
            self._constrained_extractor = ConstrainedExtractor(
                model=self.model,
                temperature=self.temperature
            )
        return self._constrained_extractor
    
    def extract_with_mode(
        self,
        text: str,
        document_id: Optional[str] = None,
        legacy_extractor: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Extract entities using the current mode.
        
        Args:
            text: Text to extract from
            document_id: Optional document ID for provenance
            legacy_extractor: Optional legacy EntityExtractor instance
        
        Returns:
            Dict with extraction results and mode info
        """
        mode = get_extraction_mode()
        logger.info(f"ShadowAdapter extracting in mode: {mode.value}")
        
        result = {
            "mode": mode.value,
            "document_id": document_id,
            "extracted_at": datetime.utcnow().isoformat()
        }
        
        if mode == ExtractionMode.LEGACY:
            if legacy_extractor:
                legacy_result = self._run_legacy_extraction(
                    text, legacy_extractor, document_id
                )
                result["legacy"] = legacy_result
                result["entities"] = legacy_result.get("entities", [])
                result["relationships"] = legacy_result.get("relationships", [])
            else:
                result["error"] = "Legacy extractor not provided"
                result["entities"] = []
                result["relationships"] = []
        
        elif mode == ExtractionMode.CONSTRAINED:
            constrained_result = self._run_constrained_extraction(text, document_id)
            result["constrained"] = constrained_result
            result["entities"] = constrained_result.get("entities", [])
            result["relationships"] = constrained_result.get("relationships", [])
            result["rejected_entities"] = constrained_result.get("rejected_entities", [])
            result["rejected_relationships"] = constrained_result.get("rejected_relationships", [])
        
        elif mode == ExtractionMode.SHADOW:
            legacy_result = {}
            if legacy_extractor:
                legacy_result = self._run_legacy_extraction(
                    text, legacy_extractor, document_id
                )
            
            constrained_result = self._run_constrained_extraction(text, document_id)
            
            result["legacy"] = legacy_result
            result["constrained"] = constrained_result
            
            result["entities"] = legacy_result.get("entities", [])
            result["relationships"] = legacy_result.get("relationships", [])
            
            if legacy_result and constrained_result:
                comparison = ShadowMetrics.log_comparison(
                    document_id=document_id or "unknown",
                    old_result=legacy_result,
                    new_result=constrained_result,
                    source_text_length=len(text)
                )
                result["comparison"] = comparison
        
        return result
    
    def extract_constrained_only(
        self,
        text: str,
        document_id: Optional[str] = None
    ) -> Tuple[ConstrainedExtractionResult, ConstrainedExtractionResult]:
        """
        Run only constrained extraction (bypass mode check).
        
        Useful for testing the constrained pipeline directly.
        """
        doc_uuid = UUID(document_id) if document_id else None
        return self.constrained_extractor.extract_all(
            text=text,
            document_id=doc_uuid,
            write_to_shadow=True
        )
    
    def _run_legacy_extraction(
        self,
        text: str,
        extractor: Any,
        document_id: Optional[str]
    ) -> Dict[str, Any]:
        """Run legacy extraction and format result."""
        try:
            entities = extractor.extract_entities(text)
            return {
                "entities": [e.to_dict() if hasattr(e, 'to_dict') else vars(e) for e in entities],
                "relationships": [],
                "success": True
            }
        except Exception as e:
            logger.error(f"Legacy extraction failed: {e}")
            return {
                "entities": [],
                "relationships": [],
                "success": False,
                "error": str(e)
            }
    
    def _run_constrained_extraction(
        self,
        text: str,
        document_id: Optional[str]
    ) -> Dict[str, Any]:
        """Run constrained extraction and format result."""
        try:
            doc_uuid = UUID(document_id) if document_id else None
            entity_result, rel_result = self.constrained_extractor.extract_all(
                text=text,
                document_id=doc_uuid,
                write_to_shadow=True
            )
            
            return {
                "entities": [
                    {
                        "name": e.canonical_name,
                        "entity_type": e.entity_type,
                        "entity_type_id": str(e.entity_type_id) if e.entity_type_id else None,
                        "confidence": e.confidence,
                        "properties": e.properties
                    }
                    for e in entity_result.entities
                ],
                "relationships": [
                    {
                        "relation_type": r.relation_type,
                        "source_name": r.source_name,
                        "target_name": r.target_name,
                        "confidence": r.confidence
                    }
                    for r in rel_result.relationships
                ],
                "rejected_entities": entity_result.rejected_entities,
                "rejected_relationships": rel_result.rejected_relationships,
                "validation_errors": entity_result.validation_errors + rel_result.validation_errors,
                "success": True
            }
        except Exception as e:
            logger.error(f"Constrained extraction failed: {e}")
            return {
                "entities": [],
                "relationships": [],
                "rejected_entities": [],
                "rejected_relationships": [],
                "success": False,
                "error": str(e)
            }
    
    def get_cutover_readiness(self) -> Dict[str, Any]:
        """Get aggregate metrics to determine cutover readiness."""
        return ShadowMetrics.get_aggregate_metrics()
