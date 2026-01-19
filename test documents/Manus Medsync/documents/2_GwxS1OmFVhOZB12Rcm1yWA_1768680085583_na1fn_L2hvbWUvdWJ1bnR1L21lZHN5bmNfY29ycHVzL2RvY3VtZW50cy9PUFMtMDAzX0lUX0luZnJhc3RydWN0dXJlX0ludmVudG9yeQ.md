# OPS-003: IT Infrastructure Inventory

| Metadata | Detail |
| :--- | :--- |
| **Document ID** | OPS-003 |
| **Title** | IT Infrastructure Inventory |
| **Version** | 1.0 |
| **Status** | Approved |
| **Effective Date** | 2026-01-17 |
| **Owner** | Chief Technology Officer (CTO), Priya Patel |
| **Related Documents** | SEC-001 (Information Security Policy), OPS-002 (Office Leases), HR-001 (Employee Policies) |

## 1. Introduction

### 1.1. Purpose and Scope

This document provides a comprehensive inventory and overview of the information technology (IT) infrastructure supporting MedSync Health's global operations and product suite. The scope includes all cloud-based services, on-premise hardware, network topology, and key enterprise applications utilized by the company's **1,200 employees** [1]. This inventory serves as a foundational reference for IT operations, security, compliance, and financial planning.

### 1.2. References

| Ref | Document ID | Title |
| :--- | :--- | :--- |
| [1] | STRAT-001 | MedSync Health Master Data Model |
| [2] | SEC-001 | Information Security Policy |
| [3] | FIN-003 | Annual IT Budget and Spend Report |
| [4] | HR-001 | Employee Handbook and Policies |

## 2. Global IT Footprint

MedSync Health operates a hybrid infrastructure model, prioritizing cloud-native solutions for product delivery and maintaining minimal, standardized on-premise infrastructure to support local office connectivity and end-user computing.

### 2.1. Office Locations and Headcount

The infrastructure is distributed across four primary global offices, each with dedicated network and end-user support infrastructure.

| Location | Region | Headcount [1] | Primary Function |
| :--- | :--- | :--- | :--- |
| **Boston, MA (HQ)** | North America | 650 | Executive, Engineering, Product, Sales |
| **London, UK** | EMEA | 280 | Sales, Customer Success, Operations |
| **Berlin, Germany** | EMEA | 150 | Engineering, R&D |
| **Singapore** | APAC | 120 | Sales, Customer Success, Support |
| **Total** | | **1,200** | |

### 2.2. Network and Connectivity

The global network utilizes a **Software-Defined Wide Area Network (SD-WAN)** architecture to ensure secure, high-performance connectivity between all four offices and the primary cloud environment.

*   **Inter-Office Connectivity:** Dedicated VPN tunnels and SD-WAN fabric.
*   **Local Area Network (LAN):** Standardized 802.1X authentication and VLAN segmentation in all offices.
*   **On-Premise Servers:** Each office maintains a small footprint of approximately 10-15 physical servers for local services (e.g., Active Directory, DNS, Print Services, Network Access Control). **Total physical server count is 55.**

## 3. Cloud Infrastructure Inventory

MedSync Health's core product suite and enterprise applications are hosted exclusively on **Amazon Web Services (AWS)**, leveraging the company's participation in the AWS Healthcare Accelerator [1].

### 3.1. AWS Account Structure

The AWS environment is structured into a multi-account organization for security, billing, and compliance separation.

| Account Name | Primary Region | Purpose | Compliance Scope |
| :--- | :--- | :--- | :--- |
| **Production** | us-east-1 (Primary) | Hosting of all four MedSync product lines. | SOC 2, HIPAA, ISO 27001 |
| **Staging/QA** | us-east-1 | Pre-production testing and quality assurance. | SOC 2 |
| **Development** | eu-central-1 | Developer sandboxes and feature branch testing. | None (Non-PHI) |
| **Security/Audit** | ap-southeast-1 | Centralized logging, security tooling, and audit trails. | ISO 27001 |

### 3.2. Core Cloud Resources

The production environment is highly available and utilizes a microservices architecture.

| Resource Type | Service | Estimated Count | Primary Use Case |
| :--- | :--- | :--- | :--- |
| **Compute** | AWS EC2, Fargate | ~500 Instances/Containers | Application hosting, API gateways, batch processing. |
| **Database** | AWS RDS (PostgreSQL) | 45 Instances | Primary data store for MedSync Connect and Portal. |
| **NoSQL Database** | AWS DynamoDB | 12 Tables | Session management, feature flags, high-speed logging. |
| **Storage** | AWS S3 | 180 Buckets | PHI storage (encrypted), static assets, backups, data lake. |
| **Networking** | AWS VPC, ALB, Route 53 | 8 VPCs | Network isolation, load balancing, DNS resolution. |
| **Security** | AWS KMS, GuardDuty, WAF | N/A | Encryption key management, threat detection, web application firewall. |

## 4. Enterprise Applications and Systems

The following systems are critical to MedSync Health's operations and are managed by the IT Operations team under the direction of the CTO.

### 4.1. Product-Supporting Systems

The four core product lines are the primary consumers of the cloud infrastructure:

*   **MedSync Connect (PROD-CONNECT):** Hospital-clinic integration platform.
*   **MedSync Analytics (PROD-ANALYTICS):** Data warehousing and reporting.
*   **MedSync Patient Portal (PROD-PORTAL):** Patient-facing web application.
*   **MedSync Compliance Suite (PROD-COMPLIANCE):** Regulatory audit and management tools.

### 4.2. Internal Corporate Systems

| System Category | Key Application | Hosting Location | Notes |
| :--- | :--- | :--- | :--- |
| **Identity & Access** | Okta | Cloud (SaaS) | Single Sign-On (SSO) for all internal and external applications. |
| **ERP/Finance** | Oracle NetSuite | Cloud (SaaS) | Financial reporting and management. (See FIN-001 for details) |
| **HRIS** | Workday | Cloud (SaaS) | Employee data, payroll, and benefits. (See HR-001 for employee policies [4]) |
| **CRM** | Salesforce | Cloud (SaaS) | Sales and Customer Success management. |
| **Service Desk** | Jira Service Management | Cloud (SaaS) | Incident, problem, and change management. |

## 5. Infrastructure Management and Financials

### 5.1. Compliance and Security

All infrastructure components are managed in accordance with MedSync Health's stringent compliance requirements, including **HIPAA, SOC 2 Type II, and ISO 27001** [1].

*   **Patch Management:** Automated patching is enforced for all cloud and on-premise operating systems.
*   **Vulnerability Scanning:** Continuous scanning is performed on all production assets. (See SEC-001 for policy details [2]).
*   **Data Encryption:** All data at rest (S3, RDS) and in transit (TLS 1.2+) is encrypted using AWS KMS.

### 5.2. Financial Overview

The IT infrastructure budget is primarily managed under the Engineering department's budget, led by the CTO.

| Metric | Value (AED) [1] | Notes |
| :--- | :--- | :--- |
| **FY 2024 Engineering Budget** | **139,680,000** | Total budget for Engineering, including personnel and infrastructure. |
| **Estimated FY 2024 Cloud Spend** | 45,000,000 | Estimated portion of the budget dedicated to AWS consumption. |
| **Estimated FY 2024 Hardware/Network** | 12,000,000 | Estimated spend on on-premise hardware, network gear, and maintenance. |

The total IT spend is subject to quarterly review and optimization, with a focus on maintaining the **-4.6% Net Margin** [1] while ensuring high availability and security.

***

**END OF DOCUMENT**
***
