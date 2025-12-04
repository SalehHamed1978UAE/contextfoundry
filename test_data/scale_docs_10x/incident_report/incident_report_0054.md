# Incident Report: Shipping Service SEV2

**Severity:** SEV2
**Date:** 2025-11-08
**Duration:** 26 minutes
**Services Affected:** Search Service, Inventory Service, Recommendation Engine

## Timeline

- 11:06: Alert triggered for Analytics Service - latency issues
- 12:05: On-call engineer (Avery Brown) paged
- 14:20: Initial investigation started
- 15:00: Root cause identified: database connection pool exhaustion
- 16:25: Mitigation applied
- 16:59: Services recovering
- 18:46: Incident resolved, monitoring

## Root Cause

Technical debt in Search Service caused cascading failures affecting Search Service, Inventory Service, Recommendation Engine.

## Resolution

The issue was resolved by rolling back the deployment. Jamie Anderson led the incident response.

## Action Items

[ ] Mia White: Create proposal for technical debt improvements
[ ] Reese Martin: Schedule meeting with Security Team to discuss next steps
[ ] Casey Martinez: Schedule meeting with Mobile Team to discuss next steps
[ ] Reese Martin: Follow up on team restructuring by 2025-11-30
[ ] Reese Martin: Follow up on cloud migration by 2025-11-17

