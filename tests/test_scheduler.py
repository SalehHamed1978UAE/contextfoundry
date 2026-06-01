"""Tests for Scheduled Maintenance (Gap 4)."""

import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_scheduled_maintenance_runs(initialized_db):
    """Call _scheduled_maintenance() directly, verify no crash."""
    # We need to set the global db_manager so _scheduled_maintenance can use it
    import src.main as main_module
    from src.db.connection import db_manager as real_db_manager

    # Save and swap the module-level db_manager
    original = main_module.db_manager
    main_module.db_manager = initialized_db
    # Also disable cache reference to avoid issues
    original_cache = main_module.semantic_cache
    main_module.semantic_cache = None

    try:
        result = await main_module._scheduled_maintenance()
        assert "conflicts" in result
        assert "stale" in result
        assert "rule_evolution" in result
        assert isinstance(result["conflicts"], list)
        assert isinstance(result["stale"], list)
    finally:
        main_module.db_manager = original
        main_module.semantic_cache = original_cache


@pytest.mark.asyncio
async def test_admin_maintenance_endpoint(test_app):
    """POST /admin/maintenance returns conflict/stale counts."""
    resp = await test_app.post("/admin/maintenance")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] == "maintenance_complete"
    assert "conflicts" in data
    assert "stale_entities" in data
    assert "rule_evolution" in data


@pytest.mark.asyncio
async def test_scheduler_configured():
    """Verify the scheduler module can be imported and configured."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    s = AsyncIOScheduler()
    s.add_job(lambda: None, "interval", hours=6, id="maintenance")
    assert s.get_job("maintenance") is not None
    # Don't start it — just verify configuration
