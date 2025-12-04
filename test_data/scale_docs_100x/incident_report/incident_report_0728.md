# Incident Report: API Gateway SEV3

**Severity:** SEV3
**Date:** 2025-06-08
**Duration:** 66 minutes
**Services Affected:** Cache Layer, Email Service

## Timeline

- 20:57: Alert triggered for Analytics Service - missing documentation
- 22:26: On-call engineer (Sage Robinson) paged
- 24:42: Initial investigation started
- 24:16: Root cause identified: database connection pool exhaustion
- 26:36: Mitigation applied
- 26:30: Services recovering
- 26:11: Incident resolved, monitoring

## Root Cause

Memory leaks in User Service caused cascading failures affecting Cache Layer, Email Service.

## Resolution

The issue was resolved by restarting affected services. Drew Patel led the incident response.

## Action Items

[ ] Casey Martinez: Follow up on testing strategy by 2025-11-20
[ ] Casey Martinez: Coordinate with SRE Team on security audit requirements
[ ] Casey Martinez: Follow up on capacity planning by 2025-11-13
[ ] Parker Harris: Create proposal for Q4 planning improvements
[ ] Sydney Clark: Review Inventory Service metrics and report back

