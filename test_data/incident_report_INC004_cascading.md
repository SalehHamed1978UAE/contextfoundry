# Incident Report: INC-004 — Cascading Authentication Failure

## Incident Summary

| Field | Value |
|-------|-------|
| Incident ID | INC-004 |
| Severity | SEV-1 (Critical) |
| Duration | 1 hour 52 minutes |
| Start Time | 2024-12-05 09:12 UTC |
| End Time | 2024-12-05 11:04 UTC |
| Root Cause Service | user-service |
| Incident Commander | David Kim |
| Status | Resolved |

## Impact

A failure in the user-service caused a cascading authentication outage affecting payment-api, order-service, notification-service, and billing-service. All services that depend on user-service for authentication were unable to process requests. Approximately 45,000 API requests failed during the outage window.

## Root Cause

The session-cache (Redis) experienced an out-of-memory condition due to a session leak bug in user-service version 2.8.0. The user-service was not properly expiring session tokens, causing session-cache memory to grow unbounded. When session-cache hit its memory limit, it began evicting active sessions, causing mass re-authentication attempts that overwhelmed users-db.

## Timeline

- **09:12** - PagerDuty alert: user-service error rate exceeds 10%
- **09:14** - David Kim (platform-team) acknowledges alert
- **09:15** - payment-api starts reporting authentication failures
- **09:16** - order-service health check fails (depends on user-service for auth)
- **09:18** - notification-service reports elevated errors
- **09:20** - David Kim declares SEV-1, opens incident channel
- **09:22** - Alice Chen (payments-team) joins: payment-api is fully down
- **09:25** - Sarah Park (commerce-team) joins: order-service is down
- **09:28** - Mike Thompson (messaging-team) joins: notification-service degraded
- **09:30** - David identifies session-cache at 100% memory
- **09:35** - Bob Martinez (database-team) reports users-db connection pool at 95%
- **09:40** - Root cause identified: session leak in user-service 2.8.0
- **09:45** - Decision: flush session-cache and rollback user-service
- **09:50** - session-cache flushed: `redis-cli -h session-cache FLUSHALL`
- **09:55** - user-service rolled back to version 2.7.3
- **10:00** - user-service health checks passing
- **10:05** - users-db connection pool returning to normal
- **10:10** - payment-api resumes processing
- **10:15** - order-service resumes processing
- **10:20** - notification-service fully recovered
- **10:30** - All downstream services confirmed healthy
- **11:04** - Backlog cleared, incident formally resolved

## Services Affected

| Service | Impact | Duration | Team |
|---------|--------|----------|------|
| user-service | Complete outage | 48 min | platform-team |
| session-cache | OOM (out of memory) | 38 min | platform-team |
| users-db | Connection pool exhaustion | 30 min | database-team |
| payment-api | Auth failures, full outage | 55 min | payments-team |
| order-service | Auth failures, full outage | 50 min | commerce-team |
| notification-service | Degraded delivery | 62 min | messaging-team |
| billing-service | Degraded | 45 min | payments-team |

## People Involved

| Name | Team | Role in Incident |
|------|------|-----------------|
| David Kim | platform-team | Incident Commander |
| Alice Chen | payments-team | payment-api recovery |
| Sarah Park | commerce-team | order-service recovery |
| Mike Thompson | messaging-team | notification-service recovery |
| Bob Martinez | database-team | users-db recovery |
| Carol Johnson | platform-team | Executive escalation |
| Rachel Green | database-team | Database monitoring |

## Cascading Failure Chain

```
session-cache OOM
  → user-service cannot store/retrieve sessions
    → mass re-auth attempts hit users-db
      → users-db connection pool exhausted
        → user-service fully down
          → payment-api auth fails
          → order-service auth fails
          → notification-service auth fails
          → billing-service auth fails
```

## Action Items

1. **DONE**: Rollback user-service to 2.7.3
2. **DONE**: Flush and restart session-cache
3. **TODO**: Fix session expiry bug in user-service (assign to platform-team)
4. **TODO**: Add session-cache memory monitoring alert at 80% threshold
5. **TODO**: Implement circuit breaker in user-service for session-cache failures
6. **TODO**: Add session-cache maxmemory-policy to evict oldest sessions first
7. **TODO**: Each downstream service should implement auth token caching to reduce dependency on user-service
8. **TODO**: Add runbook entry for session-cache OOM scenarios

## Relationship to Other Incidents

- **Related to**: INC-003 (similar cascading pattern from infrastructure failure)
- **Affects**: user-service, payment-api, order-service, notification-service, billing-service
- **Root infrastructure**: session-cache, users-db

## Lessons Learned

1. A single cache failure can cascade to every authenticated service in the platform
2. Session token TTL must be enforced at the cache level, not just application level
3. Circuit breakers need to cover cache dependencies, not just service-to-service calls
4. Each team should implement local auth token caching to survive user-service outages
5. Memory monitoring on session-cache was insufficient — alert threshold was too high

## Document Metadata

- **Author**: David Kim (platform-team)
- **Created**: 2024-12-05
- **Reviewed by**: Carol Johnson (platform-team)
