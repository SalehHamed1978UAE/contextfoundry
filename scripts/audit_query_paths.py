"""
Audit query paths to ensure all entry points use shared helpers.
Run after any code changes to catch path divergence.
"""

import re
from pathlib import Path

AUDIT_FILES = {
    'web_app.py': {
        'must_not_contain': [
            (r'QAVerifier\(\)', 'Should not instantiate QAVerifier directly'),
            (r'qa_verifier\.verify', 'Should not call QA verify directly'),
        ],
        'must_contain': [
            (r'ToolAgent\(', 'Must instantiate ToolAgent'),
            (r'agent\.query\(|agent_result\s*=\s*agent\.query', 'Must call agent.query()'),
        ],
    },
    'src/context_foundry/agents/tool_agent.py': {
        'must_contain': [
            (r'build_qa_evidence', 'Must use build_qa_evidence helper'),
            (r'calculate_confidence', 'Must use calculate_confidence helper'),
            (r'build_response', 'Must use build_response helper'),
        ],
    },
}

RESPONSE_PATHS = {
    'src/context_foundry/agents/tool_agent.py': {
        'must_have_qa_verdict': True,
        'build_response_pattern': r'build_response\([^)]*\)',
    }
}

def audit_file(filepath: str, rules: dict) -> list:
    violations = []
    
    try:
        content = Path(filepath).read_text()
    except FileNotFoundError:
        return [f"FILE NOT FOUND: {filepath}"]
    
    for pattern, message in rules.get('must_contain', []):
        if not re.search(pattern, content):
            violations.append(f"MISSING in {filepath}: {message}")
    
    for pattern, message in rules.get('must_not_contain', []):
        matches = list(re.finditer(pattern, content))
        if matches:
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                violations.append(f"VIOLATION in {filepath}:{line_num}: {message}")
    
    return violations

def audit_qa_verdict_in_responses(filepath: str) -> list:
    """Ensure all build_response calls include qa_verdict parameter."""
    violations = []
    
    try:
        content = Path(filepath).read_text()
    except FileNotFoundError:
        return [f"FILE NOT FOUND: {filepath}"]
    
    build_response_pattern = r'build_response\(\s*\n([^)]+)\)'
    matches = list(re.finditer(build_response_pattern, content, re.MULTILINE | re.DOTALL))
    
    for match in matches:
        call_content = match.group(1)
        line_num = content[:match.start()].count('\n') + 1
        
        if 'qa_verdict=' not in call_content and 'qa_verdict =' not in call_content:
            violations.append(f"MISSING qa_verdict in build_response at {filepath}:{line_num}")
    
    return violations

def main():
    print("=" * 60)
    print("QUERY PATH AUDIT")
    print("=" * 60)
    
    all_violations = []
    
    for filepath, rules in AUDIT_FILES.items():
        violations = audit_file(filepath, rules)
        all_violations.extend(violations)
    
    qa_violations = audit_qa_verdict_in_responses('src/context_foundry/agents/tool_agent.py')
    all_violations.extend(qa_violations)
    
    if all_violations:
        print("\n[X] AUDIT FAILED\n")
        for v in all_violations:
            print(f"  - {v}")
        print(f"\nTotal violations: {len(all_violations)}")
        return 1
    else:
        print("\n[OK] AUDIT PASSED")
        print("All query paths use shared helpers correctly.")
        print("All build_response calls include qa_verdict parameter.")
        return 0

if __name__ == "__main__":
    exit(main())
