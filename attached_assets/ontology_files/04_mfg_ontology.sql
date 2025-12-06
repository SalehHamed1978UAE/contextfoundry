-- =============================================================================
-- Context Foundry: Manufacturing & Industrial Production Domain Template
-- =============================================================================
-- Archetype: MFG (ID: 04)
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: Perplexity
-- Date: 2025-12-06
-- RFC Version: 2.0 (Dual-System Architecture)
-- Status: REFACTORED - Full architectural alignment
-- =============================================================================

-- =============================================================================
-- SHARED TYPE REFERENCES (from shared_ontology.sql)
-- These types are NOT defined here, only referenced in relationships
-- =============================================================================
-- Facility: 20000000-0000-0001-0000-000000000001
-- ProductionFacility: 20000000-0000-0001-0000-000000000002
-- ProcessingFacility: 20000000-0000-0001-0000-000000000003
-- Good: 20000000-0000-0002-0000-000000000001
-- Commodity: 20000000-0000-0002-0000-000000000002
-- FinishedProduct: 20000000-0000-0002-0000-000000000003
-- Shipment: 20000000-0000-0003-0000-000000000001
-- OperationalTeam: 20000000-0000-0004-0000-000000000001
-- OperationsTeam: 20000000-0000-0004-0000-000000000003
-- QualityTeam: 20000000-0000-0004-0000-000000000004
-- OperationalDocument: 20000000-0000-0005-0000-000000000001
-- =============================================================================

-- =============================================================================
-- ABSTRACT TYPES (intermediate hierarchy for manufacturing domain)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

