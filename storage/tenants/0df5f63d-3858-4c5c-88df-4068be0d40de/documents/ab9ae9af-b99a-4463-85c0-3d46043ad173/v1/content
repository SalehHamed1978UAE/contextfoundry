# SEC-007: Vendor Risk Assessment Framework

**Document ID:** SEC-007
**Title:** Vendor Risk Assessment Framework
**Version:** 1.0
**Effective Date:** 2026-01-17
**Owner:** VP of Operations (James Thompson)
**Approver:** Information Security Steering Committee

---

## 1. Introduction and Purpose

The **Vendor Risk Assessment Framework (VRAF)** defines the structured process by which MedSync Health identifies, assesses, and mitigates risks associated with third-party vendors, suppliers, and service providers. This framework is critical to protecting MedSync Health's sensitive data, including Protected Health Information (PHI) and Personally Identifiable Information (PII), and ensuring continuous compliance with regulatory obligations.

The primary objectives of this framework are to:
*   Establish a consistent, repeatable, and scalable process for vendor due diligence.
*   Ensure that all third parties with access to MedSync Health systems or data maintain a security posture commensurate with the risk they pose.
*   Maintain compliance with relevant regulatory standards, including HIPAA and GDPR.

## 2. Scope and Applicability

This framework applies to **all** current and prospective third-party vendors engaged by MedSync Health, regardless of their location, that:
1.  Have access to MedSync Health's internal network, systems, or applications.
2.  Process, store, or transmit MedSync Health's sensitive data (PHI, PII, financial data).
3.  Provide a service that is critical to MedSync Health's business operations or service delivery.

## 3. Vendor Risk Tiers and Assessment Frequency

Vendors are categorized into three tiers based on the criticality of the service they provide and their level of access to sensitive data. This tiering dictates the rigor and frequency of the required risk assessment.

| Risk Tier | Description | Data Access Level | Assessment Frequency | Required Documentation |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (Critical)** | Access to PHI/PII, or provides a mission-critical service (e.g., cloud hosting, EHR integration). | High (PHI/PII, Financial) | Annual, plus ad-hoc | Full Security Questionnaire, SOC 2 Report, Penetration Test Summary |
| **Tier 2 (Standard)** | Access to non-sensitive internal data, or provides a non-critical service (e.g., HR platform, marketing automation). | Medium (Internal Data) | Biennial (Every 2 years) | Standard Security Questionnaire, Attestation of Compliance |
| **Tier 3 (Low)** | No access to MedSync systems or data (e.g., office supplies, non-IT consulting). | None | Initial Due Diligence Only | Basic Questionnaire |

## 4. Technical Security Assessment Criteria

For Tier 1 and Tier 2 vendors, the Information Security team performs a detailed technical review focused on the following domains. The vendor must demonstrate adherence to the controls outlined in the **Information Security Policy (SEC-001)**.

### 4.1. Data Protection and Encryption
*   **Data-at-Rest:** All sensitive data must be encrypted using industry-standard algorithms (e.g., AES-256). Encryption keys must be managed securely and separately from the data.
*   **Data-in-Transit:** All data transmission between MedSync Health and the vendor, and within the vendor's environment, must use secure protocols (TLS 1.2 or higher) with strong cipher suites.
*   **Data Segregation:** For multi-tenant environments, logical and technical controls must ensure complete segregation of MedSync Health data from other clients.

### 4.2. Access Control and Identity Management
*   **Principle of Least Privilege:** Vendor access must be provisioned based on the minimum necessary permissions to perform the service.
*   **Multi-Factor Authentication (MFA):** MFA is mandatory for all remote access to systems containing MedSync Health data.
*   **Access Review:** Vendors must provide evidence of regular (quarterly) internal access reviews. (See **SEC-011: Access Control Policy** for MedSync's internal standards).

### 4.3. Security Operations and Incident Response
*   **Vulnerability Management:** Vendors must maintain a formal vulnerability management program, including monthly scanning and remediation of critical vulnerabilities within 7 days.
*   **Security Monitoring:** 24/7 security monitoring (SIEM/IDS/IPS) must be in place for all systems processing MedSync Health data.
*   **Incident Reporting:** Vendors must agree to report any security incident or breach affecting MedSync Health data within **24 hours** of discovery. (Cross-reference with **SEC-006: Security Incident Response Plan**).

## 5. Compliance and Regulatory Requirements

MedSync Health requires all vendors to comply with applicable laws and regulations, especially those governing healthcare data. The VRAF requires vendors to provide evidence of their own compliance and certification status.

| Standard/Regulation | MedSync Health Status | Vendor Requirement |
| :--- | :--- | :--- |
| **HIPAA (Health Insurance Portability and Accountability Act)** | Certified March 2020 | Mandatory for all vendors handling PHI. Requires a signed Business Associate Agreement (BAA). |
| **GDPR (General Data Protection Regulation)** | Implemented May 2020 | Mandatory for all vendors processing data of EU residents. Requires adherence to Data Processing Addendum (DPA). |
| **SOC 2 Type II** | First certified August 2021, renewed August 2024 | Mandatory for Tier 1 vendors. Report must cover the relevant Trust Services Criteria (Security, Availability, Confidentiality). |
| **ISO 27001 (Information Security Management)** | Certified November 2022 | Highly recommended for Tier 1 vendors; required for international data processing. |

## 6. Risk Mitigation and Off-Boarding

### 6.1. Risk Mitigation
If a vendor assessment identifies high-risk findings, a formal **Risk Treatment Plan (RTP)** must be agreed upon. The RTP must include:
*   Specific remediation actions.
*   Responsible parties within the vendor organization.
*   A clear timeline for completion (e.g., 30, 60, or 90 days).
*   A follow-up verification process by the MedSync Health Information Security team.

### 6.2. Off-Boarding
Upon contract termination, the vendor off-boarding process must ensure the secure return or destruction of all MedSync Health data. This includes:
*   A formal written attestation from the vendor confirming data destruction.
*   Immediate revocation of all user accounts and system access (See **SEC-011**).
*   A final review by the VRM team to confirm all contractual obligations regarding data handling have been met.

---

## Document Control

| Revision | Date | Description | Author |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-01-17 | Initial Release | Manus AI |

## Cross-Reference Index

*   **SEC-001:** Information Security Policy
*   **SEC-006:** Security Incident Response Plan
*   **SEC-011:** Access Control Policy
