# Incident Report: Shipping Service SEV2

**Severity:** SEV2
**Date:** 2025-07-02
**Duration:** 72 minutes
**Services Affected:** Recommendation Engine

## Timeline

- 13:42: Alert triggered for Order Service - timeout errors
- 14:50: On-call engineer (Finley Moore) paged
- 15:19: Initial investigation started
- 16:04: Root cause identified: memory leak in cache layer
- 18:07: Mitigation applied
- 19:20: Services recovering
- 20:43: Incident resolved, monitoring

## Root Cause

Missing documentation in Notification Service caused cascading failures affecting Recommendation Engine.

## Resolution

The issue was resolved by restarting affected services. Reese Martin led the incident response.

## Action Items

[ ] Blake Walker: Schedule meeting with Growth Team to discuss next steps
[ ] Blake Walker: Coordinate with QA Team on capacity planning requirements
[ ] Dakota Miller: Schedule meeting with Platform Team to discuss next steps

