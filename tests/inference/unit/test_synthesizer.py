"""Exhaustive case-analysis tests for VerdictSynthesizer.

The synthesiser is the only place categorical thresholds live. Every branch
must be hit by these tests. No LLM, no DB, no I/O — pure logic.
"""
from __future__ import annotations

import pytest
from src.context_foundry.inference.contracts import (
    Fact, Condition, EvaluationPlan, EvidenceItem, ProofAttempt, Challenge,
    MetaAudit, Verdict,
)
from src.context_foundry.inference.synthesizer import VerdictSynthesizer


# ---------- helpers ----------
def mk_fact(s="src", r="REL", t="tgt"):
    return Fact(source_entity_id=s, relationship_type=r, target_entity_id=t)


def mk_plan():
    return EvaluationPlan(fact_type="REL")


def mk_meta(thorough=True, valid="valid", complete=True, replan=False):
    return MetaAudit(
        plan_completeness_verdict="complete" if complete else "incomplete",
        evidence_thoroughness_verdict="thorough" if thorough else "shallow",
        proof_validity_verdict=valid,
        recommend_replan=replan,
    )


def mk_proof(succeeded=False):
    return ProofAttempt(succeeded=succeeded)


def mk_authoritative_evidence(doc_id="doc-A", chunk_id="ch-1"):
    """Confirming evidence with a passing source-authority verdict."""
    inner = Verdict(
        status="SUPPORTED", fact=mk_fact("ch-x", "IS_AUTHORITATIVE_FOR", "REL"),
    )
    return EvidenceItem(
        chunk_id=chunk_id, source_document_id=doc_id,
        content="confirming", speaks_to="t", polarity="confirms",
        source_authority_verdict=inner,
    )


def mk_unauthoritative_evidence(chunk_id="ch-X"):
    """Confirming evidence with no source-authority verdict (treated as unverified)."""
    return EvidenceItem(
        chunk_id=chunk_id, source_document_id="doc-?",
        content="anon", speaks_to="t", polarity="confirms",
        source_authority_verdict=None,
    )


SYNTH = VerdictSynthesizer()


# ============================================================ DISPROVEN
def test_disproof_succeeds_with_valid_meta_returns_disproven():
    f = mk_fact()
    v = SYNTH.synthesize(
        f, mk_plan(), [], [],
        proof=mk_proof(False),
        disproof=ProofAttempt(succeeded=True, chain=["x", "y"]),
        meta=mk_meta(valid="valid"), sub_verdicts=[],
    )
    assert v.status == "DISPROVEN"


def test_disproof_succeeds_with_invalid_meta_does_not_return_disproven():
    """Spec: disproof must be paired with meta.proof_validity_verdict == 'valid'."""
    f = mk_fact()
    v = SYNTH.synthesize(
        f, mk_plan(), [], [],
        proof=mk_proof(False),
        disproof=ProofAttempt(succeeded=True),
        meta=mk_meta(valid="invalid"), sub_verdicts=[],
    )
    assert v.status != "DISPROVEN"


def test_surviving_challenge_with_no_confirming_evidence_returns_disproven():
    f = mk_fact()
    challenge = Challenge(description="counter", survived_rebuttal=True)
    v = SYNTH.synthesize(
        f, mk_plan(), [], [challenge],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(valid="no_proof_attempted"),
        sub_verdicts=[],
    )
    assert v.status == "DISPROVEN"


# ============================================================ PROVEN
def test_proof_succeeds_with_no_surviving_challenges_returns_proven():
    f = mk_fact()
    rebutted = Challenge(description="weak", survived_rebuttal=False)
    v = SYNTH.synthesize(
        f, mk_plan(), [], [rebutted],
        proof=ProofAttempt(succeeded=True, chain=["a"]),
        disproof=mk_proof(False),
        meta=mk_meta(valid="valid"), sub_verdicts=[],
    )
    assert v.status == "PROVEN"
    assert v.surviving_challenges == []


def test_proof_succeeds_with_invalid_meta_does_not_return_proven():
    f = mk_fact()
    v = SYNTH.synthesize(
        f, mk_plan(), [], [],
        proof=ProofAttempt(succeeded=True), disproof=mk_proof(False),
        meta=mk_meta(valid="invalid"), sub_verdicts=[],
    )
    assert v.status != "PROVEN"


# ============================================================ CONTESTED
def test_proof_succeeds_with_surviving_challenge_returns_contested():
    f = mk_fact()
    challenge = Challenge(description="real", survived_rebuttal=True)
    v = SYNTH.synthesize(
        f, mk_plan(), [], [challenge],
        proof=ProofAttempt(succeeded=True),
        disproof=mk_proof(False),
        meta=mk_meta(valid="valid"), sub_verdicts=[],
    )
    assert v.status == "CONTESTED"
    assert v.surviving_challenges == [challenge]


def test_no_proof_surviving_challenge_with_confirming_evidence_returns_contested():
    f = mk_fact()
    challenge = Challenge(description="real", survived_rebuttal=True)
    confirming = EvidenceItem(content="ok", speaks_to="t", polarity="confirms",
                               chunk_id="c1", source_document_id="d1")
    v = SYNTH.synthesize(
        f, mk_plan(), [confirming], [challenge],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(valid="no_proof_attempted"), sub_verdicts=[],
    )
    assert v.status == "CONTESTED"


# ============================================================ UNDERSPECIFIED
def test_disproven_presupposition_returns_underspecified():
    f = mk_fact()
    bad_pre = Verdict(status="DISPROVEN",
                       fact=mk_fact("a", "IS_PERSON", "p"))
    v = SYNTH.synthesize(
        f, mk_plan(), [], [],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(), sub_verdicts=[bad_pre],
    )
    assert v.status == "UNDERSPECIFIED"


