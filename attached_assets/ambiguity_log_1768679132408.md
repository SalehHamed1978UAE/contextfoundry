'''# MedSync Health - Ambiguity Log

This document identifies intentionally ambiguous cases in the document corpus. These cases are designed to test the knowledge retrieval system's ability to handle ambiguity, either by selecting the most appropriate answer or by flagging the ambiguity to the user.

---

## Ambiguous Case 1: Multiple Retention Metrics

**Location:** customer_metrics.md

**Ambiguous Question:** "What is the retention rate?"

**Why It's Ambiguous:** The document contains three different retention metrics:
- Customer Retention Rate: 92%
- Logo Retention Rate: 87%
- Net Revenue Retention (NRR): 115%

**Expected Behavior:** The system should either:
1. Ask for clarification about which retention metric is needed, OR
2. Provide all three metrics with their specific names, OR
3. Default to "Customer Retention Rate" as the most commonly referenced metric

---

## Ambiguous Case 2: OKR Target vs. Actual Goal

**Location:** okrs_2026.md

**Ambiguous Question:** "How many new hospital clients should Sales & Marketing acquire in Q1 2026?"

**Why It's Ambiguous:** The document states:
- "Acquire **15 new hospital clients** in Q1 (Target: 12)"

This creates ambiguity between the stated goal (15) and the target (12).

**Expected Behavior:** The system should either:
1. Recognize the ambiguity and provide both values, OR
2. Default to the primary stated number (15), OR
3. Flag this as an inconsistency

---

## Ambiguous Case 3: PTO Policy with Exceptions

**Location:** hr_policies.md

**Ambiguous Question:** "How many days of PTO do employees receive?"

**Why It's Ambiguous:** The policy states:
- Standard PTO: 20 days
- Director Level Exception: 25 days

**Expected Behavior:** The system should either:
1. Provide the standard policy (20 days) and note the exception, OR
2. Ask for clarification about the employee level, OR
3. Provide both values with context

---

## Ambiguous Case 4: Multiple NPS References

**Location:** customer_metrics.md and okrs_2026.md

**Ambiguous Question:** "What is the NPS?"

**Why It's Ambiguous:** Two different NPS values appear:
- Current NPS: 60 (customer_metrics.md)
- Target NPS for Q1 2026: 60 (okrs_2026.md)

While these happen to be the same value, the context is different (current vs. target).

**Expected Behavior:** The system should:
1. Distinguish between current and target NPS, OR
2. Provide both with temporal context

---

## Ambiguous Case 5: Audit Dates

**Location:** security_compliance.md

**Ambiguous Question:** "When was the audit?"

**Why It's Ambiguous:** Multiple audits are referenced:
- SOC 2 Type II: September 2025
- HIPAA: October 2025
- ISO 27001: June 2025

**Expected Behavior:** The system should either:
1. Ask which certification audit is being referenced, OR
2. Provide all three audit dates with their respective certifications

---

## Ambiguous Case 6: Referral Bonus for "Senior" Roles

**Location:** hr_policies.md

**Ambiguous Question:** "What is the referral bonus for a senior role?"

**Why It's Ambiguous:** The document uses "Senior / Lead (e.g., Senior Engineer)" as a category, which could be interpreted as:
- Any role with "Senior" in the title, OR
- Specifically the "Senior/Lead" level in the table

**Expected Behavior:** The system should:
1. Return $3,000 based on the table category, OR
2. Ask for clarification if the role is truly at the Senior/Lead level

---

## Ambiguous Case 7: Revenue Context

**Location:** financials_2025.md, quarterly reports, and okrs_2026.md

**Ambiguous Question:** "What is the revenue?"

**Why It's Ambiguous:** Multiple revenue figures exist:
- FY 2023 Revenue: $40M
- FY 2024 Revenue: $50M
- FY 2025 Revenue: $80M
- Q4 2025 Revenue: $25M
- 2026 ARR Target: $120M

**Expected Behavior:** The system should:
1. Ask for the specific fiscal year or time period, OR
2. Default to the most recent completed fiscal year (FY 2025)

---

## Ambiguous Case 8: Customer Count vs. New Acquisitions

**Location:** customer_metrics.md and okrs_2026.md

**Ambiguous Question:** "How many customers does MedSync Health have?"

**Why It's Ambiguous:** The documents reference:
- Total customer count: 142 (as of EOY 2025)
- New acquisitions in 2025: 50
- Target for 2026: 70 new acquisitions

**Expected Behavior:** The system should:
1. Return the total customer count (142) as the most direct answer, OR
2. Provide context about new acquisitions if relevant

---

## Ambiguous Case 9: Onboarding Time

**Location:** okrs_2026.md and customer_onboarding_metrics.md

**Ambiguous Question:** "What is the customer onboarding time?"

**Why It's Ambiguous:** The documents state:
- Current average: 52 days (customer_onboarding_metrics.md)
- Previous reference: 60 days (okrs_2026.md)
- Target: 45 days (okrs_2026.md)

**Expected Behavior:** The system should:
1. Distinguish between current, previous, and target onboarding time, OR
2. Provide the most recent actual value with context

---

## Ambiguous Case 10: Data Subject Requests

**Location:** gdpr_privacy_report.md

**Ambiguous Question:** "How many data subject requests were completed?"

**Why It's Ambiguous:** The document shows:
- Total received: 65
- Total completed within 30 days: 65

While these are the same, the question could be asking for total received vs. total completed.

**Expected Behavior:** The system should:
1. Return 65 as both received and completed are the same, OR
2. Clarify that all 65 received requests were completed

---

## Ambiguous Case 11: Quarterly Revenue

**Location:** Multiple quarterly reports

**Ambiguous Question:** "What was the Q3 revenue?"

**Why It's Ambiguous:** Without specifying the year, this could refer to:
- Q3 2025: $20.0M
- Q3 2024: (not explicitly stated but can be calculated)

**Expected Behavior:** The system should:
1. Ask for clarification about which year, OR
2. Default to the most recent Q3 (2025)

---

## Ambiguous Case 12: Employee Count

**Location:** company_profile.md and budget_2026.md

**Ambiguous Question:** "How many employees does MedSync Health have?"

**Why It's Ambiguous:** Multiple employee counts exist:
- Current (Dec 2025): 487
- Target (EOY 2026): 625

**Expected Behavior:** The system should:
1. Provide the current count (487) as the most direct answer, OR
2. Include context about future hiring plans

---

## Ambiguous Case 13: Budget vs. Actual Spending

**Location:** financials_2025.md and budget_2026.md

**Ambiguous Question:** "What is the R&D spending?"

**Why It's Ambiguous:** Multiple values exist:
- Actual FY 2025: $15.0M
- Budgeted 2026: $22.0M

**Expected Behavior:** The system should:
1. Ask for clarification about which year or whether actual vs. budget is needed, OR
2. Provide the most recent actual figure with context

---

## Ambiguous Case 14: Office Location

**Location:** company_profile.md and office_space_plan.md

**Ambiguous Question:** "Where is MedSync Health's office?"

**Why It's Ambiguous:** Multiple offices exist:
- Headquarters: Boston, MA
- European Operations: London, UK

**Expected Behavior:** The system should:
1. Provide both office locations, OR
2. Default to headquarters (Boston) and mention the London office

---

## Ambiguous Case 15: Performance Rating

**Location:** Multiple employee records

**Ambiguous Question:** "What was Emily Williams' performance rating?"

**Why It's Ambiguous:** Multiple performance reviews exist:
- December 2025: 4 - Exceeds Expectations
- June 2025: 4 - Exceeds Expectations

**Expected Behavior:** The system should:
1. Provide the most recent rating (December 2025), OR
2. Ask for clarification about which review period

---

**Total Ambiguous Cases:** 15
'''
