# Incident Report: Shipping Service SEV1

**Severity:** SEV1
**Date:** 2025-11-17
**Duration:** 122 minutes
**Services Affected:** Recommendation Engine, Fraud Detection, Auth Service, Checkout Service

## Timeline

- 05:27: Alert triggered for Checkout Service - configuration drift
- 06:35: On-call engineer (Logan Jackson) paged
- 07:21: Initial investigation started
- 07:45: Root cause identified: resource limit reached
- 08:03: Mitigation applied
- 08:51: Services recovering
- 08:24: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Search Service caused cascading failures affecting Recommendation Engine, Fraud Detection, Auth Service, Checkout Service.

## Resolution

The issue was resolved by rolling back the deployment. Logan Jackson led the incident response.

## Action Items

[ ] Riley Garcia: Coordinate with Platform Team on technical debt requirements
[ ] Riley Garcia: Review Recommendation Engine metrics and report back
[ ] Dakota Miller: Review Payment Service metrics and report back
[ ] Dakota Miller: Follow up on microservices refactoring by 2025-11-25

