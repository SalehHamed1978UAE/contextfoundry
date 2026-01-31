# Cost Reduction Planning Session
**Date:** November 15, 2024
**Attendees:** Mia White, George Brown, Julia Adams, Alex Rivera
**Purpose:** Present detailed cost analysis for 15% savings target

---

## Executive Summary

**Current Annual Tech Spend:** $2.4M
**15% Savings Target:** $360K
**Identified Savings:** $285K (11.9%)
**Gap to Target:** $75K

---

## Identified Savings Breakdown

### 1. Infrastructure Optimization: $115K

**George Brown presented:**

- Unused cloud resources: $96K/year
  - 12 idle EC2 instances (dev/test environments never decommissioned)
  - 3TB of orphaned S3 storage
  - Unused load balancer capacity

- Right-sizing opportunities: $19K/year
  - Payment Service database is over-provisioned
  - API Gateway instances can be downsized during off-peak hours

**Alex Rivera:** The Payment Service database sizing is intentional - we need headroom for Black Friday.

**George Brown:** We could use auto-scaling instead of fixed over-provisioning. Saves money 11 months of the year.

**Mia White:** Let's pilot auto-scaling on a less critical service first. Maybe Notification Service?

**DECISION:** Pilot database auto-scaling on Notification Service in Q1.

---

### 2. Vendor Consolidation: $85K

**Julia Adams presented:**

- Analytics tools: $40K savings
  - Currently using Mixpanel, Amplitude, AND custom Metabase
  - Proposal: Consolidate to Amplitude + Metabase
  - Michael Torres approved, pending migration plan

- Customer support tools: $25K savings
  - Redundant Zendesk and Intercom subscriptions
  - Consolidate to Intercom only

- Development tools: $20K savings
  - Unused GitHub Enterprise seats (we have 50, use 35)
  - Downgrade Figma plan (Tom Baker approved)

**Mia White:** The analytics consolidation makes sense, but I want to ensure we don't lose any critical tracking.

**Julia Adams:** Ian Clark reviewed it. We'll lose some historical Mixpanel data, but we can export what matters.

---

### 3. Contract Renegotiations: $60K

**George Brown:**

- DataDog renewal: Negotiated 15% discount ($30K savings)
- AWS Enterprise Agreement: Additional credits secured ($20K)
- CloudShift termination: Avoided 3 months of unused service ($10K)

**Mia White:** Good work on these. The DataDog discount is particularly helpful since we're using it more post-migration.

---

### 4. Process Improvements: $25K

**Alex Rivera:**

- Reduced on-call contractor spend by improving incident automation
- Sarah Chen and Alex Thompson implemented auto-remediation for common alerts

---

## Gap Analysis

**Mia White:** We're $75K short of the 15% target. Options?

**George Brown:** We could reduce redundancy in the Fraud Detection Service infrastructure. It's running in 3 availability zones when 2 would suffice.

**Mia White:** I'm uncomfortable reducing Fraud Detection redundancy. That's a critical path for Payment Service.

**Alex Rivera:** What about delaying the observability platform purchase we discussed?

**Mia White:** We already deferred that from Q4 to Q1. Pushing it further hurts our SRE capabilities.

**Julia Adams:** Could we revisit headcount planning? We have 3 open roles budgeted.

**Mia White:** I'd rather not freeze hiring. The frontend team is already stretched.

**OPEN QUESTION:** How do we close the $75K gap without impacting reliability or growth?

---

## Concerns Raised

**Mia White:** I want to formally document my concerns about the 15% target. It's achievable, but risky. We're trading operational margin for savings.

**George Brown:** I share that concern. The infrastructure optimization assumes nothing goes wrong during the changes.

**Julia Adams:** From Product side, the analytics consolidation will create a temporary data gap. Ian Clark flagged this as a risk for Q1 planning.

---

## Next Steps

1. Execute infrastructure cleanup immediately ($96K)
2. Begin analytics consolidation (Julia Adams, target: December 15)
3. Complete vendor renegotiations (George Brown, done)
4. Present gap options to CFO (Mia White, November 20)
5. Final decision on 15% vs realistic target (Board, November 25)

---

## Appendix: Risk Register

| Savings Item | Amount | Risk Level | Mitigation |
|-------------|--------|------------|------------|
| Unused cloud resources | $96K | Low | Already idle |
| Analytics consolidation | $40K | Medium | Data migration plan |
| DB auto-scaling pilot | $19K | Medium | Start with non-critical service |
| Fraud Detection redundancy | $25K | High | NOT RECOMMENDED |
