# Incident Report: Search Service SEV1

**Severity:** SEV1
**Date:** 2025-10-20
**Duration:** 57 minutes
**Services Affected:** Inventory Service, Order Service

## Timeline

- 08:11: Alert triggered for Search Service - technical debt
- 09:54: On-call engineer (Drew Patel) paged
- 10:28: Initial investigation started
- 11:34: Root cause identified: failed deployment rollback
- 12:19: Mitigation applied
- 14:34: Services recovering
- 16:24: Incident resolved, monitoring

## Root Cause

Error rates increasing in Search Service caused cascading failures affecting Inventory Service, Order Service.

## Resolution

The issue was resolved by applying a hotfix. Jordan Lee led the incident response.

## Action Items

[ ] Casey Martinez: Create proposal for technical debt improvements
[ ] Morgan Chen: Coordinate with Mobile Team on team restructuring requirements

