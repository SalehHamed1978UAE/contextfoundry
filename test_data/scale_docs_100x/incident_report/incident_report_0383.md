# Incident Report: SMS Gateway SEV1

**Severity:** SEV1
**Date:** 2025-08-05
**Duration:** 94 minutes
**Services Affected:** Auth Service, User Service, Checkout Service, Recommendation Engine

## Timeline

- 06:26: Alert triggered for Order Service - resource exhaustion
- 06:47: On-call engineer (Blake Adams) paged
- 07:55: Initial investigation started
- 07:14: Root cause identified: certificate expiration
- 09:28: Mitigation applied
- 10:21: Services recovering
- 12:20: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Payment Service caused cascading failures affecting Auth Service, User Service, Checkout Service, Recommendation Engine.

## Resolution

The issue was resolved by increasing resource limits. Dakota Miller led the incident response.

## Action Items

[ ] Mia White: Create proposal for vendor evaluation improvements
[ ] Reese Martin: Coordinate with SRE Team on observability stack requirements

