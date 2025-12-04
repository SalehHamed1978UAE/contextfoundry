# Incident Report: API Gateway SEV2

**Severity:** SEV2
**Date:** 2025-11-14
**Duration:** 107 minutes
**Services Affected:** User Service

## Timeline

- 14:40: Alert triggered for API Gateway - configuration drift
- 16:42: On-call engineer (Jordan Lee) paged
- 17:07: Initial investigation started
- 19:29: Root cause identified: database connection pool exhaustion
- 19:19: Mitigation applied
- 19:53: Services recovering
- 21:24: Incident resolved, monitoring

## Root Cause

Data inconsistency in Checkout Service caused cascading failures affecting User Service.

## Resolution

The issue was resolved by restarting affected services. Riley Garcia led the incident response.

## Action Items

[ ] Avery Brown: Create proposal for caching strategy improvements
[ ] Sage Robinson: Create proposal for Q4 planning improvements
[ ] Parker Harris: Coordinate with Infrastructure Team on database sharding requirements
[ ] Dakota Miller: Schedule meeting with Data Team to discuss next steps
[ ] Dakota Miller: Review Inventory Service metrics and report back

