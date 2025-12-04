# Incident Report: Notification Service SEV3

**Severity:** SEV3
**Date:** 2025-06-27
**Duration:** 108 minutes
**Services Affected:** Shipping Service, Cache Layer, API Gateway, Search Service

## Timeline

- 20:58: Alert triggered for Payment Service - latency issues
- 21:55: On-call engineer (Morgan Chen) paged
- 22:15: Initial investigation started
- 23:59: Root cause identified: memory leak in cache layer
- 23:50: Mitigation applied
- 25:43: Services recovering
- 27:19: Incident resolved, monitoring

## Root Cause

Technical debt in Email Service caused cascading failures affecting Shipping Service, Cache Layer, API Gateway, Search Service.

## Resolution

The issue was resolved by increasing resource limits. Drew Patel led the incident response.

## Action Items

[ ] Blake Adams: Review API Gateway metrics and report back
[ ] Tatum Lewis: Review Auth Service metrics and report back
[ ] Riley Garcia: Schedule meeting with Frontend Team to discuss next steps
[ ] Tatum Lewis: Coordinate with Frontend Team on compliance requirements requirements

