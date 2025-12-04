# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-10-15
**Duration:** 104 minutes
**Services Affected:** Shipping Service, Order Service, Search Service, Notification Service

## Timeline

- 03:33: Alert triggered for Shipping Service - configuration drift
- 03:18: On-call engineer (Blake Walker) paged
- 05:32: Initial investigation started
- 06:32: Root cause identified: network partition in Inventory Service
- 06:13: Mitigation applied
- 06:50: Services recovering
- 07:41: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Auth Service caused cascading failures affecting Shipping Service, Order Service, Search Service, Notification Service.

## Resolution

The issue was resolved by rolling back the deployment. Parker Harris led the incident response.

## Action Items

[ ] Kendall Thomas: Review Search Service metrics and report back
[ ] Avery Brown: Coordinate with Data Team on compliance requirements requirements
[ ] Casey Martinez: Create proposal for database sharding improvements
[ ] Riley Garcia: Coordinate with Platform Team on vendor evaluation requirements

