# Incident Report: Inventory Service SEV2

**Severity:** SEV2
**Date:** 2025-11-26
**Duration:** 124 minutes
**Services Affected:** Recommendation Engine, Email Service

## Timeline

- 13:39: Alert triggered for Checkout Service - scaling bottlenecks
- 13:53: On-call engineer (Jamie Anderson) paged
- 15:56: Initial investigation started
- 16:34: Root cause identified: failed deployment rollback
- 16:29: Mitigation applied
- 16:08: Services recovering
- 18:53: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Notification Service caused cascading failures affecting Recommendation Engine, Email Service.

## Resolution

The issue was resolved by rolling back the deployment. Alex Rivera led the incident response.

## Action Items

[ ] Jordan Lee: Coordinate with API Team on testing strategy requirements
[ ] Emerson Wilson: Schedule meeting with Data Team to discuss next steps

