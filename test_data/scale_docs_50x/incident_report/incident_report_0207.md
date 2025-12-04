# Incident Report: Shipping Service SEV3

**Severity:** SEV3
**Date:** 2025-11-10
**Duration:** 75 minutes
**Services Affected:** Auth Service, Recommendation Engine

## Timeline

- 02:44: Alert triggered for User Service - missing documentation
- 04:58: On-call engineer (Sage Robinson) paged
- 04:21: Initial investigation started
- 04:09: Root cause identified: certificate expiration
- 05:38: Mitigation applied
- 06:27: Services recovering
- 06:50: Incident resolved, monitoring

## Root Cause

Missing documentation in Fraud Detection caused cascading failures affecting Auth Service, Recommendation Engine.

## Resolution

The issue was resolved by rolling back the deployment. Logan Jackson led the incident response.

## Action Items

[ ] Parker Harris: Create proposal for security audit improvements
[ ] Sage Robinson: Schedule meeting with Platform Team to discuss next steps
[ ] Riley Garcia: Coordinate with Growth Team on capacity planning requirements
[ ] Dakota Miller: Review Fraud Detection metrics and report back
[ ] Sage Robinson: Create proposal for compliance requirements improvements

