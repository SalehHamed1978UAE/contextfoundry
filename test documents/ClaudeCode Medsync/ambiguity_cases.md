# Ambiguity Cases Log - MedSync Health

This document lists 20 intentionally ambiguous cases designed to test AI system disambiguation and coherence checking capabilities.

---

## Case 1: Multiple Retention Metrics

**Location:** SALES-003 (Churn Analysis FY 2024)

**Ambiguity:**
- Customer Retention Rate: 91%
- Logo Retention: 87%
- Net Revenue Retention (NRR): 118%
- Gross Revenue Retention (GRR): 94%

**Test Question:** "What is the retention rate?"

**Expected System Behavior:** Should flag ambiguity or ask for clarification about which retention metric is needed.

**Why Ambiguous:** Four different retention metrics exist, each measuring different aspects of customer retention.

---

## Case 2: OKR Target Format

**Location:** STRAT-005 (Engineering Department OKRs 2024)

**Ambiguity:**
KR2: Acquire 500 new hospital clients (Target: 450, Stretch: 600)

**Test Question:** "What is the target for new hospital clients?"

**Expected System Behavior:** Should recognize that 450 is labeled "Target" but 500 is the KR goal, creating ambiguity.

**Why Ambiguous:** The KR states 500, but explicitly labels 450 as "Target" and 600 as "Stretch," creating confusion about the actual target.

---

## Case 3: Level-Based Referral Bonus

**Location:** HR-006 (Referral Program)

**Ambiguity:**
- IC (Individual Contributor): AED 7,350
- Manager: AED 12,862.50
- Director+: AED 18,375

**Test Question:** "What is the referral bonus?"

**Expected System Behavior:** Should note that the bonus depends on the employee's level and ask for clarification.

**Why Ambiguous:** Three different bonus amounts exist depending on job level.

---

## Case 4: Product Revenue vs ARR

**Location:** PROD-001 (Product Specification) vs FIN-001 (Annual Report)

**Ambiguity:**
- PROD-001 states ARR: AED 183,500,000
- FIN-001 states FY 2024 Revenue: AED 186,690,000

**Test Question:** "What is the revenue for MedSync Connect?"

**Expected System Behavior:** Should recognize the difference between ARR (Annual Recurring Revenue) and actual FY revenue.

**Why Ambiguous:** ARR and actual revenue are different metrics; ARR excludes one-time fees and services.

---

## Case 5: Average vs Range Compensation

**Location:** HR-007 (Compensation Bands)

**Ambiguity:**
- Document states "Average IC Compensation: AED 294,000"
- But actual range might be AED 220,500 - AED 367,500

**Test Question:** "What is the IC compensation?"

**Expected System Behavior:** Should clarify whether asking for average, minimum, maximum, or range.

**Why Ambiguous:** Compensation can be expressed as average, range, or specific band levels.

---

## Case 6: Fiscal Year vs Calendar Year

**Location:** Multiple financial documents

**Ambiguity:**
- MedSync Health uses calendar year as fiscal year (Jan 1 - Dec 31)
- But some metrics might reference "FY 2024" vs "CY 2024"

**Test Question:** "What was the revenue in fiscal year 2024?"

**Expected System Behavior:** Should recognize that FY = CY for this company, but the ambiguity exists in general business contexts.

**Why Ambiguous:** In many companies, fiscal year differs from calendar year.

---

## Case 7: Customer Count vs Customer Organization Count

**Location:** SALES-001 (Customer Metrics) vs PROD-001 to PROD-004 (Product Specs)

**Ambiguity:**
- Total unique customer organizations: 3,930
- Product-specific customer counts sum to more than 3,930 (some customers use multiple products)

**Test Question:** "How many customers does MedSync Health have?"

**Expected System Behavior:** Should clarify whether asking for unique organizations or total product subscriptions.

**Why Ambiguous:** Customers can be counted by unique organizations or by product subscriptions.

---

## Case 8: Employee Count by Time Period

**Location:** Multiple documents

**Ambiguity:**
- Q4 2024: 1,200 employees
- Average FY 2024: ~1,163 employees
- End of FY 2024: 1,200 employees

**Test Question:** "How many employees in 2024?"

**Expected System Behavior:** Should clarify whether asking for end-of-year, average, or specific quarter.

**Why Ambiguous:** Employee count varies throughout the year.

---

## Case 9: Revenue by Product vs Revenue by Geography

**Location:** FIN-001 (Annual Report 2024)

**Ambiguity:**
- Revenue by Product: 4 categories summing to AED 485,100,000
- Revenue by Geography: 3 regions summing to AED 485,100,000

**Test Question:** "What is the revenue breakdown?"

**Expected System Behavior:** Should ask whether breakdown is by product, geography, or another dimension.

**Why Ambiguous:** Multiple valid breakdowns exist for the same total revenue.

---

## Case 10: NPS Score Timing

**Location:** SALES-002 (NPS Analysis Q4 2024) vs PROD-001 to PROD-004 (Product Specs)

**Ambiguity:**
- Product specs show NPS scores (may be annual or latest)
- SALES-002 shows Q4 2024 NPS scores

**Test Question:** "What is the NPS score for MedSync Connect?"

**Expected System Behavior:** Should recognize that NPS can vary by time period.

**Why Ambiguous:** NPS scores change over time; question doesn't specify time period.

---

## Case 11: Headcount by Department vs by Office

**Location:** HR-015 (Org Chart)

**Ambiguity:**
- Headcount by department: 8 departments totaling 1,200
- Headcount by office: 4 offices totaling 1,200

