# Incident Report: Auth Service SEV3

**Severity:** SEV3
**Date:** 2025-10-20
**Duration:** 175 minutes
**Services Affected:** Order Service, SMS Gateway, Cache Layer, API Gateway

## Timeline

- 10:49: Alert triggered for SMS Gateway - latency issues
- 10:29: On-call engineer (Emerson Wilson) paged
- 12:15: Initial investigation started
- 12:21: Root cause identified: resource limit reached
- 12:41: Mitigation applied
- 13:51: Services recovering
- 15:03: Incident resolved, monitoring

## Root Cause

Technical debt in Auth Service caused cascading failures affecting Order Service, SMS Gateway, Cache Layer, API Gateway.

## Resolution

The issue was resolved by rolling back the deployment. Kendall Thomas led the incident response.

## Action Items

[ ] Drew Patel: Coordinate with QA Team on budget allocation requirements
[ ] Drew Patel: Follow up on documentation by 2025-11-09

