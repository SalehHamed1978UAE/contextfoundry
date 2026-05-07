"""Ad-hoc runner: re-extract 5 specific documents with OntologyCentricPipeline.

Wipes existing entities/relationships from the 5 source_document_ids first
(so we measure ONLY what the new ontology produces), then runs the pipeline
with document_type_override (so no LLM classification call).

Usage:
  python scripts/reextract_5_docs.py
"""
import os, sys, glob, logging
sys.path.insert(0, '.')

logging.disable(logging.WARNING)

from sqlalchemy import create_engine, text as sa_text
from sqlalchemy.orm import sessionmaker

from src.context_foundry.extraction.ontology_centric_pipeline import OntologyCentricPipeline

VAULT_ID = '176a4fb2-0bb4-4da3-9068-0e26268fca71'

# (filename, document_type) — type chosen to match what classifier returned earlier
TARGETS = [
    ('01_executive_team.md',                'org_chart'),
    ('04_greenhydrogen_initiative.md',      'project_plan'),
    ('06_solid_state_battery_design.md',    'architecture_doc'),
    ('01_boeing_customer_profile.md',       'customer_profile'),
    ('14_lockheed_martin_customer.md',      'customer_profile'),
]


def find_doc_path(filename):
    paths = glob.glob(f'./test documents/ClaudeCode_NExus_Industries_corpus/**/{filename}', recursive=True)
    return paths[0] if paths else None


def main():
    eng = create_engine(os.environ['DATABASE_URL'])
    Session = sessionmaker(bind=eng)
    s = Session()

    # Resolve doc IDs
    rows = s.execute(sa_text("""
        SELECT id::text AS id, name FROM platform.documents
        WHERE tenant_id = :t AND name = ANY(:names)
    """), {"t": VAULT_ID, "names": [t[0] for t in TARGETS]}).mappings().all()
    id_by_name = {r['name']: r['id'] for r in rows}

    print("=== STEP 1: Wipe existing extraction for these 5 docs ===")
    for filename, _ in TARGETS:
        did = id_by_name.get(filename)
        if not did:
            print(f"  {filename}: NOT IN VAULT, skipping")
            continue
        # delete relationships sourced from this doc
        rdel = s.execute(sa_text("""
            DELETE FROM public.relationships
            WHERE tenant_id = CAST(:t AS uuid) AND source_document_id = :d
        """), {"t": VAULT_ID, "d": did})
        s.commit()
        print(f"  {filename}: deleted {rdel.rowcount} rels (entities preserved; canonicalizer will reuse them)")

    print("\n=== STEP 2: Run OntologyCentricPipeline on each doc ===")
    pipeline = OntologyCentricPipeline(
        session=s,
        tenant_id=VAULT_ID,
        model='gpt-4o-mini',
        enable_canonicalization=True,
        auto_stage=True,
        enable_job_tracking=False,  # avoid duplicate-job constraint issues
    )

    for filename, doc_type in TARGETS:
        did = id_by_name.get(filename)
        if not did:
            continue
        path = find_doc_path(filename)
        if not path:
            print(f"  {filename}: source file not found on disk")
            continue
        text = open(path).read()
        print(f"\n--- {filename} (type={doc_type}, {len(text)} chars) ---")
        try:
            result = pipeline.extract(
                text=text,
                document_id=did,
                filename=filename,
                document_type_override=doc_type,
            )
            print(f"  success={result.success}")
            print(f"  entities={len(result.entities)} relations={len(result.relations)} chunks={result.chunks_stored}")
            if result.staging_result:
                print(f"  staged: {result.staging_result.entities_created} entities, {result.staging_result.relations_created} rels")
            # break down by relation_type
            from collections import Counter
            rt_counts = Counter(r.relation_type for r in result.relations)
            print(f"  relation_types: {dict(rt_counts)}")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()
            s.rollback()

    print("\n=== STEP 3: Verify edges in vault for these 5 docs ===")
    for filename, _ in TARGETS:
        did = id_by_name.get(filename)
        if not did: continue
        rs = s.execute(sa_text("""
            SELECT relationship_type, COUNT(*) AS n
            FROM public.relationships
            WHERE tenant_id = CAST(:t AS uuid) AND source_document_id = :d
            GROUP BY relationship_type ORDER BY n DESC
        """), {"t": VAULT_ID, "d": did}).mappings().all()
        print(f"\n--- {filename} ({sum(r['n'] for r in rs)} edges) ---")
        for r in rs:
            marker = ' ◀ NEW' if r['relationship_type'] in ('HOLDS_ROLE','HAS_SPEC','USES_MATERIAL','INVOLVES') else ''
            print(f"    {r['relationship_type']:<28} {r['n']:>3}{marker}")

    print("\n=== STEP 4: Targeted check across these 5 docs ===")
    ids = [id_by_name[f] for f, _ in TARGETS if f in id_by_name]
    for rt in ('HOLDS_ROLE','HAS_SPEC','USES_MATERIAL','INVOLVES'):
        n = s.execute(sa_text("""
            SELECT COUNT(*) AS n FROM public.relationships
            WHERE tenant_id = CAST(:t AS uuid) AND source_document_id = ANY(:ids) AND relationship_type = :rt
        """), {"t": VAULT_ID, "ids": ids, "rt": rt}).scalar()
        print(f"  {rt:<22} {n}")

    s.close()


if __name__ == '__main__':
    main()
