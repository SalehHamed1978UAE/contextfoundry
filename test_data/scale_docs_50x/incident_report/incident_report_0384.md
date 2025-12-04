# Incident Report: Payment Service SEV2

**Severity:** SEV2
**Date:** 2025-06-15
**Duration:** 82 minutes
**Services Affected:** Notification Service, Order Service

## Timeline

- 19:02: Alert triggered for Cache Layer - security vulnerabilities
- 20:38: On-call engineer (Jamie Anderson) paged
- 20:05: Initial investigation started
- 22:15: Root cause identified: memory leak in cache layer
- 22:07: Mitigation applied
- 22:25: Services recovering
- 24:05: Incident resolved, monitoring

## Root Cause

Missing documentation in Search Service caused cascading failures affecting Notification Service, Order Service.

## Resolution

The issue was resolved by restarting affected services. Kendall Thomas led the incident response.

## Action Items

[ ] Tatum Lewis: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Harper Taylor: Coordinate with Frontend Team on capacity planning requirements
[ ] Cameron Davis: Coordinate with QA Team on cloud migration requirements
[ ] Morgan Chen: Follow up on disaster recovery by 2025-11-04
[ ] Tatum Lewis: Follow up on performance optimization by 2025-11-30

