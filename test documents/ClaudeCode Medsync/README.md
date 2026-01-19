# MedSync Health - Enterprise Document Corpus

**Version:** 1.0  
**Date:** January 2026  
**Purpose:** AI System Stress Testing & Knowledge Retrieval Validation

---

## Overview

This corpus contains **100 realistic enterprise documents** for MedSync Health, a fictional Series D healthcare technology company, along with **200 Q&A pairs** designed to stress test knowledge retrieval systems at scale.

### What's Included

- **100 Documents** across 8 categories (Financial, HR, Product, Sales, Security, Legal, Strategy, Operations)
- **200 Q&A Pairs** with diverse types (Simple, Metric, Temporal, Comparison, Policy, Multi-hop)
- **20 Ambiguous Cases** to test disambiguation capabilities
- **15 Unanswerable Questions** to test knowledge boundary recognition
- **Full Data Consistency** across all documents
- **Extensive Cross-References** between documents

---

## Quick Start

### 1. Extract the Archive

```bash
tar -xzf medsync_corpus_complete.tar.gz
cd medsync_corpus/
```

### 2. Explore the Documents

```bash
# View document index
cat document_index.md

# Browse documents
ls documents/

# View a sample document
cat documents/0_b5isQ522snCaPWDiR1DiFL_*_FIN-001_*.md
```

### 3. Review Q&A Test Set

```bash
# View all 200 questions
cat qa_test_set.md

# Search for specific question types
grep "Type: MULTI-HOP" qa_test_set.md
```

### 4. Check Ambiguity Cases

```bash
# View intentionally ambiguous cases
cat ambiguity_cases.md
```

### 5. Validate Consistency

```bash
# Run validation script
python3 validate_consistency.py
```

---

## File Structure

```
medsync_corpus/
├── documents/                    # 100 enterprise documents
│   ├── FIN-*.md                 # Financial documents (15)
│   ├── HR-*.md                  # HR & People documents (15)
│   ├── PROD-*.md                # Product documents (15)
│   ├── SALES-*.md               # Sales documents (12)
│   ├── SEC-*.md                 # Security documents (12)
│   ├── LEGAL-*.md               # Legal documents (8)
│   ├── STRAT-*.md               # Strategy documents (12)
│   └── OPS-*.md                 # Operations documents (11)
├── master_data_model.md         # Core company data reference
├── data_consistency.md          # Consistency validation checklist
├── qa_test_set.md               # 200 Q&A pairs for testing
├── ambiguity_cases.md           # 20 intentional ambiguities
├── document_index.md            # Complete document catalog
├── validation_report.md         # Validation results
├── validate_consistency.py      # Automated validation script
└── README.md                    # This file
```

---

## Company Profile: MedSync Health

**Industry:** Healthcare Technology / Digital Health Platform  
**Stage:** Series D (preparing for IPO)  
**Founded:** January 2019  
**Headquarters:** Boston, MA, USA  
**Employees:** 1,200 across 4 offices (Boston, London, Berlin, Singapore)  
**Revenue (FY 2024):** AED 485,100,000  
**Total Funding:** AED 992,250,000

### Products (4 Total)

1. **MedSync Connect** - Hospital-clinic integration platform
2. **MedSync Analytics** - Healthcare data analytics and reporting
3. **MedSync Patient Portal** - Patient engagement platform
4. **MedSync Compliance Suite** - Regulatory compliance management

### Customers

- **520** Hospitals
- **3,200** Clinics
- **210** Insurance Providers
- **3,930** Total Organizations

---

## Document Categories

### Financial Documents (15)
Annual reports, quarterly reports, investor presentations, cap table, funding history, budget plans

**Key Metrics:**
- FY 2024 Revenue: AED 485,100,000
- Gross Margin: 75%
- Operating Margin: -4.1%
- Net Margin: -4.6%

### HR & People Documents (15)
Employee handbook, policies (PTO, parental leave, travel, expense), compensation, performance reviews, DEI report, org chart

**Key Metrics:**
- Total Employees: 1,200
- Voluntary Attrition: 12.5%
- Average Tenure: 2.3 years

### Product Documents (15)
Product specs, roadmaps, integration guides, API docs, release notes, competitive analysis, pricing

