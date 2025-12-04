# Incident Report: Notification Service SEV3

**Severity:** SEV3
**Date:** 2025-10-18
**Duration:** 41 minutes
**Services Affected:** Email Service, Cache Layer, Notification Service, Recommendation Engine

## Timeline

- 13:49: Alert triggered for API Gateway - timeout errors
- 14:25: On-call engineer (Casey Martinez) paged
- 15:56: Initial investigation started
- 16:27: Root cause identified: database connection pool exhaustion
- 18:18: Mitigation applied
- 20:55: Services recovering
- 21:44: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Search Service caused cascading failures affecting Email Service, Cache Layer, Notification Service, Recommendation Engine.

## Resolution

The issue was resolved by applying a hotfix. Parker Harris led the incident response.

## Action Items

[ ] Sydney Clark: Create proposal for microservices refactoring improvements
[ ] Quinn Thompson: Coordinate with Frontend Team on Q4 planning requirements
[ ] Tatum Lewis: Review Payment Service metrics and report back
[ ] Morgan Chen: Coordinate with Infrastructure Team on capacity planning requirements

