"""
Entity and Relation Extraction Pipeline for Context Foundry.

Context Foundry is a MULTI-DOMAIN knowledge extraction system supporting:
- Venture Capital & Private Equity
- Healthcare & Life Sciences
- Legal & Compliance
- Human Resources & Talent
- Finance & Banking
- Technology & IT Operations
- Real Estate & Property Management
- And any other domain with structured knowledge

Uses LLM-powered NER and relation extraction with confidence scoring.
The system automatically adapts to the domain of uploaded documents.
"""
from .entity_extractor import EntityExtractor, ExtractedEntity
from .relation_extractor import RelationExtractor, ExtractedRelation
from .extraction_pipeline import ExtractionPipeline
from .staging_loader import StagingLoader, StagingResult
from .duplicate_detector import DuplicateDetector, DuplicateCandidate, DuplicateDetectionResult
from .validation import ExtractionValidator, ValidationSample, ValidationResult, run_validation_report
from .post_processor import (
    ExtractionPostProcessor,
    PostProcessorResult,
    RoleNormalizer,
    get_post_processor,
    get_role_normalizer,
)

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
    "PostProcessorResult",
    "RoleNormalizer",
    "get_post_processor",
    "get_role_normalizer",
]
