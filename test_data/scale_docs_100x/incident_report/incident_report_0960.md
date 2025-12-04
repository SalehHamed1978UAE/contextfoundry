# Incident Report: Order Service SEV1

**Severity:** SEV1
**Date:** 2025-08-17
**Duration:** 38 minutes
**Services Affected:** Fraud Detection, Auth Service, Payment Service

## Timeline

- 19:43: Alert triggered for Cache Layer - scaling bottlenecks
- 21:46: On-call engineer (Morgan Chen) paged
- 22:13: Initial investigation started
- 24:21: Root cause identified: database connection pool exhaustion
- 25:45: Mitigation applied
- 25:59: Services recovering
- 25:36: Incident resolved, monitoring

## Root Cause

Timeout errors in Order Service caused cascading failures affecting Fraud Detection, Auth Service, Payment Service.

## Resolution

The issue was resolved by restarting affected services. Parker Harris led the incident response.

## Action Items

[ ] Blake Adams: Review API Gateway metrics and report back
[ ] Jordan Lee: Review API Gateway metrics and report back
[ ] Blake Adams: Review Analytics Service metrics and report back
[ ] Quinn Thompson: Follow up on capacity planning by 2025-11-23

