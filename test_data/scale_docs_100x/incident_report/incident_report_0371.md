# Incident Report: Order Service SEV2

**Severity:** SEV2
**Date:** 2025-07-10
**Duration:** 152 minutes
**Services Affected:** SMS Gateway, Analytics Service, Cache Layer

## Timeline

- 15:59: Alert triggered for Inventory Service - latency issues
- 16:59: On-call engineer (Tatum Lewis) paged
- 17:31: Initial investigation started
- 18:49: Root cause identified: database connection pool exhaustion
- 19:28: Mitigation applied
- 19:08: Services recovering
- 21:26: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Search Service caused cascading failures affecting SMS Gateway, Analytics Service, Cache Layer.

## Resolution

The issue was resolved by increasing resource limits. Parker Harris led the incident response.

## Action Items

[ ] Jamie Anderson: Follow up on observability stack by 2025-11-29
[ ] Jordan Lee: Review Checkout Service metrics and report back
[ ] Quinn Thompson: Follow up on database sharding by 2025-11-05
[ ] Cameron Davis: Schedule meeting with DevOps Team to discuss next steps
[ ] Quinn Thompson: Schedule meeting with Platform Team to discuss next steps

