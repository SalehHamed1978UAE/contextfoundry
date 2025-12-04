# Incident Report: Order Service SEV3

**Severity:** SEV3
**Date:** 2025-10-01
**Duration:** 120 minutes
**Services Affected:** Analytics Service, Search Service, Order Service

## Timeline

- 07:48: Alert triggered for Auth Service - timeout errors
- 09:15: On-call engineer (Sydney Clark) paged
- 09:24: Initial investigation started
- 11:50: Root cause identified: database connection pool exhaustion
- 13:02: Mitigation applied
- 14:04: Services recovering
- 15:36: Incident resolved, monitoring

## Root Cause

Technical debt in Shipping Service caused cascading failures affecting Analytics Service, Search Service, Order Service.

## Resolution

The issue was resolved by rolling back the deployment. Mia White led the incident response.

## Action Items

[ ] Dakota Miller: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Parker Harris: Review SMS Gateway metrics and report back
[ ] Blake Walker: Schedule meeting with Mobile Team to discuss next steps
[ ] Finley Moore: Create proposal for technical debt improvements

