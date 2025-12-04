# Incident Report: Payment Service SEV3

**Severity:** SEV3
**Date:** 2025-06-20
**Duration:** 97 minutes
**Services Affected:** Notification Service

## Timeline

- 03:13: Alert triggered for Notification Service - security vulnerabilities
- 04:48: On-call engineer (Reese Martin) paged
- 05:10: Initial investigation started
- 07:36: Root cause identified: failed deployment rollback
- 09:32: Mitigation applied
- 09:14: Services recovering
- 09:06: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Cache Layer caused cascading failures affecting Notification Service.

## Resolution

The issue was resolved by rolling back the deployment. Jordan Lee led the incident response.

## Action Items

[ ] Taylor Kim: Schedule meeting with Backend Team to discuss next steps
[ ] Taylor Kim: Create proposal for team restructuring improvements
[ ] Jordan Lee: Schedule meeting with Frontend Team to discuss next steps
[ ] Sydney Clark: Create proposal for vendor evaluation improvements

