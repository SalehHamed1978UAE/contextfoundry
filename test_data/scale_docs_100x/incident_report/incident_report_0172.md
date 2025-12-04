# Incident Report: Inventory Service SEV2

**Severity:** SEV2
**Date:** 2025-10-28
**Duration:** 80 minutes
**Services Affected:** Cache Layer

## Timeline

- 16:53: Alert triggered for Order Service - deployment failures
- 18:34: On-call engineer (Blake Walker) paged
- 19:39: Initial investigation started
- 20:29: Root cause identified: certificate expiration
- 22:48: Mitigation applied
- 24:49: Services recovering
- 25:13: Incident resolved, monitoring

## Root Cause

Error rates increasing in Shipping Service caused cascading failures affecting Cache Layer.

## Resolution

The issue was resolved by increasing resource limits. Mia White led the incident response.

## Action Items

[ ] Mia White: Coordinate with Infrastructure Team on documentation requirements
[ ] Riley Garcia: Create proposal for technical debt improvements

