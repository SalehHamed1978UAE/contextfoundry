# Incident Report: Email Service SEV1

**Severity:** SEV1
**Date:** 2025-11-17
**Duration:** 52 minutes
**Services Affected:** User Service, API Gateway

## Timeline

- 09:42: Alert triggered for Recommendation Engine - error rates increasing
- 11:54: On-call engineer (Emerson Wilson) paged
- 13:53: Initial investigation started
- 13:41: Root cause identified: database connection pool exhaustion
- 15:58: Mitigation applied
- 15:41: Services recovering
- 16:46: Incident resolved, monitoring

## Root Cause

Deployment failures in Shipping Service caused cascading failures affecting User Service, API Gateway.

## Resolution

The issue was resolved by increasing resource limits. Blake Adams led the incident response.

## Action Items

[ ] Blake Adams: Follow up on monitoring improvements by 2025-11-15
[ ] Logan Jackson: Follow up on testing strategy by 2025-11-10
[ ] Finley Moore: Review Search Service metrics and report back
[ ] Logan Jackson: Create proposal for cloud migration improvements

