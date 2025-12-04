# Incident Report: Auth Service SEV1

**Severity:** SEV1
**Date:** 2025-09-01
**Duration:** 108 minutes
**Services Affected:** Order Service, Recommendation Engine

## Timeline

- 20:49: Alert triggered for Search Service - deployment failures
- 20:58: On-call engineer (Tatum Lewis) paged
- 21:33: Initial investigation started
- 22:56: Root cause identified: resource limit reached
- 23:26: Mitigation applied
- 25:11: Services recovering
- 27:18: Incident resolved, monitoring

## Root Cause

Missing documentation in Payment Service caused cascading failures affecting Order Service, Recommendation Engine.

## Resolution

The issue was resolved by rolling back the deployment. Quinn Thompson led the incident response.

## Action Items

[ ] Taylor Kim: Create proposal for performance optimization improvements
[ ] Tatum Lewis: Follow up on security audit by 2025-11-25

