# Incident Report: Fraud Detection SEV2

**Severity:** SEV2
**Date:** 2025-09-10
**Duration:** 142 minutes
**Services Affected:** Payment Service, Auth Service, User Service, Notification Service

## Timeline

- 12:26: Alert triggered for Shipping Service - security vulnerabilities
- 13:45: On-call engineer (Emerson Wilson) paged
- 13:55: Initial investigation started
- 15:03: Root cause identified: certificate expiration
- 17:15: Mitigation applied
- 17:14: Services recovering
- 19:39: Incident resolved, monitoring

## Root Cause

Missing documentation in Shipping Service caused cascading failures affecting Payment Service, Auth Service, User Service, Notification Service.

## Resolution

The issue was resolved by restarting affected services. Sydney Clark led the incident response.

## Action Items

[ ] Riley Garcia: Coordinate with Growth Team on observability stack requirements
[ ] Drew Patel: Schedule meeting with DevOps Team to discuss next steps

