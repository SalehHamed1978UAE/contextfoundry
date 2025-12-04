# Incident Report: Inventory Service SEV1

**Severity:** SEV1
**Date:** 2025-09-29
**Duration:** 153 minutes
**Services Affected:** Shipping Service, Recommendation Engine, Auth Service

## Timeline

- 12:55: Alert triggered for SMS Gateway - technical debt
- 14:29: On-call engineer (Harper Taylor) paged
- 14:40: Initial investigation started
- 16:31: Root cause identified: certificate expiration
- 18:30: Mitigation applied
- 19:42: Services recovering
- 19:21: Incident resolved, monitoring

## Root Cause

Deployment failures in Email Service caused cascading failures affecting Shipping Service, Recommendation Engine, Auth Service.

## Resolution

The issue was resolved by increasing resource limits. Avery Brown led the incident response.

## Action Items

[ ] Blake Walker: Review Recommendation Engine metrics and report back
[ ] Taylor Kim: Schedule meeting with Platform Team to discuss next steps

