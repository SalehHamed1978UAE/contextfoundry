"""
Stage 1G Step 1 diagnostic: compare endpoint-eligibility counts between
admin (RLS bypassed) and tenant_session(role='user') contexts for the S vault.

Read-only. Does not mutate any data.
"""
import sys
from collections import Counter

from sqlalchemy import text as sql_text
from sqlalchemy.orm import aliased

from src.context_foundry.models.schema import (
    get_session,
    tenant_session,
    Entity,
    Relationship,
    LifecycleState,
)

S_TENANT = "5df41308-4033-441d-b712-77928b8ea93e"


def measure(session, label: str) -> dict:
    """Compute the same endpoint-eligibility numbers under whatever
    session context the caller provides."""
    src = aliased(Entity)
    tgt = aliased(Entity)

    # Pure SQL via raw query for perfect parity with admin-side measurement.
    rels = (
        session.query(
            Relationship.id,
            Relationship.relationship_type,
            Relationship.source_id,
            Relationship.target_id,
            src.lifecycle_state.label("src_state"),
            tgt.lifecycle_state.label("tgt_state"),
        )
        .outerjoin(src, src.id == Relationship.source_id)
        .outerjoin(tgt, tgt.id == Relationship.target_id)
        .filter(Relationship.lifecycle_state == LifecycleState.STAGING)
        .all()
    )

    total = len(rels)
    src_trusted = sum(1 for r in rels if r.src_state == LifecycleState.TRUSTED)
    tgt_trusted = sum(1 for r in rels if r.tgt_state == LifecycleState.TRUSTED)
    both_trusted = sum(
        1
        for r in rels
        if r.src_state == LifecycleState.TRUSTED
        and r.tgt_state == LifecycleState.TRUSTED
    )

    type_dist = Counter(
        r.relationship_type
        for r in rels
        if r.src_state == LifecycleState.TRUSTED
        and r.tgt_state == LifecycleState.TRUSTED
    )

    print(f"\n=== {label} ===")
    print(f"  total_staging_rels: {total}")
    print(f"  src_trusted: {src_trusted}")
    print(f"  tgt_trusted: {tgt_trusted}")
    print(f"  both_trusted (endpoint-eligible): {both_trusted}")
    print(f"  rel_type distribution for both-trusted set:")
    for rel_type, n in type_dist.most_common():
        print(f"    {rel_type}: {n}")

    return {
        "label": label,
        "total": total,
        "src_trusted": src_trusted,
        "tgt_trusted": tgt_trusted,
        "both_trusted": both_trusted,
        "type_dist": dict(type_dist),
    }


def main():
    print(f"S vault tenant_id = {S_TENANT}")

    # 1) admin (RLS bypassed) — equivalent to direct psql with app.role=admin
    admin_session = get_session(use_rls_role=False)
    admin_session.execute(sql_text("SET app.role='admin'"))
    try:
        admin_result = measure(admin_session, "ADMIN role (RLS bypassed)")
    finally:
        admin_session.close()

    # 2) tenant_session(role='user') — exact same context as scripts/run_promotion.py
    with tenant_session(S_TENANT, role='user') as ts:
        user_result = measure(ts._session, "tenant_session(role='user') for S vault")

    # Compare
    print("\n=== STEP 1 COMPARISON ===")
    keys = ["total", "src_trusted", "tgt_trusted", "both_trusted"]
    matched = True
    for k in keys:
        a = admin_result[k]
        u = user_result[k]
        ok = "✓" if a == u else "✗ MISMATCH"
        print(f"  {k:30s} admin={a:6d}  user={u:6d}  {ok}")
        if a != u:
            matched = False

    if not matched:
        print("\n*** STEP 1 STOP TRIGGER: counts differ between admin and tenant_session ***")
        sys.exit(1)

    print("\n*** STEP 1 PASSED: admin and tenant_session see same endpoint-eligibility counts ***")
    print(f"*** Proceed to Step 2 with both_trusted = {user_result['both_trusted']} ***")
    sys.exit(0)


if __name__ == "__main__":
    main()
