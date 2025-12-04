# Incident Report: Recommendation Engine SEV1

**Severity:** SEV1
**Date:** 2025-11-27
**Duration:** 144 minutes
**Services Affected:** Search Service, Payment Service, Inventory Service

## Timeline

- 16:03: Alert triggered for Inventory Service - scaling bottlenecks
- 16:05: On-call engineer (Harper Taylor) paged
- 17:16: Initial investigation started
- 19:48: Root cause identified: certificate expiration
- 20:22: Mitigation applied
- 21:50: Services recovering
- 21:16: Incident resolved, monitoring

## Root Cause

Memory leaks in Cache Layer caused cascading failures affecting Search Service, Payment Service, Inventory Service.

## Resolution

The issue was resolved by restarting affected services. Avery Brown led the incident response.

## Action Items

[ ] Kendall Thomas: Review Checkout Service metrics and report back
[ ] Kendall Thomas: Follow up on API versioning by 2025-11-07
[ ] Reese Martin: Coordinate with Platform Team on compliance requirements requirements
[ ] Logan Jackson: Coordinate with QA Team on documentation requirements
[ ] Cameron Davis: Coordinate with API Team on microservices refactoring requirements

