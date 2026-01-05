# Incident Report: INC-2025-0892

**Incident Title**: Patient Identity Service Outage  
**Severity**: Critical (Patient Safety)  
**Date**: November 15, 2025  
**Duration**: 2 hours 15 minutes  
**Author**: Dr. Fatima Al-Hassan, Chief Medical Information Officer

---

## Executive Summary

On November 15, 2025, the Patient Identity Service experienced a complete outage lasting 2 hours and 15 minutes. This incident affected all clinical systems that depend on patient identification, including the EHR, Lab System, Pharmacy System, and Radiology System. During the outage, clinicians were forced to use paper-based downtime procedures.

---

## Impact Assessment

### Systems Affected

The Patient Identity Service outage affected the following systems:

- **EHR**: Unable to open patient charts (100% functionality loss)
- **Lab System**: Unable to process new orders or match results to patients
- **Pharmacy System**: Unable to verify patient identity for medication dispensing
- **Radiology System**: Unable to match images to patient records
- **Appointment Scheduling**: Unable to check in patients
- **Billing System**: Unable to process charges (degraded, not critical)

### Patient Impact

- 847 patients affected across all facilities
- 12 medication delays (resolved without patient harm)
- 34 lab orders delayed
- 0 adverse events reported

### Financial Impact

- Estimated revenue delay: AED 450,000
- Staff overtime for catch-up: AED 28,000
- No penalties or fines

---

## Timeline

| Time (GST) | Event |
|------------|-------|
| 09:12 | Master Patient Index database primary node fails |
| 09:13 | Patient Identity Service begins returning errors |
| 09:14 | EHR displays "Patient Lookup Failed" errors |
| 09:15 | Monitoring alerts fire for all dependent systems |
| 09:18 | Clinical Systems Team on-call paged |
| 09:22 | Downtime procedures activated at all facilities |
| 09:30 | Database Administration Team engaged |
| 09:45 | Root cause identified: disk failure on primary node |
| 10:15 | Failover to standby initiated |
| 10:45 | Failover complete, Patient Identity Service restored |
| 11:00 | EHR and Lab System confirmed operational |
| 11:15 | Pharmacy System confirmed operational |
| 11:27 | All systems confirmed healthy |

---

## Root Cause

The Master Patient Index database primary node experienced a disk controller failure. The automatic failover to the standby node did not trigger because the heartbeat process was misconfigured after a maintenance window in October 2025.

---

## Contributing Factors

1. Heartbeat configuration was not validated after October maintenance
2. No monitoring for failover readiness
3. Patient Identity Service has no local cache for recent lookups
4. All clinical systems have synchronous dependency on Patient Identity Service

---

## Lessons Learned

**What went well:**
- Downtime procedures were activated within 10 minutes
- No patient safety events occurred
- Staff training on paper procedures was effective

**What went poorly:**
- Failover should have been automatic (45+ minutes to manual failover)
- Single point of failure in Patient Identity Service
- No degraded mode for clinical systems

---

## Action Items

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| Validate failover configuration monthly | Database Administration Team | Dec 1, 2025 | Complete |
| Add failover readiness monitoring | Infrastructure Team | Dec 15, 2025 | In Progress |
| Implement Patient Identity Service cache | Clinical Systems Team | Jan 30, 2026 | Planned |
| Add degraded mode to EHR | Clinical Systems Team | Feb 28, 2026 | Planned |
| Conduct failover drill | All Teams | Jan 15, 2026 | Planned |

---

## Regulatory Reporting

This incident was reported to:
- Ministry of Health: Case #MOH-2025-11-0234
- Hospital Quality Committee: Reviewed November 18, 2025
- HAAD (Health Authority Abu Dhabi): Notification submitted
