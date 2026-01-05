# Al Shifa Health System - Technology Architecture

**Document Owner**: Health IT Department  
**Last Updated**: November 2025  
**Classification**: Internal

---

## Overview

Al Shifa Health System operates 12 hospitals and 45 clinics across the UAE. This document describes our core technology infrastructure supporting patient care, clinical operations, and administrative functions.

---

## Core Systems

### Electronic Health Record (EHR)

The EHR system is the central repository for all patient medical records. It depends on the Patient Identity Service for patient matching, the Clinical Database for record storage, and the Audit Service for compliance logging. All clinical applications access patient data through the EHR.

**Owner**: Clinical Systems Team  
**Criticality**: Tier 1 - Patient Safety Critical  
**SLA**: 99.99% availability

### Patient Identity Service

The Patient Identity Service manages unique patient identifiers across all facilities. It depends on the Master Patient Index database and the Identity Verification API for duplicate detection. The EHR, Lab System, Pharmacy System, and Radiology System all depend on Patient Identity Service.

**Owner**: Clinical Systems Team  
**Criticality**: Tier 1 - Patient Safety Critical

### Lab System

The Lab System manages laboratory orders, specimen tracking, and result reporting. It depends on the EHR for patient context, the Lab Instruments Interface for analyzer integration, and the Lab Results Database for storage. Results are sent to the EHR automatically.

**Owner**: Diagnostics Team  
**Criticality**: Tier 1

### Pharmacy System

The Pharmacy System handles medication orders, dispensing, and inventory management. It depends on the EHR for prescription orders, the Drug Interaction Database for safety checks, and the Inventory System for stock management. It connects to the Ministry of Health controlled substance reporting system.

**Owner**: Pharmacy IT Team  
**Criticality**: Tier 1 - Patient Safety Critical

### Radiology System (PACS)

The PACS stores and distributes medical images. It depends on the EHR for order information, the Image Storage Array for DICOM files, and the Radiology Worklist for technologist assignments.

**Owner**: Diagnostics Team  
**Criticality**: Tier 2

### Billing System

The Billing System processes patient charges, insurance claims, and payments. It depends on the EHR for clinical documentation, the Insurance Gateway for claim submission, and the Finance Database for transaction records.

**Owner**: Revenue Cycle Team  
**Criticality**: Tier 2

### Appointment Scheduling

The Scheduling System manages patient appointments across all facilities. It depends on the Patient Identity Service for patient lookup, the Provider Directory for clinician availability, and the Scheduling Database.

**Owner**: Patient Access Team  
**Criticality**: Tier 3

---

## Databases

### Clinical Database
Primary storage for EHR records. PostgreSQL cluster with synchronous replication.
**Owner**: Database Administration Team

### Master Patient Index
Patient identity and matching data. Oracle database.
**Owner**: Database Administration Team

### Lab Results Database
Laboratory test results and reference ranges. PostgreSQL.
**Owner**: Database Administration Team

### Finance Database
Financial transactions and billing records. Oracle database.
**Owner**: Database Administration Team

### Image Storage Array
DICOM image storage. NetApp with 2PB capacity.
**Owner**: Infrastructure Team

---

## Integration Layer

### Integration Engine

The Integration Engine routes messages between all clinical systems using HL7 FHIR standards. All systems depend on Integration Engine for interoperability. If Integration Engine fails, systems cannot exchange data.

**Owner**: Integration Team  
**Criticality**: Tier 1

---

## Team Responsibilities

| Team | Systems Owned |
|------|---------------|
| Clinical Systems Team | EHR, Patient Identity Service |
| Diagnostics Team | Lab System, Radiology System (PACS) |
| Pharmacy IT Team | Pharmacy System |
| Revenue Cycle Team | Billing System |
| Patient Access Team | Appointment Scheduling |
| Integration Team | Integration Engine |
| Database Administration Team | All databases |
| Infrastructure Team | Image Storage Array, Network |
