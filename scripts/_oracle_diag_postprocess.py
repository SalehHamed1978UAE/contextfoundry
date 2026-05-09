"""Post-process the diagnostic oracle run log into per-question diag records.

The runner's _CounterCapture is a no-op in this code path because structlog's
filtering bound logger writes directly to stderr (it doesn't route through the
stdlib `cf.inference` logger). The events are in the log file (tee'd from the
runner's stderr); we parse them here and emit a per-question diag table.

Usage:
    python -u scripts/_oracle_diag_postprocess.py \
        --log  test_results/v2_parallel/oracle_vector_clean_20260509.log \
        --jsonl test_results/v2_parallel/oracle_vector_clean_20260509.jsonl
"""
from __future__ import annotations
import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path

QMARK_RE = re.compile(r"--- Q(\d+) \(\d+/\d+\) — elapsed=")

def parse_log(log_path: Path):
    """Return a dict {qid: [event_dict, ...]}."""
    by_q: dict[int, list[dict]] = defaultdict(list)
    cur_qid: int | None = None
    with open(log_path) as f:
        for line in f:
            m = QMARK_RE.search(line)
            if m:
                cur_qid = int(m.group(1))
                continue
            # Trace events are JSON dicts on their own line (structlog JSONRenderer
            # sends them straight to stderr, prefixed by nothing).
            line = line.strip()
            if not (line.startswith("{") and '"event"' in line):
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if cur_qid is not None:
                by_q[cur_qid].append(ev)
    return by_q


def diag_for_question(qid: int, events: list[dict], rec: dict) -> dict:
    pol_dist = {"confirms": 0, "disconfirms": 0, "neutral": 0, "unset": 0}
    strat_totals = {"graph_endpoint": 0, "fts_chunks": 0,
                    "vector_chunks": 0, "vector_entities_to_rels": 0}
    diag = {
        "qid": qid,
        "question": rec.get("question"),
        "expected": rec.get("expected"),
        "extractable": rec.get("v2_extractable"),
        "v2_status": rec.get("v2_status"),
        "v2_correct": rec.get("v2_correct"),
        "wall_seconds": rec.get("v2_wall_time_s"),
        "subject_id": rec.get("v2_subject_id"),
        "target_id": rec.get("v2_target_id"),
        "rel_type": rec.get("v2_relationship_type"),
        "trace_count": 0,
        "depth0_trace_id": None,
        "planner_reached": False,
        "plan_hash": None,
        "presupposition_count": 0,
        "evidence_query_count": 0,
        "falsifier_count": 0,
        "presupposition_results": [],
        "any_presupposition_disproven": False,
        "gather_reached": False,
        "chunks_retrieved": 0,
        "chunks_passed_to_polarity": 0,
        "polarity_distribution": pol_dist,
        "gatherer_strategy_counts": strat_totals,
        "planner_llm_calls": 0,
        "planner_llm_misses": 0,
        "planner_llm_hits": 0,
        "gatherer_llm_calls": 0,
        "gatherer_llm_misses": 0,
        "gatherer_llm_hits": 0,
        "prover_llm_calls": 0,
        "prover_llm_misses": 0,
        "prover_llm_hits": 0,
        "adversary_llm_calls": 0,
        "spans_seen": defaultdict(int),
        "events_seen": defaultdict(int),
    }
    # Identify the depth-0 trace_id (each question opens exactly one root trace
    # via tracer.trace(); recursive evaluates open NEW trace_ids).
    depth0_trace = None
    for ev in events:
        if ev.get("event") == "trace_start" and ev.get("depth", -1) == 0:
            depth0_trace = ev.get("trace_id")
            break
    diag["depth0_trace_id"] = depth0_trace
    diag["trace_count"] = sum(1 for ev in events if ev.get("event") == "trace_start")

    for ev in events:
        et = ev.get("event")
        diag["events_seen"][et] += 1
        # Restrict aggregations to the depth-0 root trace so recursive
        # presupposition evaluates don't pollute totals.
        if depth0_trace and ev.get("trace_id") != depth0_trace:
            continue
        if et == "planner_complete" and ev.get("depth", 0) == 0:
            diag["planner_reached"] = True
            diag["plan_hash"] = ev.get("plan_hash")
            diag["presupposition_count"] = ev.get("presupposition_count", 0)
            diag["evidence_query_count"] = ev.get("evidence_query_count", 0)
            diag["falsifier_count"] = ev.get("falsifier_count", 0)
        elif et == "presuppositions_complete" and ev.get("depth", 0) == 0:
            diag["presupposition_results"] = ev.get("results", [])
            diag["any_presupposition_disproven"] = bool(ev.get("any_disproven"))
        elif et == "evidence_query_results":
            diag["gather_reached"] = True
            for s in ev.get("strategies", []):
                name = s.get("strategy")
                if name in strat_totals:
                    strat_totals[name] += s.get("items_returned", 0)
        elif et == "evidence_gathered" and ev.get("depth", 0) == 0:
            diag["chunks_retrieved"] = ev.get("count", 0)
        elif et == "polarity_classified":
            diag["chunks_passed_to_polarity"] += 1
            pol = ev.get("polarity") or "unset"
            pol_dist[pol] = pol_dist.get(pol, 0) + 1
        elif et == "span_end":
            stage = ev.get("stage")
            diag["spans_seen"][stage] += 1
            calls = ev.get("llm_call_count", 0) or 0
            misses = ev.get("llm_cache_miss_count", 0) or 0
            hits = ev.get("llm_cache_hit_count", 0) or 0
            if stage == "planner":
                diag["planner_llm_calls"] += calls
                diag["planner_llm_misses"] += misses
                diag["planner_llm_hits"] += hits
            elif stage == "gatherer":
                diag["gatherer_llm_calls"] += calls
                diag["gatherer_llm_misses"] += misses
                diag["gatherer_llm_hits"] += hits
            elif stage == "prover":
                diag["prover_llm_calls"] += calls
                diag["prover_llm_misses"] += misses
                diag["prover_llm_hits"] += hits
            elif stage == "adversary":
                diag["adversary_llm_calls"] += calls

    diag["spans_seen"] = dict(diag["spans_seen"])
    diag["events_seen"] = dict(diag["events_seen"])
    diag["case_classification"] = classify(diag, rec)
    return diag


