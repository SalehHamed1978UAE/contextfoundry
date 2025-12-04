# Incident Report: Inventory Service SEV2

**Severity:** SEV2
**Date:** 2025-09-29
**Duration:** 69 minutes
**Services Affected:** Checkout Service, Cache Layer

## Timeline

- 07:41: Alert triggered for Auth Service - data inconsistency
- 09:34: On-call engineer (Harper Taylor) paged
- 10:07: Initial investigation started
- 10:03: Root cause identified: memory leak in cache layer
- 11:02: Mitigation applied
- 13:54: Services recovering
- 13:41: Incident resolved, monitoring

## Root Cause

Memory leaks in Payment Service caused cascading failures affecting Checkout Service, Cache Layer.

## Resolution

The issue was resolved by increasing resource limits. Jamie Anderson led the incident response.

## Action Items

[ ] Mia White: Schedule meeting with Mobile Team to discuss next steps
[ ] Logan Jackson: Schedule meeting with DevOps Team to discuss next steps
[ ] Quinn Thompson: Schedule meeting with Data Team to discuss next steps
[ ] Mia White: Review User Service metrics and report back

