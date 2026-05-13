"""Unit tests for Stage 2D — DOCUMENT_EVIDENCE fallback.

Covers the 6 minimum tests from the Stage 2D plan plus additional precision
checks for the trigger and provenance plumbing.

These tests do NOT touch the database — they stub the SQLAlchemy session and
the OpenAI client. Integration coverage (real DB, real LLM) is provided by
scripts/run_qonly_direct.py against the Stage 1J vault.
"""
from __future__ import annotations

import os
import sys
import types
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.context_foundry.retrieval.document_evidence_fallback import (  # noqa: E402
    ANSWER_SOURCE_DOCUMENT_EVIDENCE,
    ANSWER_SOURCE_TRUSTED_GRAPH,
    EvidenceChunk,
    FallbackResult,
    attempt_document_evidence_fallback,
    find_evidence_chunks,
    is_attribute_query,
    looks_like_no_data,
    synthesize_from_chunks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Row:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _stub_session(rows):
    session = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = rows
    session.execute.return_value = result
    return session


def _stub_openai(answer_text: str):
    client = MagicMock()
    msg = MagicMock()
    msg.content = answer_text
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    client.chat.completions.create.return_value = completion
    return client


def _row(chunk_id="c1", document_id="d1", title="Doc One", chunk_index=0,
         char_start=0, char_end=100, text=""):
    return _Row(chunk_id=chunk_id, document_id=document_id,
                document_title=title, chunk_index=chunk_index,
                char_start=char_start, char_end=char_end, text=text)


# ---------------------------------------------------------------------------
# is_attribute_query / looks_like_no_data
# ---------------------------------------------------------------------------

def test_is_attribute_query_money():
    assert is_attribute_query("What is the total company backlog?") == "money"

def test_is_attribute_query_date():
    assert is_attribute_query("When was Michael Chang appointed?") == "date"

def test_is_attribute_query_spec():
    assert is_attribute_query("How many qubits does the platform have?") == "spec"

def test_is_attribute_query_certification():
    assert is_attribute_query("Is the platform FedRAMP certified?") == "certification"

def test_is_attribute_query_credential():
    assert is_attribute_query("Where did Victoria Chen get her degree?") == "credential"

def test_is_attribute_query_returns_none_for_role():
    assert is_attribute_query("Who is the CEO of Nexus Industries?") is None

def test_is_attribute_query_returns_none_for_relationship():
    assert is_attribute_query("Does Nexus partner with Boeing?") is None

def test_is_attribute_query_handles_empty():
    assert is_attribute_query("") is None
    assert is_attribute_query(None) is None  # type: ignore[arg-type]

def test_looks_like_no_data_dont_know():
    assert looks_like_no_data("I don't have enough information to answer this.")

def test_looks_like_no_data_couldnt_find():
    assert looks_like_no_data("I couldn't find that in the knowledge base.")

def test_looks_like_no_data_unknown():
    assert looks_like_no_data("Unknown.")

def test_looks_like_no_data_real_answer_returns_false():
    assert not looks_like_no_data("The total backlog is $12.4 billion.")

def test_looks_like_no_data_empty_string_is_no_data():
    assert looks_like_no_data("")
    assert looks_like_no_data(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# find_evidence_chunks (tenant-scoped, ranked, deterministic)
# ---------------------------------------------------------------------------

def test_find_evidence_chunks_returns_top_k_by_overlap():
    rows = [
        _row(chunk_id="c1", text="The total company backlog is $12.4 billion."),
        _row(chunk_id="c2", text="Backlog and revenue both grew."),
        _row(chunk_id="c3", text="Unrelated content about hiring."),
        _row(chunk_id="c4", text="Backlog of $12.4 billion was reported in Q3."),
    ]
    session = _stub_session(rows)
    chunks = find_evidence_chunks(session, "tenant-x", "What is the total company backlog?", top_k=3)
    # c3 has zero overlap and must be excluded.
    ids = [c.chunk_id for c in chunks]
    assert "c3" not in ids
    assert len(chunks) <= 3
    assert chunks[0].overlap_score >= chunks[-1].overlap_score


def test_find_evidence_chunks_returns_empty_for_empty_tokens():
    session = _stub_session([])
    chunks = find_evidence_chunks(session, "tenant-x", "the a an", top_k=5)
    assert chunks == []


def test_find_evidence_chunks_passes_tenant_id_to_sql():
    rows = [_row(chunk_id="c1", text="qubits 1024")]
    session = _stub_session(rows)
    find_evidence_chunks(session, "tenant-abc", "How many qubits?", top_k=5)
    call_kwargs = session.execute.call_args
    bound_params = call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs
    assert bound_params["tid"] == "tenant-abc"


# ---------------------------------------------------------------------------
# synthesize_from_chunks
# ---------------------------------------------------------------------------

def test_synthesize_returns_llm_answer():
    chunk = EvidenceChunk(chunk_id="c1", document_id="d1", document_title="Doc",
                          chunk_index=0, char_start=0, char_end=10, text="qubits 1024",
                          overlap_score=2.0)
    client = _stub_openai("1024 qubits.")
    result = synthesize_from_chunks("How many qubits?", [chunk], openai_client=client)
    assert result == "1024 qubits."


def test_synthesize_returns_none_for_NOT_IN_DOCUMENTS():
    chunk = EvidenceChunk(chunk_id="c1", document_id="d1", document_title="Doc",
                          chunk_index=0, char_start=0, char_end=10, text="...",
                          overlap_score=1.0)
    client = _stub_openai("NOT_IN_DOCUMENTS")
    result = synthesize_from_chunks("Random question?", [chunk], openai_client=client)
    assert result is None


def test_synthesize_returns_none_for_empty_chunks():
    client = _stub_openai("anything")
    assert synthesize_from_chunks("Q?", [], openai_client=client) is None


# ---------------------------------------------------------------------------
# attempt_document_evidence_fallback orchestrator
# ---------------------------------------------------------------------------

def test_orchestrator_does_not_fire_when_kg_has_trusted_answer():
    """Plan test 1: TRUSTED graph fact wins; fallback not used."""
    session = _stub_session([_row(chunk_id="c1", text="backlog of $12.4 billion")])
    client = _stub_openai("$12.4 billion")
    result = attempt_document_evidence_fallback(
        session, "tenant-x", "What is the total company backlog?",
        kg_answer="The total backlog is $12.4 billion.",
        kg_answer_source=ANSWER_SOURCE_TRUSTED_GRAPH,
        openai_client=client,
    )
    assert result is None
    session.execute.assert_not_called()


def test_orchestrator_fires_when_kg_says_dont_know_and_chunks_have_answer():
    """Plan test 2: KG no_data + chunks contain answer → DOCUMENT_EVIDENCE."""
    session = _stub_session([_row(chunk_id="c1", text="backlog of $12.4 billion")])
    client = _stub_openai("The total backlog is $12.4 billion.")
    result = attempt_document_evidence_fallback(
        session, "tenant-x", "What is the total company backlog?",
        kg_answer="I don't have that information.",
        kg_answer_source=None,
        openai_client=client,
    )
    assert result is not None
    assert isinstance(result, FallbackResult)
    assert result.answer_source == ANSWER_SOURCE_DOCUMENT_EVIDENCE
    assert result.attribute_category == "money"
    assert len(result.chunks) >= 1
    assert len(result.citations) >= 1
    assert "12.4 billion" in result.answer
    assert all("chunk_id" in c and "document_id" in c for c in result.citations)


def test_orchestrator_returns_none_when_neither_kg_nor_chunks_have_answer():
    """Plan test 3: KG no_data + chunks empty → caller sees GAP."""
    session = _stub_session([])  # no chunks
    client = _stub_openai("anything")
    result = attempt_document_evidence_fallback(
        session, "tenant-x", "What is the total company backlog?",
        kg_answer="I don't know.",
        kg_answer_source=None,
        openai_client=client,
    )
    assert result is None


def test_orchestrator_returns_none_when_llm_says_NOT_IN_DOCUMENTS():
    """Plan test 3 variant: chunks present but LLM cannot ground answer → GAP."""
    session = _stub_session([_row(chunk_id="c1", text="unrelated content")])
    client = _stub_openai("NOT_IN_DOCUMENTS")
    result = attempt_document_evidence_fallback(
        session, "tenant-x", "What is the total company backlog?",
        kg_answer="I don't know.",
        kg_answer_source=None,
        openai_client=client,
    )
    assert result is None


def test_orchestrator_does_not_fire_for_non_attribute_query():
    """Fallback is conservative — non-attribute queries are skipped entirely."""
    session = _stub_session([_row(chunk_id="c1", text="anything")])
    client = _stub_openai("an answer")
    result = attempt_document_evidence_fallback(
        session, "tenant-x", "Who is the CEO of Nexus Industries?",
        kg_answer="I don't know.",
        kg_answer_source=None,
        openai_client=client,
    )
    assert result is None


def test_orchestrator_is_tenant_scoped():
    """Plan test 4: every SQL call carries tenant_id."""
    session = _stub_session([_row(chunk_id="c1", text="qubits 1024")])
    client = _stub_openai("1024 qubits.")
    result = attempt_document_evidence_fallback(
        session, "tenant-XYZ", "How many qubits in the platform?",
        kg_answer="I don't know.",
        kg_answer_source=None,
        openai_client=client,
    )
    assert result is not None
    bound = session.execute.call_args.args[1] if len(session.execute.call_args.args) > 1 \
        else session.execute.call_args.kwargs
    assert bound["tid"] == "tenant-XYZ"


def test_orchestrator_does_not_mutate_session():
    """Plan test 5: fallback never writes — only .execute() (SELECT) is called."""
    session = _stub_session([_row(chunk_id="c1", text="qubits 1024")])
    client = _stub_openai("1024 qubits.")
    attempt_document_evidence_fallback(
        session, "tenant-x", "How many qubits?",
        kg_answer="I don't know.",
        kg_answer_source=None,
        openai_client=client,
    )
    # No .add(), .commit(), .delete(), .merge(), .flush() should be invoked.
    for method in ("add", "add_all", "commit", "delete", "merge", "flush"):
        assert not getattr(session, method).called, f"session.{method}() must not be called"


def test_orchestrator_carries_provenance_on_every_citation():
    session = _stub_session([
        _row(chunk_id="c1", document_id="d1", title="Backlog Report",
             chunk_index=2, char_start=100, char_end=300,
             text="The total backlog is $12.4 billion as of Q3."),
    ])
    client = _stub_openai("$12.4 billion")
    result = attempt_document_evidence_fallback(
        session, "tenant-x", "What is the total company backlog?",
        kg_answer="I don't have that.",
        kg_answer_source=None,
        openai_client=client,
    )
    assert result is not None
    cit = result.citations[0]
    assert cit["chunk_id"] == "c1"
    assert cit["document_id"] == "d1"
    assert cit["document_title"] == "Backlog Report"
    assert cit["chunk_index"] == 2
    assert cit["char_start"] == 100
    assert cit["char_end"] == 300
    assert "12.4 billion" in cit["snippet"]


# ---------------------------------------------------------------------------
# Plan test 6 — tree retrieval default
# ---------------------------------------------------------------------------

def test_tree_default_is_false_in_test_runner():
    """Stage 2D Part A: env-default for CF_TREE_BASED_RETRIEVAL must be 'false'."""
    runner_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "src", "test_runner", "runner.py"
    )
    with open(runner_path) as f:
        body = f.read()
    # Both env reads must default to "false".
    occurrences = body.count('os.environ.get("CF_TREE_BASED_RETRIEVAL", "false")')
    assert occurrences >= 2, (
        f"runner.py should default CF_TREE_BASED_RETRIEVAL to 'false' "
        f"in both call sites; found {occurrences}"
    )
    assert 'os.environ.get("CF_TREE_BASED_RETRIEVAL", "true")' not in body, (
        "runner.py must not retain any 'true' default for CF_TREE_BASED_RETRIEVAL"
    )

    executor_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "src", "test_runner", "test_executor.py"
    )
    with open(executor_path) as f:
        body = f.read()
    assert 'os.environ.get("CF_TREE_BASED_RETRIEVAL", "false")' in body
    assert 'os.environ.get("CF_TREE_BASED_RETRIEVAL", "true")' not in body

    start_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "start.sh")
    with open(start_path) as f:
        body = f.read()
    assert "export CF_TREE_BASED_RETRIEVAL=false" in body
    assert "export CF_TREE_BASED_RETRIEVAL=true" not in body


def test_per_request_override_still_works_for_true():
    """Plan test 6: explicit override paths are unchanged."""
    # ToolAgent.query accepts tree_based_retrieval=Optional[bool] — a True value
    # forwards through QueryPipeline.process. We assert the parameter exists
    # and is forwarded by inspecting the source.
    agent_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "src", "context_foundry", "agents", "tool_agent.py"
    )
    with open(agent_path) as f:
        body = f.read()
    assert "tree_based_retrieval: Optional[bool] = None" in body
    assert "tree_based_retrieval=tree_based_retrieval" in body
