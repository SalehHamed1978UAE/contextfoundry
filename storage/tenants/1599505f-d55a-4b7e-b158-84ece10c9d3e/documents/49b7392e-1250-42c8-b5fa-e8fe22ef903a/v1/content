# SEC-011: Access Control Policy

**Version:** 1.1
**Effective Date:** January 1, 2026
**Review Date:** January 1, 2027
**Owner:** Chief Information Security Officer (CISO)
**Document ID:** SEC-011

## 1. Introduction and Purpose

The purpose of this **Access Control Policy** is to establish the requirements for managing and controlling access to MedSync Health's information systems, applications, and data assets, including all forms of Protected Health Information (PHI) and Personally Identifiable Information (PII). This policy ensures that access is granted strictly on a **need-to-know** and **least privilege** basis, thereby protecting the confidentiality, integrity, and availability of all sensitive data.

This policy is a foundational component of MedSync Health's overall Information Security Management System (ISMS) and must be read in conjunction with the **Information Security Policy (SEC-001)** and the **Data Classification Policy (SEC-010)**.

## 2. Scope

This policy applies to all MedSync Health employees, contractors, temporary staff, and third-party vendors who are granted access to MedSync Health's corporate network, systems, and data, regardless of location or device used. This includes all systems supporting the MedSync Connect, MedSync Analytics, MedSync Patient Portal, and MedSync Compliance Suite product lines.

## 3. Compliance Framework

MedSync Health maintains a robust compliance posture, and this policy is designed to meet the stringent requirements of multiple regulatory and industry standards. The dates below reflect MedSync Health's commitment to continuous compliance.

| Standard/Regulation | Status | Date of Certification/Implementation | Relevance to Access Control |
| :--- | :--- | :--- | :--- |
| **HIPAA** (Health Insurance Portability and Accountability Act) | Certified | March 2020 | Requires technical safeguards to protect ePHI, including access control mechanisms (45 CFR 164.312(a)(1)). |
| **GDPR** (General Data Protection Regulation) | Implemented | May 2020 | Mandates data minimization and purpose limitation, enforced through strict access controls (Article 5). |
| **SOC 2 Type II** | Renewed Certification | August 2024 (First certified August 2021) | Addresses the Trust Services Criteria of Security, Availability, and Confidentiality, with a focus on logical access controls. |
| **ISO 27001** | Certified | November 2022 | Aligns with Annex A controls, specifically A.9 (Access Control) and A.13 (Communications Security). |

## 4. Access Control Principles

### 4.1. Least Privilege

All users shall be granted the minimum level of access necessary to perform their assigned job functions. Default access for all systems is **Deny-All**. Access requests must be justified by a business need and approved by the resource owner and the user's direct manager.

### 4.2. Role-Based Access Control (RBAC)

Access to all major systems and applications must be managed using a formal **Role-Based Access Control (RBAC)** model. Roles must be defined based on job function, not individual identity, and mapped to specific permissions. The CISO team maintains the master list of approved roles and their associated permissions, as detailed in the **Data Classification Policy (SEC-010)**.

### 4.3. Segregation of Duties (SoD)

Critical functions, particularly those involving financial transactions, system administration, and production data access, must be separated to prevent a single individual from controlling an entire process. The system must enforce SoD where technically feasible.

## 5. Technical Access Controls

### 5.1. Authentication Requirements

1.  **Multi-Factor Authentication (MFA):** MFA is mandatory for all remote access, all privileged accounts, and all access to systems containing **Confidential** or **Restricted** data (as defined in SEC-010), including PHI and PII.
2.  **Password Policy:** All passwords must comply with the requirements set forth in the **Acceptable Use Policy (SEC-005)**, including minimum length, complexity, and maximum age.
3.  **Single Sign-On (SSO):** Where possible, access must be federated through MedSync Health's centralized Identity Provider (IdP) to ensure consistent policy enforcement and centralized logging.

### 5.2. Privileged Access Management (PAM)

1.  **Dedicated Accounts:** Privileged access (e.g., system administrators, database administrators) must use dedicated, non-personal accounts.
2.  **Just-in-Time (JIT) Access:** Access to production environments and critical infrastructure must be granted using a JIT model, requiring explicit approval and automatically revoking access after a defined time limit (maximum 4 hours).
3.  **Session Monitoring:** All privileged sessions must be recorded, monitored, and audited by the Security Operations Center (SOC) team.

### 5.3. Network Access Control

1.  **VPN Requirement:** All remote access to the internal network must be conducted via a secure, company-provided Virtual Private Network (VPN) solution that enforces device posture checks.
2.  **Firewall Rules:** Network segmentation must be enforced to isolate environments (e.g., Development, Staging, Production) and restrict traffic flow based on the principle of least functionality.

## 6. Access Lifecycle Management

### 6.1. User Provisioning

Access provisioning must be initiated by a formal request, approved by the manager and system owner, and executed by the IT or Security team. Access must be granted only after the user has acknowledged the **Acceptable Use Policy (SEC-005)**.

### 6.2. Access Review and Recertification

All user access rights must be formally reviewed and recertified by the resource owner and the user's manager at a minimum frequency defined below:

| Account Type | Review Frequency | Reviewer |
| :--- | :--- | :--- |
| **Standard User Accounts** | Quarterly (Every 90 days) | Manager |
| **Privileged Accounts** | Monthly (Every 30 days) | System Owner & CISO Team |
| **Third-Party/Vendor Accounts** | Upon Contract Renewal (Minimum Semi-Annually) | Vendor Manager & CISO Team |

### 6.3. User De-provisioning

Upon termination of employment or contract, all access rights must be revoked immediately. The de-provisioning process must be completed within **one (1) hour** of notification of termination. The CISO team must audit the de-provisioning log monthly.

## 7. Policy Enforcement

Any violation of this policy may result in disciplinary action, up to and including termination of employment or contract, and may result in legal action. All access control violations are logged and reported to the Security Incident Response Team (SIRT) for investigation, as per the **Security Incident Reports (SEC-006)** procedure.

---
*End of Document*
