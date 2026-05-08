"""VerdictSynthesizer — pure logic, no LLM, no scoring weights.

The ONLY place categorical thresholds appear in the engine. Thresholds are
structural counts (≥2 distinct authoritative sources), not weighted scores.
This module is exhaustively unit-tested because every other stage's output
funnels through it.
"""
from __future__ import annotations

from typing import List, Optional
from .contracts import (
    Fact, EvaluationPlan, EvidenceItem, Challenge, ProofAttempt,
    MetaAudit, Verdict, VerdictStatus,
)


_AUTH_OK = ("PROVEN", "STRONGLY_SUPPORTED", "SUPPORTED")


def _confirming_authoritative(evidence: List[EvidenceItem]) -> List[EvidenceItem]:
    """Filter to confirming evidence whose source has a passing authority verdict.

    If `source_authority_verdict is None` we treat the source as 'unverified'
    and EXCLUDE it from authoritative count — that's the conservative choice
    that prevents an unverified blog post from getting a fact promoted to
    STRONGLY_SUPPORTED. Such evidence still appears in the verdict; it just
    doesn't clear the authoritative-count bar.
    """
    out = []
    for e in evidence:
        if e.polarity != "confirms":
            continue
        if e.source_authority_verdict is None:
            continue
        if e.source_authority_verdict.status in _AUTH_OK:
            out.append(e)
    return out


def _count_distinct_documents(evidence: List[EvidenceItem]) -> int:
    seen = set()
    for e in evidence:
        if e.source_document_id:
            seen.add(e.source_document_id)
        elif e.chunk_id:
            # Fall back to chunk if document_id missing — undercounts in the
            # multi-chunk-per-doc case, but never overcounts.
            seen.add(("chunk", e.chunk_id))
    return len(seen)


class VerdictSynthesizer:
    """Synthesise a categorical verdict from stages 1-5 outputs.

    `synthesize` is pure and deterministic — same inputs always produce same
    output, byte-for-byte. No LLM, no I/O.
    """

    def synthesize(
        self,
        fact: Fact,
        plan: EvaluationPlan,
        evidence: List[EvidenceItem],
        challenges: List[Challenge],
        proof: Optional[ProofAttempt],
        disproof: Optional[ProofAttempt],
        meta: MetaAudit,
        sub_verdicts: List[Verdict],
        depth: int = 0,
    ) -> Verdict:
        trace: List[str] = []
        caveats: List[str] = []
        surviving = [c for c in challenges if c.survived_rebuttal]

        # 1a. Presupposition disproved → fact's preconditions fail
        for sv in sub_verdicts:
            if sv.status == "DISPROVEN":
                trace.append(f"presupposition DISPROVEN: {sv.fact.key()}")
                return self._mk(
                    "UNDERSPECIFIED", fact, plan, evidence, surviving,
                    proof, disproof, meta, sub_verdicts, trace,
                    caveats=["presupposition disproven"], depth=depth,
                )
        # 1b. Presupposition itself UNDERSPECIFIED → fact ambiguous as well.
        #     Spec lines 745-748 explicitly handle DISPROVEN; common-sense
        #     extension: if we can't even verify a precondition, we can't
        #     reach a positive verdict on what depends on it.
        for sv in sub_verdicts:
            if sv.status == "UNDERSPECIFIED":
                trace.append(f"presupposition UNDERSPECIFIED: {sv.fact.key()}")
                return self._mk(
                    "UNDERSPECIFIED", fact, plan, evidence, surviving,
                    proof, disproof, meta, sub_verdicts, trace,
                    caveats=["presupposition could not be verified"], depth=depth,
                )

        # 2. Disproof succeeded with valid proof chain → fact is false
        if disproof and disproof.succeeded and meta.proof_validity_verdict == "valid":
            trace.append("disproof succeeded; meta confirmed proof valid")
            return self._mk(
                "DISPROVEN", fact, plan, evidence, surviving,
                proof, disproof, meta, sub_verdicts, trace,
                caveats=caveats, depth=depth,
            )

        # 3. Proof succeeded with valid proof chain
        if proof and proof.succeeded and meta.proof_validity_verdict == "valid":
            trace.append("proof succeeded; meta confirmed proof valid")
            if not surviving:
                return self._mk(
                    "PROVEN", fact, plan, evidence, surviving,
                    proof, disproof, meta, sub_verdicts, trace,
                    caveats=caveats, depth=depth,
                )
            trace.append(f"{len(surviving)} surviving challenge(s) → CONTESTED")
            return self._mk(
                "CONTESTED", fact, plan, evidence, surviving,
                proof, disproof, meta, sub_verdicts, trace,
                caveats=[f"{len(surviving)} adversarial challenge(s) survived rebuttal"],
                depth=depth,
            )

        # 4. No formal proof. Surviving challenge with no confirming evidence
        #    is decisive. With confirming evidence it becomes a contest.
        if surviving:
            confirming = [e for e in evidence if e.polarity == "confirms"]
            if confirming:
                trace.append(
                    f"{len(surviving)} surviving challenge(s) AND "
                    f"{len(confirming)} confirming evidence → CONTESTED"
                )
                return self._mk(
                    "CONTESTED", fact, plan, evidence, surviving,
                    proof, disproof, meta, sub_verdicts, trace,
                    caveats=[c.description for c in surviving], depth=depth,
                )
            trace.append(f"{len(surviving)} surviving challenge(s), no confirming evidence → DISPROVEN")
            return self._mk(
                "DISPROVEN", fact, plan, evidence, surviving,
                proof, disproof, meta, sub_verdicts, trace,
                caveats=[c.description for c in surviving], depth=depth,
            )

        # 5. No proof, no surviving challenges. Count distinct authoritative
        #    sources confirming the fact.
        if meta.evidence_thoroughness_verdict == "shallow":
            trace.append("meta: evidence gathering shallow → UNDERSUPPORTED")
            return self._mk(
                "UNDERSUPPORTED", fact, plan, evidence, surviving,
                proof, disproof, meta, sub_verdicts, trace,
                caveats=["evidence gathering ruled shallow by meta-audit"],
                depth=depth,
            )

        confirming_auth = _confirming_authoritative(evidence)
        n_distinct = _count_distinct_documents(confirming_auth)
        trace.append(
            f"distinct authoritative confirming sources: {n_distinct} "
            f"(of {len(confirming_auth)} authoritative-confirming evidence items)"
        )

        if n_distinct >= 2:
            return self._mk(
                "STRONGLY_SUPPORTED", fact, plan, evidence, surviving,
                proof, disproof, meta, sub_verdicts, trace,
                caveats=caveats, depth=depth,
            )
        if n_distinct == 1:
            return self._mk(
                "SUPPORTED", fact, plan, evidence, surviving,
                proof, disproof, meta, sub_verdicts, trace,
                caveats=caveats, depth=depth,
            )
        return self._mk(
            "UNDERSUPPORTED", fact, plan, evidence, surviving,
            proof, disproof, meta, sub_verdicts, trace,
            caveats=["no authoritative confirming evidence found"], depth=depth,
        )

    @staticmethod
    def _mk(status: VerdictStatus, fact, plan, evidence, surviving,
            proof, disproof, meta, sub_verdicts, trace, caveats, depth) -> Verdict:
        return Verdict(
            status=status, fact=fact, plan=plan, evidence=evidence,
            surviving_challenges=surviving, proof_attempt=proof,
            disproof_attempt=disproof, meta_audit=meta,
            sub_verdicts=sub_verdicts, trace=list(trace),
            caveats=list(caveats), depth=depth,
        )
