"""
Stage 1K — VerificationWorker deadlock-fix regression tests.

Targeted tests for the smallest-fix changes in
``src/context_foundry/workers/verification_worker.py``:

1. Per-batch commit (not one final commit at the end of the run).
2. Deterministic ordering of facts before processing (so concurrent workers
   acquire row locks in the same sequence).
3. ``session.no_autoflush`` wrapping the read-before-write section that
   originally triggered the autoflush race.
4. Bounded deadlock retry on per-batch commit, with exponential backoff,
   logged.
5. A failed batch commit does not roll back successfully-committed earlier
   batches.
6. Tenant scoping is preserved (the worker still filters EvidenceRecord by
   tenant_id when one is supplied).

These tests use stubs — they intentionally do NOT require a live database,
LLM, or true concurrent transactions, because the brief's acceptance bar is
"transaction-order regression test, deterministic batch ordering test, small
integration smoke" when a true deadlock cannot be unit-tested.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from src.context_foundry.workers.verification_worker import (
    VerificationConfig,
    VerificationResult,
    VerificationWorker,
)
from src.context_foundry.models.schema import (
    FactType,
    VerificationStatus,
)


# ---------------------------------------------------------------------------
# Fake session that records ordering, autoflush state, and commit attempts.
# ---------------------------------------------------------------------------


@dataclass
class FakeEvidenceRecord:
    fact_id: uuid.UUID
    fact_type: FactType
    evidence_text: str = "evidence text"
    tenant_id: Optional[uuid.UUID] = None


class FakeQuery:
    def __init__(self, session: "FakeSession", model_name: str):
        self.session = session
        self.model_name = model_name
        self._filters: List[Any] = []
        self._limit: Optional[int] = None

    def filter(self, *args, **kwargs):
        # Track that a query happened — the original bug was that this
        # triggered an autoflush mid-loop.
        self.session.query_count += 1
        self.session.last_query_was_autoflushable = (
            not self.session._no_autoflush_depth > 0
        )
        return self

    def limit(self, n):
        self._limit = n
        return self

    def all(self):
        return self.session.evidence_records[: (self._limit or len(self.session.evidence_records))]

    def first(self):
        # Simulate "no existing FactVerification row" — branch we want to test.
        return None


class FakeNoAutoflushCM:
    def __init__(self, session: "FakeSession"):
        self.session = session

    def __enter__(self):
        self.session._no_autoflush_depth += 1
        self.session.entered_no_autoflush_count += 1
        return self.session

    def __exit__(self, exc_type, exc, tb):
        self.session._no_autoflush_depth -= 1
        return False


class FakeSession:
    def __init__(
        self,
        evidence_records: List[FakeEvidenceRecord],
        commit_outcomes: Optional[List[Optional[Exception]]] = None,
    ):
        self.evidence_records = evidence_records
        # If commit_outcomes[i] is an Exception, raise on the (i+1)-th commit.
        self.commit_outcomes: List[Optional[Exception]] = commit_outcomes or []
        self.commit_calls = 0
        self.rollback_calls = 0
        self.add_calls: List[Any] = []
        self.query_count = 0
        self.last_query_was_autoflushable = False
        self._no_autoflush_depth = 0
        self.entered_no_autoflush_count = 0

    @property
    def no_autoflush(self):
        return FakeNoAutoflushCM(self)

    def query(self, model):
        return FakeQuery(self, getattr(model, "__name__", str(model)))

    def add(self, obj):
        self.add_calls.append(obj)

    def commit(self):
        idx = self.commit_calls
        self.commit_calls += 1
        if idx < len(self.commit_outcomes) and self.commit_outcomes[idx] is not None:
            raise self.commit_outcomes[idx]

    def rollback(self):
        self.rollback_calls += 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_worker(
    session: FakeSession,
    config: Optional[VerificationConfig] = None,
    tenant_id: Optional[str] = None,
) -> VerificationWorker:
    """Construct a VerificationWorker without touching OpenAI."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
        with patch("src.context_foundry.workers.verification_worker.OpenAI") as openai_cls:
            openai_cls.return_value = MagicMock()
            worker = VerificationWorker(
                session=session,
                tenant_id=tenant_id,
                config=config or VerificationConfig(batch_size=2, max_facts_per_run=10),
            )
    return worker


