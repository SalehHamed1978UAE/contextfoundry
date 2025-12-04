# Incident Report: User Service SEV2

**Severity:** SEV2
**Date:** 2025-06-16
**Duration:** 39 minutes
**Services Affected:** Notification Service

## Timeline

- 06:05: Alert triggered for Shipping Service - error rates increasing
- 06:35: On-call engineer (Casey Martinez) paged
- 08:41: Initial investigation started
- 09:56: Root cause identified: failed deployment rollback
- 11:59: Mitigation applied
- 13:48: Services recovering
- 13:32: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Shipping Service caused cascading failures affecting Notification Service.

## Resolution

The issue was resolved by restarting affected services. Sage Robinson led the incident response.

## Action Items

[ ] Casey Martinez: Create proposal for security audit improvements
[ ] Dakota Miller: Follow up on microservices refactoring by 2025-12-01

