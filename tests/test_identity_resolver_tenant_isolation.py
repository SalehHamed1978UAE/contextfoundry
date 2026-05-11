"""
Stage 1I — IdentityResolver tenant-isolation regression tests.

Verifies the six tenant-invariant guards added to
``src/context_foundry/agents/identity_resolver.py`` after Stage 1H finding
(2026-05-11) that 99.5% of in-window merges (2418 / 2431) were cross-tenant
relationship retargets.

Acceptance properties (from
``docs/inbox/Stage 1I — IdentityResolver Tenant-Isolation Fix.md``):

  T1  Cross-tenant candidate is rejected — no merge, no rel changes
  T2  _merge_pair tenant-scoped lookup fails closed for cross-tenant pair
  T3  _transfer_relationships does not retarget across tenants
  T4  Within-tenant transfer still works
  T5  Candidate generation is tenant-scoped (same-name diff-tenant != same-tenant)
  T6  No cross-tenant leakage regression (DB-level COUNT == 0)

Test pattern follows ``tests/test_gardener_promotion_perf_fix.py``: synthetic
zero-prefix tenant ids inside a SAVEPOINT that is rolled back at teardown.
No impact on real vault data.
"""
import os
import uuid
from datetime import datetime

import pytest

os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

from sqlalchemy import text as sql_text

from src.context_foundry.agents.identity_resolver import (
    IdentityResolver,
    IdentityResolutionConfig,
    DuplicateCandidate,
    MergeDecision,
)
from src.context_foundry.models.schema import (
    get_session,
    Entity,
    Relationship,
    LifecycleState,
)


# Two synthetic tenant ids — chosen to be deterministically not-real (zero-prefix).
TENANT_A = "00000000-0000-0000-0000-0000000a1000"
TENANT_B = "00000000-0000-0000-0000-0000000b1000"
TENANT_A_UUID = uuid.UUID(TENANT_A)
TENANT_B_UUID = uuid.UUID(TENANT_B)


@pytest.fixture
def admin_session_with_rollback():
    """Admin session (RLS bypassed) wrapped in a savepoint that rolls back."""
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    session = get_session(use_rls_role=False)
    session.execute(sql_text("SET app.role = 'admin'"))
    session.begin_nested()  # SAVEPOINT
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_entity(
    session,
    tenant_id_uuid,
    name,
    entity_type="ORGANIZATION",
    lifecycle=LifecycleState.STAGING,
    confidence=0.90,
    properties=None,
):
    e = Entity(
        id=uuid.uuid4(),
        tenant_id=tenant_id_uuid,
        name=name,
        entity_type=entity_type,
        lifecycle_state=lifecycle,
        confidence=confidence,
        properties=properties or {},
        created_at=datetime.utcnow(),
    )
    session.add(e)
    session.flush()
    return e


def _make_rel(
    session,
    tenant_id_uuid,
    source,
    target,
    rel_type="WORKS_AT",
    confidence=0.80,
    lifecycle=LifecycleState.STAGING,
):
    r = Relationship(
        id=uuid.uuid4(),
        tenant_id=tenant_id_uuid,
        source_id=source.id,
        target_id=target.id,
        relationship_type=rel_type,
        confidence=confidence,
        lifecycle_state=lifecycle,
        created_at=datetime.utcnow(),
    )
    session.add(r)
    session.flush()
    return r


# ---------------------------------------------------------------------------
# T0: __init__ fail-closed
# ---------------------------------------------------------------------------


def test_t0_init_requires_tenant_id():
    """Constructing without tenant_id raises ValueError (fail-closed)."""
    with pytest.raises(ValueError, match="tenant_id"):
        IdentityResolver(session=None, tenant_id=None)
    with pytest.raises(ValueError, match="tenant_id"):
        IdentityResolver(session=None, tenant_id="")


def test_t0_init_accepts_str_or_uuid():
    """Constructor accepts both str UUID and uuid.UUID."""
    r1 = IdentityResolver(session=None, tenant_id=TENANT_A)
    r2 = IdentityResolver(session=None, tenant_id=TENANT_A_UUID)
    assert r1.tenant_uuid == TENANT_A_UUID
    assert r2.tenant_uuid == TENANT_A_UUID
    assert r1.tenant_id == TENANT_A
    assert r2.tenant_id == TENANT_A


# ---------------------------------------------------------------------------
# T1: Cross-tenant candidate is rejected (synthetic candidate)
# ---------------------------------------------------------------------------


