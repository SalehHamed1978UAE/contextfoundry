"""Smoke test: ask gpt-4o-mini, gpt-4o, and claude-sonnet-4 to extract entities/relations
from 02_organizational_announcement.md. Score each on 3 specific role-appointment facts:
  1. Robert Kim → HOLDS_POSITION → President of Nexus Digital Solutions
  2. Jennifer Walsh → HOLDS_POSITION → CISO / Chief Information Security Officer
  3. Dr. Alan Chen → HOLDS_POSITION → VP of Engineering
Writes results to /tmp/smoke_test_models.json
"""
import os, json, re, sys

DOC_PATH = "test documents/ClaudeCode_NExus_Industries_corpus/communications/02_organizational_announcement.md"
TEXT = open(DOC_PATH).read()

SYSTEM = """You are a precise entity and relationship extraction system.

Extract ALL entities and relationships from this organizational announcement.

For EVERY person mentioned with a job title, create a HOLDS_POSITION relationship:
- Person -> HOLDS_POSITION -> Role (e.g., "Robert Kim" -> HOLDS_POSITION -> "President of Nexus Digital Solutions")

For EVERY organization mentioned, create an ORGANIZATION entity.
For EVERY appointment/replacement event, create an EVENT entity.

Output STRICT JSON only:
{
  "entities": [{"name": "...", "entity_type": "PERSON|ORGANIZATION|ROLE|EVENT"}],
  "relations": [{"source": "...", "relation_type": "...", "target": "..."}]
}"""

def call_openai(model):
    from openai import OpenAI
    c = OpenAI()
    kwargs = dict(
        model=model,
        messages=[{"role":"system","content":SYSTEM},{"role":"user","content":TEXT}],
        response_format={"type":"json_object"},
    )
    # gpt-5* family rejects non-default temperature
    if not model.startswith("gpt-5"):
        kwargs["temperature"] = 0
    r = c.chat.completions.create(**kwargs)
    return r.choices[0].message.content

def call_anthropic(model):
    import anthropic
    c = anthropic.Anthropic()
    kwargs = dict(
        model=model, max_tokens=4096,
        system=SYSTEM,
        messages=[{"role":"user","content":TEXT}],
    )
    # claude-opus-4-7 deprecates temperature
    if "opus-4-7" not in model and "opus-4.7" not in model:
        kwargs["temperature"] = 0
    r = c.messages.create(**kwargs)
    txt = r.content[0].text
    # extract JSON if wrapped
    m = re.search(r'\{.*\}', txt, re.DOTALL)
    return m.group(0) if m else txt

def score(payload):
    """Return dict of which target facts were captured."""
    try:
        d = json.loads(payload)
        rels = d.get('relations', [])
    except Exception as e:
        return {"parse_error": str(e), "raw_first_400": payload[:400]}
    def has(rels, src_kw, rel_kws, tgt_kws):
        for r in rels:
            s = (r.get('source','') or '').lower()
            rt = (r.get('relation_type','') or '').lower()
            t = (r.get('target','') or '').lower()
            if any(k in s for k in src_kw) and any(k in rt for k in rel_kws) and any(k in t for k in tgt_kws):
                return f"{r.get('source')} -[{r.get('relation_type')}]-> {r.get('target')}"
        return None
    fact1 = has(rels, ['robert kim'], ['holds_position','position','role','appointed','president_of'], ['president'])
    fact2 = has(rels, ['jennifer walsh'], ['holds_position','position','role','appointed'], ['ciso','chief information security'])
    fact3 = has(rels, ['alan chen'], ['holds_position','position','role','appointed'], ['vp of engineering','vp engineering','vice president of engineering'])
    return {
        "n_entities": len(d.get('entities',[])),
        "n_relations": len(rels),
        "fact1_robert_kim_president": fact1,
        "fact2_jennifer_walsh_ciso": fact2,
        "fact3_alan_chen_vp_eng": fact3,
        "score": sum(1 for x in [fact1,fact2,fact3] if x),
        "all_relations_sample": rels[:30],
    }

def main():
    out = {}
    targets = [
        ("openai", "gpt-4o-mini"),
        ("openai", "gpt-4o"),
        ("openai", "gpt-5.5"),
        ("openai", "gpt-5.5-pro"),
        ("openai", "gpt-5"),
        ("anthropic", "claude-sonnet-4-20250514"),
        ("anthropic", "claude-opus-4-7"),
        ("anthropic", "claude-opus-4-7-20260301"),
    ]
    for vendor, model in targets:
        print(f"\n=== {vendor} :: {model} ===", flush=True)
        try:
            payload = (call_openai if vendor=='openai' else call_anthropic)(model)
            sc = score(payload)
            out[model] = sc
            print(f"  ent={sc.get('n_entities','?')} rel={sc.get('n_relations','?')} score={sc.get('score','?')}/3")
            print(f"  fact1 RobertKim-Pres: {sc.get('fact1_robert_kim_president')}")
            print(f"  fact2 Walsh-CISO:    {sc.get('fact2_jennifer_walsh_ciso')}")
            print(f"  fact3 AlanChen-VPE:  {sc.get('fact3_alan_chen_vp_eng')}")
        except Exception as e:
            out[model] = {"error": str(e)}
            print(f"  ERROR: {e}")
    json.dump(out, open('/tmp/smoke_test_models.json','w'), indent=2, default=str)
    print("\nWrote /tmp/smoke_test_models.json")
    print("\n=== SUMMARY ===")
    for m, sc in out.items():
        if 'error' in sc:
            print(f"  {m}: ERROR {sc['error'][:80]}")
        else:
            print(f"  {m}: score {sc.get('score','?')}/3 (ent={sc.get('n_entities')}, rel={sc.get('n_relations')})")

if __name__ == '__main__':
    main()
