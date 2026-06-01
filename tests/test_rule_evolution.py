"""Tests for Self-Evolving Procedural Rules (Gap 5)."""

from uuid import uuid4

import pytest
import pytest_asyncio

from src.agents.extraction import ExtractionAgent


@pytest_asyncio.fixture()
async def extractor(initialized_db):
    return ExtractionAgent(initialized_db)


@pytest_asyncio.fixture()
async def setup_rules(initialized_db):
    """Insert test rules and clean up after."""
    rule_ids = []

    async def _insert(name, times_applied, times_violated, priority=5, enabled=True):
        rid = uuid4()
        rule_ids.append(rid)
        async with initialized_db.get_postgres_connection() as conn:
            await conn.execute(
                """INSERT INTO symbolic_rules
                       (id, rule_name, rule_type, rule_expression,
                        rule_description, priority, enabled,
                        times_applied, times_violated)
                   VALUES ($1, $2, 'validation', '{}', $3, $4, $5, $6, $7)""",
                rid,
                name,
                f"Test rule: {name}",
                priority,
                enabled,
                times_applied,
                times_violated,
            )
        return rid

    yield _insert

    # Cleanup
    async with initialized_db.get_postgres_connection() as conn:
        for rid in rule_ids:
            await conn.execute("DELETE FROM symbolic_rules WHERE id = $1", rid)


@pytest.mark.asyncio
async def test_disable_broken_rule(extractor, initialized_db, setup_rules):
    """Rule with >80% violation rate and >=50 applications gets disabled."""
    await setup_rules("broken_rule", times_applied=60, times_violated=50)

    result = await extractor.rule_evolver()
    assert "broken_rule" in result["disabled"]


@pytest.mark.asyncio
async def test_promote_clean_rule(extractor, initialized_db, setup_rules):
    """Rule with 0 violations and >=20 applications gets priority +1."""
    rid = await setup_rules("clean_rule", times_applied=25, times_violated=0, priority=5)

    result = await extractor.rule_evolver()
    assert "clean_rule" in result["promoted"]

    # Verify priority increased
    async with initialized_db.get_postgres_connection() as conn:
        row = await conn.fetchrow(
            "SELECT priority FROM symbolic_rules WHERE id = $1", rid
        )
        assert row["priority"] == 6


@pytest.mark.asyncio
async def test_demote_noisy_rule(extractor, initialized_db, setup_rules):
    """Rule with 40-80% violation rate gets priority -1."""
    rid = await setup_rules("noisy_rule", times_applied=30, times_violated=15, priority=5)

    result = await extractor.rule_evolver()
    assert "noisy_rule" in result["demoted"]

    # Verify priority decreased
    async with initialized_db.get_postgres_connection() as conn:
        row = await conn.fetchrow(
            "SELECT priority FROM symbolic_rules WHERE id = $1", rid
        )
        assert row["priority"] == 4


@pytest.mark.asyncio
async def test_no_change_insufficient_data(extractor, initialized_db, setup_rules):
    """Rule with <20 applications should not be changed."""
    rid = await setup_rules("new_rule", times_applied=10, times_violated=0, priority=5)

    result = await extractor.rule_evolver()
    assert "new_rule" not in result["disabled"]
    assert "new_rule" not in result["promoted"]
    assert "new_rule" not in result["demoted"]

    # Verify priority unchanged
    async with initialized_db.get_postgres_connection() as conn:
        row = await conn.fetchrow(
            "SELECT priority, enabled FROM symbolic_rules WHERE id = $1", rid
        )
        assert row["priority"] == 5
        assert row["enabled"] is True
