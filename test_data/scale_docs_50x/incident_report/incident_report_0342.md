# Incident Report: Cache Layer SEV2

**Severity:** SEV2
**Date:** 2025-06-25
**Duration:** 93 minutes
**Services Affected:** Order Service, Search Service, Checkout Service, User Service

## Timeline

- 07:20: Alert triggered for Order Service - latency issues
- 09:01: On-call engineer (Logan Jackson) paged
- 10:23: Initial investigation started
- 10:41: Root cause identified: memory leak in cache layer
- 11:54: Mitigation applied
- 11:08: Services recovering
- 13:24: Incident resolved, monitoring

## Root Cause

Timeout errors in Fraud Detection caused cascading failures affecting Order Service, Search Service, Checkout Service, User Service.

## Resolution

The issue was resolved by applying a hotfix. Kendall Thomas led the incident response.

## Action Items

[ ] Tatum Lewis: Schedule meeting with API Team to discuss next steps
[ ] Jordan Lee: Schedule meeting with Security Team to discuss next steps
[ ] Cameron Davis: Schedule meeting with Platform Team to discuss next steps
[ ] Alex Rivera: Create proposal for cloud migration improvements

