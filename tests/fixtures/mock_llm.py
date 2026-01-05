"""
Mock LLM Fixtures for Deterministic Testing.

Week 4 Stabilization - Mock LLM Support

Provides mock responses for LLM calls to enable:
1. Fast test execution without API calls
2. Deterministic, reproducible test results
3. No dependency on external services

Usage:
    from tests.fixtures.mock_llm import MockLLMClient, mock_openai_responses

    # In test fixtures
    @pytest.fixture
    def mock_llm():
        return MockLLMClient()
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import json


@dataclass
class MockChatMessage:
    """Mock chat completion message."""
    role: str = "assistant"
    content: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class MockChoice:
    """Mock chat completion choice."""
    message: MockChatMessage
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class MockUsage:
    """Mock token usage."""
    prompt_tokens: int = 100
    completion_tokens: int = 50
    total_tokens: int = 150


@dataclass
class MockChatCompletion:
    """Mock OpenAI chat completion response."""
    id: str = "chatcmpl-mock123"
    object: str = "chat.completion"
    created: int = 1704067200
    model: str = "gpt-4o-mini"
    choices: List[MockChoice] = field(default_factory=list)
    usage: MockUsage = field(default_factory=MockUsage)
    
    def __post_init__(self):
        if not self.choices:
            self.choices = [MockChoice(message=MockChatMessage())]


class MockLLMClient:
    """
    Mock LLM client for testing.
    
    Provides canned responses for common query patterns to enable
    deterministic testing without actual LLM API calls.
    """
    
    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.responses = responses or self._default_responses()
        self.call_count = 0
        self.last_messages: List[Dict] = []
    
    def _default_responses(self) -> Dict[str, str]:
        """Default canned responses for common query patterns."""
        return {
            "dependency": json.dumps({
                "entities": [
                    {"name": "API Gateway", "type": "SERVICE"},
                    {"name": "Payment Service", "type": "SERVICE"},
                ],
                "relationships": [
                    {"source": "API Gateway", "target": "Payment Service", "type": "DEPENDS_ON"}
                ]
            }),
            "impact": json.dumps({
                "affected_entities": [
                    {"name": "Order Service", "impact_level": "direct"},
                    {"name": "Frontend", "impact_level": "indirect"},
                ],
                "blast_radius": 2
            }),
            "ownership": json.dumps({
                "owner": "Platform Team",
                "owner_type": "TEAM",
                "confidence": 0.9
            }),
            "entity": json.dumps({
                "name": "Payment Service",
                "type": "SERVICE",
                "description": "Handles all payment processing",
                "status": "active"
            }),
            "extraction": json.dumps({
                "entities": [
                    {"name": "Database", "type": "DATABASE"},
                    {"name": "API", "type": "SERVICE"},
                ],
                "relationships": [
                    {"source": "API", "target": "Database", "type": "CONNECTS_TO"}
                ]
            }),
            "default": "I understand your query. Based on the available information, here is my response."
        }
    
    def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "gpt-4o-mini",
        **kwargs
    ) -> MockChatCompletion:
        """
        Mock chat completion that returns canned responses.
        
        Matches query patterns to return appropriate mock responses.
        """
        self.call_count += 1
        self.last_messages = messages
        
        last_message = messages[-1].get("content", "") if messages else ""
        response_content = self._match_response(last_message)
        
        return MockChatCompletion(
            choices=[
                MockChoice(
                    message=MockChatMessage(content=response_content)
                )
            ]
        )
    
    def _match_response(self, query: str) -> str:
        """Match query to appropriate canned response."""
        query_lower = query.lower()
        
        if any(kw in query_lower for kw in ["depend", "rely", "upstream", "requires"]):
            return self.responses.get("dependency", self.responses["default"])
        
        if any(kw in query_lower for kw in ["impact", "affect", "blast", "downstream"]):
            return self.responses.get("impact", self.responses["default"])
        
        if any(kw in query_lower for kw in ["owns", "owner", "manages", "responsible"]):
            return self.responses.get("ownership", self.responses["default"])
        
        if any(kw in query_lower for kw in ["extract", "parse", "analyze document"]):
            return self.responses.get("extraction", self.responses["default"])
        
        return self.responses.get("default", "")
    
    def create_embeddings(
        self, 
        texts: List[str], 
        model: str = "text-embedding-3-small"
    ) -> List[List[float]]:
        """
        Mock embedding generation.
        
        Returns deterministic fake embeddings based on text hash.
        """
        embeddings = []
        for text in texts:
            text_hash = hash(text)
            embedding = [
                ((text_hash >> i) % 1000) / 1000.0 - 0.5
                for i in range(1536)
            ]
            embeddings.append(embedding)
        return embeddings


class MockOpenAI:
    """
    Drop-in mock for OpenAI client.
    
    Usage:
        import openai
        openai.ChatCompletion = MockOpenAI()
    """
    
    def __init__(self):
        self.mock_client = MockLLMClient()
    
    class chat:
        class completions:
            @staticmethod
            def create(**kwargs) -> MockChatCompletion:
                client = MockLLMClient()
                return client.chat_completion(
                    messages=kwargs.get("messages", []),
                    model=kwargs.get("model", "gpt-4o-mini")
                )


def mock_openai_responses(monkeypatch):
    """
    Pytest fixture to mock OpenAI API calls.
    
    Usage:
        def test_something(monkeypatch):
            mock_openai_responses(monkeypatch)
            # Now all OpenAI calls return mock responses
    """
    mock_client = MockLLMClient()
    
    def mock_chat_create(**kwargs):
        return mock_client.chat_completion(
            messages=kwargs.get("messages", []),
            model=kwargs.get("model", "gpt-4o-mini")
        )
    
    try:
        import openai
        monkeypatch.setattr(openai.chat.completions, "create", mock_chat_create)
    except (ImportError, AttributeError):
        pass


@dataclass
class MockEmbeddingResponse:
    """Mock embedding response."""
    data: List[Dict] = field(default_factory=list)
    model: str = "text-embedding-3-small"
    usage: Dict = field(default_factory=lambda: {"prompt_tokens": 10, "total_tokens": 10})


def create_mock_embedding(text: str, dimensions: int = 1536) -> List[float]:
    """Create a deterministic mock embedding for a text."""
    text_hash = hash(text)
    return [
        ((text_hash >> (i % 64)) % 1000) / 1000.0 - 0.5
        for i in range(dimensions)
    ]
