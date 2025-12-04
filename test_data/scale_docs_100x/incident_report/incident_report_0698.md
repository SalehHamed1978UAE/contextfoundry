# Incident Report: Order Service SEV1

**Severity:** SEV1
**Date:** 2025-07-26
**Duration:** 24 minutes
**Services Affected:** Order Service, Fraud Detection, Recommendation Engine

## Timeline

- 09:23: Alert triggered for Email Service - scaling bottlenecks
- 10:49: On-call engineer (Kendall Thomas) paged
- 12:36: Initial investigation started
- 14:27: Root cause identified: database connection pool exhaustion
- 14:51: Mitigation applied
- 14:44: Services recovering
- 16:57: Incident resolved, monitoring

## Root Cause

Missing documentation in Email Service caused cascading failures affecting Order Service, Fraud Detection, Recommendation Engine.

## Resolution

The issue was resolved by increasing resource limits. Sage Robinson led the incident response.

## Action Items

[ ] Finley Moore: Review Shipping Service metrics and report back
[ ] Parker Harris: Create proposal for capacity planning improvements
[ ] Emerson Wilson: Schedule meeting with Data Team to discuss next steps
[ ] Finley Moore: Create proposal for vendor evaluation improvements
[ ] Finley Moore: Follow up on compliance requirements by 2025-11-30

