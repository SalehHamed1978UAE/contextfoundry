# Incident Report: Auth Service SEV3

**Severity:** SEV3
**Date:** 2025-06-10
**Duration:** 84 minutes
**Services Affected:** Fraud Detection, Email Service, Auth Service, Cache Layer

## Timeline

- 19:08: Alert triggered for Payment Service - deployment failures
- 20:47: On-call engineer (Jordan Lee) paged
- 20:53: Initial investigation started
- 21:50: Root cause identified: memory leak in cache layer
- 21:18: Mitigation applied
- 23:38: Services recovering
- 23:05: Incident resolved, monitoring

## Root Cause

Resource exhaustion in SMS Gateway caused cascading failures affecting Fraud Detection, Email Service, Auth Service, Cache Layer.

## Resolution

The issue was resolved by restarting affected services. Mia White led the incident response.

## Action Items

[ ] Finley Moore: Coordinate with Mobile Team on caching strategy requirements
[ ] Morgan Chen: Coordinate with SRE Team on disaster recovery requirements
[ ] Emerson Wilson: Create proposal for cost reduction improvements

