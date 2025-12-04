# Incident Report: Payment Service SEV2

**Severity:** SEV2
**Date:** 2025-11-21
**Duration:** 16 minutes
**Services Affected:** Email Service, Cache Layer

## Timeline

- 05:18: Alert triggered for Search Service - missing documentation
- 06:10: On-call engineer (Parker Harris) paged
- 08:02: Initial investigation started
- 08:04: Root cause identified: certificate expiration
- 09:32: Mitigation applied
- 10:12: Services recovering
- 10:39: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Fraud Detection caused cascading failures affecting Email Service, Cache Layer.

## Resolution

The issue was resolved by rolling back the deployment. Reese Martin led the incident response.

## Action Items

[ ] Sage Robinson: Coordinate with Mobile Team on technical debt requirements
[ ] Riley Garcia: Schedule meeting with Growth Team to discuss next steps

