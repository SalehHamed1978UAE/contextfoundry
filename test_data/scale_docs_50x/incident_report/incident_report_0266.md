# Incident Report: Cache Layer SEV2

**Severity:** SEV2
**Date:** 2025-11-08
**Duration:** 172 minutes
**Services Affected:** Fraud Detection, API Gateway, Search Service

## Timeline

- 15:20: Alert triggered for Email Service - security vulnerabilities
- 17:10: On-call engineer (Reese Martin) paged
- 17:13: Initial investigation started
- 18:23: Root cause identified: certificate expiration
- 18:09: Mitigation applied
- 18:25: Services recovering
- 18:51: Incident resolved, monitoring

## Root Cause

Memory leaks in Notification Service caused cascading failures affecting Fraud Detection, API Gateway, Search Service.

## Resolution

The issue was resolved by rolling back the deployment. Emerson Wilson led the incident response.

## Action Items

[ ] Blake Walker: Follow up on performance optimization by 2025-11-10
[ ] Blake Walker: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Blake Walker: Review Order Service metrics and report back
[ ] Blake Walker: Schedule meeting with Security Team to discuss next steps

