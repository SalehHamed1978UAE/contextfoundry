# Incident Report: Checkout Service SEV2

**Severity:** SEV2
**Date:** 2025-06-11
**Duration:** 24 minutes
**Services Affected:** SMS Gateway, User Service

## Timeline

- 11:47: Alert triggered for Auth Service - missing documentation
- 11:50: On-call engineer (Finley Moore) paged
- 11:27: Initial investigation started
- 13:36: Root cause identified: memory leak in cache layer
- 15:38: Mitigation applied
- 17:14: Services recovering
- 19:13: Incident resolved, monitoring

## Root Cause

Configuration drift in User Service caused cascading failures affecting SMS Gateway, User Service.

## Resolution

The issue was resolved by rolling back the deployment. Finley Moore led the incident response.

## Action Items

[ ] Blake Adams: Review Analytics Service metrics and report back
[ ] Parker Harris: Create proposal for CI/CD pipeline improvements

