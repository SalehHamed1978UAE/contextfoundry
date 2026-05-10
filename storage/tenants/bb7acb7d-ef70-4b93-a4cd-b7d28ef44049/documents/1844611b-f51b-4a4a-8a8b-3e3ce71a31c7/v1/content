# SEC-004: GDPR Policy and Procedures

| Attribute | Value |
| :--- | :--- |
| **Document ID** | SEC-004 |
| **Title** | GDPR Policy and Procedures |
| **Version** | 1.2 |
| **Effective Date** | May 25, 2020 |
| **Last Review Date** | January 15, 2026 |
| **Owner** | General Counsel (Robert Foster) |
| **Applicability** | All MedSync Health employees, contractors, and systems processing EU/EEA personal data. |

## 1. Introduction and Scope

The General Data Protection Regulation (GDPR) (Regulation (EU) 2016/679) is a comprehensive data protection law that governs the processing of personal data of individuals in the European Union (EU) and European Economic Area (EEA). MedSync Health, with offices in London, UK, and Berlin, Germany, is committed to full compliance with the GDPR as both a Data Controller and a Data Processor.

This policy outlines the procedures and technical and organizational measures (TOMs) MedSync Health has implemented to ensure compliance with the GDPR. **GDPR Compliance was formally implemented across all relevant systems and processes in May 2020**, coinciding with the launch of the MedSync Connect platform (PROD-CONNECT), which handles sensitive patient data.

## 2. Principles of Data Processing

MedSync Health adheres to the seven core principles of data processing as defined by Article 5 of the GDPR:

| Principle | MedSync Health Implementation |
| :--- | :--- |
| **Lawfulness, Fairness, and Transparency** | Processing is based on a lawful basis (e.g., consent, contract, legitimate interest) and is clearly documented in the Privacy Notice. |
| **Purpose Limitation** | Personal data is collected for specified, explicit, and legitimate purposes and not further processed in a manner that is incompatible with those purposes. |
| **Data Minimization** | Only data strictly necessary for the specified purpose is collected and processed. Data retention schedules are defined in **SEC-009: Data Retention Policy**. |
| **Accuracy** | Procedures are in place to ensure personal data is accurate and kept up to date. Data subjects have the right to rectification. |
| **Storage Limitation** | Personal data is stored only for as long as necessary. Automated deletion and anonymization routines are implemented. |
| **Integrity and Confidentiality** | Processing is secured using appropriate technical and organizational measures (TOMs). |
| **Accountability** | The Data Protection Officer (DPO) oversees compliance, and records of processing activities (RoPA) are maintained. |

## 3. Data Subject Rights Procedures

MedSync Health has established formal procedures for handling Data Subject Access Requests (DSARs) within the one-month statutory timeframe.

| Data Subject Right | Procedure Summary | Technical Control |
| :--- | :--- | :--- |
| **Right of Access (SAR)** | Requests are logged in the Compliance Suite (PROD-COMPLIANCE) and fulfilled by the Data Governance team, providing a copy of all processed personal data. | Automated data retrieval scripts from all primary data stores (PostgreSQL, S3). |
| **Right to Rectification** | Data quality team updates inaccurate data within 7 days of verification. | Role-Based Access Control (RBAC) ensures only authorized personnel can modify production data (See **SEC-011: Access Control Policy**). |
| **Right to Erasure ("Right to be Forgotten")** | Data is permanently deleted from production and backup systems. Deletion is logged and auditable. | Cryptographic shredding of data blocks and secure deletion of keys. Deletion confirmation is provided to the data subject. |
| **Right to Restriction of Processing** | Data is logically segregated and marked as restricted in the database. | Database-level flags and application logic prevent further processing until restriction is lifted. |
| **Right to Data Portability** | Data is provided in a structured, commonly used, and machine-readable format (e.g., JSON or CSV). | API endpoint for data export, secured via OAuth 2.0 and mutual TLS. |
| **Right to Object** | Processing is halted immediately, pending review of the objection's grounds. | Audit logs track the cessation of processing activities. |

## 4. Technical and Organizational Measures (TOMs)

MedSync Health maintains a robust security posture, evidenced by its certifications, to protect personal data.

### 4.1. Data Security and Encryption
All personal data (PD) and special categories of personal data (SCPD) are protected both in transit and at rest.

