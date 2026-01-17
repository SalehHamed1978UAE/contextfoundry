# SEC-012: Encryption Standards

| Attribute | Value |
| :--- | :--- |
| **Document ID** | SEC-012 |
| **Title** | Encryption Standards |
| **Version** | 1.0 |
| **Effective Date** | January 17, 2026 |
| **Owner** | Chief Information Security Officer (CISO) |
| **Review Cycle** | Annual |

---

## 1. Purpose and Scope

The purpose of this document is to establish the mandatory standards for the use of cryptographic controls to protect MedSync Health's data assets, particularly Electronic Protected Health Information (ePHI) and Personally Identifiable Information (PII), from unauthorized access, disclosure, modification, or destruction.

This standard applies to all MedSync Health employees, contractors, systems, applications, and services that store, process, or transmit sensitive data, regardless of the environment (production, staging, development, or corporate).

## 2. Compliance Mandates

MedSync Health is committed to maintaining the highest level of data protection and regulatory compliance. The encryption standards defined herein are designed to meet or exceed the requirements of the following key certifications and regulations:

| Standard/Regulation | Status | Key Dates |
| :--- | :--- | :--- |
| **HIPAA Compliance** | Certified | Certified **March 2020** |
| **GDPR Compliance** | Implemented | Implemented **May 2020** |
| **SOC 2 Type II** | Certified | First certified **August 2021**, renewed **August 2024** |
| **ISO 27001** | Certified | Certified **November 2022** |

The use of strong, industry-standard encryption is a foundational control for achieving the confidentiality and integrity requirements of these mandates.

## 3. Encryption at Rest (EAR)

All sensitive data, including ePHI and PII, stored on any MedSync Health system or service must be encrypted at rest.

### 3.1. Storage Encryption Requirements

| Data Type/Location | Encryption Standard | Key Management Service |
| :--- | :--- | :--- |
| **Databases (e.g., RDS, MongoDB)** | AES-256 (Transparent Data Encryption or Field-Level) | AWS KMS or Azure Key Vault |
| **File Storage (e.g., S3, Azure Blob)** | AES-256 (Server-Side Encryption with KMS keys) | AWS KMS or Azure Key Vault |
| **Backups and Archives** | AES-256 | Managed by Backup Solution (must use KMS-protected keys) |
| **Endpoint Devices (Laptops, Mobile)** | Full Disk Encryption (FDE) - e.g., BitLocker, FileVault | Centralized Management System |

### 3.2. Algorithm Specification

The mandatory algorithm for all data at rest is **Advanced Encryption Standard (AES)** with a key length of **256 bits** (AES-256). All implementations must use FIPS 140-2 validated cryptographic modules.

## 4. Encryption in Transit (EIT)

All data transmitted over networks, particularly public or untrusted networks (e.g., the internet), must be protected by strong encryption in transit.

### 4.1. Transport Layer Security (TLS)

All external and internal communications carrying sensitive data must use **Transport Layer Security (TLS) version 1.2 or higher**. **TLS 1.3** is the preferred standard for all new deployments.

| Requirement | Standard |
| :--- | :--- |
| **Protocol Version** | TLS 1.2 minimum; TLS 1.3 preferred |
| **Cipher Suites** | Must support Perfect Forward Secrecy (PFS) and use strong ciphers (e.g., ECDHE-RSA-AES256-GCM-SHA384) |
| **Certificate Strength** | Minimum 2048-bit RSA or 256-bit ECC keys |
| **Certificate Authority** | Must be issued by a trusted, publicly recognized CA or MedSync's internal CA |

### 4.2. Application-Layer Encryption

For specific high-risk data transfers, such as API calls between microservices handling ePHI, additional application-layer encryption (e.g., signed and encrypted JSON Web Tokens) may be required, as detailed in **SEC-005: Secure Coding Policy**.

## 5. Key Management Standards

The security of MedSync Health's encrypted data is directly dependent on the security of its cryptographic keys. All key management activities must adhere to the principle of least privilege and separation of duties.

### 5.1. Key Storage and Access

1.  **Storage:** All master encryption keys must be stored in a FIPS 140-2 Level 3 compliant Hardware Security Module (HSM) or a managed cloud Key Management Service (KMS) (e.g., AWS KMS, Azure Key Vault).
2.  **Access Control:** Access to encryption keys must be strictly controlled and logged. Key access policies must be reviewed quarterly. (See **SEC-011: Access Control Policy** for detailed role-based access controls).
3.  **Key Rotation:** Master encryption keys must be automatically rotated at least every 12 months. Data encryption keys (DEKs) should be rotated based on the volume of data encrypted or the age of the key, as defined by the system architect.

### 5.2. Key Lifecycle

| Phase | Requirement | Responsibility |
| :--- | :--- | :--- |
| **Generation** | Keys must be generated using cryptographically secure pseudo-random number generators (CSPRNGs) within the KMS/HSM. | Security Engineering |
| **Distribution** | Keys must never be transmitted in the clear. Key wrapping must be used for any necessary transfer. | Security Engineering |
| **Storage** | Stored only in KMS/HSM. | Cloud Operations |
| **Destruction** | Keys must be securely destroyed (cryptographic erasure) upon retirement, with destruction logs retained for a minimum of 7 years. | Security Operations |

## 6. Enforcement and Monitoring

### 6.1. Auditing and Logging

All cryptographic operations, including key access, key rotation, and encryption/decryption events, must be logged and monitored. Logs must be retained for a minimum of 90 days for active analysis and 1 year for archival purposes, as per **SEC-008: Logging and Monitoring Policy**.

### 6.2. Non-Compliance

Any system or application found to be non-compliant with this standard must be immediately isolated from the production network until the encryption controls are correctly implemented and verified by the Security Team.

---
*End of Document*