**Key Metrics:**
- 4 Product Lines
- NPS Scores: 68-75
- ARR by Product

### Sales & Customer Documents (12)
Customer metrics, NPS analysis, churn analysis, case studies, sales playbook, partner agreements

**Key Metrics:**
- Logo Retention: 87%
- Customer Retention: 91%
- GRR: 94%
- NRR: 118%

### Security & Compliance Documents (12)
SOC 2, HIPAA, ISO 27001, GDPR, security policies, incident reports, disaster recovery

**Key Certifications:**
- SOC 2 Type II (August 2024)
- HIPAA (March 2020)
- ISO 27001 (November 2022)
- GDPR (May 2020)

### Legal Documents (8)
Terms of service, privacy policy, MSA template, SLA definitions, IP policy, NDA template, board resolutions, bylaws

### Strategy & Planning Documents (12)
Company and department OKRs, strategic plans, market analysis, M&A targets, expansion plans

### Operations Documents (11)
Vendor contracts, office leases, IT infrastructure, software licenses, procurement policy, sustainability report

---

## Q&A Test Set

### Question Distribution

| Type | Count | Description |
|------|-------|-------------|
| SIMPLE | 40 | Direct lookup questions |
| METRIC | 50 | Numeric value questions |
| TEMPORAL | 30 | Time-based questions |
| COMPARISON | 25 | Comparison questions |
| POLICY | 35 | Policy detail questions |
| MULTI-HOP | 20 | Multi-document reasoning |
| **TOTAL** | **200** | |

### Difficulty Distribution

| Difficulty | Count | Percentage |
|------------|-------|------------|
| EASY | 80 | 40% |
| MEDIUM | 80 | 40% |
| HARD | 40 | 20% |

### Special Cases

- **Unanswerable Questions:** 15 (test "I don't know" capability)
- **Calculation Required:** 20 (test mathematical reasoning)
- **Ambiguous Questions:** 20 (test disambiguation)

---

## Testing Use Cases

### 1. Basic Retrieval Testing

Test simple fact lookup and metric retrieval:

```
Q: Who is the CEO of MedSync Health?
A: Dr. Sarah Chen
Source: HR-015, FIN-001
```

### 2. Multi-Document Reasoning

Test cross-document information synthesis:

```
Q: What is the revenue per employee for FY 2024?
A: AED 404,250 (485,100,000 / 1,200)
Source: FIN-001, HR-015
```

### 3. Disambiguation Testing

Test handling of ambiguous questions:

```
Q: What is the retention rate?
Expected: System should ask which retention metric:
- Logo Retention: 87%
- Customer Retention: 91%
- GRR: 94%
- NRR: 118%
```

### 4. Knowledge Boundary Testing

Test recognition of unanswerable questions:

```
Q: What is the company's target IPO date?
A: [NOT IN DOCUMENTS]
Expected: System should respond "I don't know" or similar
```

### 5. Consistency Validation

Test cross-document data consistency:

```python
# Run automated validation
python3 validate_consistency.py
```

---

## Data Consistency Guarantees

✅ **Revenue Consistency**
- Quarterly revenues sum to annual total
- Product revenues sum to total revenue
- Geographic revenues sum to total revenue

✅ **Headcount Consistency**
- Department headcounts sum to 1,200
- Office headcounts sum to 1,200
- Consistent across all time periods

✅ **Customer Metrics Consistency**
- Customer counts match across documents
- Retention metrics are consistent
- NPS scores align across products

✅ **Financial Metrics Consistency**
- All calculations are correct
- Margins and ratios are accurate
- Funding rounds sum correctly

---

## Ambiguity Cases

The corpus includes **20 intentionally ambiguous cases** to test disambiguation:

### Example 1: Multiple Retention Metrics
**Question:** "What is the retention rate?"  
**Ambiguity:** Four different retention metrics exist (Logo, Customer, GRR, NRR)  
**Expected:** System should ask for clarification

### Example 2: Level-Based Policy
**Question:** "What is the referral bonus?"  
**Ambiguity:** Bonus varies by level (IC: AED 7,350, Manager: AED 12,862.50, Director+: AED 18,375)  
**Expected:** System should ask for employee level

