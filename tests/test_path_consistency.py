"""
Verify CLI and Web return identical results for the same query.
"""

import os
import pytest
import requests
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

CONSISTENCY_QUERIES = [
    "Who is the CEO?",
    "Who reports to the CEO?",
    "What is the CIO's compensation?",
]

TEST_VAULT_ID = "8d02fa60-6f2f-424f-a1ed-65b7f98fec31"

def get_cli_result(query: str, vault_id: str) -> dict:
    """Get result via CLI path (direct ToolAgent call)."""
    from src.context_foundry.models.schema import set_tenant_context
    from src.context_foundry.agents.tool_agent import ToolAgent
    
    engine = create_engine(os.environ['DATABASE_URL'])
    with Session(engine) as db:
        set_tenant_context(db, vault_id)
        agent = ToolAgent(db, vault_id)
        return agent.query(query, [], vault_context="Hospital Vault")

def get_web_result(query: str, vault_id: str, base_url: str = "http://localhost:5000") -> dict:
    """Get result via Web path (API call)."""
    response = requests.post(
        f"{base_url}/api/vault/{vault_id}/chat",
        json={"query": query},
        timeout=120
    )
    return response.json()

@pytest.mark.parametrize("query", CONSISTENCY_QUERIES)
def test_cli_web_consistency(query):
    """CLI and Web must return same confidence for same query."""
    
    cli_result = get_cli_result(query, TEST_VAULT_ID)
    web_result = get_web_result(query, TEST_VAULT_ID)
    
    cli_confidence = cli_result.get('confidence')
    web_confidence = web_result.get('confidence')
    assert cli_confidence == web_confidence, \
        f"Confidence mismatch for '{query}': CLI={cli_confidence}, Web={web_confidence}"
    
    cli_verdict = cli_result.get('qa_verdict', {}).get('status')
    web_verdict = web_result.get('qa_verdict', {}).get('status')
    assert cli_verdict == web_verdict, \
        f"QA verdict mismatch for '{query}': CLI={cli_verdict}, Web={web_verdict}"

def test_no_duplicate_qa_in_web():
    """Verify web path doesn't run QA twice."""
    web_app_content = Path('web_app.py').read_text()
    
    qa_count = web_app_content.count('QAVerifier(')
    assert qa_count <= 1, f"Found {qa_count} QAVerifier instantiations in web_app.py - should be 0 or 1"

def test_all_build_response_have_qa_verdict():
    """Verify all build_response calls include qa_verdict."""
    import re
    
    tool_agent_content = Path('src/context_foundry/agents/tool_agent.py').read_text()
    
    build_response_pattern = r'build_response\(\s*\n([^)]+)\)'
    matches = list(re.finditer(build_response_pattern, tool_agent_content, re.MULTILINE | re.DOTALL))
    
    missing_verdict = []
    for match in matches:
        call_content = match.group(1)
        line_num = tool_agent_content[:match.start()].count('\n') + 1
        
        if 'qa_verdict=' not in call_content and 'qa_verdict =' not in call_content:
            missing_verdict.append(line_num)
    
    assert len(missing_verdict) == 0, \
        f"build_response calls missing qa_verdict at lines: {missing_verdict}"
