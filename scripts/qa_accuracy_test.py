#!/usr/bin/env python3
"""
Comprehensive Q&A Accuracy Test - Counts actual correct/wrong/missing answers.
Exports all responses to a file for validation.
"""
import requests
import time
import sys
import os
import json
import re
from datetime import datetime

BASE_URL = "http://localhost:5000"
NEXATECH_VAULT_ID = "bbdef43c-2817-41dd-a5e4-0192893cbf19"

QUESTIONS = [
    ("What was NexaTech's total revenue in FY 2023?", "$42.3 million"),
    ("What was NexaTech's total revenue in FY 2024?", "$64.8 million"),
    ("What was NexaTech's total revenue in FY 2025?", "$87.5 million"),
    ("What was the net income/loss in FY 2023?", "-$13.2 million (loss)"),
    ("What was the net income/loss in FY 2024?", "-$12.4 million (loss)"),
    ("What was the net income/loss in FY 2025?", "-$9.5 million (loss)"),
    ("What was the gross margin percentage in FY 2025?", "76.9%"),
    ("How much did NexaTech spend on Sales & Marketing in FY 2025?", "$35.0 million"),
    ("What was the total cash at the end of FY 2025?", "$98.8 million"),
    ("What was the subscription revenue in FY 2024?", "$55.3 million"),
    ("What was the year-over-year revenue growth rate from FY 2023 to FY 2024?", "35%"),
    ("What was the operating margin in FY 2024?", "-19.8%"),
    ("What was the CAGR for revenue from FY 2023 to FY 2025?", "43.8%"),
    ("What percentage of FY 2025 revenue came from subscriptions?", "85.9%"),
    ("What was the improvement in net margin from FY 2023 to FY 2025?", "20.3 percentage points"),
    ("What was the total funding raised through Series C?", "$85 million"),
    ("What was the total OpEx budget for FY 2024?", "$62.3 million"),
    ("What was the ending cash position targeted in the FY25 forecast?", "$98.8 million"),
    ("What was the committed annual spend with AWS?", "$2.5 million annually"),
    ("What is the target LTV:CAC ratio for Q3 2025?", "3.5x"),
    ("Who is the CEO of NexaTech Solutions?", "Sarah Chen"),
    ("Who is the CTO of NexaTech Solutions?", "Dr. Marcus Rodriguez"),
    ("Who is the CFO of NexaTech Solutions?", "Jennifer Walsh"),
    ("Who is the CRO (Chief Revenue Officer)?", "David Kim"),
    ("When was NexaTech Solutions founded?", "January 2021"),
    ("Where is NexaTech's headquarters located?", "Austin, Texas"),
    ("How many employees did NexaTech have at the end of FY 2024?", "537"),
    ("How many customers did NexaTech have at the end of FY 2024?", "2,147"),
    ("What industry does NexaTech operate in?", "Enterprise Software / Business Intelligence"),
    ("What is NexaTech's flagship product?", "NexaInsight Platform"),
    ("What is the name of the AI-powered autonomous analytics agent project?", "Project Athena"),
    ("When is the beta launch planned for Project Athena?", "September 30, 2026"),
    ("When is the GA (General Availability) launch planned for Project Athena?", "March 31, 2027"),
    ("What is the budget allocated for Project Athena?", "$4.5 million"),
    ("What is the revenue target for FY 2026 in the strategic plan?", "$125 million"),
    ("Which region is NexaTech planning to expand into according to the strategic plan?", "Latin America"),
    ("In which city will NexaTech establish its Latin America headquarters?", "São Paulo, Brazil"),
    ("What is the target revenue from Latin America by end of 2027?", "$15 million"),
    ("What is the company's target for achieving EBITDA profitability?", "FY 2027"),
    ("Who led the Series C funding round?", "Summit Peak Investments"),
    ("What is the company's 401(k) matching policy?", "100% match up to 4%"),
    ("What is the annual professional development stipend?", "$2,000"),
    ("How many paid company holidays does NexaTech observe?", "11"),
    ("What is the referral bonus for hiring an Individual Contributor?", "$2,000"),
    ("What is the referral bonus for hiring a Director or above?", "$5,000"),
    ("What are the three performance rating levels?", "Exceeds Expectations, Meets Expectations, Needs Improvement"),
    ("When does the mid-year performance check-in occur?", "Q3"),
    ("What percentage of women were in leadership roles in 2025?", "38%"),
    ("What is the home office setup stipend for remote employees?", "$500"),
    ("Can remote employees work from public Wi-Fi without VPN?", "No"),
    ("What is the annual quota for an Account Executive in FY 2025?", "$1.2 million in new ARR"),
    ("What is the base salary for an Account Executive?", "$90,000"),
    ("What is the on-target earnings (OTE) for an Account Executive?", "$180,000"),
    ("What is the commission rate for achieving 100-120% of quota?", "12%"),
    ("What is the monthly quota for a Sales Development Representative?", "20 qualified meetings"),
    ("What is the commission per qualified meeting for an SDR?", "$250"),
    ("What is the NPS (Net Promoter Score) mentioned in Q1 2024 all-hands?", "68"),
    ("What is the customer retention rate mentioned in the marketing brochure?", "94%"),
    ("What is the target number of new customers for Q1 2024 OKRs?", "150"),
    ("What is the target Net Revenue Retention (NRR) for Q1 2024?", "Above 120%"),
    ("What is the default API rate limit for the NexaInsight Platform?", "1,000 requests per minute"),
    ("What is NexaTech's cloud provider?", "Amazon Web Services (AWS)"),
    ("What programming languages are used for backend services?", "Python, Go, and Node.js"),
    ("What database is used for metadata and configuration?", "PostgreSQL"),
    ("What is the Recovery Time Objective (RTO) in the disaster recovery plan?", "4 hours"),
    ("What is the Recovery Point Objective (RPO)?", "1 hour"),
    ("How often are database backups performed?", "Every 6 hours"),
    ("What version of the platform was released in January 2025?", "Version 3.0"),
    ("What was the query performance improvement in version 3.0?", "40% faster"),
    ("What are the three products in NexaTech's product portfolio?", "NexaInsight Platform, NexaFlow, NexaSecure"),
    ("Is NexaTech SOC 2 Type II certified?", "Yes"),
    ("Is NexaTech ISO 27001 certified?", "Yes"),
    ("What encryption standard is used for data at rest?", "AES-256"),
    ("What TLS version is required for data in transit?", "TLS 1.2 or higher"),
    ("Is multi-factor authentication (MFA) required?", "Yes"),
    ("How many GDPR access requests were processed in 2024?", "45"),
    ("How many GDPR erasure requests were processed in 2024?", "12"),
    ("What is the timeframe for completing GDPR data subject requests?", "30 days"),
    ("What percentage of employees completed GDPR training?", "100%"),
    ("What state's laws govern the Terms of Service?", "Texas"),
    ("Which customer achieved 25% faster decision-making with NexaInsight?", "GlobalBank Financial Services"),
    ("How much did GlobalBank save annually by using NexaInsight?", "$5 million"),
    ("What percentage reduction in reporting time did GlobalBank achieve?", "50%"),
    ("What improvement in fraud detection did GlobalBank achieve?", "10% improvement"),
    ("Which healthcare customer is featured in a success story?", "MediCare Health Systems"),
    ("What percentage improvement in care coordination did MediCare achieve?", "35%"),
    ("Which retail customer reduced stockouts by 28%?", "RetailMax Corporation"),
    ("What was Tableau's market share according to the competitive analysis?", "18%"),
    ("What was Power BI's market share?", "22%"),
    ("What is NexaTech's market share in the mid-market segment?", "3.2%"),
    ("When was the Q1 2023 board meeting held?", "March 15, 2023"),
    ("What was the revenue for Q1 2023 mentioned in the board meeting?", "$10.2 million"),
    ("What was the year-over-year growth rate mentioned in the Q1 2023 board meeting?", "180%"),
    ("When was the Series C round closed according to board minutes?", "September 2025"),
    ("What is the maximum reimbursement for domestic hotel stays?", "In travel policy"),
    ("How many core values does NexaTech have?", "6"),
    ("What is the AWS contract term?", "3 years (2023-2025)"),
    ("What is the AWS volume discount percentage?", "15%"),
    ("What is the AWS uptime SLA?", "99.99%"),
    ("When does the AWS contract expire?", "December 31, 2025"),
    ("How many employees were hired between the start of FY 2024 and end of FY 2025?", "237 employees"),
    ("What was the total funding raised across all rounds?", "$151.5 million"),
    ("What percentage of revenue does NexaTech spend on R&D in FY 2025?", "32%"),
    ("Who are the three board members mentioned in board meeting minutes?", "John Smith, Maria Garcia, Robert Lee"),
    ("What is the time-to-value for NexaTech compared to industry average?", "6 weeks vs. 16 weeks"),
]


