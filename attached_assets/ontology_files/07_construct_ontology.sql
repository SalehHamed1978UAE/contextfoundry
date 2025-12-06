-- =============================================================================
-- Context Foundry: Construction Ontology
-- =============================================================================
-- Purpose: Defines types for construction projects, contractors, sites,
--          documents, and project management
-- Domain: CONSTRUCT (0007)
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: Claude (Reconstructed)
-- Date: 2025-12-06
-- RFC Version: 2.0 (Dual-System Architecture)
-- =============================================================================

-- =============================================================================
-- ABSTRACT CONSTRUCTION TYPES
-- UUID Pattern: 20000000-0007-0000-0000-00000000XXXX
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0007-0000-0000-000000000001', 'ConstructionFacility', 2, 'Construction Facility',
 'Facility where construction or development activities occur',
 '20000000-0000-0001-0000-000000000001',
 '{"type": "object", "properties": {"facility_type": {"type": "string", "enum": ["TEMPORARY", "PERMANENT", "STAGING"]}, "is_active": {"type": "boolean"}}}',
 '["construction facility", "site facility", "project facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000002', 'ConstructionProject', 2, 'Construction Project',
 'Abstract parent for all construction and development projects',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"project_code": {"type": "string"}, "stakeholder_count": {"type": "integer"}}}',
 '["construction project", "development project", "infrastructure project"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- CORE PROJECT TYPES
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0007-0000-0000-000000000003', 'Project', 2, 'Project',
 'Construction or development project spanning multiple phases and stakeholders',
 '20000000-0007-0000-0000-000000000002',
 '{"type": "object", "properties": {"project_id": {"type": "string"}, "project_name": {"type": "string"}, "project_type": {"type": "string", "enum": ["BUILDING", "INFRASTRUCTURE", "INDUSTRIAL", "MIXED_USE"]}, "delivery_model": {"type": "string", "enum": ["EPC", "EPCM", "DESIGN_BUILD", "TRADITIONAL", "PPP"]}, "start_date": {"type": "string", "format": "date-time"}, "end_date_planned": {"type": "string", "format": "date-time"}, "end_date_actual": {"type": "string", "format": "date-time"}, "status": {"type": "string", "enum": ["PLANNING", "TENDERING", "UNDER_CONSTRUCTION", "ON_HOLD", "COMMISSIONING", "COMPLETED"]}, "contract_value": {"type": "number"}, "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}, "location_description": {"type": "string"}}}',
 '["project name", "project ID", "construction project", "EPC project", "design and build", "contract value", "project duration", "project status"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000004', 'ConstructionSite', 2, 'Construction Site',
 'Physical location where construction activities are executed',
 '20000000-0007-0000-0000-000000000001',
 '{"type": "object", "properties": {"site_id": {"type": "string"}, "site_name": {"type": "string"}, "address": {"type": "string"}, "city": {"type": "string"}, "country": {"type": "string"}, "site_area_sqm": {"type": "number"}, "site_conditions": {"type": "string"}}}',
 '["construction site", "site address", "project site", "jobsite", "site location", "site area"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000005', 'Budget', 2, 'Project Budget',
 'Allocated financial resources for a project or phase',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"budget_id": {"type": "string"}, "budget_type": {"type": "string", "enum": ["INITIAL", "REVISED", "FINAL"]}, "amount": {"type": "number"}, "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}, "contingency_amount": {"type": "number"}, "baseline_date": {"type": "string", "format": "date-time"}}}',
 '["project budget", "budget allocation", "approved budget", "revised budget", "budget baseline", "cost plan"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- ORGANIZATION AND ROLE TYPES
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0007-0000-0000-000000000006', 'Contractor', 2, 'Contractor',
 'General or subcontractor responsible for delivering construction scope',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"contractor_type": {"type": "string", "enum": ["MAIN", "SUBCONTRACTOR", "SPECIALIST"]}, "registration_number": {"type": "string"}, "prequalification_status": {"type": "string"}, "specializations": {"type": "array", "items": {"type": "string"}}}}',
 '["contractor", "main contractor", "general contractor", "EPC contractor", "subcontractor", "builder"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000007', 'Consultant', 2, 'Consultant',
 'Professional services provider for construction projects',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"consultant_type": {"type": "string", "enum": ["DESIGN", "ENGINEERING", "SUPERVISION", "COST", "LEGAL"]}, "license_number": {"type": "string"}, "specializations": {"type": "array", "items": {"type": "string"}}}}',
 '["consultant", "design consultant", "engineering consultant", "supervision consultant", "PMC"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000008', 'ProjectManager', 2, 'Project Manager',
 'Individual managing construction project delivery',
 '00000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"employee_id": {"type": "string"}, "certification": {"type": "string"}, "years_experience": {"type": "integer"}}}',
 '["Project Manager", "PM", "project director", "overall project manager", "lead project manager"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000009', 'SiteSupervisor', 2, 'Site Supervisor',
 'Individual supervising on-site construction operations',
 '00000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"employee_id": {"type": "string"}, "area_of_responsibility": {"type": "string"}, "shift": {"type": "string"}}}',
 '["site supervisor", "site engineer", "construction manager", "site in-charge", "foreman"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000000A', 'ProjectSponsor', 2, 'Project Sponsor',
 'Organization funding or commissioning the project',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"sponsor_type": {"type": "string", "enum": ["GOVERNMENT", "PRIVATE", "PPP", "JOINT_VENTURE"]}, "funding_commitment": {"type": "number"}}}',
 '["project sponsor", "client", "employer", "owner", "government entity", "special purpose vehicle"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- PROJECT ELEMENT TYPES
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0007-0000-0000-00000000000B', 'Milestone', 2, 'Milestone',
 'Key project checkpoint or deliverable',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"milestone_id": {"type": "string"}, "milestone_name": {"type": "string"}, "planned_date": {"type": "string", "format": "date"}, "actual_date": {"type": "string", "format": "date"}, "status": {"type": "string", "enum": ["PENDING", "ACHIEVED", "DELAYED", "CANCELLED"]}}}',
 '["milestone", "key milestone", "project milestone", "substantial completion", "taking over"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000000C', 'ProjectPhase', 2, 'Project Phase',
 'Distinct stage in project lifecycle',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"phase_name": {"type": "string"}, "sequence": {"type": "integer"}, "start_date": {"type": "string", "format": "date"}, "end_date": {"type": "string", "format": "date"}, "status": {"type": "string"}}}',
 '["project phase", "design phase", "procurement phase", "construction phase", "commissioning phase"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000000D', 'ChangeOrder', 2, 'Change Order',
 'Modification to project scope or contract terms',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"change_order_number": {"type": "string"}, "change_type": {"type": "string", "enum": ["SCOPE", "DESIGN", "SCHEDULE", "COST"]}, "value_impact": {"type": "number"}, "schedule_impact_days": {"type": "integer"}, "status": {"type": "string", "enum": ["DRAFT", "SUBMITTED", "APPROVED", "REJECTED"]}}}',
 '["change order", "variation order", "VO", "scope change", "contract change", "change notice"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- DOCUMENT TYPES
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0007-0000-0000-00000000000E', 'Contract', 2, 'Contract',
 'Legal agreement for construction services',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"contract_number": {"type": "string"}, "contract_type": {"type": "string", "enum": ["EPC", "EPCM", "DESIGN_BUILD", "LUMP_SUM", "COST_PLUS", "UNIT_RATE"]}, "contract_value": {"type": "number"}, "currency": {"type": "string"}, "effective_date": {"type": "string", "format": "date"}, "expiry_date": {"type": "string", "format": "date"}}}',
 '["EPC Contract", "construction contract", "contract number", "agreement", "design and build contract"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000000F', 'Drawing', 2, 'Drawing',
 'Technical construction drawing or plan',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"drawing_number": {"type": "string"}, "drawing_title": {"type": "string"}, "revision": {"type": "string"}, "drawing_type": {"type": "string", "enum": ["IFC", "SHOP", "AS_BUILT", "TENDER", "CONCEPT"]}, "discipline": {"type": "string"}, "scale": {"type": "string"}}}',
 '["drawing no.", "construction drawing", "shop drawing", "for construction", "IFC drawing", "as-built"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000010', 'ProgressReport', 2, 'Progress Report',
 'Report on project status and progress',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"report_period": {"type": "string"}, "overall_progress_pct": {"type": "number"}, "planned_progress_pct": {"type": "number"}, "variance": {"type": "number"}, "key_issues": {"type": "array", "items": {"type": "string"}}}}',
 '["progress report", "monthly progress", "weekly progress", "site progress", "overall progress"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000011', 'SafetyInspection', 2, 'Safety Inspection',
 'HSE inspection event on construction site',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"inspection_date": {"type": "string", "format": "date"}, "inspector": {"type": "string"}, "inspection_type": {"type": "string", "enum": ["ROUTINE", "INCIDENT", "AUDIT"]}, "findings_count": {"type": "integer"}, "critical_findings": {"type": "integer"}}}',
 '["safety inspection", "HSE inspection", "site inspection", "safety audit", "HSE report"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000012', 'Permit', 2, 'Permit',
 'Official authorization for construction activities',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"permit_number": {"type": "string"}, "permit_type": {"type": "string", "enum": ["BUILDING", "EXCAVATION", "DEMOLITION", "OCCUPANCY", "ENVIRONMENTAL"]}, "issuing_authority": {"type": "string"}, "issue_date": {"type": "string", "format": "date"}, "expiry_date": {"type": "string", "format": "date"}}}',
 '["building permit", "construction permit", "excavation permit", "demolition permit", "permit number"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000013', 'TenderDocument', 2, 'Tender Document',
 'Documentation for procurement bidding',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"tender_reference": {"type": "string"}, "tender_type": {"type": "string", "enum": ["OPEN", "RESTRICTED", "NEGOTIATED", "DIRECT"]}, "submission_deadline": {"type": "string", "format": "date-time"}, "estimated_value": {"type": "number"}}}',
 '["tender document", "RFP", "request for proposal", "tender reference", "bid document", "ITT"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000014', 'PPPAgreement', 2, 'PPP Agreement',
 'Public-private partnership contract',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"agreement_type": {"type": "string", "enum": ["BOT", "BOO", "BOOT", "DBFOM", "CONCESSION"]}, "concession_period_years": {"type": "integer"}, "government_contribution": {"type": "number"}, "private_investment": {"type": "number"}}}',
 '["PPP agreement", "public-private partnership", "concession agreement", "DBFOM", "BOT contract"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000015', 'CommissioningReport', 2, 'Commissioning Report',
 'Report on testing and commissioning activities',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"system_name": {"type": "string"}, "test_date": {"type": "string", "format": "date"}, "test_result": {"type": "string", "enum": ["PASS", "FAIL", "CONDITIONAL"]}, "defects_identified": {"type": "integer"}, "remedial_actions": {"type": "string"}}}',
 '["commissioning report", "testing and commissioning", "pre-commissioning", "system test", "handover"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- NEW TYPES FROM QA REVIEW
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0007-0000-0000-000000000016', 'Subcontract', 2, 'Subcontract',
 'Contract between main contractor and subcontractor',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"subcontract_number": {"type": "string"}, "work_package": {"type": "string"}, "subcontract_value": {"type": "number"}, "start_date": {"type": "string", "format": "date"}, "end_date": {"type": "string", "format": "date"}}}',
 '["subcontract", "sub-contract", "work package", "trade contract", "specialist contract"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000017', 'MaterialDelivery', 2, 'Material Delivery',
 'Delivery event of construction materials to site',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"delivery_note_number": {"type": "string"}, "delivery_date": {"type": "string", "format": "date"}, "material_type": {"type": "string"}, "quantity": {"type": "number"}, "unit": {"type": "string"}, "supplier": {"type": "string"}}}',
 '["material delivery", "delivery note", "site delivery", "materials received", "goods received"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000018', 'ConstructionDefect', 2, 'Construction Defect',
 'Defect or non-conformance identified during construction',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"defect_id": {"type": "string"}, "defect_type": {"type": "string"}, "location": {"type": "string"}, "severity": {"type": "string", "enum": ["MINOR", "MAJOR", "CRITICAL"]}, "status": {"type": "string", "enum": ["OPEN", "IN_PROGRESS", "CLOSED"]}}}',
 '["defect", "snag", "punch list item", "non-conformance", "NCR", "deficiency", "remedial work"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000019', 'PaymentCertificate', 2, 'Payment Certificate',
 'Certificate for progress payment to contractor',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"certificate_number": {"type": "string"}, "payment_period": {"type": "string"}, "gross_amount": {"type": "number"}, "retention": {"type": "number"}, "net_amount": {"type": "number"}, "status": {"type": "string", "enum": ["DRAFT", "SUBMITTED", "APPROVED", "PAID"]}}}',
 '["payment certificate", "IPC", "interim payment", "progress payment", "payment application"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000001A', 'ConstructionMaterial', 2, 'Construction Material',
 'Material used in construction works',
 '20000000-0000-0002-0000-000000000001',
 '{"type": "object", "properties": {"material_code": {"type": "string"}, "material_name": {"type": "string"}, "material_type": {"type": "string", "enum": ["CONCRETE", "STEEL", "AGGREGATE", "TIMBER", "ELECTRICAL", "MECHANICAL"]}, "specification": {"type": "string"}, "unit_of_measure": {"type": "string"}}}',
 '["construction material", "building material", "concrete", "rebar", "steel", "aggregate", "cement"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- CONSTRUCTION RELATIONSHIPS
