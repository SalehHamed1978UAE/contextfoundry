# GreenHydrogen Production Process Specification

**Document Type:** Process Specification
**Authority Level:** 1 (Authoritative)
**Document Number:** TEC-ENR-001
**Version:** 2.1
**Effective Date:** January 1, 2026
**Owner:** Dr. Marcus Thompson, Technical Lead
**Classification:** Internal

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jun 2024 | M. Thompson | Initial release |
| 1.5 | Oct 2024 | M. Thompson | Equipment updates |
| 2.0 | Dec 2025 | M. Thompson | Pre-commissioning |
| 2.1 | Jan 2026 | M. Thompson | Final specifications |

---

## 1. Facility Overview

### 1.1 Site Information

| Parameter | Value |
|-----------|-------|
| Location | El Paso, Texas |
| Site Area | 85 acres |
| Building Area | 125,000 sq ft |
| Grid Connection | 138 kV substation |
| Water Source | Rio Grande (treated) |
| Product Delivery | Pipeline to Shell facility |

### 1.2 Production Capacity

| Parameter | Phase 1 | Full Capacity |
|-----------|---------|---------------|
| Hydrogen Output | 425 kg/hr | 850 kg/hr |
| Daily Production | 10,200 kg | 20,400 kg |
| Annual Production | 3.5M kg | 7.0M kg |
| Operating Hours | 8,400 hrs/yr | 8,400 hrs/yr |
| Availability Target | 92% | 95% |

### 1.3 Product Specifications

| Parameter | Specification | Test Method |
|-----------|---------------|-------------|
| Purity | ≥99.999% H₂ | GC analysis |
| Moisture | ≤5 ppm | Dew point |
| Oxygen | ≤1 ppm | Trace analysis |
| Nitrogen | ≤10 ppm | Trace analysis |
| CO₂ | ≤1 ppm | Trace analysis |
| Delivery Pressure | 30 bar | Gauge |
| Delivery Temperature | 25±10°C | Thermocouple |

---

## 2. Process Description

### 2.1 Process Flow Overview

```
Solar/Grid Power → Electrolyzer → H₂ Separation → Compression → Storage → Pipeline
       ↓              ↓                              ↓
  Transformer    Deionized Water              Heat Recovery
       ↓              ↑                              ↓
  Rectifier      Water Treatment              Cooling Tower
```

### 2.2 Major Process Steps

| Step | Description | Equipment |
|------|-------------|-----------|
| 1 | Power conditioning | Transformer, rectifier |
| 2 | Water treatment | RO, EDI, polishing |
| 3 | Electrolysis | PEM electrolyzer stacks |
| 4 | Gas separation | Phase separators |
| 5 | Purification | Catalytic deoxidizer, dryer |
| 6 | Compression | Multi-stage compressor |
| 7 | Storage | Pressure vessels |
| 8 | Delivery | Pipeline metering |

---

## 3. Electrolysis System

### 3.1 Electrolyzer Specifications

| Parameter | Specification |
|-----------|---------------|
| Manufacturer | Nel Hydrogen |
| Model | M5000 PEM |
| Units Installed | 5 |
| Capacity per Unit | 85 kg H₂/hr |
| Stack Configuration | 2 stacks per unit |
| Cell Count | 100 cells per stack |
| Operating Pressure | 30 bar |
| Operating Temperature | 50-80°C |
| Efficiency | 54 kWh/kg H₂ |
| Water Consumption | 9 L/kg H₂ |

### 3.2 Cell Stack Details

| Parameter | Specification |
|-----------|---------------|
| Membrane | Nafion® 117 |
| Anode Catalyst | IrO₂ (2.0 mg/cm²) |
| Cathode Catalyst | Pt/C (0.5 mg/cm²) |
| Active Area | 1,500 cm² |
| Current Density | 2.0 A/cm² |
| Cell Voltage | 1.8-2.0 V |
| Stack Voltage | 180-200 V |
| Stack Current | 3,000 A |

### 3.3 Performance Curves

| Load (%) | H₂ Rate (kg/hr) | Efficiency (kWh/kg) | Power (MW) |
|----------|-----------------|---------------------|------------|
| 20 | 17 | 58 | 0.99 |
| 40 | 34 | 56 | 1.90 |
| 60 | 51 | 55 | 2.81 |
| 80 | 68 | 54 | 3.67 |
| 100 | 85 | 54 | 4.59 |

---

