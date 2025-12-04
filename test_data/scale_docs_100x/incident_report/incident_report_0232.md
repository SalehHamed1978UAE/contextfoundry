# Incident Report: SMS Gateway SEV2

**Severity:** SEV2
**Date:** 2025-06-12
**Duration:** 33 minutes
**Services Affected:** Order Service

## Timeline

- 12:21: Alert triggered for Order Service - resource exhaustion
- 13:58: On-call engineer (Cameron Davis) paged
- 15:09: Initial investigation started
- 16:01: Root cause identified: database connection pool exhaustion
- 18:26: Mitigation applied
- 20:58: Services recovering
- 22:56: Incident resolved, monitoring

## Root Cause

Error rates increasing in Inventory Service caused cascading failures affecting Order Service.

## Resolution

The issue was resolved by restarting affected services. Cameron Davis led the incident response.

## Action Items

[ ] Morgan Chen: Coordinate with Security Team on caching strategy requirements
[ ] Reese Martin: Create proposal for hiring priorities improvements
[ ] Blake Adams: Follow up on budget allocation by 2025-11-24
[ ] Reese Martin: Create proposal for CI/CD pipeline improvements
[ ] Morgan Chen: Create proposal for security audit improvements

