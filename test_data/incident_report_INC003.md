# Incident Report: INC-003 — Payment Processing Outage

## Incident Summary

| Field | Value |
|-------|-------|
| Incident ID | INC-003 |
| Severity | SEV-1 (Critical) |
| Duration | 2 hours 37 minutes |
| Start Time | 2024-11-28 14:23 UTC |
| End Time | 2024-11-28 17:00 UTC |
| Affected Service | payment-api |
| Incident Commander | Alice Chen |
| Status | Resolved |

## Impact

The payment-api service experienced a complete outage affecting all payment processing. Approximately 12,000 transactions were delayed. The billing-service and order-service were also impacted as they depend on payment-api for transaction confirmation.

## Root Cause

A deployment of payment-api version 3.2.1 introduced a database migration that added an index to the transactions table in payments-db. The index creation locked the table for writes, causing connection pool exhaustion. This was caused by INC-002 recommendations being partially implemented — the connection pool increase was applied without the corresponding query timeout changes.

## Timeline

- **14:23** - PagerDuty alert fires: payment-api error rate exceeds 5%
- **14:25** - Alice Chen (payments-team) acknowledges alert
- **14:30** - Alice identifies payments-db connection pool at 100% utilization
- **14:35** - David Kim (platform-team) joins incident channel
- **14:40** - Root cause identified: table lock from deployment migration
- **14:45** - Decision to rollback payment-api to version 3.2.0
- **14:50** - Rollback initiated via: `kubectl rollout undo deployment/payment-api`
- **15:00** - payment-api rolled back, but payments-db still has lock
- **15:15** - database-team contacted for emergency intervention
- **15:30** - Bob Martinez (database-team) kills the blocking migration query
- **15:45** - payments-db connection pool returns to normal
- **16:00** - payment-api health checks passing, processing resumed
- **16:30** - Backlog of 12,000 delayed transactions processed
- **17:00** - All systems nominal, incident resolved

## Services Affected

| Service | Impact | Duration |
|---------|--------|----------|
| payment-api | Complete outage | 2h 37m |
| billing-service | Degraded (payment confirmations delayed) | 2h 37m |
| order-service | Degraded (order completion blocked) | 1h 45m |
| notification-service | Minor (payment confirmation emails delayed) | 1h 00m |

## People Involved

| Name | Team | Role in Incident |
|------|------|-----------------|
| Alice Chen | payments-team | Incident Commander |
| David Kim | platform-team | Infrastructure Support |
| Bob Martinez | database-team | Database Recovery |
| Carol Johnson | platform-team | Escalation Manager |

## Action Items

1. **DONE**: Rollback payment-api to 3.2.0
2. **TODO**: Add pre-deployment check for table-locking migrations
3. **TODO**: Implement online index creation (CREATE INDEX CONCURRENTLY)
4. **TODO**: Add circuit breaker between payment-api and payments-db
5. **TODO**: Update runbook with migration-related failure scenario
6. **TODO**: Add deployment freeze policy for payments-db schema changes

## Relationship to Other Incidents

- **Caused by**: INC-002 (partial implementation of connection pool recommendations)
- **Affects**: payment-api, billing-service, order-service, notification-service
- **Related runbook**: runbook_payment_api_recovery.md

## Lessons Learned

1. Database migrations that lock tables must never run during business hours
2. Connection pool changes and query timeout changes must be deployed together
3. The payments-db should have a read replica for failover during maintenance
4. The circuit breaker pattern in payment-api needs to cover database failures, not just downstream service failures

## Document Metadata

- **Author**: Alice Chen (payments-team)
- **Created**: 2024-11-29
- **Reviewed by**: Carol Johnson (platform-team)
