"""Tests for Wiki Compiler (Gap 2)."""

import pytest
import pytest_asyncio

from src.agents.wiki_compiler import WikiCompiler
from tests.conftest import ENTITY_1_ID, ENTITY_2_ID, REL_1_ID


@pytest_asyncio.fixture()
async def wiki(initialized_db, seed_test_data):
    """WikiCompiler backed by seeded test data."""
    compiler = WikiCompiler(initialized_db)
    await compiler.ensure_table()

    yield compiler

    # Cleanup wiki_pages created during test
    async with initialized_db.get_postgres_connection() as conn:
        await conn.execute("DELETE FROM wiki_pages")


@pytest.mark.asyncio
async def test_compile_entity_page(wiki):
    result = await wiki.compile_entity_page("Service", "PaymentService")
    assert result["compiled"] is True
    assert result["title"] == "PaymentService"
    assert result["entity_type"] == "Service"
    assert result["entities_count"] >= 1
    assert result["confidence_avg"] > 0


@pytest.mark.asyncio
async def test_compile_includes_relationships(wiki):
    await wiki.compile_entity_page("Service", "PaymentService")
    page = await wiki.get_page("Service", "PaymentService")
    assert page is not None
    # The seeded data has Platform OWNS PaymentService
    assert "Relationships" in page["markdown"]
    assert "OWNS" in page["markdown"]


@pytest.mark.asyncio
async def test_compile_all(wiki):
    result = await wiki.compile_all()
    # Seeded data has 2 TRUSTED entities: PaymentService and Platform
    assert result["compiled"] >= 2
    assert result["total_candidates"] >= 2


@pytest.mark.asyncio
async def test_get_page_found(wiki):
    await wiki.compile_entity_page("Service", "PaymentService")
    page = await wiki.get_page("Service", "PaymentService")
    assert page is not None
    assert page["title"] == "PaymentService"
    assert "# PaymentService" in page["markdown"]


@pytest.mark.asyncio
async def test_get_page_not_found(wiki):
    page = await wiki.get_page("Service", "NonExistentService")
    assert page is None
