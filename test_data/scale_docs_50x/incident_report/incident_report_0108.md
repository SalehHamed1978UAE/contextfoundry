# Incident Report: SMS Gateway SEV2

**Severity:** SEV2
**Date:** 2025-08-12
**Duration:** 160 minutes
**Services Affected:** Inventory Service, Email Service

## Timeline

- 14:47: Alert triggered for Shipping Service - resource exhaustion
- 14:21: On-call engineer (Jordan Lee) paged
- 15:43: Initial investigation started
- 17:51: Root cause identified: memory leak in cache layer
- 18:34: Mitigation applied
- 20:30: Services recovering
- 22:12: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Inventory Service caused cascading failures affecting Inventory Service, Email Service.

## Resolution

The issue was resolved by applying a hotfix. Morgan Chen led the incident response.

## Action Items

[ ] Reese Martin: Review User Service metrics and report back
[ ] Riley Garcia: Review Cache Layer metrics and report back
[ ] Blake Adams: Schedule meeting with Data Team to discuss next steps
[ ] Reese Martin: Coordinate with API Team on compliance requirements requirements
[ ] Casey Martinez: Review SMS Gateway metrics and report back

