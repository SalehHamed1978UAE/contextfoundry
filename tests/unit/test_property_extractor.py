"""Unit tests for PropertyExtractor (Stage 3B).

Uses the _stub_session pattern from test_property_store.py.
No database required — all SQL is intercepted via MagicMock.
LLM calls are mocked.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.context_foundry.extraction.property_extractor import (
    PropertyExtractor,
    _tokenize,
    _strip_json_fences,
    _extract_fiscal_year,
)
from src.context_foundry.adapters.property_adapter import (
    is_value_shaped_name,
    parse_numeric,
)


# ---------------------------------------------------------------------------
# Helpers (matching test_property_store.py pattern)
# ---------------------------------------------------------------------------

class _Row:
    """Generic row object for mocking SQL results."""
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def get(self, key, default=None):
        return getattr(self, key, default)


def _stub_session(rows=None):
    """Create a MagicMock session. execute().fetchall() returns `rows`."""
    session = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = rows or []
    session.execute.return_value = result
    return session


def _chunk_row(chunk_id="c-1", document_id="doc-1", text=""):
    return _Row(chunk_id=chunk_id, document_id=document_id, text=text)


def _entity_row(id="e-1", name="Nexus Industries", entity_type="ORGANIZATION", aliases=None):
    return _Row(id=id, name=name, entity_type=entity_type, aliases=aliases or [])


def _make_extractor(session=None, dry_run=False):
    """Create a PropertyExtractor with mocked OpenAI client."""
    session = session or _stub_session()
    ext = PropertyExtractor.__new__(PropertyExtractor)
    ext.session = session
    ext.tenant_id = "t-test"
    ext.dry_run = dry_run
    ext.client = MagicMock()
    return ext


def _mock_llm_response(content: str):
    """Create a mock OpenAI chat.completions.create() response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------------------------------------------------------------------------
# Tests: _tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_basic_tokenization(self):
        tokens = _tokenize("Nexus Industries Revenue")
        assert "nexus" in tokens
        assert "industries" in tokens
        assert "revenue" in tokens

    def test_stopwords_removed(self):
        tokens = _tokenize("the revenue of the company")
        assert "the" not in tokens
        assert "of" not in tokens
        assert "revenue" in tokens
        assert "company" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []
        assert _tokenize(None) == []

    def test_short_tokens_removed(self):
        tokens = _tokenize("a b cd efg")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "cd" in tokens
        assert "efg" in tokens


# ---------------------------------------------------------------------------
# Tests: _strip_json_fences
# ---------------------------------------------------------------------------

class TestStripJsonFences:
    def test_strips_json_fence(self):
        raw = '```json\n[{"a": 1}]\n```'
        assert _strip_json_fences(raw) == '[{"a": 1}]'

    def test_strips_plain_fence(self):
        raw = '```\n[{"a": 1}]\n```'
        assert _strip_json_fences(raw) == '[{"a": 1}]'

    def test_no_fence_passthrough(self):
        raw = '[{"a": 1}]'
        assert _strip_json_fences(raw) == '[{"a": 1}]'


# ---------------------------------------------------------------------------
# Tests: _extract_fiscal_year
# ---------------------------------------------------------------------------

class TestExtractFiscalYear:
    def test_fy_prefix(self):
        assert _extract_fiscal_year("FY2025") == "2025"

    def test_quarter_year(self):
        assert _extract_fiscal_year("Q3 2025") == "2025"

    def test_plain_year(self):
        assert _extract_fiscal_year("2025") == "2025"

    def test_none_input(self):
        assert _extract_fiscal_year(None) is None

    def test_no_year(self):
        assert _extract_fiscal_year("ongoing") is None


# ---------------------------------------------------------------------------
# Tests: _find_chunks_for_entity
# ---------------------------------------------------------------------------

class TestFindChunks:
    def test_builds_ilike_query_with_entity_tokens(self):
        session = _stub_session([])
        ext = _make_extractor(session)
        ext._find_chunks_for_entity("Nexus Industries", [])

        # Should have called execute with an ILIKE query
        call_args = session.execute.call_args
        sql_str = str(call_args.args[0].text) if hasattr(call_args.args[0], 'text') else str(call_args.args[0])
        assert "ILIKE" in sql_str
        params = call_args.args[1]
        assert params["tid"] == "t-test"
        # Check that tokens are present as params
        token_params = {k: v for k, v in params.items() if k.startswith("t")}
        assert any("nexus" in v for v in token_params.values())
        assert any("industries" in v for v in token_params.values())

    def test_includes_aliases_in_search(self):
        session = _stub_session([])
        ext = _make_extractor(session)
        ext._find_chunks_for_entity("Nexus", ["Nexus Industries", "NXI"])

        call_args = session.execute.call_args
        params = call_args.args[1]
        token_params = {k: v for k, v in params.items() if k.startswith("t")}
        # Should have tokens from both entity name and aliases
        values = list(token_params.values())
        assert any("nexus" in v for v in values)
        assert any("nxi" in v for v in values)

    def test_empty_entity_name_returns_empty(self):
        ext = _make_extractor()
        result = ext._find_chunks_for_entity("", [])
        assert result == []

    def test_tenant_isolation(self):
        session = _stub_session([])
        ext = _make_extractor(session)
        ext.tenant_id = "tenant-ABC"
        ext._find_chunks_for_entity("Nexus", [])

        call_args = session.execute.call_args
        params = call_args.args[1]
        assert params["tid"] == "tenant-ABC"


