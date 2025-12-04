# Incident Report: Checkout Service SEV2

**Severity:** SEV2
**Date:** 2025-10-08
**Duration:** 31 minutes
**Services Affected:** SMS Gateway, Payment Service

## Timeline

- 01:36: Alert triggered for Fraud Detection - data inconsistency
- 03:14: On-call engineer (Tatum Lewis) paged
- 05:42: Initial investigation started
- 06:43: Root cause identified: memory leak in cache layer
- 07:11: Mitigation applied
- 08:44: Services recovering
- 10:03: Incident resolved, monitoring

## Root Cause

Resource exhaustion in SMS Gateway caused cascading failures affecting SMS Gateway, Payment Service.

## Resolution

The issue was resolved by restarting affected services. Jamie Anderson led the incident response.

## Action Items

[ ] Sage Robinson: Schedule meeting with API Team to discuss next steps
[ ] Quinn Thompson: Review API Gateway metrics and report back

