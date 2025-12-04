# Incident Report: Analytics Service SEV2

**Severity:** SEV2
**Date:** 2025-06-23
**Duration:** 33 minutes
**Services Affected:** Inventory Service, API Gateway, Notification Service

## Timeline

- 02:15: Alert triggered for Search Service - missing documentation
- 04:01: On-call engineer (Tatum Lewis) paged
- 04:00: Initial investigation started
- 06:40: Root cause identified: memory leak in cache layer
- 07:06: Mitigation applied
- 08:04: Services recovering
- 10:31: Incident resolved, monitoring

## Root Cause

Missing documentation in Notification Service caused cascading failures affecting Inventory Service, API Gateway, Notification Service.

## Resolution

The issue was resolved by applying a hotfix. Tatum Lewis led the incident response.

## Action Items

[ ] Tatum Lewis: Schedule meeting with Mobile Team to discuss next steps
[ ] Emerson Wilson: Schedule meeting with QA Team to discuss next steps