# ---------------------------------------------------------------------------
# Tests: _extract_properties_from_chunk
# ---------------------------------------------------------------------------

class TestExtractPropertiesFromChunk:
    def test_parses_valid_json_response(self):
        ext = _make_extractor()
        llm_response = json.dumps([
            {
                "attribute_name": "revenue",
                "attribute_value": "$8.45 billion",
                "period": "FY2025",
                "confidence": 0.92,
                "unit": "USD",
            }
        ])
        ext.client.chat.completions.create.return_value = _mock_llm_response(llm_response)

        result = ext._extract_properties_from_chunk(
            "Nexus Industries reported $8.45 billion revenue in FY2025.",
            "Nexus Industries",
            "ORGANIZATION",
        )
        assert len(result) == 1
        assert result[0]["attribute_name"] == "revenue"
        assert result[0]["attribute_value"] == "$8.45 billion"

    def test_handles_json_fenced_response(self):
        ext = _make_extractor()
        llm_response = '```json\n[{"attribute_name": "budget", "attribute_value": "$2.3 billion", "period": null, "confidence": 0.9, "unit": "USD"}]\n```'
        ext.client.chat.completions.create.return_value = _mock_llm_response(llm_response)

        result = ext._extract_properties_from_chunk("chunk", "entity", "TYPE")
        assert len(result) == 1
        assert result[0]["attribute_name"] == "budget"

    def test_returns_empty_for_invalid_json(self):
        ext = _make_extractor()
        ext.client.chat.completions.create.return_value = _mock_llm_response("not json at all")

        result = ext._extract_properties_from_chunk("chunk", "entity", "TYPE")
        assert result == []

    def test_returns_empty_when_no_client(self):
        ext = _make_extractor()
        ext.client = None

        result = ext._extract_properties_from_chunk("chunk", "entity", "TYPE")
        assert result == []

    def test_handles_single_dict_response(self):
        ext = _make_extractor()
        llm_response = json.dumps({
            "attribute_name": "headcount",
            "attribute_value": "12,500",
            "period": "FY2025",
            "confidence": 0.88,
            "unit": None,
        })
        ext.client.chat.completions.create.return_value = _mock_llm_response(llm_response)

        result = ext._extract_properties_from_chunk("chunk", "entity", "TYPE")
        assert len(result) == 1

    def test_handles_llm_exception(self):
        ext = _make_extractor()
        ext.client.chat.completions.create.side_effect = Exception("API error")

        result = ext._extract_properties_from_chunk("chunk", "entity", "TYPE")
        assert result == []

    def test_multiple_facts_from_single_chunk(self):
        ext = _make_extractor()
        llm_response = json.dumps([
            {"attribute_name": "revenue", "attribute_value": "$8.45 billion", "period": "FY2025", "confidence": 0.92, "unit": "USD"},
            {"attribute_name": "headcount", "attribute_value": "12,500", "period": "FY2025", "confidence": 0.88, "unit": None},
            {"attribute_name": "ebitda_margin", "attribute_value": "23.5%", "period": "FY2025", "confidence": 0.85, "unit": "%"},
        ])
        ext.client.chat.completions.create.return_value = _mock_llm_response(llm_response)

        result = ext._extract_properties_from_chunk("chunk", "Nexus", "ORG")
        assert len(result) == 3

    def test_empty_array_response(self):
        ext = _make_extractor()
        ext.client.chat.completions.create.return_value = _mock_llm_response("[]")

        result = ext._extract_properties_from_chunk("no props here", "entity", "TYPE")
        assert result == []


# ---------------------------------------------------------------------------
# Tests: _ground_check
# ---------------------------------------------------------------------------

class TestGroundCheck:
    def test_accepts_value_in_chunk(self):
        ext = _make_extractor()
        assert ext._ground_check(
            "$8.45 billion",
            "Nexus Industries reported $8.45 billion in revenue."
        ) is True

    def test_rejects_fabricated_value(self):
        ext = _make_extractor()
        assert ext._ground_check(
            "$999 trillion",
            "Nexus Industries reported $8.45 billion in revenue."
        ) is False

    def test_case_insensitive(self):
        ext = _make_extractor()
        assert ext._ground_check("Active", "Project status is active.") is True

    def test_empty_value_rejected(self):
        ext = _make_extractor()
        assert ext._ground_check("", "some chunk text") is False

    def test_empty_chunk_rejected(self):
        ext = _make_extractor()
        assert ext._ground_check("$100", "") is False


