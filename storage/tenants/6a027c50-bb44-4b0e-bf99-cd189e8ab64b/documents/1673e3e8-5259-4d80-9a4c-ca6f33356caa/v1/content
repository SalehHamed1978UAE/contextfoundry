
# Post-Mortem: MedSync Platform Outage - January 29, 2026

**Date:** January 30, 2026
**Author:** Ben Carter, CTO

## 1. Summary

On January 29, 2026, from 2:15 PM to 3:30 PM EST, the MedSync Platform experienced a full outage, affecting all customers. The root cause was a misconfigured network ACL that blocked traffic to our primary database.

## 2. Timeline of Events

- **2:15 PM:** Alerts begin firing for database connectivity issues.
- **2:20 PM:** On-call engineer Emily Williams begins investigating.
- **2:45 PM:** The issue is escalated to the infrastructure team.
- **3:10 PM:** The misconfigured network ACL is identified as the root cause.
- **3:25 PM:** The ACL is corrected, and database connectivity is restored.
- **3:30 PM:** The MedSync Platform is fully operational.

## 3. Root Cause

A network engineer was performing a routine update to the network ACLs and accidentally removed a rule that allowed traffic from the application servers to the database.

## 4. Impact

- All customers were unable to access the MedSync Platform for 75 minutes.
- No data was lost.

## 5. Lessons Learned

- **Lack of automated testing for ACL changes:** We need to implement a process for automatically testing ACL changes before they are deployed to production.
- **Slow escalation process:** It took too long to escalate the issue to the infrastructure team. We need to review and improve our on-call escalation procedures.

## 6. Action Items

- **[Completed]** Correct the misconfigured network ACL.
- **[In Progress]** Implement a CI/CD pipeline for network ACL changes with automated testing.
- **[To Do]** Review and update the on-call escalation process.
