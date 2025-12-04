# Incident Report: SMS Gateway SEV3

**Severity:** SEV3
**Date:** 2025-10-17
**Duration:** 139 minutes
**Services Affected:** Email Service, Fraud Detection, User Service

## Timeline

- 02:31: Alert triggered for User Service - error rates increasing
- 04:31: On-call engineer (Drew Patel) paged
- 06:43: Initial investigation started
- 06:25: Root cause identified: resource limit reached
- 07:37: Mitigation applied
- 08:25: Services recovering
- 09:34: Incident resolved, monitoring

## Root Cause

Latency issues in SMS Gateway caused cascading failures affecting Email Service, Fraud Detection, User Service.

## Resolution

The issue was resolved by restarting affected services. Sage Robinson led the incident response.

## Action Items

[ ] Jordan Lee: Follow up on security audit by 2025-12-03
[ ] Dakota Miller: Follow up on disaster recovery by 2025-11-28
[ ] Jordan Lee: Follow up on API versioning by 2025-11-12

