# Incident Report: Email Service SEV2

**Severity:** SEV2
**Date:** 2025-09-16
**Duration:** 39 minutes
**Services Affected:** API Gateway, Payment Service, Fraud Detection

## Timeline

- 08:13: Alert triggered for Cache Layer - configuration drift
- 10:03: On-call engineer (Taylor Kim) paged
- 12:11: Initial investigation started
- 12:51: Root cause identified: memory leak in cache layer
- 14:34: Mitigation applied
- 14:57: Services recovering
- 15:56: Incident resolved, monitoring

## Root Cause

Configuration drift in SMS Gateway caused cascading failures affecting API Gateway, Payment Service, Fraud Detection.

## Resolution

The issue was resolved by restarting affected services. Morgan Chen led the incident response.

## Action Items

[ ] Tatum Lewis: Schedule meeting with Mobile Team to discuss next steps
[ ] Emerson Wilson: Schedule meeting with QA Team to discuss next steps
[ ] Emerson Wilson: Create proposal for database sharding improvements

