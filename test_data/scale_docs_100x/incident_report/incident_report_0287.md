# Incident Report: Cache Layer SEV3

**Severity:** SEV3
**Date:** 2025-08-31
**Duration:** 96 minutes
**Services Affected:** Inventory Service, Email Service, User Service

## Timeline

- 17:36: Alert triggered for Cache Layer - deployment failures
- 19:49: On-call engineer (Alex Rivera) paged
- 20:33: Initial investigation started
- 21:09: Root cause identified: failed deployment rollback
- 23:37: Mitigation applied
- 25:46: Services recovering
- 27:24: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Inventory Service caused cascading failures affecting Inventory Service, Email Service, User Service.

## Resolution

The issue was resolved by restarting affected services. Jordan Lee led the incident response.

## Action Items

[ ] Blake Walker: Create proposal for technical debt improvements
[ ] Kendall Thomas: Create proposal for documentation improvements
[ ] Casey Martinez: Follow up on testing strategy by 2025-11-11
[ ] Blake Walker: Follow up on Q4 planning by 2025-11-30
[ ] Mia White: Review Email Service metrics and report back

