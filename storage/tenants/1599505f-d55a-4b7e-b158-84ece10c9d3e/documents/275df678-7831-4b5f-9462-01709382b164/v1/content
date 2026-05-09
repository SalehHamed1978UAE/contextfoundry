# SEC-001: SOC 2 Type II Report 2024

## System and Organization Controls (SOC) 2 Type II Report
### For MedSync Health's Digital Health Platform Services
---

**Document ID:** SEC-001  
**Report Date:** August 31, 2024  
**Reporting Period:** August 1, 2023, to July 31, 2024  
**Auditor:** Fictional Audit Firm, LLP (Independent Service Auditor)  
**MedSync Health Certification Status:** Renewed August 2024 (First certified August 2021)

---

## 1. Independent Service Auditor's Report

To the Management of MedSync Health:

We have examined MedSync Health's assertion regarding the description of its Digital Health Platform Services system and the suitability of the design and operating effectiveness of its controls to achieve the related control objectives based on the applicable Trust Services Criteria (TSC) set forth in the AICPA's *Trust Services Criteria for Security, Availability, and Confidentiality* (2017 version).

In our opinion, MedSync Health's description of its Digital Health Platform Services system was fairly presented, and the controls were suitably designed and operated effectively to provide reasonable assurance that the control objectives were achieved during the period August 1, 2023, to July 31, 2024.

## 2. Management's Assertion

MedSync Health's management asserts that the accompanying description of the Digital Health Platform Services system is presented fairly, and that the controls were suitably designed and operated effectively throughout the reporting period to achieve the control objectives related to the TSC for Security, Availability, and Confidentiality.

**MedSync Health Profile:**
MedSync Health is a leading **Healthcare Technology / Digital Health Platform** founded in January 2019. The company provides critical services, including the **MedSync Connect** hospital-clinic integration platform and the **MedSync Patient Portal**, which process sensitive patient data (ePHI).

## 3. Description of the MedSync Health Digital Health Platform Services System

### 3.1. System Components and Scope

The scope of this SOC 2 Type II report covers the infrastructure, software, people, procedures, and data relevant to the delivery of MedSync Health's core platform services, specifically **MedSync Connect (PROD-CONNECT)** and **MedSync Patient Portal (PROD-PORTAL)**.

**Key Technical Components:**
*   **Infrastructure:** AWS cloud environment, utilizing VPCs, security groups, and dedicated subnets for production workloads.
*   **Data Storage:** Encrypted databases (PostgreSQL, DynamoDB) using AWS KMS for key management. All ePHI is stored in dedicated, segregated environments.
*   **Application Layer:** Microservices architecture deployed via Kubernetes (EKS), managed through a CI/CD pipeline (GitLab, ArgoCD).
*   **Network Security:** Web Application Firewalls (WAF) and Intrusion Detection Systems (IDS) are deployed at the perimeter.

### 3.2. Compliance Context

MedSync Health maintains a robust, integrated compliance program. The SOC 2 Type II renewal in **August 2024** is a key component of this framework, which also includes:

| Compliance Standard | Certification/Implementation Date |
| :--- | :--- |
| **HIPAA Compliance** | Certified March 2020 |
| **GDPR Compliance** | Implemented May 2020 |
| **ISO 27001** | Certified November 2022 |

## 4. Applicable Trust Services Criteria and Control Activities

The following sections detail the control activities tested against the applicable Trust Services Criteria (TSC).

### 4.1. CC: Common Criteria (Security)

The security principle refers to the protection of the system against unauthorized access, use, or modification.

| Control ID | Control Description | Technical Specification & Cross-Reference |
| :--- | :--- | :--- |
| **CC6.1** | **Logical Access Control** | User access is managed via a centralized Identity Provider (IdP) and enforced through Role-Based Access Control (RBAC). Multi-Factor Authentication (MFA) is mandatory for all administrative and production access. |
| **CC6.2** | **Privileged Access Management (PAM)** | Privileged access to production environments is strictly limited, logged, and reviewed quarterly. Just-in-Time (JIT) access is implemented for break-glass scenarios. (See **SEC-011** for access control details) |
| **CC7.1** | **Change Management** | All changes to production systems are reviewed, tested, and approved via a formal Change Advisory Board (CAB) process. Automated vulnerability scanning is performed on all new code branches. |
| **CC7.2** | **Vulnerability Management** | Continuous vulnerability scanning is performed on all assets. Critical vulnerabilities (CVSS score > 9.0) are patched within 72 hours. Penetration tests are conducted annually by an independent third party. |
| **CC7.3** | **Intrusion Detection and Prevention** | Network traffic is monitored 24/7 by a Security Information and Event Management (SIEM) system. Automated alerts are generated for suspicious activity. (See **SEC-006** for Security Incident Reports) |

### 4.2. A: Availability

The availability principle refers to the system being available for operation and use as committed or agreed.

| Control ID | Control Description | Technical Specification & Cross-Reference |
| :--- | :--- | :--- |
| **A1.1** | **Performance Monitoring** | System performance and capacity are monitored in real-time. Automated scaling policies are in place to handle peak loads, ensuring a target uptime of 99.95% for core services. |
| **A1.2** | **Disaster Recovery (DR)** | A documented and tested Disaster Recovery Plan (DRP) is maintained. Production data is replicated across three Availability Zones (AZs) within the primary region. Full DR failover testing is conducted semi-annually. (See **OPS-003** for Business Continuity Plan) |
| **A1.3** | **Data Backup and Restoration** | Full backups of all production data are performed daily and retained for 90 days. Restoration procedures are tested monthly to ensure a Recovery Time Objective (RTO) of less than 4 hours for critical systems. |

### 4.3. C: Confidentiality

The confidentiality principle refers to the protection of information designated as confidential from unauthorized disclosure.

| Control ID | Control Description | Technical Specification & Cross-Reference |
| :--- | :--- | :--- |
| **C1.1** | **Data Encryption in Transit** | All data transmitted over public networks, including API calls and user sessions, is encrypted using TLS 1.2 or higher with strong cipher suites (e.g., AES-256). |
| **C1.2** | **Data Encryption at Rest** | All sensitive data, including ePHI and PII, is encrypted at rest using AES-256. Database encryption is managed via AWS KMS, with key rotation enforced every 90 days. |
| **C1.3** | **Data Retention and Disposal** | Data retention policies are strictly enforced in accordance with HIPAA and GDPR requirements. Data is securely purged using NIST 800-88 compliant methods upon expiration of the retention period. (See **LEGAL-005** for Data Retention Policy) |

## 5. Summary of Tests of Controls

The service auditor's tests of controls included, but were not limited to:
*   Reviewing documentation of policies and procedures.
*   Inspecting system configuration settings (e.g., security groups, IAM roles).
*   Observing the operation of controls (e.g., change management meetings, incident response drills).
*   Reperforming a sample of control activities (e.g., verifying user de-provisioning).

**Results:** The controls tested were found to be operating effectively throughout the reporting period. No exceptions were noted that would result in a qualified opinion.

---
*This document is for informational purposes only and should be read in conjunction with the Independent Service Auditor's full report.*
