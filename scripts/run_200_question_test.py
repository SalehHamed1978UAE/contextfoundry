#!/usr/bin/env python3
"""Run 200 question test suite for MedSync Health vault."""
import requests
import re
import time
import json
import sys

BASE_URL = "http://localhost:5000"
VAULT_ID = "73beac38-9fdb-4d24-a68e-134b7a03aecd"

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
    
    with open('/tmp/medsync_200_results.json', 'w') as f:
        json.dump({'passed': passed, 'total': len(results), 
                  'pct': round(100*passed/len(results), 1), 
                  'failures': failures}, f, indent=2)
    
    return passed, len(results)

if __name__ == "__main__":
    main()
