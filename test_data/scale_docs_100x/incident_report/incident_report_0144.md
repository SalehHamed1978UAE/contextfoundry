# Incident Report: Email Service SEV2

**Severity:** SEV2
**Date:** 2025-10-29
**Duration:** 157 minutes
**Services Affected:** SMS Gateway, Recommendation Engine

## Timeline

- 13:01: Alert triggered for Auth Service - error rates increasing
- 14:36: On-call engineer (Blake Adams) paged
- 15:21: Initial investigation started
- 15:44: Root cause identified: network partition in Search Service
- 16:15: Mitigation applied
- 18:32: Services recovering
- 20:55: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Search Service caused cascading failures affecting SMS Gateway, Recommendation Engine.

## Resolution

The issue was resolved by increasing resource limits. Jamie Anderson led the incident response.

## Action Items

[ ] Emerson Wilson: Create proposal for API versioning improvements
[ ] Morgan Chen: Create proposal for incident response improvements

