# Cloud Migration Plan - 2024/2025

**Document Owner:** Alex Rivera, Director of Platform
**Last Updated:** November 10, 2024
**Status:** IN PROGRESS

---

## Executive Summary

This document outlines our strategy for migrating critical infrastructure from on-premise data centers to AWS cloud. The migration will be executed in phases over 6 months, with Auth Service and API Gateway completing in Q4 2024, and Payment Service completing in Q1 2025.

## Current State

**On-Premise Infrastructure:**
- 3 physical data centers (Primary, DR, Edge)
- 47 bare-metal servers
- 12 TB PostgreSQL databases
- Legacy networking requiring VPN for all internal traffic

**Pain Points:**
- Infrastructure costs growing 20% annually
- 6-week lead time for new server provisioning
- Limited scalability for traffic spikes (Black Friday, product launches)
- DR failover tested quarterly but never fully validated

## Target State

**AWS Cloud Infrastructure:**
- Multi-region deployment (us-east-1 primary, us-west-2 DR)
- Kubernetes (EKS) for container orchestration
- RDS PostgreSQL with automated failover
- Auto-scaling for traffic elasticity

**Expected Benefits:**
- 35% cost reduction over 3 years
- Same-day provisioning for new services
- Automatic scaling up to 10x normal load
- Real DR capability with sub-1-hour RTO

## Migration Phases

### Phase 1: Auth Service (October - November 2024)
**Status:** IN PROGRESS (65% complete)
**Owner:** Sarah Chen

**Components:**
- User authentication endpoints
- Session management
- OAuth integrations
- User Database replication

**Key Milestones:**
- [x] Infrastructure setup (complete)
- [x] Database replication (complete)
- [x] API endpoint migration (in progress)
- [ ] Load testing
- [ ] Production cutover

**Risks:**
- Connection pooling behavior differs in cloud (mitigated with Ryan Adams testing)
- OAuth callback URLs need customer communication

### Phase 2: API Gateway (November - December 2024)
**Status:** PLANNED
**Owner:** Brian Taylor

**Components:**
- Request routing
- Rate limiting
- SSL termination
- Logging and metrics

**Dependencies:**
- Auth Service must be stable before API Gateway migration
- MigrateX onboarding must be complete

### Phase 3: Notification Service (December 2024)
**Status:** PLANNED
**Owner:** Alex Thompson

**Components:**
- Email delivery pipeline
- SMS gateway integration
- Push notification service
- Queue management

**Notes:**
- Lower priority than Auth/API Gateway
- Circuit breaker implementation should precede migration

### Phase 4: Payment Service (January - February 2025)
**Status:** DEFERRED
**Owner:** Emily Rodriguez / Lisa Park

**Components:**
- Transaction processing
- Fraud Detection Service integration
- PCI-compliant data handling
- Financial reconciliation

**Dependencies:**
- Fraud Detection API modernization (Lisa Park, 2 weeks)
- PCI audit must occur post-stabilization (January 15 deadline)

**Risks:**
- Most complex migration due to PCI requirements
- Legacy Fraud Detection integration needs decoupling
- Must maintain zero-downtime for payment processing

---

## Vendor Tooling

### Decision History

**August 2024:** Selected CloudShift ($60K/year) based on initial evaluation
**October 2024:** Concerns raised about CloudShift support responsiveness
**November 2024:** **DECISION CHANGED** - Switched to MigrateX ($85K/year)

**Rationale for Switch:**
- CloudShift support SLA (24hr) inadequate for production issues
- PostgreSQL extension support incomplete (critical for pgvector)
- MigrateX reference customers (FinanceApp Inc) had positive experience
- Better rollback capabilities (15 min vs 45 min)

**Lessons Learned:**
Initial vendor selection weighted cost too heavily over support quality. Future evaluations will include support SLA as primary criterion.

---

## Rollback Strategy

Each migration phase includes automated rollback:

1. **Pre-cutover:** Full database snapshot and infrastructure state capture
2. **During cutover:** Traffic split (10% → 50% → 100%) with automatic rollback if error rates exceed 1%
3. **Post-cutover:** 48-hour burn-in period before decommissioning old infrastructure
4. **Emergency:** One-command rollback returns to previous state within 15 minutes

---

## Timeline Summary

| Phase | Service | Start | Target Complete | Status |
|-------|---------|-------|-----------------|--------|
| 1 | Auth Service | Oct 1 | Nov 29 | In Progress |
| 2 | API Gateway | Nov 20 | Dec 6 | Planned |
| 3 | Notification Service | Dec 10 | Dec 20 | Planned |
| 4 | Payment Service | Jan 6 | Feb 28 | Deferred |

---

## Resource Allocation

| Team Member | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|-------------|---------|---------|---------|---------|
| Sarah Chen | Lead | Support | - | Support |
| Brian Taylor | Support | Lead | Support | Support |
| Amy Chen | Testing | Testing | - | Testing |
| Ryan Adams | Database | Database | - | Database |
| Alex Thompson | - | - | Lead | Support |
| Lisa Park | - | - | - | Lead |
| Priya Sharma | Shadow | Active | Active | Active |

---

## Open Questions

1. ~~Should we proceed with CloudShift or evaluate alternatives?~~ **RESOLVED: MigrateX selected**

2. Can we complete Payment Service migration before PCI audit? **UNDER DISCUSSION** - Current plan is to stabilize before audit, complete migration after.

3. Should Fraud Detection Service migrate with Payment Service or separately? **UNRESOLVED** - Lisa Park is analyzing options.

4. What's the rollback plan if we discover issues post-migration? **DOCUMENTED** - See Rollback Strategy section.

---

## Appendix: Lessons Learned

### From Auth Service Migration (So Far)

**What Went Well:**
- MigrateX tooling is excellent
- Database replication was seamless
- Team ramped up quickly on new tools

**What We'd Do Differently:**
- Start vendor evaluation earlier (cost us 2 weeks)
- Include more buffer time for unexpected dependencies
- Communicate earlier with dependent teams (Payments Team integration testing)

---

**Document History:**
- v1.0 (Aug 15, 2024): Initial plan with CloudShift
- v1.1 (Oct 22, 2024): Updated timeline for Payment Service deferral
- v1.2 (Nov 1, 2024): Vendor change to MigrateX
- v1.3 (Nov 10, 2024): Current version with lessons learned