# ---------------------------------------------------------------------------
# Tests: _resolve_subject
# ---------------------------------------------------------------------------

class TestResolveSubject:
    def test_accepts_entity_in_chunk(self):
        ext = _make_extractor()
        assert ext._resolve_subject(
            "Nexus Industries",
            "Nexus Industries reported $8.45 billion in revenue."
        ) is True

    def test_rejects_absent_entity(self):
        ext = _make_extractor()
        assert ext._resolve_subject(
            "Quantum Shield",
            "Nexus Industries reported $8.45 billion in revenue."
        ) is False

    def test_case_insensitive(self):
        ext = _make_extractor()
        assert ext._resolve_subject(
            "nexus industries",
            "NEXUS INDUSTRIES reported revenue."
        ) is True

    def test_empty_entity_rejected(self):
        ext = _make_extractor()
        assert ext._resolve_subject("", "some chunk") is False

    def test_empty_chunk_rejected(self):
        ext = _make_extractor()
        assert ext._resolve_subject("Nexus", "") is False


# ---------------------------------------------------------------------------
# Tests: confidence thresholds
# ---------------------------------------------------------------------------

class TestConfidenceThresholds:
    def _run_extract(self, confidence):
        """Run extract_for_entity with a single chunk and fact at given confidence."""
        ext = _make_extractor()

        chunk = _Row(
            text="Nexus Industries reported $8.45 billion in revenue for FY2025.",
            document_id="doc-1",
        )
        ext._find_chunks_for_entity = MagicMock(return_value=[chunk])

        llm_response = json.dumps([{
            "attribute_name": "revenue",
            "attribute_value": "$8.45 billion",
            "period": "FY2025",
            "confidence": confidence,
            "unit": "USD",
        }])
        ext.client.chat.completions.create.return_value = _mock_llm_response(llm_response)

        entity = {"id": "e-1", "name": "Nexus Industries", "entity_type": "ORGANIZATION", "aliases": []}
        return ext.extract_for_entity(entity)

    def test_high_confidence_trusted(self):
        facts = self._run_extract(0.92)
        assert len(facts) == 1
        assert facts[0]["lifecycle_state"] == "TRUSTED"

    def test_threshold_085_trusted(self):
        facts = self._run_extract(0.85)
        assert len(facts) == 1
        assert facts[0]["lifecycle_state"] == "TRUSTED"

    def test_medium_confidence_staging(self):
        facts = self._run_extract(0.75)
        assert len(facts) == 1
        assert facts[0]["lifecycle_state"] == "STAGING"

    def test_threshold_060_staging(self):
        facts = self._run_extract(0.60)
        assert len(facts) == 1
        assert facts[0]["lifecycle_state"] == "STAGING"

    def test_low_confidence_rejected(self):
        facts = self._run_extract(0.50)
        assert len(facts) == 0

    def test_very_low_confidence_rejected(self):
        facts = self._run_extract(0.30)
        assert len(facts) == 0


# ---------------------------------------------------------------------------
# Tests: is_value_shaped_name filter (reuse from property_adapter)
# ---------------------------------------------------------------------------

class TestValueShapedNameFilter:
    def test_rejects_currency_names(self):
        assert is_value_shaped_name("$8.45 billion") is True

    def test_rejects_fiscal_period_names(self):
        assert is_value_shaped_name("FY2025") is True

    def test_accepts_real_entity_names(self):
        assert is_value_shaped_name("Nexus Industries") is False
        assert is_value_shaped_name("Quantum Shield") is False


# ---------------------------------------------------------------------------
# Tests: numeric parsing delegation
# ---------------------------------------------------------------------------

class TestNumericParsing:
    def test_parse_numeric_billions(self):
        assert parse_numeric("$8.45 billion") == pytest.approx(8.45e9)

    def test_parse_numeric_plain(self):
        assert parse_numeric("12,500") == pytest.approx(12500.0)

    def test_parse_numeric_none_for_date(self):
        assert parse_numeric("2025-01-15") is None


# ---------------------------------------------------------------------------
# Tests: entity with no matching chunks
# ---------------------------------------------------------------------------

class TestNoChunks:
    def test_no_chunks_returns_empty(self):
        ext = _make_extractor()
        ext._find_chunks_for_entity = MagicMock(return_value=[])

        entity = {"id": "e-1", "name": "Phantom Corp", "entity_type": "ORGANIZATION", "aliases": []}
        facts = ext.extract_for_entity(entity)
        assert facts == []


