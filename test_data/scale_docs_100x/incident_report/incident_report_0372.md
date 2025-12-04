# Incident Report: Auth Service SEV3

**Severity:** SEV3
**Date:** 2025-08-22
**Duration:** 17 minutes
**Services Affected:** Order Service, Notification Service, Search Service

## Timeline

- 20:51: Alert triggered for API Gateway - technical debt
- 20:27: On-call engineer (Drew Patel) paged
- 21:47: Initial investigation started
- 22:01: Root cause identified: resource limit reached
- 23:48: Mitigation applied
- 24:57: Services recovering
- 25:42: Incident resolved, monitoring

## Root Cause

Memory leaks in Search Service caused cascading failures affecting Order Service, Notification Service, Search Service.

## Resolution

The issue was resolved by increasing resource limits. Blake Adams led the incident response.

## Action Items

[ ] Jamie Anderson: Create proposal for technical debt improvements
[ ] Casey Martinez: Coordinate with Growth Team on cost reduction requirements
[ ] Drew Patel: Schedule meeting with Backend Team to discuss next steps
[ ] Taylor Kim: Follow up on team restructuring by 2025-12-01
[ ] Taylor Kim: Create proposal for cloud migration improvements

