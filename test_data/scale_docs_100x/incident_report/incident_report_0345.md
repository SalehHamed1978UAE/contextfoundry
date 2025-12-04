# Incident Report: Checkout Service SEV2

**Severity:** SEV2
**Date:** 2025-11-26
**Duration:** 89 minutes
**Services Affected:** Auth Service, Fraud Detection

## Timeline

- 13:09: Alert triggered for API Gateway - latency issues
- 13:53: On-call engineer (Jamie Anderson) paged
- 13:13: Initial investigation started
- 15:28: Root cause identified: failed deployment rollback
- 17:20: Mitigation applied
- 17:34: Services recovering
- 18:46: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Inventory Service caused cascading failures affecting Auth Service, Fraud Detection.

## Resolution

The issue was resolved by restarting affected services. Avery Brown led the incident response.

## Action Items

[ ] Alex Rivera: Review Auth Service metrics and report back
[ ] Blake Adams: Review Checkout Service metrics and report back
[ ] Cameron Davis: Coordinate with Frontend Team on monitoring improvements requirements
[ ] Blake Adams: Create proposal for cloud migration improvements
[ ] Blake Adams: Review Search Service metrics and report back

