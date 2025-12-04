# Incident Report: User Service SEV1

**Severity:** SEV1
**Date:** 2025-12-03
**Duration:** 105 minutes
**Services Affected:** Checkout Service

## Timeline

- 21:03: Alert triggered for Cache Layer - security vulnerabilities
- 22:04: On-call engineer (Dakota Miller) paged
- 22:55: Initial investigation started
- 24:13: Root cause identified: certificate expiration
- 24:06: Mitigation applied
- 25:42: Services recovering
- 27:21: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Email Service caused cascading failures affecting Checkout Service.

## Resolution

The issue was resolved by restarting affected services. Casey Martinez led the incident response.

## Action Items

[ ] Quinn Thompson: Follow up on scalability planning by 2025-11-28
[ ] Taylor Kim: Review API Gateway metrics and report back