## 4. Water Treatment System

### 4.1 Feed Water Requirements

| Parameter | Limit | Test Method |
|-----------|-------|-------------|
| Conductivity | ≤0.1 µS/cm | Inline sensor |
| TOC | ≤50 ppb | Online analyzer |
| Silica | ≤10 ppb | Colorimetric |
| Iron | ≤5 ppb | ICP-MS |
| Chloride | ≤5 ppb | IC |
| Dissolved O₂ | ≤10 ppb | DO sensor |

### 4.2 Treatment Train

| Stage | Equipment | Capacity | Purpose |
|-------|-----------|----------|---------|
| 1 | Multimedia filter | 300 gpm | Solids removal |
| 2 | Softener | 300 gpm | Hardness removal |
| 3 | RO (2-pass) | 150 gpm | Salt removal |
| 4 | EDI | 100 gpm | Ionic polish |
| 5 | UV sterilizer | 100 gpm | Microbial control |
| 6 | Mixed bed polish | 80 gpm | Final polish |
| 7 | Deaeration | 80 gpm | O₂ removal |

### 4.3 Water Balance

| Stream | Flow Rate | Daily Volume |
|--------|-----------|--------------|
| Raw Water In | 15 gpm | 21,600 gal |
| RO Reject | 7.5 gpm | 10,800 gal |
| Process Water | 6.5 gpm | 9,360 gal |
| Makeup | 1.0 gpm | 1,440 gal |
| Blowdown | 0.5 gpm | 720 gal |

---

## 5. Power System

### 5.1 Electrical Configuration

| Component | Rating | Purpose |
|-----------|--------|---------|
| Main Transformer | 138 kV / 4.16 kV, 35 MVA | Grid interface |
| Distribution | 4.16 kV switchgear | Power distribution |
| Rectifiers (5) | 4.16 kV / 200 VDC, 5 MW each | AC/DC conversion |
| UPS | 480 VAC, 500 kVA | Critical loads |
| Emergency Gen | 480 VAC, 2 MW | Backup power |

### 5.2 Power Consumption

| Load | Power (MW) | % Total |
|------|------------|---------|
| Electrolyzers | 22.9 | 85% |
| Compressors | 2.8 | 10% |
| Water Treatment | 0.5 | 2% |
| Cooling | 0.6 | 2% |
| Aux/BOP | 0.2 | 1% |
| **Total** | **27.0** | **100%** |

### 5.3 Power Quality Requirements

| Parameter | Requirement |
|-----------|-------------|
| Voltage Variation | ±5% |
| Frequency | 60 Hz ±0.5% |
| Power Factor | ≥0.95 |
| THD | ≤5% |

---

## 6. Compression and Storage

### 6.1 Compressor System

| Parameter | Specification |
|-----------|---------------|
| Manufacturer | Atlas Copco |
| Model | HX-350 |
| Type | Reciprocating, oil-free |
| Units | 3 (2 operating + 1 spare) |
| Inlet Pressure | 30 bar |
| Outlet Pressure | 200 bar |
| Capacity | 300 kg/hr each |
| Power | 1.4 MW each |
| Stages | 3 |
| Intercooling | Water cooled |

### 6.2 Storage System

| Parameter | Specification |
|-----------|---------------|
| Type | Steel pressure vessels |
| Manufacturer | Chart Industries |
| Vessels | 6 |
| Volume | 50 m³ each |
| Pressure Rating | 200 bar |
| Material | 316L SS |
| Total Capacity | 5,400 kg H₂ |
| Buffer Time | 12 hours at full rate |

### 6.3 Pressure Levels

| Location | Pressure |
|----------|----------|
| Electrolyzer outlet | 30 bar |
| Compressor inlet | 28 bar |
| Compressor outlet | 200 bar |
| Storage | 180-200 bar |
| Pipeline | 30 bar |

---

## 7. Safety Systems

### 7.1 Hazardous Area Classification

| Zone | Classification | Extent |
|------|----------------|--------|
| Electrolyzer room | Class I, Div 1, Group B | 10 ft radius |
| Compressor area | Class I, Div 1, Group B | 15 ft radius |
| Storage area | Class I, Div 2, Group B | 25 ft radius |
| Control room | Non-hazardous | N/A |

### 7.2 Detection Systems

