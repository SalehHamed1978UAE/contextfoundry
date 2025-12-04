# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-09-18
**Duration:** 68 minutes
**Services Affected:** Auth Service, Fraud Detection

## Timeline

- 14:03: Alert triggered for Checkout Service - data inconsistency
- 16:12: On-call engineer (Morgan Chen) paged
- 18:44: Initial investigation started
- 18:49: Root cause identified: network partition in Order Service
- 20:03: Mitigation applied
- 21:41: Services recovering
- 23:19: Incident resolved, monitoring

## Root Cause

Technical debt in Payment Service caused cascading failures affecting Auth Service, Fraud Detection.

## Resolution

The issue was resolved by rolling back the deployment. Dakota Miller led the incident response.

## Action Items

[ ] Parker Harris: Schedule meeting with Growth Team to discuss next steps
[ ] Riley Garcia: Create proposal for testing strategy improvements