# ---------------------------------------------------------------------------
# Tests: chunk with no extractable properties
# ---------------------------------------------------------------------------

class TestNoProperties:
    def test_chunk_with_no_properties(self):
        ext = _make_extractor()
        chunk = _Row(text="Nexus Industries was founded in 2015.", document_id="doc-1")
        ext._find_chunks_for_entity = MagicMock(return_value=[chunk])
        ext.client.chat.completions.create.return_value = _mock_llm_response("[]")

        entity = {"id": "e-1", "name": "Nexus Industries", "entity_type": "ORGANIZATION", "aliases": []}
        facts = ext.extract_for_entity(entity)
        assert facts == []


# ---------------------------------------------------------------------------
# Tests: dry_run mode
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_does_not_call_upsert(self):
        ext = _make_extractor(dry_run=True)
        ext.dry_run = True

        chunk = _Row(
            text="Nexus Industries reported $8.45 billion in revenue.",
            document_id="doc-1",
        )
        ext._find_chunks_for_entity = MagicMock(return_value=[chunk])

        llm_response = json.dumps([{
            "attribute_name": "revenue",
            "attribute_value": "$8.45 billion",
            "period": "FY2025",
            "confidence": 0.92,
            "unit": "USD",
        }])
        ext.client.chat.completions.create.return_value = _mock_llm_response(llm_response)

        entity = {"id": "e-1", "name": "Nexus Industries", "entity_type": "ORGANIZATION", "aliases": []}
        facts = ext.extract_for_entity(entity)
        assert len(facts) == 1
        # dry_run doesn't prevent extract_for_entity from returning facts;
        # it prevents extract_all from calling upsert


# ---------------------------------------------------------------------------
# Tests: extract_for_entity integration
# ---------------------------------------------------------------------------

class TestExtractForEntity:
    def test_full_extraction_pipeline(self):
        """End-to-end: entity → chunks → LLM → ground check → facts."""
        ext = _make_extractor()

        chunk = _Row(
            text="Nexus Industries reported revenue of $8.45 billion for FY2025, with 12,500 employees.",
            document_id="doc-1",
        )
        ext._find_chunks_for_entity = MagicMock(return_value=[chunk])

        llm_response = json.dumps([
            {"attribute_name": "revenue", "attribute_value": "$8.45 billion", "period": "FY2025", "confidence": 0.92, "unit": "USD"},
            {"attribute_name": "headcount", "attribute_value": "12,500", "period": "FY2025", "confidence": 0.88, "unit": None},
        ])
        ext.client.chat.completions.create.return_value = _mock_llm_response(llm_response)

        entity = {"id": "e-1", "name": "Nexus Industries", "entity_type": "ORGANIZATION", "aliases": []}
        facts = ext.extract_for_entity(entity)

        assert len(facts) == 2
        rev = [f for f in facts if f["attribute_name"] == "revenue"][0]
        assert rev["attribute_value"] == "$8.45 billion"
        assert rev["numeric_value"] == pytest.approx(8.45e9)
        assert rev["lifecycle_state"] == "TRUSTED"
        assert rev["fiscal_year"] == "2025"
        assert rev["entity_id"] == "e-1"
        assert rev["entity_name"] == "Nexus Industries"

    def test_ground_check_filters_fabricated(self):
        """Fabricated values not in chunk text get filtered out."""
        ext = _make_extractor()

        chunk = _Row(
            text="Nexus Industries reported revenue of $8.45 billion for FY2025.",
            document_id="doc-1",
        )
        ext._find_chunks_for_entity = MagicMock(return_value=[chunk])

        llm_response = json.dumps([
            {"attribute_name": "revenue", "attribute_value": "$8.45 billion", "period": "FY2025", "confidence": 0.92, "unit": "USD"},
            {"attribute_name": "fake_metric", "attribute_value": "$999 trillion", "period": "FY2025", "confidence": 0.95, "unit": "USD"},
        ])
        ext.client.chat.completions.create.return_value = _mock_llm_response(llm_response)

        entity = {"id": "e-1", "name": "Nexus Industries", "entity_type": "ORGANIZATION", "aliases": []}
        facts = ext.extract_for_entity(entity)

        assert len(facts) == 1
        assert facts[0]["attribute_name"] == "revenue"

    def test_subject_resolution_filters_wrong_entity(self):
        """Chunks that don't mention the entity get skipped."""
        ext = _make_extractor()

        chunk = _Row(
            text="Quantum Shield project has a budget of $2.3 billion.",
            document_id="doc-1",
        )
        ext._find_chunks_for_entity = MagicMock(return_value=[chunk])

        entity = {"id": "e-1", "name": "Nexus Industries", "entity_type": "ORGANIZATION", "aliases": []}
        facts = ext.extract_for_entity(entity)
        assert facts == []
