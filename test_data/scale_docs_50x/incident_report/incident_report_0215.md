# Incident Report: Checkout Service SEV1

**Severity:** SEV1
**Date:** 2025-09-19
**Duration:** 69 minutes
**Services Affected:** Order Service, API Gateway, Auth Service, Search Service

## Timeline

- 20:19: Alert triggered for Auth Service - deployment failures
- 20:31: On-call engineer (Avery Brown) paged
- 22:37: Initial investigation started
- 23:52: Root cause identified: memory leak in cache layer
- 23:30: Mitigation applied
- 24:50: Services recovering
- 26:45: Incident resolved, monitoring

## Root Cause

Data inconsistency in Shipping Service caused cascading failures affecting Order Service, API Gateway, Auth Service, Search Service.

## Resolution

The issue was resolved by restarting affected services. Reese Martin led the incident response.

## Action Items

[ ] Taylor Kim: Schedule meeting with Security Team to discuss next steps
[ ] Emerson Wilson: Follow up on documentation by 2025-11-10