| System | Sensors | Setpoints |
|--------|---------|-----------|
| H₂ Leak Detection | 48 catalytic | Low: 10% LEL, High: 25% LEL |
| O₂ Monitoring | 12 electrochemical | Low: 19.5%, High: 23.5% |
| Fire Detection | Flame, smoke | N/A |
| CO Detection | 8 electrochemical | 35 ppm alarm |

### 7.3 Emergency Systems

| System | Description | Response Time |
|--------|-------------|---------------|
| ESD | Full plant shutdown | <10 seconds |
| Blowdown | Safe vent to atmosphere | <30 seconds |
| Deluge | Water spray system | <60 seconds |
| Isolation | Auto valve closure | <5 seconds |

### 7.4 Safety Interlocks

| Interlock | Trigger | Action |
|-----------|---------|--------|
| High H₂ | 25% LEL | Shutdown electrolyzer |
| High Pressure | 220 bar | Open relief valve |
| Low Water | Low level | Shutdown electrolyzer |
| High Temperature | 85°C stack | Reduce power |
| Power Loss | Grid failure | Safe shutdown |

---

## 8. Control System

### 8.1 DCS Architecture

| Component | Manufacturer | Model |
|-----------|--------------|-------|
| DCS | Emerson | DeltaV |
| Controllers | Emerson | S-series |
| I/O | Emerson | Electronic marshalling |
| HMI | Emerson | DeltaV Live |
| Historian | OSIsoft | PI |

### 8.2 Control Loops

| Loop | Type | Setpoint |
|------|------|----------|
| Stack power | Cascade | Per production target |
| Water level | PID | 80% tank level |
| Pressure | Split-range | 30 bar |
| Temperature | PID | 65°C operating |
| pH | On-off | 6.5-7.5 |

### 8.3 Operating Modes

| Mode | Description | Authority |
|------|-------------|-----------|
| Startup | Controlled warmup | Operator |
| Normal | Automatic production | DCS |
| Turndown | Reduced capacity | DCS/Operator |
| Standby | Hot standby | Operator |
| Shutdown | Controlled cooldown | Operator |
| Emergency | Immediate stop | SIS |

---

## 9. Environmental Compliance

### 9.1 Emissions

| Emission | Source | Control |
|----------|--------|---------|
| CO₂ | Zero (green power) | N/A |
| NOx | Zero | N/A |
| Water vapor | Cooling tower | Drift eliminator |
| O₂ | Byproduct | Vented |

### 9.2 Waste Streams

| Stream | Volume | Disposition |
|--------|--------|-------------|
| RO concentrate | 10,800 gal/day | Evaporation pond |
| Spent resin | 500 kg/year | Hazmat disposal |
| Waste oil | 100 gal/year | Recycle |
| Cooling tower blowdown | 720 gal/day | Treatment |

### 9.3 Permits

| Permit | Agency | Status |
|--------|--------|--------|
| Air | TCEQ | Approved |
| Water | TCEQ | Approved |
| Building | El Paso County | Approved |
| Pipeline | Texas RRC | Approved |

---

## 10. Commissioning Requirements

### 10.1 Pre-Commissioning

| Activity | Status |
|----------|--------|
| Equipment installation | Complete |
| Piping hydrostatic test | Complete |
| Electrical termination | Complete |
| Instrument calibration | 95% complete |
| Control system FAT | Complete |

### 10.2 Commissioning Phases

| Phase | Duration | Description |
|-------|----------|-------------|
| Pre-comm | 4 weeks | Checks, cleaning, drying |
| Cold comm | 2 weeks | Non-hydrogen testing |
| Hot comm | 2 weeks | Hydrogen introduction |
| Performance | 2 weeks | Capacity testing |
| Reliability | 4 weeks | 30-day run |

### 10.3 Performance Test Criteria

| Parameter | Acceptance |
|-----------|------------|
| H₂ production rate | ≥95% design |
| H₂ purity | ≥99.999% |
| Efficiency | ≤56 kWh/kg |
| Availability | ≥90% during test |
| Safety systems | 100% functional |

---

## 11. Appendices

### A. P&IDs
- PID-001: Water Treatment
- PID-002: Electrolysis
- PID-003: Compression
- PID-004: Storage
- PID-005: Utilities

### B. Equipment List
- See Equipment Master List (EML-GH-001)

### C. Instrument List
- See Instrument Index (II-GH-001)

---

**Prepared By:** Dr. Marcus Thompson, Technical Lead
**Approved By:** Jennifer Walsh, Project Director
**Classification:** Internal
