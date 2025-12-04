# Incident Report: Email Service SEV2

**Severity:** SEV2
**Date:** 2025-11-04
**Duration:** 71 minutes
**Services Affected:** SMS Gateway, Recommendation Engine

## Timeline

- 08:55: Alert triggered for Shipping Service - data inconsistency
- 10:04: On-call engineer (Jamie Anderson) paged
- 11:55: Initial investigation started
- 11:18: Root cause identified: resource limit reached
- 12:08: Mitigation applied
- 13:46: Services recovering
- 15:19: Incident resolved, monitoring

## Root Cause

Technical debt in Auth Service caused cascading failures affecting SMS Gateway, Recommendation Engine.

## Resolution

The issue was resolved by rolling back the deployment. Harper Taylor led the incident response.

## Action Items

[ ] Morgan Chen: Follow up on incident response by 2025-12-02
[ ] Harper Taylor: Coordinate with DevOps Team on incident response requirements

