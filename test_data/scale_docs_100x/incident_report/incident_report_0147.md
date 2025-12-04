# Incident Report: Checkout Service SEV2

**Severity:** SEV2
**Date:** 2025-09-19
**Duration:** 125 minutes
**Services Affected:** SMS Gateway, User Service, Cache Layer

## Timeline

- 18:31: Alert triggered for Order Service - memory leaks
- 18:05: On-call engineer (Blake Walker) paged
- 18:47: Initial investigation started
- 19:49: Root cause identified: failed deployment rollback
- 21:30: Mitigation applied
- 23:44: Services recovering
- 24:07: Incident resolved, monitoring

## Root Cause

Technical debt in Notification Service caused cascading failures affecting SMS Gateway, User Service, Cache Layer.

## Resolution

The issue was resolved by increasing resource limits. Jamie Anderson led the incident response.

## Action Items

[ ] Parker Harris: Follow up on budget allocation by 2025-12-03
[ ] Tatum Lewis: Create proposal for observability stack improvements
[ ] Dakota Miller: Review Payment Service metrics and report back

