# Incident Report: Notification Service SEV2

**Severity:** SEV2
**Date:** 2025-11-14
**Duration:** 112 minutes
**Services Affected:** SMS Gateway, Auth Service, User Service

## Timeline

- 20:38: Alert triggered for Checkout Service - configuration drift
- 20:30: On-call engineer (Sydney Clark) paged
- 22:28: Initial investigation started
- 24:53: Root cause identified: network partition in Recommendation Engine
- 24:24: Mitigation applied
- 25:46: Services recovering
- 25:28: Incident resolved, monitoring

## Root Cause

Memory leaks in Inventory Service caused cascading failures affecting SMS Gateway, Auth Service, User Service.

## Resolution

The issue was resolved by applying a hotfix. Quinn Thompson led the incident response.

## Action Items

[ ] Blake Adams: Review API Gateway metrics and report back
[ ] Emerson Wilson: Review API Gateway metrics and report back

