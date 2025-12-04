# Incident Report: User Service SEV3

**Severity:** SEV3
**Date:** 2025-07-12
**Duration:** 150 minutes
**Services Affected:** Cache Layer

## Timeline

- 04:28: Alert triggered for Auth Service - timeout errors
- 04:14: On-call engineer (Harper Taylor) paged
- 04:04: Initial investigation started
- 04:14: Root cause identified: memory leak in cache layer
- 05:25: Mitigation applied
- 07:15: Services recovering
- 08:57: Incident resolved, monitoring

## Root Cause

Configuration drift in Notification Service caused cascading failures affecting Cache Layer.

## Resolution

The issue was resolved by increasing resource limits. Sage Robinson led the incident response.

## Action Items

[ ] Finley Moore: Review Email Service metrics and report back
[ ] Avery Brown: Review Recommendation Engine metrics and report back
[ ] Sage Robinson: Schedule meeting with Platform Team to discuss next steps
[ ] Avery Brown: Create proposal for testing strategy improvements

