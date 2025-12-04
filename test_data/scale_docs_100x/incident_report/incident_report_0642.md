# Incident Report: API Gateway SEV2

**Severity:** SEV2
**Date:** 2025-07-20
**Duration:** 167 minutes
**Services Affected:** Order Service, Recommendation Engine, Payment Service

## Timeline

- 04:58: Alert triggered for Search Service - security vulnerabilities
- 05:51: On-call engineer (Blake Walker) paged
- 05:11: Initial investigation started
- 05:59: Root cause identified: network partition in Inventory Service
- 05:16: Mitigation applied
- 06:19: Services recovering
- 07:14: Incident resolved, monitoring

## Root Cause

Missing documentation in Email Service caused cascading failures affecting Order Service, Recommendation Engine, Payment Service.

## Resolution

The issue was resolved by restarting affected services. Cameron Davis led the incident response.

## Action Items

[ ] Emerson Wilson: Create proposal for caching strategy improvements
[ ] Riley Garcia: Follow up on budget allocation by 2025-11-25
[ ] Kendall Thomas: Follow up on performance optimization by 2025-12-02
[ ] Avery Brown: Create proposal for hiring priorities improvements

