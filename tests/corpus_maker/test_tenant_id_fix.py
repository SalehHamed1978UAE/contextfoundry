"""
Stage 1B β blocker fix — tenant-id consistency tests.

Per docs/inbox/piece_2_stage1b_corpus_maker_fix_2026-05-10.md.

Covers:
  T1. TenantService.create_tenant(..., tenant_id=<uuid>) creates a row with exactly that ID.
  T2. TenantService.create_tenant(...) without tenant_id preserves prior generated-ID behavior.
  T3. get_or_create_tenant(vault_id, corpus_name) returns a tenant whose id == vault_id when not pre-existing.
  T4. Existing tenant lookup returns existing tenant and does not create a duplicate.
  T5. update_tenant_metadata writes corpus_metadata to settings without changing tenant id.

All tests use unique slugs/names + clean up after themselves so the suite is idempotent
against the live test DB.
"""

import os
import uuid
import pytest
import psycopg2

DB_URL = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set")


def _conn():
    return psycopg2.connect(DB_URL)


def _delete_tenant(tenant_id):
    """Test cleanup — only safe because tests upload no docs."""
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM platform.tenant_quotas WHERE tenant_id=%s", (str(tenant_id),))
            cur.execute("DELETE FROM platform.tenants WHERE id=%s", (str(tenant_id),))
            c.commit()


@pytest.fixture
def tenant_service():
    from platform_foundation.src.tenant_service import TenantService
    return TenantService()


def test_t1_create_tenant_with_explicit_tenant_id(tenant_service):
    """T1: explicit tenant_id is used as platform.tenants.id."""
    explicit_id = str(uuid.uuid4())
    slug = f"t1-{explicit_id[:8]}"
    try:
        t = tenant_service.create_tenant(
            name=f"T1 Explicit {explicit_id[:8]}",
            slug=slug,
            tenant_id=explicit_id,
        )
        assert str(t["id"]) == explicit_id, f"created id {t['id']} != explicit {explicit_id}"
        with _conn() as c, c.cursor() as cur:
            cur.execute("SELECT id FROM platform.tenants WHERE id=%s", (explicit_id,))
            row = cur.fetchone()
            assert row is not None and str(row[0]) == explicit_id
            cur.execute("SELECT tenant_id FROM platform.tenant_quotas WHERE tenant_id=%s", (explicit_id,))
            assert cur.fetchone() is not None, "tenant_quotas FK should now resolve"
    finally:
        _delete_tenant(explicit_id)


def test_t2_create_tenant_without_id_preserves_legacy_behavior(tenant_service):
    """T2: omitting tenant_id falls back to gen_random_uuid() default — existing callers unaffected."""
    slug = f"t2-{uuid.uuid4().hex[:8]}"
    t = tenant_service.create_tenant(
        name=f"T2 Generated {slug}",
        slug=slug,
    )
    try:
        assert t["id"] is not None
        # Returned id should be a valid uuid (not None/empty); we don't compare against
        # any caller-specified value because none was passed.
        uuid.UUID(str(t["id"]))
    finally:
        _delete_tenant(t["id"])


def test_t3_get_or_create_tenant_uses_vault_id(tenant_service):
    """T3: get_or_create_tenant returns tenant whose id == provided vault_id when new."""
    from src.corpus_maker.uploader import get_or_create_tenant
    vault_id = str(uuid.uuid4())
    try:
        result = get_or_create_tenant(vault_id, f"T3 Corpus {vault_id[:8]}")
        assert result is not None, "get_or_create_tenant returned None — bug regressed"
        assert str(result["id"]) == vault_id, (
            f"get_or_create_tenant minted id {result['id']} != vault_id {vault_id}"
        )
    finally:
        _delete_tenant(vault_id)


def test_t4_existing_tenant_returned_no_duplicate(tenant_service):
    """T4: existing tenant lookup returns existing row, does not create a duplicate."""
    from src.corpus_maker.uploader import get_or_create_tenant
    vault_id = str(uuid.uuid4())
    try:
        first = get_or_create_tenant(vault_id, f"T4 First {vault_id[:8]}")
        assert str(first["id"]) == vault_id

        second = get_or_create_tenant(vault_id, f"T4 Different Name {vault_id[:8]}")
        assert str(second["id"]) == vault_id

        with _conn() as c, c.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM platform.tenants WHERE id=%s", (vault_id,))
            assert cur.fetchone()[0] == 1, "duplicate tenant row was created"
    finally:
        _delete_tenant(vault_id)


def test_t5_update_tenant_metadata_writes_settings_without_id_change(tenant_service):
    """T5: update_tenant_metadata mutates settings.corpus_metadata + (optionally)
    primary_organization_name; does NOT change tenants.id."""
    vault_id = str(uuid.uuid4())
    slug = f"t5-{vault_id[:8]}"
    try:
        tenant_service.create_tenant(
            name=f"T5 Tenant {vault_id[:8]}",
            slug=slug,
            tenant_id=vault_id,
        )
        ok = tenant_service.update_tenant_metadata(
            vault_id,
            metadata={
                "corpus_name": "T5 Corpus",
                "anchor_organization": "T5 Anchor Org",
                "document_count": 7,
            },
        )
        assert ok is True

        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "SELECT id, settings, primary_organization_name FROM platform.tenants WHERE id=%s",
                (vault_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert str(row[0]) == vault_id, "tenant id changed during metadata update"
            settings = row[1] or {}
            assert "corpus_metadata" in settings, "corpus_metadata not stored in settings"
            assert settings["corpus_metadata"]["corpus_name"] == "T5 Corpus"
            assert settings["corpus_metadata"]["document_count"] == 7
            assert row[2] == "T5 Anchor Org", "primary_organization_name not mirrored"
    finally:
        _delete_tenant(vault_id)
