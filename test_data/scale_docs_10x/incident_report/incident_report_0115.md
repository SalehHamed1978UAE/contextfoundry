# Incident Report: SMS Gateway SEV3

**Severity:** SEV3
**Date:** 2025-10-26
**Duration:** 23 minutes
**Services Affected:** Checkout Service

## Timeline

- 04:03: Alert triggered for Payment Service - security vulnerabilities
- 05:54: On-call engineer (Tatum Lewis) paged
- 05:06: Initial investigation started
- 07:42: Root cause identified: network partition in Notification Service
- 08:38: Mitigation applied
- 09:44: Services recovering
- 10:04: Incident resolved, monitoring

## Root Cause

Missing documentation in Order Service caused cascading failures affecting Checkout Service.

## Resolution

The issue was resolved by rolling back the deployment. Taylor Kim led the incident response.

## Action Items

[ ] Avery Brown: Review Inventory Service metrics and report back
[ ] Casey Martinez: Create proposal for incident response improvements

