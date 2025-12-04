"""
Pytest configuration for Context Foundry regression tests.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.agents.retrieval import RetrievalAgent
from src.context_foundry.agents.reasoning import ReasoningAgent


@pytest.fixture(scope="session")
def retrieval_agent():
    """Create a single RetrievalAgent for all tests."""
    return RetrievalAgent()


@pytest.fixture(scope="session")
def reasoning_agent():
    """Create a single ReasoningAgent for all tests."""
    return ReasoningAgent()


@pytest.fixture(scope="session")
def run_query(retrieval_agent, reasoning_agent):
    """Factory fixture for running queries."""
    def _run(query: str):
        bundle = retrieval_agent.build_context_bundle(query)
        result = reasoning_agent.reason(bundle)
        result['_bundle'] = bundle
        return result
    return _run
