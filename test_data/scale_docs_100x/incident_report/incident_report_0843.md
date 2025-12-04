# Incident Report: API Gateway SEV2

**Severity:** SEV2
**Date:** 2025-06-21
**Duration:** 100 minutes
**Services Affected:** Search Service, Inventory Service, Auth Service

## Timeline

- 10:30: Alert triggered for Recommendation Engine - scaling bottlenecks
- 11:35: On-call engineer (Emerson Wilson) paged
- 11:47: Initial investigation started
- 13:25: Root cause identified: network partition in User Service
- 13:22: Mitigation applied
- 14:05: Services recovering
- 15:55: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in API Gateway caused cascading failures affecting Search Service, Inventory Service, Auth Service.

## Resolution

The issue was resolved by increasing resource limits. Casey Martinez led the incident response.

## Action Items

[ ] Casey Martinez: Coordinate with Infrastructure Team on cloud migration requirements
[ ] Mia White: Follow up on performance optimization by 2025-11-12
[ ] Mia White: Follow up on documentation by 2025-11-15

