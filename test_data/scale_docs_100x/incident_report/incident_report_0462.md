# Incident Report: Payment Service SEV2

**Severity:** SEV2
**Date:** 2025-10-07
**Duration:** 177 minutes
**Services Affected:** Payment Service, Checkout Service

## Timeline

- 08:51: Alert triggered for Shipping Service - configuration drift
- 10:56: On-call engineer (Quinn Thompson) paged
- 12:15: Initial investigation started
- 13:48: Root cause identified: failed deployment rollback
- 15:23: Mitigation applied
- 17:51: Services recovering
- 18:28: Incident resolved, monitoring

## Root Cause

Error rates increasing in Search Service caused cascading failures affecting Payment Service, Checkout Service.

## Resolution

The issue was resolved by applying a hotfix. Kendall Thomas led the incident response.

## Action Items

[ ] Blake Adams: Coordinate with Infrastructure Team on Q4 planning requirements
[ ] Harper Taylor: Coordinate with Security Team on testing strategy requirements

