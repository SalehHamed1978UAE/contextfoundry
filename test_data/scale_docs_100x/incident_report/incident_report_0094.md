# Incident Report: Email Service SEV1

**Severity:** SEV1
**Date:** 2025-10-03
**Duration:** 142 minutes
**Services Affected:** Email Service, Cache Layer, Auth Service

## Timeline

- 12:14: Alert triggered for Search Service - error rates increasing
- 14:32: On-call engineer (Logan Jackson) paged
- 14:14: Initial investigation started
- 14:15: Root cause identified: resource limit reached
- 14:33: Mitigation applied
- 14:52: Services recovering
- 15:21: Incident resolved, monitoring

## Root Cause

Deployment failures in Checkout Service caused cascading failures affecting Email Service, Cache Layer, Auth Service.

## Resolution

The issue was resolved by restarting affected services. Finley Moore led the incident response.

## Action Items

[ ] Kendall Thomas: Coordinate with API Team on incident response requirements
[ ] Mia White: Follow up on CI/CD pipeline by 2025-11-26
[ ] Kendall Thomas: Coordinate with API Team on Q4 planning requirements

