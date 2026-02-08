# High-Temperature Superconducting Wire Manufacturing Specification

**Document Type:** Manufacturing Specification
**Authority Level:** 1 (Authoritative)
**Document Number:** TEC-MAT-001
**Version:** 2.0
**Effective Date:** January 1, 2026
**Owner:** Dr. Robert Chen, Materials R&D Director
**Classification:** Confidential - Proprietary

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jun 2024 | R. Chen | Initial specification |
| 1.5 | Dec 2024 | R. Chen | Process optimization |
| 2.0 | Jan 2026 | R. Chen | Production scale-up |

---

## 1. Product Overview

### 1.1 Product Description

Nexus HTS Wire is a second-generation (2G) high-temperature superconducting wire based on REBCO (Rare Earth Barium Copper Oxide) coated conductor technology. The wire exhibits zero electrical resistance when cooled below its critical temperature, enabling lossless current transmission.

### 1.2 Product Specifications

| Parameter | Standard Grade | High-Performance |
|-----------|----------------|------------------|
| Width | 4 mm | 4 mm, 12 mm |
| Thickness | 0.1 mm | 0.1 mm |
| Critical Current (Ic) | 150 A/4mm | 250 A/4mm |
| Critical Temperature (Tc) | 92 K | 92 K |
| Minimum Bend Radius | 25 mm | 15 mm |
| Operating Temperature | 20-77 K | 4-77 K |
| Piece Length | 100-500 m | 100-1000 m |

### 1.3 Applications

| Application | Requirements | Customers |
|-------------|--------------|-----------|
| MRI Magnets | High field, long length | Siemens Healthineers |
| Fusion Reactors | Extreme field, radiation | Government labs |
| Power Cables | High capacity, flexibility | Utilities |
| Motors/Generators | Compact, high efficiency | Transportation |
| Research Magnets | Ultra-high field | Universities |

---

## 2. Wire Architecture

### 2.1 Layer Structure

```
┌─────────────────────────────────────────────────────┐
│                  Silver Cap (2 μm)                   │
├─────────────────────────────────────────────────────┤
│                   REBCO (1-2 μm)                     │
├─────────────────────────────────────────────────────┤
│                   Buffer Stack                       │
│  ┌─────────────────────────────────────────────┐    │
│  │           LaMnO₃ (30 nm)                    │    │
│  ├─────────────────────────────────────────────┤    │
│  │           MgO (10 nm) - IBAD               │    │
│  ├─────────────────────────────────────────────┤    │
│  │           Y₂O₃ (10 nm)                      │    │
│  ├─────────────────────────────────────────────┤    │
│  │           Al₂O₃ (80 nm)                     │    │
│  └─────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────┤
│              Hastelloy Substrate (50 μm)             │
├─────────────────────────────────────────────────────┤
│                  Silver Base (2 μm)                  │
└─────────────────────────────────────────────────────┘
```

### 2.2 Layer Specifications

| Layer | Material | Thickness | Function |
|-------|----------|-----------|----------|
| Cap | Silver | 2 μm | Stabilizer, protection |
| Superconductor | REBCO | 1-2 μm | Current carrier |
| Buffer 1 | LaMnO₃ | 30 nm | Lattice match |
| Buffer 2 | MgO (IBAD) | 10 nm | Texture template |
| Buffer 3 | Y₂O₃ | 10 nm | Diffusion barrier |
| Buffer 4 | Al₂O₃ | 80 nm | Seed layer |
| Substrate | Hastelloy C276 | 50 μm | Mechanical support |
| Base | Silver | 2 μm | Stabilizer |

---

## 3. Manufacturing Process

### 3.1 Process Flow

```
Substrate Prep → Buffer Deposition → REBCO Deposition → Metallization → Testing → Packaging
     (1)              (2-5)               (6)              (7)          (8)        (9)
```

### 3.2 Process Steps

| Step | Process | Equipment | Parameters |
|------|---------|-----------|------------|
| 1 | Substrate cleaning | Ultrasonic, plasma | 99.99% clean |
| 2 | Al₂O₃ deposition | RF sputtering | 200°C, 2 mTorr |
| 3 | Y₂O₃ deposition | RF sputtering | 250°C, 2 mTorr |
| 4 | MgO IBAD | Ion beam assisted | 10-12° tilt |
| 5 | LaMnO₃ deposition | PLD | 800°C, O₂ |
| 6 | REBCO deposition | MOCVD | 780°C, O₂ |
| 7 | Silver sputtering | DC sputtering | Room temp |
| 8 | Oxygenation | Furnace anneal | 500°C, O₂ |
| 9 | Testing | Ic measurement | 77K, self-field |

---

## 4. IBAD MgO Buffer Process

### 4.1 Ion Beam Parameters

| Parameter | Value |
|-----------|-------|
| Ion Species | Ar⁺ |
| Energy | 750 eV |
| Current Density | 150 μA/cm² |
| Incidence Angle | 45° |
| Assist Angle | 45° |
| Substrate Temperature | Ambient |
| Deposition Rate | 0.5 nm/min |
| Target Thickness | 10 nm |

### 4.2 Texture Requirements

| Parameter | Requirement | Measurement |
|-----------|-------------|-------------|
| In-plane texture (Δφ) | <10° FWHM | XRD phi scan |
| Out-of-plane texture (Δω) | <5° FWHM | XRD omega scan |
| Biaxial texture | Required | Pole figure |
| Surface roughness | <1 nm RMS | AFM |

---

## 5. REBCO Deposition (MOCVD)

### 5.1 Precursor Specifications