-- Manufacturing-specific facility abstraction
('20000000-0004-0000-0000-000000000001', 'ManufacturingFacility', 2, 'Manufacturing Facility',
 'Facility where manufacturing or production activities occur. Parent for plants, mills, factories.',
 '20000000-0000-0001-0000-000000000002', -- parent: shared ProductionFacility
 '{"type": "object", "properties": {"manufacturing_type": {"type": "string", "enum": ["steel", "cables", "pipes", "packaging", "leather", "general"]}, "employee_count": {"type": "integer"}, "shift_pattern": {"type": "string", "enum": ["24x7", "two_shift", "single_shift"]}, "certifications": {"type": "array", "items": {"type": "string"}}}}',
 '["manufacturing facility", "manufacturing plant", "factory", "mill", "production works", "EMSTEEL", "Ducab", "Al Gharbia"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Quality-specific facility abstraction
('20000000-0004-0000-0000-000000000002', 'QualityFacility', 2, 'Quality Facility',
 'Facility where quality control and testing activities occur. Inherits from ProcessingFacility.',
 '20000000-0000-0001-0000-000000000003', -- parent: shared ProcessingFacility
 '{"type": "object", "properties": {"test_capacity": {"type": "integer"}, "accreditations": {"type": "array", "items": {"type": "string"}}, "equipment_list": {"type": "array", "items": {"type": "string"}}}}',
 '["quality facility", "QC laboratory", "testing center", "inspection facility", "lab", "quality lab"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- CONCRETE TYPES - FACILITIES (extractable manufacturing-specific entities)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0004-0000-0000-000000000003', 'ManufacturingPlant', 2, 'Manufacturing Plant',
 'Large-scale facility where industrial manufacturing takes place. Produces finished goods from raw materials.',
 '20000000-0004-0000-0000-000000000001', -- parent: ManufacturingFacility (MFG abstract)
 '{"type": "object", "properties": {"plant_code": {"type": "string"}, "total_capacity": {"type": "string"}, "commissioning_date": {"type": "string", "format": "date"}, "major_equipment": {"type": "array", "items": {"type": "string"}}, "environmental_rating": {"type": "string"}}}',
 '["manufacturing plant", "mill", "factory", "production plant", "works", "EMSTEEL", "Ducab facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-000000000004', 'ProductionLine', 2, 'Production Line',
 'Sequence of equipment and processes for manufacturing. Parent type: ManufacturingFacility part.',
 '20000000-0004-0000-0000-000000000001', -- parent: ManufacturingFacility
 '{"type": "object", "properties": {"line_id": {"type": "string"}, "line_name": {"type": "string"}, "process_type": {"type": "string"}, "throughput_rate": {"type": "string"}, "throughput_unit": {"type": "string"}, "operational_status": {"type": "string", "enum": ["running", "idle", "down", "maintenance"]}}}',
 '["production line", "assembly line", "rolling mill", "extrusion line", "Line A", "cable line", "pipe line"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-000000000005', 'QCLab', 2, 'QC Laboratory',
 'Designated facility where quality control testing is performed. Part of QualityFacility hierarchy.',
 '20000000-0004-0000-0000-000000000002', -- parent: QualityFacility (MFG abstract)
 '{"type": "object", "properties": {"lab_name": {"type": "string"}, "lab_code": {"type": "string"}, "test_types": {"type": "array", "items": {"type": "string"}}, "accreditation": {"type": "string"}}}',
 '["QC lab", "quality laboratory", "testing laboratory", "material testing lab", "inspection center"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-000000000006', 'Inventory', 2, 'Inventory Stock',
 'Stock of materials, finished products, or equipment held at a location. Structural asset.',
 '20000000-0000-0001-0000-000000000004', -- parent: shared StorageFacility
 '{"type": "object", "properties": {"stock_level": {"type": "number"}, "stock_unit": {"type": "string"}, "reorder_point": {"type": "number"}, "location_code": {"type": "string"}, "valuation_currency": {"type": "string"}, "valuation_amount": {"type": "number"}}}',
 '["stock", "inventory", "warehouse stock", "material stock", "spare parts inventory", "finished goods inventory"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- CONCRETE TYPES - GOODS (use shared hierarchy, domain-specific only)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0004-0000-0000-000000000007', 'RawMaterial', 2, 'Raw Material',
 'Basic input material for manufacturing. Inherits from shared Commodity. MFG-specific tracking.',
 '20000000-0000-0002-0000-000000000002', -- parent: shared Commodity
 '{"type": "object", "properties": {"material_code": {"type": "string"}, "supplier_batch": {"type": "string"}, "supplier_name": {"type": "string"}, "receiving_date": {"type": "string", "format": "date"}, "expiry_date": {"type": "string", "format": "date"}, "hazard_class": {"type": "string"}}}',
 '["feedstock", "raw material", "input material", "billet", "copper rod", "polymer granules", "cement clinker", "steel scrap"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-000000000008', 'ProductBatch', 2, 'Product Batch',
 'Specific quantity of goods produced under same conditions in single manufacturing run. Structural asset.',
 '10000000-0000-0000-0000-000000000001', -- parent: Asset (L1) - batch is tracking entity
 '{"type": "object", "properties": {"batch_number": {"type": "string"}, "product_ref": {"type": "string"}, "manufacture_date": {"type": "string", "format": "date"}, "batch_size": {"type": "number"}, "batch_unit": {"type": "string"}, "quality_status": {"type": "string", "enum": ["pass", "fail", "rework", "pending"]}, "lot_expiry": {"type": "string", "format": "date"}}}',
 '["batch number", "lot number", "production run", "heat number", "batch", "lot"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- Note: FinishedProduct uses shared UUID (20000000-0000-0002-0000-000000000003)
-- Do NOT redefine here. Domain will reference shared UUID in relationships.

-- =============================================================================
-- CONCRETE TYPES - DOCUMENTATION (manufacturing-specific documents)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0004-0000-0000-000000000009', 'ProductSpec', 2, 'Product Specification',
 'Document defining requirements and standards for a specific product. Inherits from OperationalDocument (shared).',
 '20000000-0000-0005-0000-000000000001', -- parent: shared OperationalDocument
 '{"type": "object", "properties": {"spec_id": {"type": "string"}, "revision": {"type": "string"}, "valid_from": {"type": "string", "format": "date"}, "valid_to": {"type": "string", "format": "date"}, "technical_standards": {"type": "array", "items": {"type": "string"}}, "approved_by": {"type": "string"}}}',
 '["product spec", "technical specification", "datasheet", "tolerance sheet", "ASTM standard", "ISO specification", "drawing"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-00000000000A', 'QCReport', 2, 'Quality Control Report',
 'Document recording results of quality testing procedures. Inherits from OperationalDocument.',
 '20000000-0000-0005-0000-000000000001', -- parent: shared OperationalDocument
 '{"type": "object", "properties": {"report_id": {"type": "string"}, "test_date": {"type": "string", "format": "date"}, "overall_result": {"type": "string", "enum": ["pass", "fail", "conditional"]}, "test_count": {"type": "integer"}, "passed_tests": {"type": "integer"}, "failed_tests": {"type": "integer"}, "inspector_name": {"type": "string"}}}',
 '["QC report", "test certificate", "certificate of analysis", "CoA", "inspection report", "test results"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-00000000000B', 'MSDS', 2, 'Material Safety Data Sheet',
 'Document listing occupational safety and health information for materials. Safety document type.',
 '20000000-0000-0005-0000-000000000001', -- parent: shared OperationalDocument
 '{"type": "object", "properties": {"material_name": {"type": "string"}, "cas_number": {"type": "string"}, "revision_date": {"type": "string", "format": "date"}, "hazard_statements": {"type": "array", "items": {"type": "string"}}, "emergency_contact": {"type": "string"}}}',
 '["MSDS", "safety data sheet", "SDS", "chemical safety data", "hazard sheet"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- EVENT TYPES (temporal manufacturing occurrences)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0004-0000-0000-00000000000C', 'ProductionRun', 2, 'Production Run',
 'Event of executing a production order on a production line. Core manufacturing event capturing execution.',
 '00000000-0000-0000-0000-000000000002', -- parent: Event (L0)
 '{"type": "object", "properties": {"run_id": {"type": "string"}, "scheduled_start": {"type": "string", "format": "date-time"}, "actual_start": {"type": "string", "format": "date-time"}, "scheduled_end": {"type": "string", "format": "date-time"}, "actual_end": {"type": "string", "format": "date-time"}, "scheduled_duration_hours": {"type": "number"}, "actual_duration_hours": {"type": "number"}, "output_quantity": {"type": "number"}, "output_unit": {"type": "string"}, "status": {"type": "string", "enum": ["planned", "in_progress", "completed", "failed", "stopped"]}}}',
 '["production run", "run", "manufacturing run", "batch run", "execution", "shift production"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-00000000000D', 'ProductionOrder', 2, 'Production Order',
 'Order issued to produce specific quantity of material. Planning event.',
 '00000000-0000-0000-0000-000000000002', -- parent: Event (L0)
 '{"type": "object", "properties": {"order_number": {"type": "string"}, "due_date": {"type": "string", "format": "date"}, "priority": {"type": "string", "enum": ["high", "medium", "low", "rush"]}, "target_quantity": {"type": "number"}, "target_unit": {"type": "string"}, "customer_ref": {"type": "string"}}}',
 '["production order", "work order", "manufacturing order", "job ticket", "MO", "PO", "work request"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-00000000000E', 'QCTestEvent', 2, 'QC Test Event',
 'Event of performing quality test on product batch. Captures test execution with temporal context.',
 '00000000-0000-0000-0000-000000000002', -- parent: Event (L0)
 '{"type": "object", "properties": {"test_id": {"type": "string"}, "test_type": {"type": "string"}, "test_date": {"type": "string", "format": "date-time"}, "measured_value": {"type": "string"}, "expected_value": {"type": "string"}, "tolerance": {"type": "string"}, "result": {"type": "string", "enum": ["pass", "fail", "pending"]}, "test_duration_minutes": {"type": "number"}}}',
 '["tensile test", "chemical analysis", "visual inspection", "pressure test", "hardness test", "dimensional check"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Additional Entity Types (from QA review)
('20000000-0004-0000-0000-00000000000F', 'Supplier', 2, 'Supplier',
 'Organization that supplies raw materials or components to manufacturing.',
 '10000000-0000-0000-0000-000000000005', -- parent: Organization (L1)
 '{"type": "object", "properties": {"supplier_id": {"type": "string"}, "supplier_name": {"type": "string"}, "supplier_type": {"type": "string", "enum": ["raw_material", "component", "equipment", "service"]}, "country": {"type": "string"}, "lead_time_days": {"type": "integer"}, "quality_rating": {"type": "string", "enum": ["A", "B", "C", "D"]}, "certified": {"type": "boolean"}}}',
 '["supplier", "vendor", "manufacturer", "source", "material supplier", "parts supplier", "supplier code"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-000000000010', 'Equipment', 2, 'Equipment',
 'Manufacturing equipment or machine used in production.',
 '10000000-0000-0000-0000-000000000001', -- parent: Asset (L1)
 '{"type": "object", "properties": {"equipment_id": {"type": "string"}, "equipment_name": {"type": "string"}, "equipment_type": {"type": "string", "enum": ["furnace", "press", "roller", "extruder", "mixer", "conveyor", "crane", "other"]}, "manufacturer": {"type": "string"}, "model": {"type": "string"}, "installation_date": {"type": "string", "format": "date"}, "status": {"type": "string", "enum": ["operational", "maintenance", "breakdown", "decommissioned"]}, "capacity": {"type": "string"}}}',
 '["equipment", "machine", "machinery", "furnace", "rolling mill", "press", "extruder", "asset tag", "equipment ID"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-000000000011', 'EquipmentMaintenance', 2, 'Equipment Maintenance',
 'Scheduled or unscheduled maintenance activity on manufacturing equipment.',
 '00000000-0000-0000-0000-000000000002', -- parent: Event (L0)
 '{"type": "object", "properties": {"work_order": {"type": "string"}, "maintenance_type": {"type": "string", "enum": ["preventive", "corrective", "predictive", "breakdown"]}, "scheduled_date": {"type": "string", "format": "date-time"}, "completed_date": {"type": "string", "format": "date-time"}, "downtime_hours": {"type": "number"}, "parts_replaced": {"type": "array", "items": {"type": "string"}}, "technician": {"type": "string"}}}',
 '["maintenance", "repair", "service", "PM", "preventive maintenance", "breakdown", "work order", "downtime", "equipment maintenance"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0004-0000-0000-000000000012', 'DefectEvent', 2, 'Defect Event',
 'Quality defect identified in production or inspection.',
 '00000000-0000-0000-0000-000000000002', -- parent: Event (L0)
 '{"type": "object", "properties": {"defect_id": {"type": "string"}, "defect_type": {"type": "string", "enum": ["dimensional", "surface", "chemical", "mechanical", "visual"]}, "severity": {"type": "string", "enum": ["critical", "major", "minor"]}, "detection_date": {"type": "string", "format": "date"}, "root_cause": {"type": "string"}, "corrective_action": {"type": "string"}, "quantity_affected": {"type": "number"}}}',
 '["defect", "non-conformance", "NCR", "reject", "rework", "deviation", "quality issue", "scrap"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- Note: Shipment uses shared UUID (20000000-0000-0003-0000-000000000001)
-- Do NOT define separately. Reference shared Shipment in relationships.

-- =============================================================================
-- RELATIONSHIP TYPES (MFG domain relationships)
-- =============================================================================

INSERT INTO ontology.relations (
    id, relation_type, source_type_id, target_type_id, 
    cardinality, semantics, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

-- Production-centric relationships (event-centric pattern)
('30000000-0004-0000-0000-000000000001', 'FULFILLS',
 '20000000-0004-0000-0000-00000000000C', '20000000-0004-0000-0000-00000000000D',
 'MANY_TO_ONE',
 'Production run fulfills a production order. Links execution event to planning event.',
 '["fulfills", "executes", "completes", "fulfilling order"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000002', 'ON_LINE',
 '20000000-0004-0000-0000-00000000000C', '20000000-0004-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Production run occurs on a specific production line.',
 '["on line", "runs on", "line runs", "executes on", "produced on"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000003', 'CONSUMES',
 '20000000-0004-0000-0000-00000000000C', '20000000-0004-0000-0000-000000000007',
 'MANY_TO_MANY',
 'Production run consumes raw materials as inputs.',
 '["consumes", "uses input", "requires material", "fed with", "inputs"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000004', 'PRODUCES',
 '20000000-0004-0000-0000-00000000000C', '20000000-0000-0002-0000-000000000003',
 'MANY_TO_MANY',
 'Production run produces finished products. References shared FinishedProduct.',
 '["produces", "manufactures", "outputs", "generates", "yields"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000005', 'CREATES_BATCH',
 '20000000-0004-0000-0000-00000000000C', '20000000-0004-0000-0000-000000000008',
 'ONE_TO_MANY',
 'Production run creates product batches for tracking and testing.',
 '["creates batch", "batch from", "produces batch", "batch of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Quality assurance (event-centric pattern)
('30000000-0004-0000-0000-000000000006', 'TESTS',
 '20000000-0004-0000-0000-00000000000E', '20000000-0004-0000-0000-000000000008',
 'MANY_TO_ONE',
 'QC test event tests a product batch.',
 '["tests", "inspects", "analyzes", "examines", "evaluates"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000007', 'AT_LAB',
 '20000000-0004-0000-0000-00000000000E', '20000000-0004-0000-0000-000000000005',
 'MANY_TO_ONE',
 'QC test event occurs at a specific QC laboratory.',
 '["at lab", "conducted at", "performed in", "at facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000008', 'PRODUCES_REPORT',
 '20000000-0004-0000-0000-00000000000E', '20000000-0004-0000-0000-00000000000A',
 'ONE_TO_ONE',
 'QC test event produces a quality control report.',
 '["report generated", "test report", "produces QC report", "documented in"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Specification compliance (structural relationship)
('30000000-0004-0000-0000-000000000009', 'MEETS_SPEC',
 '20000000-0000-0002-0000-000000000003', '20000000-0004-0000-0000-000000000009',
 'MANY_TO_MANY',
 'Finished product complies with product specification. Structural quality attribute.',
 '["meets spec", "complies with", "per standard", "per specification", "in accordance with"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Storage and inventory (structural relationship)
('30000000-0004-0000-0000-00000000000A', 'STORED_IN',
 '20000000-0004-0000-0000-000000000008', '20000000-0004-0000-0000-000000000006',
 'MANY_TO_ONE',
 'Product batch or material is stored in inventory at location.',
 '["stored in", "stored at", "inventory in", "warehouse at", "location"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Team-based operations (using shared team hierarchy)
('30000000-0004-0000-0000-00000000000B', 'PERFORMED_BY',
 '20000000-0004-0000-0000-00000000000C', '20000000-0000-0004-0000-000000000003',
 'MANY_TO_MANY',
 'Production run is performed by operations team. References shared OperationsTeam.',
 '["performed by", "executed by", "run by", "operated by", "staffed by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-00000000000C', 'EXECUTED_BY',
 '20000000-0004-0000-0000-00000000000E', '20000000-0000-0004-0000-000000000004',
 'MANY_TO_MANY',
 'QC test event is executed by quality team. References shared QualityTeam.',
 '["executed by", "performed by", "tested by", "analyzed by", "inspected by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Shipment (using shared Shipment)
('30000000-0004-0000-0000-00000000000D', 'CONTAINS_GOODS',
 '20000000-0000-0003-0000-000000000001', '20000000-0000-0002-0000-000000000003',
 'MANY_TO_MANY',
 'Shared Shipment contains finished products. References shared Shipment type.',
 '["contains", "includes", "carries", "loaded with", "cargo"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Documentation
('30000000-0004-0000-0000-00000000000E', 'REFERENCES_SPEC',
 '20000000-0004-0000-0000-00000000000A', '20000000-0004-0000-0000-000000000009',
 'MANY_TO_ONE',
 'QC report references product specification being tested.',
 '["per spec", "specification", "testing against", "compliance with"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- End of Manufacturing Domain Template
-- =============================================================================

INSERT INTO ontology.relations (
    id, relation_type, source_type_id, target_type_id, 
    cardinality, semantics, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('30000000-0004-0000-0000-00000000000F', 'CONTAINS_LINE', 
 '20000000-0004-0000-0000-000000000003', '20000000-0004-0000-0000-000000000004',
 'ONE_TO_MANY',
 'Manufacturing plant contains production lines',
 '["contains", "has line", "production line", "line at plant"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000010', 'DOCUMENTS_MATERIAL', 
 '20000000-0004-0000-0000-00000000000B', '20000000-0004-0000-0000-000000000007',
 'MANY_TO_ONE',
 'MSDS documents safety information for raw material',
 '["MSDS for", "safety data sheet", "material safety", "documents material"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Additional Relationships (from QA review)
('30000000-0004-0000-0000-000000000011', 'SUPPLIED_BY', 
 '20000000-0004-0000-0000-000000000007', '20000000-0004-0000-0000-00000000000F',
 'MANY_TO_ONE',
 'Raw material is supplied by a supplier',
 '["supplied by", "from supplier", "vendor", "sourced from"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000012', 'EQUIPMENT_ON_LINE', 
 '20000000-0004-0000-0000-000000000010', '20000000-0004-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Equipment is installed on a production line',
 '["on line", "installed on", "part of line", "equipment at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000013', 'EQUIPMENT_AT_PLANT', 
 '20000000-0004-0000-0000-000000000010', '20000000-0004-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Equipment is located at a manufacturing plant',
 '["at plant", "located at", "installed at", "equipment at facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000014', 'MAINTENANCE_ON_EQUIPMENT', 
 '20000000-0004-0000-0000-000000000011', '20000000-0004-0000-0000-000000000010',
 'MANY_TO_ONE',
 'Equipment maintenance is performed on equipment',
 '["maintenance on", "repair of", "service for", "work order for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000015', 'MAINTENANCE_BY_TEAM', 
 '20000000-0004-0000-0000-000000000011', '20000000-0000-0004-0000-000000000002',
 'MANY_TO_ONE',
 'Equipment maintenance is performed by maintenance team',
 '["performed by", "maintenance team", "technician", "repaired by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000016', 'DEFECT_IN_BATCH', 
 '20000000-0004-0000-0000-000000000012', '20000000-0004-0000-0000-000000000008',
 'MANY_TO_ONE',
 'Defect event is found in a product batch',
 '["defect in", "found in batch", "batch defect", "NCR for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000017', 'DEFECT_ON_LINE', 
 '20000000-0004-0000-0000-000000000012', '20000000-0004-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Defect event occurred on a production line',
 '["on line", "line defect", "production issue on"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0004-0000-0000-000000000018', 'EQUIPMENT_FROM_SUPPLIER', 
 '20000000-0004-0000-0000-000000000010', '20000000-0004-0000-0000-00000000000F',
 'MANY_TO_ONE',
 'Equipment was purchased from a supplier',
 '["from supplier", "manufactured by", "purchased from", "OEM"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- End of Manufacturing Domain Template
-- =============================================================================