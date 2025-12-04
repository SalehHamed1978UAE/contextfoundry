# Incident Report: Checkout Service SEV3

**Severity:** SEV3
**Date:** 2025-09-29
**Duration:** 177 minutes
**Services Affected:** Notification Service, Recommendation Engine

## Timeline

- 16:28: Alert triggered for Analytics Service - scaling bottlenecks
- 18:48: On-call engineer (Harper Taylor) paged
- 20:52: Initial investigation started
- 21:38: Root cause identified: resource limit reached
- 22:14: Mitigation applied
- 22:52: Services recovering
- 23:11: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Notification Service caused cascading failures affecting Notification Service, Recommendation Engine.

## Resolution

The issue was resolved by applying a hotfix. Blake Walker led the incident response.

## Action Items

[ ] Emerson Wilson: Review Recommendation Engine metrics and report back
[ ] Quinn Thompson: Schedule meeting with DevOps Team to discuss next steps
[ ] Quinn Thompson: Coordinate with Frontend Team on cost reduction requirements
[ ] Tatum Lewis: Schedule meeting with SRE Team to discuss next steps

