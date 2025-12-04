# Incident Report: Shipping Service SEV3

**Severity:** SEV3
**Date:** 2025-09-10
**Duration:** 34 minutes
**Services Affected:** User Service, Payment Service, Cache Layer, Email Service

## Timeline

- 18:01: Alert triggered for Search Service - error rates increasing
- 18:40: On-call engineer (Alex Rivera) paged
- 20:39: Initial investigation started
- 22:15: Root cause identified: resource limit reached
- 24:40: Mitigation applied
- 26:05: Services recovering
- 26:19: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in API Gateway caused cascading failures affecting User Service, Payment Service, Cache Layer, Email Service.

## Resolution

The issue was resolved by restarting affected services. Sage Robinson led the incident response.

## Action Items

[ ] Riley Garcia: Create proposal for API versioning improvements
[ ] Riley Garcia: Create proposal for technical debt improvements
[ ] Parker Harris: Review Inventory Service metrics and report back

