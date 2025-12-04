# Incident Report: User Service SEV2

**Severity:** SEV2
**Date:** 2025-07-27
**Duration:** 45 minutes
**Services Affected:** Auth Service

## Timeline

- 11:33: Alert triggered for Auth Service - memory leaks
- 12:08: On-call engineer (Riley Garcia) paged
- 12:45: Initial investigation started
- 14:12: Root cause identified: failed deployment rollback
- 15:20: Mitigation applied
- 16:21: Services recovering
- 18:32: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Order Service caused cascading failures affecting Auth Service.

## Resolution

The issue was resolved by restarting affected services. Jordan Lee led the incident response.

## Action Items

[ ] Casey Martinez: Schedule meeting with Security Team to discuss next steps
[ ] Morgan Chen: Follow up on performance optimization by 2025-11-29
[ ] Jordan Lee: Schedule meeting with Backend Team to discuss next steps
[ ] Riley Garcia: Review Payment Service metrics and report back

