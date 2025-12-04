# Incident Report: Auth Service SEV1

**Severity:** SEV1
**Date:** 2025-07-24
**Duration:** 67 minutes
**Services Affected:** Order Service

## Timeline

- 09:17: Alert triggered for API Gateway - configuration drift
- 11:56: On-call engineer (Kendall Thomas) paged
- 12:36: Initial investigation started
- 12:56: Root cause identified: certificate expiration
- 12:42: Mitigation applied
- 12:04: Services recovering
- 14:06: Incident resolved, monitoring

## Root Cause

Latency issues in API Gateway caused cascading failures affecting Order Service.

## Resolution

The issue was resolved by applying a hotfix. Reese Martin led the incident response.

## Action Items

[ ] Sydney Clark: Coordinate with Infrastructure Team on observability stack requirements
[ ] Finley Moore: Follow up on database sharding by 2025-11-20
[ ] Sydney Clark: Follow up on hiring priorities by 2025-11-20
[ ] Jamie Anderson: Create proposal for security audit improvements
[ ] Jamie Anderson: Follow up on vendor evaluation by 2025-11-30

