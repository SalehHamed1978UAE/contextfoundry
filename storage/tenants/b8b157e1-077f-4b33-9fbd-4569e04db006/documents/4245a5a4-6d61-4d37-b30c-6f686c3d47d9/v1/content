# Aerospace Division Engineering Design Review

**Document Type:** Engineering Review Minutes
**Authority Level:** 2 (Primary)
**Meeting Date:** January 7, 2026
**Location:** Tucson Engineering Center
**Classification:** Internal - ITAR Restricted

---

## Attendees

### Review Board

| Name | Role | Status |
|------|------|--------|
| Dr. Elena Rodriguez | Chief Engineer (Chair) | Present |
| Thomas Mueller | Falcon X Program Director | Present |
| James Park | Manufacturing Engineering | Present |
| Sarah Mitchell | Avionics Lead | Present |
| Dr. Michael Foster | Aerodynamics Lead | Present |
| Robert Lee | Flight Test | Present |
| Jennifer Walsh | Quality Assurance | Present |

### Presenters
- Dr. Kevin Chen, Propulsion Engineer
- Maria Santos, Structures Engineer
- David Kim, Systems Integration Lead

---

## Review Agenda

1. Falcon X Propulsion System CDR Status
2. Starliner Satellite Bus Thermal Design
3. Hypersonic Scramjet Test Results
4. Engineering Action Item Review

---

## Item 1: Falcon X Propulsion System CDR

**Presenter:** Dr. Kevin Chen

### Design Summary

| Parameter | Requirement | Design Value | Margin |
|-----------|-------------|--------------|--------|
| Maximum Thrust | 4,500 lbf | 4,820 lbf | +7.1% |
| Specific Fuel Consumption | <0.65 lb/hp-hr | 0.58 lb/hp-hr | +10.8% |
| Weight | <485 lbs | 472 lbs | +2.7% |
| MTBO | 2,000 hrs | 2,200 hrs | +10% |
| Starting Altitude | 25,000 ft | 28,000 ft | +12% |

### Design Changes Since PDR

| Change | Reason | Impact |
|--------|--------|--------|
| Fuel pump upgrade | Reliability improvement | +$180K, -8 lbs |
| FADEC software rev | Performance optimization | No cost impact |
| Exhaust nozzle material | High-temp capability | +$45K, +2 lbs |
| Oil cooler relocation | Thermal management | No cost impact |

### Test Results Summary

| Test | Status | Results |
|------|--------|---------|
| Sea Level Static | Complete | All parameters met |
| Altitude Simulation | Complete | 105% of requirements |
| Endurance (500 hrs) | Complete | No anomalies |
| Environmental | In Progress | 75% complete |
| Vibration | Complete | Margins confirmed |

### Open Issues

| Issue | Severity | Resolution Plan | ECD |
|-------|----------|-----------------|-----|
| Fuel line chafing | Minor | Clamp redesign | Jan 20 |
| Oil temp margin | Low | Cooler upsizing | Jan 31 |
| Sensor redundancy | Medium | Add backup sensor | Feb 15 |

### Review Board Decision

**STATUS: APPROVED WITH CONDITIONS**

Conditions:
1. Complete environmental testing by February 1
2. Resolve fuel line chafing issue
3. Implement sensor redundancy before first flight

---

## Item 2: Starliner Satellite Bus Thermal Design

**Presenter:** Maria Santos

### Thermal Requirements

| Parameter | Requirement | Design Value |
|-----------|-------------|--------------|
| Operating Temp Range | -40°C to +85°C | -45°C to +90°C |
| Component Temp Control | ±5°C | ±3°C |
| Power Dissipation | 2.5 kW | 2.8 kW capable |
| Heat Rejection | 3.2 kW | 3.5 kW capable |
| Heater Power | <400W (eclipse) | 320W |

### Thermal Control System

| Component | Function | Mass |
|-----------|----------|------|
| Radiator Panels (4) | Heat rejection | 28 kg |
| MLI Blankets | Insulation | 12 kg |
| Heat Pipes (8) | Heat transport | 8 kg |
| Heaters (24) | Cold case survival | 3 kg |
| Louvers (6) | Variable rejection | 4 kg |
| **Total** | | **55 kg** |

### Analysis Results

| Case | Max Temp | Min Temp | Margin |
|------|----------|----------|--------|
| Hot Operational | 78°C | N/A | 7°C |
| Cold Operational | N/A | -32°C | 8°C |
| Hot Survival | 95°C | N/A | 10°C |
| Cold Survival | N/A | -48°C | 7°C |

### Concerns Raised

**Dr. Rodriguez:** Concerned about thermal margin on high-power transponder option.

**Response:** Analysis assumes 30% design margin. Detailed modeling of high-power option in progress. Results due January 25.

**James Park:** Manufacturing feasibility of heat pipe integration?

**Response:** Prototype heat pipe assembly tested. Brazing process validated. No issues anticipated.

### Review Board Decision

**STATUS: APPROVED**

Action Items:
1. Complete high-power transponder thermal analysis
2. Validate heat pipe assembly in qualification unit

---

## Item 3: Hypersonic Scramjet Test Results

**Presenter:** David Kim

### Test Campaign Summary

