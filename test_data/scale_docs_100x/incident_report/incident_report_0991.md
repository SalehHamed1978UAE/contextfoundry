# Incident Report: Inventory Service SEV3

**Severity:** SEV3
**Date:** 2025-07-22
**Duration:** 91 minutes
**Services Affected:** SMS Gateway

## Timeline

- 04:33: Alert triggered for Order Service - latency issues
- 05:46: On-call engineer (Finley Moore) paged
- 05:55: Initial investigation started
- 06:53: Root cause identified: resource limit reached
- 07:09: Mitigation applied
- 07:19: Services recovering
- 09:25: Incident resolved, monitoring

## Root Cause

Latency issues in Auth Service caused cascading failures affecting SMS Gateway.

## Resolution

The issue was resolved by applying a hotfix. Morgan Chen led the incident response.

## Action Items

[ ] Sydney Clark: Review Inventory Service metrics and report back
[ ] Riley Garcia: Schedule meeting with Data Team to discuss next steps
[ ] Morgan Chen: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Sydney Clark: Review API Gateway metrics and report back
[ ] Tatum Lewis: Schedule meeting with Infrastructure Team to discuss next steps

