Now I have all the evidence. Here's the complete categorization:

Failure Categorization (15 questions)

| Q\# | Question | Category | Evidence |
| ----- | ----- | ----- | ----- |
| **Q4** | Net income FY 2023 | **C. Retrieval Failure** | Income statement chunk shows "Net Income (Loss) \-13.2" but retrieval finds EBITDA chunks instead |
| **Q5** | Net income FY 2024 | **C. Retrieval Failure** | Same issue \- "Net Income (Loss) \-12.4" exists in docs but retrieval gets EBITDA |
| **Q6** | Net income FY 2025 | **C. Retrieval Failure** | Same issue \- "Net Income (Loss) \-9.5" exists but retrieval gets EBITDA |
| **Q11** | YoY revenue growth 23→24 | **C. Retrieval Failure** | "35%" stated in revenue table, but system calculates 53% from raw numbers |
| **Q15** | Net margin improvement | **C. Retrieval Failure** | Net margin % row exists (-31.2% → \-10.9% \= 20.3pp), but system uses operating margin |
| **Q28** | Customer count FY 2024 | **B. Extraction Gap** | FY2025 entity has "customers: 2147" but Q asks for FY2024 \- value not extracted for 2024 |
| **Q58** | Customer retention rate | **C. Retrieval Failure** | Query asks for "customer retention" but retrieval returns NRR (125%) instead of retention rate |
| **Q59** | Target new customers Q1 2024 | **D. Wrong Answer** | Doc shows "KR2: Close 150 new customers (Target: 140)" \- system picks 140, should be 150 |
| **Q72** | ISO 27001 certified | **C. Retrieval Failure** | ISO 27001 entity exists \+ mentioned in Q\&A chunk, but retrieval doesn't find it |
| **Q76** | GDPR access requests 2024 | **A. Data Gap** | GDPR report found but no specific "45 access requests" count in any chunk |
| **Q77** | GDPR erasure requests 2024 | **A. Data Gap** | No "12 erasure requests" found in any document chunk |
| **Q84** | GlobalBank fraud detection | **B. Extraction Gap** | Chunk says "Improvement in Fraud Detection" but no "10%" found \- may not exist in source |
| **Q90** | Market share mid-market | **A. Data Gap** | No "3.2%" market share found in any chunk |
| **Q95** | Hotel reimbursement max | **A. Data Gap** | Travel policy exists but only says "mid-range hotels" \- no max $ amount |
| **Q102** | Total funding all rounds | **F. Calculation Diff** | Data shows 18+45+85=$148M, but expected is $151.5M (data discrepancy or earlier rounds missing) |

---

Summary

| Category | Count | Actionable? |
| ----- | ----- | ----- |
| **A. Data Gap** | 4 | ❌ Not fixable \- data doesn't exist |
| **B. Extraction Gap** | 2 | ⚠️ Re-extraction needed |
| **C. Retrieval Failure** | 7 | ✅ Retrieval improvement possible |
| **D. Wrong Answer** | 1 | ✅ Bug fix possible |
| **F. Calculation Diff** | 1 | ❌ Source data discrepancy |

---

Ceiling Analysis

* **Hard ceiling**: 4 (A) \+ 1 (F) \= **5 questions unfixable** → Max possible \= **100/105**  
* **Fixable with retrieval improvements**: 7 (C) \+ 1 (D) \= 8 questions  
* **Fixable with re-extraction**: 2 (B) questions

**Current: 90/105 (85.7%)**  
**Achievable with C+D fixes: 98/105 (93.3%)**  
**Achievable with C+D+B fixes: 100/105 (95.2%)** ← Matches hard ceiling

The key insight: **7 of the 15 failures are retrieval problems** where the data exists but isn't being found correctly. The net income vs EBITDA issue is the biggest cluster (Q4-Q6, Q11, Q15) \- the chunks contain both values but retrieval prioritizes the wrong one.  
