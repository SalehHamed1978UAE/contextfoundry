# Incident Report: Order Service SEV1

**Severity:** SEV1
**Date:** 2025-10-07
**Duration:** 58 minutes
**Services Affected:** User Service, Auth Service, Recommendation Engine, Search Service

## Timeline

- 19:32: Alert triggered for Auth Service - security vulnerabilities
- 19:11: On-call engineer (Finley Moore) paged
- 20:35: Initial investigation started
- 20:43: Root cause identified: database connection pool exhaustion
- 20:05: Mitigation applied
- 20:39: Services recovering
- 22:07: Incident resolved, monitoring

## Root Cause

Technical debt in Inventory Service caused cascading failures affecting User Service, Auth Service, Recommendation Engine, Search Service.

## Resolution

The issue was resolved by rolling back the deployment. Blake Adams led the incident response.

## Action Items

[ ] Jamie Anderson: Schedule meeting with DevOps Team to discuss next steps
[ ] Jamie Anderson: Create proposal for technical debt improvements

