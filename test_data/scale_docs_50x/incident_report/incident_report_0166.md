# Incident Report: Inventory Service SEV2

**Severity:** SEV2
**Date:** 2025-08-26
**Duration:** 124 minutes
**Services Affected:** Shipping Service, User Service, Auth Service, Email Service

## Timeline

- 19:58: Alert triggered for Order Service - scaling bottlenecks
- 21:22: On-call engineer (Quinn Thompson) paged
- 22:06: Initial investigation started
- 22:07: Root cause identified: database connection pool exhaustion
- 24:56: Mitigation applied
- 24:52: Services recovering
- 24:10: Incident resolved, monitoring

## Root Cause

Memory leaks in SMS Gateway caused cascading failures affecting Shipping Service, User Service, Auth Service, Email Service.

## Resolution

The issue was resolved by rolling back the deployment. Quinn Thompson led the incident response.

## Action Items

[ ] Blake Adams: Follow up on Q4 planning by 2025-11-21
[ ] Blake Adams: Review Email Service metrics and report back
[ ] Blake Walker: Schedule meeting with QA Team to discuss next steps
[ ] Morgan Chen: Follow up on database sharding by 2025-11-28
[ ] Riley Garcia: Coordinate with Security Team on testing strategy requirements

