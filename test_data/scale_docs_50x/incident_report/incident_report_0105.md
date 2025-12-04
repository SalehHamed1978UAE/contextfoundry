# Incident Report: Payment Service SEV2

**Severity:** SEV2
**Date:** 2025-11-21
**Duration:** 79 minutes
**Services Affected:** User Service, Checkout Service, Fraud Detection, Search Service

## Timeline

- 07:15: Alert triggered for Search Service - data inconsistency
- 08:30: On-call engineer (Drew Patel) paged
- 08:23: Initial investigation started
- 09:58: Root cause identified: network partition in Notification Service
- 10:17: Mitigation applied
- 12:31: Services recovering
- 13:02: Incident resolved, monitoring

## Root Cause

Deployment failures in Auth Service caused cascading failures affecting User Service, Checkout Service, Fraud Detection, Search Service.

## Resolution

The issue was resolved by rolling back the deployment. Cameron Davis led the incident response.

## Action Items

[ ] Riley Garcia: Follow up on cost reduction by 2025-11-09
[ ] Kendall Thomas: Follow up on testing strategy by 2025-11-30
[ ] Dakota Miller: Create proposal for monitoring improvements improvements
[ ] Tatum Lewis: Follow up on disaster recovery by 2025-11-28

