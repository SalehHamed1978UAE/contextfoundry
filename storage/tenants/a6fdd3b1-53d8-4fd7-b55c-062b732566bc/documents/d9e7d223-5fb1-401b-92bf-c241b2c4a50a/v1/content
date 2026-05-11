# PROD-003: MedSync Patient Portal Product Specification

**Document ID:** PROD-003
**Title:** MedSync Patient Portal Product Specification
**Version:** 1.4
**Status:** Active
**Date:** January 17, 2026
**Author:** Product Management Team

---

## 1. Product Overview

The **MedSync Patient Portal (PROD-PORTAL)** is a secure, HIPAA-compliant patient engagement and communication platform designed to empower patients with direct access to their health information, scheduling tools, and communication channels with their care providers. It serves as the primary digital interface between MedSync's hospital and clinic clients and their patient populations, driving better health outcomes and operational efficiency.

### 1.1. Business Summary

| Metric | Value | Reference |
| :--- | :--- | :--- |
| **Product ID** | PROD-PORTAL | Master Data |
| **Launch Date** | June 2021 | Master Data |
| **Product Description** | Patient engagement and communication platform | Master Data |
| **FY 2024 Annual Recurring Revenue (ARR)** | AED 91,850,000 | Master Data |
| **Q4 2024 Net Promoter Score (NPS)** | 75 | See SALES-002 for NPS details |
| **Customer Organizations** | 380 Hospitals, 1,950 Clinics | Master Data |
| **FY 2024 Total Revenue** | AED 96,757,500 | See FIN-005 for detailed revenue breakdown |

### 1.2. Key Functional Areas

The MedSync Patient Portal is structured around four core functional modules:

1.  **Health Record Access:** Secure viewing and downloading of medical records, lab results, and clinical summaries.
2.  **Appointment Management:** Self-service scheduling, rescheduling, and cancellation of appointments.
3.  **Secure Messaging:** HIPAA-compliant direct communication with care teams.
4.  **Billing & Payments:** Reviewing statements and making secure payments.

---

## 2. Functional Specifications

### 2.1. Core Features

| Feature | Description | Status |
| :--- | :--- | :--- |
| **Single Sign-On (SSO)** | Integration with hospital/clinic identity providers (e.g., Active Directory, Okta) for seamless access. | Live (v1.0) |
| **Results Delivery** | Real-time push notifications and email alerts for new lab and imaging results. | Live (v1.1) |
| **Medication Refills** | Request and track prescription refills directly through the portal. | Live (v1.2) |
| **Telehealth Integration** | Direct launch of virtual visit sessions via embedded WebRTC client. | Live (v1.3) |
| **Proxy Access** | Ability for parents/guardians to manage the accounts of minors or dependents. | Live (v1.4) |

### 2.2. Data Integration and Interoperability

The portal is built on a robust API layer that ensures seamless data exchange with Electronic Health Record (EHR) systems.

| Integration Point | Standard | Status |
| :--- | :--- | :--- |
| **EHR Data Exchange** | FHIR R4 (Fast Healthcare Interoperability Resources) | Core |
| **Scheduling System** | HL7 v2.5 (ADT, SIU messages) | Core |
| **Billing System** | X12 EDI (835/837 transactions) | Core |
| **Major EHR Connectors** | Epic Systems, Cerner | See STRAT-004 for partnership details |

---

## 3. Technical Specifications

### 3.1. Architecture

The MedSync Patient Portal utilizes a modern microservices architecture deployed on AWS (Amazon Web Services).

*   **Frontend:** ReactJS with TypeScript, served via AWS CloudFront CDN.
*   **Backend:** Python (Flask/FastAPI) microservices, containerized with Docker.
*   **Database:** PostgreSQL (RDS) for transactional data; DynamoDB for session and non-relational data.
*   **API Gateway:** AWS API Gateway for request routing, security, and throttling.
*   **Security:** OAuth 2.0 and OpenID Connect for authentication; all data is encrypted at rest (AES-256) and in transit (TLS 1.3).

### 3.2. Compliance and Security

The platform is designed and operated in strict adherence to global healthcare and data privacy regulations.

| Standard | Certification/Compliance | Date Achieved | Reference |
| :--- | :--- | :--- | :--- |
| **Data Privacy** | HIPAA Compliant | March 2020 | See SEC-001 |
| **Security Controls** | SOC 2 Type II | Renewed August 2024 | See SEC-002 |
| **Information Security** | ISO 27001 Certified | November 2022 | See SEC-003 |
| **EU Data Protection** | GDPR Compliant | May 2020 | See LEGAL-005 |

### 3.3. Performance Metrics (Target SLA)

| Metric | Target |
| :--- | :--- |
| **API Response Time (P95)** | < 250ms |
| **Uptime (Monthly)** | 99.99% |
| **Concurrent Users** | 50,000+ |
| **Data Throughput** | 10,000 transactions/second |

---

## 4. Version History

| Version | Release Date | Key Changes |
| :--- | :--- | :--- |
| **1.0** | June 2021 | Initial Launch: Basic record viewing and secure messaging. |
| **1.1** | October 2021 | Added lab results delivery and notification system. |
| **1.2** | March 2022 | Integrated self-service appointment scheduling and cancellation. |
| **1.3** | September 2022 | Introduced integrated telehealth module (WebRTC). |
| **1.4** | May 2023 | Enhanced Proxy Access features and improved mobile responsiveness. |
| **1.5** | Q1 2025 (Planned) | **Roadmap:** Integration of AI-driven symptom checker and personalized health insights. |

---

## 5. Financial Context

The MedSync Patient Portal is a high-growth product, demonstrating strong customer satisfaction (NPS 75) and significant revenue contribution. Its revenue growth trajectory for FY 2024 is detailed below:

| Quarter | Revenue (AED) | % of Total FY 2024 Revenue |
| :--- | :--- | :--- |
| **Q1 2024** | 22,522,500 | 23.28% |
| **Q2 2024** | 23,520,000 | 24.31% |
| **Q3 2024** | 24,990,000 | 25.83% |
| **Q4 2024** | 25,725,000 | 26.58% |
| **FY 2024 Total** | 96,757,500 | 100.00% |

The high NPS score reflects the product's success in improving patient engagement, which directly correlates with higher retention rates (See HR-003 for employee satisfaction data, which impacts service quality). The product's success is a key driver for the company's overall Net Revenue Retention (NRR) of 118%.

---

## 6. Future Direction (High-Level Roadmap)

The 2025 roadmap focuses on leveraging AI and expanding the platform's utility beyond basic communication.

| Quarter | Focus Area | Key Features |
| :--- | :--- | :--- |
| **Q1 2025** | Personalized Health | AI-driven symptom checker, integration with wearable devices (Apple Health, Google Fit). |
| **Q2 2025** | Care Coordination | Shared care plans with non-MedSync providers, in-app referral tracking. |
| **Q3 2025** | Patient Education | Interactive educational modules, personalized content based on diagnosis. |
| **Q4 2025** | Global Expansion | Localization for EMEA and APAC regions, multi-language support (Arabic, German, Mandarin). |
