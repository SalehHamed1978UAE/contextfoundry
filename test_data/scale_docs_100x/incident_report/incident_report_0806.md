# Incident Report: Auth Service SEV3

**Severity:** SEV3
**Date:** 2025-09-23
**Duration:** 68 minutes
**Services Affected:** Recommendation Engine

## Timeline

- 13:07: Alert triggered for Search Service - missing documentation
- 14:21: On-call engineer (Tatum Lewis) paged
- 14:29: Initial investigation started
- 15:05: Root cause identified: failed deployment rollback
- 16:07: Mitigation applied
- 18:44: Services recovering
- 20:24: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in API Gateway caused cascading failures affecting Recommendation Engine.

## Resolution

The issue was resolved by restarting affected services. Reese Martin led the incident response.

## Action Items

[ ] Mia White: Follow up on vendor evaluation by 2025-11-24
[ ] Mia White: Review Shipping Service metrics and report back

