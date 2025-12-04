# Incident Report: User Service SEV1

**Severity:** SEV1
**Date:** 2025-08-09
**Duration:** 172 minutes
**Services Affected:** Cache Layer, Notification Service, Inventory Service, Recommendation Engine

## Timeline

- 04:46: Alert triggered for Checkout Service - latency issues
- 04:32: On-call engineer (Casey Martinez) paged
- 04:26: Initial investigation started
- 04:05: Root cause identified: failed deployment rollback
- 05:02: Mitigation applied
- 06:58: Services recovering
- 08:45: Incident resolved, monitoring

## Root Cause

Memory leaks in Notification Service caused cascading failures affecting Cache Layer, Notification Service, Inventory Service, Recommendation Engine.

## Resolution

The issue was resolved by rolling back the deployment. Riley Garcia led the incident response.

## Action Items

[ ] Logan Jackson: Follow up on hiring priorities by 2025-11-12
[ ] Cameron Davis: Coordinate with Platform Team on budget allocation requirements
[ ] Logan Jackson: Coordinate with QA Team on monitoring improvements requirements
[ ] Cameron Davis: Create proposal for CI/CD pipeline improvements
[ ] Logan Jackson: Schedule meeting with Infrastructure Team to discuss next steps

