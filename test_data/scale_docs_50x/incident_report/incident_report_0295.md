# Incident Report: User Service SEV3

**Severity:** SEV3
**Date:** 2025-07-27
**Duration:** 164 minutes
**Services Affected:** Recommendation Engine

## Timeline

- 04:11: Alert triggered for Notification Service - timeout errors
- 05:27: On-call engineer (Drew Patel) paged
- 05:06: Initial investigation started
- 05:37: Root cause identified: certificate expiration
- 06:44: Mitigation applied
- 08:25: Services recovering
- 09:03: Incident resolved, monitoring

## Root Cause

Technical debt in Checkout Service caused cascading failures affecting Recommendation Engine.

## Resolution

The issue was resolved by applying a hotfix. Quinn Thompson led the incident response.

## Action Items

[ ] Reese Martin: Review Search Service metrics and report back
[ ] Kendall Thomas: Coordinate with Infrastructure Team on vendor evaluation requirements