def test_t1_cross_tenant_candidate_rejected_no_merge(admin_session_with_rollback):
    s = admin_session_with_rollback
    # Same name, different tenants
    a = _make_entity(s, TENANT_A_UUID, "Acme Corp")
    b = _make_entity(s, TENANT_B_UUID, "Acme Corp")
    target_a = _make_entity(s, TENANT_A_UUID, "Engineering Dept")
    target_b = _make_entity(s, TENANT_B_UUID, "Engineering Dept")
    rel_a = _make_rel(s, TENANT_A_UUID, a, target_a, rel_type="HAS_DEPT")
    rel_b = _make_rel(s, TENANT_B_UUID, b, target_b, rel_type="HAS_DEPT")
    s.flush()

    rel_a_id, rel_b_id = rel_a.id, rel_b.id
    rel_a_src, rel_b_src = rel_a.source_id, rel_b.source_id

    resolver = IdentityResolver(session=s, tenant_id=TENANT_A)
    # Synthetic candidate that pairs A from tenant A with B from tenant B
    candidate = DuplicateCandidate(
        entity_a_id=str(a.id),
        entity_b_id=str(b.id),
        entity_a_name=a.name,
        entity_b_name=b.name,
        entity_type=a.entity_type,
        similarity_score=0.99,
        signals=["exact_name_match"],
        merge_decision=MergeDecision.AUTO_MERGE,
    )

    result = resolver._perform_merge(candidate)

    assert result is None, "Cross-tenant merge must be refused"
    s.refresh(rel_a)
    s.refresh(rel_b)
    assert rel_a.source_id == rel_a_src, "rel_a source_id must not change"
    assert rel_b.source_id == rel_b_src, "rel_b source_id must not change"
    s.refresh(a)
    s.refresh(b)
    assert a.lifecycle_state != LifecycleState.ARCHIVED
    assert b.lifecycle_state != LifecycleState.ARCHIVED


# ---------------------------------------------------------------------------
# T2: _merge_pair (called via _perform_merge) loads by tenant; foreign side missing
# ---------------------------------------------------------------------------


def test_t2_merge_pair_tenant_scoped_lookup_fails_closed(admin_session_with_rollback):
    s = admin_session_with_rollback
    a = _make_entity(s, TENANT_A_UUID, "Foo Org")
    b = _make_entity(s, TENANT_B_UUID, "Foo Org")
    s.flush()

    a_id_global = s.query(Entity).filter(Entity.id == a.id).first()
    b_id_global = s.query(Entity).filter(Entity.id == b.id).first()
    assert a_id_global is not None and b_id_global is not None, (
        "Both entities must exist globally — pre-condition for the test"
    )

    resolver = IdentityResolver(session=s, tenant_id=TENANT_A)
    candidate = DuplicateCandidate(
        entity_a_id=str(a.id),
        entity_b_id=str(b.id),
        entity_a_name=a.name,
        entity_b_name=b.name,
        entity_type=a.entity_type,
        similarity_score=0.99,
        signals=["exact_name_match"],
        merge_decision=MergeDecision.AUTO_MERGE,
    )

    result = resolver._perform_merge(candidate)
    assert result is None, (
        "Tenant-scoped lookup must reject the cross-tenant side and skip merge"
    )


# ---------------------------------------------------------------------------
# T3: _transfer_relationships does not retarget across tenants
# ---------------------------------------------------------------------------


def test_t3_transfer_relationships_does_not_retarget_cross_tenant(
    admin_session_with_rollback,
):
    s = admin_session_with_rollback
    from_e = _make_entity(s, TENANT_A_UUID, "From Org")
    to_e = _make_entity(s, TENANT_B_UUID, "To Org")  # different tenant
    target = _make_entity(s, TENANT_A_UUID, "Target")
    rel = _make_rel(s, TENANT_A_UUID, from_e, target, rel_type="HAS_DEPT")
    s.flush()

    rel_orig_source = rel.source_id
    rel_orig_target = rel.target_id

    resolver = IdentityResolver(session=s, tenant_id=TENANT_A)
    transferred = resolver._transfer_relationships(from_e, to_e)

    assert transferred == 0
    s.refresh(rel)
    assert rel.source_id == rel_orig_source
    assert rel.target_id == rel_orig_target


# ---------------------------------------------------------------------------
# T4: Within-tenant transfer still works
# ---------------------------------------------------------------------------


