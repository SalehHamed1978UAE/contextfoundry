# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-11-13
**Duration:** 98 minutes
**Services Affected:** API Gateway

## Timeline

- 04:37: Alert triggered for Inventory Service - technical debt
- 05:34: On-call engineer (Blake Walker) paged
- 07:23: Initial investigation started
- 08:57: Root cause identified: memory leak in cache layer
- 09:37: Mitigation applied
- 11:43: Services recovering
- 12:04: Incident resolved, monitoring

## Root Cause

Data inconsistency in Cache Layer caused cascading failures affecting API Gateway.

## Resolution

The issue was resolved by increasing resource limits. Sage Robinson led the incident response.

## Action Items

[ ] Drew Patel: Follow up on technical debt by 2025-11-17
[ ] Alex Rivera: Review Search Service metrics and report back
[ ] Dakota Miller: Create proposal for incident response improvements
[ ] Casey Martinez: Follow up on microservices refactoring by 2025-11-10

