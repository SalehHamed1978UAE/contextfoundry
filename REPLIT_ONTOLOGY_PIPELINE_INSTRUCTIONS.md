# Replit Instructions: Enable Ontology-Centric Extraction

**Date:** February 2, 2026
**Goal:** Switch from multi-model extraction to ontology-centric extraction and measure impact

---

## Context

We have TWO extraction pipelines:

| Pipeline | File | Currently Used? |
|----------|------|-----------------|
| **Multi-Model** | `multi_extractor.py` | ✅ YES (default) |
| **Ontology-Centric** | `ontology_centric_pipeline.py` | ❌ NO (unused) |

The Ontology-Centric pipeline has 710 lines of code that:
- Classifies document type
- Loads per-document-type ontology schemas
- Extracts with ontology guidance
- Canonicalizes using embeddings
- Updates reference ontology with new types

**This is Phase 3 Ontology Foundry - it's built but not wired up.**

---

## Task 1: Create Comparison Script

Create `scripts/compare_extraction_pipelines.py`:

```python
#!/usr/bin/env python3
"""
Compare Multi-Model vs Ontology-Centric extraction pipelines.
Runs both on the same documents and measures differences.
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Multi-model pipeline
from src.context_foundry.extraction.multi_extractor import (
    MultiModelExtractor,
    DocumentInfo,
)

# Ontology-centric pipeline
from src.context_foundry.extraction.ontology_centric_pipeline import (
    OntologyCentricPipeline,
    OntologyCentricResult,
)


def get_session():
    database_url = os.environ.get('DATABASE_URL')
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def get_sample_documents(session, tenant_id: str, limit: int = 5) -> List[Dict]:
    """Get sample documents for comparison."""
    result = session.execute(text("""
        SELECT d.id, d.filename, d.mime_type, dc.content
        FROM platform.documents d
        JOIN document_chunks dc ON d.id = dc.document_id
        WHERE d.tenant_id = :tenant_id
        GROUP BY d.id, d.filename, d.mime_type, dc.content
        LIMIT :limit
    """), {'tenant_id': tenant_id, 'limit': limit})

    docs = []
    for row in result:
        docs.append({
            'id': str(row.id),
            'filename': row.filename,
            'content': row.content[:5000] if row.content else '',
        })
    return docs


def run_multi_model(session, tenant_id: str, doc: Dict) -> Dict:
    """Run multi-model extraction on a document."""
    extractor = MultiModelExtractor(session=session, tenant_id=tenant_id)

    doc_info = DocumentInfo(
        document_id=doc['id'],
        filename=doc['filename'],
        content=doc['content'],
    )

    result = extractor.extract_document(doc_info)

    return {
        'pipeline': 'multi_model',
        'entity_count': len(result.entities) if result.entities else 0,
        'relation_count': len(result.relations) if result.relations else 0,
        'entity_types': list(set(e.entity_type for e in result.entities)) if result.entities else [],
    }


def run_ontology_centric(session, tenant_id: str, doc: Dict) -> Dict:
    """Run ontology-centric extraction on a document."""
    pipeline = OntologyCentricPipeline(
        session=session,
        tenant_id=tenant_id,
        auto_stage=False,  # Don't stage - just compare
    )

    result = pipeline.process_document(
        document_id=doc['id'],
        content=doc['content'],
        filename=doc['filename'],
    )

    return {
        'pipeline': 'ontology_centric',
        'document_type': result.document_type,
        'entity_count': len(result.entities),
        'relation_count': len(result.relations),
        'entity_types': list(set(e.entity_type for e in result.entities)),
        'new_entity_types': result.new_entity_types,
        'new_relationship_types': result.new_relationship_types,
    }


def compare_pipelines(tenant_id: str, limit: int = 5):
    """Run comparison between pipelines."""
    session = get_session()

    print(f"Fetching {limit} sample documents from tenant {tenant_id[:8]}...")
    docs = get_sample_documents(session, tenant_id, limit)

    if not docs:
        print("No documents found!")
        return

    print(f"Found {len(docs)} documents. Running comparison...\n")

    results = []

    for i, doc in enumerate(docs):
        print(f"[{i+1}/{len(docs)}] {doc['filename'][:50]}...")

        try:
            multi_result = run_multi_model(session, tenant_id, doc)
            print(f"  Multi-Model: {multi_result['entity_count']} entities, {multi_result['relation_count']} relations")
        except Exception as e:
            print(f"  Multi-Model: ERROR - {e}")
            multi_result = {'pipeline': 'multi_model', 'error': str(e)}

        try:
            onto_result = run_ontology_centric(session, tenant_id, doc)
            print(f"  Ontology:    {onto_result['entity_count']} entities, {onto_result['relation_count']} relations")
            print(f"               Doc type: {onto_result['document_type']}")
        except Exception as e:
            print(f"  Ontology:    ERROR - {e}")
            onto_result = {'pipeline': 'ontology_centric', 'error': str(e)}

        results.append({
            'document': doc['filename'],
            'multi_model': multi_result,
            'ontology_centric': onto_result,
        })
        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    multi_entities = sum(r['multi_model'].get('entity_count', 0) for r in results)
    multi_relations = sum(r['multi_model'].get('relation_count', 0) for r in results)
    onto_entities = sum(r['ontology_centric'].get('entity_count', 0) for r in results)
    onto_relations = sum(r['ontology_centric'].get('relation_count', 0) for r in results)

    print(f"Multi-Model:      {multi_entities} entities, {multi_relations} relations")
    print(f"Ontology-Centric: {onto_entities} entities, {onto_relations} relations")

    # Save results
    output_file = f"comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_file}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--tenant-id', required=True, help='Tenant/vault ID')
    parser.add_argument('--limit', type=int, default=5, help='Number of documents to compare')
    args = parser.parse_args()

    compare_pipelines(args.tenant_id, args.limit)
```

