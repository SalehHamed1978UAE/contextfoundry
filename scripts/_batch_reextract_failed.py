"""Re-extract docs whose latest extraction job FAILED with the relationship_type bug.
Idempotent via /tmp/reextract_results.json. Auto-classifies doc type. Updates doc status on success.

Usage: python scripts/_batch_reextract_failed.py [--count N]
"""
import os, sys, glob, json, logging, traceback, argparse
sys.path.insert(0, '.')
logging.disable(logging.WARNING)

from sqlalchemy import create_engine, text as sa_text
from sqlalchemy.orm import sessionmaker
from src.context_foundry.extraction.ontology_centric_pipeline import OntologyCentricPipeline
from collections import Counter

V = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
RESULT_FILE = '/tmp/reextract_results.json'

def load_results():
    if not os.path.exists(RESULT_FILE): return {}
    with open(RESULT_FILE) as f: return json.load(f)

def save_results(d):
    with open(RESULT_FILE, 'w') as f: json.dump(d, f, indent=2)

def get_failed_docs(s):
    rows = s.execute(sa_text(f"""
        WITH latest AS (
          SELECT DISTINCT ON (document_id) document_id, status, error_message, created_at
          FROM public.extraction_jobs
          WHERE tenant_id = CAST('{V}' AS uuid)
          ORDER BY document_id, created_at DESC
        )
        SELECT d.id::text AS doc_id, d.name
        FROM latest l
        JOIN platform.documents d ON d.id = l.document_id
        WHERE l.status = 'FAILED' AND l.error_message LIKE '%relationship_type%'
        ORDER BY d.name
    """)).fetchall()
    return [(r[0], r[1]) for r in rows]

def get_docs_from_v1(s):
    """Re-audit the same docs that v1 processed (read names from /tmp/reextract_results.v1.json)."""
    import json
    if not os.path.exists('/tmp/reextract_results.v1.json'):
        return []
    v1 = json.load(open('/tmp/reextract_results.v1.json'))
    names = list(v1.keys())
    rows = s.execute(sa_text(
        f"SELECT id::text, name FROM platform.documents "
        f"WHERE tenant_id=CAST('{V}' AS uuid) AND name = ANY(:names) ORDER BY name"
    ), {"names": names}).fetchall()
    return [(r[0], r[1]) for r in rows]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--count', type=int, default=4)
    ap.add_argument('--source', choices=['failed','v1'], default='failed',
                    help='failed=latest job is FAILED with bug; v1=names from /tmp/reextract_results.v1.json')
    args = ap.parse_args()

    eng = create_engine(os.environ['DATABASE_URL'])
    Session = sessionmaker(bind=eng)
    s = Session()
    docs = get_failed_docs(s) if args.source == 'failed' else get_docs_from_v1(s)
    s.close()
    print(f"Source={args.source}, total docs: {len(docs)}", flush=True)

    results = load_results()
    pending = [(did, fn) for did, fn in docs if not (fn in results and results[fn].get('success'))]
    print(f"Pending: {len(pending)}; will process up to {args.count} this run", flush=True)

    processed = 0
    for did, fn in pending:
        if processed >= args.count: break
        # find file
        paths = glob.glob(f'./test documents/ClaudeCode_NExus_Industries_corpus/**/{fn}', recursive=True)
        if not paths:
            print(f"SKIP {fn} (file not found on disk)", flush=True)
            results[fn] = {"success": False, "error": "file not found on disk"}
            save_results(results); continue
        text = open(paths[0]).read()
        print(f"\n--- [{processed+1}/{args.count}] {fn} ({len(text)} chars, doc_id={did}) ---", flush=True)
        s = Session()
        try:
            p = OntologyCentricPipeline(
                session=s, tenant_id=V, model='gpt-4o-mini',
                enable_canonicalization=True, auto_stage=True,
                enable_job_tracking=True,
            )
            r = p.extract(text=text, document_id=did, filename=fn)  # no override -> auto-classify
            rt = dict(Counter(x.relation_type for x in r.relations))
            sr = r.staging_result
            staging_errs = list(sr.errors) if sr else []
            results[fn] = {
                "success": r.success,
                "doc_id": did,
                "doc_type": r.document_type,
                "entities": len(r.entities),
                "relations": len(r.relations),
                "relation_types": rt,
                "staged_entities": sr.entities_created if sr else None,
                "staged_relations_created": sr.relations_created if sr else None,
                "staged_relations_updated": getattr(sr, 'relations_updated', 0) if sr else None,
                "staged_relations_skipped": getattr(sr, 'relations_skipped', 0) if sr else None,
                "staged_relations_as_candidates": getattr(sr, 'relations_as_candidates', 0) if sr else None,
                "staging_errors": staging_errs[:5],
                "staging_error_count": len(staging_errs),
                "error": r.error,
            }
            save_results(results)
            # Only mark doc as extracted when the pipeline reports success AND staging had no errors.
            # Note: staged_relations_created can be 0 legitimately (all skipped as duplicates), so we do not gate on it.
            if r.success and not staging_errs:
                s.execute(sa_text("""
                    UPDATE platform.documents
                       SET extraction_level='ontology', status='extracted', updated_at=NOW()
                     WHERE id = CAST(:did AS uuid)
                """), {"did": did})
                s.commit()
                results[fn]["doc_marked_extracted"] = True
            else:
                results[fn]["doc_marked_extracted"] = False
            save_results(results)
            print(f"  success={r.success} type={r.document_type} ent={len(r.entities)} rel={len(r.relations)} "
                  f"staged_ent={sr.entities_created if sr else '?'} "
                  f"staged_rel_created={sr.relations_created if sr else '?'} "
                  f"updated={getattr(sr,'relations_updated',0) if sr else '?'} "
                  f"skipped={getattr(sr,'relations_skipped',0) if sr else '?'} "
                  f"candidates={getattr(sr,'relations_as_candidates',0) if sr else '?'} "
                  f"staging_errs={len(staging_errs)} marked_extracted={results[fn]['doc_marked_extracted']}", flush=True)
            if r.error:
                print(f"  ERROR: {r.error}", flush=True)
            if staging_errs:
                print(f"  STAGING ERRORS ({len(staging_errs)}): {staging_errs[:3]}", flush=True)
        except Exception as e:
            traceback.print_exc()
            results[fn] = {"success": False, "error": str(e)}
            save_results(results)
        finally:
            s.close()
        processed += 1

    print(f"\nDone. Processed {processed} docs this run.", flush=True)
    remaining = sum(1 for did, fn in docs if not (fn in load_results() and load_results()[fn].get('success')))
    print(f"Remaining: {remaining}", flush=True)

if __name__ == '__main__':
    main()
