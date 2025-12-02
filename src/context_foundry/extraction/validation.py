"""
Extraction Validation for Context Foundry MVP2.
Creates validation samples and measures extraction precision/recall.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import os

from .entity_extractor import ExtractedEntity
from .relation_extractor import ExtractedRelation


@dataclass
class ValidationSample:
    """A single validation sample with ground truth."""
    sample_id: str
    text: str
    ground_truth_entities: List[Dict]
    ground_truth_relations: List[Dict]
    extracted_entities: List[ExtractedEntity] = field(default_factory=list)
    extracted_relations: List[ExtractedRelation] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "sample_id": self.sample_id,
            "text": self.text,
            "ground_truth_entities": self.ground_truth_entities,
            "ground_truth_relations": self.ground_truth_relations,
            "extracted_entities": [e.to_dict() for e in self.extracted_entities],
            "extracted_relations": [r.to_dict() for r in self.extracted_relations],
        }


@dataclass
class ValidationMetrics:
    """Precision, recall, and F1 metrics."""
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    
    @property
    def precision(self) -> float:
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)
    
    @property
    def recall(self) -> float:
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)
    
    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)
    
    def to_dict(self) -> Dict:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class ValidationResult:
    """Complete validation result with metrics per entity/relation type."""
    total_samples: int
    entity_metrics: Dict[str, ValidationMetrics] = field(default_factory=dict)
    relation_metrics: Dict[str, ValidationMetrics] = field(default_factory=dict)
    overall_entity_metrics: ValidationMetrics = field(default_factory=ValidationMetrics)
    overall_relation_metrics: ValidationMetrics = field(default_factory=ValidationMetrics)
    sample_results: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "total_samples": self.total_samples,
            "entity_metrics": {k: v.to_dict() for k, v in self.entity_metrics.items()},
            "relation_metrics": {k: v.to_dict() for k, v in self.relation_metrics.items()},
            "overall_entity_metrics": self.overall_entity_metrics.to_dict(),
            "overall_relation_metrics": self.overall_relation_metrics.to_dict(),
            "sample_results": self.sample_results,
        }


def generate_validation_samples() -> List[ValidationSample]:
    """Generate validation samples with ground truth annotations."""
    samples = [
        ValidationSample(
            sample_id="val-001",
            text="""The Payment Gateway Service is a critical microservice owned by the Payments Team. 
It depends on the Payment Database (PostgreSQL) for transaction records and the Redis Cache 
for session management. Sarah Chen is the Tech Lead of the Payments Team.""",
            ground_truth_entities=[
                {"name": "Payment Gateway Service", "type": "SERVICE"},
                {"name": "Payments Team", "type": "TEAM"},
                {"name": "Payment Database", "type": "DATABASE"},
                {"name": "Redis Cache", "type": "COMPONENT"},
                {"name": "Sarah Chen", "type": "PERSON"},
            ],
            ground_truth_relations=[
                {"source": "Payments Team", "target": "Payment Gateway Service", "type": "OWNS"},
                {"source": "Payment Gateway Service", "target": "Payment Database", "type": "DEPENDS_ON"},
                {"source": "Payment Gateway Service", "target": "Redis Cache", "type": "DEPENDS_ON"},
                {"source": "Sarah Chen", "target": "Payments Team", "type": "MEMBER_OF"},
            ],
        ),
        ValidationSample(
            sample_id="val-002",
            text="""INC-2024-042: On March 15, 2024, the Auth Service experienced a major outage 
affecting 50,000 users. The incident was caused by a deadlock in the Auth Database. 
Mike Rodriguez (SRE Team Lead) resolved the issue by restarting the database cluster. 
For future SEV1 incidents affecting authentication, escalate to Director of Engineering.""",
            ground_truth_entities=[
                {"name": "INC-2024-042", "type": "INCIDENT"},
                {"name": "Auth Service", "type": "SERVICE"},
                {"name": "Auth Database", "type": "DATABASE"},
                {"name": "Mike Rodriguez", "type": "PERSON"},
                {"name": "SRE Team", "type": "TEAM"},
                {"name": "Director of Engineering", "type": "PERSON"},
            ],
            ground_truth_relations=[
                {"source": "INC-2024-042", "target": "Auth Service", "type": "AFFECTS"},
                {"source": "INC-2024-042", "target": "Auth Database", "type": "CAUSED_BY"},
                {"source": "Mike Rodriguez", "target": "INC-2024-042", "type": "RESOLVED_BY"},
                {"source": "Mike Rodriguez", "target": "SRE Team", "type": "MEMBER_OF"},
            ],
        ),
        ValidationSample(
            sample_id="val-003",
            text="""The API Gateway routes traffic to downstream services including the Order Service, 
