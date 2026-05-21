"""
CLI tool for Context Foundry operations

Usage:
    python -m src.cli load-data             # Load walking skeleton data
    python -m src.cli load-scaled-data      # Load scaled MVP 2 data
    python -m src.cli embed-documents       # Embed walking skeleton documents
    python -m src.cli embed-scaled-docs     # Embed scaled documents
    python -m src.cli promote-all           # Promote all STAGING to TRUSTED
    python -m src.cli promote-evidence      # Evidence-based promotion (stricter)
    python -m src.cli extract <file>        # Extract entities from a document
    python -m src.cli extract-all           # Extract from all test_data/ documents
    python -m src.cli dedup                 # Run dedup on STAGING entities
    python -m src.cli stats                 # Show system statistics
    python -m src.cli clear-data            # Clear all data (WARNING: destructive)
"""

import asyncio
import json
import sys
from pathlib import Path

from src.db.connection import init_databases, close_databases, db_manager
from src.agents.graph_loader import GraphLoaderAgent
from src.agents.gardener import GardenerAgent
from src.utils.embeddings import EmbeddingService, DocumentEmbedder


async def load_walking_skeleton():
    """Load walking skeleton data into the system"""

    print("\n" + "="*60)
    print("Loading Walking Skeleton Data")
    print("="*60 + "\n")

    await init_databases()

    try:
        # Load data files
        data_dir = Path("data")

        with open(data_dir / "entities.json") as f:
            entities = json.load(f)

        with open(data_dir / "relationships.json") as f:
            relationships = json.load(f)

        with open(data_dir / "rules.json") as f:
            rules = json.load(f)

        # Initialize agents
        loader = GraphLoaderAgent(db_manager)

        # Load entities
        print("Loading entities...")
        entity_result = await loader.load_entities(entities)
        print(f"✓ Loaded {entity_result['loaded_count']} entities")
        if entity_result['errors']:
            print(f"  Errors: {len(entity_result['errors'])}")
            for error in entity_result['errors'][:3]:
                print(f"    - {error}")

        # Load relationships
        print("\nLoading relationships...")
        rel_result = await loader.load_relationships(relationships)
        print(f"✓ Loaded {rel_result['loaded_count']} relationships")
        if rel_result['errors']:
            print(f"  Errors: {len(rel_result['errors'])}")
            for error in rel_result['errors'][:3]:
                print(f"    - {error}")

        # Load rules
        print("\nLoading symbolic rules...")
        rule_result = await loader.load_symbolic_rules(rules)
        print(f"✓ Loaded {rule_result['loaded_count']} rules")
        if rule_result['errors']:
            print(f"  Errors: {len(rule_result['errors'])}")

        # Show stats
        print("\n" + "-"*60)
        stats = await loader.get_stats()
        print("System Statistics:")
        print(f"  Entities: {stats['entities']}")
        print(f"  Relationships: {stats['relationships']}")
        print(f"  Rules: {stats['rules']}")
        print("-"*60 + "\n")

    finally:
        await close_databases()


async def promote_all_to_trusted():
    """Promote all STAGING entities to TRUSTED"""

    print("\n" + "="*60)
    print("Promoting All Entities to TRUSTED")
    print("="*60 + "\n")

    await init_databases()

    try:
        gardener = GardenerAgent(db_manager)

        result = await gardener.promote_all_staging()

        print(f"✓ Promoted {result['promoted_count']} entities")
        print(f"✓ Promoted {result['relationships_promoted']} relationships")

        if result.get('errors'):
            print(f"\n✗ Errors: {len(result['errors'])}")
            for error in result['errors'][:5]:
                print(f"    - {error}")

    finally:
        await close_databases()


async def show_stats():
    """Show system statistics"""

    print("\n" + "="*60)
    print("Context Foundry Statistics")
    print("="*60 + "\n")

    await init_databases()

    try:
        loader = GraphLoaderAgent(db_manager)
        stats = await loader.get_stats()

        print("Entities by Lifecycle State:")
        for state, count in stats['entities'].items():
            print(f"  {state}: {count}")

        print(f"\nRelationships: {stats['relationships']}")
        print(f"Symbolic Rules: {stats['rules']}")
        print()

    finally:
        await close_databases()


