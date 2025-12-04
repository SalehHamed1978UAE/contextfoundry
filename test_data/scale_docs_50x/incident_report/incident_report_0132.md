# Incident Report: Notification Service SEV2

**Severity:** SEV2
**Date:** 2025-06-20
**Duration:** 137 minutes
**Services Affected:** Notification Service, SMS Gateway

## Timeline

- 19:45: Alert triggered for Inventory Service - data inconsistency
- 19:53: On-call engineer (Emerson Wilson) paged
- 20:44: Initial investigation started
- 21:54: Root cause identified: memory leak in cache layer
- 22:46: Mitigation applied
- 23:35: Services recovering
- 24:37: Incident resolved, monitoring

## Root Cause

Configuration drift in Email Service caused cascading failures affecting Notification Service, SMS Gateway.

## Resolution

The issue was resolved by applying a hotfix. Sydney Clark led the incident response.

## Action Items

[ ] Dakota Miller: Coordinate with Growth Team on compliance requirements requirements
[ ] Taylor Kim: Follow up on compliance requirements by 2025-11-16
[ ] Avery Brown: Follow up on CI/CD pipeline by 2025-11-27

