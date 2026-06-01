"""
Tests for MCP server tools.

Imports MCP tool functions directly and calls them as async functions.
10 tests covering all structured-data tools.
"""

import json

import pytest
import pytest_asyncio

from tests.conftest import ENTITY_1_ID, ENTITY_2_ID, ENTITY_3_ID, REL_1_ID

# Import the module; tools reference the module-level singletons
import src.mcp_server as mcp_mod


@pytest_asyncio.fixture(autouse=True)
async def init_mcp(initialized_db, embedding_service, document_embedder):
    """Wire up MCP module singletons so tools can run without stdio."""
    old_db = mcp_mod._db_manager
    old_emb = mcp_mod._embedding_service
    old_doc = mcp_mod._document_embedder

    mcp_mod._db_manager = initialized_db
    mcp_mod._embedding_service = embedding_service
    mcp_mod._document_embedder = document_embedder
    yield
    mcp_mod._db_manager = old_db
    mcp_mod._embedding_service = old_emb
    mcp_mod._document_embedder = old_doc


# ─── search_entities ──────────────────────────────────────────────────


async def test_search_entities_by_type(seed_test_data):
    raw = await mcp_mod.search_entities(type="Service")
    data = json.loads(raw)
    assert isinstance(data, list)
    assert any(str(ENTITY_1_ID) in str(e.get("entity_id")) for e in data)


async def test_search_entities_by_name(seed_test_data):
    raw = await mcp_mod.search_entities(name="platform")
    data = json.loads(raw)
    assert isinstance(data, list)
    assert any("Platform" in (e.get("extracted_text") or "") for e in data)


# ─── get_entity ───────────────────────────────────────────────────────


async def test_get_entity_found(seed_test_data):
    raw = await mcp_mod.get_entity(str(ENTITY_2_ID))
    data = json.loads(raw)
    assert data["entity_type"] == "Team"
    assert "relationships" in data
    assert len(data["relationships"]) >= 1


async def test_get_entity_not_found(seed_test_data):
    raw = await mcp_mod.get_entity("00000000-0000-0000-0000-ffffffffffff")
    data = json.loads(raw)
    assert "error" in data


# ─── search_documents (vector) ────────────────────────────────────────


async def test_search_documents_vector(seed_test_data):
    raw = await mcp_mod.search_documents(query="credit card payments", top_k=5)
    data = json.loads(raw)
    assert isinstance(data, list)
    if data:
        assert "similarity" in data[0]


# ─── search_documents_by_text (keyword) ──────────────────────────────


async def test_search_documents_by_text_keyword(seed_test_data):
    raw = await mcp_mod.search_documents_by_text(query="Stripe")
    data = json.loads(raw)
    assert isinstance(data, list)
    assert any("Stripe" in (d.get("chunk_text") or "") for d in data)


# ─── get_document ─────────────────────────────────────────────────────


async def test_get_document_found(seed_test_data):
    raw = await mcp_mod.get_document("doc-1")
    data = json.loads(raw)
    assert isinstance(data, list)
    assert len(data) == 2  # two chunks seeded


async def test_get_document_not_found(seed_test_data):
    raw = await mcp_mod.get_document("nonexistent-doc")
    data = json.loads(raw)
    assert "error" in data


# ─── search_relationships ─────────────────────────────────────────────


async def test_search_relationships_by_type(seed_test_data):
    raw = await mcp_mod.search_relationships(relationship_type="OWNS")
    data = json.loads(raw)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all(r["relationship_type"] == "OWNS" for r in data)


# ─── get_system_stats ─────────────────────────────────────────────────


async def test_get_system_stats(seed_test_data):
    raw = await mcp_mod.get_system_stats()
    data = json.loads(raw)
    expected_keys = {
        "entities_total", "entities_trusted", "entities_staging",
        "entities_archived", "relationships_total", "documents_embedded",
        "queries_processed", "feedback_records",
    }
    assert expected_keys.issubset(data.keys())
    assert data["entities_total"] >= 3
