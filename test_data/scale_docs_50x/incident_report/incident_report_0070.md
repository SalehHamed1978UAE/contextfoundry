# Incident Report: User Service SEV2

**Severity:** SEV2
**Date:** 2025-10-06
**Duration:** 17 minutes
**Services Affected:** Recommendation Engine, Auth Service, Notification Service

## Timeline

- 18:35: Alert triggered for Auth Service - security vulnerabilities
- 18:31: On-call engineer (Sage Robinson) paged
- 19:20: Initial investigation started
- 20:10: Root cause identified: network partition in Search Service
- 21:26: Mitigation applied
- 21:23: Services recovering
- 22:59: Incident resolved, monitoring

## Root Cause

Error rates increasing in Fraud Detection caused cascading failures affecting Recommendation Engine, Auth Service, Notification Service.

## Resolution

The issue was resolved by restarting affected services. Sydney Clark led the incident response.

## Action Items

[ ] Cameron Davis: Review Email Service metrics and report back
[ ] Blake Walker: Follow up on performance optimization by 2025-12-03

