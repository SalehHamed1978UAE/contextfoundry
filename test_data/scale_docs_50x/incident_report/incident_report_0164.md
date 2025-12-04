# Incident Report: Checkout Service SEV2

**Severity:** SEV2
**Date:** 2025-11-06
**Duration:** 66 minutes
**Services Affected:** User Service

## Timeline

- 03:36: Alert triggered for Cache Layer - latency issues
- 05:42: On-call engineer (Casey Martinez) paged
- 07:43: Initial investigation started
- 07:01: Root cause identified: failed deployment rollback
- 08:31: Mitigation applied
- 09:03: Services recovering
- 09:17: Incident resolved, monitoring

## Root Cause

Timeout errors in Analytics Service caused cascading failures affecting User Service.

## Resolution

The issue was resolved by restarting affected services. Kendall Thomas led the incident response.

## Action Items

[ ] Cameron Davis: Create proposal for vendor evaluation improvements
[ ] Riley Garcia: Coordinate with Mobile Team on documentation requirements
[ ] Cameron Davis: Coordinate with Platform Team on CI/CD pipeline requirements
[ ] Alex Rivera: Review Fraud Detection metrics and report back
[ ] Riley Garcia: Review Search Service metrics and report back

