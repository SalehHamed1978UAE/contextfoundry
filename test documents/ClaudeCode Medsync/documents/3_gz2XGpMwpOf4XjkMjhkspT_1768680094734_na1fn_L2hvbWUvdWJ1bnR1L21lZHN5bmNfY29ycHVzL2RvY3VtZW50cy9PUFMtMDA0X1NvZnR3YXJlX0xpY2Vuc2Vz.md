# OPS-004: Software Licenses Policy and Management

**Document ID:** OPS-004
**Title:** Software Licenses Policy and Management
**Version:** 1.0
**Effective Date:** 2026-01-17
**Owner:** Operations Department (IT Infrastructure)
**Approver:** James Thompson, COO

---

## 1. Introduction and Purpose

This document establishes the policy and procedures for the acquisition, deployment, management, and retirement of all software licenses used by MedSync Health. The primary goal is to ensure compliance with vendor licensing agreements, optimize software expenditure, and mitigate legal and financial risks associated with unauthorized software use.

This policy applies to all employees, contractors, and third-party vendors who utilize MedSync Health's computing resources or proprietary software. Compliance with this policy is mandatory and is overseen by the Operations Department, specifically the IT Infrastructure team.

## 2. Scope and Governance

### 2.1. Scope

The scope of this policy covers all software, whether commercial off-the-shelf (COTS), open-source, or custom-developed, that requires a license or subscription for use within the MedSync Health environment. This includes, but is not limited to:

*   Operating Systems and Virtualization Software.
*   Productivity and Collaboration Suites (e.g., Microsoft 365).
*   Specialized Line-of-Business Applications (e.g., CRM, ERP, Development Tools).
*   Security and Compliance Software.

### 2.2. Governance and Responsibility

The **Operations Department** is the central authority for Software Asset Management (SAM). The **Chief Operating Officer (COO)**, James Thompson, holds ultimate accountability for the AED 44,160,000 Operations budget, which includes a significant portion for software licensing [1].

| Role/Department | Responsibility |
| :--- | :--- |
| **IT Infrastructure Team** (Operations) | Centralized management of the SAM program, license procurement, deployment, tracking, and annual audits. |
| **Department Heads** | Budgeting for department-specific software needs and ensuring their teams comply with license usage terms. |
| **Finance & Legal** | Reviewing and approving all software contracts, ensuring financial compliance, and managing vendor relationships. |
| **All Employees** | Adhering to the terms of use for all licensed software and reporting any unauthorized use or compliance concerns. |

## 3. Software License Lifecycle Procedures

### 3.1. Request and Approval

All requests for new software or additional licenses must be submitted through the designated IT Service Management (ITSM) platform.

1.  **Justification:** The requester must provide a clear business case, including the number of required seats, the department (aligned with the 8 total departments), and the estimated annual cost.
2.  **Budget Review:** The request is routed to the relevant Department Head (e.g., Engineering, Sales) for budget approval.
3.  **Technical Review:** The IT Infrastructure Team assesses technical compatibility, security risks (cross-reference to SEC-001), and integration requirements.
4.  **Procurement:** Once approved, the IT Infrastructure Team, in coordination with the Finance & Legal department (65 employees), executes the purchase order and contract.

### 3.2. Deployment and Tracking

All licensed software must be deployed and tracked using the centralized SAM system.

*   **Deployment:** Software is deployed via standardized images or centralized deployment tools to ensure proper installation and configuration across all 4 global offices (Boston, London, Berlin, Singapore).
*   **Tracking:** The SAM system maintains a real-time inventory of license keys, activation status, and assigned users (aligned with the total 1,200 employees).

### 3.3. Audit and Optimization

The IT Infrastructure Team conducts quarterly internal audits and an annual comprehensive audit to ensure compliance and identify optimization opportunities.

*   **Reclamation:** Licenses that have not been used for 90 consecutive days are flagged for reclamation and reassignment.
*   **True-Up:** Annual true-up processes are managed to align license counts with current headcount (1,200 total) and departmental needs.

## 4. Key Software License Inventory

