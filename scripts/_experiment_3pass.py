"""
3-pass extraction experiment on a single document.
Pass 1: Candidate Discovery (no filtering)
Pass 2: Evidence Verification (STRONG/WEAK/NONE/CONTRADICTED)
Pass 3: Adjudication (precise type selection)

Target facts (from 02_organizational_announcement.md):
  (a) Robert Kim -> President of Nexus Digital Solutions
  (b) Jennifer Walsh -> CISO
  (c) Alan Chen -> VP Engineering

Usage: python scripts/_experiment_3pass.py [doc_path]
"""
import json
import os
import sys
import time
from pathlib import Path
from openai import OpenAI

MODEL = "gpt-4o-mini"
DEFAULT_DOC = "test documents/ClaudeCode_NExus_Industries_corpus/communications/02_organizational_announcement.md"

client = OpenAI()


def llm(system: str, user: str, response_format_json: bool = True) -> dict:
    t0 = time.time()
    kwargs = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
    }
    if response_format_json:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content
    dt = time.time() - t0
    usage = resp.usage
    print(f"  [llm] {dt:.1f}s  prompt={usage.prompt_tokens} completion={usage.completion_tokens}")
    try:
        return json.loads(text), usage
    except json.JSONDecodeError as e:
        print(f"  [llm] JSON parse failed: {e}\n{text[:500]}")
        return {}, usage


# =====================================================================
# PASS 1: Candidate Discovery
# =====================================================================
PASS1_SYSTEM = """You are an aggressive information extractor. Surface EVERY possible
entity and EVERY possible relationship, including ones you are uncertain about. Err
heavily on the side of inclusion. Mark confidence honestly (0-1).

Entity types to consider (non-exhaustive): PERSON, ROLE, ORGANIZATION, BUSINESS_UNIT,
PRODUCT, DATE, EVENT, CERTIFICATION, LOCATION, METRIC, EDUCATION_INSTITUTION.

For relationships, use the most specific verb. Examples: HOLDS_ROLE, FORMERLY_HELD,
REPORTS_TO, APPOINTED_AS, SUCCEEDS, REPLACES, JOINED_AT, PART_OF, ACTING_LEAD_OF,
CERTIFIED_BY, HOLDS_DEGREE_FROM, EFFECTIVE_DATE, MEMBER_OF, OVERSEES.

CRITICAL TABLE RULE - read carefully:
Markdown tables (lines starting with | and separator rows like |---|) are STRUCTURED
DATA. For EVERY data row in EVERY table you MUST emit one relationship hypothesis per
column-pair that asserts a fact. In particular, for tables whose columns are
"Role | Name | Previous Role" (or similar role-assignment shape):
  - For each data row, emit BOTH:
      Person --HOLDS_ROLE--> NewRole
      Person --FORMERLY_HELD--> PreviousRole   (when previous-role column is non-empty
                                                and not "No change")
  - Do this for EVERY row, even if the same person also appears in surrounding prose.
Do NOT skip table rows because they look redundant. Tables are first-class.

Section headers like "### New Leadership Team" frequently introduce such tables.

Output strict JSON with shape:
{
  "entities": [{"name": str, "type": str, "confidence": float}],
  "relationships": [{"source": str, "type": str, "target": str, "confidence": float, "snippet_hint": str}]
}

snippet_hint = a short phrase (3-12 words) from the text that supports the fact.
"""

PASS1_USER_TMPL = """TEXT:
\"\"\"
{text}
\"\"\"

List EVERY possible entity and EVERY possible relationship. Be exhaustive."""


def pass1_discover(text: str) -> dict:
    print("\n=== PASS 1: Candidate Discovery ===")
    out, _ = llm(PASS1_SYSTEM, PASS1_USER_TMPL.format(text=text))
    print(f"  entities: {len(out.get('entities', []))}, relationships: {len(out.get('relationships', []))}")
    return out


# =====================================================================
# PASS 2: Evidence Verification
# =====================================================================
PASS2_SYSTEM = """You are an evidence verifier. For each relationship hypothesis, find
the EXACT sentence (verbatim, full sentence) in the text that proves or disproves it.

Rate evidence_strength as one of:
  STRONG       - sentence directly states the relationship as a fact
  WEAK         - sentence implies it but is ambiguous, partial, or indirect
  NONE         - no sentence supports it
  CONTRADICTED - a sentence directly contradicts it

Output strict JSON:
{
  "verifications": [
    {
      "source": str,
      "type": str,
      "target": str,
      "evidence_strength": "STRONG"|"WEAK"|"NONE"|"CONTRADICTED",
      "evidence_sentence": str,
      "reasoning": str
    }
  ]
}
The order and count of verifications MUST match the input hypotheses exactly."""

PASS2_USER_TMPL = """TEXT:
\"\"\"
{text}
\"\"\"

HYPOTHESES (verify each one):
{hyps}
"""


def pass2_verify(text: str, hypotheses: list) -> dict:
    print("\n=== PASS 2: Evidence Verification ===")
    hyps_str = json.dumps(
        [{"source": h["source"], "type": h["type"], "target": h["target"]} for h in hypotheses],
        indent=2,
    )
    out, _ = llm(PASS2_SYSTEM, PASS2_USER_TMPL.format(text=text, hyps=hyps_str))
    verifications = out.get("verifications", [])
    by_strength = {}
    for v in verifications:
        by_strength.setdefault(v.get("evidence_strength", "?"), 0)
        by_strength[v.get("evidence_strength", "?")] += 1
    print(f"  verified: {len(verifications)}  by strength: {by_strength}")
    return out


