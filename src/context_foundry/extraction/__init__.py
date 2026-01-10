"""
Entity and Relation Extraction Pipeline for Context Foundry MVP2.
Uses LLM-powered NER and relation extraction with confidence scoring.
"""
from .entity_extractor import EntityExtractor, ExtractedEntity
from .relation_extractor import RelationExtractor, ExtractedRelation
from .extraction_pipeline import ExtractionPipeline
from .staging_loader import StagingLoader, StagingResult
from .duplicate_detector import DuplicateDetector, DuplicateCandidate, DuplicateDetectionResult
from .validation import ExtractionValidator, ValidationSample, ValidationResult, run_validation_report
from .post_processor import ExtractionPostProcessor
from .validator import GapValidator, ExtractionGap, GapSeverity

__all__ = [
    "EntityExtractor", 
    "ExtractedEntity",
    "RelationExtractor", 
    "ExtractedRelation",
    "ExtractionPipeline",
    "StagingLoader",
    "StagingResult",
    "DuplicateDetector",
    "DuplicateCandidate",
    "DuplicateDetectionResult",
    "ExtractionValidator",
    "ValidationSample",
    "ValidationResult",
    "run_validation_report",
    "ExtractionPostProcessor",
    "GapValidator",
    "ExtractionGap",
    "GapSeverity",
]
