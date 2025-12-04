# 2025 Engineering Roadmap - DRAFT

**Document Owner:** Mia White, VP Engineering
**Status:** DRAFT - Pending Board Approval
**Last Updated:** November 12, 2024

---

## Strategic Themes

### Theme 1: Complete Cloud Transformation
Finish what we started in 2024. Payment Service migration and full cloud-native operations.

### Theme 2: Operational Excellence
Invest in observability, automation, and incident reduction. Target: 50% fewer customer-facing incidents.

### Theme 3: Selective Innovation
Explore AI operations assistant (pending feasibility study) while maintaining core platform focus.

### Theme 4: Sustainable Efficiency
Meet cost reduction targets without sacrificing reliability or team health.

---

## Q1 2025 Priorities

### 1. Payment Service Cloud Migration
**Owner:** Emily Rodriguez / Lisa Park
**Status:** Primary focus
**Dependencies:** Fraud Detection API modernization (must complete by mid-January)

**Milestones:**
- January 6: Begin migration prep
- January 15: PCI audit (must pass with stable environment)
- February 15: Production cutover target
- February 28: Stabilization complete

**Risk:** PCI audit timing is tight. If Fraud Detection work slips, entire timeline is at risk.

### 2. Checkout Flow Redesign
**Owner:** Emily Zhang / Fiona Martinez
**Status:** Rescheduled from Q4

**Milestones:**
- January 15: Design finalization
- February 1: Development start
- March 15: Beta release
- March 31: General availability

**Note:** Deferred from Q4 due to Payment Service constraints. Enterprise sales has been informed.

### 3. Cost Reduction Execution - Phase 1
**Owner:** George Brown / Julia Adams
**Status:** Planning

**Milestones:**
- January 1: Begin unused resource cleanup
- January 15: Analytics tool consolidation starts
- February 1: Vendor renegotiations complete
- March 1: Phase 1 savings validated

**Target:** $140K savings (Tier 1 items)

---

## Q2 2025 Priorities

### 1. AI Operations Assistant Prototype
**Owner:** Ian Clark / Hannah White
**Status:** Contingent on Q1 feasibility study

**Milestones (if approved):**
- April 1: Prototype development begins
- May 15: Internal testing
- June 15: Pilot customer identification
- June 30: Prototype evaluation

**Condition:** Must not impact Q1 commitments. Only proceeds if feasibility study is positive.

### 2. Observability Platform Expansion
**Owner:** George Brown / Alex Thompson
**Status:** Contingent on Q4 2024 core deployment

**Milestones:**
- April 1: ML anomaly detection integration
- May 1: Full distributed tracing rollout
- June 1: Self-service dashboard creation

### 3. Cost Reduction Execution - Phase 2
**Owner:** George Brown
**Status:** Planning

**Milestones:**
- April 1: Database auto-scaling pilot
- May 1: Contractor reduction (automation-based)
- June 1: Phase 2 savings validated

**Target:** $145K additional savings (Tier 2 items)

---

## Q3-Q4 2025 Priorities (Tentative)

### Q3 Focus Areas
- AI Operations Assistant MVP (if prototype succeeds)
- Platform scalability improvements
- Developer experience enhancements

### Q4 Focus Areas
- 2026 planning
- Technical debt reduction sprint
- Year-end optimization

**Note:** Q3-Q4 priorities are tentative and will be refined based on Q1-Q2 outcomes.

---

## Resource Allocation

### Headcount Plan

| Role | Q1 | Q2 | Q3 | Q4 |
|------|----|----|----|----|
| Current Headcount | 28 | 28 | 29 | 29 |
| Planned Hires | 0 | 1 | 0 | 0 |
| Attrition Assumption | 1 | 1 | 1 | 1 |
| Year-End | - | - | - | 29 |

**Note:** Hiring is constrained due to cost reduction targets. One hire approved for Q2 (Senior SRE).

### Team Capacity Allocation

| Team | Q1 Cloud | Q1 Product | Q1 Efficiency | Q2+ Innovation |
|------|----------|------------|---------------|----------------|
| Platform | 50% | 20% | 30% | TBD |
| Frontend | 10% | 70% | 20% | TBD |
| SRE | 30% | 10% | 60% | TBD |
| Data | 20% | 20% | 60% | TBD |

---

## Key Dependencies

### External Dependencies
- MigrateX support for Payment Service migration
- AWS capacity in us-west-2 region
- PCI auditor availability (January 15 fixed)

### Internal Dependencies
- Fraud Detection API modernization (blocks Payment Service)
- Observability platform deployment (blocks Q2 ML work)
- Cost reduction approval (blocks certain investments)

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Payment Service timeline slip | Medium | High | Weekly executive check-ins, escalation path |
| PCI audit issues | Low | Critical | Pre-audit review with external consultant |
| Team burnout | Medium | High | Workload monitoring, selective hiring |
| Cost targets conflict with delivery | High | Medium | Transparent tradeoff discussions |
| AI prototype fails | Medium | Low | Limited investment (20% time only) |

---

## Success Metrics

| Metric | Current | Q2 Target | Year-End Target |
|--------|---------|-----------|-----------------|
| Cloud Migration % | 45% | 100% | 100% |
| Customer-Facing Incidents | 4/month | 2/month | 1/month |
| MTTR | 45 min | 30 min | 20 min |
| Cost vs 2024 | Baseline | -6% | -12% |
| Employee NPS | 42 | 45 | 50 |

---

## Open Questions for Board

1. Is 12% cost reduction acceptable, or does the Board require the full 15%?
2. Should we proceed with AI Operations investment before cost targets are met?
3. What's the appetite for acquisition vs build for AI capabilities?
4. Are there corporate strategic changes that would impact this roadmap?

---

## Approval Status

- [ ] Mia White (VP Engineering) - Author, pending final review
- [ ] Michael Torres (VP Product) - Pending alignment meeting
- [ ] James Wilson (CFO) - Pending budget confirmation
- [ ] Board - December presentation scheduled

---

**Next Steps:**
1. November 20: Leadership alignment meeting
2. November 25: CFO budget review
3. December 5: Board presentation
4. December 15: Final roadmap published

---

**Document History:**
- v0.1 (Nov 12, 2024): Initial draft
