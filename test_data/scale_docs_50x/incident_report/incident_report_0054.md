# Incident Report: Cache Layer SEV2

**Severity:** SEV2
**Date:** 2025-07-02
**Duration:** 108 minutes
**Services Affected:** Inventory Service, API Gateway

## Timeline

- 12:26: Alert triggered for API Gateway - latency issues
- 12:39: On-call engineer (Blake Walker) paged
- 13:24: Initial investigation started
- 14:48: Root cause identified: certificate expiration
- 14:01: Mitigation applied
- 16:24: Services recovering
- 18:07: Incident resolved, monitoring

## Root Cause

Deployment failures in SMS Gateway caused cascading failures affecting Inventory Service, API Gateway.

## Resolution

The issue was resolved by restarting affected services. Alex Rivera led the incident response.

## Action Items

[ ] Reese Martin: Schedule meeting with SRE Team to discuss next steps
[ ] Reese Martin: Create proposal for microservices refactoring improvements
[ ] Dakota Miller: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Drew Patel: Create proposal for testing strategy improvements
[ ] Logan Jackson: Coordinate with API Team on technical debt requirements

