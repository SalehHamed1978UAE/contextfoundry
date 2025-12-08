# Phase 5: Add Domain-Specific Few-Shot Examples

**Why:** Research shows domain-matched examples add +4.71% recall over generic examples.

**Scope:** Create example files for 6 domains. Only implement AFTER Phase 4 passes.

---

## Overview

Create these files in `brain/examples/`:

| File | Domain | Entity Focus |
|------|--------|--------------|
| finance_examples.json | Finance/Investment | FINANCIAL_INSTRUMENT, NPV, EBITDA |
| healthcare_examples.json | Healthcare | MEDICAL_CONDITION, TREATMENT, MEDICATION |
| maritime_examples.json | Maritime/Ports | VESSEL, PORT, CARGO, VOYAGE |
| energy_examples.json | Energy/Oil & Gas | FACILITY, RESOURCE, CAPACITY |
| construction_examples.json | Construction | BUILDING, PERMIT, MATERIAL |
| legal_examples.json | Legal/Regulatory | STATUTE, CASE, COURT |

---

## File 1: brain/examples/finance_examples.json

```json
{
  "domain": "finance",
  "description": "Financial services and investment document examples",
  "examples": [
    {
      "input": "Goldman Sachs underwrote the $500M bond issuance for ADQ. The NPV analysis showed positive returns with an IRR of 18%.",
      "output": [
        {"name": "Goldman Sachs", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Named financial institution"},
        {"name": "$500M bond issuance", "type": "FINANCIAL_INSTRUMENT", "confidence": 0.95, "reasoning": "Specific financial product"},
        {"name": "ADQ", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Named organization"},
        {"name": "NPV", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Financial methodology"},
        {"name": "IRR", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Financial metric"}
      ]
    },
    {
      "input": "The sovereign wealth fund's EBITDA improved by 15%. Monte Carlo Simulation was used to stress-test projections.",
      "output": [
        {"name": "sovereign wealth fund", "type": "ORGANIZATION", "confidence": 0.90, "reasoning": "Type of financial institution"},
        {"name": "EBITDA", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Financial metric"},
        {"name": "Monte Carlo Simulation", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Named analytical methodology"}
      ]
    },
    {
      "input": "The Risk Committee approved the Value at Risk model. Compliance Officer reviewed GDPR requirements.",
      "output": [
        {"name": "Risk Committee", "type": "ORGANIZATION", "confidence": 0.90, "reasoning": "Body that ACTS (approved)"},
        {"name": "Value at Risk", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Named risk methodology"},
        {"name": "Compliance Officer", "type": "ROLE", "confidence": 0.95, "reasoning": "Job title"},
        {"name": "GDPR", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Named regulation"}
      ]
    },
    {
      "input": "Subsidiary A reported to Corporate Treasury. The intercompany loan was structured as a convertible note.",
      "output": [
        {"name": "Subsidiary A", "type": "ORGANIZATION", "confidence": 0.95, "reasoning": "Named entity"},
        {"name": "Corporate Treasury", "type": "ORGANIZATION", "confidence": 0.90, "reasoning": "Organizational unit"},
        {"name": "intercompany loan", "type": "FINANCIAL_INSTRUMENT", "confidence": 0.90, "reasoning": "Financial instrument"},
        {"name": "convertible note", "type": "FINANCIAL_INSTRUMENT", "confidence": 0.90, "reasoning": "Specific instrument"}
      ]
    },
    {
      "input": "The Four Pillars of AI Valuation framework guides investment decisions. Pillar 1 covers Foundational Inputs.",
      "output": [
        {"name": "Four Pillars of AI Valuation", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Named framework"},
        {"name": "Pillar 1", "type": "CONCEPT", "confidence": 0.85, "reasoning": "Framework component"},
        {"name": "Foundational Inputs", "type": "CONCEPT", "confidence": 0.90, "reasoning": "Named category"}
      ]
    }
  ]
}
```

---

## File 2: brain/examples/healthcare_examples.json

