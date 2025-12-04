# Incident Report: User Service SEV3

**Severity:** SEV3
**Date:** 2025-11-18
**Duration:** 61 minutes
**Services Affected:** SMS Gateway, User Service

## Timeline

- 02:04: Alert triggered for Analytics Service - data inconsistency
- 02:46: On-call engineer (Finley Moore) paged
- 02:33: Initial investigation started
- 02:40: Root cause identified: certificate expiration
- 02:01: Mitigation applied
- 02:03: Services recovering
- 03:24: Incident resolved, monitoring

## Root Cause

Latency issues in User Service caused cascading failures affecting SMS Gateway, User Service.

## Resolution

The issue was resolved by restarting affected services. Reese Martin led the incident response.

## Action Items

[ ] Morgan Chen: Review Order Service metrics and report back
[ ] Cameron Davis: Coordinate with Backend Team on security audit requirements

