"""Smoke test for the TypeDiscoveryAgent ↔ StagingLoader wiring.

We don't want to invoke the LLM here, so we exercise the wiring directly:
build a StagingLoader, attach a TypeDiscoveryAgent, hand it a synthetic batch
of ExtractedRelation-like objects, and verify the agent's observation_log
captured every relation BEFORE any normalisation or rejection happened.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from context_foundry.discovery.type_discovery_agent import TypeDiscoveryAgent


def main() -> int:
    print("Wiring smoke test: StagingLoader → TypeDiscoveryAgent")

    # We can't construct a real StagingLoader without a DB session, but we
    # only care about the observe-on-load_relations hook. Build a stand-in
    # that mirrors the production hook code path exactly.
    class FakeLoader:
        def __init__(self):
            self._type_discovery_agent = None
            self._type_discovery_doc_type = "unknown"
        # copied from staging_loader.set_type_discovery_agent
        def set_type_discovery_agent(self, agent, document_type="unknown"):
            self._type_discovery_agent = agent
            self._type_discovery_doc_type = document_type or "unknown"
        # mirrors the hook block at the top of staging_loader.load_relations
        def load_relations(self, relations):
            if self._type_discovery_agent is not None and relations:
                self._type_discovery_agent.observe_extraction(
                    relations, document_type=self._type_discovery_doc_type
                )
            # production then iterates and normalises — that's irrelevant
            # to whether the agent saw the raw signal.
            return len(relations)

    agent = TypeDiscoveryAgent(known_types={"HOLDS_POSITION", "WORKS_AT"},
                               min_observations=3)
    loader = FakeLoader()
    loader.set_type_discovery_agent(agent, document_type="communications")

    # Synthetic extraction: 3 PRESIDENT_OF mentions + 3 HAS_BUDGET + 1 known
    rels = [
        SimpleNamespace(raw_relationship_type="PRESIDENT_OF",
                        relation_type="HOLDS_POSITION",
                        source_type="PERSON", target_type="ORGANIZATION",
                        source_span="Sarah Chen, President of Nexus Digital Solutions",
                        confidence=0.95),
        SimpleNamespace(raw_relationship_type="PRESIDENT_OF",
                        relation_type="HOLDS_POSITION",
                        source_type="PERSON", target_type="ORGANIZATION",
                        source_span="Robert Kim, President of Nexus Aerospace Division",
                        confidence=0.93),
        SimpleNamespace(raw_relationship_type="PRESIDENT_OF",
                        relation_type="HOLDS_POSITION",
                        source_type="PERSON", target_type="ORGANIZATION",
                        source_span="Maria Lopez, President of Nexus Energy Systems",
                        confidence=0.91),
        SimpleNamespace(raw_relationship_type="HAS_BUDGET",
                        relation_type="HAS_BUDGET",
                        source_type="PROJECT", target_type="METRIC",
                        source_span="Falcon project has a budget of $50M",
                        confidence=0.9),
        SimpleNamespace(raw_relationship_type="HAS_BUDGET",
                        relation_type="HAS_BUDGET",
                        source_type="PROJECT", target_type="METRIC",
                        source_span="GreenH2 has a budget of $225M",
                        confidence=0.92),
        SimpleNamespace(raw_relationship_type="HAS_BUDGET",
                        relation_type="HAS_BUDGET",
                        source_type="PROJECT", target_type="METRIC",
                        source_span="Apollo has a budget of $80M",
                        confidence=0.88),
        SimpleNamespace(raw_relationship_type="WORKS_AT",
                        relation_type="WORKS_AT",
                        source_type="PERSON", target_type="ORGANIZATION",
                        source_span="Alan Chen works at Nexus",
                        confidence=0.94),
    ]
    loader.load_relations(rels)

    # 1. Agent saw every observation
    assert len(agent.observation_log) == len(rels), (
        f"Hook didn't fire: agent saw {len(agent.observation_log)} of {len(rels)}"
    )
    print(f"  hook fired: {len(agent.observation_log)}/{len(rels)} observations recorded")

    # 2. Discovery surfaces the unmapped patterns
    proposals = {p.proposed_type: p for p in agent.discover_types()}
    print(f"  proposals: {sorted(proposals.keys())}")
    assert "PRESIDENT_OF" in proposals, "PRESIDENT_OF not surfaced"
    assert "HAS_BUDGET" in proposals, "HAS_BUDGET not surfaced"
    assert "WORKS_AT" not in proposals, "WORKS_AT is known and should not be proposed"
    assert proposals["PRESIDENT_OF"].parent_type == "HOLDS_POSITION", \
        "PRESIDENT_OF missing parent_type"
    print("  PRESIDENT_OF parent_type=HOLDS_POSITION: ok")
    print("  HAS_BUDGET surfaced as standalone proposal: ok")
    print("  WORKS_AT (known) correctly excluded: ok")

    print("\nWIRING SMOKE TEST: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
