# Information Security Policy

**Document Type:** Corporate Policy
**Authority Level:** 1 (Authoritative)
**Policy Number:** POL-002
**Effective Date:** January 1, 2025
**Last Reviewed:** January 2026
**Owner:** Chief Information Security Officer
**Classification:** Internal

---

## Purpose

This policy establishes requirements for protecting Nexus Industries' information assets, ensuring confidentiality, integrity, and availability of data across all systems and operations.

---

## Scope

This policy applies to:
- All information systems owned or operated by Nexus
- All employees, contractors, and third parties with system access
- All data regardless of format (electronic, physical, verbal)
- All locations including remote work environments

---

## Information Classification

### Classification Levels

| Level | Definition | Examples |
|-------|------------|----------|
| **Public** | Approved for external distribution | Press releases, public financials |
| **Internal** | General business, internal only | Org charts, procedures |
| **Confidential** | Sensitive, need-to-know | Customer data, contracts |
| **Restricted** | Highly sensitive, strict controls | Trade secrets, ITAR, PII |

### Handling Requirements

| Level | Storage | Transmission | Disposal |
|-------|---------|--------------|----------|
| Public | Unrestricted | Any method | Standard |
| Internal | Company systems | Internal email OK | Standard |
| Confidential | Encrypted, access controlled | Encrypted only | Secure destruction |
| Restricted | Encrypted, logged access | Encrypted, approved channels | Certified destruction |

---

## Access Control

### Principles

| Principle | Description |
|-----------|-------------|
| Least Privilege | Minimum access required for job |
| Need-to-Know | Access only to required information |
| Separation of Duties | Critical functions split among people |
| Individual Accountability | Unique IDs, no sharing |

### Access Management

| Action | Requirement |
|--------|-------------|
| New Access | Manager approval, documented |
| Access Change | Manager approval, within 48 hours |
| Termination | Same-day revocation |
| Privileged Access | VP approval, quarterly review |
| Third-Party Access | Contract required, CISO approval |

### Authentication Requirements

| System Type | Requirement |
|-------------|-------------|
| Standard Systems | Complex password + MFA |
| Privileged Systems | Strong MFA + PAM |
| Remote Access | VPN + MFA |
| Critical Systems | Hardware token + biometric |

**Password Requirements:**
- Minimum 14 characters
- Complexity required (upper, lower, number, special)
- 90-day rotation
- No reuse of last 12 passwords
- Lockout after 5 failed attempts

---

## Network Security

### Architecture

| Zone | Description | Controls |
|------|-------------|----------|
| External | Internet-facing | Firewall, WAF, IPS |
| DMZ | Public services | Hardened, monitored |
| Internal | Business systems | Segmented, logged |
| Restricted | Sensitive systems | Air-gapped where required |

### Requirements

| Control | Requirement |
|---------|-------------|
| Firewalls | Default deny, logged |
| Intrusion Detection | All perimeters |
| Encryption | TLS 1.2+ for all external |
| Monitoring | 24/7 SOC coverage |
| Vulnerability Scanning | Weekly automated, quarterly manual |

---

## Endpoint Security

### Required Controls

| Control | Standard |
|---------|----------|
| Antivirus/EDR | CrowdStrike (corporate) |
| Encryption | Full disk encryption |
| Patching | Critical: 72 hours, High: 7 days |
| Mobile Device Management | Required for company data |
| USB Controls | Restricted, logged |

### Approved Devices

| Device Type | Policy |
|-------------|--------|
| Company Laptops | Fully managed |
| Company Mobile | MDM required |
| Personal Devices | No corporate data (exceptions with approval) |
| Removable Media | Encrypted, approved only |

---

## Data Protection

### Encryption Requirements

| Data State | Requirement |
|------------|-------------|
| At Rest | AES-256 or equivalent |
| In Transit | TLS 1.2+ or equivalent |
| In Processing | Secure enclaves where appropriate |
| Backup | Encrypted |

### Data Loss Prevention

| Control | Scope |
|---------|-------|
| Email DLP | All outbound email |
| Web DLP | All web traffic |
| Endpoint DLP | All managed devices |
| Cloud DLP | All SaaS applications |

---

## Incident Response

### Incident Classification

| Severity | Definition | Response Time |
|----------|------------|---------------|
| Critical | Active breach, widespread impact | Immediate |
| High | Confirmed compromise, limited impact | 1 hour |
| Medium | Suspicious activity, potential risk | 4 hours |
| Low | Policy violation, no compromise | 24 hours |

### Response Process

1. **Detection:** Automated alerts, user reports
2. **Triage:** SOC initial assessment
3. **Containment:** Isolate affected systems
4. **Eradication:** Remove threat
5. **Recovery:** Restore operations
6. **Lessons Learned:** Post-incident review

### Reporting Requirements

| Incident Type | Internal Report | External Report |
|---------------|-----------------|-----------------|
| Data Breach (PII) | CISO immediately | Per regulation (typically 72 hrs) |
| Ransomware | CISO immediately | Law enforcement if advised |
| ITAR Violation | CISO + Legal | State Dept. as required |
| Business Impact | CISO + Business | Customer if contractually required |

---

## Third-Party Security

### Requirements

| Risk Level | Assessment |
|------------|------------|
| Low | Self-assessment questionnaire |
| Medium | Security questionnaire + SOC 2 |
| High | On-site assessment + continuous monitoring |
| Critical | All above + right to audit |

### Contractual Requirements

- Data protection clauses
- Breach notification (24 hours)
- Security requirements
- Audit rights
- Termination data return/destruction

---

## Security Awareness

### Training Requirements

| Training | Frequency | Audience |
|----------|-----------|----------|
| Security Awareness | Annual | All employees |
| Phishing Simulation | Quarterly | All employees |
| Role-Based Training | Annual | IT, developers, privileged users |
| Incident Response | Annual | Response team |

---

## Compliance

### Standards and Frameworks

| Standard | Scope |
|----------|-------|
| NIST Cybersecurity Framework | Enterprise |
| ISO 27001 | Certified locations |
| CMMC Level 3 | Defense programs |
| SOC 2 Type II | SaaS products |
| NERC CIP | Energy systems |

### Audits

| Audit Type | Frequency |
|------------|-----------|
| Internal Security Audit | Quarterly |
| External Penetration Test | Annual |
| Compliance Audit | Annual |
| Third-Party Audit | Per contract |

---

## Enforcement

| Violation | Consequence |
|-----------|-------------|
| Unintentional, first offense | Training, documented |
| Negligent | Written warning |
| Intentional/Repeated | Termination |
| Malicious | Termination + legal action |

---

## Governance

**Information Security Council:**
- CISO (Chair)
- CTO
- General Counsel
- Division CISOs
- VP IT

**Review:** Annual policy review

---

*Approved by: Maria Santos, CISO*
*Effective: January 1, 2025*
