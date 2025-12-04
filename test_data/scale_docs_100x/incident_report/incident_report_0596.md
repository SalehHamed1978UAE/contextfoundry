# Incident Report: Analytics Service SEV1

**Severity:** SEV1
**Date:** 2025-11-03
**Duration:** 107 minutes
**Services Affected:** Inventory Service, User Service, Auth Service, Analytics Service

## Timeline

- 10:10: Alert triggered for Checkout Service - error rates increasing
- 12:40: On-call engineer (Finley Moore) paged
- 12:36: Initial investigation started
- 14:18: Root cause identified: database connection pool exhaustion
- 14:21: Mitigation applied
- 14:14: Services recovering
- 15:43: Incident resolved, monitoring

## Root Cause

Configuration drift in Email Service caused cascading failures affecting Inventory Service, User Service, Auth Service, Analytics Service.

## Resolution

The issue was resolved by increasing resource limits. Kendall Thomas led the incident response.

## Action Items

[ ] Avery Brown: Follow up on observability stack by 2025-11-20
[ ] Finley Moore: Follow up on microservices refactoring by 2025-11-17
[ ] Tatum Lewis: Follow up on capacity planning by 2025-11-24
[ ] Reese Martin: Review User Service metrics and report back