```json
{
  "domain": "healthcare",
  "description": "Healthcare and medical document examples",
  "examples": [
    {
      "input": "Dr. Ahmed Al-Rashid diagnosed Type 2 Diabetes and prescribed Metformin 500mg. The patient was referred to Cleveland Clinic Abu Dhabi.",
      "output": [
        {"name": "Dr. Ahmed Al-Rashid", "type": "PERSON", "confidence": 1.0, "reasoning": "Named physician"},
        {"name": "Type 2 Diabetes", "type": "MEDICAL_CONDITION", "confidence": 0.95, "reasoning": "Medical diagnosis"},
        {"name": "Metformin 500mg", "type": "MEDICATION", "confidence": 0.95, "reasoning": "Medication with dosage"},
        {"name": "Cleveland Clinic Abu Dhabi", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Healthcare facility"}
      ]
    },
    {
      "input": "The Clinical Protocol for Cardiac Rehabilitation was updated by the Department of Cardiology. Phase 2 begins at week 4.",
      "output": [
        {"name": "Clinical Protocol for Cardiac Rehabilitation", "type": "DOCUMENT", "confidence": 0.95, "reasoning": "Named clinical document"},
        {"name": "Department of Cardiology", "type": "ORGANIZATION", "confidence": 0.95, "reasoning": "Organizational unit"},
        {"name": "Phase 2", "type": "PROCESS", "confidence": 0.90, "reasoning": "Treatment phase"},
        {"name": "Cardiac Rehabilitation", "type": "TREATMENT", "confidence": 0.90, "reasoning": "Treatment type"}
      ]
    },
    {
      "input": "The Electronic Health Record integrates with Laboratory Information System. HIPAA compliance is verified by Privacy Officer.",
      "output": [
        {"name": "Electronic Health Record", "type": "SYSTEM", "confidence": 0.95, "reasoning": "Healthcare system"},
        {"name": "Laboratory Information System", "type": "SYSTEM", "confidence": 0.95, "reasoning": "Healthcare system"},
        {"name": "HIPAA", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Named regulation"},
        {"name": "Privacy Officer", "type": "ROLE", "confidence": 0.90, "reasoning": "Job role"}
      ]
    },
    {
      "input": "MRI scan revealed herniated disc at L4-L5. Orthopedic Surgeon recommended physical therapy.",
      "output": [
        {"name": "MRI scan", "type": "PROCEDURE", "confidence": 0.90, "reasoning": "Medical procedure"},
        {"name": "herniated disc at L4-L5", "type": "MEDICAL_CONDITION", "confidence": 0.95, "reasoning": "Diagnosis with location"},
        {"name": "Orthopedic Surgeon", "type": "ROLE", "confidence": 0.90, "reasoning": "Medical role"},
        {"name": "physical therapy", "type": "TREATMENT", "confidence": 0.90, "reasoning": "Treatment type"}
      ]
    },
    {
      "input": "Abu Dhabi Health Services Company (SEHA) operates 12 hospitals. Chief Medical Officer reports to Ministry of Health.",
      "output": [
        {"name": "Abu Dhabi Health Services Company", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Healthcare org"},
        {"name": "SEHA", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Acronym"},
        {"name": "Chief Medical Officer", "type": "ROLE", "confidence": 0.95, "reasoning": "Executive role"},
        {"name": "Ministry of Health", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Government agency"}
      ]
    }
  ]
}
```

---

## File 3: brain/examples/maritime_examples.json

