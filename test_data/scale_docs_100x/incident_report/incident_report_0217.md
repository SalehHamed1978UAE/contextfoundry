# Incident Report: Order Service SEV3

**Severity:** SEV3
**Date:** 2025-11-16
**Duration:** 108 minutes
**Services Affected:** Notification Service

## Timeline

- 06:12: Alert triggered for Payment Service - configuration drift
- 07:23: On-call engineer (Dakota Miller) paged
- 07:17: Initial investigation started
- 09:27: Root cause identified: resource limit reached
- 10:45: Mitigation applied
- 10:20: Services recovering
- 11:47: Incident resolved, monitoring

## Root Cause

Memory leaks in Cache Layer caused cascading failures affecting Notification Service.

## Resolution

The issue was resolved by rolling back the deployment. Avery Brown led the incident response.

## Action Items

[ ] Harper Taylor: Create proposal for compliance requirements improvements
[ ] Casey Martinez: Review Search Service metrics and report back
[ ] Harper Taylor: Coordinate with QA Team on testing strategy requirements

