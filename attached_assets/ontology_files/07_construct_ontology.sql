-- =============================================================================
-- Context Foundry: Project Development & Construction Domain Template
-- =============================================================================
-- Archetype: CONSTRUCT (ID: 07)
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: Perplexity AI
-- Date: 2025-12-06
-- RFC Version: 2.0 (Dual-System Architecture)
-- =============================================================================

-- =============================================================================
-- SHARED TYPE REFERENCES (from shared_ontology.sql)
-- These types are NOT defined here, only referenced
-- =============================================================================
-- Facility: 20000000-0000-0001-0000-000000000001
-- ProductionFacility: 20000000-0000-0001-0000-000000000002
-- ProcessingFacility: 20000000-0000-0001-0000-000000000003
-- StorageFacility: 20000000-0000-0001-0000-000000000004
-- TransportFacility: 20000000-0000-0001-0000-000000000005
-- Good: 20000000-0000-0002-0000-000000000001
-- Commodity: 20000000-0000-0002-0000-000000000002
-- FinishedProduct: 20000000-0000-0002-0000-000000000003
-- UtilityProduct: 20000000-0000-0002-0000-000000000004
-- Shipment: 20000000-0000-0003-0000-000000000001
-- Container: 20000000-0000-0003-0000-000000000002
-- TransportVehicle: 20000000-0000-0003-0000-000000000003
-- OperationalTeam: 20000000-0000-0004-0000-000000000001
-- MaintenanceTeam: 20000000-0000-0004-0000-000000000002
-- OperationsTeam: 20000000-0000-0004-0000-000000000003
-- QualityTeam: 20000000-0000-0004-0000-000000000004
-- OperationalDocument: 20000000-0000-0005-0000-000000000001
-- Procedure: 20000000-0000-0005-0000-000000000002
-- IncidentReport: 20000000-0000-0005-0000-000000000003
-- MaintenanceLog: 20000000-0000-0005-0000-000000000004
-- RegulatoryFiling: 20000000-0000-0005-0000-000000000005
-- LinearAsset: 20000000-0000-0006-0000-000000000001
-- =============================================================================

-- =============================================================================
-- ABSTRACT TYPES (intermediate hierarchy for CONSTRUCT domain)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