def test_t4_within_tenant_transfer_works(admin_session_with_rollback):
    s = admin_session_with_rollback
    from_e = _make_entity(s, TENANT_A_UUID, "Acme (dup)")
    to_e = _make_entity(
        s, TENANT_A_UUID, "Acme",
        lifecycle=LifecycleState.TRUSTED, confidence=0.95,
    )
    target = _make_entity(s, TENANT_A_UUID, "Engineering")
    rel = _make_rel(s, TENANT_A_UUID, from_e, target, rel_type="HAS_DEPT")
    s.flush()

    rel_id = rel.id
    rel_orig_target = rel.target_id

    resolver = IdentityResolver(session=s, tenant_id=TENANT_A)
    transferred = resolver._transfer_relationships(from_e, to_e)

    assert transferred == 1
    s.refresh(rel)
    assert rel.source_id == to_e.id, "source_id must retarget to survivor"
    assert rel.target_id == rel_orig_target, "target_id unchanged"
    assert rel.tenant_id == TENANT_A_UUID, "tenant_id must remain unchanged"


# ---------------------------------------------------------------------------
# T5: Candidate generation is tenant-scoped (full run() path)
# ---------------------------------------------------------------------------


def test_t5_candidate_generation_tenant_scoped(admin_session_with_rollback):
    s = admin_session_with_rollback
    # Same-name entity in tenant B should NOT pair with tenant A's entity
    a1 = _make_entity(s, TENANT_A_UUID, "DupName Org")
    a2 = _make_entity(
        s, TENANT_A_UUID, "DupName Org",
        lifecycle=LifecycleState.TRUSTED, confidence=0.95,
    )
    b1 = _make_entity(s, TENANT_B_UUID, "DupName Org")
    s.flush()

    resolver = IdentityResolver(session=s, tenant_id=TENANT_A)
    result = resolver.run(commit=False, staging_only=True)

    candidate_pairs = {
        tuple(sorted([c.entity_a_id, c.entity_b_id])) for c in resolver.candidates
    }
    in_tenant_pair = tuple(sorted([str(a1.id), str(a2.id)]))
    cross_tenant_pair_ab = tuple(sorted([str(a1.id), str(b1.id)]))
    cross_tenant_pair_ab2 = tuple(sorted([str(a2.id), str(b1.id)]))

    assert in_tenant_pair in candidate_pairs, "Same-tenant duplicates must be detected"
    assert cross_tenant_pair_ab not in candidate_pairs, (
        "Cross-tenant pair (A↔B) must NOT be generated"
    )
    assert cross_tenant_pair_ab2 not in candidate_pairs, (
        "Cross-tenant pair (A↔B) must NOT be generated"
    )


# ---------------------------------------------------------------------------
# T6: No cross-tenant leakage regression — DB-level COUNT
# ---------------------------------------------------------------------------


def test_t6_no_cross_tenant_relationship_leakage(admin_session_with_rollback):
    """
    After a full identity-resolver run on a synthetic two-tenant setup, the
    DB-level cross-tenant count for the synthetic test rows must be zero.
    """
    s = admin_session_with_rollback

    # Tenant A: two duplicates + relationships
    a1 = _make_entity(s, TENANT_A_UUID, "Globex Inc")
    a2 = _make_entity(
        s, TENANT_A_UUID, "Globex Inc",
        lifecycle=LifecycleState.TRUSTED, confidence=0.95,
    )
    a_target = _make_entity(s, TENANT_A_UUID, "Sales Dept")
    a_rel = _make_rel(s, TENANT_A_UUID, a1, a_target, rel_type="HAS_DEPT")

    # Tenant B: same-named entity that the buggy old code would have merged into
    b1 = _make_entity(s, TENANT_B_UUID, "Globex Inc")
    b_target = _make_entity(s, TENANT_B_UUID, "Sales Dept")
    b_rel = _make_rel(s, TENANT_B_UUID, b1, b_target, rel_type="HAS_DEPT")
    s.flush()

    test_entity_ids = [str(eid) for eid in (a1.id, a2.id, a_target.id, b1.id, b_target.id)]
    test_rel_ids = [str(rid) for rid in (a_rel.id, b_rel.id)]

    resolver = IdentityResolver(session=s, tenant_id=TENANT_A)
    resolver.run(commit=False, staging_only=True)
    s.flush()

    leak_count = s.execute(
        sql_text(
            """
            SELECT COUNT(*)
            FROM relationships r
            JOIN entities src ON src.id = r.source_id
            JOIN entities tgt ON tgt.id = r.target_id
            WHERE r.id = ANY(CAST(:rel_ids AS uuid[]))
              AND (r.tenant_id <> src.tenant_id OR r.tenant_id <> tgt.tenant_id)
            """
        ),
        {"rel_ids": test_rel_ids},
    ).scalar()

    assert leak_count == 0, (
        f"Cross-tenant relationship leakage detected for synthetic test rows: {leak_count}"
    )

    # Also assert that tenant B's entity is untouched
    s.refresh(b1)
    assert b1.tenant_id == TENANT_B_UUID
    assert b1.lifecycle_state != LifecycleState.ARCHIVED, (
        "Tenant B's entity must not be archived by tenant A's resolver"
    )


