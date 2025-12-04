# Incident Report: SMS Gateway SEV2

**Severity:** SEV2
**Date:** 2025-06-26
**Duration:** 79 minutes
**Services Affected:** Order Service, Notification Service

## Timeline

- 08:29: Alert triggered for Inventory Service - memory leaks
- 10:18: On-call engineer (Quinn Thompson) paged
- 10:12: Initial investigation started
- 10:11: Root cause identified: resource limit reached
- 12:45: Mitigation applied
- 14:17: Services recovering
- 16:18: Incident resolved, monitoring

## Root Cause

Configuration drift in Cache Layer caused cascading failures affecting Order Service, Notification Service.

## Resolution

The issue was resolved by applying a hotfix. Parker Harris led the incident response.

## Action Items

[ ] Blake Adams: Create proposal for vendor evaluation improvements
[ ] Blake Adams: Coordinate with Data Team on disaster recovery requirements
[ ] Blake Adams: Coordinate with Platform Team on monitoring improvements requirements
[ ] Casey Martinez: Review Auth Service metrics and report back
[ ] Riley Garcia: Review Checkout Service metrics and report back

