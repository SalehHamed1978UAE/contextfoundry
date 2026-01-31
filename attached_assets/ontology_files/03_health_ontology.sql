-- =============================================================================
-- Context Foundry: Healthcare & Life Sciences Domain Template
-- =============================================================================
-- Archetype: HEALTH (ID: 03)
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: Integration Pass (from ChatGPT docs)
-- Date: 2025-12-06
-- RFC Version: 2.0 (Dual-System Architecture)
-- Companies Served: Pure Health, Arcera (Abu Dhabi Health Services)
-- =============================================================================

-- =============================================================================
-- SHARED TYPE REFERENCES (from shared_ontology.sql - DO NOT REDEFINE)
-- =============================================================================
-- Facility: 20000000-0000-0001-0000-000000000001
-- ProductionFacility: 20000000-0000-0001-0000-000000000002
-- Good: 20000000-0000-0002-0000-000000000001
-- FinishedProduct: 20000000-0000-0002-0000-000000000003
-- OperationalTeam: 20000000-0000-0004-0000-000000000001
-- OperationalDocument: 20000000-0000-0005-0000-000000000001
-- IncidentReport: 20000000-0000-0005-0000-000000000003

-- =============================================================================
-- ENTITY TYPES
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

-- Abstract Types
('20000000-0003-0000-0000-000000000001', 'HealthFacility', 2, 'Health Facility',
 'Abstract parent for all healthcare facilities.',
 '20000000-0000-0001-0000-000000000001',
 '{"type": "object", "properties": {"facility_type": {"type": "string"}, "accreditation": {"type": "string"}}}',
 '["health facility", "medical facility", "healthcare facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000002', 'MedicalEvent', 2, 'Medical Event',
 'Abstract parent for clinical events with temporal properties.',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"start_time": {"type": "string", "format": "date-time"}, "end_time": {"type": "string", "format": "date-time"}, "status": {"type": "string", "enum": ["scheduled", "in_progress", "completed", "cancelled"]}}}',
 '["event", "clinical event", "medical event"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Concrete Facility Types
