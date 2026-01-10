"""
Tests for AnswerVerifierAgent

Uses mocked OpenAI client to test verification logic.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import List, Optional

from src.context_foundry.agents.qa_verifier import AnswerVerifierAgent, QAVerdict


@dataclass
class MockEntity:
    name: str
    entity_type: str = "SERVICE"


@dataclass
class MockRelationship:
    relationship_type: str
    source_name: str
    target_name: str
    confidence: float = 0.8


@dataclass
class MockRetrievalResult:
    entity_name: str = "Order Service"
    entity_type: str = "SERVICE"
    entity_found: bool = True
    entities: List[MockEntity] = None
    affected_entities: List[dict] = None
    relationships: List[MockRelationship] = None
    
    def __post_init__(self):
        if self.entities is None:
            self.entities = []
        if self.affected_entities is None:
            self.affected_entities = []
        if self.relationships is None:
            self.relationships = []


class TestStructuralRules:
    """Test Layer 1: Structural checks (no LLM)."""
    
    def test_empty_answer_rejected(self):
        """Empty answer should be REJECTED."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_client = None
        verifier.llm_model = "gpt-4o-mini"
        
        retrieval = MockRetrievalResult()
        
        verdict = verifier._structural_rules(retrieval, "")
        assert verdict.status == "REJECTED"
        assert "Empty" in verdict.reason
    
    def test_whitespace_only_rejected(self):
        """Whitespace-only answer should be REJECTED."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_client = None
        verifier.llm_model = "gpt-4o-mini"
        
        retrieval = MockRetrievalResult()
        
        verdict = verifier._structural_rules(retrieval, "   \n\t  ")
        assert verdict.status == "REJECTED"
    
    def test_no_data_long_answer_suspicious(self):
        """No data retrieved + long answer = SUSPICIOUS."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_client = None
        verifier.llm_model = "gpt-4o-mini"
        
        retrieval = MockRetrievalResult(
            entity_name=None,
            entity_found=False,
            entities=[],
            affected_entities=[],
            relationships=[]
        )
        
        long_answer = "This is a very detailed answer " * 20  # >200 chars
        
        verdict = verifier._structural_rules(retrieval, long_answer)
        assert verdict.status == "SUSPICIOUS"
    
    def test_has_data_passes_to_llm(self):
        """With data present, should pass to LLM verification."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_client = None
        verifier.llm_model = "gpt-4o-mini"
        
        retrieval = MockRetrievalResult(
            entity_name="Order Service",
            entity_found=True,
            relationships=[MockRelationship("DEPENDS_ON", "Order Service", "Database")]
        )
        
        verdict = verifier._structural_rules(retrieval, "The Order Service depends on Database.")
        assert verdict.status == "NEEDS_LLM"


class TestLLMVerification:
    """Test Layer 2: LLM semantic verification."""
    
    @patch.object(AnswerVerifierAgent, '__init__', lambda x, llm_model: None)
    def test_llm_returns_supported(self):
        """LLM returning SUPPORTED should pass through."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_model = "gpt-4o-mini"
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "status": "SUPPORTED",
            "reason": "Answer correctly addresses the question with evidence."
        })
        
        verifier.llm_client = Mock()
        verifier.llm_client.chat.completions.create.return_value = mock_response
        
        retrieval = MockRetrievalResult(
            entity_name="Payment Service",
            relationships=[MockRelationship("MANAGES", "Platform Team", "Payment Service")]
        )
        
        verdict = verifier._llm_verify(
            "Who manages the Payment Service?",
            "Platform Team manages the Payment Service.",
            retrieval
        )
        
        assert verdict.status == "SUPPORTED"
    
    @patch.object(AnswerVerifierAgent, '__init__', lambda x, llm_model: None)
    def test_llm_returns_off_topic(self):
        """LLM returning OFF_TOPIC should be blocked."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_model = "gpt-4o-mini"
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "status": "OFF_TOPIC",
            "reason": "Answer describes dependencies instead of ownership."
        })
        
        verifier.llm_client = Mock()
        verifier.llm_client.chat.completions.create.return_value = mock_response
        
        retrieval = MockRetrievalResult(
            entity_name="Order Service",
            relationships=[MockRelationship("DEPENDS_ON", "Order Service", "Database")]
        )
        
        verdict = verifier._llm_verify(
            "Who is responsible for the Order Service?",
            "The Order Service depends on the Database and Auth Service.",
            retrieval
        )
        
        assert verdict.status == "OFF_TOPIC"
    
    @patch.object(AnswerVerifierAgent, '__init__', lambda x, llm_model: None)
    def test_llm_returns_insufficient(self):
        """LLM returning INSUFFICIENT for partial answers."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_model = "gpt-4o-mini"
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "status": "INSUFFICIENT",
            "reason": "Answer mentions the service but doesn't provide owner information."
        })
        
        verifier.llm_client = Mock()
        verifier.llm_client.chat.completions.create.return_value = mock_response
        
        retrieval = MockRetrievalResult(entity_name="Order Service")
        
        verdict = verifier._llm_verify(
            "Who owns the Order Service?",
            "The Order Service exists in the system.",
            retrieval
        )
        
        assert verdict.status == "INSUFFICIENT"
    
    @patch.object(AnswerVerifierAgent, '__init__', lambda x, llm_model: None)
    def test_llm_json_in_code_block(self):
        """LLM response wrapped in code blocks should be parsed correctly."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_model = "gpt-4o-mini"
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = """```json
{
    "status": "SUPPORTED",
    "reason": "Answer addresses the question."
}
```"""
        
        verifier.llm_client = Mock()
        verifier.llm_client.chat.completions.create.return_value = mock_response
        
        retrieval = MockRetrievalResult()
        
        verdict = verifier._llm_verify("Test?", "Test answer.", retrieval)
        
        assert verdict.status == "SUPPORTED"
    
    @patch.object(AnswerVerifierAgent, '__init__', lambda x, llm_model: None)
    def test_llm_json_parse_error(self):
        """Invalid JSON from LLM should return REVIEW."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_model = "gpt-4o-mini"
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is not valid JSON"
        
        verifier.llm_client = Mock()
        verifier.llm_client.chat.completions.create.return_value = mock_response
        
        retrieval = MockRetrievalResult()
        
        verdict = verifier._llm_verify("Test?", "Test answer.", retrieval)
        
        assert verdict.status == "REVIEW"
        assert "parse" in verdict.reason.lower()
    
    @patch.object(AnswerVerifierAgent, '__init__', lambda x, llm_model: None)
    def test_llm_api_error(self):
        """API error should return REVIEW."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_model = "gpt-4o-mini"
        
        verifier.llm_client = Mock()
        verifier.llm_client.chat.completions.create.side_effect = Exception("API Error")
        
        retrieval = MockRetrievalResult()
        
        verdict = verifier._llm_verify("Test?", "Test answer.", retrieval)
        
        assert verdict.status == "REVIEW"
        assert "failed" in verdict.reason.lower()


class TestFullVerification:
    """Test complete verify() flow."""
    
    @patch.object(AnswerVerifierAgent, '__init__', lambda x, llm_model: None)
    def test_empty_answer_short_circuits(self):
        """Empty answer should be rejected without calling LLM."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_model = "gpt-4o-mini"
        verifier.llm_client = Mock()
        
        retrieval = MockRetrievalResult()
        
        verdict = verifier.verify("Who owns this?", "", retrieval)
        
        assert verdict.status == "REJECTED"
        verifier.llm_client.chat.completions.create.assert_not_called()
    
    @patch.object(AnswerVerifierAgent, '__init__', lambda x, llm_model: None)
    def test_suspicious_short_circuits(self):
        """Suspicious answers should be flagged without LLM."""
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        verifier.llm_model = "gpt-4o-mini"
        verifier.llm_client = Mock()
        
        retrieval = MockRetrievalResult(
            entity_name=None,
            entity_found=False,
            entities=[],
            affected_entities=[],
            relationships=[]
        )
        
        long_answer = "A very detailed fabricated answer. " * 20
        
        verdict = verifier.verify("Who owns this?", long_answer, retrieval)
        
        assert verdict.status == "SUSPICIOUS"
        verifier.llm_client.chat.completions.create.assert_not_called()


class TestHelperMethods:
    """Test _get_name and _get_type helpers."""
    
    def test_get_name_from_object(self):
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        entity = MockEntity(name="Test Service")
        assert verifier._get_name(entity) == "Test Service"
    
    def test_get_name_from_dict(self):
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        entity = {"name": "Test Service", "type": "SERVICE"}
        assert verifier._get_name(entity) == "Test Service"
    
    def test_get_name_from_string(self):
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        assert verifier._get_name("Test Service") == "Test Service"
    
    def test_get_type_from_object(self):
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        rel = MockRelationship("DEPENDS_ON", "A", "B")
        assert verifier._get_type(rel) == "DEPENDS_ON"
    
    def test_get_type_from_dict(self):
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        rel = {"relationship_type": "MANAGES", "source": "A", "target": "B"}
        assert verifier._get_type(rel) == "MANAGES"
    
    def test_get_type_from_dict_with_type_key(self):
        verifier = AnswerVerifierAgent.__new__(AnswerVerifierAgent)
        rel = {"type": "OWNS", "source": "A", "target": "B"}
        assert verifier._get_type(rel) == "OWNS"
