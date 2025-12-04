# Incident Report: Notification Service SEV3

**Severity:** SEV3
**Date:** 2025-08-29
**Duration:** 151 minutes
**Services Affected:** SMS Gateway, Search Service, Recommendation Engine

## Timeline

- 08:46: Alert triggered for API Gateway - timeout errors
- 08:43: On-call engineer (Parker Harris) paged
- 08:56: Initial investigation started
- 08:42: Root cause identified: certificate expiration
- 09:53: Mitigation applied
- 09:54: Services recovering
- 11:51: Incident resolved, monitoring

## Root Cause

Timeout errors in Notification Service caused cascading failures affecting SMS Gateway, Search Service, Recommendation Engine.

## Resolution

The issue was resolved by increasing resource limits. Jamie Anderson led the incident response.

## Action Items

[ ] Avery Brown: Schedule meeting with API Team to discuss next steps
[ ] Parker Harris: Create proposal for cloud migration improvements
[ ] Morgan Chen: Follow up on observability stack by 2025-11-05
[ ] Mia White: Coordinate with Security Team on hiring priorities requirements
[ ] Casey Martinez: Review Inventory Service metrics and report back

