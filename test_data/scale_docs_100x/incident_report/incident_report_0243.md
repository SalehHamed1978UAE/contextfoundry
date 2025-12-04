# Incident Report: Notification Service SEV2

**Severity:** SEV2
**Date:** 2025-07-12
**Duration:** 79 minutes
**Services Affected:** Notification Service

## Timeline

- 13:40: Alert triggered for Payment Service - security vulnerabilities
- 13:25: On-call engineer (Jordan Lee) paged
- 15:33: Initial investigation started
- 15:31: Root cause identified: certificate expiration
- 16:35: Mitigation applied
- 16:58: Services recovering
- 16:15: Incident resolved, monitoring

## Root Cause

Deployment failures in Search Service caused cascading failures affecting Notification Service.

## Resolution

The issue was resolved by rolling back the deployment. Reese Martin led the incident response.

## Action Items

[ ] Jordan Lee: Schedule meeting with API Team to discuss next steps
[ ] Sydney Clark: Schedule meeting with Security Team to discuss next steps
[ ] Sydney Clark: Create proposal for API versioning improvements
[ ] Sydney Clark: Create proposal for API versioning improvements
[ ] Jordan Lee: Review API Gateway metrics and report back

