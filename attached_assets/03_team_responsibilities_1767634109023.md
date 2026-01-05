# Al Shifa Health System - IT Team Responsibilities

**Document Owner**: CIO Office  
**Last Updated**: November 2025

---

## Team Directory

### Clinical Systems Team

**Manager**: Ahmed Al-Rashid  
**Headcount**: 14 engineers  
**Focus**: Core clinical applications

**Systems Owned:**
- Electronic Health Record (EHR)
- Patient Identity Service
- Clinical Decision Support
- Order Entry Module

**On-call rotation**: clinical-systems-oncall (PagerDuty)  
**Escalation**: Ahmed Al-Rashid (ahmed.rashid@alshifa.ae)

**Responsibilities:**
- EHR configuration and customization
- Patient matching algorithms
- Clinical workflow optimization
- Physician and nurse support
- Regulatory compliance for clinical systems

---

### Diagnostics Team

**Manager**: Dr. Layla Mahmoud  
**Headcount**: 8 engineers  
**Focus**: Laboratory and imaging systems

**Systems Owned:**
- Lab System (LIS)
- Radiology System (PACS)
- Lab Instruments Interface
- Radiology Worklist

**On-call rotation**: diagnostics-oncall (PagerDuty)  
**Escalation**: Dr. Layla Mahmoud (layla.mahmoud@alshifa.ae)

**Responsibilities:**
- Lab analyzer integrations
- DICOM image routing
- Results delivery to EHR
- Quality control interfaces

---

### Pharmacy IT Team

**Manager**: Khalid Hassan  
**Headcount**: 5 engineers  
**Focus**: Medication management systems

**Systems Owned:**
- Pharmacy System
- Drug Interaction Database
- Controlled Substance Reporting
- Automated Dispensing Cabinets

**On-call rotation**: pharmacy-it-oncall (PagerDuty)  
**Escalation**: Khalid Hassan (khalid.hassan@alshifa.ae)

**Responsibilities:**
- Medication order processing
- Drug interaction alerting
- Inventory management
- MOH controlled substance reporting

---

### Revenue Cycle Team

**Manager**: Sara Al-Fahim  
**Headcount**: 10 engineers  
**Focus**: Financial systems

**Systems Owned:**
- Billing System
- Insurance Gateway
- Patient Accounting
- Collections Module

**On-call rotation**: revenue-cycle-oncall (PagerDuty)  
**Escalation**: Sara Al-Fahim (sara.fahim@alshifa.ae)

**Responsibilities:**
- Charge capture accuracy
- Claims submission and follow-up
- Payment processing
- Revenue reporting

---

### Patient Access Team

**Manager**: Noura Khalil  
**Headcount**: 6 engineers  
**Focus**: Patient-facing systems

**Systems Owned:**
- Appointment Scheduling
- Patient Portal
- Check-in Kiosks
- Wait Time Display

**On-call rotation**: patient-access-oncall (PagerDuty)  
**Escalation**: Noura Khalil (noura.khalil@alshifa.ae)

**Responsibilities:**
- Scheduling optimization
- Patient self-service
- Registration workflows
- Access to care metrics

---

### Integration Team

**Manager**: Omar Saeed  
**Headcount**: 7 engineers  
**Focus**: System interoperability

**Systems Owned:**
- Integration Engine
- API Gateway
- HL7 FHIR Server
- Message Queue

**On-call rotation**: integration-oncall (PagerDuty)  
**Escalation**: Omar Saeed (omar.saeed@alshifa.ae)

**Responsibilities:**
- Interface development and maintenance
- Message routing and transformation
- FHIR API management
- External partner integrations

---

### Database Administration Team

**Manager**: Yusuf Al-Mansoori  
**Headcount**: 6 DBAs  
**Focus**: Data platform

**Systems Owned:**
- Clinical Database
- Master Patient Index
- Lab Results Database
- Finance Database
- Data Warehouse

**On-call rotation**: dba-oncall (PagerDuty)  
**Escalation**: Yusuf Al-Mansoori (yusuf.mansoori@alshifa.ae)

**Responsibilities:**
- Database performance optimization
- Backup and recovery
- Replication management
- Data security and encryption

---

### Infrastructure Team

**Manager**: Tariq Nasser  
**Headcount**: 12 engineers  
**Focus**: Core infrastructure

**Systems Owned:**
- Image Storage Array
- Network infrastructure
- Server virtualization
- Cloud services

**On-call rotation**: infrastructure-oncall (PagerDuty)  
**Escalation**: Tariq Nasser (tariq.nasser@alshifa.ae)

**Responsibilities:**
- Compute and storage provisioning
- Network connectivity
- Disaster recovery
- Security infrastructure

---

## Escalation Matrix

| Severity | First Response | Escalation (15 min) | Executive (30 min) |
|----------|----------------|---------------------|-------------------|
| Critical (Patient Safety) | On-call + CMIO | All affected team managers | CIO + CMO |
| High | On-call engineer | Team manager | CIO |
| Medium | On-call engineer | Team manager | - |
| Low | Next business day | - | - |

---

## Cross-Team Dependencies

The following dependencies exist between teams:

- **Clinical Systems** depends on **Database Administration** for Clinical Database
- **Clinical Systems** depends on **Integration Team** for external connections
- **Diagnostics** depends on **Clinical Systems** for EHR integration
- **Pharmacy IT** depends on **Clinical Systems** for medication orders
- **Revenue Cycle** depends on **Clinical Systems** for clinical documentation
- **All Teams** depend on **Integration Team** for system interoperability
- **All Teams** depend on **Infrastructure** for compute and network