Inventory Service, and Shipping Service. The Platform Team manages the API Gateway and 
the underlying Kubernetes infrastructure. James Wilson is the Platform Team Manager.""",
            ground_truth_entities=[
                {"name": "API Gateway", "type": "SERVICE"},
                {"name": "Order Service", "type": "SERVICE"},
                {"name": "Inventory Service", "type": "SERVICE"},
                {"name": "Shipping Service", "type": "SERVICE"},
                {"name": "Platform Team", "type": "TEAM"},
                {"name": "James Wilson", "type": "PERSON"},
            ],
            ground_truth_relations=[
                {"source": "API Gateway", "target": "Order Service", "type": "DEPENDS_ON"},
                {"source": "API Gateway", "target": "Inventory Service", "type": "DEPENDS_ON"},
                {"source": "API Gateway", "target": "Shipping Service", "type": "DEPENDS_ON"},
                {"source": "Platform Team", "target": "API Gateway", "type": "MANAGES"},
            ],
        ),
        ValidationSample(
            sample_id="val-004",
            text="""The Notification Service sends alerts via email and SMS. It depends on the 
Message Queue (RabbitMQ) for asynchronous processing and the User Preferences Database 
for opt-in settings. The Communications Team owns this service, led by Lisa Park.""",
            ground_truth_entities=[
                {"name": "Notification Service", "type": "SERVICE"},
                {"name": "Message Queue", "type": "COMPONENT"},
                {"name": "User Preferences Database", "type": "DATABASE"},
                {"name": "Communications Team", "type": "TEAM"},
                {"name": "Lisa Park", "type": "PERSON"},
            ],
            ground_truth_relations=[
                {"source": "Notification Service", "target": "Message Queue", "type": "DEPENDS_ON"},
                {"source": "Notification Service", "target": "User Preferences Database", "type": "DEPENDS_ON"},
                {"source": "Communications Team", "target": "Notification Service", "type": "OWNS"},
            ],
        ),
        ValidationSample(
            sample_id="val-005",
            text="""INC-2024-099: The Checkout Service went down due to connection timeout to 