# ---------------------------------------------------------------------------
# T7 (extra): _choose_survivor raises on cross-tenant entities (defense-in-depth)
# ---------------------------------------------------------------------------


def test_t7_choose_survivor_raises_on_cross_tenant(admin_session_with_rollback):
    s = admin_session_with_rollback
    a = _make_entity(s, TENANT_A_UUID, "Org X")
    b = _make_entity(s, TENANT_B_UUID, "Org X")
    s.flush()

    resolver = IdentityResolver(session=s, tenant_id=TENANT_A)
    with pytest.raises(ValueError, match="cross-tenant"):
        resolver._choose_survivor(a, b)


# ---------------------------------------------------------------------------
# T8 (extra): _same_tenant helper sanity
# ---------------------------------------------------------------------------


def test_t9_opposite_endpoint_tenant_check(admin_session_with_rollback):
    """
    Architect HIGH (Stage 1I review 2026-05-11): _transfer_relationships must
    verify the OPPOSITE endpoint entity tenant before retargeting, not just
    rel.tenant_id and from/to entities. A pre-existing corrupt rel where
    rel.tenant_id matches but the opposite endpoint already lives in a foreign
    tenant must NOT have its source_id/target_id rewritten.

    Setup: tenant A from_entity, tenant A to_entity (within-tenant survivor),
           rel.tenant_id = A, rel.source = from_entity (A), rel.target = entity
           in tenant B (the pre-existing pollution).

    Expectation: rel.source_id NOT rewritten; transferred=0.
    """
    s = admin_session_with_rollback
    from_e = _make_entity(s, TENANT_A_UUID, "Acme A (dup)")
    to_e = _make_entity(
        s, TENANT_A_UUID, "Acme A",
        lifecycle=LifecycleState.TRUSTED, confidence=0.95,
    )
    foreign_target = _make_entity(s, TENANT_B_UUID, "Foreign Target B")
    # Corrupt rel: tenant_id=A, source in A, but target in B (the pollution shape)
    corrupt_rel = _make_rel(s, TENANT_A_UUID, from_e, foreign_target, rel_type="HAS_DEPT")
    s.flush()

    rel_orig_source = corrupt_rel.source_id
    rel_orig_target = corrupt_rel.target_id

    resolver = IdentityResolver(session=s, tenant_id=TENANT_A)
    transferred = resolver._transfer_relationships(from_e, to_e)

    assert transferred == 0, (
        "Corrupt rel with foreign-tenant target endpoint must NOT be retargeted"
    )
    s.refresh(corrupt_rel)
    assert corrupt_rel.source_id == rel_orig_source, (
        "source_id of corrupt rel must NOT be rewritten by tenant-A resolver"
    )
    assert corrupt_rel.target_id == rel_orig_target, "target_id unchanged"


def test_t9b_opposite_endpoint_check_incoming_direction(admin_session_with_rollback):
    """
    Mirror of T9 for the incoming_relationships loop: corrupt rel where
    target=from_entity (in A) but source = entity in tenant B.
    """
    s = admin_session_with_rollback
    from_e = _make_entity(s, TENANT_A_UUID, "Beta A (dup)")
    to_e = _make_entity(
        s, TENANT_A_UUID, "Beta A",
        lifecycle=LifecycleState.TRUSTED, confidence=0.95,
    )
    foreign_source = _make_entity(s, TENANT_B_UUID, "Foreign Source B")
    corrupt_rel = _make_rel(s, TENANT_A_UUID, foreign_source, from_e, rel_type="HAS_DEPT")
    s.flush()

    rel_orig_source = corrupt_rel.source_id
    rel_orig_target = corrupt_rel.target_id

    resolver = IdentityResolver(session=s, tenant_id=TENANT_A)
    transferred = resolver._transfer_relationships(from_e, to_e)

    assert transferred == 0
    s.refresh(corrupt_rel)
    assert corrupt_rel.source_id == rel_orig_source
    assert corrupt_rel.target_id == rel_orig_target


def test_t8_same_tenant_helper(admin_session_with_rollback):
    s = admin_session_with_rollback
    a = _make_entity(s, TENANT_A_UUID, "Helper Test 1")
    b = _make_entity(s, TENANT_A_UUID, "Helper Test 2")
    c = _make_entity(s, TENANT_B_UUID, "Helper Test 3")

    resolver = IdentityResolver(session=s, tenant_id=TENANT_A)
    assert resolver._same_tenant(a, b) is True
    assert resolver._same_tenant(a, c) is False
    assert resolver._same_tenant(a, None) is False
    assert resolver._same_tenant() is True  # vacuously true