---

## Task 2: Run Comparison Test

```bash
# Run on Nexus vault (5 documents)
python scripts/compare_extraction_pipelines.py \
  --tenant-id "1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91" \
  --limit 5
```

**Expected output:**
- Entity/relation counts from both pipelines
- Document type classification from ontology pipeline
- Any new types discovered

---

## Task 3: If Ontology Pipeline Wins, Make It Default

Modify `scripts/run_vault_extraction.py`:

```python
# Add import at top
from src.context_foundry.extraction.ontology_centric_pipeline import (
    OntologyCentricPipeline,
)

# Add argument
parser.add_argument('--use-ontology', action='store_true',
                    help='Use ontology-centric pipeline instead of multi-model')

# In main extraction loop, check flag:
if args.use_ontology:
    pipeline = OntologyCentricPipeline(
        session=session,
        tenant_id=vault_id,
        auto_stage=True,
    )
    result = pipeline.process_document(doc_id, content, filename)
else:
    # Existing multi-model code
    ...
```

---

## Task 4: Run Full Test Suite with Ontology Pipeline

```bash
# Re-extract with ontology pipeline
python scripts/run_vault_extraction.py \
  --vault-id "1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91" \
  --use-ontology

# Run 100-question test
python -m src.test_runner.runner \
  --vault-id "1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91" \
  --questions "src/test_questions/nexus_100q.json"
```

---

## Success Criteria

| Metric | Multi-Model Baseline | Ontology Target |
|--------|---------------------|-----------------|
| Test Accuracy | 82-84% | ≥84% (no regression) |
| Extraction Time | Baseline | Within 2x |
| Entity Types | Ad-hoc | Schema-constrained |

**Key questions to answer:**
1. Does ontology-centric extraction produce similar entity/relation counts?
2. Does it improve or maintain test accuracy?
3. Does document type classification work correctly?
4. Are new types being discovered and added to ontology?

---

## Reporting

After running comparison, report:

```
PIPELINE COMPARISON RESULTS
===========================
Documents tested: X
Multi-Model: X entities, Y relations
Ontology:    X entities, Y relations

Document Type Detection:
- corporate_report: X docs
- technical_spec: Y docs
- unknown: Z docs

New Types Discovered:
- Entity types: [list]
- Relationship types: [list]

Test Accuracy (if run):
- Multi-Model baseline: XX%
- Ontology pipeline: XX%

Recommendation: [Use ontology / Stay with multi-model / Need more testing]
```

---

## Files to Review

| File | Purpose |
|------|---------|
| `src/context_foundry/extraction/ontology_centric_pipeline.py` | Main pipeline |
| `src/context_foundry/extraction/ontology_manager.py` | Manages ontologies |
| `src/context_foundry/extraction/document_classifier.py` | Classifies doc types |
| `src/context_foundry/extraction/canonicalizer.py` | Embedding-based canonicalization |

---

## Don't Do This

- ❌ Don't delete or break the multi-model pipeline
- ❌ Don't stage results until comparison is done
- ❌ Don't change ontology tables directly
- ❌ Don't run on production vaults without backup