def _stub_get_unverified_facts(worker: VerificationWorker, evidence_records: List[FakeEvidenceRecord]):
    """Bypass the real DB query path; return fake fact dicts."""
    fact_dicts = []
    for er in evidence_records:
        info_type = "entity" if er.fact_type == FactType.ENTITY else "relationship"
        fact_dicts.append(
            {
                "evidence_record": er,
                "fact_info": {
                    "type": info_type,
                    "description": f"{info_type} {er.fact_id}",
                    "name": str(er.fact_id),
                    "model": MagicMock(verified=False, evidence_verification_status=None),
                },
            }
        )
    worker._get_unverified_facts = lambda limit: fact_dicts  # type: ignore[assignment]


def _stub_process_batch(worker: VerificationWorker, status: VerificationStatus = VerificationStatus.VERIFIED):
    """Skip the LLM. Mark every fact in the batch as ``status``."""
    def _fn(batch: List[Dict[str, Any]]) -> List[VerificationResult]:
        return [
            VerificationResult(
                fact_id=item["evidence_record"].fact_id,
                fact_type=item["evidence_record"].fact_type,
                status=status,
                reason="stub",
                confidence=0.9,
            )
            for item in batch
        ]
    worker._process_batch = _fn  # type: ignore[assignment]


def _stub_update_fact_status(worker: VerificationWorker):
    """Skip the entity/relationship lookup; just record what would be updated."""
    worker._update_fact_status = lambda result: None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Test 1: deterministic ordering before processing
# ---------------------------------------------------------------------------


def test_facts_are_processed_in_deterministic_pk_order():
    """Stage 1K: facts must be sorted by (fact_type, fact_id) so any two
    concurrent workers serialize on the same lock order."""
    # Intentionally shuffled UUIDs.
    ids = [
        uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        uuid.UUID("00000000-0000-0000-0000-000000000001"),
        uuid.UUID("88888888-8888-8888-8888-888888888888"),
        uuid.UUID("11111111-1111-1111-1111-111111111111"),
    ]
    records = [FakeEvidenceRecord(fact_id=i, fact_type=FactType.ENTITY) for i in ids]

    session = FakeSession(evidence_records=records)
    worker = _make_worker(session, config=VerificationConfig(batch_size=10, max_facts_per_run=10))
    _stub_get_unverified_facts(worker, records)
    _stub_update_fact_status(worker)

    seen_order: List[uuid.UUID] = []

    def _record_batch(batch):
        for item in batch:
            seen_order.append(item["evidence_record"].fact_id)
        return [
            VerificationResult(
                fact_id=item["evidence_record"].fact_id,
                fact_type=item["evidence_record"].fact_type,
                status=VerificationStatus.VERIFIED,
                reason="stub",
                confidence=0.9,
            )
            for item in batch
        ]
    worker._process_batch = _record_batch  # type: ignore[assignment]

    worker.run()

    assert seen_order == sorted(ids, key=str), (
        f"Facts must be processed in sorted-by-pk order, got {seen_order}"
    )


# ---------------------------------------------------------------------------
# Test 2: per-batch commit (not one final commit)
# ---------------------------------------------------------------------------


def test_commits_per_batch_not_once_at_end():
    """Stage 1K: with batch_size=2 and 5 facts, we must see 3 commits
    (not the original 1)."""
    records = [
        FakeEvidenceRecord(fact_id=uuid.uuid4(), fact_type=FactType.ENTITY) for _ in range(5)
    ]
    session = FakeSession(evidence_records=records)
    worker = _make_worker(session, config=VerificationConfig(batch_size=2, max_facts_per_run=10))
    _stub_get_unverified_facts(worker, records)
    _stub_process_batch(worker)
    _stub_update_fact_status(worker)

    stats = worker.run()

    assert session.commit_calls == 3, f"Expected 3 batch commits, got {session.commit_calls}"
    assert stats["facts_processed"] == 5
    assert stats["verified"] == 5
    assert stats["errors"] == 0


# ---------------------------------------------------------------------------
# Test 3: no_autoflush wraps the read-before-write section
# ---------------------------------------------------------------------------