def test_underspecified_presupposition_propagates_underspecified():
    """Presupposition we couldn't verify → can't reach a positive verdict."""
    f = mk_fact()
    ambig = Verdict(status="UNDERSPECIFIED",
                     fact=mk_fact("a", "IS_PERSON", "p"))
    # Even with confirming evidence and no challenges, we can't conclude.
    v = SYNTH.synthesize(
        f, mk_plan(),
        [mk_authoritative_evidence("docA", "c1"),
         mk_authoritative_evidence("docB", "c2")],
        [],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(thorough=True, valid="no_proof_attempted"),
        sub_verdicts=[ambig],
    )
    assert v.status == "UNDERSPECIFIED"


# ============================================================ UNDERSUPPORTED
def test_no_evidence_no_proof_returns_undersupported():
    f = mk_fact()
    v = SYNTH.synthesize(
        f, mk_plan(), [], [],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(thorough=True, valid="no_proof_attempted"),
        sub_verdicts=[],
    )
    assert v.status == "UNDERSUPPORTED"


def test_shallow_evidence_returns_undersupported_even_with_confirming():
    f = mk_fact()
    v = SYNTH.synthesize(
        f, mk_plan(),
        [mk_authoritative_evidence("d1", "c1"), mk_authoritative_evidence("d2", "c2")],
        [],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(thorough=False, valid="no_proof_attempted"),
        sub_verdicts=[],
    )
    assert v.status == "UNDERSUPPORTED"


def test_unverified_confirming_evidence_does_not_clear_supported_bar():
    """Source-authority is required: unverified evidence leaves verdict undersupported."""
    f = mk_fact()
    v = SYNTH.synthesize(
        f, mk_plan(),
        [mk_unauthoritative_evidence("c1"), mk_unauthoritative_evidence("c2")],
        [],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(thorough=True, valid="no_proof_attempted"),
        sub_verdicts=[],
    )
    assert v.status == "UNDERSUPPORTED"


# ============================================================ SUPPORTED
def test_one_authoritative_source_returns_supported():
    f = mk_fact()
    v = SYNTH.synthesize(
        f, mk_plan(), [mk_authoritative_evidence("docX", "c1")], [],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(thorough=True, valid="no_proof_attempted"),
        sub_verdicts=[],
    )
    assert v.status == "SUPPORTED"


def test_two_chunks_same_document_returns_supported_not_strongly():
    """Distinct DOCUMENTS, not distinct chunks. Two chunks in one doc = 1 source."""
    f = mk_fact()
    v = SYNTH.synthesize(
        f, mk_plan(),
        [mk_authoritative_evidence("doc-same", "c1"),
         mk_authoritative_evidence("doc-same", "c2")],
        [],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(thorough=True, valid="no_proof_attempted"),
        sub_verdicts=[],
    )
    assert v.status == "SUPPORTED"


# ============================================================ STRONGLY_SUPPORTED
def test_two_distinct_authoritative_documents_returns_strongly_supported():
    f = mk_fact()
    v = SYNTH.synthesize(
        f, mk_plan(),
        [mk_authoritative_evidence("docA", "c1"),
         mk_authoritative_evidence("docB", "c2")],
        [],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(thorough=True, valid="no_proof_attempted"),
        sub_verdicts=[],
    )
    assert v.status == "STRONGLY_SUPPORTED"


def test_three_distinct_documents_still_strongly_supported():
    f = mk_fact()
    ev = [mk_authoritative_evidence(f"doc-{i}", f"c-{i}") for i in range(5)]
    v = SYNTH.synthesize(
        f, mk_plan(), ev, [],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(thorough=True, valid="no_proof_attempted"),
        sub_verdicts=[],
    )
    assert v.status == "STRONGLY_SUPPORTED"


# ============================================================ rebutted-challenge sanity
def test_rebutted_challenges_do_not_block_strongly_supported():
    f = mk_fact()
    rebutted = Challenge(description="weak attack", survived_rebuttal=False)
    v = SYNTH.synthesize(
        f, mk_plan(),
        [mk_authoritative_evidence("docA", "c1"),
         mk_authoritative_evidence("docB", "c2")],
        [rebutted],
        proof=mk_proof(False), disproof=mk_proof(False),
        meta=mk_meta(thorough=True, valid="no_proof_attempted"),
        sub_verdicts=[],
    )
    assert v.status == "STRONGLY_SUPPORTED"


# ============================================================ determinism
def test_synthesise_is_deterministic():
    f = mk_fact()
    plan = mk_plan()
    ev = [mk_authoritative_evidence("docA", "c1"),
          mk_authoritative_evidence("docB", "c2")]
    args = (f, plan, ev, [], mk_proof(False), mk_proof(False),
            mk_meta(thorough=True, valid="no_proof_attempted"), [])
    v1 = SYNTH.synthesize(*args)
    v2 = SYNTH.synthesize(*args)
    assert v1.model_dump_json() == v2.model_dump_json()


def test_recursion_guard_basic():
    from src.context_foundry.inference.recursion import RecursionGuard
    g = RecursionGuard(max_depth=3)
    f1 = mk_fact("a", "R", "b")
    f2 = mk_fact("c", "R", "d")
    assert not g.has_visited(f1)
    g2 = g.child(f1)
    assert g2.has_visited(f1)
    assert not g2.has_visited(f2)
    assert not g.has_visited(f1)  # parent unaffected
    g3 = g2.child(f2)
    assert g3.depth == 2
    assert not g3.at_max_depth()
    g4 = g3.child(mk_fact("e", "R", "f"))
    assert g4.at_max_depth()
