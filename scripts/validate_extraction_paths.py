"""
Real-world validation: Compare legacy vs constrained extraction paths.

This script runs both extraction paths on actual IT Ops documents and logs:
- Entity count difference
- Types extracted by each path  
- What the new path rejected that old path would have accepted
- Overlap ratio

Run: PYTHONPATH=/home/runner/workspace python scripts/validate_extraction_paths.py
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Tuple
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.context_foundry.extraction.entity_extractor import EntityExtractor, ExtractedEntity
from src.context_foundry.ontology.constrained_extractor import ConstrainedExtractor
from src.context_foundry.ontology.repository import OntologyRepository
from src.context_foundry.ontology.prompt_generator import SchemaPromptGenerator


@dataclass
class ExtractionResult:
    """Result from one extraction path."""
    path_name: str
    document_name: str
    entity_count: int
    entities: List[Dict]
    type_distribution: Dict[str, int]
    execution_time_ms: float
    

@dataclass
class ComparisonMetrics:
    """Comparison metrics between two extraction paths."""
    document_name: str
    legacy_count: int
    constrained_count: int
    count_difference: int
    legacy_types: Set[str]
    constrained_types: Set[str]
    types_only_in_legacy: Set[str]
    types_only_in_constrained: Set[str]
    rejected_entities: List[Dict]
    overlap_ratio: float
    legacy_type_distribution: Dict[str, int]
    constrained_type_distribution: Dict[str, int]


def load_test_documents() -> List[Tuple[str, str]]:
    """Load 5 IT Ops documents for validation."""
    docs = [
        ("test_data/synthetic_docs/meetings/platform_team_standup_oct28.md", "Platform Team Standup"),
        ("test_data/synthetic_docs/slack/incidents_channel_updates.md", "Incidents Channel"),
        ("test_data/synthetic_docs/strategy/cloud_migration_plan.md", "Cloud Migration Plan"),
        ("test_data/synthetic_docs/meetings/vendor_evaluation_call_migrateX.md", "Vendor Evaluation"),
        ("test_data/synthetic_docs/emails/escalation_payment_service_delay.md", "Payment Service Escalation"),
    ]
    
    loaded = []
    for path, name in docs:
        if os.path.exists(path):
            with open(path, 'r') as f:
                content = f.read()
            loaded.append((name, content))
            print(f"  Loaded: {name} ({len(content)} chars)")
        else:
            print(f"  WARNING: {path} not found")
    
    return loaded


def run_legacy_extraction(text: str, doc_name: str) -> ExtractionResult:
    """Run legacy YAML-based extraction."""
    import time
    start = time.time()
    
    extractor = EntityExtractor()
    entities = extractor.extract_from_text(
        text=text,
        document_id=f"validation-{doc_name}",
        chunk_id="chunk-0"
    )
    
    elapsed_ms = (time.time() - start) * 1000
    
    type_dist = Counter(e.entity_type for e in entities)
    
    return ExtractionResult(
        path_name="legacy",
        document_name=doc_name,
        entity_count=len(entities),
        entities=[e.to_dict() for e in entities],
        type_distribution=dict(type_dist),
        execution_time_ms=elapsed_ms
    )


def run_constrained_extraction(text: str, doc_name: str) -> Tuple[ExtractionResult, List[Dict]]:
    """Run constrained DB-backed extraction. Returns result and rejected entities."""
    import time
    from uuid import uuid4
    start = time.time()
    
    repo = OntologyRepository()
    generator = SchemaPromptGenerator(repo)
    extractor = ConstrainedExtractor(
        repository=repo,
        prompt_generator=generator
    )
    
    result = extractor.extract_entities(
        text=text,
        document_id=uuid4()
    )
    
    elapsed_ms = (time.time() - start) * 1000
    
    type_dist = Counter(e.entity_type for e in result.entities)
    
    rejected = [
        {
            "entity_type": r.get("entity_type", "UNKNOWN"),
            "canonical_name": r.get("canonical_name", "UNKNOWN"),
            "reason": r.get("reason", "type_not_in_ontology")
        }
        for r in result.rejected_entities
    ]
    
    return ExtractionResult(
        path_name="constrained",
        document_name=doc_name,
        entity_count=len(result.entities),
        entities=[
            {
                "entity_type": e.entity_type,
                "canonical_name": e.canonical_name,
                "confidence": e.confidence,
                "source_span": e.source_span
            }
            for e in result.entities
        ],
        type_distribution=dict(type_dist),
        execution_time_ms=elapsed_ms
    ), rejected


def compute_overlap(legacy_entities: List[Dict], constrained_entities: List[Dict]) -> float:
    """Compute overlap ratio based on canonical names."""
    legacy_names = {e.get("canonical_name", "").lower() for e in legacy_entities}
    constrained_names = {e.get("canonical_name", "").lower() for e in constrained_entities}
    
    if not legacy_names and not constrained_names:
        return 1.0
    
    intersection = legacy_names & constrained_names
    union = legacy_names | constrained_names
    
    return len(intersection) / len(union) if union else 0.0


def compare_results(legacy: ExtractionResult, constrained: ExtractionResult, rejected: List[Dict]) -> ComparisonMetrics:
    """Compare extraction results from both paths."""
    legacy_types = set(legacy.type_distribution.keys())
    constrained_types = set(constrained.type_distribution.keys())
    
    overlap = compute_overlap(legacy.entities, constrained.entities)
    
    return ComparisonMetrics(
        document_name=legacy.document_name,
        legacy_count=legacy.entity_count,
        constrained_count=constrained.entity_count,
        count_difference=legacy.entity_count - constrained.entity_count,
        legacy_types=legacy_types,
        constrained_types=constrained_types,
        types_only_in_legacy=legacy_types - constrained_types,
        types_only_in_constrained=constrained_types - legacy_types,
        rejected_entities=rejected,
        overlap_ratio=overlap,
        legacy_type_distribution=legacy.type_distribution,
        constrained_type_distribution=constrained.type_distribution
    )


def print_report(all_metrics: List[ComparisonMetrics]):
    """Print formatted validation report."""
    print("\n" + "="*80)
    print("EXTRACTION PATH VALIDATION REPORT")
    print("="*80)
    print(f"Generated: {datetime.now().isoformat()}")
    print(f"Documents tested: {len(all_metrics)}")
    
    total_legacy = sum(m.legacy_count for m in all_metrics)
    total_constrained = sum(m.constrained_count for m in all_metrics)
    total_rejected = sum(len(m.rejected_entities) for m in all_metrics)
    avg_overlap = sum(m.overlap_ratio for m in all_metrics) / len(all_metrics) if all_metrics else 0
    
    print(f"\n{'='*80}")
    print("AGGREGATE METRICS")
    print(f"{'='*80}")
    print(f"Total entities (legacy):      {total_legacy}")
    print(f"Total entities (constrained): {total_constrained}")
    print(f"Difference:                   {total_legacy - total_constrained}")
    print(f"Total rejected:               {total_rejected}")
    print(f"Average overlap ratio:        {avg_overlap:.2%}")
    
    all_legacy_types = Counter()
    all_constrained_types = Counter()
    for m in all_metrics:
        all_legacy_types.update(m.legacy_type_distribution)
        all_constrained_types.update(m.constrained_type_distribution)
    
    print(f"\n{'='*80}")
    print("TYPE DISTRIBUTION - LEGACY PATH")
    print(f"{'='*80}")
    for t, count in sorted(all_legacy_types.items(), key=lambda x: -x[1]):
        print(f"  {t:20} {count:3}")
    
    print(f"\n{'='*80}")
    print("TYPE DISTRIBUTION - CONSTRAINED PATH")
    print(f"{'='*80}")
    for t, count in sorted(all_constrained_types.items(), key=lambda x: -x[1]):
        print(f"  {t:20} {count:3}")
    
    types_only_legacy = set(all_legacy_types.keys()) - set(all_constrained_types.keys())
    types_only_constrained = set(all_constrained_types.keys()) - set(all_legacy_types.keys())
    
    if types_only_legacy:
        print(f"\n{'='*80}")
        print("TYPES ONLY IN LEGACY (not in ontology)")
        print(f"{'='*80}")
        for t in sorted(types_only_legacy):
            print(f"  {t}: {all_legacy_types[t]} occurrences")
    
    if types_only_constrained:
        print(f"\n{'='*80}")
        print("TYPES ONLY IN CONSTRAINED")
        print(f"{'='*80}")
        for t in sorted(types_only_constrained):
            print(f"  {t}: {all_constrained_types[t]} occurrences")
    
    print(f"\n{'='*80}")
    print("REJECTED ENTITIES (would have been accepted by legacy)")
    print(f"{'='*80}")
    all_rejected = []
    for m in all_metrics:
        for r in m.rejected_entities:
            all_rejected.append({**r, "document": m.document_name})
    
    if all_rejected:
        rejected_by_type = Counter(r["entity_type"] for r in all_rejected)
        print(f"By type:")
        for t, count in sorted(rejected_by_type.items(), key=lambda x: -x[1]):
            print(f"  {t:20} {count:3} rejections")
        print(f"\nDetails:")
        for r in all_rejected[:20]:
            print(f"  [{r['document']}] {r['entity_type']}: {r['canonical_name']}")
        if len(all_rejected) > 20:
            print(f"  ... and {len(all_rejected) - 20} more")
    else:
        print("  No rejections - constrained path accepted everything legacy would have")
    
    print(f"\n{'='*80}")
    print("PER-DOCUMENT SUMMARY")
    print(f"{'='*80}")
    for m in all_metrics:
        print(f"\n{m.document_name}:")
        print(f"  Legacy: {m.legacy_count} entities | Constrained: {m.constrained_count} entities")
        print(f"  Overlap: {m.overlap_ratio:.1%} | Rejected: {len(m.rejected_entities)}")
        print(f"  Legacy types: {sorted(m.legacy_types)}")
        print(f"  Constrained types: {sorted(m.constrained_types)}")
    
    print(f"\n{'='*80}")
    print("VALIDATION VERDICT")
    print(f"{'='*80}")
    
    if avg_overlap >= 0.85:
        print("PASS: High overlap ratio (>=85%) - extraction paths are aligned")
    elif avg_overlap >= 0.70:
        print("WARNING: Moderate overlap ratio (70-85%) - review rejected entities")
    else:
        print("FAIL: Low overlap ratio (<70%) - significant divergence between paths")
    
    if total_rejected == 0:
        print("PASS: No entities rejected by constrained path")
    elif total_rejected <= 5:
        print(f"WARNING: {total_rejected} entities rejected - review for legitimacy")
    else:
        print(f"FAIL: {total_rejected} entities rejected - may be missing valid types in ontology")


def save_results(all_metrics: List[ComparisonMetrics], legacy_results: List[ExtractionResult], constrained_results: List[ExtractionResult]):
    """Save detailed results to JSON for further analysis."""
    output_dir = Path("logs/extraction_validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"validation_{timestamp}.json"
    
    def serialize_metrics(m: ComparisonMetrics) -> dict:
        return {
            "document_name": m.document_name,
            "legacy_count": m.legacy_count,
            "constrained_count": m.constrained_count,
            "count_difference": m.count_difference,
            "legacy_types": list(m.legacy_types),
            "constrained_types": list(m.constrained_types),
            "types_only_in_legacy": list(m.types_only_in_legacy),
            "types_only_in_constrained": list(m.types_only_in_constrained),
            "rejected_entities": m.rejected_entities,
            "overlap_ratio": m.overlap_ratio,
            "legacy_type_distribution": m.legacy_type_distribution,
            "constrained_type_distribution": m.constrained_type_distribution
        }
    
    output = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "documents_tested": len(all_metrics),
            "total_legacy_entities": sum(m.legacy_count for m in all_metrics),
            "total_constrained_entities": sum(m.constrained_count for m in all_metrics),
            "total_rejected": sum(len(m.rejected_entities) for m in all_metrics),
            "average_overlap": sum(m.overlap_ratio for m in all_metrics) / len(all_metrics) if all_metrics else 0
        },
        "per_document_metrics": [serialize_metrics(m) for m in all_metrics],
        "legacy_results": [asdict(r) for r in legacy_results],
        "constrained_results": [asdict(r) for r in constrained_results]
    }
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {output_file}")


def main():
    print("="*80)
    print("EXTRACTION PATH VALIDATION")
    print("Comparing: Legacy (YAML) vs Constrained (Database-backed)")
    print("="*80)
    
    print("\n1. Loading test documents...")
    documents = load_test_documents()
    
    if not documents:
        print("ERROR: No documents found!")
        return
    
    print(f"\n2. Running extraction on {len(documents)} documents...")
    
    all_metrics = []
    legacy_results = []
    constrained_results = []
    
    for i, (doc_name, content) in enumerate(documents, 1):
        print(f"\n--- Document {i}/{len(documents)}: {doc_name} ---")
        
        print("  Running legacy extraction...")
        legacy = run_legacy_extraction(content, doc_name)
        print(f"  Legacy: {legacy.entity_count} entities in {legacy.execution_time_ms:.0f}ms")
        
        print("  Running constrained extraction...")
        constrained, rejected = run_constrained_extraction(content, doc_name)
        print(f"  Constrained: {constrained.entity_count} entities in {constrained.execution_time_ms:.0f}ms")
        print(f"  Rejected: {len(rejected)} entities")
        
        metrics = compare_results(legacy, constrained, rejected)
        all_metrics.append(metrics)
        legacy_results.append(legacy)
        constrained_results.append(constrained)
    
    print_report(all_metrics)
    save_results(all_metrics, legacy_results, constrained_results)


if __name__ == "__main__":
    main()