See `ambiguity_cases.md` for all 20 cases.

---

## Validation Results

✅ **Document Count:** 100/100 documents present  
✅ **Content Quality:** All documents substantive and realistic  
✅ **Data Consistency:** Zero consistency errors found  
✅ **Cross-References:** All document IDs valid  
✅ **Q&A Coverage:** 200 questions covering all difficulty levels  
✅ **Ambiguity Cases:** 20 cases implemented correctly  

**Status:** Production-ready for AI system testing

---

## Usage Recommendations

### For RAG System Testing

1. **Index all 100 documents** in your vector database
2. **Start with EASY questions** to validate basic retrieval
3. **Progress to HARD questions** to test advanced reasoning
4. **Test ambiguous cases** to validate disambiguation
5. **Measure accuracy by question type and difficulty**

### For LLM Evaluation

1. **Provide documents as context** (test context window limits)
2. **Ask questions from the Q&A set**
3. **Compare answers to ground truth**
4. **Track accuracy, hallucination rate, and confidence**

### For Coherence Checking

1. **Use ambiguous cases** to test disambiguation
2. **Test unanswerable questions** for knowledge boundaries
3. **Validate cross-document consistency checking**
4. **Measure clarification question quality**

---

## Metrics to Track

### Accuracy Metrics
- Overall accuracy (correct answers / total questions)
- Accuracy by question type (SIMPLE, METRIC, etc.)
- Accuracy by difficulty (EASY, MEDIUM, HARD)

### Retrieval Metrics
- Retrieval precision (relevant docs / retrieved docs)
- Retrieval recall (relevant docs retrieved / total relevant)
- Average retrieval time

### Reasoning Metrics
- Multi-hop question accuracy
- Calculation accuracy
- Temporal reasoning accuracy

### Disambiguation Metrics
- Ambiguity detection rate
- Clarification question quality
- Context-aware response accuracy

### Knowledge Boundary Metrics
- "I don't know" precision (correct refusals / total refusals)
- "I don't know" recall (correct refusals / unanswerable questions)

---

## Technical Specifications

**Format:** Markdown (.md)  
**Encoding:** UTF-8  
**Total Size:** ~1 MB uncompressed  
**Archive Size:** ~216 KB compressed  
**Average Document Length:** ~800-2000 words  
**Total Word Count:** ~100,000+ words

**Currency:** AED (United Arab Emirates Dirham)  
**Date Format:** Month Year (e.g., "March 2020")  
**Number Format:** Comma-separated (e.g., "1,200")

---

## Limitations & Disclaimers

⚠️ **Fictional Company:** MedSync Health is entirely fictional. All data is synthetic.

⚠️ **Educational Use Only:** Not for actual business or legal purposes.

⚠️ **Simplified Content:** Real enterprise documents would be more complex.

⚠️ **Time Period:** Documents are dated for 2024-2025 timeframe.

⚠️ **Currency Note:** Uses AED for financial reporting (per user preference).

---

## Support & Contact

**Documentation:** See `validation_report.md` for detailed validation results  
**Issues:** Check `data_consistency.md` for consistency requirements  
**Questions:** Refer to `document_index.md` for document catalog

---

## License & Attribution

This corpus was generated for AI system testing purposes. The company, people, and data are entirely fictional. Feel free to use this corpus for:

- AI system testing and evaluation
- RAG system development
- LLM benchmarking
- Knowledge retrieval research
- Educational purposes

---

## Version History

**v1.0 (January 2026)**
- Initial release
- 100 documents across 8 categories
- 200 Q&A pairs with proper distribution
- 20 ambiguous cases
- Full data consistency validation
- Production-ready for testing

---

## Quick Reference

**Total Documents:** 100  
**Total Q&A Pairs:** 200 (+ 15 unanswerable)  
**Ambiguous Cases:** 20  
**Data Consistency Errors:** 0  
**Validation Status:** ✅ PASSED  

**Ready for:** RAG testing, LLM evaluation, knowledge retrieval benchmarking, coherence checking validation

---

**Generated:** January 2026  
**Status:** Production-Ready  
**Quality:** Validated & Approved ✅
