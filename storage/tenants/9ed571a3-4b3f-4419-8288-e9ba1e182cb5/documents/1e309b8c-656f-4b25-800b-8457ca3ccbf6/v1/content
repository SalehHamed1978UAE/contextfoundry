# SEC-003: ISO 27001 Certification Statement

| Attribute | Value |
| :--- | :--- |
| **Document ID** | SEC-003 |
| **Title** | ISO/IEC 27001:2013 Certification Statement |
| **Version** | 1.1 |
| **Status** | Approved |
| **Classification** | Public |
| **Effective Date** | November 2022 |
| **Review Date** | November 2025 |
| **Author** | Manus AI (on behalf of MedSync Health CISO) |

---

## 1. Introduction and Purpose

This document confirms MedSync Health's successful implementation and certification of an Information Security Management System (ISMS) in accordance with the requirements of **ISO/IEC 27001:2013**. The purpose of this certification is to provide assurance to customers, partners, and regulatory bodies that MedSync Health manages information security risks effectively and maintains the confidentiality, integrity, and availability of its information assets.

MedSync Health achieved its initial ISO/IEC 27001:2013 certification in **November 2022**. This certification is maintained through a continuous program of internal audits, management reviews, and annual external surveillance audits.

## 2. Information Security Management System (ISMS) Scope

The ISMS covers the people, processes, and technology supporting the delivery and operation of MedSync Health's core product lines: MedSync Connect, MedSync Analytics, MedSync Patient Portal, and MedSync Compliance Suite.

**Scope Definition:**
The design, development, deployment, and maintenance of MedSync Health's cloud-based healthcare technology platform, including all associated infrastructure, data centers (AWS-hosted), and corporate IT systems, managed from the global headquarters in Boston, MA, and regional offices in London, Berlin, and Singapore.

**Exclusions:**
No major exclusions were taken against the ISO 27001:2013 standard. All controls in Annex A were considered, and applicable controls were implemented.

## 3. Statement of Applicability (SoA) Summary

The following table summarizes the implementation status of key control domains from ISO/IEC 27001:2013 Annex A, demonstrating the comprehensive nature of MedSync Health's security posture.

| Annex A Control Domain | Control Objective Summary | Key Technical Details & Cross-Reference |
| :--- | :--- | :--- |
| **A.5 Information Security Policies** | Establish management direction for information security. | Policies are reviewed annually and communicated to all personnel. See **SEC-001** for the overarching Information Security Policy. |
| **A.6 Organization of Information Security** | Establish a management framework to initiate and control the implementation of information security within the organization. | A dedicated Security Team reports directly to the CTO. Roles and responsibilities are defined in the ISMS Charter. |
| **A.9 Access Control** | Control access to information and information processing facilities. | Implementation of Role-Based Access Control (RBAC), Multi-Factor Authentication (MFA) for all remote access, and least privilege principles. See **SEC-011** for the detailed Access Control Policy. |
| **A.12 Operations Security** | Ensure the secure operation of information processing facilities. | Formal change management process (ITIL-aligned), capacity management, and malware protection across all endpoints and servers. |
| **A.14 System Acquisition, Development, and Maintenance** | Ensure that security is an integral part of information systems across the entire lifecycle. | Integration of security testing (SAST/DAST) into the CI/CD pipeline, and adherence to the Secure Software Development Lifecycle (SSDL). See **PROD-001** for SSDL details. |
| **A.16 Information Security Incident Management** | Manage information security incidents and weaknesses effectively. | A formal Security Incident Response Plan (SIRP) is in place, with mandatory annual tabletop exercises. Detailed incident reports are logged. See **SEC-006** for the Security Incident Reports and Response Plan. |
| **A.18 Compliance** | Avoid breaches of any criminal or civil law, statutory, regulatory, or contractual obligations, and any security requirements. | Integrated compliance program covering multiple regulatory frameworks, including HIPAA and GDPR. |

## 4. Technical Security Controls and Specifications

MedSync Health's ISMS is built upon a robust set of technical controls, including:

### 4.1. Cryptography and Key Management (A.10)
*   **Data at Rest:** All Protected Health Information (PHI) and sensitive customer data stored in AWS S3 and RDS is encrypted using **AES-256** with keys managed by **AWS Key Management Service (KMS)**.
*   **Data in Transit:** All external and internal communication channels utilize **TLS 1.2 or higher** with strong cipher suites (e.g., ECDHE-RSA-AES256-GCM-SHA384).

### 4.2. Network Security Management (A.13)
*   **Segmentation:** The production environment is logically segmented from corporate and development networks using **VPC and Subnet isolation** in AWS.
*   **Intrusion Detection:** A managed **IDS/IPS solution** (AWS GuardDuty and third-party WAF) is deployed at the perimeter and within the network to monitor for malicious activity.

### 4.3. Supplier Relationships (A.15)
*   All critical suppliers (e.g., AWS, monitoring services) are subject to a formal due diligence process, including review of their own security certifications (e.g., SOC 2, ISO 27001).

## 5. Integrated Compliance Framework

MedSync Health operates an integrated compliance framework, ensuring that the ISO 27001 ISMS aligns with and supports other critical regulatory and assurance requirements.

| Compliance Framework | Certification/Implementation Date | Scope of Coverage |
| :--- | :--- | :--- |
| **HIPAA Compliance** | Certified **March 2020** | US-based operations, handling of Protected Health Information (PHI) via MedSync Connect and Patient Portal. |
| **GDPR Compliance** | Implemented **May 2020** | EMEA-based operations, protection of personal data for EU residents. |
| **SOC 2 Type II** | First certified **August 2021**, renewed **August 2024** | Trust Services Criteria (Security, Availability, Confidentiality) for the MedSync Health platform. |
| **ISO 27001** | Certified **November 2022** | Global ISMS for all information assets and operations. |

This integrated approach ensures a single, unified set of security controls that satisfy the requirements of multiple standards, maximizing efficiency and consistency across the organization.

## 6. Management Commitment and Review

The MedSync Health leadership team, led by the CISO and CTO, is committed to the continuous improvement of the ISMS. The ISMS is formally reviewed by the Executive Management Team at least annually to ensure its continuing suitability, adequacy, and effectiveness.

---
*End of Document*
