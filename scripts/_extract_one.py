"""Extract ONE document, append result to /tmp/reextract_results.json. Idempotent: skips if already done."""
import os, sys, glob, logging, json, traceback
sys.path.insert(0, '.')
logging.disable(logging.WARNING)

from sqlalchemy import create_engine, text as sa_text
from sqlalchemy.orm import sessionmaker
from src.context_foundry.extraction.ontology_centric_pipeline import OntologyCentricPipeline
from collections import Counter

V = '176a4fb2-0bb4-4da3-9068-0e26268fca71'
RESULT_FILE = '/tmp/reextract_results.json'
NEW_TYPES = {'HOLDS_ROLE','HAS_SPEC','USES_MATERIAL','INVOLVES'}

def load_results():
    if not os.path.exists(RESULT_FILE): return {}
    with open(RESULT_FILE) as f: return json.load(f)

def save_results(d):
    with open(RESULT_FILE,'w') as f: json.dump(d, f, indent=2)

def main():
    fn = sys.argv[1]; dt = sys.argv[2]
    results = load_results()
    if fn in results and results[fn].get('success'):
        print(f"SKIP {fn} (already done)"); return
    eng = create_engine(os.environ['DATABASE_URL'])
    s = sessionmaker(bind=eng)()
    did = s.execute(sa_text("SELECT id::text FROM platform.documents WHERE tenant_id=CAST(:t AS uuid) AND name=:n"),
                    {"t":V,"n":fn}).scalar()
    paths = glob.glob(f'./test documents/ClaudeCode_NExus_Industries_corpus/**/{fn}', recursive=True)
    text = open(paths[0]).read()
    print(f"--- {fn} (type={dt}, doc_id={did}, {len(text)} chars) ---", flush=True)
    try:
        p = OntologyCentricPipeline(session=s, tenant_id=V, model='gpt-4o-mini',
                                    enable_canonicalization=True, auto_stage=True,
                                    enable_job_tracking=False)
        r = p.extract(text=text, document_id=did, filename=fn, document_type_override=dt)
        rt_counts = dict(Counter(x.relation_type for x in r.relations))
        new_edges = [{"src":x.source_name,"type":x.relation_type,"tgt":x.target_name}
                     for x in r.relations if x.relation_type in NEW_TYPES]
        results[fn] = {
            "success": r.success,
            "doc_id": did,
            "doc_type": dt,
            "entities": len(r.entities),
            "relations": len(r.relations),
            "relation_types": rt_counts,
            "staged_entities": r.staging_result.entities_created if r.staging_result else None,
            "staged_relations": r.staging_result.relations_created if r.staging_result else None,
            "new_type_count": len(new_edges),
            "new_edges_sample": new_edges[:30],
        }
        save_results(results)
        print(f"  success={r.success}  ent={len(r.entities)} rel={len(r.relations)}  NEW_edges={len(new_edges)}", flush=True)
        print(f"  rel_types: {rt_counts}", flush=True)
    except Exception as e:
        traceback.print_exc()
        results[fn] = {"success": False, "error": str(e)}
        save_results(results)

if __name__ == '__main__':
    main()