the Payments Database. The incident lasted 45 minutes and affected checkout functionality. 
David Lee from the Payments Team investigated. The root cause was a network partition 
between the service and database.""",
            ground_truth_entities=[
                {"name": "INC-2024-099", "type": "INCIDENT"},
                {"name": "Checkout Service", "type": "SERVICE"},
                {"name": "Payments Database", "type": "DATABASE"},
                {"name": "David Lee", "type": "PERSON"},
                {"name": "Payments Team", "type": "TEAM"},
            ],
            ground_truth_relations=[
                {"source": "INC-2024-099", "target": "Checkout Service", "type": "AFFECTS"},
                {"source": "INC-2024-099", "target": "Payments Database", "type": "CAUSED_BY"},
                {"source": "David Lee", "target": "Payments Team", "type": "MEMBER_OF"},
            ],
        ),
    ]
    return samples


class ExtractionValidator:
    """Validates extraction quality against ground truth."""
    
    def __init__(self, extraction_pipeline):
        """
        Initialize the validator.
        
        Args:
            extraction_pipeline: ExtractionPipeline instance to validate
        """
        self.pipeline = extraction_pipeline
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity/relation name for comparison."""
        return name.lower().strip()
    
    def _match_entity(
        self, 
        extracted: ExtractedEntity, 
        ground_truth: Dict
    ) -> bool:
        """Check if extracted entity matches ground truth."""
        extracted_name = self._normalize_name(extracted.canonical_name)
        gt_name = self._normalize_name(ground_truth["name"])
        
        name_match = (
            extracted_name == gt_name or
            extracted_name in gt_name or
            gt_name in extracted_name
        )
        
        type_match = extracted.entity_type == ground_truth["type"]
        
        return name_match and type_match
    
    def _match_relation(
        self,
        extracted: ExtractedRelation,
        ground_truth: Dict
    ) -> bool:
        """Check if extracted relation matches ground truth."""
        extracted_source = self._normalize_name(extracted.source_name)
        extracted_target = self._normalize_name(extracted.target_name)
        gt_source = self._normalize_name(ground_truth["source"])
        gt_target = self._normalize_name(ground_truth["target"])
        
        source_match = (
            extracted_source == gt_source or
            extracted_source in gt_source or
            gt_source in extracted_source
        )
        target_match = (
            extracted_target == gt_target or
            extracted_target in gt_target or
            gt_target in extracted_target
        )
        
        type_match = extracted.relation_type == ground_truth["type"]
        
        return source_match and target_match and type_match
    
    def validate_sample(self, sample: ValidationSample) -> Dict:
        """
        Validate extraction on a single sample.
        
        Args:
            sample: ValidationSample with ground truth
            
        Returns:
            Dict with entity and relation metrics for this sample
        """
        result = self.pipeline.extract_from_text(
            text=sample.text,
            document_id=sample.sample_id,
            document_title=f"Validation Sample {sample.sample_id}"
        )
        
        sample.extracted_entities = result.entities
        sample.extracted_relations = result.relations
        
        entity_metrics = ValidationMetrics()
        gt_matched = set()
        
        for extracted in result.entities:
            matched = False
            for i, gt in enumerate(sample.ground_truth_entities):
                if i not in gt_matched and self._match_entity(extracted, gt):
                    entity_metrics.true_positives += 1
                    gt_matched.add(i)
                    matched = True
                    break
            if not matched:
                entity_metrics.false_positives += 1
        
        entity_metrics.false_negatives = len(sample.ground_truth_entities) - len(gt_matched)
        
        relation_metrics = ValidationMetrics()
        gt_rel_matched = set()
        
        for extracted in result.relations:
            matched = False
            for i, gt in enumerate(sample.ground_truth_relations):
                if i not in gt_rel_matched and self._match_relation(extracted, gt):
                    relation_metrics.true_positives += 1
                    gt_rel_matched.add(i)
                    matched = True
                    break
            if not matched:
                relation_metrics.false_positives += 1
        
        relation_metrics.false_negatives = len(sample.ground_truth_relations) - len(gt_rel_matched)
        
        return {
            "sample_id": sample.sample_id,
            "entity_metrics": entity_metrics.to_dict(),
            "relation_metrics": relation_metrics.to_dict(),
            "extracted_entities": [e.to_dict() for e in result.entities],
            "extracted_relations": [r.to_dict() for r in result.relations],
            "ground_truth_entities": sample.ground_truth_entities,
            "ground_truth_relations": sample.ground_truth_relations,
        }
    
    def validate_all(
        self, 
        samples: Optional[List[ValidationSample]] = None
    ) -> ValidationResult:
        """
        Run validation on all samples.
        
        Args:
            samples: List of ValidationSample, or None to use default samples
            
        Returns:
            ValidationResult with aggregate metrics
        """
        if samples is None:
            samples = generate_validation_samples()
        
        result = ValidationResult(total_samples=len(samples))
        
        for sample in samples:
            sample_result = self.validate_sample(sample)
            result.sample_results.append(sample_result)
            
            sample_entity = sample_result["entity_metrics"]
            result.overall_entity_metrics.true_positives += sample_entity["true_positives"]
            result.overall_entity_metrics.false_positives += sample_entity["false_positives"]
            result.overall_entity_metrics.false_negatives += sample_entity["false_negatives"]
            
            sample_rel = sample_result["relation_metrics"]
            result.overall_relation_metrics.true_positives += sample_rel["true_positives"]
            result.overall_relation_metrics.false_positives += sample_rel["false_positives"]
            result.overall_relation_metrics.false_negatives += sample_rel["false_negatives"]
        
        return result


def run_validation_report() -> Dict:
    """Run full validation and return formatted report."""
    from .extraction_pipeline import ExtractionPipeline
    
    pipeline = ExtractionPipeline(model='gpt-4o-mini', temperature=0.1)
    validator = ExtractionValidator(pipeline)
    
    print("Running validation on 5 samples...")
    result = validator.validate_all()
    
    report = {
        "summary": {
            "total_samples": result.total_samples,
            "entity_precision": f"{result.overall_entity_metrics.precision:.1%}",
            "entity_recall": f"{result.overall_entity_metrics.recall:.1%}",
            "entity_f1": f"{result.overall_entity_metrics.f1:.1%}",
            "relation_precision": f"{result.overall_relation_metrics.precision:.1%}",
            "relation_recall": f"{result.overall_relation_metrics.recall:.1%}",
            "relation_f1": f"{result.overall_relation_metrics.f1:.1%}",
        },
        "details": result.to_dict(),
    }
    
    print("\n=== VALIDATION REPORT ===")
    print(f"Samples: {result.total_samples}")
    print(f"\nEntity Extraction:")
    print(f"  Precision: {result.overall_entity_metrics.precision:.1%}")
    print(f"  Recall: {result.overall_entity_metrics.recall:.1%}")
    print(f"  F1 Score: {result.overall_entity_metrics.f1:.1%}")
    print(f"\nRelation Extraction:")
    print(f"  Precision: {result.overall_relation_metrics.precision:.1%}")
    print(f"  Recall: {result.overall_relation_metrics.recall:.1%}")
    print(f"  F1 Score: {result.overall_relation_metrics.f1:.1%}")
    
    return report
