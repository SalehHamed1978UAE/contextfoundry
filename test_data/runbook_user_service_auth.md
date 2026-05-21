# Runbook: User Service Authentication Recovery

## Overview

This runbook covers recovery procedures for the user-service when authentication failures occur. The user-service is owned by the platform-team and handles all authentication and user management across the organization.

## Service Dependencies

The user-service depends on the following infrastructure:
- users-db (PostgreSQL database) - primary user data store
- session-cache (Redis cache) - session token storage
- notification-service (for password reset emails)
- api-gateway (upstream routing)

## Team Ownership

The platform-team is responsible for user-service operations. Primary on-call contact is Bob Martinez (Senior SRE, platform-team). Escalation goes to Carol Johnson (Engineering Manager, platform-team).

## Common Failure Scenarios

### Scenario 1: Session Cache Failure

**Symptoms:**
- Users unable to maintain logged-in state
- Spike in authentication requests hitting users-db directly
- Redis connection errors in user-service logs

**Diagnostic Steps:**

1. Check session-cache connectivity:
```bash
redis-cli -h session-cache.internal ping
```

2. Verify cache memory usage:
```bash
redis-cli -h session-cache.internal INFO memory
```

3. Check user-service logs for Redis errors:
```bash
kubectl logs -l app=user-service --tail=100 | grep -i redis
```

**Recovery Actions:**

1. IMMEDIATE: User-service falls back to database-only auth (degraded but functional)
2. SHORT-TERM: Restart session-cache pod if unresponsive
3. LONG-TERM: Implement session-cache clustering for high availability

**Escalation:**
Contact platform-team via #platform-ops Slack channel. If database load spikes above 80%, escalate to the database-team.

### Scenario 2: Database Connection Issues

**Symptoms:**
- Login failures across all services
- user-service health endpoint returns 503
- Connection pool exhaustion in users-db

**Diagnostic Steps:**

1. Check users-db connection count:
```sql
SELECT count(*) FROM pg_stat_activity WHERE datname = 'users';
```

2. Check user-service health:
```bash
curl https://user-service.internal/health
```

**Recovery Actions:**

1. Restart user-service deployment to release connections
2. If users-db is unresponsive, contact database-team for emergency restart
3. Enable read replica failover if primary is degraded

### Scenario 3: JWT Token Signing Key Rotation

**Symptoms:**
- Sudden spike in 401 errors across all downstream services
- payment-api and notification-service reporting auth failures
- Token validation errors in logs

**Diagnostic Steps:**

1. Verify current signing key matches across instances
2. Check recent deployments for key rotation changes
3. Confirm api-gateway is forwarding correct headers

**Recovery Actions:**

1. If accidental key rotation: rollback user-service to previous version
2. If planned rotation: ensure all services have the new public key
3. Clear session-cache to force re-authentication

## Monitoring and Alerts

- Prometheus metrics: authentication_requests_total, auth_failures_total
- Grafana dashboard: "User Service Auth Metrics"
- PagerDuty: Routes to platform-team on-call schedule

## Related Services

- **Downstream consumers**: payment-api, notification-service, billing-service, order-service
- **Infrastructure**: users-db, session-cache, api-gateway
- **Supporting teams**: platform-team, database-team

## Contact Information

- **Primary Owner**: platform-team (#platform-ops Slack)
- **On-Call**: Bob Martinez (PagerDuty)
- **Escalation**: Carol Johnson (Engineering Manager)

## Document Metadata

- **Last Updated**: 2024-11-15
- **Version**: 2.1
- **Author**: Bob Martinez (platform-team)
- **Review Cycle**: Monthly