```json
{
  "domain": "maritime",
  "description": "Maritime, shipping, and port operations examples",
  "examples": [
    {
      "input": "MV Ever Given arrived at Khalifa Port with 20,000 TEU containers. Port Authority cleared vessel for berth 7.",
      "output": [
        {"name": "MV Ever Given", "type": "VESSEL", "confidence": 1.0, "reasoning": "Named ship"},
        {"name": "Khalifa Port", "type": "PORT", "confidence": 1.0, "reasoning": "Named port"},
        {"name": "20,000 TEU containers", "type": "CARGO", "confidence": 0.90, "reasoning": "Cargo specification"},
        {"name": "Port Authority", "type": "ORGANIZATION", "confidence": 0.90, "reasoning": "Org that ACTS (cleared)"},
        {"name": "berth 7", "type": "LOCATION", "confidence": 0.85, "reasoning": "Specific location"}
      ]
    },
    {
      "input": "Abu Dhabi Ports operates Zayed Port and Musaffah Port. Terminal Operating System tracks container movements.",
      "output": [
        {"name": "Abu Dhabi Ports", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Port operator"},
        {"name": "Zayed Port", "type": "PORT", "confidence": 1.0, "reasoning": "Named port"},
        {"name": "Musaffah Port", "type": "PORT", "confidence": 1.0, "reasoning": "Named port"},
        {"name": "Terminal Operating System", "type": "SYSTEM", "confidence": 0.90, "reasoning": "Operational system"}
      ]
    },
    {
      "input": "Voyage from Singapore to Jebel Ali takes 7 days. Ship Captain must submit cargo manifest 48 hours before arrival.",
      "output": [
        {"name": "Singapore", "type": "LOCATION", "confidence": 1.0, "reasoning": "City/country"},
        {"name": "Jebel Ali", "type": "PORT", "confidence": 0.95, "reasoning": "Named port"},
        {"name": "Ship Captain", "type": "ROLE", "confidence": 0.90, "reasoning": "Maritime role"},
        {"name": "cargo manifest", "type": "DOCUMENT", "confidence": 0.90, "reasoning": "Shipping document"}
      ]
    },
    {
      "input": "Tanker Safety Framework requires double-hull construction. ADNOC Logistics manages fleet of 15 VLCCs.",
      "output": [
        {"name": "Tanker Safety Framework", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Safety standard"},
        {"name": "double-hull construction", "type": "CONCEPT", "confidence": 0.85, "reasoning": "Technical spec"},
        {"name": "ADNOC Logistics", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Named company"},
        {"name": "15 VLCCs", "type": "VESSEL", "confidence": 0.90, "reasoning": "Fleet of vessels"}
      ]
    },
    {
      "input": "Draft restriction of 16 meters limits vessel size. Harbour Master coordinates all vessel traffic.",
      "output": [
        {"name": "Draft restriction of 16 meters", "type": "CONCEPT", "confidence": 0.85, "reasoning": "Technical spec"},
        {"name": "Harbour Master", "type": "ROLE", "confidence": 0.95, "reasoning": "Maritime role"}
      ]
    }
  ]
}
```

---

## File 4: brain/examples/energy_examples.json

```json
{
  "domain": "energy",
  "description": "Energy, oil & gas, and utilities examples",
  "examples": [
    {
      "input": "ADNOC operates Ruwais Refinery with 900,000 bpd capacity. Gas Processing Plant feeds into Habshan-Fujairah Pipeline.",
      "output": [
        {"name": "ADNOC", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Energy company"},
        {"name": "Ruwais Refinery", "type": "FACILITY", "confidence": 1.0, "reasoning": "Processing facility"},
        {"name": "900,000 bpd capacity", "type": "CONCEPT", "confidence": 0.85, "reasoning": "Capacity spec"},
        {"name": "Gas Processing Plant", "type": "FACILITY", "confidence": 0.90, "reasoning": "Facility type"},
        {"name": "Habshan-Fujairah Pipeline", "type": "FACILITY", "confidence": 1.0, "reasoning": "Named infrastructure"}
      ]
    },
    {
      "input": "Barakah Nuclear Power Plant achieved first criticality in Unit 1. Emirates Nuclear Energy Corporation manages all four units.",
      "output": [
        {"name": "Barakah Nuclear Power Plant", "type": "FACILITY", "confidence": 1.0, "reasoning": "Named plant"},
        {"name": "first criticality", "type": "EVENT", "confidence": 0.90, "reasoning": "Nuclear milestone"},
        {"name": "Unit 1", "type": "FACILITY", "confidence": 0.85, "reasoning": "Reactor unit"},
        {"name": "Emirates Nuclear Energy Corporation", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Named org"}
      ]
    },
    {
      "input": "Proven reserves of 98 billion barrels support 2030 targets. Petroleum Institute provides training for field engineers.",
      "output": [
        {"name": "Proven reserves of 98 billion barrels", "type": "RESOURCE", "confidence": 0.90, "reasoning": "Quantified resource"},
        {"name": "2030 targets", "type": "CONCEPT", "confidence": 0.85, "reasoning": "Strategic target"},
        {"name": "Petroleum Institute", "type": "ORGANIZATION", "confidence": 0.95, "reasoning": "Named institution"},
        {"name": "field engineers", "type": "ROLE", "confidence": 0.85, "reasoning": "Job role"}
      ]
    },
    {
      "input": "Solar PV Installation at Noor Abu Dhabi generates 1.2 GW. Masdar coordinates renewable energy projects.",
      "output": [
        {"name": "Solar PV Installation", "type": "FACILITY", "confidence": 0.90, "reasoning": "Facility type"},
        {"name": "Noor Abu Dhabi", "type": "FACILITY", "confidence": 1.0, "reasoning": "Named project"},
        {"name": "1.2 GW", "type": "CONCEPT", "confidence": 0.80, "reasoning": "Capacity"},
        {"name": "Masdar", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Named company"}
      ]
    },
    {
      "input": "Upstream Division reported 3.5 million bpd. HSE Manager ensures Environmental Impact Assessment compliance.",
      "output": [
        {"name": "Upstream Division", "type": "ORGANIZATION", "confidence": 0.90, "reasoning": "Org unit"},
        {"name": "3.5 million bpd", "type": "CONCEPT", "confidence": 0.85, "reasoning": "Production metric"},
        {"name": "HSE Manager", "type": "ROLE", "confidence": 0.95, "reasoning": "Job role"},
        {"name": "Environmental Impact Assessment", "type": "CONCEPT", "confidence": 0.90, "reasoning": "Regulatory framework"}
      ]
    }
  ]
}
```