('20000000-0003-0000-0000-000000000003', 'Hospital', 2, 'Hospital',
 'Inpatient healthcare institution providing medical and surgical treatment.',
 '20000000-0003-0000-0000-000000000001',
 '{"type": "object", "properties": {"bed_capacity": {"type": "integer"}, "hospital_type": {"type": "string", "enum": ["general", "specialized", "teaching", "rehabilitation"]}, "emergency_services": {"type": "boolean"}, "jci_accredited": {"type": "boolean"}}}',
 '["hospital", "medical center", "general hospital", "Cleveland Clinic Abu Dhabi", "Tawam Hospital", "Al Ain Hospital"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000004', 'Clinic', 2, 'Clinic',
 'Outpatient healthcare center for medical treatment.',
 '20000000-0003-0000-0000-000000000001',
 '{"type": "object", "properties": {"clinic_type": {"type": "string", "enum": ["primary_care", "specialty", "urgent_care", "dental"]}, "services": {"type": "array", "items": {"type": "string"}}}}',
 '["clinic", "health clinic", "medical clinic", "outpatient center", "polyclinic"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000005', 'Laboratory', 2, 'Laboratory',
 'Facility for medical diagnostics, pathology, or research.',
 '20000000-0003-0000-0000-000000000001',
 '{"type": "object", "properties": {"lab_type": {"type": "string", "enum": ["diagnostic", "pathology", "research", "clinical_trials"]}, "iso_certified": {"type": "boolean"}}}',
 '["laboratory", "lab", "diagnostic lab", "pathology lab", "testing facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000006', 'PharmaMfgPlant', 2, 'Pharma Manufacturing Plant',
 'Pharmaceutical manufacturing facility for drug production.',
 '20000000-0000-0001-0000-000000000002',
 '{"type": "object", "properties": {"license_id": {"type": "string"}, "gmp_certified": {"type": "boolean"}, "production_capacity": {"type": "number"}}}',
 '["manufacturing plant", "pharmaceutical plant", "drug factory", "production facility", "Julphar", "Arcera"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Agent Types
('20000000-0003-0000-0000-000000000007', 'Patient', 2, 'Patient',
 'Individual receiving healthcare services.',
 '10000000-0000-0000-0000-000000000004',
 '{"type": "object", "properties": {"patient_id": {"type": "string"}, "date_of_birth": {"type": "string", "format": "date"}, "gender": {"type": "string"}, "blood_type": {"type": "string"}}}',
 '["patient", "patient ID", "MRN", "medical record number"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000008', 'MedicalTeam', 2, 'Medical Team',
 'Team of healthcare professionals providing care.',
 '20000000-0000-0004-0000-000000000001',
 '{"type": "object", "properties": {"team_type": {"type": "string", "enum": ["surgical", "nursing", "emergency", "primary_care", "specialist"]}, "department": {"type": "string"}}}',
 '["medical team", "care team", "clinical team", "surgical team", "nursing team"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Product Types
('20000000-0003-0000-0000-000000000009', 'Medication', 2, 'Medication',
 'Pharmaceutical product for treatment.',
 '20000000-0000-0002-0000-000000000003',
 '{"type": "object", "properties": {"generic_name": {"type": "string"}, "brand_name": {"type": "string"}, "form": {"type": "string", "enum": ["tablet", "capsule", "injection", "syrup", "cream", "inhaler"]}, "strength": {"type": "string"}, "atc_code": {"type": "string"}}}',
 '["medication", "drug", "medicine", "pharmaceutical", "prescription"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-00000000000A', 'DrugBatch', 2, 'Drug Batch',
 'Production batch of a medication.',
 '20000000-0003-0000-0000-000000000009',
 '{"type": "object", "properties": {"batch_number": {"type": "string"}, "manufacture_date": {"type": "string", "format": "date"}, "expiry_date": {"type": "string", "format": "date"}, "quantity": {"type": "integer"}}}',
 '["batch", "lot number", "drug batch", "production batch", "batch number"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Event Types
('20000000-0003-0000-0000-00000000000B', 'Encounter', 2, 'Encounter',
 'Patient visit or admission to a healthcare facility.',
 '20000000-0003-0000-0000-000000000002',
 '{"type": "object", "properties": {"encounter_type": {"type": "string", "enum": ["outpatient", "inpatient", "emergency", "telehealth"]}, "admission_date": {"type": "string", "format": "date-time"}, "discharge_date": {"type": "string", "format": "date-time"}, "chief_complaint": {"type": "string"}}}',
 '["encounter", "visit", "admission", "patient visit", "consultation"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-00000000000C', 'MedicalProcedure', 2, 'MedicalProcedure',
 'Medical or surgical procedure performed on a patient.',
 '20000000-0003-0000-0000-000000000002',
 '{"type": "object", "properties": {"procedure_code": {"type": "string"}, "procedure_name": {"type": "string"}, "procedure_date": {"type": "string", "format": "date-time"}, "outcome": {"type": "string"}}}',
 '["procedure", "surgery", "operation", "treatment", "intervention", "performed", "undergone", "CPT code", "surgical procedure"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-00000000000D', 'Diagnosis', 2, 'Diagnosis',
 'Clinical diagnosis for a patient.',
 '20000000-0003-0000-0000-000000000002',
 '{"type": "object", "properties": {"icd_code": {"type": "string"}, "diagnosis_name": {"type": "string"}, "diagnosis_date": {"type": "string", "format": "date"}, "severity": {"type": "string", "enum": ["mild", "moderate", "severe", "critical"]}}}',
 '["diagnosis", "diagnosed with", "ICD code", "condition", "disease", "Dx", "diagnosis code", "ICD-10", "chronic illness", "has a history of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-00000000000E', 'ClinicalTrial', 2, 'Clinical Trial',
 'Research study evaluating medical treatments.',
 '20000000-0003-0000-0000-000000000002',
 '{"type": "object", "properties": {"trial_id": {"type": "string"}, "trial_phase": {"type": "string", "enum": ["phase_1", "phase_2", "phase_3", "phase_4"]}, "sponsor": {"type": "string"}, "start_date": {"type": "string", "format": "date"}, "end_date": {"type": "string", "format": "date"}}}',
 '["clinical trial", "trial", "study", "research study", "phase 3", "sponsor", "clinical study", "subject ID", "ethics approval", "randomized trial"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Record Types
('20000000-0003-0000-0000-00000000000F', 'MedicalRecord', 2, 'Medical Record',
 'Patient medical record or health information.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"record_id": {"type": "string"}, "record_type": {"type": "string"}, "created_date": {"type": "string", "format": "date"}}}',
 '["medical record", "health record", "EMR", "EHR", "patient chart"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000010', 'InsurancePolicy', 2, 'Insurance Policy',
 'Health insurance policy covering a patient.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"policy_number": {"type": "string"}, "insurer": {"type": "string"}, "coverage_type": {"type": "string"}, "effective_date": {"type": "string", "format": "date"}, "expiry_date": {"type": "string", "format": "date"}}}',
 '["insurance policy", "health insurance", "coverage", "policy number", "Daman", "ADNIC"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000011', 'InsuranceClaim', 2, 'Insurance Claim',
 'Claim submitted for healthcare services.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"claim_id": {"type": "string"}, "claim_date": {"type": "string", "format": "date"}, "amount": {"type": "number"}, "status": {"type": "string", "enum": ["submitted", "approved", "denied", "pending"]}}}',
 '["insurance claim", "claim", "reimbursement", "claim number", "E-claim", "TPA", "submitted claim", "claim status"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000012', 'RegulatoryApproval', 2, 'Regulatory Approval',
 'Drug or device approval from regulatory authority.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"approval_number": {"type": "string"}, "approval_date": {"type": "string", "format": "date"}, "authority": {"type": "string"}, "approval_type": {"type": "string", "enum": ["drug", "device", "facility"]}}}',
 '["approval", "regulatory approval", "drug approval", "FDA", "DOH", "EMA"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000013', 'Prescription', 2, 'Prescription',
 'Medication prescription issued to a patient.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"prescription_id": {"type": "string"}, "issue_date": {"type": "string", "format": "date"}, "dosage": {"type": "string"}, "frequency": {"type": "string"}, "duration_days": {"type": "integer"}}}',
 '["prescription", "Rx", "prescribed", "medication order", "script", "written prescription"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Additional Entity Types (from QA review)
('20000000-0003-0000-0000-000000000014', 'MedicalDevice', 2, 'Medical Device',
 'Medical equipment or device used in patient care.',
 '20000000-0000-0002-0000-000000000003',
 '{"type": "object", "properties": {"device_id": {"type": "string"}, "device_type": {"type": "string", "enum": ["diagnostic", "therapeutic", "monitoring", "surgical", "life_support"]}, "manufacturer": {"type": "string"}, "model": {"type": "string"}, "fda_class": {"type": "string", "enum": ["I", "II", "III"]}, "calibration_date": {"type": "string", "format": "date"}}}',
 '["device", "medical device", "equipment", "ventilator", "MRI", "CT scanner", "ultrasound", "defibrillator", "infusion pump", "monitor"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000015', 'CarePlan', 2, 'Care Plan',
 'Longitudinal treatment plan for a patient condition.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"plan_id": {"type": "string"}, "condition": {"type": "string"}, "goals": {"type": "array", "items": {"type": "string"}}, "start_date": {"type": "string", "format": "date"}, "review_date": {"type": "string", "format": "date"}, "status": {"type": "string", "enum": ["active", "completed", "suspended", "cancelled"]}}}',
 '["care plan", "treatment plan", "care pathway", "clinical pathway", "management plan", "cancer care plan", "diabetes management"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000016', 'Referral', 2, 'Referral',
 'Patient referral between healthcare providers or facilities.',
 '20000000-0003-0000-0000-000000000002',
 '{"type": "object", "properties": {"referral_id": {"type": "string"}, "referral_date": {"type": "string", "format": "date"}, "reason": {"type": "string"}, "urgency": {"type": "string", "enum": ["routine", "urgent", "emergency"]}, "specialty": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "accepted", "completed", "declined"]}}}',
 '["referral", "referred to", "refer patient", "specialist referral", "transfer", "consult request"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000017', 'HealthcareProvider', 2, 'Healthcare Provider',
 'Organization that operates healthcare facilities (hospital network, health system).',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"provider_id": {"type": "string"}, "provider_type": {"type": "string", "enum": ["health_system", "hospital_network", "medical_group", "government"]}, "license_number": {"type": "string"}, "accreditation": {"type": "string"}}}',
 '["healthcare provider", "health system", "hospital network", "SEHA", "Pure Health", "Mubadala Health", "NMC", "VPS Healthcare", "Mediclinic"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000018', 'Bed', 2, 'Bed',
 'Hospital bed for inpatient care.',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"bed_id": {"type": "string"}, "bed_type": {"type": "string", "enum": ["general", "ICU", "NICU", "CCU", "isolation", "emergency", "recovery"]}, "ward": {"type": "string"}, "floor": {"type": "string"}, "status": {"type": "string", "enum": ["available", "occupied", "cleaning", "maintenance"]}}}',
 '["bed", "hospital bed", "ICU bed", "ward bed", "bed number", "bed capacity", "bed occupancy"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-000000000019', 'Appointment', 2, 'Appointment',
 'Scheduled healthcare appointment.',
 '20000000-0003-0000-0000-000000000002',
 '{"type": "object", "properties": {"appointment_id": {"type": "string"}, "scheduled_time": {"type": "string", "format": "date-time"}, "duration_minutes": {"type": "integer"}, "appointment_type": {"type": "string", "enum": ["consultation", "follow_up", "procedure", "telehealth", "vaccination"]}, "status": {"type": "string", "enum": ["scheduled", "confirmed", "completed", "cancelled", "no_show"]}}}',
 '["appointment", "scheduled", "booking", "slot", "consultation time", "follow-up appointment"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0003-0000-0000-00000000001A', 'DiagnosticReport', 2, 'Diagnostic Report',
 'Laboratory or imaging diagnostic report.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"report_id": {"type": "string"}, "report_type": {"type": "string", "enum": ["laboratory", "radiology", "pathology", "genetic"]}, "test_name": {"type": "string"}, "result_date": {"type": "string", "format": "date"}, "status": {"type": "string", "enum": ["preliminary", "final", "amended"]}}}',
 '["lab report", "test results", "radiology report", "pathology report", "blood test", "X-ray", "MRI report", "CT report", "biopsy"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- RELATIONSHIP TYPES
-- =============================================================================

INSERT INTO ontology.relations (
    id, relation_type, source_type_id, target_type_id, 
    cardinality, semantics, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('30000000-0003-0000-0000-000000000001', 'OCCURRED_AT', 
 '20000000-0003-0000-0000-00000000000B', '20000000-0003-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Encounter occurred at a healthcare facility',
 '["at", "in", "visited", "admitted to", "seen at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000002', 'INVOLVES_PATIENT', 
 '20000000-0003-0000-0000-000000000002', '20000000-0003-0000-0000-000000000007',
 'MANY_TO_MANY',
 'Medical event involves a patient',
 '["patient", "for patient", "on patient", "involves"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000003', 'PERFORMED_BY', 
 '20000000-0003-0000-0000-000000000002', '20000000-0003-0000-0000-000000000008',
 'MANY_TO_ONE',
 'Medical event performed by a medical team',
 '["performed by", "by team", "care team", "treating team"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000004', 'DIAGNOSED_DURING', 
 '20000000-0003-0000-0000-00000000000D', '20000000-0003-0000-0000-00000000000B',
 'MANY_TO_ONE',
 'Diagnosis made during an encounter',
 '["diagnosed during", "during visit", "at encounter"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000005', 'PROCEDURE_DURING', 
 '20000000-0003-0000-0000-00000000000C', '20000000-0003-0000-0000-00000000000B',
 'MANY_TO_ONE',
 'Procedure performed during an encounter',
 '["during", "at visit", "during admission"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000006', 'COVERED_BY', 
 '20000000-0003-0000-0000-000000000007', '20000000-0003-0000-0000-000000000010',
 'MANY_TO_ONE',
 'Patient is covered by insurance policy',
 '["covered by", "insured under", "insurance", "policy holder"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000007', 'CLAIM_FOR', 
 '20000000-0003-0000-0000-000000000011', '20000000-0003-0000-0000-00000000000B',
 'MANY_TO_ONE',
 'Insurance claim is for an encounter',
 '["claim for", "for services", "reimbursement for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000008', 'ENROLLED_IN', 
 '20000000-0003-0000-0000-000000000007', '20000000-0003-0000-0000-00000000000E',
 'MANY_TO_MANY',
 'Patient is enrolled in a clinical trial',
 '["enrolled in", "participating in", "trial participant"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000009', 'APPROVAL_FOR', 
 '20000000-0003-0000-0000-000000000012', '20000000-0003-0000-0000-000000000009',
 'MANY_TO_ONE',
 'Regulatory approval is for a medication',
 '["approval for", "approved for", "licensed"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000000A', 'ISSUED_BY', 
 '20000000-0003-0000-0000-000000000012', '10000000-0000-0000-0000-000000000005',
 'MANY_TO_ONE',
 'Regulatory approval issued by an organization',
 '["issued by", "granted by", "approved by", "authority"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000000B', 'PRODUCES', 
 '20000000-0003-0000-0000-000000000006', '20000000-0003-0000-0000-00000000000A',
 'ONE_TO_MANY',
 'Pharma plant produces drug batches',
 '["produces", "manufactures", "makes", "production of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000000C', 'PRESCRIPTION_FOR', 
 '20000000-0003-0000-0000-000000000013', '20000000-0003-0000-0000-000000000009',
 'MANY_TO_ONE',
 'Prescription is for a medication',
 '["prescription for", "prescribed", "Rx for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000000D', 'PRESCRIBED_TO', 
 '20000000-0003-0000-0000-000000000013', '20000000-0003-0000-0000-000000000007',
 'MANY_TO_ONE',
 'Prescription issued to a patient',
 '["prescribed to", "for patient", "patient prescription"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000000E', 'RECORD_FOR', 
 '20000000-0003-0000-0000-00000000000F', '20000000-0003-0000-0000-000000000007',
 'MANY_TO_ONE',
 'Medical record belongs to a patient',
 '["record for", "patient record", "chart for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000000F', 'TRIAL_AT', 
 '20000000-0003-0000-0000-00000000000E', '20000000-0003-0000-0000-000000000001',
 'MANY_TO_MANY',
 'Clinical trial conducted at a healthcare facility',
 '["conducted at", "trial site", "study location"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000010', 'HOSPITAL_HAS_LAB', 
 '20000000-0003-0000-0000-000000000003', '20000000-0003-0000-0000-000000000005',
 'ONE_TO_MANY',
 'Hospital has laboratory facilities',
 '["has lab", "laboratory at", "diagnostic services"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000011', 'CLINIC_REFERS_TO', 
 '20000000-0003-0000-0000-000000000004', '20000000-0003-0000-0000-000000000003',
 'MANY_TO_MANY',
 'Clinic refers patients to hospital',
 '["refers to", "referral to", "transferred to"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000012', 'LAB_SUPPORTS', 
 '20000000-0003-0000-0000-000000000005', '20000000-0003-0000-0000-00000000000B',
 'ONE_TO_MANY',
 'Laboratory supports encounters with diagnostic services',
 '["lab results for", "diagnostics for", "tests for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Additional Relationships (from QA review)
('30000000-0003-0000-0000-000000000013', 'DEVICE_USED_IN', 
 '20000000-0003-0000-0000-000000000014', '20000000-0003-0000-0000-00000000000C',
 'MANY_TO_MANY',
 'Medical device used in a procedure',
 '["used in", "device for", "equipment used", "performed with"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000014', 'DEVICE_AT_FACILITY', 
 '20000000-0003-0000-0000-000000000014', '20000000-0003-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Medical device located at a healthcare facility',
 '["located at", "installed at", "device at", "equipment at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000015', 'CAREPLAN_FOR', 
 '20000000-0003-0000-0000-000000000015', '20000000-0003-0000-0000-000000000007',
 'MANY_TO_ONE',
 'Care plan is for a patient',
 '["care plan for", "treatment for patient", "patient care plan"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000016', 'CAREPLAN_ADDRESSES', 
 '20000000-0003-0000-0000-000000000015', '20000000-0003-0000-0000-00000000000D',
 'MANY_TO_ONE',
 'Care plan addresses a diagnosis',
 '["addresses", "for condition", "management of", "treating"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000017', 'REFERRAL_FROM', 
 '20000000-0003-0000-0000-000000000016', '20000000-0003-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Referral originated from a healthcare facility',
 '["referred from", "from clinic", "from hospital", "referring facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000018', 'REFERRAL_TO', 
 '20000000-0003-0000-0000-000000000016', '20000000-0003-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Referral is to a healthcare facility',
 '["referred to", "to hospital", "to specialist", "receiving facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000019', 'REFERRAL_FOR_PATIENT', 
 '20000000-0003-0000-0000-000000000016', '20000000-0003-0000-0000-000000000007',
 'MANY_TO_ONE',
 'Referral is for a patient',
 '["referral for", "patient referred", "refer patient"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000001A', 'PROVIDER_OPERATES', 
 '20000000-0003-0000-0000-000000000017', '20000000-0003-0000-0000-000000000001',
 'ONE_TO_MANY',
 'Healthcare provider operates a facility',
 '["operates", "owns", "manages", "runs", "network includes"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000001B', 'BED_AT_HOSPITAL', 
 '20000000-0003-0000-0000-000000000018', '20000000-0003-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Bed is located at a hospital',
 '["bed at", "ward at", "located in", "hospital bed"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000001C', 'PATIENT_ASSIGNED_BED', 
 '20000000-0003-0000-0000-000000000007', '20000000-0003-0000-0000-000000000018',
 'MANY_TO_ONE',
 'Patient is assigned to a bed during admission',
 '["assigned bed", "in bed", "admitted to bed", "bed assignment"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000001D', 'APPOINTMENT_FOR_PATIENT', 
 '20000000-0003-0000-0000-000000000019', '20000000-0003-0000-0000-000000000007',
 'MANY_TO_ONE',
 'Appointment is scheduled for a patient',
 '["appointment for", "scheduled for", "patient appointment"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000001E', 'APPOINTMENT_AT', 
 '20000000-0003-0000-0000-000000000019', '20000000-0003-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Appointment is at a healthcare facility',
 '["appointment at", "scheduled at", "visit to"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-00000000001F', 'REPORT_FOR_ENCOUNTER', 
 '20000000-0003-0000-0000-00000000001A', '20000000-0003-0000-0000-00000000000B',
 'MANY_TO_ONE',
 'Diagnostic report is for an encounter',
 '["report for", "results from", "diagnostics from visit"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000020', 'REPORT_FOR_PATIENT', 
 '20000000-0003-0000-0000-00000000001A', '20000000-0003-0000-0000-000000000007',
 'MANY_TO_ONE',
 'Diagnostic report is for a patient',
 '["patient results", "report for patient", "test results for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000021', 'DEVICE_APPROVAL', 
 '20000000-0003-0000-0000-000000000012', '20000000-0003-0000-0000-000000000014',
 'MANY_TO_ONE',
 'Regulatory approval is for a medical device',
 '["device approval", "approved device", "device cleared"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0003-0000-0000-000000000022', 'CLAIM_COVERS_PROCEDURE', 
 '20000000-0003-0000-0000-000000000011', '20000000-0003-0000-0000-00000000000C',
 'MANY_TO_MANY',
 'Insurance claim covers a medical procedure',
 '["claim for procedure", "procedure covered", "reimbursement for treatment"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- End of Healthcare Domain Template
-- =============================================================================