async def load_scaled_data():
    """Load scaled MVP 2 data into the system"""

    print("\n" + "="*60)
    print("Loading Scaled MVP 2 Data")
    print("="*60 + "\n")

    await init_databases()

    try:
        # Load data files
        data_dir = Path("data/scaled")

        with open(data_dir / "entities.json") as f:
            entities = json.load(f)

        with open(data_dir / "relationships.json") as f:
            relationships = json.load(f)

        with open(data_dir / "rules.json") as f:
            rules = json.load(f)

        # Initialize agents
        loader = GraphLoaderAgent(db_manager)

        # Load entities
        print("Loading entities...")
        entity_result = await loader.load_entities(entities)
        print(f"✓ Loaded {entity_result['loaded_count']} entities")
        if entity_result['errors']:
            print(f"  Errors: {len(entity_result['errors'])}")
            for error in entity_result['errors'][:3]:
                print(f"    - {error}")

        # Load relationships
        print("\nLoading relationships...")
        rel_result = await loader.load_relationships(relationships)
        print(f"✓ Loaded {rel_result['loaded_count']} relationships")
        if rel_result['errors']:
            print(f"  Errors: {len(rel_result['errors'])}")
            for error in rel_result['errors'][:3]:
                print(f"    - {error}")

        # Load rules
        print("\nLoading symbolic rules...")
        rule_result = await loader.load_symbolic_rules(rules)
        print(f"✓ Loaded {rule_result['loaded_count']} rules")
        if rule_result['errors']:
            print(f"  Errors: {len(rule_result['errors'])}")

        # Show stats
        print("\n" + "-"*60)
        stats = await loader.get_stats()
        print("System Statistics:")
        print(f"  Entities: {stats['entities']}")
        print(f"  Relationships: {stats['relationships']}")
        print(f"  Rules: {stats['rules']}")
        print("-"*60 + "\n")

    finally:
        await close_databases()


async def embed_documents():
    """Embed all documents from walking skeleton data"""

    print("\n" + "="*60)
    print("Embedding Documents")
    print("="*60 + "\n")

    await init_databases()

    try:
        # Load documents
        data_dir = Path("data")
        with open(data_dir / "documents.json") as f:
            documents = json.load(f)

        # Initialize embedding service and embedder
        print("Initializing embedding service...")
        embedding_service = EmbeddingService(use_ollama=False)  # Use local for reliability
        embedder = DocumentEmbedder(db_manager, embedding_service)

        # Embed all documents
        print(f"\nEmbedding {len(documents)} documents...\n")
        result = await embedder.embed_all_documents(documents)

        print("\n" + "-"*60)
        print(f"✓ Processed {result['documents_processed']} documents")
        print(f"✓ Created {result['total_chunks']} chunks")
        print(f"✓ Stored {result['total_embeddings']} embeddings")
        print("-"*60 + "\n")

    finally:
        await close_databases()


async def embed_scaled_documents():
    """Embed all documents from scaled MVP 2 data"""

    print("\n" + "="*60)
    print("Embedding Scaled Documents")
    print("="*60 + "\n")

    await init_databases()

    try:
        # Load documents
        data_dir = Path("data/scaled")
        with open(data_dir / "documents.json") as f:
            documents = json.load(f)

        # Initialize embedding service and embedder
        print("Initializing embedding service...")
        embedding_service = EmbeddingService(use_ollama=False)  # Use local for reliability
        embedder = DocumentEmbedder(db_manager, embedding_service)

        # Embed all documents
        print(f"\nEmbedding {len(documents)} documents...\n")
        result = await embedder.embed_all_documents(documents)

        print("\n" + "-"*60)
        print(f"✓ Processed {result['documents_processed']} documents")
        print(f"✓ Created {result['total_chunks']} chunks")
        print(f"✓ Stored {result['total_embeddings']} embeddings")
        print("-"*60 + "\n")

    finally:
        await close_databases()


async def clear_all_data():
    """Clear all data from the system (WARNING: destructive)"""

    print("\n" + "="*60)
    print("WARNING: Clear All Data")
    print("="*60)
    print("\nThis will DELETE all data from:")
    print("  - graph_lifecycle (entities)")
    print("  - relationship_metadata")
    print("  - document_embeddings")
    print("  - context_bundles")
    print("  - query_responses")
    print("  - feedback_records")
    print("  - session_memory")
    print("  - symbolic_rules")
    print("\nThe Apache AGE graph will be dropped and recreated.")
    print("\n" + "="*60)

    response = input("\nType 'DELETE' to confirm: ")
    if response != "DELETE":
        print("Aborted.")
        return

    await init_databases()

    try:
        async with db_manager.get_postgres_connection() as conn:
            print("\nClearing data...")

            # Clear tables
            await conn.execute("TRUNCATE TABLE feedback_records CASCADE")
            print("  ✓ Cleared feedback_records")

            await conn.execute("TRUNCATE TABLE query_responses CASCADE")
            print("  ✓ Cleared query_responses")

            await conn.execute("TRUNCATE TABLE context_bundles CASCADE")
            print("  ✓ Cleared context_bundles")

            await conn.execute("TRUNCATE TABLE session_memory CASCADE")
            print("  ✓ Cleared session_memory")

            await conn.execute("TRUNCATE TABLE document_embeddings CASCADE")
            print("  ✓ Cleared document_embeddings")

            await conn.execute("TRUNCATE TABLE relationship_metadata CASCADE")
            print("  ✓ Cleared relationship_metadata")

            await conn.execute("TRUNCATE TABLE graph_lifecycle CASCADE")
            print("  ✓ Cleared graph_lifecycle")

            await conn.execute("TRUNCATE TABLE symbolic_rules CASCADE")
            print("  ✓ Cleared symbolic_rules")

            # Drop and recreate AGE graph
            print("\nRecreating Apache AGE graph...")
            await conn.execute("LOAD 'age'")
            await conn.execute("SET search_path = ag_catalog, '$user', public")

            try:
                await conn.execute("SELECT drop_graph('cf_knowledge', true)")
                print("  ✓ Dropped existing graph")
            except:
                pass  # Graph may not exist

            await conn.execute("SELECT create_graph('cf_knowledge')")
            print("  ✓ Created new graph")

        print("\n" + "="*60)
        print("All data cleared successfully")
        print("="*60 + "\n")

    finally:
        await close_databases()