-- =============================================================================

INSERT INTO ontology.relations (
    id, relation_type, source_type_id, target_type_id, 
    cardinality, semantics, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('30000000-0007-0000-0000-000000000001', 'PROJECT_AT_SITE', 
 '20000000-0007-0000-0000-000000000003', '20000000-0007-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Project is executed at construction site',
 '["at site", "project site", "located at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000002', 'PROJECT_HAS_BUDGET', 
 '20000000-0007-0000-0000-000000000003', '20000000-0007-0000-0000-000000000005',
 'ONE_TO_MANY',
 'Project has budget allocations',
 '["project budget", "budget for", "allocated budget"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000003', 'PROJECT_CONTRACTOR', 
 '20000000-0007-0000-0000-000000000003', '20000000-0007-0000-0000-000000000006',
 'MANY_TO_MANY',
 'Project has contractors',
 '["contractor for", "main contractor", "engaged contractor"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000004', 'PROJECT_CONSULTANT', 
 '20000000-0007-0000-0000-000000000003', '20000000-0007-0000-0000-000000000007',
 'MANY_TO_MANY',
 'Project has consultants',
 '["consultant for", "design consultant", "PMC for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000005', 'PROJECT_MANAGER_OF', 
 '20000000-0007-0000-0000-000000000008', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Project manager manages project',
 '["PM for", "manages", "project manager of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000006', 'SUPERVISES_SITE', 
 '20000000-0007-0000-0000-000000000009', '20000000-0007-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Site supervisor supervises construction site',
 '["supervises", "in charge of", "manages site"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000007', 'PROJECT_SPONSOR_OF', 
 '20000000-0007-0000-0000-00000000000A', '20000000-0007-0000-0000-000000000003',
 'ONE_TO_MANY',
 'Sponsor funds project',
 '["sponsor of", "client of", "owner of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000008', 'PROJECT_MILESTONE', 
 '20000000-0007-0000-0000-000000000003', '20000000-0007-0000-0000-00000000000B',
 'ONE_TO_MANY',
 'Project has milestones',
 '["milestone for", "key date", "project milestone"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000009', 'PROJECT_PHASE', 
 '20000000-0007-0000-0000-000000000003', '20000000-0007-0000-0000-00000000000C',
 'ONE_TO_MANY',
 'Project has phases',
 '["phase of", "project phase", "stage of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000000A', 'CHANGE_ORDER_FOR', 
 '20000000-0007-0000-0000-00000000000D', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Change order applies to project',
 '["change order for", "VO for", "variation on"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000000B', 'CONTRACT_FOR_PROJECT', 
 '20000000-0007-0000-0000-00000000000E', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Contract governs project',
 '["contract for", "agreement for", "covers project"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000000C', 'CONTRACT_WITH_CONTRACTOR', 
 '20000000-0007-0000-0000-00000000000E', '20000000-0007-0000-0000-000000000006',
 'MANY_TO_ONE',
 'Contract is with contractor',
 '["contract with", "contractor agreement", "engaged under"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000000D', 'DRAWING_FOR_PROJECT', 
 '20000000-0007-0000-0000-00000000000F', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Drawing belongs to project',
 '["drawing for", "project drawing", "design for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000000E', 'REPORT_FOR_PROJECT', 
 '20000000-0007-0000-0000-000000000010', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Progress report for project',
 '["report on", "progress for", "status of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000000F', 'INSPECTION_AT_SITE', 
 '20000000-0007-0000-0000-000000000011', '20000000-0007-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Safety inspection at construction site',
 '["inspection at", "site inspection", "conducted at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000010', 'PERMIT_FOR_PROJECT', 
 '20000000-0007-0000-0000-000000000012', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Permit issued for project',
 '["permit for", "authorization for", "approval for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000011', 'TENDER_FOR_PROJECT', 
 '20000000-0007-0000-0000-000000000013', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Tender document for project procurement',
 '["tender for", "RFP for", "bid for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000012', 'PPP_FOR_PROJECT', 
 '20000000-0007-0000-0000-000000000014', '20000000-0007-0000-0000-000000000003',
 'ONE_TO_ONE',
 'PPP agreement governs project',
 '["PPP for", "concession for", "partnership for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000013', 'COMMISSIONING_FOR_PROJECT', 
 '20000000-0007-0000-0000-000000000015', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Commissioning report for project',
 '["commissioning for", "handover of", "testing for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000014', 'SUBCONTRACT_FOR', 
 '20000000-0007-0000-0000-000000000016', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Subcontract is for project',
 '["subcontract for", "work package for", "trade contract for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000015', 'SUBCONTRACT_WITH', 
 '20000000-0007-0000-0000-000000000016', '20000000-0007-0000-0000-000000000006',
 'MANY_TO_ONE',
 'Subcontract is with subcontractor',
 '["subcontract with", "awarded to", "engaged"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000016', 'DELIVERY_TO_SITE', 
 '20000000-0007-0000-0000-000000000017', '20000000-0007-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Material delivery to construction site',
 '["delivered to", "received at", "site delivery"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000017', 'DELIVERY_OF_MATERIAL', 
 '20000000-0007-0000-0000-000000000017', '20000000-0007-0000-0000-00000000001A',
 'MANY_TO_ONE',
 'Delivery is of construction material',
 '["delivery of", "material delivered", "goods received"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000018', 'DEFECT_AT_SITE', 
 '20000000-0007-0000-0000-000000000018', '20000000-0007-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Defect identified at construction site',
 '["defect at", "snag at", "NCR at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000019', 'DEFECT_FOR_PROJECT', 
 '20000000-0007-0000-0000-000000000018', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Defect is for project',
 '["defect on", "project defect", "punch item for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000001A', 'PAYMENT_FOR_PROJECT', 
 '20000000-0007-0000-0000-000000000019', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Payment certificate for project',
 '["payment for", "IPC for", "progress payment for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000001B', 'PAYMENT_TO_CONTRACTOR', 
 '20000000-0007-0000-0000-000000000019', '20000000-0007-0000-0000-000000000006',
 'MANY_TO_ONE',
 'Payment certificate to contractor',
 '["payment to", "payable to", "certified for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000001C', 'MATERIAL_FOR_PROJECT', 
 '20000000-0007-0000-0000-00000000001A', '20000000-0007-0000-0000-000000000003',
 'MANY_TO_MANY',
 'Construction material used in project',
 '["material for", "used in", "specified for"]',
 'ACTIVE', 1.0, '1.0.0', NOW());
