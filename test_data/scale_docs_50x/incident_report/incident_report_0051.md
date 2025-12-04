# Incident Report: Fraud Detection SEV1

**Severity:** SEV1
**Date:** 2025-11-25
**Duration:** 105 minutes
**Services Affected:** Cache Layer, Shipping Service

## Timeline

- 13:46: Alert triggered for Shipping Service - scaling bottlenecks
- 13:34: On-call engineer (Sydney Clark) paged
- 15:01: Initial investigation started
- 15:32: Root cause identified: failed deployment rollback
- 17:44: Mitigation applied
- 19:55: Services recovering
- 19:12: Incident resolved, monitoring

## Root Cause

Resource exhaustion in User Service caused cascading failures affecting Cache Layer, Shipping Service.

## Resolution

The issue was resolved by increasing resource limits. Drew Patel led the incident response.

## Action Items

[ ] Sage Robinson: Follow up on technical debt by 2025-11-05
[ ] Harper Taylor: Follow up on hiring priorities by 2025-11-25

