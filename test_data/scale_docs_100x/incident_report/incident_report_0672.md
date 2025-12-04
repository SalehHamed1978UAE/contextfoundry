# Incident Report: Fraud Detection SEV1

**Severity:** SEV1
**Date:** 2025-08-08
**Duration:** 162 minutes
**Services Affected:** SMS Gateway, Email Service, Search Service

## Timeline

- 13:35: Alert triggered for Cache Layer - scaling bottlenecks
- 14:00: On-call engineer (Finley Moore) paged
- 16:16: Initial investigation started
- 18:14: Root cause identified: resource limit reached
- 19:55: Mitigation applied
- 19:57: Services recovering
- 20:29: Incident resolved, monitoring

## Root Cause

Timeout errors in User Service caused cascading failures affecting SMS Gateway, Email Service, Search Service.

## Resolution

The issue was resolved by restarting affected services. Alex Rivera led the incident response.

## Action Items

[ ] Dakota Miller: Review Checkout Service metrics and report back
[ ] Dakota Miller: Schedule meeting with QA Team to discuss next steps
[ ] Tatum Lewis: Coordinate with SRE Team on team restructuring requirements
[ ] Dakota Miller: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Parker Harris: Coordinate with Mobile Team on technical debt requirements

