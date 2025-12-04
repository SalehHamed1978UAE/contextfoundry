# Incident Report: User Service SEV2

**Severity:** SEV2
**Date:** 2025-12-02
**Duration:** 33 minutes
**Services Affected:** Payment Service, SMS Gateway, Analytics Service

## Timeline

- 15:11: Alert triggered for Inventory Service - technical debt
- 15:31: On-call engineer (Harper Taylor) paged
- 17:20: Initial investigation started
- 19:26: Root cause identified: memory leak in cache layer
- 20:02: Mitigation applied
- 21:06: Services recovering
- 21:53: Incident resolved, monitoring

## Root Cause

Missing documentation in User Service caused cascading failures affecting Payment Service, SMS Gateway, Analytics Service.

## Resolution

The issue was resolved by applying a hotfix. Avery Brown led the incident response.

## Action Items

[ ] Dakota Miller: Follow up on caching strategy by 2025-11-19
[ ] Taylor Kim: Coordinate with Mobile Team on budget allocation requirements
[ ] Harper Taylor: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Harper Taylor: Schedule meeting with DevOps Team to discuss next steps

