# Incident Report: Payment Service SEV2

**Severity:** SEV2
**Date:** 2025-08-19
**Duration:** 111 minutes
**Services Affected:** Checkout Service

## Timeline

- 02:09: Alert triggered for Payment Service - configuration drift
- 02:08: On-call engineer (Quinn Thompson) paged
- 04:42: Initial investigation started
- 05:12: Root cause identified: failed deployment rollback
- 06:43: Mitigation applied
- 08:59: Services recovering
- 09:28: Incident resolved, monitoring

## Root Cause

Technical debt in Email Service caused cascading failures affecting Checkout Service.

## Resolution

The issue was resolved by rolling back the deployment. Jordan Lee led the incident response.

## Action Items

[ ] Harper Taylor: Schedule meeting with Mobile Team to discuss next steps
[ ] Tatum Lewis: Create proposal for cost reduction improvements
[ ] Drew Patel: Create proposal for scalability planning improvements
[ ] Tatum Lewis: Schedule meeting with Data Team to discuss next steps
[ ] Morgan Chen: Schedule meeting with Mobile Team to discuss next steps