# =====================================================================
# PASS 3: Adjudication (precise type selection)
# =====================================================================
PASS3_SYSTEM = """You are an adjudicator. For each STRONG relationship, choose the most
PRECISE relationship type from the controlled vocabulary below. For WEAK, suggest a type
but flag for_review=true. Discard NONE. For CONTRADICTED, set type to null and explain.

Controlled vocabulary (prefer specific over general):
  PERSON-ROLE: HOLDS_ROLE, APPOINTED_AS, FORMERLY_HELD, SUCCEEDS, REPLACES, REPORTS_TO,
               ACTING_LEAD_OF, JOINED_AT, RESIGNED_FROM
  ROLE-ORG:    ROLE_IN, ROLE_OF
  ORG-ORG:     PART_OF, OVERSEES, SUBSIDIARY_OF
  PERSON-ORG:  EMPLOYEE_OF, FORMER_EMPLOYEE_OF
  ORG-PRODUCT: OFFERS, OPERATES
  ORG-CERT:    HOLDS_CERTIFICATION
  PERSON-EDU:  HOLDS_DEGREE_FROM
  EVENT-DATE:  EFFECTIVE_ON, OCCURS_ON
  PERSON-EVENT: HOSTS, ATTENDS

Output strict JSON:
{
  "final": [
    {
      "source": str,
      "target": str,
      "final_type": str | null,
      "evidence_strength": str,
      "evidence_sentence": str,
      "for_review": bool,
      "notes": str
    }
  ]
}"""

PASS3_USER_TMPL = """VERIFIED HYPOTHESES:
{verifs}

For each, pick the most precise type from the controlled vocabulary. Discard NONE."""


def pass3_adjudicate(verifications: list) -> dict:
    print("\n=== PASS 3: Adjudication ===")
    keep = [v for v in verifications if v.get("evidence_strength") in ("STRONG", "WEAK", "CONTRADICTED")]
    print(f"  adjudicating {len(keep)} of {len(verifications)} (dropped NONE)")
    if not keep:
        return {"final": []}
    out, _ = llm(PASS3_SYSTEM, PASS3_USER_TMPL.format(verifs=json.dumps(keep, indent=2)))
    finals = out.get("final", [])
    strong = sum(1 for f in finals if f.get("evidence_strength") == "STRONG")
    weak = sum(1 for f in finals if f.get("for_review"))
    print(f"  finalized: {len(finals)}  strong: {strong}  flagged_for_review: {weak}")
    return out


# =====================================================================
# Target check
# =====================================================================
TARGETS = [
    {"id": "a", "person": "Robert Kim",     "role": "President",     "org_hint": "Nexus Digital Solutions"},
    {"id": "b", "person": "Jennifer Walsh", "role": "CISO",          "org_hint": None},
    {"id": "c", "person": "Alan Chen",      "role": "VP Engineering", "org_hint": None},
]


def _norm(s: str) -> str:
    return (s or "").lower().replace(".", "").replace(",", "").strip()


def check_targets(finals: list) -> dict:
    print("\n=== TARGET CHECK ===")
    results = {}
    for tgt in TARGETS:
        person_n = _norm(tgt["person"])
        role_keywords = _norm(tgt["role"]).split()
        org_n = _norm(tgt["org_hint"]) if tgt["org_hint"] else None
        hits = []
        for f in finals:
            src = _norm(f.get("source", ""))
            tar = _norm(f.get("target", ""))
            ftype = (f.get("final_type") or "").upper()
            # Either side could carry the person; the other side carries role/org
            person_match = person_n in src or person_n in tar
            role_match = all(kw in (src + " " + tar + " " + ftype) for kw in role_keywords)
            org_match = (org_n is None) or (org_n in src or org_n in tar)
            if person_match and role_match and org_match:
                hits.append(f)
        passed = len(hits) > 0
        results[tgt["id"]] = {
            "target": f"{tgt['person']} -> {tgt['role']}" + (f" of {tgt['org_hint']}" if tgt["org_hint"] else ""),
            "passed": passed,
            "hit_count": len(hits),
            "hits": hits[:3],
        }
        mark = "PASS" if passed else "MISS"
        print(f"  [{mark}] ({tgt['id']}) {results[tgt['id']]['target']}  hits={len(hits)}")
        for h in hits[:2]:
            print(f"        {h.get('source')} --[{h.get('final_type')}]--> {h.get('target')}  ({h.get('evidence_strength')})")
            print(f"        evidence: {(h.get('evidence_sentence') or '')[:140]}")
    return results


# =====================================================================
# Main
# =====================================================================
def main():
    doc_path = Path(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DOC)
    text = doc_path.read_text()
    print(f"DOC: {doc_path}  ({len(text)} chars)")
    print(f"MODEL: {MODEL}")

    p1 = pass1_discover(text)
    hyps = p1.get("relationships", [])
    if not hyps:
        print("ERROR: pass 1 produced no relationships; aborting")
        return

    p2 = pass2_verify(text, hyps)
    verifs = p2.get("verifications", [])
    if not verifs:
        print("ERROR: pass 2 produced no verifications; aborting")
        return

    p3 = pass3_adjudicate(verifs)
    finals = p3.get("final", [])

    target_results = check_targets(finals)

    out_path = Path("/tmp/3pass_experiment.json")
    out_path.write_text(json.dumps({
        "doc": str(doc_path),
        "model": MODEL,
        "pass1": p1,
        "pass2": p2,
        "pass3": p3,
        "target_check": target_results,
    }, indent=2))
    passed_count = sum(1 for r in target_results.values() if r["passed"])
    print(f"\n=== RESULT: {passed_count}/3 targets caught ===")
    print(f"Full output: {out_path}")


if __name__ == "__main__":
    main()
