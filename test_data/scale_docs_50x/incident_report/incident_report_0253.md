# Incident Report: Email Service SEV2

**Severity:** SEV2
**Date:** 2025-06-19
**Duration:** 113 minutes
**Services Affected:** Recommendation Engine, Search Service, Email Service

## Timeline

- 05:05: Alert triggered for User Service - technical debt
- 07:35: On-call engineer (Riley Garcia) paged
- 07:21: Initial investigation started
- 09:30: Root cause identified: failed deployment rollback
- 09:24: Mitigation applied
- 10:49: Services recovering
- 11:44: Incident resolved, monitoring

## Root Cause

Latency issues in Order Service caused cascading failures affecting Recommendation Engine, Search Service, Email Service.

## Resolution

The issue was resolved by restarting affected services. Morgan Chen led the incident response.

## Action Items

[ ] Sydney Clark: Schedule meeting with DevOps Team to discuss next steps
[ ] Mia White: Create proposal for caching strategy improvements
[ ] Mia White: Review API Gateway metrics and report back
[ ] Mia White: Schedule meeting with SRE Team to discuss next steps
[ ] Sydney Clark: Schedule meeting with DevOps Team to discuss next steps

