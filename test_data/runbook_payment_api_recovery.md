# Runbook: Payment API Recovery Procedures

## Overview

This runbook covers recovery procedures for the payment-api service when it experiences degraded performance or outages.

The payment-api is owned by the payments-team and is a critical service for payment processing.

## Service Dependencies

The payment-api service depends on the following infrastructure:
- payments-db (PostgreSQL database)
- api-cache (Redis cache)
- user-service (for authentication)
- notification-service (for payment confirmations)

## Common Failure Scenarios

### Scenario 1: Database Connection Pool Exhaustion

**Symptoms:**
- High latency on payment endpoints
- Connection timeout errors in logs
- Database refusing new connections

**Diagnostic Steps:**

1. Check current database connections:
```sql
SELECT count(*) FROM pg_stat_activity WHERE datname = 'payments';
```

2. Identify long-running queries:
```sql
SELECT pid, query, state, query_start
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;
```

**Recovery Actions:**

1. IMMEDIATE: Restart the payment-api service to release stuck connections
2. SHORT-TERM: Increase max_connections on payments-db from 100 to 200
3. LONG-TERM: Fix connection leaks in application code

**Escalation:**
Contact platform-team if database restart is required.

### Scenario 2: Cache Failure

**Symptoms:**
- Increased latency due to cache misses
- High database load
- Redis connection errors

**Diagnostic Steps:**

1. Check Redis connectivity:
```bash
redis-cli -h api-cache ping
```

2. Check memory usage:
```bash
redis-cli -h api-cache INFO memory
```

**Recovery Actions:**

1. Payment API can operate without cache (degraded performance)
2. Verify circuit breaker is active
3. Coordinate with platform-team to restore cache

### Scenario 3: Cascading Failures from user-service

**Symptoms:**
- Authentication failures
- Payment API timing out on user verification
- Increased error rates

**Diagnostic Steps:**

1. Check user-service health endpoint:
```bash
curl https://user-service.internal/health
```

2. Review payment-api circuit breaker status

**Recovery Actions:**

1. Circuit breaker should prevent cascading failure
2. If circuit breaker not active, enable manual failover
3. Coordinate with auth-team to resolve user-service issues

## Monitoring and Alerts

The payment-api has the following monitoring:
- Prometheus metrics at /metrics endpoint
- Grafana dashboard: "Payment API Operations"
- PagerDuty alert routing to payments-team

## Rollback Procedures

If a recent deployment caused the issue:

1. Check deployment timestamp against incident start time
2. Rollback using: `kubectl rollout undo deployment/payment-api`
3. Verify service recovery
4. Notify devops-team of rollback

## Post-Incident Actions

After resolving the incident:

1. Update incident report in Jira
2. Schedule postmortem with payments-team
3. Add lessons learned to this runbook
4. Update monitoring if gaps identified

## Related Services

- **Upstream dependencies**: user-service, notification-service
- **Downstream dependencies**: payment-processor, billing-service
- **Infrastructure**: payments-db, api-cache, api-gateway

## Contact Information

- **Primary Owner**: payments-team (#payments Slack channel)
- **On-Call**: PagerDuty Schedule Payments
- **Escalation**: Platform SRE (via platform-team)

## Document Metadata

- **Last Updated**: 2024-12-02
- **Version**: 1.2
- **Author**: Alice Chen (payments-team)
- **Review Cycle**: Quarterly