| Precursor | Compound | Purity | Flow Rate |
|-----------|----------|--------|-----------|
| Y source | Y(thd)₃ | 99.9% | 0.4 sccm |
| Ba source | Ba(thd)₂ | 99.9% | 0.8 sccm |
| Cu source | Cu(thd)₂ | 99.9% | 1.0 sccm |
| Oxidizer | O₂ | 99.999% | 500 sccm |
| Carrier | Ar | 99.999% | 200 sccm |

### 5.2 Deposition Conditions

| Parameter | Value |
|-----------|-------|
| Substrate Temperature | 780 ± 5°C |
| Chamber Pressure | 2.5 Torr |
| Deposition Rate | 0.5-1.0 μm/hr |
| Target Stoichiometry | Y:Ba:Cu = 1:2:3 |
| Film Thickness | 1.0-2.0 μm |
| Line Speed | 5-10 m/hr |

### 5.3 Critical Process Controls

| Control | Setpoint | Tolerance | Action |
|---------|----------|-----------|--------|
| Temperature | 780°C | ±5°C | Auto adjust |
| O₂ Partial Pressure | 500 mTorr | ±20 mTorr | Alarm |
| Precursor Ratio | 1:2:3 | ±5% | Adjust flow |
| Line Speed | Target | ±2% | Servo control |

---

## 6. Quality Control

### 6.1 In-Line Testing

| Test | Method | Frequency | Criteria |
|------|--------|-----------|----------|
| Visual | Camera inspection | Continuous | No defects |
| Thickness | Ellipsometry | Every 10 m | ±10% target |
| Texture | XRD | Every 50 m | Δφ <10° |
| Surface | Laser profilometry | Continuous | Ra <5 nm |

### 6.2 End-of-Line Testing

| Test | Method | Sample Rate | Specification |
|------|--------|-------------|---------------|
| Critical Current (Ic) | 4-point probe @ 77K | 100% | ≥150 A/4mm |
| Ic Uniformity | Reel scanner | 100% | CV <10% |
| n-value | I-V curve | 10% | ≥25 |
| Bend Test | Mandrel | 5% | No degradation |
| Tensile | Pull test | 2% | ≥600 MPa |

### 6.3 Acceptance Criteria

| Parameter | Standard | High-Perf |
|-----------|----------|-----------|
| Ic (77K, self-field) | ≥150 A/4mm | ≥250 A/4mm |
| Ic uniformity (CV) | ≤10% | ≤5% |
| n-value | ≥25 | ≥30 |
| Piece length | ≥100 m | ≥200 m |
| Defect density | <1/m | <0.5/m |

---

## 7. Production Capacity

### 7.1 Current Capacity

| Line | Location | Capacity | Status |
|------|----------|----------|--------|
| Line 1 | Albuquerque | 200 km/year | Operating |
| Line 2 | Albuquerque | 300 km/year | Operating |
| Line 3 | Albuquerque | 500 km/year | Commissioning |
| **Total** | | **1,000 km/year** | |

### 7.2 Production Economics

| Parameter | Value |
|-----------|-------|
| Material Cost | $25/m |
| Conversion Cost | $35/m |
| Total Cost | $60/m |
| Selling Price | $100-150/m |
| Gross Margin | 40-60% |

### 7.3 Yield Metrics

| Category | Current | Target 2027 |
|----------|---------|-------------|
| First Pass Yield | 75% | 85% |
| Overall Yield | 85% | 92% |
| Piece Length (avg) | 180 m | 300 m |
| Scrap Rate | 15% | 8% |

---

## 8. Material Specifications

### 8.1 Raw Materials

| Material | Grade | Supplier | Inventory |
|----------|-------|----------|-----------|
| Hastelloy C276 | HTS grade | Haynes | 6 months |
| REBCO precursors | Electronic | Alfa Aesar | 3 months |
| Silver | 99.99% | ESPI | 3 months |
| Process gases | Ultra-high purity | Linde | 1 month |
| MgO target | 99.9% | Kurt Lesker | 6 months |

### 8.2 Material Handling

| Material | Storage | Handling |
|----------|---------|----------|
| Substrates | Clean room, N₂ | Gloves, vacuum |
| Precursors | Glovebox, -20°C | Inert atmosphere |
| Finished wire | Desiccated, 25°C | Gloves, ESD |

---

## 9. Environmental and Safety

### 9.1 Process Hazards

| Hazard | Source | Control |
|--------|--------|---------|
| High temperature | MOCVD reactor | Interlocks, PPE |
| Toxic gases | Precursor decomposition | Scrubber, monitoring |
| High voltage | Ion beam source | LOTO, guards |
| Cryogens | Testing | Ventilation, PPE |

### 9.2 Emissions Control

| Emission | Source | Treatment |
|----------|--------|-----------|
| VOCs | MOCVD exhaust | Thermal oxidizer |
| Particulates | Sputtering | HEPA filtration |
| CO₂ | Combustion | None (permitted) |
| Water vapor | Cooling | None |

### 9.3 Waste Streams

| Waste | Volume | Disposition |
|-------|--------|-------------|
| Spent targets | 100 kg/year | Recycle |
| Failed product | 150 km/year | Recycle |
| Chemicals | 500 L/year | Hazmat disposal |
| Packaging | 2,000 kg/year | Recycle |

---

## 10. References

- ASTM F2714 (Superconductor Test Methods)
- IEC 61788 (Superconductivity Standards)
- Internal Specification HTS-001 through HTS-025
- Process Validation Report PVR-HTS-2025

---

**Prepared By:** Dr. Robert Chen, Materials R&D Director
**Approved By:** John Williams, Materials Division President
**Classification:** Confidential - Proprietary Technology