-- Construction-specific abstract facility hierarchy
('20000000-0007-0000-0000-000000000010', 'ConstructionFacility', 2, 'Construction Facility', 'Facility where construction or development activities occur. Abstract parent for construction sites and project facilities.',
'20000000-0000-0001-0000-000000000001',
'{"type": "object", "properties": {"facility_type": {"type": "string", "enum": ["TEMPORARY", "PERMANENT", "STAGING"]}, "is_active": {"type": "boolean"}}}',
'["construction facility", "site facility", "project facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Construction-specific abstract project hierarchy
('20000000-0007-0000-0000-000000000011', 'ConstructionProject', 2, 'Construction Project', 'Abstract parent for all construction and development projects. Inherits from Asset with project-specific properties.',
'10000000-0000-0000-0000-000000000001',
'{"type": "object", "properties": {"project_code": {"type": "string"}, "stakeholder_count": {"type": "integer"}}}',
'["construction project", "development project", "infrastructure project"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- =============================================================================
-- CONCRETE TYPES (extractable entities)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

-- Core Project Assets (now inherits through abstract types)
('20000000-0007-0000-0000-000000000001', 'Project', 2, 'Project', 'Construction or development project spanning multiple phases and stakeholders. Concrete implementation of ConstructionProject.',
'20000000-0007-0000-0000-000000000011',
'{"type": "object", "properties": {"project_id": {"type": "string"}, "project_name": {"type": "string"}, "project_type": {"type": "string", "enum": ["BUILDING", "INFRASTRUCTURE", "INDUSTRIAL", "MIXED_USE"]}, "delivery_model": {"type": "string", "enum": ["EPC", "EPCM", "DESIGN_BUILD", "TRADITIONAL", "PPP"]}, "start_date": {"type": "string", "format": "date-time"}, "end_date_planned": {"type": "string", "format": "date-time"}, "end_date_actual": {"type": "string", "format": "date-time"}, "status": {"type": "string", "enum": ["PLANNING", "TENDERING", "UNDER_CONSTRUCTION", "ON_HOLD", "COMMISSIONING", "COMPLETED"]}, "contract_value": {"type": "number"}, "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}, "location_description": {"type": "string"}}}',
'["project name", "project ID", "construction project", "EPC project", "design and build", "contract value", "project duration", "project status"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000002', 'ConstructionSite', 2, 'Construction Site', 'Physical location where construction activities are executed. Concrete implementation of ConstructionFacility.',
'20000000-0007-0000-0000-000000000010',
'{"type": "object", "properties": {"site_id": {"type": "string"}, "site_name": {"type": "string"}, "address": {"type": "string"}, "city": {"type": "string"}, "country": {"type": "string"}, "site_area_sqm": {"type": "number"}, "site_conditions": {"type": "string"}}}',
'["construction site", "site address", "project site", "jobsite", "site location", "site area"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000003', 'Budget', 2, 'Project Budget', 'Allocated financial resources for a project or phase',
'10000000-0000-0000-0000-000000000001',
'{"type": "object", "properties": {"budget_id": {"type": "string"}, "budget_type": {"type": "string", "enum": ["INITIAL", "REVISED", "FINAL"]}, "amount": {"type": "number"}, "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}, "contingency_amount": {"type": "number"}, "baseline_date": {"type": "string", "format": "date-time"}}}',
'["project budget", "budget allocation", "approved budget", "revised budget", "budget baseline", "cost plan"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Organizations & Roles
('20000000-0007-0000-0000-000000000004', 'Contractor', 2, 'Contractor', 'General or subcontractor responsible for delivering construction scope. Linked to OperationalTeam for team-based operations.',
'10000000-0000-0000-0000-000000000005',
'{"type": "object", "properties": {"contractor_id": {"type": "string"}, "contractor_name": {"type": "string"}, "contractor_type": {"type": "string", "enum": ["MAIN", "SUBCONTRACTOR", "EPC", "EPCM"]}, "trade": {"type": "string"}, "registration_number": {"type": "string"}}}',
'["contractor", "main contractor", "general contractor", "EPC contractor", "subcontractor", "builder"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000005', 'Consultant', 2, 'Consultant', 'Design, engineering, or specialist consultancy organization',
'10000000-0000-0000-0000-000000000005',
'{"type": "object", "properties": {"consultant_id": {"type": "string"}, "consultant_name": {"type": "string"}, "consultant_type": {"type": "string", "enum": ["DESIGN", "ENGINEERING", "SUPERVISION", "COST", "HSE", "COMMISSIONING"]}}}',
'["consultant", "design consultant", "engineering consultant", "supervision consultant", "PMC", "cost consultant"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000006', 'ProjectManager', 2, 'Project Manager', 'Person responsible for project delivery, schedule, cost, and quality',
'10000000-0000-0000-0000-000000000004',
'{"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string", "format": "email"}, "phone": {"type": "string"}, "employer": {"type": "string"}}}',
'["Project Manager", "PM", "project director", "overall project manager", "lead project manager"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000007', 'SiteSupervisor', 2, 'Site Supervisor', 'Person responsible for day-to-day supervision of construction activities on site',
'10000000-0000-0000-0000-000000000004',
'{"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string", "format": "email"}, "phone": {"type": "string"}, "shift": {"type": "string"}}}',
'["site supervisor", "site engineer", "construction manager", "site in-charge", "foreman"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000008', 'SponsorOrganization', 2, 'Sponsor Organization', 'Public or private organization sponsoring or owning the project',
'10000000-0000-0000-0000-000000000005',
'{"type": "object", "properties": {"org_id": {"type": "string"}, "org_name": {"type": "string"}, "org_role": {"type": "string", "enum": ["GOVERNMENT", "PRIVATE", "JV", "SPV"]}}}',
'["project sponsor", "client", "employer", "owner", "government entity", "special purpose vehicle", "SPV"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- =============================================================================
-- EVENT TYPES (temporal occurrences with temporal properties)
-- =============================================================================

('20000000-0007-0000-0000-000000000009', 'Milestone', 2, 'Milestone', 'Key project event marking completion of major deliverable or phase. Event-centric modeling captures temporal context.',
'00000000-0000-0000-0000-000000000002',
'{"type": "object", "properties": {"milestone_id": {"type": "string"}, "milestone_name": {"type": "string"}, "milestone_type": {"type": "string", "enum": ["CONTRACT_AWARD", "NOTICE_TO_PROCEED", "FOUNDATION_COMPLETION", "TOPPING_OUT", "MEP_COMPLETION", "COMMISSIONING_START", "SUBSTANTIAL_COMPLETION", "FINAL_COMPLETION"]}, "planned_date": {"type": "string", "format": "date-time"}, "actual_date": {"type": "string", "format": "date-time"}, "status": {"type": "string", "enum": ["PLANNED", "ACHIEVED", "DELAYED"]}}}',
'["milestone", "key milestone", "project milestone", "substantial completion", "topping out", "NTP", "notice to proceed"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000000A', 'Phase', 2, 'Project Phase', 'Distinct phase in the project lifecycle such as design, procurement, construction, commissioning. Event with time boundaries.',
'00000000-0000-0000-0000-000000000002',
'{"type": "object", "properties": {"phase_id": {"type": "string"}, "phase_name": {"type": "string"}, "phase_type": {"type": "string", "enum": ["INITIATION", "DESIGN", "PROCUREMENT", "CONSTRUCTION", "COMMISSIONING", "HANDOVER"]}, "start_date_planned": {"type": "string", "format": "date-time"}, "end_date_planned": {"type": "string", "format": "date-time"}, "start_date_actual": {"type": "string", "format": "date-time"}, "end_date_actual": {"type": "string", "format": "date-time"}}}',
'["project phase", "design phase", "procurement phase", "construction phase", "commissioning phase", "hand over phase"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000000B', 'ChangeOrder', 2, 'Change Order', 'Formal modification to contract scope, cost, or schedule. Event capturing scope change with temporal and financial impact.',
'00000000-0000-0000-0000-000000000002',
'{"type": "object", "properties": {"change_order_id": {"type": "string"}, "change_order_number": {"type": "string"}, "reason": {"type": "string", "enum": ["DESIGN_CHANGE", "SITE_CONDITION", "CLIENT_REQUEST", "REGULATORY", "VALUE_ENGINEERING"]}, "description": {"type": "string"}, "status": {"type": "string", "enum": ["PROPOSED", "APPROVED", "REJECTED", "IMPLEMENTED"]}, "cost_impact": {"type": "number"}, "time_impact_days": {"type": "integer"}, "submission_date": {"type": "string", "format": "date-time"}, "approval_date": {"type": "string", "format": "date-time"}}}',
'["change order", "variation order", "VO", "scope change", "contract change", "change directive"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Documents inherit from shared OperationalDocument
('20000000-0007-0000-0000-00000000000C', 'Contract', 2, 'EPC / Construction Contract', 'Contract defining scope, schedule, and commercial terms between owner and contractor. Inherits from shared OperationalDocument.',
'20000000-0000-0005-0000-000000000001',
'{"type": "object", "properties": {"contract_id": {"type": "string"}, "contract_number": {"type": "string"}, "contract_type": {"type": "string", "enum": ["EPC", "EPCM", "DESIGN_BUILD", "LUMP_SUM", "UNIT_RATE"]}, "signing_date": {"type": "string", "format": "date-time"}, "effective_date": {"type": "string", "format": "date-time"}, "contract_value": {"type": "number"}, "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}, "completion_time_days": {"type": "integer"}}}',
'["EPC Contract", "construction contract", "contract number", "agreement", "design-build contract", "lump sum contract"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000000D', 'Drawing', 2, 'Construction Drawing', 'Engineering or architectural drawing issued for design, tender, or construction. Inherits from shared OperationalDocument.',
'20000000-0000-0005-0000-000000000001',
'{"type": "object", "properties": {"drawing_number": {"type": "string"}, "revision": {"type": "string"}, "drawing_type": {"type": "string", "enum": ["ARCHITECTURAL", "STRUCTURAL", "MEP", "CIVIL", "SHOP_DRAWING", "AS_BUILT"]}, "issue_purpose": {"type": "string", "enum": ["FOR_INFORMATION", "FOR_TENDER", "FOR_CONSTRUCTION", "AS_BUILT"]}, "issue_date": {"type": "string", "format": "date-time"}}}',
'["drawing no.", "construction drawing", "shop drawing", "for construction", "IFC drawing", "as-built drawing", "tender drawing"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000000E', 'ProgressReport', 2, 'Progress Report', 'Periodic report summarizing physical and financial progress of project. Inherits from shared OperationalDocument.',
'20000000-0000-0005-0000-000000000001',
'{"type": "object", "properties": {"report_id": {"type": "string"}, "report_period_start": {"type": "string", "format": "date-time"}, "report_period_end": {"type": "string", "format": "date-time"}, "overall_progress_percent": {"type": "number", "minimum": 0, "maximum": 100}, "physical_progress_percent": {"type": "number", "minimum": 0, "maximum": 100}, "financial_progress_percent": {"type": "number", "minimum": 0, "maximum": 100}}}',
'["progress report", "monthly progress", "weekly progress", "site progress", "overall progress", "physical progress", "financial progress"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000000F', 'SafetyInspection', 2, 'Safety Inspection Report', 'Report documenting safety inspections, findings, and corrective actions on site. Inherits from shared IncidentReport.',
'20000000-0000-0005-0000-000000000003',
'{"type": "object", "properties": {"inspection_id": {"type": "string"}, "inspection_date": {"type": "string", "format": "date-time"}, "inspector_name": {"type": "string"}, "inspection_type": {"type": "string", "enum": ["ROUTINE", "INCIDENT_BASED", "AUDIT"]}, "non_conformities_count": {"type": "integer"}, "stoppage_issued": {"type": "boolean"}}}',
'["safety inspection", "HSE inspection", "site inspection", "safety audit", "HSE report", "non-conformance", "corrective actions"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000012', 'Permit', 2, 'Construction Permit', 'Official permit or approval required for construction activities. Inherits from shared RegulatoryFiling.',
'20000000-0000-0005-0000-000000000005',
'{"type": "object", "properties": {"permit_id": {"type": "string"}, "permit_type": {"type": "string", "enum": ["BUILDING", "EXCAVATION", "DEMOLITION", "HOT_WORK", "ROAD_CLOSURE"]}, "issuing_authority": {"type": "string"}, "issue_date": {"type": "string", "format": "date-time"}, "expiry_date": {"type": "string", "format": "date-time"}, "status": {"type": "string", "enum": ["APPLIED", "APPROVED", "REJECTED", "EXPIRED"]}}}',
'["building permit", "construction permit", "excavation permit", "demolition permit", "hot work permit", "road closure permit"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000013', 'TenderDocument', 2, 'Tender Document', 'Document package issued for bidding including scope, drawings, and commercial conditions. Inherits from shared OperationalDocument.',
'20000000-0000-0005-0000-000000000001',
'{"type": "object", "properties": {"tender_id": {"type": "string"}, "tender_reference": {"type": "string"}, "issue_date": {"type": "string", "format": "date-time"}, "submission_deadline": {"type": "string", "format": "date-time"}, "tender_status": {"type": "string", "enum": ["OPEN", "CLOSED", "CANCELLED", "AWARDED"]}}}',
'["tender document", "RFP", "request for proposal", "tender reference", "bid documents", "invitation to tender"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000014', 'PPPAgreement', 2, 'PPP Agreement', 'Public-private partnership agreement defining rights, obligations, and risk allocation. Inherits from shared OperationalDocument.',
'20000000-0000-0005-0000-000000000001',
'{"type": "object", "properties": {"ppp_id": {"type": "string"}, "agreement_name": {"type": "string"}, "ppp_model": {"type": "string", "enum": ["DBFOM", "BOT", "BOO", "DBFO"]}, "signature_date": {"type": "string", "format": "date-time"}, "concession_term_years": {"type": "integer"}}}',
'["PPP agreement", "public-private partnership", "concession agreement", "DBFOM", "BOT contract", "PPP contract"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000015', 'CommissioningReport', 2, 'Commissioning Report', 'Report documenting testing, commissioning, and handover status of systems and facilities. Inherits from shared OperationalDocument.',
'20000000-0000-0005-0000-000000000001',
'{"type": "object", "properties": {"report_id": {"type": "string"}, "commissioning_phase": {"type": "string", "enum": ["PRE_COMMISSIONING", "COMMISSIONING", "POST_COMMISSIONING"]}, "report_date": {"type": "string", "format": "date-time"}, "systems_covered": {"type": "string"}, "issues_open": {"type": "integer"}, "issues_closed": {"type": "integer"}}}',
'["commissioning report", "testing and commissioning", "pre-commissioning", "system handover", "commissioning status", "commissioning checklist"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Additional Entity Types (from QA review)
('20000000-0007-0000-0000-000000000016', 'Subcontract', 2, 'Subcontract',
'Contract between main contractor and subcontractor for specific work package.',
'20000000-0000-0005-0000-000000000001',
'{"type": "object", "properties": {"subcontract_id": {"type": "string"}, "subcontract_number": {"type": "string"}, "work_package": {"type": "string"}, "trade": {"type": "string", "enum": ["STRUCTURAL", "MEP", "CIVIL", "FINISHING", "FACADE", "LANDSCAPING", "SPECIALIST"]}, "award_date": {"type": "string", "format": "date"}, "completion_date": {"type": "string", "format": "date"}, "value": {"type": "number"}, "currency": {"type": "string"}, "status": {"type": "string", "enum": ["DRAFT", "AWARDED", "IN_PROGRESS", "COMPLETED", "TERMINATED"]}}}',
'["subcontract", "sub-contract", "work package", "trade contract", "specialist contract", "MEP subcontract", "structural subcontract"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000017', 'MaterialDelivery', 2, 'Material Delivery',
'Delivery event of construction materials to site.',
'00000000-0000-0000-0000-000000000002',
'{"type": "object", "properties": {"delivery_id": {"type": "string"}, "delivery_date": {"type": "string", "format": "date-time"}, "material_type": {"type": "string"}, "quantity": {"type": "number"}, "unit": {"type": "string"}, "supplier": {"type": "string"}, "delivery_note": {"type": "string"}, "inspection_status": {"type": "string", "enum": ["PENDING", "PASSED", "REJECTED", "PARTIAL"]}}}',
'["material delivery", "delivery note", "site delivery", "materials received", "goods received", "delivery date", "DN"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000018', 'ConstructionDefect', 2, 'Construction Defect',
'Defect or non-conformance identified during construction or inspection.',
'00000000-0000-0000-0000-000000000002',
'{"type": "object", "properties": {"defect_id": {"type": "string"}, "defect_type": {"type": "string", "enum": ["STRUCTURAL", "FINISHING", "MEP", "WATERPROOFING", "DIMENSIONAL", "MATERIAL"]}, "location": {"type": "string"}, "severity": {"type": "string", "enum": ["CRITICAL", "MAJOR", "MINOR"]}, "identified_date": {"type": "string", "format": "date"}, "rectification_date": {"type": "string", "format": "date"}, "status": {"type": "string", "enum": ["OPEN", "IN_PROGRESS", "RECTIFIED", "VERIFIED"]}}}',
'["defect", "snag", "punch list item", "non-conformance", "NCR", "deficiency", "rework", "remediation"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-000000000019', 'PaymentCertificate', 2, 'Payment Certificate',
'Certificate certifying completed work for payment.',
'20000000-0000-0005-0000-000000000001',
'{"type": "object", "properties": {"certificate_id": {"type": "string"}, "certificate_number": {"type": "integer"}, "period_start": {"type": "string", "format": "date"}, "period_end": {"type": "string", "format": "date"}, "gross_amount": {"type": "number"}, "retention": {"type": "number"}, "net_amount": {"type": "number"}, "currency": {"type": "string"}, "status": {"type": "string", "enum": ["DRAFT", "SUBMITTED", "APPROVED", "PAID"]}}}',
'["payment certificate", "IPC", "interim payment", "progress payment", "payment application", "valuation"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0007-0000-0000-00000000001A', 'ConstructionMaterial', 2, 'Construction Material',
'Material used in construction works.',
'20000000-0000-0002-0000-000000000002',
'{"type": "object", "properties": {"material_code": {"type": "string"}, "material_name": {"type": "string"}, "category": {"type": "string", "enum": ["CONCRETE", "STEEL", "TIMBER", "AGGREGATES", "FINISHES", "MEP", "SPECIALIST"]}, "unit": {"type": "string"}, "specification": {"type": "string"}, "approved_suppliers": {"type": "array", "items": {"type": "string"}}}}',
'["construction material", "building material", "concrete", "rebar", "steel", "aggregate", "finishing material", "insulation"]',
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

-- Project & Location (structural relationship)
('30000000-0007-0000-0000-000000000001', 'LOCATED_AT', '20000000-0007-0000-0000-000000000001', '20000000-0007-0000-0000-000000000002', 'MANY_TO_ONE',
'Project is executed at specific construction site',
'["project located at", "site location", "project site", "constructed at", "site address"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Organizations & Responsibilities
('30000000-0007-0000-0000-000000000002', 'WORKS_ON', '20000000-0007-0000-0000-000000000004', '20000000-0007-0000-0000-000000000001', 'MANY_TO_MANY',
'Contractor is engaged to deliver scope on project',
'["contractor for", "engaged on project", "appointed as main contractor", "appointed as subcontractor", "works on project"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000003', 'DESIGNS', '20000000-0007-0000-0000-000000000005', '20000000-0007-0000-0000-000000000001', 'MANY_TO_MANY',
'Consultant provides design or engineering services for project',
'["design consultant for", "engineer for", "architect for", "provides design services", "responsible for design"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000004', 'MANAGES', '20000000-0007-0000-0000-000000000006', '20000000-0007-0000-0000-000000000001', 'MANY_TO_ONE',
'Project manager is accountable for overall delivery of project',
'["Project Manager", "managed by", "overall project manager", "PM for", "project director"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000005', 'SUPERVISES', '20000000-0007-0000-0000-000000000007', '20000000-0007-0000-0000-000000000002', 'MANY_TO_ONE',
'Site supervisor is responsible for day-to-day supervision of construction site',
'["site supervisor", "site in-charge", "supervises site", "site managed by", "construction manager"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000006', 'SPONSORS', '20000000-0007-0000-0000-000000000008', '20000000-0007-0000-0000-000000000001', 'MANY_TO_ONE',
'Sponsor organization funds or owns the project',
'["project sponsor", "client", "employer", "owner of project", "sponsored by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Phases, Milestones, and Progress (event-centric)
('30000000-0007-0000-0000-000000000007', 'HAS_PHASE', '20000000-0007-0000-0000-000000000001', '20000000-0007-0000-0000-00000000000A', 'ONE_TO_MANY',
'Project is divided into distinct phases (events with temporal boundaries)',
'["project phase", "phase of", "phase name", "construction phase", "design phase"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000008', 'ACHIEVES', '20000000-0007-0000-0000-000000000001', '20000000-0007-0000-0000-000000000009', 'ONE_TO_MANY',
'Project achieves key milestones (temporal events)',
'["milestone achieved", "substantial completion", "topping out", "NTP issued", "final completion"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000009', 'REPORTS_PROGRESS_FOR', '20000000-0007-0000-0000-00000000000E', '20000000-0007-0000-0000-000000000001', 'MANY_TO_ONE',
'Progress report documents status of project during reporting period',
'["progress report for", "project progress", "status of project", "monthly report", "weekly report"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Contracts, Change Orders, and Budget
('30000000-0007-0000-0000-00000000000A', 'GOVERNED_BY_CONTRACT', '20000000-0007-0000-0000-000000000001', '20000000-0007-0000-0000-00000000000C', 'MANY_TO_ONE',
'Project is governed by main EPC or construction contract (structural)',
'["under contract", "EPC contract", "governed by", "contract number", "main contract"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000000B', 'MODIFIES_CONTRACT', '20000000-0007-0000-0000-00000000000B', '20000000-0007-0000-0000-00000000000C', 'MANY_TO_ONE',
'Change order (event) modifies scope, cost, or schedule under contract',
'["change order to", "variation to contract", "VO against", "amendment to contract", "modifies contract"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000000C', 'ALLOCATED_TO_PHASE', '20000000-0007-0000-0000-000000000003', '20000000-0007-0000-0000-00000000000A', 'MANY_TO_MANY',
'Budget is allocated across project phases (events)',
'["budget allocation", "allocated to phase", "phase budget", "budget for construction phase", "budget for design phase"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000000D', 'RELATES_TO_PROJECT', '20000000-0007-0000-0000-00000000000B', '20000000-0007-0000-0000-000000000001', 'MANY_TO_ONE',
'Change order (event) belongs to specific project',
'["project change", "change order for project", "project VO", "scope change in project"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Safety, Permits, and Compliance
('30000000-0007-0000-0000-00000000000E', 'INSPECTS_SITE', '20000000-0007-0000-0000-00000000000F', '20000000-0007-0000-0000-000000000002', 'MANY_TO_ONE',
'Safety inspection is performed for specific construction site',
'["site inspection", "HSE inspection", "inspection of site", "safety audit of site"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000000F', 'REQUIRES_PERMIT', '20000000-0007-0000-0000-000000000001', '20000000-0007-0000-0000-000000000012', 'ONE_TO_MANY',
'Project requires permits to execute certain activities',
'["subject to permit", "building permit for", "permit required", "work permit", "construction permit"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Tendering & PPP
('30000000-0007-0000-0000-000000000010', 'TENDERED_THROUGH', '20000000-0007-0000-0000-000000000001', '20000000-0007-0000-0000-000000000013', 'MANY_TO_ONE',
'Project was procured via specific tender process and tender documents',
'["tender for", "RFP for", "invitation to tender", "tender reference", "procured through tender"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000011', 'STRUCTURED_BY_PPP', '20000000-0007-0000-0000-000000000001', '20000000-0007-0000-0000-000000000014', 'MANY_TO_ONE',
'Project is structured and governed under PPP agreement',
'["PPP project", "under PPP agreement", "concession agreement", "public-private partnership"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Commissioning & Handover
('30000000-0007-0000-0000-000000000012', 'COMMISSIONED_BY', '20000000-0007-0000-0000-000000000015', '20000000-0007-0000-0000-000000000001', 'MANY_TO_ONE',
'Commissioning report documents commissioning activities for project',
'["commissioning of", "testing and commissioning", "commissioning report for", "systems commissioned", "handover testing"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000013', 'DOCUMENTS_PROJECT', 
 '20000000-0007-0000-0000-00000000000D', '20000000-0007-0000-0000-000000000001',
 'MANY_TO_MANY',
 'Drawing documents aspects of a construction project',
 '["drawing for", "architectural drawing", "engineering drawing", "plans for", "blueprints"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Additional Relationships (from QA review)
('30000000-0007-0000-0000-000000000014', 'SUBCONTRACT_FOR', 
 '20000000-0007-0000-0000-000000000016', '20000000-0007-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Subcontract is for a project',
 '["subcontract for", "work package for", "sub-contract on project"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000015', 'SUBCONTRACT_WITH', 
 '20000000-0007-0000-0000-000000000016', '20000000-0007-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Subcontract is awarded to a contractor',
 '["subcontract with", "awarded to", "contracted to"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000016', 'DELIVERY_TO_SITE', 
 '20000000-0007-0000-0000-000000000017', '20000000-0007-0000-0000-000000000002',
 'MANY_TO_ONE',
 'Material delivery is to a construction site',
 '["delivered to", "delivery to site", "materials at site"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000017', 'DELIVERY_OF_MATERIAL', 
 '20000000-0007-0000-0000-000000000017', '20000000-0007-0000-0000-00000000001A',
 'MANY_TO_ONE',
 'Material delivery is of a specific material type',
 '["delivery of", "material delivered", "goods received"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000018', 'DEFECT_AT_SITE', 
 '20000000-0007-0000-0000-000000000018', '20000000-0007-0000-0000-000000000002',
 'MANY_TO_ONE',
 'Defect is identified at a construction site',
 '["defect at", "snag at site", "issue at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-000000000019', 'DEFECT_FOR_PROJECT', 
 '20000000-0007-0000-0000-000000000018', '20000000-0007-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Defect is associated with a project',
 '["defect for project", "project defect", "punch list for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000001A', 'PAYMENT_FOR_PROJECT', 
 '20000000-0007-0000-0000-000000000019', '20000000-0007-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Payment certificate is for a project',
 '["payment for", "IPC for project", "valuation for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000001B', 'PAYMENT_TO_CONTRACTOR', 
 '20000000-0007-0000-0000-000000000019', '20000000-0007-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Payment certificate is issued to a contractor',
 '["payment to", "paid to contractor", "certified for payment"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0007-0000-0000-00000000001C', 'MATERIAL_FOR_PROJECT', 
 '20000000-0007-0000-0000-00000000001A', '20000000-0007-0000-0000-000000000001',
 'MANY_TO_MANY',
 'Construction material is used for a project',
 '["material for", "used in project", "specified for"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- END OF PROJECT DEVELOPMENT & CONSTRUCTION ONTOLOGY
-- =============================================================================