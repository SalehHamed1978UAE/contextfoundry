# Incident Report: Shipping Service SEV2

**Severity:** SEV2
**Date:** 2025-08-12
**Duration:** 131 minutes
**Services Affected:** Notification Service

## Timeline

- 19:01: Alert triggered for Inventory Service - configuration drift
- 21:56: On-call engineer (Quinn Thompson) paged
- 22:39: Initial investigation started
- 23:44: Root cause identified: failed deployment rollback
- 25:15: Mitigation applied
- 25:57: Services recovering
- 27:30: Incident resolved, monitoring

## Root Cause

Missing documentation in Search Service caused cascading failures affecting Notification Service.

## Resolution

The issue was resolved by restarting affected services. Jamie Anderson led the incident response.

## Action Items

[ ] Harper Taylor: Review Recommendation Engine metrics and report back
[ ] Cameron Davis: Review Fraud Detection metrics and report back
[ ] Reese Martin: Follow up on observability stack by 2025-11-08
[ ] Harper Taylor: Schedule meeting with SRE Team to discuss next steps

