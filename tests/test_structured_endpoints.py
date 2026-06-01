"""
Tests for the 6 structured query endpoints.
15 tests covering entities, relationships, and documents.
"""

import pytest

from tests.conftest import ENTITY_1_ID, ENTITY_2_ID, ENTITY_3_ID


# ─── Entities ─────────────────────────────────────────────────────────


async def test_list_entities_default(test_app, seed_test_data):
    """Default listing returns TRUSTED entities."""
    resp = await test_app.get("/entities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    for e in body["entities"]:
        assert e["lifecycle_state"] == "TRUSTED"


async def test_list_entities_filter_by_type(test_app, seed_test_data):
    resp = await test_app.get("/entities", params={"type": "Service"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(e["entity_type"] == "Service" for e in body["entities"])


async def test_list_entities_filter_by_name(test_app, seed_test_data):
    resp = await test_app.get("/entities", params={"name": "payment"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any("payment" in (e["extracted_text"] or "").lower() for e in body["entities"])


async def test_list_entities_filter_by_state(test_app, seed_test_data):
    resp = await test_app.get("/entities", params={"state": "STAGING"})
    assert resp.status_code == 200
    body = resp.json()
    for e in body["entities"]:
        assert e["lifecycle_state"] == "STAGING"


async def test_list_entities_min_confidence(test_app, seed_test_data):
    resp = await test_app.get("/entities", params={"min_confidence": 0.9})
    assert resp.status_code == 200
    body = resp.json()
    for e in body["entities"]:
        assert e["confidence"] >= 0.9


async def test_list_entities_pagination(test_app, seed_test_data):
    resp = await test_app.get(
        "/entities", params={"state": "TRUSTED", "limit": 1, "offset": 0}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["entities"]) <= 1


async def test_get_entity_found(test_app, seed_test_data):
    resp = await test_app.get(f"/entities/{ENTITY_2_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entity_type"] == "Team"
    assert body["extracted_text"] == "Platform"
    assert isinstance(body["relationships"], list)
    assert len(body["relationships"]) >= 1


async def test_get_entity_not_found(test_app, seed_test_data):
    resp = await test_app.get("/entities/00000000-0000-0000-0000-ffffffffffff")
    assert resp.status_code == 404


# ─── Relationships ────────────────────────────────────────────────────


async def test_list_relationships_default(test_app, seed_test_data):
    resp = await test_app.get("/relationships")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert "relationships" in body


async def test_list_relationships_filter_type(test_app, seed_test_data):
    resp = await test_app.get("/relationships", params={"relationship_type": "OWNS"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert all(r["relationship_type"] == "OWNS" for r in body["relationships"])


# ─── Documents ────────────────────────────────────────────────────────


async def test_list_documents_default(test_app, seed_test_data):
    resp = await test_app.get("/documents")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2


async def test_list_documents_keyword_query(test_app, seed_test_data):
    resp = await test_app.get("/documents", params={"query": "Stripe"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any("Stripe" in d["chunk_text"] for d in body["documents"])


async def test_get_document_found(test_app, seed_test_data):
    resp = await test_app.get("/documents/doc-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2  # two chunks seeded
    indices = [d["chunk_index"] for d in body["documents"]]
    assert indices == sorted(indices)


async def test_get_document_not_found(test_app, seed_test_data):
    resp = await test_app.get("/documents/nonexistent-doc")
    assert resp.status_code == 404


async def test_vector_search_documents(test_app, seed_test_data):
    resp = await test_app.get(
        "/documents/search", params={"query": "credit card payments", "top_k": 5}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "credit card payments"
    assert isinstance(body["results"], list)
    if body["results"]:
        assert "similarity" in body["results"][0]
        assert "text" in body["results"][0]
