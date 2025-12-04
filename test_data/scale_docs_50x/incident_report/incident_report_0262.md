# Incident Report: Auth Service SEV1

**Severity:** SEV1
**Date:** 2025-11-22
**Duration:** 143 minutes
**Services Affected:** Fraud Detection

## Timeline

- 17:41: Alert triggered for User Service - deployment failures
- 19:34: On-call engineer (Mia White) paged
- 19:03: Initial investigation started
- 19:53: Root cause identified: resource limit reached
- 20:49: Mitigation applied
- 22:42: Services recovering
- 23:24: Incident resolved, monitoring

## Root Cause

Memory leaks in Notification Service caused cascading failures affecting Fraud Detection.

## Resolution

The issue was resolved by applying a hotfix. Reese Martin led the incident response.

## Action Items

[ ] Reese Martin: Coordinate with SRE Team on capacity planning requirements
[ ] Blake Adams: Schedule meeting with API Team to discuss next steps
[ ] Blake Adams: Coordinate with DevOps Team on cloud migration requirements
[ ] Blake Adams: Follow up on monitoring improvements by 2025-11-05

