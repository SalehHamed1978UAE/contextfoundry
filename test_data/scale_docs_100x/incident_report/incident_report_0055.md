# Incident Report: Payment Service SEV2

**Severity:** SEV2
**Date:** 2025-10-25
**Duration:** 150 minutes
**Services Affected:** Order Service

## Timeline

- 09:35: Alert triggered for Search Service - error rates increasing
- 09:32: On-call engineer (Harper Taylor) paged
- 10:55: Initial investigation started
- 11:01: Root cause identified: resource limit reached
- 11:35: Mitigation applied
- 13:13: Services recovering
- 15:19: Incident resolved, monitoring

## Root Cause

Configuration drift in Auth Service caused cascading failures affecting Order Service.

## Resolution

The issue was resolved by applying a hotfix. Finley Moore led the incident response.

## Action Items

[ ] Morgan Chen: Follow up on capacity planning by 2025-11-30
[ ] Blake Adams: Coordinate with Infrastructure Team on vendor evaluation requirements
[ ] Blake Adams: Follow up on budget allocation by 2025-11-10
[ ] Finley Moore: Review Payment Service metrics and report back
[ ] Finley Moore: Coordinate with SRE Team on API versioning requirements

