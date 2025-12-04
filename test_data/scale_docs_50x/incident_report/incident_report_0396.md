# Incident Report: Shipping Service SEV2

**Severity:** SEV2
**Date:** 2025-09-22
**Duration:** 161 minutes
**Services Affected:** Order Service, Recommendation Engine

## Timeline

- 04:40: Alert triggered for API Gateway - technical debt
- 04:56: On-call engineer (Quinn Thompson) paged
- 04:50: Initial investigation started
- 05:48: Root cause identified: failed deployment rollback
- 06:42: Mitigation applied
- 06:20: Services recovering
- 06:44: Incident resolved, monitoring

## Root Cause

Data inconsistency in Cache Layer caused cascading failures affecting Order Service, Recommendation Engine.

## Resolution

The issue was resolved by applying a hotfix. Blake Adams led the incident response.

## Action Items

[ ] Blake Adams: Follow up on capacity planning by 2025-11-14
[ ] Reese Martin: Schedule meeting with API Team to discuss next steps
[ ] Casey Martinez: Review Analytics Service metrics and report back
[ ] Reese Martin: Coordinate with Backend Team on testing strategy requirements
[ ] Casey Martinez: Schedule meeting with Mobile Team to discuss next steps

