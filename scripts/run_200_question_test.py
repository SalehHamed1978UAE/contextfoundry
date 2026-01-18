#!/usr/bin/env python3
"""Run 235 question test suite for MedSync Health vault."""
import requests
import re
import time
import json
import sys
import os
from datetime import datetime

BASE_URL = "http://localhost:5000"
VAULT_ID = "73beac38-9fdb-4d24-a68e-134b7a03aecd"
RESULTS_DIR = "test_results"

def parse_questions(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    pattern = r'\*\*Q(\d+):\*\*\s*(.+?)\n\*\*A\1:\*\*\s*(.+?)(?=\n\*\*|$)'
    return [(int(n), q.strip(), a.strip().split('\n')[0].strip()) 
            for n, q, a in re.findall(pattern, content, re.DOTALL)]

def check_answer(response, expected):
    if not response: return False
    resp = response.lower().replace(',', '').replace('$', '').strip()
    exp = expected.lower().replace(',', '').replace('$', '').strip()
    if exp in resp: return True
    words = [w for w in exp.split() if len(w) > 2][:6]
    return words and sum(1 for w in words if w in resp) >= len(words) * 0.5

def main():
    questions = parse_questions('test_documents/medsync_health/question_bank_200.md')
    print(f"Testing {len(questions)} questions from MedSync Health vault")
    print("=" * 60)
    
    session = requests.Session()
    session.post(f'{BASE_URL}/api/dev/auth', 
                json={'email': 'test@test.com', 'tenant_id': VAULT_ID})
    
    results = []
    
    for i, (qnum, query, expected) in enumerate(questions):
        try:
            r = session.post(f"{BASE_URL}/api/vault/chat",
                           json={"vault_id": VAULT_ID, "query": query}, timeout=90)
            answer = r.json().get('answer', '')[:300]
            passed = check_answer(answer, expected)
            results.append({
                'q': qnum, 'passed': passed, 
                'query': query[:50], 'expected': expected[:40],
                'answer': '' if passed else answer[:60]
            })
            if not passed:
                print(f"✗ Q{qnum}: exp='{expected[:30]}' got='{answer[:50]}'")
        except Exception as e:
            results.append({'q': qnum, 'passed': False, 'error': str(e)[:50]})
            print(f"✗ Q{qnum}: ERROR - {e}")
        
        if (i + 1) % 25 == 0:
            p = sum(1 for r in results if r['passed'])
            print(f"[{i+1}/{len(questions)}] {p}/{i+1} passed ({100*p/(i+1):.0f}%)")
    
    passed = sum(1 for r in results if r['passed'])
    failures = [r for r in results if not r['passed']]
    
    print("\n" + "=" * 60)
    print(f"FINAL: {passed}/{len(results)} ({100*passed/len(results):.1f}%)")
    print("=" * 60)
    
    if failures:
        print(f"\n{len(failures)} failures (first 20):")
        for r in failures[:20]:
            print(f"  Q{r['q']}: {r.get('answer', r.get('error', ''))[:50]}")
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output = {
        'timestamp': timestamp,
        'summary': {
            'total': len(results),
            'passed': passed,
            'failed': len(failures),
            'accuracy_pct': round(100*passed/len(results), 1)
        },
        'breakdown': {
            'Q1-100': {'passed': sum(1 for r in results if r['q'] <= 100 and r['passed']), 'total': sum(1 for r in results if r['q'] <= 100)},
            'Q101-200': {'passed': sum(1 for r in results if 100 < r['q'] <= 200 and r['passed']), 'total': sum(1 for r in results if 100 < r['q'] <= 200)},
            'Q201-235': {'passed': sum(1 for r in results if r['q'] > 200 and r['passed']), 'total': sum(1 for r in results if r['q'] > 200)}
        },
        'failures': failures
    }
    
    latest_file = f"{RESULTS_DIR}/medsync_health_235q_results.json"
    timestamped_file = f"{RESULTS_DIR}/medsync_health_235q_{timestamp}.json"
    
    with open(latest_file, 'w') as f:
        json.dump(output, f, indent=2)
    with open(timestamped_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to:")
    print(f"  - {latest_file} (latest)")
    print(f"  - {timestamped_file} (archived)")
    
    return passed, len(results)

if __name__ == "__main__":
    main()