def normalize_answer(answer: str) -> str:
    """Normalize answer for comparison."""
    if not answer:
        return ""
    answer = answer.lower().strip()
    answer = re.sub(r'[,\s]+', ' ', answer)
    answer = re.sub(r'\$\s*', '$', answer)
    answer = re.sub(r'(\d+)\s*%', r'\1%', answer)
    return answer


def extract_key_values(text: str) -> set:
    """Extract key values (numbers, percentages, names) from text."""
    values = set()
    numbers = re.findall(r'\$?[\d,]+\.?\d*\s*(?:million|billion|%|x)?', text.lower())
    values.update(numbers)
    names = re.findall(r'(?:Dr\.\s+)?[A-Z][a-z]+\s+[A-Z][a-z]+', text)
    values.update([n.lower() for n in names])
    return values


def check_answer_match(expected: str, actual: str) -> tuple:
    """
    Check if answer matches expected.
    Returns (status, reason) where status is 'correct', 'wrong', or 'missing'
    """
    if not actual:
        return ('missing', 'No answer provided')
    
    actual_lower = actual.lower()
    expected_lower = expected.lower()
    
    no_answer_patterns = [
        'could not find', 'no information', 'not available', 'unable to find',
        'don\'t have', 'cannot determine', 'not mentioned', 'no data',
        'insufficient information', 'not found in'
    ]
    for pattern in no_answer_patterns:
        if pattern in actual_lower:
            return ('missing', f'Answer indicates missing info: "{pattern}"')
    
    expected_norm = normalize_answer(expected)
    actual_norm = normalize_answer(actual)
    
    if expected_norm in actual_norm:
        return ('correct', 'Direct match')
    
    expected_values = extract_key_values(expected)
    actual_values = extract_key_values(actual)
    
    if expected_values and expected_values.issubset(actual_values):
        return ('correct', 'Key values match')
    
    key_terms = [
        term.strip() for term in re.split(r'[,/()]', expected_lower) 
        if len(term.strip()) > 2
    ]
    matches = sum(1 for term in key_terms if term in actual_lower)
    if matches >= len(key_terms) * 0.7:
        return ('correct', f'Partial match ({matches}/{len(key_terms)} terms)')
    
    if expected_lower in ['yes', 'no']:
        if expected_lower in actual_lower.split()[:20]:
            return ('correct', 'Yes/No match')
    
    return ('wrong', f'Expected "{expected}" but got different value')


