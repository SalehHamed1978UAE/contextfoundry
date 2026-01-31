#!/usr/bin/env python3
"""
Manus HealthTech Q&A Test Suite - First 30 Questions
Tests against vault ID: 73beac38-9fdb-4d24-a68e-134b7a03aecd
"""
import requests
import time
import sys
import re
from datetime import datetime

BASE_URL = "http://localhost:5000"
VAULT_ID = "73beac38-9fdb-4d24-a68e-134b7a03aecd"

QUESTIONS = [
    ("What is the name of the company?", "MedSync Health, Inc."),
    ("When was MedSync Health founded?", "2018"),
    ("Where is MedSync Health headquartered?", "Boston, Massachusetts"),
    ("Who is the CEO of MedSync Health?", "Dr. Evelyn Reed"),
    ("Who is the CFO of MedSync Health?", "Maria Rodriguez"),
    ("Who is the CTO of MedSync Health?", "Ben Carter"),
    ("Who is the Chief Product Officer?", "Sarah Chen"),
    ("Who is the Chief Revenue Officer?", "David Miller"),
    ("What is MedSync Health's primary product?", "MedSync Platform"),
    ("What industry does MedSync Health operate in?", "Healthcare Technology"),
    ("How many employees does MedSync Health have?", "487"),
    ("What is the funding stage of MedSync Health?", "Series C"),
    ("How much did MedSync Health raise in its Series C round?", "$85 million"),
    ("What is the total funding raised by MedSync Health?", "$165 million"),
    ("Where is MedSync Health's European operations located?", "London"),
    ("When was MedSync Health's European operations established?", "2022"),
    ("What is the standard PTO for all employees?", "20 days"),
    ("How many weeks of parental leave does a primary caregiver receive?", "16 weeks"),
    ("How many weeks of parental leave does a secondary caregiver receive?", "8 weeks"),
    ("What is the referral bonus for a Senior Engineer?", "$3,000"),
    ("What is the referral bonus for a Director?", "$8,000"),
    ("What is the maximum hotel rate per night in major metropolitan areas?", "$350"),
    ("Is MedSync Health SOC 2 Type II compliant?", "Yes"),
    ("Is MedSync Health HIPAA compliant?", "Yes"),
    ("Is MedSync Health ISO 27001 certified?", "Yes"),
    ("When was the last SOC 2 audit?", "September 2025"),
    ("When was the last HIPAA audit?", "October 2025"),
    ("When was the last ISO 27001 audit?", "June 2025"),
    ("How many hospital clients does MedSync Health have?", "142"),
    ("How many data breach incidents were reported in 2025?", "Zero"),
]

def normalize_answer(text):
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[.,!?;:"\']', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def check_answer(response_text, expected):
    if not response_text:
        return False
    resp_norm = normalize_answer(response_text)
    exp_norm = normalize_answer(expected)
    if exp_norm in resp_norm:
        return True
    exp_words = exp_norm.split()
    if len(exp_words) >= 2:
        matches = sum(1 for w in exp_words if w in resp_norm)
        if matches >= len(exp_words) * 0.7:
            return True
    if exp_norm == "zero" and ("zero" in resp_norm or "0" in resp_norm or "no" in resp_norm):
        return True
    return False

def run_tests():
    print("=" * 80)
    print(f"MANUS HEALTHTECH Q&A TEST SUITE")
    print(f"Vault ID: {VAULT_ID}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    session = requests.Session()
    
    print("Authenticating...")
    auth_resp = session.post(f'{BASE_URL}/api/dev/auth', json={
        'email': 'e2e-test@contextfoundry.local',
        'tenant_id': VAULT_ID
    })
    if auth_resp.status_code != 200:
        print(f"Auth failed: {auth_resp.status_code} - {auth_resp.text}")
        return 0, len(QUESTIONS)
    print("Authenticated successfully\n")
    
    results = []
    correct = 0
    wrong = 0
    errors = 0
    
    for i, (question, expected) in enumerate(QUESTIONS, 1):
        print(f"\n[Q{i:02d}] {question}")
        print(f"  Expected: {expected}")
        
        try:
            resp = session.post(
                f"{BASE_URL}/api/vault/chat",
                json={"vault_id": VAULT_ID, "query": question},
                timeout=120
            )
            
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer", "")
                confidence = data.get("confidence", 0)
                
                is_correct = check_answer(answer, expected)
                status = "PASS" if is_correct else "FAIL"
                
                if is_correct:
                    correct += 1
                else:
                    wrong += 1
                
                print(f"  Got: {answer[:100]}..." if len(answer) > 100 else f"  Got: {answer}")
                print(f"  Confidence: {confidence}")
                print(f"  Status: {status}")
                
                results.append({
                    "q": i,
                    "question": question,
                    "expected": expected,
                    "got": answer,
                    "confidence": confidence,
                    "status": status
                })
            else:
                errors += 1
                print(f"  ERROR: HTTP {resp.status_code} - {resp.text[:100]}")
                results.append({"q": i, "question": question, "status": "ERROR", "error": f"HTTP {resp.status_code}"})
                
        except Exception as e:
            errors += 1
            print(f"  ERROR: {str(e)}")
            results.append({"q": i, "question": question, "status": "ERROR", "error": str(e)})
        
        time.sleep(0.5)
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total = len(QUESTIONS)
    print(f"Total Questions: {total}")
    print(f"Correct: {correct} ({100*correct/total:.1f}%)")
    print(f"Wrong: {wrong} ({100*wrong/total:.1f}%)")
    print(f"Errors: {errors} ({100*errors/total:.1f}%)")
    print(f"\nAccuracy: {correct}/{total} = {100*correct/total:.1f}%")
    
    print("\n" + "-" * 80)
    print("FAILED QUESTIONS:")
    print("-" * 80)
    for r in results:
        if r.get("status") != "PASS":
            print(f"Q{r['q']}: {r['question']}")
            print(f"   Expected: {r.get('expected', 'N/A')}")
            print(f"   Got: {r.get('got', r.get('error', 'N/A'))[:100]}")
            print()
    
    return correct, total

if __name__ == "__main__":
    correct, total = run_tests()
    sys.exit(0 if correct >= total * 0.95 else 1)
