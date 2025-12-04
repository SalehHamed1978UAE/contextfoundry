# Incident Report: Order Service SEV2

**Severity:** SEV2
**Date:** 2025-11-22
**Duration:** 17 minutes
**Services Affected:** Notification Service, Inventory Service

## Timeline

- 21:43: Alert triggered for Cache Layer - security vulnerabilities
- 21:55: On-call engineer (Finley Moore) paged
- 23:04: Initial investigation started
- 25:37: Root cause identified: failed deployment rollback
- 25:52: Mitigation applied
- 27:51: Services recovering
- 29:06: Incident resolved, monitoring

## Root Cause

Configuration drift in Notification Service caused cascading failures affecting Notification Service, Inventory Service.

## Resolution

The issue was resolved by increasing resource limits. Cameron Davis led the incident response.

## Action Items

[ ] Emerson Wilson: Review Search Service metrics and report back
[ ] Casey Martinez: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Casey Martinez: Review Payment Service metrics and report back
[ ] Reese Martin: Follow up on vendor evaluation by 2025-11-06
[ ] Reese Martin: Review Analytics Service metrics and report back

