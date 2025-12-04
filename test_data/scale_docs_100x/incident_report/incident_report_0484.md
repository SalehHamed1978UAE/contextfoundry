# Incident Report: User Service SEV3

**Severity:** SEV3
**Date:** 2025-09-09
**Duration:** 154 minutes
**Services Affected:** Order Service

## Timeline

- 08:49: Alert triggered for Order Service - data inconsistency
- 08:15: On-call engineer (Sage Robinson) paged
- 10:15: Initial investigation started
- 11:05: Root cause identified: network partition in Search Service
- 12:23: Mitigation applied
- 12:33: Services recovering
- 13:26: Incident resolved, monitoring

## Root Cause

Latency issues in User Service caused cascading failures affecting Order Service.

## Resolution

The issue was resolved by increasing resource limits. Riley Garcia led the incident response.

## Action Items

[ ] Riley Garcia: Review Auth Service metrics and report back
[ ] Blake Walker: Create proposal for cost reduction improvements
[ ] Alex Rivera: Follow up on API versioning by 2025-11-21
[ ] Reese Martin: Review User Service metrics and report back

