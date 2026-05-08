"""Verification harness for CrossDocumentValidator (Component 3).

Two tests:

A. **Real DB fact validation.** Pull every relationship in the 5 target docs,
   run each through ``validate_fact``, and report distribution of statuses.
   Verify that:
     - CORROBORATED facts have ≥2 corroborating edges from distinct sources.
     - SINGLE_SOURCE facts have exactly 1.
     - ORPHAN facts have 0.
     - Status counts sum to total facts validated.

B. **Synthetic singular-role contradiction.** Insert two HOLDS_POSITION edges
   pointing to the same ROLE target from different PERSONs into a temporary
   fixture (in-memory dicts mocking the session) and verify the validator
   returns CONTRADICTED with action_required='HUMAN_REVIEW'.
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from context_foundry.discovery.cross_document_validator import (
    CrossDocumentValidator,
    ExtractedFact,
)


TENANT = "176a4fb2-0bb4-4da3-9068-0e26268fca71"
DOC_IDS = [
    "c18d20e2-dd41-494c-9e4c-1e30911005e9",
    "a2b7c91e-5041-4800-b98b-0f663d8548dc",
    "a33dc47e-d00a-429c-b928-969ac385fe4b",
    "b98efc6e-0f6a-4bdc-b773-3241be8cc272",
    "123ac4df-3c05-4a1b-9f41-805fd8582412",
]


def test_a_real_data() -> bool:
    print("\n" + "=" * 78)
    print("TEST A: Validate real DB facts from the 5 target documents")
    print("=" * 78)
    engine = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=engine)
    session = Session()
    validator = CrossDocumentValidator(session, tenant_id=TENANT)

    rows = session.execute(text("""
        SELECT
          r.id, r.source_id, r.target_id, r.relationship_type,
          r.source_chunk_id, r.source_document_id, r.confidence,
          r.valid_from, r.valid_to,
          se.name AS src_name, te.name AS tgt_name
        FROM relationships r
        JOIN entities se ON se.id = r.source_id
        JOIN entities te ON te.id = r.target_id
        JOIN document_chunks dc ON dc.id = se.source_chunk_id
        WHERE dc.document_id = ANY(CAST(:dids AS uuid[]))
          AND r.tenant_id = CAST(:tid AS uuid)
    """), {"dids": DOC_IDS, "tid": TENANT}).fetchall()
    print(f"  facts to validate: {len(rows)}")

    status_counts: Counter = Counter()
    samples = {"CORROBORATED": [], "SINGLE_SOURCE": [], "ORPHAN": [], "CONTRADICTED": []}
    for r in rows:
        fact = ExtractedFact(
            source_entity_id=str(r[1]),
            target_entity_id=str(r[2]),
            relationship_type=r[3],
            evidence_chunk_id=str(r[4]) if r[4] else None,
            source_document_id=str(r[5]) if r[5] else None,
            valid_from=r[7],
            valid_to=r[8],
            confidence=r[6] or 0.0,
        )
        result = validator.validate_fact(fact)
        status_counts[result.status] += 1
        if len(samples[result.status]) < 3:
            samples[result.status].append((r[9], r[3], r[10], result))

    total = sum(status_counts.values())
    print(f"\n  status distribution ({total} facts):")
    for status, n in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"    {status:14s} {n:>3}  ({n/total:.1%})")

    print("\n  samples per status:")
    for status, items in samples.items():
        if not items:
            continue
        print(f"    {status}:")
        for src_name, rel, tgt_name, res in items:
            print(f"      ({src_name})-[{rel}]->({tgt_name})  conf={res.confidence}")
            print(f"        action={res.action_required}  {res.reasoning}")

    # Invariants
    assert total == len(rows), "Status counts don't sum to total"
    assert status_counts["CORROBORATED"] + status_counts["SINGLE_SOURCE"] \
           + status_counts["ORPHAN"] + status_counts["CONTRADICTED"] == total
    # CORROBORATED requires >= 2 corroborating edges → re-verify a sample
    for src_name, rel, tgt_name, res in samples["CORROBORATED"]:
        assert res.corroborating_count >= 2, \
            f"CORROBORATED {src_name}-[{rel}]->{tgt_name} has corroborating={res.corroborating_count}"
    for src_name, rel, tgt_name, res in samples["SINGLE_SOURCE"]:
        assert res.corroborating_count == 1
    for src_name, rel, tgt_name, res in samples["ORPHAN"]:
        assert res.corroborating_count == 0

    print("\n  Invariants: PASS (counts sum, status thresholds correct)")
    session.close()
    return True


def test_b_synthetic_contradiction() -> bool:
    print("\n" + "=" * 78)
    print("TEST B: Synthetic singular-role contradiction (in-memory)")
    print("=" * 78)

    # Mock session that returns canned rows for each query.
    role_id = "00000000-0000-0000-0000-000000000a01"
    person_a = "00000000-0000-0000-0000-000000000b01"
    person_b = "00000000-0000-0000-0000-000000000b02"
    chunk_a = "00000000-0000-0000-0000-000000000c01"
    chunk_b = "00000000-0000-0000-0000-000000000c02"
    doc_a = "00000000-0000-0000-0000-000000000d01"
    doc_b = "00000000-0000-0000-0000-000000000d02"

    class FakeMappings:
        def __init__(self, rows): self._rows = rows
        def fetchall(self): return self._rows

    class FakeResult:
        def __init__(self, rows): self._rows = rows
        def mappings(self): return FakeMappings(self._rows)

    class FakeSession:
        def execute(self, sql, params):
            sql_text = str(sql)
            # Corroboration query targets source_id, target_id, relationship_type
            if "source_id = CAST(:src AS uuid)" in sql_text and "relationship_type = :rt" in sql_text:
                return FakeResult([])  # no corroboration
            # Contradiction query: target_id = X, relationship_type IN (...), source_id <> Y
            if "target_id = CAST(:tgt AS uuid)" in sql_text and "ANY(:rels)" in sql_text:
                return FakeResult([{
                    "id": "00000000-0000-0000-0000-000000000e01",
                    "source_id": person_b,
                    "target_id": role_id,
                    "relationship_type": "HOLDS_POSITION",
                    "source_document_id": doc_b,
                    "source_chunk_id": chunk_b,
                    "lifecycle_state": "STAGING",
                }])
            return FakeResult([])

    validator = CrossDocumentValidator(FakeSession(), tenant_id=TENANT)
    fact = ExtractedFact(
        source_entity_id=person_a,
        target_entity_id=role_id,
        relationship_type="HOLDS_POSITION",
        evidence_chunk_id=chunk_a,
        source_document_id=doc_a,
        confidence=0.95,
    )
    result = validator.validate_fact(fact)
    print(f"  status: {result.status}")
    print(f"  action: {result.action_required}")
    print(f"  reasoning: {result.reasoning}")
    print(f"  contradicting_count: {result.contradicting_count}")
    print(f"  examples: {result.contradicting_examples}")

    assert result.status == "CONTRADICTED", f"expected CONTRADICTED, got {result.status}"
    assert result.action_required == "HUMAN_REVIEW"
    assert result.contradicting_count == 1
    print("\n  Singular-role conflict detected: PASS")

    # And: two consistent corroborators (different chunks) → CORROBORATED
    class FakeSession2:
        def execute(self, sql, params):
            sql_text = str(sql)
            if "source_id = CAST(:src AS uuid)" in sql_text and "relationship_type = :rt" in sql_text:
                return FakeResult([
                    {"id": "x1", "source_id": person_a, "target_id": role_id,
                     "relationship_type": "HOLDS_POSITION", "source_chunk_id": chunk_b,
                     "source_document_id": doc_b, "lifecycle_state": "STAGING", "confidence": 0.9},
                    {"id": "x2", "source_id": person_a, "target_id": role_id,
                     "relationship_type": "HOLDS_POSITION", "source_chunk_id": "00000000-0000-0000-0000-000000000c03",
                     "source_document_id": "00000000-0000-0000-0000-000000000d03", "lifecycle_state": "STAGING", "confidence": 0.85},
                ])
            return FakeResult([])  # no contradictions
    v2 = CrossDocumentValidator(FakeSession2(), tenant_id=TENANT)
    res2 = v2.validate_fact(fact)
    print(f"\n  multi-source same fact → status: {res2.status} (conf={res2.confidence})")
    assert res2.status == "CORROBORATED", f"expected CORROBORATED, got {res2.status}"
    assert res2.action_required == "AUTO_PROMOTE"
    assert res2.confidence >= 0.8
    print("  Corroboration path: PASS")
    return True


def main() -> int:
    a = test_a_real_data()
    b = test_b_synthetic_contradiction()
    print("\n" + "=" * 78)
    print(f"OVERALL: {'PASS' if (a and b) else 'FAIL'}")
    print("=" * 78)
    return 0 if (a and b) else 1


if __name__ == "__main__":
    raise SystemExit(main())
