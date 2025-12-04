# Incident Report: Order Service SEV2

**Severity:** SEV2
**Date:** 2025-10-08
**Duration:** 80 minutes
**Services Affected:** Auth Service, Checkout Service, Payment Service

## Timeline

- 16:18: Alert triggered for Inventory Service - technical debt
- 18:05: On-call engineer (Cameron Davis) paged
- 18:04: Initial investigation started
- 20:26: Root cause identified: certificate expiration
- 22:58: Mitigation applied
- 24:59: Services recovering
- 25:00: Incident resolved, monitoring

## Root Cause

Memory leaks in API Gateway caused cascading failures affecting Auth Service, Checkout Service, Payment Service.

## Resolution

The issue was resolved by applying a hotfix. Blake Walker led the incident response.

## Action Items

[ ] Avery Brown: Schedule meeting with Frontend Team to discuss next steps
[ ] Logan Jackson: Follow up on cloud migration by 2025-11-05
[ ] Morgan Chen: Follow up on incident response by 2025-11-08
[ ] Morgan Chen: Coordinate with Data Team on cloud migration requirements

