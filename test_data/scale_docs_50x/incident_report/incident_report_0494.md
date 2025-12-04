# Incident Report: Checkout Service SEV2

**Severity:** SEV2
**Date:** 2025-11-24
**Duration:** 56 minutes
**Services Affected:** Inventory Service, Shipping Service, Order Service

## Timeline

- 10:40: Alert triggered for Checkout Service - data inconsistency
- 12:15: On-call engineer (Emerson Wilson) paged
- 12:56: Initial investigation started
- 14:00: Root cause identified: database connection pool exhaustion
- 14:22: Mitigation applied
- 15:02: Services recovering
- 15:27: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Auth Service caused cascading failures affecting Inventory Service, Shipping Service, Order Service.

## Resolution

The issue was resolved by restarting affected services. Blake Walker led the incident response.

## Action Items

[ ] Logan Jackson: Schedule meeting with API Team to discuss next steps
[ ] Taylor Kim: Coordinate with Data Team on testing strategy requirements
[ ] Parker Harris: Follow up on budget allocation by 2025-11-24

