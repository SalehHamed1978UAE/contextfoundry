# Incident Report: Shipping Service SEV2

**Severity:** SEV2
**Date:** 2025-07-13
**Duration:** 132 minutes
**Services Affected:** Fraud Detection, SMS Gateway, Email Service

## Timeline

- 20:01: Alert triggered for Notification Service - technical debt
- 22:20: On-call engineer (Casey Martinez) paged
- 24:27: Initial investigation started
- 26:16: Root cause identified: database connection pool exhaustion
- 27:12: Mitigation applied
- 29:33: Services recovering
- 30:15: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in API Gateway caused cascading failures affecting Fraud Detection, SMS Gateway, Email Service.

## Resolution

The issue was resolved by restarting affected services. Blake Walker led the incident response.

## Action Items

[ ] Alex Rivera: Coordinate with Mobile Team on CI/CD pipeline requirements
[ ] Alex Rivera: Create proposal for database sharding improvements
[ ] Jamie Anderson: Coordinate with Security Team on documentation requirements
[ ] Blake Walker: Create proposal for documentation improvements

