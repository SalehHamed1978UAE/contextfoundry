# Incident Report: Checkout Service SEV3

**Severity:** SEV3
**Date:** 2025-11-06
**Duration:** 102 minutes
**Services Affected:** Email Service, Cache Layer

## Timeline

- 13:32: Alert triggered for Email Service - data inconsistency
- 13:21: On-call engineer (Drew Patel) paged
- 13:06: Initial investigation started
- 14:37: Root cause identified: certificate expiration
- 16:52: Mitigation applied
- 17:46: Services recovering
- 18:09: Incident resolved, monitoring

## Root Cause

Data inconsistency in Search Service caused cascading failures affecting Email Service, Cache Layer.

## Resolution

The issue was resolved by rolling back the deployment. Avery Brown led the incident response.

## Action Items

[ ] Tatum Lewis: Review Email Service metrics and report back
[ ] Tatum Lewis: Follow up on cost reduction by 2025-11-10