def test_store_verdict_runs_inside_no_autoflush_block():
    """Stage 1K: every batch must enter the no_autoflush context manager
    BEFORE _store_verdict's internal query() runs. This is the autoflush
    race that originally caused the deadlock."""
    records = [FakeEvidenceRecord(fact_id=uuid.uuid4(), fact_type=FactType.ENTITY) for _ in range(3)]
    session = FakeSession(evidence_records=records)
    worker = _make_worker(session, config=VerificationConfig(batch_size=10, max_facts_per_run=10))
    _stub_get_unverified_facts(worker, records)
    _stub_process_batch(worker)
    _stub_update_fact_status(worker)

    worker.run()

    # The session's query() inside _store_verdict ran 3 times (once per fact),
    # and every single one must have observed _no_autoflush_depth > 0
    # (i.e., last_query_was_autoflushable=False after the loop).
    assert session.entered_no_autoflush_count == 1, (
        f"Expected exactly one no_autoflush block per batch, got {session.entered_no_autoflush_count}"
    )
    assert session.query_count >= 3
    assert session.last_query_was_autoflushable is False


# ---------------------------------------------------------------------------
# Test 4: bounded deadlock retry on commit succeeds on retry
# ---------------------------------------------------------------------------


def _make_deadlock_error() -> OperationalError:
    """Build an OperationalError whose message contains 'deadlock'."""
    orig = type("FakeOrig", (Exception,), {"pgcode": "40P01"})("deadlock detected")
    return OperationalError("UPDATE entities ...", {}, orig)


def test_batch_retries_on_deadlock_and_succeeds():
    """Stage 1K: a deadlock on commit triggers retry with backoff; on success
    the batch is reported as committed and stats are accurate."""
    records = [FakeEvidenceRecord(fact_id=uuid.uuid4(), fact_type=FactType.ENTITY) for _ in range(2)]
    # First commit raises deadlock, second succeeds.
    session = FakeSession(
        evidence_records=records,
        commit_outcomes=[_make_deadlock_error(), None],
    )
    worker = _make_worker(
        session,
        config=VerificationConfig(
            batch_size=2,
            max_facts_per_run=10,
            deadlock_max_retries=3,
            deadlock_initial_backoff_s=0.0,  # no real sleep in tests
        ),
    )
    _stub_get_unverified_facts(worker, records)
    _stub_process_batch(worker)
    _stub_update_fact_status(worker)

    stats = worker.run()

    assert session.commit_calls == 2
    assert session.rollback_calls == 1
    assert stats["facts_processed"] == 2
    assert stats["verified"] == 2
    assert stats["errors"] == 0


# ---------------------------------------------------------------------------
# Test 5: deadlock retry is bounded (does not loop forever)
# ---------------------------------------------------------------------------


def test_batch_deadlock_retry_is_bounded():
    """Stage 1K: deadlocks beyond the retry budget cause the worker to abort
    that batch (not infinite-loop) and report errors. Earlier successful
    batches are NOT rolled back."""
    records = [FakeEvidenceRecord(fact_id=uuid.uuid4(), fact_type=FactType.ENTITY) for _ in range(4)]
    # Batch 1 (2 facts) — commits fine. Batch 2 (2 facts) — every retry deadlocks.
    session = FakeSession(
        evidence_records=records,
        commit_outcomes=[
            None,
            _make_deadlock_error(),
            _make_deadlock_error(),
            _make_deadlock_error(),
            _make_deadlock_error(),  # one extra, just in case
        ],
    )
    worker = _make_worker(
        session,
        config=VerificationConfig(
            batch_size=2,
            max_facts_per_run=10,
            deadlock_max_retries=3,
            deadlock_initial_backoff_s=0.0,
        ),
    )
    _stub_get_unverified_facts(worker, records)
    _stub_process_batch(worker)
    _stub_update_fact_status(worker)

    stats = worker.run()

    # Initial attempt + 3 retries = 4 commit attempts on batch 2, plus 1 success
    # on batch 1 = 5 total commit() calls.
    assert session.commit_calls == 5, f"Expected 5 commit attempts, got {session.commit_calls}"
    assert session.rollback_calls == 4, f"Expected 4 rollbacks, got {session.rollback_calls}"
    # Batch 1 succeeded → 2 facts persisted; batch 2 aborted → 0.
    assert stats["facts_processed"] == 2
    assert stats["verified"] == 2
    assert stats["errors"] == 1


