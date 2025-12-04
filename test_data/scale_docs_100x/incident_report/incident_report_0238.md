# Incident Report: Checkout Service SEV3

**Severity:** SEV3
**Date:** 2025-11-17
**Duration:** 47 minutes
**Services Affected:** Auth Service

## Timeline

- 15:43: Alert triggered for Search Service - configuration drift
- 16:19: On-call engineer (Harper Taylor) paged
- 17:48: Initial investigation started
- 19:21: Root cause identified: database connection pool exhaustion
- 20:57: Mitigation applied
- 22:29: Services recovering
- 23:34: Incident resolved, monitoring

## Root Cause

Latency issues in Checkout Service caused cascading failures affecting Auth Service.

## Resolution

The issue was resolved by restarting affected services. Morgan Chen led the incident response.

## Action Items

[ ] Dakota Miller: Follow up on monitoring improvements by 2025-12-04
[ ] Finley Moore: Create proposal for compliance requirements improvements
[ ] Kendall Thomas: Create proposal for observability stack improvements
[ ] Casey Martinez: Follow up on budget allocation by 2025-11-23

