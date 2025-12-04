# Incident Report: SMS Gateway SEV1

**Severity:** SEV1
**Date:** 2025-08-26
**Duration:** 121 minutes
**Services Affected:** Email Service, SMS Gateway, User Service

## Timeline

- 13:38: Alert triggered for Checkout Service - configuration drift
- 13:07: On-call engineer (Riley Garcia) paged
- 14:33: Initial investigation started
- 16:14: Root cause identified: certificate expiration
- 18:53: Mitigation applied
- 18:47: Services recovering
- 19:57: Incident resolved, monitoring

## Root Cause

Data inconsistency in Fraud Detection caused cascading failures affecting Email Service, SMS Gateway, User Service.

## Resolution

The issue was resolved by restarting affected services. Jordan Lee led the incident response.

## Action Items

[ ] Casey Martinez: Schedule meeting with Frontend Team to discuss next steps
[ ] Morgan Chen: Coordinate with API Team on hiring priorities requirements
[ ] Taylor Kim: Schedule meeting with QA Team to discuss next steps

