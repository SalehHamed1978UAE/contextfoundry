# Incident Report: Email Service SEV2

**Severity:** SEV2
**Date:** 2025-10-19
**Duration:** 19 minutes
**Services Affected:** Notification Service, SMS Gateway

## Timeline

- 14:20: Alert triggered for Auth Service - timeout errors
- 15:45: On-call engineer (Cameron Davis) paged
- 15:23: Initial investigation started
- 15:30: Root cause identified: certificate expiration
- 17:23: Mitigation applied
- 19:36: Services recovering
- 21:34: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Analytics Service caused cascading failures affecting Notification Service, SMS Gateway.

## Resolution

The issue was resolved by applying a hotfix. Tatum Lewis led the incident response.

## Action Items

[ ] Morgan Chen: Follow up on technical debt by 2025-11-12
[ ] Quinn Thompson: Follow up on vendor evaluation by 2025-11-24
[ ] Alex Rivera: Follow up on CI/CD pipeline by 2025-11-20
[ ] Alex Rivera: Schedule meeting with QA Team to discuss next steps
[ ] Finley Moore: Create proposal for CI/CD pipeline improvements