async def extract_document():
    """Extract entities and relationships from a document"""
    from src.utils.extraction_pipeline import run_extraction_pipeline

    if len(sys.argv) < 3:
        print("Usage: python -m src.cli extract <file_path> [document_type]")
        sys.exit(1)

    file_path = sys.argv[2]
    document_type = sys.argv[3] if len(sys.argv) > 3 else "runbook"

    result = await run_extraction_pipeline(file_path, document_type)

    print(f"\nSummary:")
    print(f"  Raw: {result['raw_entities']} entities, {result['raw_relationships']} relationships")
    print(f"  After dedup: {result['deduped_entities']} entities, {result['deduped_relationships']} relationships")
    print(f"  Inserted: {result['inserted_entities']} entities, {result['inserted_relationships']} relationships")
    print(f"  DB merges: {result['db_merges']}, Cross-doc resolved: {result['cross_doc_resolved']}")


async def extract_all_documents():
    """Extract from all documents in test_data/"""
    from src.utils.extraction_pipeline import run_batch_extraction
    import glob

    directory = sys.argv[2] if len(sys.argv) > 2 else "test_data/"
    document_type = sys.argv[3] if len(sys.argv) > 3 else "runbook"

    file_paths = sorted(glob.glob(f"{directory}/*.md"))
    if not file_paths:
        print(f"No .md files found in {directory}")
        sys.exit(1)

    print(f"Found {len(file_paths)} documents:")
    for fp in file_paths:
        print(f"  - {Path(fp).name}")

    await run_batch_extraction(file_paths, document_type)


async def run_dedup():
    """Run deduplication on STAGING entities"""
    from src.agents.dedup import DeduplicationAgent

    print("\n" + "="*60)
    print("Running Deduplication on STAGING")
    print("="*60 + "\n")

    await init_databases()

    try:
        dedup = DeduplicationAgent(db_manager)

        # Merge STAGING duplicates
        print("Merging STAGING duplicates...")
        merge_result = await dedup.merge_staging_duplicates()
        print(f"  Groups found: {merge_result['duplicate_groups_found']}")
        print(f"  Entities merged: {merge_result['entities_merged']}")

        # Cross-document resolution
        print("\nCross-document resolution...")
        matches = await dedup.find_cross_document_matches()
        if matches:
            resolution = await dedup.resolve_cross_document_matches(matches)
            print(f"  Resolved: {resolution['resolved']}")
        else:
            print("  No cross-document duplicates found")

        if merge_result['errors']:
            print(f"\nErrors: {len(merge_result['errors'])}")
            for error in merge_result['errors'][:5]:
                print(f"  - {error}")

    finally:
        await close_databases()


async def promote_with_evidence():
    """Evidence-based promotion from STAGING to TRUSTED"""

    print("\n" + "="*60)
    print("Evidence-Based Promotion")
    print("="*60 + "\n")

    await init_databases()

    try:
        gardener = GardenerAgent(db_manager)

        min_confidence = float(sys.argv[2]) if len(sys.argv) > 2 else 0.70
        min_sources = int(sys.argv[3]) if len(sys.argv) > 3 else 1

        print(f"Criteria: confidence >= {min_confidence}, sources >= {min_sources}")

        result = await gardener.promote_with_evidence(
            min_confidence=min_confidence,
            min_sources=min_sources
        )

        print(f"\nResults:")
        print(f"  Promoted entities: {result['promoted_entities']}")
        print(f"  Promoted relationships: {result['promoted_relationships']}")
        print(f"  Skipped (low confidence): {result['skipped_low_confidence']}")
        print(f"  Skipped (insufficient sources): {result['skipped_insufficient_sources']}")

    finally:
        await close_databases()


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "load-data":
        await load_walking_skeleton()
    elif command == "load-scaled-data":
        await load_scaled_data()
    elif command == "embed-documents":
        await embed_documents()
    elif command == "embed-scaled-docs":
        await embed_scaled_documents()
    elif command == "promote-all":
        await promote_all_to_trusted()
    elif command == "promote-evidence":
        await promote_with_evidence()
    elif command == "extract":
        await extract_document()
    elif command == "extract-all":
        await extract_all_documents()
    elif command == "dedup":
        await run_dedup()
    elif command == "stats":
        await show_stats()
    elif command == "clear-data":
        await clear_all_data()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
