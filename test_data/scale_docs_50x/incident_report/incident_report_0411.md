# Incident Report: Search Service SEV2

**Severity:** SEV2
**Date:** 2025-11-13
**Duration:** 123 minutes
**Services Affected:** Auth Service, SMS Gateway

## Timeline

- 07:00: Alert triggered for Recommendation Engine - latency issues
- 08:33: On-call engineer (Sage Robinson) paged
- 08:23: Initial investigation started
- 08:39: Root cause identified: network partition in Payment Service
- 10:23: Mitigation applied
- 10:52: Services recovering
- 10:32: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in User Service caused cascading failures affecting Auth Service, SMS Gateway.

## Resolution

The issue was resolved by rolling back the deployment. Blake Adams led the incident response.

## Action Items

[ ] Sage Robinson: Follow up on team restructuring by 2025-11-23
[ ] Reese Martin: Schedule meeting with Backend Team to discuss next steps
[ ] Sage Robinson: Follow up on testing strategy by 2025-11-06
[ ] Sage Robinson: Review Payment Service metrics and report back