*   **Encryption in Transit:** All network communication, including API calls and user access to MedSync platforms (PROD-CONNECT, PROD-PORTAL), is secured using TLS 1.2 or higher with strong cipher suites (e.g., AES-256).
*   **Encryption at Rest:** All production databases and file storage systems (e.g., AWS S3 buckets) are encrypted using AES-256. Data is encrypted using a hierarchical key management system, with keys managed by AWS KMS and rotated quarterly.
*   **Pseudonymization:** Where possible, identifiers are replaced with pseudonyms to reduce the linkability of data to a specific data subject. This is a core feature of the MedSync Analytics platform (PROD-ANALYTICS).

### 4.2. Access Control and Audit
Access to systems processing personal data is strictly controlled.

*   **Principle of Least Privilege:** Access is granted only on a need-to-know basis. This is enforced via our Identity and Access Management (IAM) system. (Refer to **SEC-011: Access Control Policy** for detailed procedures).
*   **Multi-Factor Authentication (MFA):** MFA is mandatory for all administrative access and for all employees accessing production environments.
*   **Audit Logging:** All access, modification, and deletion events related to personal data are logged and retained for a minimum of 12 months. Logs are monitored 24/7 for suspicious activity.

### 4.3. Compliance Context
MedSync Health's commitment to data security is independently verified:
*   **ISO 27001 Certification:** Certified in **November 2022**. This Information Security Management System (ISMS) provides the framework for our TOMs.
*   **SOC 2 Type II Attestation:** First certified in **August 2021** and successfully renewed in **August 2024**. This attestation covers the Trust Services Criteria of Security, Availability, and Confidentiality.
*   **HIPAA Compliance:** Certified in **March 2020**. This ensures the protection of Protected Health Information (PHI), which overlaps significantly with GDPR's SCPD.

## 5. Data Breach Notification and Incident Response

In the event of a personal data breach, MedSync Health follows a defined Incident Response Plan.

*   **Internal Reporting:** All employees are required to report suspected security incidents immediately to the Security Operations Center (SOC).
*   **Incident Management:** The full procedure for handling, investigating, and resolving security incidents is detailed in **SEC-006: Security Incident Reports and Response Plan**.
*   **Notification to Supervisory Authority:** Where a breach is likely to result in a risk to the rights and freedoms of natural persons, MedSync Health will notify the relevant Supervisory Authority (e.g., the ICO or the BfDI) **without undue delay and, where feasible, not later than 72 hours** after becoming aware of it.
*   **Notification to Data Subjects:** When the personal data breach is likely to result in a high risk to the rights and freedoms of natural persons, the data subjects will be notified without undue delay.

## 6. Data Protection Impact Assessments (DPIAs) and Privacy by Design

MedSync Health integrates privacy considerations into the entire lifecycle of its products and services.

*   **Privacy by Design:** All new projects, systems, and product features (e.g., the MedSync Compliance Suite, PROD-COMPLIANCE) undergo a mandatory Privacy by Design review before development begins.
*   **DPIA Requirement:** A formal Data Protection Impact Assessment (DPIA) is conducted for any processing operation that is likely to result in a high risk to the rights and freedoms of natural persons. This includes the deployment of new large-scale data processing technologies or systems involving special categories of personal data. DPIA records are maintained for five years.

## 7. International Data Transfers

MedSync Health transfers personal data between its global offices (Boston, London, Berlin, Singapore) and to its cloud service providers.

*   **EU-US Transfers:** For transfers to the US (e.g., to the Boston HQ and US-based cloud infrastructure), MedSync Health relies on the EU-US Data Privacy Framework (DPF) certification, or, as a fallback, the implementation of the European Commission's **Standard Contractual Clauses (SCCs)**, coupled with supplementary measures to ensure an essentially equivalent level of protection to that guaranteed under the GDPR.
*   **Intra-Group Transfers:** Transfers between MedSync Health entities are governed by an Intra-Group Data Transfer Agreement incorporating the SCCs.
*   **Vendor Management:** All third-party vendors processing personal data on MedSync Health's behalf are subject to a Data Processing Agreement (DPA) that mandates GDPR compliance and includes the necessary SCCs where applicable. (Refer to **SEC-012: Third-Party Risk Management Policy**).
