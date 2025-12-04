# Incident Report: Shipping Service SEV2

**Severity:** SEV2
**Date:** 2025-11-15
**Duration:** 69 minutes
**Services Affected:** Notification Service

## Timeline

- 15:19: Alert triggered for Checkout Service - scaling bottlenecks
- 16:38: On-call engineer (Avery Brown) paged
- 18:20: Initial investigation started
- 19:48: Root cause identified: failed deployment rollback
- 21:53: Mitigation applied
- 21:19: Services recovering
- 23:58: Incident resolved, monitoring

## Root Cause

Timeout errors in Payment Service caused cascading failures affecting Notification Service.

## Resolution

The issue was resolved by rolling back the deployment. Drew Patel led the incident response.

## Action Items

[ ] Dakota Miller: Review SMS Gateway metrics and report back
[ ] Finley Moore: Schedule meeting with Mobile Team to discuss next steps
[ ] Blake Adams: Coordinate with Backend Team on scalability planning requirements
[ ] Blake Adams: Review Shipping Service metrics and report back

