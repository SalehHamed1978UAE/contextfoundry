# Incident Report: Search Service SEV2

**Severity:** SEV2
**Date:** 2025-06-07
**Duration:** 65 minutes
**Services Affected:** Analytics Service, Search Service, Cache Layer, Notification Service

## Timeline

- 10:42: Alert triggered for Fraud Detection - resource exhaustion
- 11:05: On-call engineer (Morgan Chen) paged
- 13:53: Initial investigation started
- 15:27: Root cause identified: failed deployment rollback
- 17:13: Mitigation applied
- 18:04: Services recovering
- 19:11: Incident resolved, monitoring

## Root Cause

Deployment failures in User Service caused cascading failures affecting Analytics Service, Search Service, Cache Layer, Notification Service.

## Resolution

The issue was resolved by increasing resource limits. Mia White led the incident response.

## Action Items

[ ] Jordan Lee: Review Inventory Service metrics and report back
[ ] Drew Patel: Review Shipping Service metrics and report back
[ ] Jordan Lee: Schedule meeting with QA Team to discuss next steps
[ ] Dakota Miller: Create proposal for database sharding improvements
[ ] Dakota Miller: Follow up on caching strategy by 2025-11-12

