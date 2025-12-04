# Incident Report: Fraud Detection SEV2

**Severity:** SEV2
**Date:** 2025-09-19
**Duration:** 100 minutes
**Services Affected:** Search Service

## Timeline

- 16:38: Alert triggered for Inventory Service - data inconsistency
- 17:57: On-call engineer (Quinn Thompson) paged
- 17:19: Initial investigation started
- 18:25: Root cause identified: failed deployment rollback
- 19:17: Mitigation applied
- 20:08: Services recovering
- 22:26: Incident resolved, monitoring

## Root Cause

Latency issues in Checkout Service caused cascading failures affecting Search Service.

## Resolution

The issue was resolved by restarting affected services. Cameron Davis led the incident response.

## Action Items

[ ] Taylor Kim: Follow up on testing strategy by 2025-11-14
[ ] Taylor Kim: Schedule meeting with QA Team to discuss next steps
[ ] Reese Martin: Review API Gateway metrics and report back