---

## File 5: brain/examples/construction_examples.json

```json
{
  "domain": "construction",
  "description": "Construction and infrastructure examples",
  "examples": [
    {
      "input": "Al Futtaim Construction completed foundation work for Tower 3. Building Permit was issued by Abu Dhabi Municipality.",
      "output": [
        {"name": "Al Futtaim Construction", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Contractor"},
        {"name": "foundation work", "type": "PROCESS", "confidence": 0.85, "reasoning": "Construction activity"},
        {"name": "Tower 3", "type": "BUILDING", "confidence": 0.90, "reasoning": "Named structure"},
        {"name": "Building Permit", "type": "PERMIT", "confidence": 0.95, "reasoning": "Regulatory document"},
        {"name": "Abu Dhabi Municipality", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Govt agency that ACTS"}
      ]
    },
    {
      "input": "Project Manager oversees 500 workers on Saadiyat Island development. Phase 2 handover scheduled for Q4 2025.",
      "output": [
        {"name": "Project Manager", "type": "ROLE", "confidence": 0.95, "reasoning": "Job role"},
        {"name": "Saadiyat Island development", "type": "PROJECT", "confidence": 0.95, "reasoning": "Named project"},
        {"name": "Phase 2 handover", "type": "PROCESS", "confidence": 0.90, "reasoning": "Project milestone"},
        {"name": "Q4 2025", "type": "DATE", "confidence": 0.95, "reasoning": "Time reference"}
      ]
    },
    {
      "input": "Reinforced concrete requires 40 MPa strength. Structural Engineer certified design per Abu Dhabi Building Code.",
      "output": [
        {"name": "Reinforced concrete", "type": "MATERIAL", "confidence": 0.85, "reasoning": "Construction material"},
        {"name": "40 MPa strength", "type": "CONCEPT", "confidence": 0.80, "reasoning": "Technical requirement"},
        {"name": "Structural Engineer", "type": "ROLE", "confidence": 0.95, "reasoning": "Professional role"},
        {"name": "Abu Dhabi Building Code", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Regulatory standard"}
      ]
    },
    {
      "input": "Aldar Properties awarded MEP contract to Drake & Scull. Fit-out phase begins after core and shell completion.",
      "output": [
        {"name": "Aldar Properties", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Developer"},
        {"name": "MEP contract", "type": "DOCUMENT", "confidence": 0.85, "reasoning": "Contract type"},
        {"name": "Drake & Scull", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Contractor"},
        {"name": "fit-out phase", "type": "PROCESS", "confidence": 0.90, "reasoning": "Construction phase"},
        {"name": "core and shell completion", "type": "PROCESS", "confidence": 0.85, "reasoning": "Milestone"}
      ]
    },
    {
      "input": "Master Plan for Yas Island includes 25 residential towers. AECOM provided design per Estidama Pearl Rating.",
      "output": [
        {"name": "Master Plan for Yas Island", "type": "DOCUMENT", "confidence": 0.95, "reasoning": "Planning document"},
        {"name": "Yas Island", "type": "LOCATION", "confidence": 1.0, "reasoning": "Geographic location"},
        {"name": "25 residential towers", "type": "BUILDING", "confidence": 0.85, "reasoning": "Building type"},
        {"name": "AECOM", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Consultancy"},
        {"name": "Estidama Pearl Rating", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Sustainability standard"}
      ]
    }
  ]
}
```