def run_accuracy_test():
    """Run full accuracy test and export results."""
    session = requests.Session()
    
    print("Authenticating...")
    auth_resp = session.post(f'{BASE_URL}/api/dev/auth', json={
        'email': 'e2e-test@contextfoundry.local',
        'tenant_id': NEXATECH_VAULT_ID
    })
    if auth_resp.status_code != 200:
        print(f"Auth failed: {auth_resp.status_code}")
        return
    print("Authenticated successfully\n")
    
    results = []
    correct = 0
    wrong = 0
    missing = 0
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = f"docs/qa_accuracy_results_{timestamp}.json"
    
    print(f"Running {len(QUESTIONS)} questions...")
    print("=" * 80)
    
    for i, (question, expected) in enumerate(QUESTIONS, 1):
        print(f"\n[{i:3d}/{len(QUESTIONS)}] {question[:60]}...")
        
        try:
            resp = session.post(f'{BASE_URL}/api/vault/chat', json={
                'vault_id': NEXATECH_VAULT_ID,
                'query': question
            }, timeout=120)
            
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get('answer', '')
                confidence = data.get('confidence', 0)
                
                status, reason = check_answer_match(expected, answer)
                
                if status == 'correct':
                    correct += 1
                    symbol = '✓'
                elif status == 'wrong':
                    wrong += 1
                    symbol = '✗'
                else:
                    missing += 1
                    symbol = '?'
                
                print(f"         {symbol} {status.upper()}: {reason}")
                print(f"         Expected: {expected}")
                print(f"         Got: {answer[:100]}..." if len(answer) > 100 else f"         Got: {answer}")
                
                results.append({
                    'question_num': i,
                    'question': question,
                    'expected': expected,
                    'actual': answer,
                    'confidence': confidence,
                    'status': status,
                    'reason': reason
                })
            else:
                missing += 1
                print(f"         ? ERROR: HTTP {resp.status_code}")
                results.append({
                    'question_num': i,
                    'question': question,
                    'expected': expected,
                    'actual': f'ERROR: {resp.status_code}',
                    'confidence': 0,
                    'status': 'missing',
                    'reason': f'HTTP error {resp.status_code}'
                })
                
        except Exception as e:
            missing += 1
            print(f"         ? EXCEPTION: {str(e)[:50]}")
            results.append({
                'question_num': i,
                'question': question,
                'expected': expected,
                'actual': f'EXCEPTION: {str(e)}',
                'confidence': 0,
                'status': 'missing',
                'reason': str(e)
            })
        
        time.sleep(0.5)
    
    print("\n" + "=" * 80)
    print("\n" + "=" * 80)
    print("ACCURACY SUMMARY")
    print("=" * 80)
    print(f"Correct:  {correct:3d}/105  ({correct/105*100:.1f}%)")
    print(f"Wrong:    {wrong:3d}/105  ({wrong/105*100:.1f}%)")
    print(f"Missing:  {missing:3d}/105  ({missing/105*100:.1f}%)")
    print("=" * 80)
    
    if correct >= 100:
        print("TARGET MET: 100/105 minimum achieved!")
    else:
        print(f"TARGET NOT MET: Need {100 - correct} more correct answers")
    
    export_data = {
        'timestamp': timestamp,
        'summary': {
            'total': 105,
            'correct': correct,
            'wrong': wrong,
            'missing': missing,
            'accuracy_pct': round(correct / 105 * 100, 1)
        },
        'results': results
    }
    
    with open(export_file, 'w') as f:
        json.dump(export_data, f, indent=2)
    print(f"\nResults exported to: {export_file}")
    
    md_file = f"docs/qa_accuracy_results_{timestamp}.md"
    with open(md_file, 'w') as f:
        f.write(f"# Q&A Accuracy Test Results\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"| Metric | Count | Percentage |\n")
        f.write(f"|--------|-------|------------|\n")
        f.write(f"| Correct | {correct} | {correct/105*100:.1f}% |\n")
        f.write(f"| Wrong | {wrong} | {wrong/105*100:.1f}% |\n")
        f.write(f"| Missing | {missing} | {missing/105*100:.1f}% |\n")
        f.write(f"| **Total** | **105** | **100%** |\n\n")
        
        if wrong > 0 or missing > 0:
            f.write(f"## Issues\n\n")
            for r in results:
                if r['status'] != 'correct':
                    f.write(f"### Q{r['question_num']}: {r['question']}\n")
                    f.write(f"- **Status:** {r['status'].upper()}\n")
                    f.write(f"- **Expected:** {r['expected']}\n")
                    f.write(f"- **Got:** {r['actual'][:200]}{'...' if len(r['actual']) > 200 else ''}\n")
                    f.write(f"- **Reason:** {r['reason']}\n\n")
        
        f.write(f"## All Results\n\n")
        f.write(f"| # | Status | Question | Expected | Actual |\n")
        f.write(f"|---|--------|----------|----------|--------|\n")
        for r in results:
            status_emoji = '✓' if r['status'] == 'correct' else ('✗' if r['status'] == 'wrong' else '?')
            q_short = r['question'][:40] + '...' if len(r['question']) > 40 else r['question']
            a_short = r['actual'][:40] + '...' if len(r['actual']) > 40 else r['actual']
            f.write(f"| {r['question_num']} | {status_emoji} | {q_short} | {r['expected']} | {a_short} |\n")
    
    print(f"Markdown report: {md_file}")
    
    return correct, wrong, missing


if __name__ == "__main__":
    run_accuracy_test()
