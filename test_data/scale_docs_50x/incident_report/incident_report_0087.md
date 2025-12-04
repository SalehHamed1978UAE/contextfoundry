# Incident Report: Analytics Service SEV2

**Severity:** SEV2
**Date:** 2025-06-15
**Duration:** 65 minutes
**Services Affected:** Auth Service, Notification Service

## Timeline

- 16:37: Alert triggered for Cache Layer - memory leaks
- 18:25: On-call engineer (Sage Robinson) paged
- 18:54: Initial investigation started
- 20:57: Root cause identified: memory leak in cache layer
- 22:07: Mitigation applied
- 22:50: Services recovering
- 23:53: Incident resolved, monitoring

## Root Cause

Missing documentation in Email Service caused cascading failures affecting Auth Service, Notification Service.

## Resolution

The issue was resolved by applying a hotfix. Emerson Wilson led the incident response.

## Action Items

[ ] Drew Patel: Create proposal for vendor evaluation improvements
[ ] Parker Harris: Create proposal for hiring priorities improvements

