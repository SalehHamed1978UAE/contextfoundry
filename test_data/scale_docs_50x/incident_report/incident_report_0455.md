# Incident Report: Search Service SEV1

**Severity:** SEV1
**Date:** 2025-09-04
**Duration:** 45 minutes
**Services Affected:** Fraud Detection, User Service

## Timeline

- 01:38: Alert triggered for Checkout Service - technical debt
- 03:48: On-call engineer (Avery Brown) paged
- 05:25: Initial investigation started
- 06:06: Root cause identified: memory leak in cache layer
- 07:48: Mitigation applied
- 08:36: Services recovering
- 08:01: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Inventory Service caused cascading failures affecting Fraud Detection, User Service.

## Resolution

The issue was resolved by restarting affected services. Quinn Thompson led the incident response.

## Action Items

[ ] Taylor Kim: Review Notification Service metrics and report back
[ ] Casey Martinez: Create proposal for caching strategy improvements
[ ] Taylor Kim: Follow up on budget allocation by 2025-11-16
[ ] Casey Martinez: Follow up on vendor evaluation by 2025-11-12

