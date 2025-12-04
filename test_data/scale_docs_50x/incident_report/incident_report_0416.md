# Incident Report: Notification Service SEV3

**Severity:** SEV3
**Date:** 2025-10-02
**Duration:** 29 minutes
**Services Affected:** Notification Service, Auth Service, User Service, API Gateway

## Timeline

- 10:33: Alert triggered for User Service - technical debt
- 12:46: On-call engineer (Cameron Davis) paged
- 12:11: Initial investigation started
- 12:28: Root cause identified: database connection pool exhaustion
- 14:59: Mitigation applied
- 14:50: Services recovering
- 14:08: Incident resolved, monitoring

## Root Cause

Missing documentation in Fraud Detection caused cascading failures affecting Notification Service, Auth Service, User Service, API Gateway.

## Resolution

The issue was resolved by rolling back the deployment. Parker Harris led the incident response.

## Action Items

[ ] Sydney Clark: Coordinate with Infrastructure Team on security audit requirements
[ ] Blake Walker: Create proposal for monitoring improvements improvements
[ ] Morgan Chen: Create proposal for microservices refactoring improvements

