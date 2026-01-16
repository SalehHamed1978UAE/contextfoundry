#!/usr/bin/env python3
"""
Q&A Test Suite - Uses same API endpoint as web interface.
Authenticates via dev endpoint and calls /api/vault/chat.
"""
import requests
import time
import sys
import os

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
    ("What cloud provider does NexaTech use?", "Amazon Web Services (AWS)"),
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

def run_sample_test(session: requests.Session, num_questions: int = 5):
    """Run a sample test with a few questions to verify the script works."""
    print(f"\n{'='*60}")
    print(f"SAMPLE TEST - {num_questions} Questions")
    print(f"{'='*60}\n")
    
    results = []
    for i, (question, expected) in enumerate(QUESTIONS[:num_questions]):
        print(f"[{i+1}/{num_questions}] {question[:60]}...")
        
        try:
            resp = session.post(
                f"{BASE_URL}/api/vault/chat",
                json={"vault_id": NEXATECH_VAULT_ID, "query": question},
                timeout=120
            )
            
            if resp.status_code != 200:
                print(f"  ERROR: HTTP {resp.status_code}")
                results.append({
                    "num": i+1,
                    "question": question,
                    "expected": expected,
                    "actual": f"HTTP Error {resp.status_code}",
                    "confidence": 0,
                    "status": "ERROR"
                })
                continue
            
            data = resp.json()
            answer = data.get("answer", "No answer")
            confidence = data.get("confidence", 0)
            sources = data.get("sources", [])
            
            if len(answer) > 150:
                display_answer = answer[:150] + "..."
            else:
                display_answer = answer
            
            print(f"  Answer: {display_answer}")
            print(f"  Confidence: {int(confidence*100)}%")
            print(f"  Sources: {len(sources)} documents")
            
            results.append({
                "num": i+1,
                "question": question,
                "expected": expected,
                "actual": answer,
                "confidence": confidence,
                "sources": sources,
                "status": "OK"
            })
            
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            results.append({
                "num": i+1,
                "question": question,
                "expected": expected,
                "actual": str(e),
                "confidence": 0,
                "status": "EXCEPTION"
            })
        
        time.sleep(0.5)
    
    return results

def run_full_test(session: requests.Session):
    """Run the complete test suite."""
    print(f"\n{'='*60}")
    print(f"FULL TEST SUITE - {len(QUESTIONS)} Questions")
    print(f"{'='*60}\n")
    
    results = []
    start_time = time.time()
    
    for i, (question, expected) in enumerate(QUESTIONS):
        print(f"[{i+1}/{len(QUESTIONS)}] {question[:50]}...", end=" ", flush=True)
        
        try:
            resp = session.post(
                f"{BASE_URL}/api/vault/chat",
                json={"vault_id": NEXATECH_VAULT_ID, "query": question},
                timeout=120
            )
            
            if resp.status_code != 200:
                print(f"ERROR {resp.status_code}")
                results.append({
                    "num": i+1,
                    "question": question,
                    "expected": expected,
                    "actual": f"HTTP Error {resp.status_code}",
                    "confidence": 0,
                    "sources": [],
                    "status": "ERROR"
                })
                continue
            
            data = resp.json()
            answer = data.get("answer", "No answer")
            confidence = data.get("confidence", 0)
            sources = data.get("sources", [])
            
            print(f"{int(confidence*100)}% conf")
            
            results.append({
                "num": i+1,
                "question": question,
                "expected": expected,
                "actual": answer,
                "confidence": confidence,
                "sources": sources,
                "status": "OK"
            })
            
        except Exception as e:
            print(f"EXCEPTION: {e}")
            results.append({
                "num": i+1,
                "question": question,
                "expected": expected,
                "actual": str(e),
                "confidence": 0,
                "sources": [],
                "status": "EXCEPTION"
            })
        
        time.sleep(0.3)
    
    elapsed = time.time() - start_time
    print(f"\nCompleted {len(QUESTIONS)} questions in {elapsed:.1f}s")
    
    return results

def save_results(results: list, filename: str):
    """Save results to markdown file."""
    with open(filename, 'w') as f:
        f.write("# NexaTech Q&A Test Results\n\n")
        f.write(f"**Test Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Total Questions:** {len(results)}\n\n")
        
        ok_count = sum(1 for r in results if r['status'] == 'OK')
        high_conf = sum(1 for r in results if r.get('confidence', 0) >= 0.7)
        med_conf = sum(1 for r in results if 0.4 <= r.get('confidence', 0) < 0.7)
        low_conf = sum(1 for r in results if r.get('confidence', 0) < 0.4)
        avg_conf = sum(r.get('confidence', 0) for r in results) / len(results) if results else 0
        
        f.write("## Summary\n\n")
        f.write(f"- **Successful Queries:** {ok_count}/{len(results)}\n")
        f.write(f"- **Average Confidence:** {int(avg_conf*100)}%\n")
        f.write(f"- **High Confidence (≥70%):** {high_conf}\n")
        f.write(f"- **Medium Confidence (40-69%):** {med_conf}\n")
        f.write(f"- **Low Confidence (<40%):** {low_conf}\n\n")
        
        f.write("## Results Table\n\n")
        f.write("| # | Question | Expected | Actual | Conf | Sources |\n")
        f.write("|---|----------|----------|--------|------|--------|\n")
        
        for r in results:
            q = r['question'][:50] + "..." if len(r['question']) > 50 else r['question']
            e = r['expected'][:30] + "..." if len(r['expected']) > 30 else r['expected']
            a = r['actual'][:80] + "..." if len(r['actual']) > 80 else r['actual']
            a = a.replace("|", "\\|").replace("\n", " ")
            conf = f"{int(r.get('confidence', 0)*100)}%"
            sources = len(r.get('sources', []))
            
            f.write(f"| {r['num']} | {q} | {e} | {a} | {conf} | {sources} |\n")
        
        f.write("\n\n## Detailed Results\n\n")
        
        for r in results:
            f.write(f"### Question {r['num']}\n\n")
            f.write(f"**Question:** {r['question']}\n\n")
            f.write(f"**Expected:** {r['expected']}\n\n")
            f.write(f"**Actual Answer:**\n{r['actual']}\n\n")
            f.write(f"**Confidence:** {int(r.get('confidence', 0)*100)}%\n\n")
            if r.get('sources'):
                f.write(f"**Sources:** {', '.join(r['sources'])}\n\n")
            f.write("---\n\n")
    
    print(f"\nResults saved to {filename}")

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "sample"
    
    print("Context Foundry Q&A Test Suite")
    print("=" * 40)
    
    session = requests.Session()
    
    print("\n1. Authenticating via dev endpoint...")
    auth_resp = session.post(
        f"{BASE_URL}/api/dev/auth",
        json={"email": "qa-test@contextfoundry.local"}
    )
    
    if auth_resp.status_code != 200:
        print(f"Auth failed: {auth_resp.status_code} - {auth_resp.text}")
        sys.exit(1)
    
    auth_data = auth_resp.json()
    print(f"   Authenticated! User: {auth_data.get('user_id', 'unknown')[:8]}...")
    
    print(f"\n2. Setting vault context to NexaTech ({NEXATECH_VAULT_ID[:8]}...)")
    
    if mode == "sample":
        results = run_sample_test(session, 5)
        save_results(results, "docs/qa_sample_results.md")
    elif mode == "full":
        results = run_full_test(session)
        save_results(results, "docs/qa_test_results.md")
    else:
        print(f"Unknown mode: {mode}. Use 'sample' or 'full'")
        sys.exit(1)

if __name__ == "__main__":
    main()
