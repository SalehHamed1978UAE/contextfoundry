# Incident Report: SMS Gateway SEV1

**Severity:** SEV1
**Date:** 2025-09-12
**Duration:** 166 minutes
**Services Affected:** API Gateway, Cache Layer

## Timeline

- 11:48: Alert triggered for Fraud Detection - memory leaks
- 13:38: On-call engineer (Tatum Lewis) paged
- 15:30: Initial investigation started
- 16:23: Root cause identified: failed deployment rollback
- 18:08: Mitigation applied
- 19:24: Services recovering
- 21:16: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Email Service caused cascading failures affecting API Gateway, Cache Layer.

## Resolution

The issue was resolved by restarting affected services. Morgan Chen led the incident response.

## Action Items

[ ] Taylor Kim: Coordinate with Platform Team on caching strategy requirements
[ ] Drew Patel: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Finley Moore: Follow up on disaster recovery by 2025-11-30