The following table details the major software licenses held by MedSync Health, with costs expressed in AED, aligned with the master data model [1].

| Software Name | Category | License Type | Total Seats | Annual Cost (AED) | Primary Allocation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Microsoft 365 Enterprise** | Productivity & Collaboration | E3 Subscription | 1,200 | 1,440,000 | All Employees (1,200) |
| **Salesforce Health Cloud** | Customer Relationship Management (CRM) | Professional | 220 | 880,000 | Sales Department (220) |
| **JetBrains All Products Pack** | Software Development Tools | Floating | 380 | 1,900,000 | Engineering Department (380) |
| **Adobe Creative Cloud** | Design & Marketing | Named User | 85 | 425,000 | Marketing Department (85) |
| **Workday HCM** | Human Capital Management (HCM) | Per Employee | 1,200 | 720,000 | HR & People (55) and All Employees |
| **SAP S/4HANA Cloud** | Enterprise Resource Planning (ERP) | Named User | 65 | 650,000 | Finance & Legal (65) |
| **CrowdStrike Falcon** | Endpoint Security | Per Endpoint | 1,200 | 960,000 | All Endpoints (1,200) |
| **Vanta** | Compliance Automation | Per Employee | 1,200 | 480,000 | Compliance (Cross-reference to SEC-002) |
| **AWS Enterprise Support** | Cloud Infrastructure | Annual Contract | N/A | 3,675,000 | IT Infrastructure (Cross-reference to OPS-003) |
| **Zoom Enterprise** | Video Conferencing | Business | 1,200 | 360,000 | All Employees (1,200) |
| **Total Estimated Annual Software License Cost** | | | | **11,490,000 AED** | |

### 4.1. License Allocation by Office

License allocation is primarily driven by departmental need, but the following table shows the distribution of the 1,200 total seats across the four global offices, which is critical for regional compliance and deployment planning.

| Office Location | Employee Headcount | Percentage of Total | Key Regional Compliance Consideration |
| :--- | :--- | :--- | :--- |
| **Boston (HQ)** | 650 | 54.2% | US Federal and State Regulations (HIPAA) |
| **London** | 280 | 23.3% | UK Data Protection Act, GDPR |
| **Berlin** | 150 | 12.5% | German Federal Data Protection Act (BDSG), GDPR |
| **Singapore** | 120 | 10.0% | Singapore Personal Data Protection Act (PDPA) |
| **Total** | **1,200** | **100.0%** | |

## 5. Compliance and Auditing

### 5.1. Policy Violations

Any employee found to be in violation of this policy, including the installation of unauthorized software or the misuse of licensed software, will be subject to disciplinary action, as outlined in the **HR-001: Employee Code of Conduct** [2].

### 5.2. Open Source Software

The use of Open Source Software (OSS) is permitted, provided that the license terms (e.g., MIT, GPL, Apache) are reviewed and approved by the Engineering and Legal departments to ensure no conflict with MedSync Health's proprietary product lines (PROD-CONNECT, PROD-ANALYTICS, etc.) [1].

## 6. Cross-Reference to Related Documents

*   **OPS-003: IT Infrastructure and Cloud Services:** Details the AWS usage and server counts, which directly impact the AWS Enterprise Support license.
*   **HR-001: Employee Code of Conduct:** Contains the disciplinary procedures for policy violations.
*   **SEC-001: Information Security Policy:** Outlines the security requirements for all software and systems.
*   **SEC-002: Regulatory Compliance Framework:** Details the requirements for HIPAA, ISO 27001, and GDPR compliance, which Vanta and other software support.

---

## References

[1] MedSync Health - Master Data Consistency Framework. `/home/ubuntu/medsync_corpus/master_data_model.md`
[2] HR-001: Employee Code of Conduct. (Fictional Cross-Reference)
[3] SEC-001: Information Security Policy. (Fictional Cross-Reference)
[4] OPS-003: IT Infrastructure and Cloud Services. (Fictional Cross-Reference)
[5] SEC-002: Regulatory Compliance Framework. (Fictional Cross-Reference)
