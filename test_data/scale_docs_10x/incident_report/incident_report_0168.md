# Incident Report: Checkout Service SEV1

**Severity:** SEV1
**Date:** 2025-08-26
**Duration:** 129 minutes
**Services Affected:** Auth Service, Checkout Service

## Timeline

- 12:44: Alert triggered for Checkout Service - security vulnerabilities
- 14:19: On-call engineer (Jamie Anderson) paged
- 15:14: Initial investigation started
- 15:59: Root cause identified: certificate expiration
- 17:48: Mitigation applied
- 17:43: Services recovering
- 18:43: Incident resolved, monitoring

## Root Cause

Latency issues in Checkout Service caused cascading failures affecting Auth Service, Checkout Service.

## Resolution

The issue was resolved by increasing resource limits. Blake Walker led the incident response.

## Action Items

[ ] Drew Patel: Coordinate with QA Team on caching strategy requirements
[ ] Avery Brown: Review Recommendation Engine metrics and report back

