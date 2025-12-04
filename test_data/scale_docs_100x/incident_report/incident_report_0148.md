# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-08-09
**Duration:** 81 minutes
**Services Affected:** SMS Gateway, Cache Layer, Payment Service, User Service

## Timeline

- 04:10: Alert triggered for Search Service - latency issues
- 06:06: On-call engineer (Casey Martinez) paged
- 08:54: Initial investigation started
- 08:32: Root cause identified: memory leak in cache layer
- 09:59: Mitigation applied
- 10:40: Services recovering
- 10:46: Incident resolved, monitoring

## Root Cause

Data inconsistency in Auth Service caused cascading failures affecting SMS Gateway, Cache Layer, Payment Service, User Service.

## Resolution

The issue was resolved by applying a hotfix. Jordan Lee led the incident response.

## Action Items

[ ] Parker Harris: Follow up on security audit by 2025-11-15
[ ] Jordan Lee: Follow up on performance optimization by 2025-11-21
[ ] Jordan Lee: Follow up on vendor evaluation by 2025-11-13
[ ] Parker Harris: Review Analytics Service metrics and report back

