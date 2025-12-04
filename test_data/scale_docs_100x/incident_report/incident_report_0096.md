# Incident Report: Notification Service SEV3

**Severity:** SEV3
**Date:** 2025-07-28
**Duration:** 106 minutes
**Services Affected:** Shipping Service, Cache Layer, Order Service, Checkout Service

## Timeline

- 08:17: Alert triggered for Search Service - deployment failures
- 08:48: On-call engineer (Harper Taylor) paged
- 08:19: Initial investigation started
- 09:44: Root cause identified: failed deployment rollback
- 11:29: Mitigation applied
- 12:40: Services recovering
- 14:10: Incident resolved, monitoring

## Root Cause

Data inconsistency in Auth Service caused cascading failures affecting Shipping Service, Cache Layer, Order Service, Checkout Service.

## Resolution

The issue was resolved by applying a hotfix. Casey Martinez led the incident response.

## Action Items

[ ] Reese Martin: Coordinate with Backend Team on cloud migration requirements
[ ] Mia White: Coordinate with Data Team on documentation requirements

