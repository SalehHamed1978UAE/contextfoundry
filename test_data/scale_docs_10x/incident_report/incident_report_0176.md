# Incident Report: Auth Service SEV1

**Severity:** SEV1
**Date:** 2025-08-06
**Duration:** 144 minutes
**Services Affected:** Analytics Service, Search Service

## Timeline

- 12:21: Alert triggered for Shipping Service - technical debt
- 14:11: On-call engineer (Finley Moore) paged
- 16:44: Initial investigation started
- 18:53: Root cause identified: failed deployment rollback
- 20:05: Mitigation applied
- 20:05: Services recovering
- 20:01: Incident resolved, monitoring

## Root Cause

Timeout errors in SMS Gateway caused cascading failures affecting Analytics Service, Search Service.

## Resolution

The issue was resolved by rolling back the deployment. Avery Brown led the incident response.

## Action Items

[ ] Avery Brown: Review API Gateway metrics and report back
[ ] Sydney Clark: Follow up on documentation by 2025-11-21
[ ] Sydney Clark: Create proposal for disaster recovery improvements
[ ] Sydney Clark: Review API Gateway metrics and report back
[ ] Avery Brown: Create proposal for cloud migration improvements

