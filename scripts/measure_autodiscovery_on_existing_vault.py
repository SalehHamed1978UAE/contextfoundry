"""Run TypeDiscoveryAgent and CrossDocumentValidator over the existing
ClaudeCode Nexus vault (176a4fb2-0bb4-4da3-9068-0e26268fca71) to answer:

  2. Which types would TypeDiscoveryAgent auto-add to the ontology?
  3. How many facts does CrossDocumentValidator promote vs. flag?
  4. Did the Walsh contradictions get detected?

We do NOT mutate the DB beyond persist_proposals (which writes to
ontology_candidates). Validator runs in report-only mode here.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from collections import Counter
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from context_foundry.discovery.type_discovery_agent import (
    TypeDiscoveryAgent,
    ObservedPattern,
)
from context_foundry.discovery.cross_document_validator import (
    CrossDocumentValidator,
    ExtractedFact,
)


def _session():
    engine = create_engine(os.environ["DATABASE_URL"])
    return sessionmaker(bind=engine)()


def db_session():
    return _session()

TENANT = "176a4fb2-0bb4-4da3-9068-0e26268fca71"


def run_discovery():
    print("=" * 78)
    print("TypeDiscoveryAgent on existing vault relationships")
    print("=" * 78)
    sess = db_session()
    # Pull every relationship with a raw_relationship_type — that's the
    # signal the agent needs. Many older rows have NULL raw (already
    # normalised at extraction time), so we'll fall back to relationship_type
    # for those.
    rows = sess.execute(text("""
        SELECT r.id, r.source_id, r.target_id, r.relationship_type,
               r.raw_relationship_type, r.source_chunk_id, r.source_document_id,
               se.entity_type AS src_type, te.entity_type AS tgt_type,
               se.name AS src_name, te.name AS tgt_name
          FROM relationships r
          JOIN entities se ON se.id = r.source_id
          JOIN entities te ON te.id = r.target_id
         WHERE r.tenant_id = CAST(:tid AS uuid)
    """), {"tid": TENANT}).mappings().fetchall()
    print(f"  total relationships in vault: {len(rows)}")
    raw_present = sum(1 for r in rows if r["raw_relationship_type"])
    print(f"  with raw_relationship_type:    {raw_present}")
    print(f"  with only normalised type:     {len(rows) - raw_present}")

    agent = TypeDiscoveryAgent(
        session=sess, min_observations=5, tenant_id=TENANT,
    )
    for r in rows:
        phrase = r["raw_relationship_type"] or r["relationship_type"]
        if not phrase:
            continue
        src_name = r["src_name"] or ""
        tgt_name = r["tgt_name"] or ""
        agent.observe(ObservedPattern(
            source_type=r["src_type"] or "UNKNOWN",
            target_type=r["tgt_type"] or "UNKNOWN",
            relationship_phrase=phrase,
            source_text=f"{src_name} -[{phrase}]-> {tgt_name}",
            document_type="historical",
            confidence=0.7,
        ))
    proposals = agent.discover_types()
    print(f"\n  proposals surfaced: {len(proposals)}")
    for p in proposals[:30]:
        print(f"   - {p.proposed_type:30s} conf={p.confidence:.2f} "
              f"count={p.observation_count:3d} parent={p.parent_type}")
    if len(proposals) > 30:
        print(f"   ... and {len(proposals) - 30} more")

    auto_approve = [p for p in proposals if p.confidence >= 0.85]
    print(f"\n  would auto-APPROVE (conf >= 0.85): {len(auto_approve)}")
    for p in auto_approve:
        print(f"     {p.proposed_type:30s}  conf={p.confidence:.2f}  parent={p.parent_type}")
    pending = [p for p in proposals if p.confidence < 0.85]
    print(f"  would mark PENDING (conf < 0.85):  {len(pending)}")

    sess.close()
    return proposals, auto_approve


def run_validator():
    print()
    print("=" * 78)
    print("CrossDocumentValidator on existing vault relationships")
    print("=" * 78)
    sess = db_session()
    rows = sess.execute(text("""
        SELECT r.id, r.source_id, r.target_id, r.relationship_type,
               r.source_chunk_id, r.source_document_id, r.lifecycle_state,
               se.name AS src_name, te.name AS tgt_name
          FROM relationships r
          JOIN entities se ON se.id = r.source_id
          JOIN entities te ON te.id = r.target_id
         WHERE r.tenant_id = CAST(:tid AS uuid)
    """), {"tid": TENANT}).mappings().fetchall()
    print(f"  total relationships to validate: {len(rows)}")

    validator = CrossDocumentValidator(session=sess, tenant_id=TENANT)
    status_counts: Counter = Counter()
    action_counts: Counter = Counter()
    contradictions = []
    walsh_findings = []
    for r in rows:
        fact = ExtractedFact(
            source_entity_id=str(r["source_id"]),
            target_entity_id=str(r["target_id"]),
            relationship_type=r["relationship_type"],
            evidence_chunk_id=str(r["source_chunk_id"]) if r["source_chunk_id"] else None,
            source_document_id=str(r["source_document_id"]) if r["source_document_id"] else None,
        )
        v = validator.validate_fact(fact)
        status_counts[v.status] += 1
        action_counts[v.action_required] += 1
        if v.status == "CONTRADICTED":
            contradictions.append((r, v))
        nm = (r["src_name"] or "").lower()
        if "walsh" in nm:
            walsh_findings.append((r, v))

    print(f"\n  Status breakdown:")
    for s, c in status_counts.most_common():
        print(f"    {s:18s} {c:5d}")
    print(f"\n  Action breakdown:")
    for a, c in action_counts.most_common():
        print(f"    {a:18s} {c:5d}")

    print(f"\n  CONTRADICTED facts: {len(contradictions)}")
    for r, v in contradictions[:15]:
        print(f"    ({r['src_name']})-[{r['relationship_type']}]->({r['tgt_name']})")
        print(f"      conf={v.confidence:.2f}  {v.reasoning}")

    print(f"\n  Walsh-related facts ({len(walsh_findings)}):")
    for r, v in walsh_findings:
        print(f"    [{v.status}] ({r['src_name']})-[{r['relationship_type']}]->({r['tgt_name']})")
        print(f"      lifecycle_state={r['lifecycle_state']}  action={v.action_required}")
        print(f"      reasoning: {v.reasoning}")

    sess.close()
    return status_counts, action_counts, contradictions, walsh_findings


if __name__ == "__main__":
    run_discovery()
    run_validator()