def classify(d: dict, rec: dict) -> str:
    if rec.get("v2_timeout"):
        return "INFRA_TIMEOUT_CANCELLATION_FAILURE"
    if rec.get("v2_status") in ("PROVEN", "STRONGLY_SUPPORTED", "SUPPORTED"):
        return "VECTOR_GATHERER_RECOVERY"
    # Planner reached but gatherer NEVER opened? presupposition gate.
    if d["planner_reached"] and not d["gather_reached"]:
        return "GAP_PLANNER_PRESUPPOSITION_GATE"
    # Vector retrieved chunks but polarity got nothing.
    new_chunks = (d["gatherer_strategy_counts"]["vector_chunks"]
                  + d["gatherer_strategy_counts"]["vector_entities_to_rels"])
    pol_total = sum(d["polarity_distribution"].values())
    if d["gather_reached"] and new_chunks > 0 and pol_total == 0:
        return "GAP_EVIDENCE_PIPELINE_DISCONNECT"
    if d["gather_reached"] and pol_total > 0 and rec.get("v2_status") in (
        "UNDERSPECIFIED", "UNDERSUPPORTED", "UNKNOWN", "DISPROVEN", "CONTESTED",
    ):
        return "GAP_EVALUATOR_REASONING_OR_PROMPT"
    return "UNCLASSIFIED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--jsonl", required=True)
    args = ap.parse_args()

    by_q = parse_log(Path(args.log))
    recs = [json.loads(l) for l in open(args.jsonl) if l.strip()]
    recs = [r for r in recs if "_summary" not in r]

    print("=" * 100)
    print(f"Diagnostic oracle post-process — {len(recs)} questions, "
          f"{sum(len(v) for v in by_q.values())} trace events parsed from log")
    print("=" * 100)

    case_tally: dict[str, list[int]] = defaultdict(list)
    for rec in recs:
        qid = int(rec["q"])
        events = by_q.get(qid, [])
        diag = diag_for_question(qid, events, rec)
        case_tally[diag["case_classification"]].append(qid)
        print()
        print(f"--- Q{qid} ({diag['case_classification']}) ---")
        print(f"  question: {diag['question']}")
        print(f"  expected: {diag['expected']!r}")
        print(f"  v2_status={diag['v2_status']}  correct={diag['v2_correct']}  "
              f"wall={diag['wall_seconds']}s  trace_count={diag['trace_count']}")
        print(f"  candidate fact: {diag['subject_id'][:8] if diag['subject_id'] else None} "
              f"--{diag['rel_type']}--> {diag['target_id'][:8] if diag['target_id'] else None}")
        print(f"  spans_seen: {diag['spans_seen']}")
        print(f"  events: planner_complete={diag['events_seen'].get('planner_complete', 0)} "
              f"presuppositions_complete={diag['events_seen'].get('presuppositions_complete', 0)} "
              f"evidence_query_results={diag['events_seen'].get('evidence_query_results', 0)} "
              f"polarity_classified={diag['events_seen'].get('polarity_classified', 0)} "
              f"evidence_gathered={diag['events_seen'].get('evidence_gathered', 0)}")
        print(f"  PLANNER: reached={diag['planner_reached']} hash={diag['plan_hash']} "
              f"presup={diag['presupposition_count']} ev_q={diag['evidence_query_count']} "
              f"falsif={diag['falsifier_count']} llm_calls={diag['planner_llm_calls']} "
              f"miss/hit={diag['planner_llm_misses']}/{diag['planner_llm_hits']}")
        if diag["presupposition_results"]:
            print(f"  PRESUPPOSITIONS (any_disproven={diag['any_presupposition_disproven']}):")
            for pr in diag["presupposition_results"]:
                fk = pr.get("fact_key") or ""
                print(f"     {pr.get('kind'):<14} {pr.get('status'):<14}  {fk[:80]}")
        print(f"  GATHER: reached={diag['gather_reached']} chunks_retrieved={diag['chunks_retrieved']} "
              f"polarity_total={diag['chunks_passed_to_polarity']} "
              f"llm_calls={diag['gatherer_llm_calls']} miss/hit="
              f"{diag['gatherer_llm_misses']}/{diag['gatherer_llm_hits']}")
        print(f"     strategies: {diag['gatherer_strategy_counts']}")
        print(f"     polarity:   {diag['polarity_distribution']}")
        print(f"  PROVER:    llm_calls={diag['prover_llm_calls']} "
              f"miss/hit={diag['prover_llm_misses']}/{diag['prover_llm_hits']}")
        print(f"  ADVERSARY: llm_calls={diag['adversary_llm_calls']}")

    print()
    print("=" * 100)
    print("CASE TALLY:")
    for k, qs in sorted(case_tally.items()):
        print(f"  {k:<42} ({len(qs)}):  {qs}")
    print("=" * 100)


if __name__ == "__main__":
    main()