---

## File 6: brain/examples/legal_examples.json

```json
{
  "domain": "legal",
  "description": "Legal and regulatory examples",
  "examples": [
    {
      "input": "Abu Dhabi Global Market Courts heard Case No. 2024-0156. Justice Sir Andrew Smith ruled in favor of Global Investments LLC.",
      "output": [
        {"name": "Abu Dhabi Global Market Courts", "type": "COURT", "confidence": 1.0, "reasoning": "Judicial body"},
        {"name": "Case No. 2024-0156", "type": "CASE", "confidence": 0.95, "reasoning": "Case identifier"},
        {"name": "Justice Sir Andrew Smith", "type": "PERSON", "confidence": 1.0, "reasoning": "Named judge"},
        {"name": "Global Investments LLC", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Named company"}
      ]
    },
    {
      "input": "Federal Law No. 2 of 2015 governs commercial companies. Ministry of Economy enforces compliance with Article 23.",
      "output": [
        {"name": "Federal Law No. 2 of 2015", "type": "STATUTE", "confidence": 1.0, "reasoning": "Named legislation"},
        {"name": "Ministry of Economy", "type": "ORGANIZATION", "confidence": 1.0, "reasoning": "Government ministry"},
        {"name": "Article 23", "type": "STATUTE", "confidence": 0.90, "reasoning": "Legal provision"}
      ]
    },
    {
      "input": "Settlement Agreement was executed December 15, 2024. Legal Counsel confirmed jurisdiction under DIFC Courts.",
      "output": [
        {"name": "Settlement Agreement", "type": "DOCUMENT", "confidence": 0.95, "reasoning": "Legal document"},
        {"name": "December 15, 2024", "type": "DATE", "confidence": 1.0, "reasoning": "Specific date"},
        {"name": "Legal Counsel", "type": "ROLE", "confidence": 0.90, "reasoning": "Professional role"},
        {"name": "DIFC Courts", "type": "COURT", "confidence": 1.0, "reasoning": "Named court system"}
      ]
    },
    {
      "input": "Arbitration Clause specifies ICC Rules with seat in Paris. Three arbitrators appointed under Arbitration Framework.",
      "output": [
        {"name": "Arbitration Clause", "type": "CONCEPT", "confidence": 0.90, "reasoning": "Legal provision type"},
        {"name": "ICC Rules", "type": "CONCEPT", "confidence": 0.95, "reasoning": "Named arbitration rules"},
        {"name": "Paris", "type": "LOCATION", "confidence": 1.0, "reasoning": "City - arbitration seat"},
        {"name": "arbitrators", "type": "ROLE", "confidence": 0.85, "reasoning": "Legal role"},
        {"name": "Arbitration Framework", "type": "CONCEPT", "confidence": 0.90, "reasoning": "Legal framework"}
      ]
    },
    {
      "input": "Data Protection Law requires consent for processing. Privacy Commissioner has authority under Regulatory Authority Law.",
      "output": [
        {"name": "Data Protection Law", "type": "STATUTE", "confidence": 0.95, "reasoning": "Named legislation"},
        {"name": "consent", "type": "CONCEPT", "confidence": 0.80, "reasoning": "Legal concept"},
        {"name": "Privacy Commissioner", "type": "ROLE", "confidence": 0.90, "reasoning": "Regulatory role"},
        {"name": "Regulatory Authority Law", "type": "STATUTE", "confidence": 0.90, "reasoning": "Named legislation"}
      ]
    }
  ]
}
```

---

## Test After Adding

Run extraction on documents from different domains:
1. A finance document → should use finance_examples.json
2. A healthcare document → should use healthcare_examples.json
3. A generic document → should fall back to core_examples.json

Verify domain classification is working and correct examples are loaded.

---

**After all domain examples work, proceed to Phase 6.**
