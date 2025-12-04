# Incident Report: Search Service SEV2

**Severity:** SEV2
**Date:** 2025-08-30
**Duration:** 85 minutes
**Services Affected:** Search Service, API Gateway, Notification Service, Order Service

## Timeline

- 12:19: Alert triggered for User Service - resource exhaustion
- 12:25: On-call engineer (Tatum Lewis) paged
- 14:54: Initial investigation started
- 14:41: Root cause identified: certificate expiration
- 16:03: Mitigation applied
- 16:37: Services recovering
- 17:37: Incident resolved, monitoring

## Root Cause

Memory leaks in Shipping Service caused cascading failures affecting Search Service, API Gateway, Notification Service, Order Service.

## Resolution

The issue was resolved by rolling back the deployment. Parker Harris led the incident response.

## Action Items

[ ] Casey Martinez: Follow up on cloud migration by 2025-11-14
[ ] Quinn Thompson: Follow up on testing strategy by 2025-11-12

