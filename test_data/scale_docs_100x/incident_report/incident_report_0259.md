# Incident Report: Search Service SEV3

**Severity:** SEV3
**Date:** 2025-08-16
**Duration:** 179 minutes
**Services Affected:** Order Service, Notification Service, Inventory Service

## Timeline

- 08:32: Alert triggered for Recommendation Engine - data inconsistency
- 10:23: On-call engineer (Tatum Lewis) paged
- 10:01: Initial investigation started
- 10:21: Root cause identified: memory leak in cache layer
- 12:29: Mitigation applied
- 13:59: Services recovering
- 15:03: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Payment Service caused cascading failures affecting Order Service, Notification Service, Inventory Service.

## Resolution

The issue was resolved by applying a hotfix. Parker Harris led the incident response.

## Action Items

[ ] Taylor Kim: Coordinate with QA Team on API versioning requirements
[ ] Kendall Thomas: Review Order Service metrics and report back
[ ] Taylor Kim: Create proposal for observability stack improvements
[ ] Reese Martin: Review Search Service metrics and report back

