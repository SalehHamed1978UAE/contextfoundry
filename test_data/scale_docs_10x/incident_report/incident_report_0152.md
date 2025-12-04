# Incident Report: User Service SEV2

**Severity:** SEV2
**Date:** 2025-10-24
**Duration:** 81 minutes
**Services Affected:** Auth Service

## Timeline

- 16:59: Alert triggered for Email Service - missing documentation
- 17:57: On-call engineer (Sage Robinson) paged
- 17:05: Initial investigation started
- 18:17: Root cause identified: failed deployment rollback
- 18:01: Mitigation applied
- 19:58: Services recovering
- 21:10: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Checkout Service caused cascading failures affecting Auth Service.

## Resolution

The issue was resolved by rolling back the deployment. Finley Moore led the incident response.

## Action Items

[ ] Sydney Clark: Coordinate with Security Team on observability stack requirements
[ ] Casey Martinez: Schedule meeting with QA Team to discuss next steps
[ ] Jamie Anderson: Create proposal for performance optimization improvements
[ ] Alex Rivera: Create proposal for documentation improvements

