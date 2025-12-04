# Incident Report: Order Service SEV2

**Severity:** SEV2
**Date:** 2025-07-14
**Duration:** 153 minutes
**Services Affected:** Notification Service, Cache Layer

## Timeline

- 19:05: Alert triggered for Order Service - memory leaks
- 21:51: On-call engineer (Casey Martinez) paged
- 21:09: Initial investigation started
- 23:08: Root cause identified: failed deployment rollback
- 24:17: Mitigation applied
- 25:39: Services recovering
- 26:58: Incident resolved, monitoring

## Root Cause

Configuration drift in Inventory Service caused cascading failures affecting Notification Service, Cache Layer.

## Resolution

The issue was resolved by restarting affected services. Sydney Clark led the incident response.

## Action Items

[ ] Logan Jackson: Create proposal for cloud migration improvements
[ ] Avery Brown: Schedule meeting with DevOps Team to discuss next steps

