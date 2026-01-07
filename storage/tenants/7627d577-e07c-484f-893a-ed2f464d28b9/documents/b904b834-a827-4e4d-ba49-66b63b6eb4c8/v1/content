# Order Service Runbook

**Service**: Order Service  
**Owner**: Commerce Team  
**Last Updated**: December 2025

---

## Service Overview

The Order Service is the core commerce service responsible for processing customer orders. It handles the complete order lifecycle from cart submission to fulfillment handoff.

### Key Metrics
- Average daily orders: 50,000
- Peak orders per minute: 500
- P99 latency: 250ms
- Availability target: 99.9%

---

## Architecture

### Dependencies

The Order Service depends on the following services:

| Dependency | Type | Purpose | Failure Impact |
|------------|------|---------|----------------|
| Auth Service | Synchronous | Validate customer tokens | Orders fail |
| Payment Service | Synchronous | Process payments | Orders fail at payment step |
| Inventory Service | Synchronous | Reserve stock | Orders fail at inventory step |
| Notification Service | Asynchronous | Send confirmations | Delayed notifications only |
| Orders Database | Synchronous | Persist order data | Complete failure |

### Dependency Details

**Auth Service dependency:**
- All incoming requests validated against Auth Service
- Token validation timeout: 500ms
- Fallback: None (required for security)
- If Auth Service is down, Order Service returns 503

**Payment Service dependency:**
- Called during checkout to process payment
- Payment timeout: 30 seconds (external processor latency)
- Fallback: Queue for retry (up to 3 attempts)
- If Payment Service is down, orders queue for retry

**Inventory Service dependency:**
- Called to check and reserve stock
- Inventory check timeout: 2 seconds
- Fallback: None (must verify stock)
- If Inventory Service is down, orders fail with "temporarily unavailable"

**Notification Service dependency:**
- Called asynchronously after order completion
- Fire-and-forget with retry queue
- If Notification Service is down, notifications queue indefinitely

**Orders Database dependency:**
- All order data persisted to Orders Database
- Connection pool: 100 connections
- If database is down, complete service failure

---

## Common Issues and Resolution

### Issue: High latency on order submission

**Symptoms:**
- P99 latency > 500ms
- Increased timeout errors

**Investigation:**
1. Check Orders Database connection pool utilization
2. Check Payment Service latency (external processor issues)
3. Check Inventory Service latency
4. Review recent deployments

**Resolution:**
- If database pool exhausted: Increase pool size or kill slow queries
- If Payment Service slow: Check external processor status page
- If Inventory Service slow: Check Products Database

### Issue: Order submission failures

**Symptoms:**
- 500 errors on /orders endpoint
- Error rate > 1%

**Investigation:**
1. Check Auth Service health (token validation)
2. Check Payment Service health
3. Check Inventory Service health
4. Check Orders Database connectivity

**Resolution:**
- Identify which dependency is failing from error logs
- If Auth Service: Escalate to Security Team
- If Payment Service: Check external processor, escalate to Commerce Team
- If Inventory Service: Escalate to Commerce Team
- If Database: Escalate to Data Engineering Team

### Issue: Missing order notifications

**Symptoms:**
- Customers not receiving confirmation emails
- Notification queue growing

**Investigation:**
1. Check Notification Service health
2. Check notification queue depth
3. Check SendGrid/Twilio status

**Resolution:**
- If Notification Service down: Escalate to Platform Engineering Team
- If external provider issue: Wait for resolution, notifications will retry
- If queue backed up: Scale Notification Service workers

---

## Deployment

### Pre-deployment checklist
- [ ] All tests passing
- [ ] Database migrations reviewed
- [ ] Dependency versions compatible
- [ ] Rollback plan documented

### Deployment steps
1. Deploy to staging environment
2. Run integration tests against staging
3. Deploy to production (canary 10%)
4. Monitor error rates for 15 minutes
5. Complete rollout to 100%

### Rollback procedure
1. Revert deployment in CI/CD
2. Verify rollback complete
3. Investigate failure cause
4. Document in post-deployment review

---

## Contacts

- **Team Lead**: David Kim (david.k@nexus.example)
- **On-call**: PagerDuty "commerce-primary"
- **Slack channel**: #commerce-team
- **Escalation**: See Team Responsibilities document

---

## Related Documents

- Architecture Overview
- Team Responsibilities
- Payment Service Runbook
- Inventory Service Runbook
