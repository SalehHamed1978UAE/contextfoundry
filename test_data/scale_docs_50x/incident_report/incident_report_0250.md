# Incident Report: Payment Service SEV2

**Severity:** SEV2
**Date:** 2025-10-19
**Duration:** 101 minutes
**Services Affected:** Recommendation Engine, Auth Service, Order Service

## Timeline

- 03:34: Alert triggered for API Gateway - latency issues
- 04:36: On-call engineer (Quinn Thompson) paged
- 06:04: Initial investigation started
- 06:14: Root cause identified: database connection pool exhaustion
- 06:07: Mitigation applied
- 07:06: Services recovering
- 07:26: Incident resolved, monitoring

## Root Cause

Memory leaks in Email Service caused cascading failures affecting Recommendation Engine, Auth Service, Order Service.

## Resolution

The issue was resolved by restarting affected services. Dakota Miller led the incident response.

## Action Items

[ ] Mia White: Follow up on caching strategy by 2025-11-27
[ ] Mia White: Create proposal for hiring priorities improvements
[ ] Mia White: Follow up on database sharding by 2025-11-22

