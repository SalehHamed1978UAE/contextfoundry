"""
Complete Extraction Pipeline

End-to-end pipeline for:
1. Document ingestion (sentence-aware chunking)
2. Entity/relationship extraction (LLM-based)
3. Deduplication and merging
4. Insertion into STAGING lifecycle
5. Cross-document entity resolution

Usage:
    from src.utils.extraction_pipeline import run_extraction_pipeline
    await run_extraction_pipeline("/path/to/document.md")
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, List

from src.db.connection import init_databases, close_databases, db_manager
from src.utils.document_ingestion import DocumentIngestionPipeline
from src.agents.extraction import ExtractionAgent
from src.agents.dedup import DeduplicationAgent


async def run_extraction_pipeline(
    file_path: str,
    document_type: str = "runbook"
) -> Dict[str, Any]:
    """
    Run complete extraction pipeline on a document

    Args:
        file_path: Path to document file
        document_type: Type of document (runbook, incident, etc.)

    Returns:
        Dictionary with pipeline results
    """

    print("\n" + "="*70)
    print("EXTRACTION PIPELINE")
    print("="*70)

    # Initialize databases
    await init_databases()

    try:
        # Step 1: Ingest document
        print(f"\nSTEP 1: Ingesting document...")
        print(f"  File: {Path(file_path).name}")

        ingestion_pipeline = DocumentIngestionPipeline(
            chunk_size=512,
            chunk_overlap=50
        )

        ingested = ingestion_pipeline.ingest_document(
            file_path=file_path,
            document_type=document_type
        )

        print(f"  ✓ Ingested: {ingested['sentence_count']} sentences, {ingested['chunk_count']} chunks")

        # Step 2: Extract entities and relationships from each chunk
        print(f"\nSTEP 2: Extracting entities and relationships...")

        extraction_agent = ExtractionAgent(db_manager)

        all_entities = []
        all_relationships = []

        for chunk in ingested['chunks']:
            extractions = await extraction_agent.extract_from_chunk(
                chunk_text=chunk.text,
                document_id=ingested['document_id'],
                document_type=document_type,
                chunk_index=chunk.chunk_index
            )

            all_entities.extend(extractions['entities'])
            all_relationships.extend(extractions['relationships'])

        raw_entity_count = len(all_entities)
        raw_relationship_count = len(all_relationships)
        print(f"\n  ✓ Raw extracted: {raw_entity_count} entities, {raw_relationship_count} relationships")

        # Step 3: Deduplicate before insertion
        print(f"\nSTEP 3: Deduplicating extractions...")

        dedup_agent = DeduplicationAgent(db_manager)
        all_entities = dedup_agent.dedup_entities(all_entities)
        all_relationships = dedup_agent.dedup_relationships(all_relationships)

        print(f"  ✓ After dedup: {len(all_entities)} entities, {len(all_relationships)} relationships")

        # Step 3b: Validate relationship endpoints
        print(f"\n  Validating relationship endpoints...")
        all_relationships = extraction_agent.validate_relationships_against_entities(
            all_relationships, all_entities
        )

        # Step 4: Insert into STAGING
        print(f"\nSTEP 4: Inserting into STAGING...")

        insertion_result = await extraction_agent.insert_extractions_to_staging(
            entities=all_entities,
            relationships=all_relationships
        )

        print(f"\n  ✓ Inserted: {insertion_result['inserted_entities']} entities, "
              f"{insertion_result['inserted_relationships']} relationships")

        if insertion_result['errors']:
            print(f"  ✗ Errors: {len(insertion_result['errors'])}")

        # Step 5: Database-level dedup (merge with prior extractions)
        print(f"\nSTEP 5: Merging duplicates in STAGING...")

        merge_result = await dedup_agent.merge_staging_duplicates()
        print(f"  ✓ Merged {merge_result['entities_merged']} duplicate entities across {merge_result['duplicate_groups_found']} groups")

        # Step 6: Cross-document resolution
        print(f"\nSTEP 6: Cross-document entity resolution...")

        cross_matches = await dedup_agent.find_cross_document_matches()
        cross_resolution = {"resolved": 0, "errors": []}
        if cross_matches:
            cross_resolution = await dedup_agent.resolve_cross_document_matches(cross_matches)
            print(f"  ✓ Resolved {cross_resolution['resolved']} cross-document matches")
        else:
            print(f"  ✓ No cross-document duplicates found")

        # Step 7: Query STAGING to show results
        print(f"\nSTEP 7: Querying STAGING for results...")

        staging_summary = await get_staging_summary(ingested['document_id'])

        print(f"\n  Entities in STAGING:")
        for entity_type, count in staging_summary['entities_by_type'].items():
            print(f"    {entity_type}: {count}")

        print(f"\n  Relationships in STAGING:")
        for rel_type, count in staging_summary['relationships_by_type'].items():
            print(f"    {rel_type}: {count}")

        print(f"\n" + "="*70)
        print("EXTRACTION PIPELINE COMPLETE")
        print("="*70)

        return {
            "document_id": ingested['document_id'],
            "document_title": ingested['title'],
            "sentences": ingested['sentence_count'],
            "chunks": ingested['chunk_count'],
            "raw_entities": raw_entity_count,
            "raw_relationships": raw_relationship_count,
            "deduped_entities": len(all_entities),
            "deduped_relationships": len(all_relationships),
            "inserted_entities": insertion_result['inserted_entities'],
            "inserted_relationships": insertion_result['inserted_relationships'],
            "db_merges": merge_result['entities_merged'],
            "cross_doc_resolved": cross_resolution['resolved'],
            "errors": insertion_result['errors'] + merge_result['errors'] + cross_resolution['errors'],
            "staging_summary": staging_summary
        }

    finally:
        await close_databases()


async def run_batch_extraction(
    file_paths: List[str],
    document_type: str = "runbook"
) -> Dict[str, Any]:
    """
    Run extraction pipeline on multiple documents sequentially.

    Args:
        file_paths: List of paths to document files
        document_type: Type of documents

    Returns:
        Aggregate results across all documents
    """

    print("\n" + "="*70)
    print(f"BATCH EXTRACTION: {len(file_paths)} documents")
    print("="*70)

    results = []
    total_entities = 0
    total_relationships = 0
    total_errors = []

    for i, file_path in enumerate(file_paths):
        print(f"\n{'─'*70}")
        print(f"Document {i+1}/{len(file_paths)}: {Path(file_path).name}")
        print(f"{'─'*70}")

        try:
            result = await run_extraction_pipeline(file_path, document_type)
            results.append(result)
            total_entities += result['inserted_entities']
            total_relationships += result['inserted_relationships']
            total_errors.extend(result['errors'])
        except Exception as e:
            print(f"  ✗ Failed: {str(e)}")
            total_errors.append(f"Document {Path(file_path).name}: {str(e)}")

    print(f"\n" + "="*70)
    print("BATCH EXTRACTION SUMMARY")
    print("="*70)
    print(f"Documents processed: {len(results)}/{len(file_paths)}")
    print(f"Total entities inserted: {total_entities}")
    print(f"Total relationships inserted: {total_relationships}")
    if total_errors:
        print(f"Total errors: {len(total_errors)}")

    return {
        "documents_processed": len(results),
        "documents_failed": len(file_paths) - len(results),
        "total_entities": total_entities,
        "total_relationships": total_relationships,
        "total_errors": total_errors,
        "results": results
    }


async def get_staging_summary(document_id: str) -> Dict[str, Any]:
    """Get summary of entities and relationships in STAGING for a document"""

    async with db_manager.get_postgres_connection() as conn:
        # Count entities by type
        entity_rows = await conn.fetch("""
            SELECT entity_type, COUNT(*) as count
            FROM graph_lifecycle
            WHERE source_document_id = $1
            AND lifecycle_state = 'STAGING'
            GROUP BY entity_type
        """, document_id)

        entities_by_type = {row['entity_type']: row['count'] for row in entity_rows}

        # Count relationships by type
        rel_rows = await conn.fetch("""
            SELECT rm.relationship_type, COUNT(*) as count
            FROM relationship_metadata rm
            WHERE rm.source_document_id = $1
            AND rm.lifecycle_state = 'STAGING'
            GROUP BY rm.relationship_type
        """, document_id)

        relationships_by_type = {row['relationship_type']: row['count'] for row in rel_rows}

        # Get sample entities with canonical name
        sample_entities = await conn.fetch("""
            SELECT entity_type,
                   COALESCE(extracted_text, source_sentence) AS canonical_name,
                   confidence
            FROM graph_lifecycle
            WHERE source_document_id = $1
            AND lifecycle_state = 'STAGING'
            ORDER BY confidence DESC
            LIMIT 10
        """, document_id)

        return {
            "entities_by_type": entities_by_type,
            "relationships_by_type": relationships_by_type,
            "sample_entities": [
                {
                    "type": row['entity_type'],
                    "name": row['canonical_name'],
                    "confidence": float(row['confidence'])
                }
                for row in sample_entities
            ]
        }


async def main():
    """CLI entry point"""
    import sys
    import glob

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m src.utils.extraction_pipeline <file_path> [document_type]")
        print("  python -m src.utils.extraction_pipeline --batch <directory> [document_type]")
        print("\nExamples:")
        print("  python -m src.utils.extraction_pipeline test_data/runbook.md runbook")
        print("  python -m src.utils.extraction_pipeline --batch test_data/")
        sys.exit(1)

    if sys.argv[1] == "--batch":
        directory = sys.argv[2] if len(sys.argv) > 2 else "test_data/"
        document_type = sys.argv[3] if len(sys.argv) > 3 else "runbook"

        # Find all markdown files
        file_paths = sorted(glob.glob(f"{directory}/*.md"))
        if not file_paths:
            print(f"No .md files found in {directory}")
            sys.exit(1)

        print(f"Found {len(file_paths)} documents:")
        for fp in file_paths:
            print(f"  - {Path(fp).name}")

        result = await run_batch_extraction(file_paths, document_type)
    else:
        file_path = sys.argv[1]
        document_type = sys.argv[2] if len(sys.argv) > 2 else "runbook"

        result = await run_extraction_pipeline(file_path, document_type)

        print("\n" + "="*70)
        print("PIPELINE SUMMARY")
        print("="*70)
        print(f"Document: {result['document_title']}")
        print(f"Sentences: {result['sentences']}")
        print(f"Chunks: {result['chunks']}")
        print(f"Raw extracted: {result['raw_entities']} entities, {result['raw_relationships']} relationships")
        print(f"After dedup: {result['deduped_entities']} entities, {result['deduped_relationships']} relationships")
        print(f"Inserted: {result['inserted_entities']} entities, {result['inserted_relationships']} relationships")
        print(f"DB merges: {result['db_merges']}")
        print(f"Cross-doc resolved: {result['cross_doc_resolved']}")

        if result['errors']:
            print(f"\nErrors: {len(result['errors'])}")
            for error in result['errors'][:5]:
                print(f"  - {error}")

        print(f"\nTop entities in STAGING (by confidence):")
        for entity in result['staging_summary']['sample_entities']:
            print(f"  - {entity['name']} ({entity['type']}, confidence={entity['confidence']:.2f})")

        print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