**Test Question:** "What is the headcount breakdown?"

**Expected System Behavior:** Should ask whether breakdown is by department, office, or another dimension.

**Why Ambiguous:** Multiple valid ways to break down headcount.

---

## Case 12: Attrition Rate Types

**Location:** HR-013 (DEI Report)

**Ambiguity:**
- Voluntary Attrition: 12.5%
- Involuntary Attrition: 3.2%
- Total Attrition: 15.7%

**Test Question:** "What is the attrition rate?"

**Expected System Behavior:** Should clarify whether asking for voluntary, involuntary, or total attrition.

**Why Ambiguous:** Three different attrition metrics exist.

---

## Case 13: Funding Amount vs Post-Money Valuation

**Location:** FIN-014 (Funding History) vs FIN-012 (Investor Presentation)

**Ambiguity:**
- Series D funding raised: AED 551,250,000
- Post-money valuation: [Not explicitly stated]

**Test Question:** "What is the Series D amount?"

**Expected System Behavior:** Should clarify whether asking for funding raised or post-money valuation.

**Why Ambiguous:** "Series D amount" could refer to capital raised or resulting valuation.

---

## Case 14: Product Launch Date vs GA Date

**Location:** PROD-001 to PROD-004 (Product Specifications)

**Ambiguity:**
- Launch date might refer to beta launch, limited availability, or general availability

**Test Question:** "When was MedSync Connect launched?"

**Expected System Behavior:** Should recognize that "launch" could mean different milestones.

**Why Ambiguous:** Products can have multiple launch phases (beta, limited, GA).

---

## Case 15: Certification Date vs Renewal Date

**Location:** SEC-001 (SOC 2 Report)

**Ambiguity:**
- First certified: August 2021
- Renewed: August 2024

**Test Question:** "When was SOC 2 certification obtained?"

**Expected System Behavior:** Should clarify whether asking for initial certification or most recent renewal.

**Why Ambiguous:** Certifications have initial dates and renewal dates.

---

## Case 16: Budget vs Actual Spending

**Location:** FIN-015 (Budget Plan) vs FIN-001 (Annual Report)

**Ambiguity:**
- Budgeted amounts for FY 2025
- Actual spending for FY 2024

**Test Question:** "What is the Engineering department budget?"

**Expected System Behavior:** Should clarify whether asking for budget (planned) or actual spending.

**Why Ambiguous:** Budget and actual spending are different metrics.

---

## Case 17: Average Deal Size Calculation Method

**Location:** SALES-001 (Customer Metrics) vs FIN-001 (Annual Report)

**Ambiguity:**
- Could be calculated as: Total Revenue / Total Customers
- Or: Total Revenue / New Customers Acquired
- Or: Average ACV by customer type

**Test Question:** "What is the average deal size?"

**Expected System Behavior:** Should clarify the calculation method.

**Why Ambiguous:** Multiple valid ways to calculate average deal size.

---

## Case 18: Office Location vs Legal Entity Location

**Location:** OPS-002 (Office Leases) vs LEGAL-008 (Corporate Bylaws)

**Ambiguity:**
- Physical offices: Boston, London, Berlin, Singapore
- Legal entity incorporation: [May be Delaware or another jurisdiction]

**Test Question:** "Where is MedSync Health located?"

**Expected System Behavior:** Should clarify whether asking for HQ, all offices, or legal incorporation.

**Why Ambiguous:** Companies have multiple "locations" (HQ, offices, legal entity).

---

## Case 19: Customer Type Overlap

**Location:** SALES-001 (Customer Metrics) vs PROD-001 to PROD-004 (Product Specs)

**Ambiguity:**
- Some hospitals are also insurance providers (integrated health systems)
- Customer counts by type may have overlap

**Test Question:** "How many hospital customers?"

**Expected System Behavior:** Should recognize potential overlap in customer categorization.

**Why Ambiguous:** Some customers fit multiple categories (e.g., integrated health systems).

---

## Case 20: Pricing Tier Ambiguity

**Location:** PROD-015 (Pricing Sheets)

**Ambiguity:**
Standard Tier: AED 2,940/month (Target: AED 2,205, Enterprise: AED 3,675)

**Test Question:** "What is the Standard tier pricing?"

**Expected System Behavior:** Should recognize that AED 2,940 is listed but "Target" shows AED 2,205, creating confusion.

**Why Ambiguous:** Multiple prices listed for the same tier with different labels.

---

## Summary

**Total Ambiguous Cases:** 20

**Categories:**
- Multiple metrics with similar names: 5 cases
- Level/role-based variations: 3 cases
- Time period ambiguities: 4 cases
- Calculation method ambiguities: 3 cases
- Categorization overlaps: 3 cases
- Terminology ambiguities: 2 cases

**Testing Purpose:**
These ambiguities test the AI system's ability to:
1. Recognize when a question has multiple valid answers
2. Request clarification from users
3. Provide context about why ambiguity exists
4. Suggest which interpretation is most likely based on context
5. Handle edge cases in data consistency checking

**Recommended System Responses:**
- "I found multiple retention metrics. Which one do you need: Logo Retention (87%), Customer Retention (91%), GRR (94%), or NRR (118%)?"
- "The referral bonus varies by level: IC (AED 7,350), Manager (AED 12,862.50), or Director+ (AED 18,375). Which level are you asking about?"
- "I found both ARR (AED 183,500,000) and FY 2024 revenue (AED 186,690,000) for MedSync Connect. Which metric do you need?"
