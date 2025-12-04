# Incident Report: Analytics Service SEV2

**Severity:** SEV2
**Date:** 2025-10-23
**Duration:** 173 minutes
**Services Affected:** Checkout Service

## Timeline

- 22:36: Alert triggered for Payment Service - resource exhaustion
- 23:47: On-call engineer (Drew Patel) paged
- 24:01: Initial investigation started
- 24:23: Root cause identified: memory leak in cache layer
- 25:19: Mitigation applied
- 25:55: Services recovering
- 25:30: Incident resolved, monitoring

## Root Cause

Timeout errors in Notification Service caused cascading failures affecting Checkout Service.

## Resolution

The issue was resolved by applying a hotfix. Dakota Miller led the incident response.

## Action Items

[ ] Morgan Chen: Coordinate with Infrastructure Team on hiring priorities requirements
[ ] Alex Rivera: Coordinate with Mobile Team on caching strategy requirements
[ ] Quinn Thompson: Review Notification Service metrics and report back

