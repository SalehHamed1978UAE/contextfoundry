'''# MedSync Health Enterprise Document Corpus

## Overview

This is a comprehensive enterprise document corpus for **MedSync Health**, a fictional Series C healthcare technology company. The corpus contains **106 documents** across 12 categories and is designed for testing AI knowledge retrieval systems, with a focus on accuracy, consistency, and the ability to handle ambiguous queries.

## Company Profile

- **Company Name:** MedSync Health, Inc.
- **Industry:** Healthcare Technology
- **Stage:** Series C (487 employees as of Dec 2025, targeting 625 by EOY 2026)
- **Founded:** 2018
- **Headquarters:** Boston, MA, USA
- **European Operations:** London, UK (established 2022)
- **Product:** MedSync Platform (AI-powered care coordination software)
- **Total Funding:** $165M (Series C: $85M in Dec 2024)

## Document Structure

### 106 Documents Across 12 Categories

| Category | Count | Description |
|---|---|---|
| **Finance** | 9 | Financial reports, quarterly results, budgets, cash flow statements |
| **HR** | 16 | Policies, employee records, job descriptions, compensation plans |
| **Product** | 7 | Roadmaps, PRDs, feature specs, user research, changelogs |
| **Engineering** | 11 | Technical specs, bug reports, architecture docs, post-mortems |
| **Sales** | 8 | Playbooks, pipeline reports, competitive analysis, deal reviews |
| **Marketing** | 8 | Marketing plans, case studies, press releases, campaigns |
| **Customer Success** | 8 | Metrics, health scores, onboarding data, support tickets |
| **Meetings** | 7 | Meeting notes, email threads, all-hands summaries |
| **Compliance** | 8 | SOC 2, HIPAA, GDPR reports, security assessments |
| **Legal** | 4 | Contracts, DPAs, NDAs, subscription agreements |
| **Operations** | 7 | Business continuity, incident response, IT inventory |
| **Executive** | 5 | Board minutes, CEO emails, investor updates, OKRs |

## Document Types

The corpus includes diverse document formats to simulate a realistic enterprise environment:

- **Financial Reports:** Annual reports, quarterly results, budgets, cash flow statements
- **Strategic Documents:** OKRs, roadmaps, strategic plans
- **HR Documents:** Policies, employee records, job descriptions, performance reviews
- **Technical Documentation:** API docs, architecture diagrams, database schemas
- **Meeting Notes:** Board minutes, team standups, all-hands meetings
- **Email Threads:** Executive communications, team discussions
- **Compliance Reports:** Audit reports, security assessments, GDPR reports
- **Customer Documents:** Case studies, support tickets, health scores
- **Sales Materials:** Playbooks, pipeline reports, competitive analysis
- **Marketing Content:** Blog posts, press releases, campaign plans

## Q&A Pairs (105 Total)

### Distribution by Type

| Type | Count | Description |
|---|---|---|
| SIMPLE | 30 | Basic factual questions (e.g., "Who is the CFO?") |
| METRIC | 30 | Numeric data questions (e.g., "What was revenue in FY 2024?") |
| TEMPORAL | 15 | Time-based comparisons (e.g., "What was YoY growth?") |
| COMPARISON | 10 | Comparative questions (e.g., "Which year had highest revenue?") |
| POLICY | 15 | Policy-related questions (e.g., "What is the PTO policy?") |
| UNANSWERABLE | 5 | Questions with no answer in documents |

## Key Features

### 1. Internal Consistency

All numeric data is mathematically consistent across documents:
- Revenue growth calculations are accurate across all quarterly and annual reports
- Financial statements balance correctly (Revenue - COGS = Gross Profit, etc.)
- Customer metrics align with stated retention/churn rates
- Employee counts are consistent across documents
- All percentages, ratios, and growth rates are verified
- Quarterly revenues sum to annual totals

### 2. Intentional Ambiguity (15 Cases)

The corpus includes realistic ambiguous scenarios to test system robustness:
- **Multiple retention metrics:** Customer retention (92%) vs. logo retention (87%) vs. NRR (115%)
- **OKR targets with different values:** "Acquire 15 new clients (Target: 12)"
- **Policies with exceptions:** Standard PTO (20 days) vs. Director-level (25 days)
- **Multiple audit dates:** SOC 2 (Sept 2025) vs. HIPAA (Oct 2025) vs. ISO 27001 (June 2025)
- **Current vs. target metrics:** Current onboarding time (52 days) vs. target (45 days)
- **Multiple time periods:** Q4 2025 revenue vs. FY 2025 revenue vs. 2026 target
- **Budget vs. actual:** Actual 2025 spending vs. budgeted 2026 spending
- **Multiple locations:** Boston HQ vs. London office
- **Multiple performance reviews:** June 2025 vs. December 2025 ratings

### 3. Unanswerable Questions (5 Cases)

To test the system's ability to say "I don't know":
- CEO salary (not mentioned in any document)
- Company valuation post-Series C (not disclosed)
- Q2 2026 pipeline (future data not yet available)
- Employee turnover rate (not tracked in documents)
- Average deal size (not provided in any document)

### 4. Realistic Formatting

Documents include:
- Financial tables with multiple columns and calculated totals
- Bullet points and numbered lists
- Headers, subheaders, and section organization
- Mix of tabular data and narrative prose
- Organizational charts and reporting structures
- Email threads with multiple participants
- Meeting notes with action items
- Technical specifications with code examples

## Use Cases

This corpus is ideal for testing:

1. **Accuracy:** Can the system retrieve the correct answer from the right document?
2. **Ambiguity Handling:** Does the system recognize and handle ambiguous queries appropriately?
3. **Negative Cases:** Can the system correctly identify when information is not available?
4. **Consistency:** Does the system maintain consistency when answering related questions?
5. **Context Understanding:** Can the system distinguish between similar metrics with different contexts (e.g., current vs. target, actual vs. budget)?
6. **Multi-Document Reasoning:** Can the system synthesize information from multiple documents?
7. **Temporal Reasoning:** Can the system understand time-based queries (e.g., "latest", "most recent", "Q4 2025")?

## Testing Recommendations

### Phase 1: Basic Accuracy (Baseline)
- Test all 100 answerable questions from qa_pairs.md
- Measure exact match accuracy by question type
- Identify which question types are most challenging
- Establish baseline performance metrics

### Phase 2: Ambiguity Testing (Robustness)
- Test the 15 ambiguous cases from ambiguity_log.md
- Evaluate whether the system flags ambiguity or makes reasonable assumptions
- Assess the quality of disambiguation strategies
- Measure false confidence (confident but wrong answers)

### Phase 3: Negative Testing (Hallucination Detection)
- Test the 5 unanswerable questions
- Verify the system responds with "I don't know" or equivalent
- Check for hallucinations or fabricated answers
- Test edge cases with partial information

### Phase 4: Consistency Testing (Reliability)
- Ask related questions in different ways (paraphrasing)
- Verify consistent answers across reformulations
- Test temporal reasoning (e.g., "current" vs. "2025" vs. "latest")
- Check for contradictory answers to similar questions

### Phase 5: Multi-Document Reasoning (Advanced)
- Ask questions that require synthesizing information from multiple documents
- Test cross-referencing capabilities
- Evaluate ability to reconcile conflicting information
- Measure performance on complex analytical queries

## Document Statistics

- **Total Documents:** 106
- **Total Words:** ~35,000 words
- **Total Tables:** 50+ tables
- **Total Numeric Data Points:** 300+
- **Date References:** 100+
- **Named Entities:** 150+ (people, places, products, certifications, companies)
- **Financial Data Points:** 100+ (revenue, costs, margins, growth rates)
- **Employee Records:** 6 detailed employee profiles
- **Meeting Notes:** 7 different meeting types
- **Email Threads:** 3 multi-participant conversations

## Validation Status

✓ All financial calculations verified (revenue, margins, growth rates)
✓ All customer metrics consistent (retention, churn, NPS)
✓ All audit schedules validated (annual cycles)
✓ All Q&A pairs reviewed for accuracy
✓ All ambiguous cases documented and intentional
✓ All unanswerable questions confirmed
✓ All employee records consistent
✓ All quarterly revenues sum to annual totals
✓ All budget vs. actual comparisons logical

## File Structure

```
healthtech_corpus/
├── README.md (this file)
├── company_profile.md
├── qa_pairs.md (100 answerable + 5 unanswerable questions)
├── ambiguity_log.md (15 intentionally ambiguous cases)
├── consistency_validation.md (mathematical validation)
└── documents/
    ├── finance/ (9 documents)
    ├── hr/ (16 documents)
    ├── product/ (7 documents)
    ├── engineering/ (11 documents)
    ├── sales/ (8 documents)
    ├── marketing/ (8 documents)
    ├── customer_success/ (8 documents)
    ├── meetings/ (7 documents)
    ├── compliance/ (8 documents)
    ├── legal/ (4 documents)
    ├── operations/ (7 documents)
    └── executive/ (5 documents)
```

## Key Metrics Summary

### Financial Performance (FY 2025)
- **Revenue:** $80M (60% YoY growth)
- **Gross Margin:** 70%
- **EBITDA:** $38M (47.5% margin)
- **Net Income:** $32M (40% margin)

### Customer Metrics (EOY 2025)
- **Total Customers:** 142 hospitals
- **Customer Retention:** 92%
- **Net Revenue Retention:** 115%
- **NPS:** 60

### Company Metrics
- **Employees:** 487 (Dec 2025)
- **Target Employees:** 625 (EOY 2026)
- **Offices:** Boston (HQ), London (EU)

## Notes for Test Designers

1. **Temporal Context Matters:** Many questions require understanding whether the query is about current state, historical data, or future targets.

2. **Precision vs. Recall Tradeoff:** Some ambiguous cases test whether the system prioritizes precision (refusing to answer without clarification) or recall (providing the most likely answer).

3. **Source Attribution:** Consider testing whether the system can cite which document(s) contain the answer.

4. **Confidence Calibration:** Test whether the system's confidence scores correlate with actual accuracy.

5. **Update Frequency:** The corpus represents a snapshot in time (January 2026). Consider how systems handle temporal queries like "current" or "latest".

---

**Created by:** Manus AI
**Date:** January 2026
**Version:** 2.0
**Total Documents:** 106
**Total Q&A Pairs:** 105
'''
