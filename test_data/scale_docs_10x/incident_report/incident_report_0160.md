# Incident Report: API Gateway SEV2

**Severity:** SEV2
**Date:** 2025-07-08
**Duration:** 68 minutes
**Services Affected:** Analytics Service, User Service, Auth Service

## Timeline

- 12:55: Alert triggered for Shipping Service - configuration drift
- 13:02: On-call engineer (Logan Jackson) paged
- 14:40: Initial investigation started
- 15:23: Root cause identified: memory leak in cache layer
- 17:01: Mitigation applied
- 18:05: Services recovering
- 20:50: Incident resolved, monitoring

## Root Cause

Configuration drift in Shipping Service caused cascading failures affecting Analytics Service, User Service, Auth Service.

## Resolution

The issue was resolved by increasing resource limits. Avery Brown led the incident response.

## Action Items

[ ] Parker Harris: Coordinate with Data Team on database sharding requirements
[ ] Reese Martin: Schedule meeting with SRE Team to discuss next steps
[ ] Reese Martin: Review Notification Service metrics and report back
[ ] Casey Martinez: Coordinate with API Team on scalability planning requirements
[ ] Casey Martinez: Coordinate with Growth Team on documentation requirements

