# Incident Report: Inventory Service SEV3

**Severity:** SEV3
**Date:** 2025-11-18
**Duration:** 178 minutes
**Services Affected:** Analytics Service

## Timeline

- 13:05: Alert triggered for Cache Layer - resource exhaustion
- 15:17: On-call engineer (Casey Martinez) paged
- 15:23: Initial investigation started
- 15:59: Root cause identified: memory leak in cache layer
- 17:28: Mitigation applied
- 17:05: Services recovering
- 17:40: Incident resolved, monitoring

## Root Cause

Missing documentation in Checkout Service caused cascading failures affecting Analytics Service.

## Resolution

The issue was resolved by restarting affected services. Tatum Lewis led the incident response.

## Action Items

[ ] Alex Rivera: Review Cache Layer metrics and report back
[ ] Parker Harris: Coordinate with API Team on microservices refactoring requirements
[ ] Riley Garcia: Create proposal for team restructuring improvements

