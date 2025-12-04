# Incident Report: Analytics Service SEV3

**Severity:** SEV3
**Date:** 2025-11-30
**Duration:** 179 minutes
**Services Affected:** Recommendation Engine, Order Service, Cache Layer, Auth Service

## Timeline

- 19:39: Alert triggered for Checkout Service - technical debt
- 19:20: On-call engineer (Casey Martinez) paged
- 20:44: Initial investigation started
- 21:41: Root cause identified: database connection pool exhaustion
- 22:32: Mitigation applied
- 24:41: Services recovering
- 26:35: Incident resolved, monitoring

## Root Cause

Latency issues in Email Service caused cascading failures affecting Recommendation Engine, Order Service, Cache Layer, Auth Service.

## Resolution

The issue was resolved by applying a hotfix. Logan Jackson led the incident response.

## Action Items

[ ] Harper Taylor: Follow up on testing strategy by 2025-11-05
[ ] Sydney Clark: Coordinate with Security Team on cloud migration requirements