# ---------------------------------------------------------------------------
# Test 6: non-deadlock OperationalError is reported and does not silently retry
# ---------------------------------------------------------------------------


def test_non_deadlock_operational_error_is_not_retried():
    """Stage 1K: only true deadlocks are retried; other OperationalErrors
    (e.g., connection lost) are reported immediately."""
    records = [FakeEvidenceRecord(fact_id=uuid.uuid4(), fact_type=FactType.ENTITY)]
    other_orig = type("FakeOrig", (Exception,), {"pgcode": "08006"})("connection failure")
    err = OperationalError("UPDATE entities ...", {}, other_orig)
    session = FakeSession(evidence_records=records, commit_outcomes=[err])
    worker = _make_worker(
        session,
        config=VerificationConfig(
            batch_size=10,
            max_facts_per_run=10,
            deadlock_max_retries=3,
            deadlock_initial_backoff_s=0.0,
        ),
    )
    _stub_get_unverified_facts(worker, records)
    _stub_process_batch(worker)
    _stub_update_fact_status(worker)

    stats = worker.run()

    # No retries — exactly one commit attempt and one rollback.
    assert session.commit_calls == 1
    assert session.rollback_calls == 1
    assert stats["facts_processed"] == 0
    assert stats["errors"] == 1


# ---------------------------------------------------------------------------
# Test 7: tenant scoping is preserved (no semantic change)
# ---------------------------------------------------------------------------


def test_tenant_scoping_is_preserved():
    """Stage 1K: the worker still constructs a tenant_uuid and the deadlock
    fix does not bypass tenant filtering. We exercise the real
    _get_unverified_facts path against a recording session to confirm the
    filter is applied when tenant_id is supplied."""
    tenant_id = "ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda"

    captured_filters: List[Any] = []

    class FilterRecordingQuery(FakeQuery):
        def filter(self, *args, **kwargs):
            captured_filters.append(args)
            return super().filter(*args, **kwargs)

    class FilterRecordingSession(FakeSession):
        def query(self, model):
            return FilterRecordingQuery(self, getattr(model, "__name__", str(model)))

    session = FilterRecordingSession(evidence_records=[])
    worker = _make_worker(session, tenant_id=tenant_id)

    # Run the real _get_unverified_facts path, which should call .filter() at
    # least once with a tenant_id constraint when tenant_id is supplied.
    worker._get_unverified_facts(limit=10)

    assert captured_filters, "tenant filter must be applied when tenant_id is supplied"
    # Tighter assertion: at least one filter expression must compare the
    # tenant_id column AND bind the worker's tenant_uuid value. Compile with
    # literal_binds=True so the UUID appears in the SQL text rather than as a
    # placeholder. This guards against a regression that silently dropped the
    # tenant predicate or filtered against the wrong column.
    compiled_chunks = []
    for args in captured_filters:
        for arg in args:
            try:
                compiled_chunks.append(
                    str(arg.compile(compile_kwargs={"literal_binds": True}))
                )
            except Exception:
                compiled_chunks.append(str(arg))
    flat = " || ".join(compiled_chunks)
    assert "tenant_id" in flat, f"no tenant_id predicate found in: {flat}"
    # SQLAlchemy + UUID may render the bound value with or without dashes
    # depending on dialect/literal_processor, so accept either canonical form.
    tenant_id_nodash = tenant_id.replace("-", "")
    assert tenant_id in flat or tenant_id_nodash in flat, (
        f"tenant_uuid {tenant_id} not bound into filter: {flat}"
    )


# ---------------------------------------------------------------------------
# Test 8: empty input is a no-op (no commits, no errors)
# ---------------------------------------------------------------------------


def test_empty_input_no_commits():
    """Stage 1K: when there is nothing to verify, the worker must not commit
    or rollback (no spurious DB churn)."""
    session = FakeSession(evidence_records=[])
    worker = _make_worker(session)
    _stub_get_unverified_facts(worker, [])

    stats = worker.run()

    assert session.commit_calls == 0
    assert session.rollback_calls == 0
    assert stats["facts_processed"] == 0
    assert stats["errors"] == 0