| Test Series | Tests | Status | Success Rate |
|-------------|-------|--------|--------------|
| Ground (Direct Connect) | 45 | Complete | 91% |
| Ground (Freejet) | 12 | Complete | 83% |
| Flight (Captive Carry) | 3 | Complete | 100% |
| Flight (Free Flight) | 0 | Planned Q2 | - |

### Key Performance Data

| Parameter | Target | Achieved | Assessment |
|-----------|--------|----------|------------|
| Mach Range | 4.0 - 6.5 | 4.2 - 6.8 | ✓ Exceeded |
| Thrust/Weight | 8:1 | 7.2:1 | ⚠ Below target |
| Combustion Efficiency | >85% | 82% | ⚠ Below target |
| Operating Envelope | Full | 90% | ⚠ Partial |
| Thermal Protection | 2,800°F | 2,650°F | ✓ Met |

### Technical Challenges

| Challenge | Root Cause | Corrective Action |
|-----------|------------|-------------------|
| Thrust shortfall | Inlet spillage at high Mach | Inlet geometry optimization |
| Combustion efficiency | Fuel mixing incomplete | Injector redesign |
| Thermal hotspots | Shock impingement | TPS material upgrade |
| Inlet unstart at Mach 6.5+ | Boundary layer separation | BL bleed system design |

### Path Forward

| Phase | Activity | Timeline | Investment |
|-------|----------|----------|------------|
| Phase 2A | Inlet redesign and test | Q1-Q2 2026 | $18M |
| Phase 2B | Injector optimization | Q2 2026 | $8M |
| Phase 3 | Free flight test | Q3-Q4 2026 | $45M |
| Phase 4 | Demonstrator vehicle | 2027-2028 | $120M |

### DoD Customer Feedback

DARPA program manager expressed continued support. Current performance issues are typical for this development stage. Funding for Phase 2 confirmed.

### Review Board Discussion

**Dr. Rodriguez:** Are we confident in the inlet redesign approach?

**David Kim:** CFD analysis shows 15% improvement potential. Subscale wind tunnel tests scheduled February.

**Thomas Mueller:** Impact on overall program schedule?

**David Kim:** 4-month delay to free flight. Within acceptable range per DARPA.

### Review Board Decision

**STATUS: PROCEED WITH MODIFICATIONS**

Actions:
1. Execute inlet redesign per proposed plan
2. Increase combustion modeling fidelity
3. Monthly progress reviews with DARPA
4. Budget reforecast for Phase 2

---

## Engineering Action Item Review

### Open Actions

| ID | Description | Owner | Due | Status |
|----|-------------|-------|-----|--------|
| EA-2025-142 | Falcon X landing gear fatigue analysis | M. Santos | Jan 15 | On Track |
| EA-2025-156 | Starliner EMC test plan | S. Mitchell | Jan 20 | On Track |
| EA-2025-163 | Hypersonic TPS material qualification | D. Kim | Feb 28 | At Risk |
| EA-2025-171 | Composite wing repair procedures | J. Park | Jan 31 | On Track |
| EA-2025-178 | Avionics software code review | S. Mitchell | Feb 15 | On Track |

### At Risk Item Discussion

**EA-2025-163:** TPS material supplier (Ultramet) experiencing production delays. Alternative supplier (Goodrich) being qualified as backup. Mitigation plan in place.

### Closed Actions

| ID | Description | Closed Date |
|----|-------------|-------------|
| EA-2025-128 | Falcon X fuel system redesign | Dec 15, 2025 |
| EA-2025-134 | GPS antenna relocation | Dec 20, 2025 |
| EA-2025-145 | Starliner structure FEA update | Jan 3, 2026 |

---

## New Action Items

| ID | Description | Owner | Due |
|----|-------------|-------|-----|
| EA-2026-001 | Complete Falcon X propulsion environmental test | Dr. K. Chen | Feb 1 |
| EA-2026-002 | Resolve fuel line chafing | Dr. K. Chen | Jan 20 |
| EA-2026-003 | High-power transponder thermal analysis | M. Santos | Jan 25 |
| EA-2026-004 | Hypersonic inlet CFD optimization | D. Kim | Feb 15 |
| EA-2026-005 | Scramjet injector trade study | D. Kim | Feb 28 |

---

## Resource and Budget

### Engineering Headcount

| Program | Current | Authorized | Gap |
|---------|---------|------------|-----|
| Falcon X | 85 | 90 | 5 |
| Starliner | 42 | 45 | 3 |
| Hypersonic | 38 | 40 | 2 |
| Other | 45 | 45 | 0 |
| **Total** | **210** | **220** | **10** |

### FY2026 Engineering Budget

| Program | Budget | YTD Spend | Forecast |
|---------|--------|-----------|----------|
| Falcon X | $52M | $4.2M | On Track |
| Starliner | $28M | $2.1M | On Track |
| Hypersonic | $65M | $5.8M | $4M Over |
| Other R&D | $35M | $2.5M | On Track |

---

## Next Review

**Date:** February 4, 2026
**Agenda:**
- Falcon X first flight readiness
- Starliner PDR preparation
- Hypersonic inlet test results

---

**Minutes Prepared By:** Dr. Elena Rodriguez, Chief Engineer
**Distribution:** Aerospace Engineering, Program Management
**Classification:** ITAR Restricted - US Persons Only
