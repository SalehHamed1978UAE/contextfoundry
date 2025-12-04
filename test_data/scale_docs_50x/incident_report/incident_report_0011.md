# Incident Report: Order Service SEV2

**Severity:** SEV2
**Date:** 2025-09-21
**Duration:** 63 minutes
**Services Affected:** Inventory Service

## Timeline

- 13:18: Alert triggered for API Gateway - memory leaks
- 15:59: On-call engineer (Logan Jackson) paged
- 17:21: Initial investigation started
- 17:05: Root cause identified: failed deployment rollback
- 19:46: Mitigation applied
- 19:34: Services recovering
- 21:00: Incident resolved, monitoring

## Root Cause

Latency issues in Cache Layer caused cascading failures affecting Inventory Service.

## Resolution

The issue was resolved by restarting affected services. Sydney Clark led the incident response.

## Action Items

[ ] Taylor Kim: Create proposal for microservices refactoring improvements
[ ] Taylor Kim: Coordinate with DevOps Team on Q4 planning requirements

