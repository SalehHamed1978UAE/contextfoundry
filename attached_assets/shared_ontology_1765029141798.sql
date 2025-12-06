-- =============================================================================
-- Context Foundry: Shared Ontology (Canonical Types)
-- =============================================================================
-- Purpose: Defines shared types that span multiple domain templates
-- Load Order: MUST be loaded BEFORE any domain ontology
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: Claude
-- Date: 2025-12-06
-- =============================================================================

-- =============================================================================
-- FACILITY HIERARCHY (20000000-0000-0001-xxxx)
-- Base types for all physical operational locations
-- =============================================================================

INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, extraction_hints) VALUES

('20000000-0000-0001-0000-000000000001', 'Facility', 2, 'Facility',
 'Physical location where operations occur. Abstract parent for all facility types.',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"name": {"type": "string"}, "location": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "decommissioned", "maintenance"]}, "coordinates": {"type": "object", "properties": {"lat": {"type": "number"}, "lng": {"type": "number"}}}}}',
 '["facility", "site", "location", "plant", "center", "hub"]'),

('20000000-0000-0001-0000-000000000002', 'ProductionFacility', 2, 'Production Facility',
 'Facility that produces goods, energy, or services. Parent for power plants, factories, farms.',
 '20000000-0000-0001-0000-000000000001',
 '{"type": "object", "properties": {"production_type": {"type": "string"}, "capacity": {"type": "number"}, "capacity_unit": {"type": "string"}, "utilization_pct": {"type": "number"}}}',
 '["production facility", "plant", "factory", "generation", "manufacturing"]'),

('20000000-0000-0001-0000-000000000003', 'ProcessingFacility', 2, 'Processing Facility',
 'Facility that transforms inputs into outputs. Parent for refineries, treatment plants, mills.',
 '20000000-0000-0001-0000-000000000001',
 '{"type": "object", "properties": {"processing_type": {"type": "string"}, "throughput": {"type": "number"}, "throughput_unit": {"type": "string"}}}',
 '["processing facility", "treatment plant", "refinery", "mill", "processing center"]'),

('20000000-0000-0001-0000-000000000004', 'StorageFacility', 2, 'Storage Facility',
 'Facility for storing goods, materials, or equipment. Parent for warehouses, depots, silos.',
 '20000000-0000-0001-0000-000000000001',
 '{"type": "object", "properties": {"storage_type": {"type": "string"}, "capacity": {"type": "number"}, "capacity_unit": {"type": "string"}, "temperature_controlled": {"type": "boolean"}}}',
 '["storage facility", "warehouse", "depot", "silo", "storage", "stockyard", "yard"]'),

('20000000-0000-0001-0000-000000000005', 'TransportFacility', 2, 'Transport Facility',
 'Facility for movement of goods or people. Parent for ports, airports, stations.',
 '20000000-0000-0001-0000-000000000001',
 '{"type": "object", "properties": {"transport_mode": {"type": "string", "enum": ["maritime", "aviation", "rail", "road", "multimodal"]}, "annual_throughput": {"type": "number"}}}',
 '["transport facility", "hub", "terminal", "port", "airport", "station"]');

-- =============================================================================
-- GOOD HIERARCHY (20000000-0000-0002-xxxx)
-- Base types for all tradeable/produceable items
-- =============================================================================

INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, extraction_hints) VALUES

('20000000-0000-0002-0000-000000000001', 'Good', 2, 'Good',
 'Tangible item that can be produced, traded, or consumed. Abstract parent for all product types.',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"name": {"type": "string"}, "sku": {"type": "string"}, "unit_of_measure": {"type": "string"}}}',
 '["good", "product", "item", "material", "commodity"]'),

('20000000-0000-0002-0000-000000000002', 'Commodity', 2, 'Commodity',
 'Raw or semi-processed tradeable material. Parent for agricultural products, minerals, basic materials.',
 '20000000-0000-0002-0000-000000000001',
 '{"type": "object", "properties": {"commodity_type": {"type": "string"}, "grade": {"type": "string"}, "origin_country": {"type": "string"}, "market_price": {"type": "number"}}}',
 '["commodity", "raw material", "feedstock", "agricultural product", "mineral", "ore"]'),

('20000000-0000-0002-0000-000000000003', 'FinishedProduct', 2, 'Finished Product',
 'Manufactured item ready for sale or use. Parent for consumer goods, industrial products.',
 '20000000-0000-0002-0000-000000000001',
 '{"type": "object", "properties": {"product_type": {"type": "string"}, "brand": {"type": "string"}, "model": {"type": "string"}, "serial_number": {"type": "string"}}}',
 '["finished product", "manufactured", "product", "goods", "output"]'),

('20000000-0000-0002-0000-000000000004', 'UtilityProduct', 2, 'Utility Product',
 'Electricity, water, gas, or similar utility output. Parent for power, water, gas products.',
 '20000000-0000-0002-0000-000000000001',
 '{"type": "object", "properties": {"utility_type": {"type": "string", "enum": ["electricity", "water", "gas", "steam", "chilled_water"]}, "unit": {"type": "string"}, "quality_grade": {"type": "string"}}}',
 '["electricity", "power", "water", "gas", "utility", "MW", "MWh", "MIGD", "cubic meters"]');

-- =============================================================================
-- LOGISTICS HIERARCHY (20000000-0000-0003-xxxx)
-- Base types for movement and shipment
-- =============================================================================

INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, extraction_hints) VALUES

('20000000-0000-0003-0000-000000000001', 'Shipment', 2, 'Shipment',
 'Movement of goods from origin to destination. Canonical shipment event used across all domains.',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"shipment_id": {"type": "string"}, "origin": {"type": "string"}, "destination": {"type": "string"}, "departure_time": {"type": "string", "format": "date-time"}, "arrival_time": {"type": "string", "format": "date-time"}, "status": {"type": "string", "enum": ["planned", "in_transit", "delivered", "delayed", "cancelled"]}, "carrier": {"type": "string"}, "tracking_number": {"type": "string"}}}',
 '["shipment", "delivery", "consignment", "cargo", "freight", "transport", "shipping"]'),

('20000000-0000-0003-0000-000000000002', 'Container', 2, 'Container',
 'Shipping container for cargo transport.',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"container_number": {"type": "string"}, "container_type": {"type": "string", "enum": ["20ft", "40ft", "40ft_HC", "reefer", "tank", "open_top"]}, "tare_weight_kg": {"type": "number"}, "max_payload_kg": {"type": "number"}}}',
 '["container", "TEU", "FEU", "shipping container", "reefer", "tank container"]'),

('20000000-0000-0003-0000-000000000003', 'TransportVehicle', 2, 'Transport Vehicle',
 'Vehicle used for transporting goods or people. Abstract parent for vessels, trucks, aircraft.',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"vehicle_id": {"type": "string"}, "vehicle_type": {"type": "string"}, "capacity": {"type": "number"}, "status": {"type": "string", "enum": ["active", "maintenance", "retired"]}}}',
 '["vehicle", "vessel", "ship", "truck", "aircraft", "train", "carrier"]');

-- =============================================================================
-- AGENT HIERARCHY (20000000-0000-0004-xxxx)
-- Base types for operational teams and roles
-- =============================================================================

INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, extraction_hints) VALUES

('20000000-0000-0004-0000-000000000001', 'OperationalTeam', 2, 'Operational Team',
 'Team responsible for operational activities. Abstract parent for specialized teams.',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"team_name": {"type": "string"}, "department": {"type": "string"}, "headcount": {"type": "integer"}, "shift_pattern": {"type": "string"}}}',
 '["team", "crew", "shift", "department", "unit", "group"]'),

('20000000-0000-0004-0000-000000000002', 'MaintenanceTeam', 2, 'Maintenance Team',
 'Team responsible for maintenance activities.',
 '20000000-0000-0004-0000-000000000001',
 '{"type": "object", "properties": {"specialization": {"type": "string"}, "certifications": {"type": "array", "items": {"type": "string"}}}}',
 '["maintenance team", "maintenance crew", "technicians", "engineers", "MRO team"]'),

('20000000-0000-0004-0000-000000000003', 'OperationsTeam', 2, 'Operations Team',
 'Team responsible for day-to-day operations.',
 '20000000-0000-0004-0000-000000000001',
 '{"type": "object", "properties": {"area_of_responsibility": {"type": "string"}, "shift": {"type": "string"}}}',
 '["operations team", "operators", "operations crew", "control room", "dispatch"]'),

('20000000-0000-0004-0000-000000000004', 'QualityTeam', 2, 'Quality Team',
 'Team responsible for quality assurance and control.',
 '20000000-0000-0004-0000-000000000001',
 '{"type": "object", "properties": {"qa_scope": {"type": "string"}, "accreditations": {"type": "array", "items": {"type": "string"}}}}',
 '["quality team", "QA", "QC", "quality control", "inspectors", "auditors"]');

-- =============================================================================
-- DOCUMENT HIERARCHY (20000000-0000-0005-xxxx)
-- Base types for operational documents
-- =============================================================================

INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, extraction_hints) VALUES

('20000000-0000-0005-0000-000000000001', 'OperationalDocument', 2, 'Operational Document',
 'Document related to operations. Abstract parent for procedures, logs, reports.',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"document_number": {"type": "string"}, "title": {"type": "string"}, "version": {"type": "string"}, "effective_date": {"type": "string", "format": "date"}, "status": {"type": "string", "enum": ["draft", "active", "superseded", "archived"]}}}',
 '["document", "procedure", "manual", "report", "log", "record"]'),

('20000000-0000-0005-0000-000000000002', 'Procedure', 2, 'Procedure',
 'Standard operating procedure or work instruction.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"procedure_type": {"type": "string"}, "applies_to": {"type": "string"}, "review_frequency": {"type": "string"}}}',
 '["procedure", "SOP", "work instruction", "protocol", "guidelines"]'),

('20000000-0000-0005-0000-000000000003', 'IncidentReport', 2, 'Incident Report',
 'Report documenting an incident, accident, or near miss.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"incident_type": {"type": "string"}, "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]}, "incident_date": {"type": "string", "format": "date-time"}, "root_cause": {"type": "string"}, "corrective_actions": {"type": "string"}}}',
 '["incident report", "accident report", "near miss", "safety report", "investigation"]'),

('20000000-0000-0005-0000-000000000004', 'MaintenanceLog', 2, 'Maintenance Log',
 'Log of maintenance activities performed.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"work_order_number": {"type": "string"}, "maintenance_type": {"type": "string"}, "performed_by": {"type": "string"}, "completion_date": {"type": "string", "format": "date"}}}',
 '["maintenance log", "work order", "service record", "repair log", "maintenance record"]'),

('20000000-0000-0005-0000-000000000005', 'RegulatoryFiling', 2, 'Regulatory Filing',
 'Document submitted to regulatory authorities.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"filing_type": {"type": "string"}, "regulator": {"type": "string"}, "submission_date": {"type": "string", "format": "date"}, "approval_status": {"type": "string", "enum": ["pending", "approved", "rejected", "conditional"]}}}',
 '["regulatory filing", "submission", "application", "permit application", "license renewal"]');

-- =============================================================================
-- LINEAR ASSET HIERARCHY (20000000-0000-0006-xxxx)
-- Base types for infrastructure that spans distances
-- =============================================================================

INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, extraction_hints) VALUES

('20000000-0000-0006-0000-000000000001', 'LinearAsset', 2, 'Linear Asset',
 'Infrastructure asset that spans a distance. Abstract parent for pipelines, transmission lines, railways.',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"length_km": {"type": "number"}, "start_point": {"type": "string"}, "end_point": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "decommissioned"]}}}',
 '["line", "pipeline", "cable", "track", "route", "corridor"]');

-- =============================================================================
-- SHARED RELATIONSHIPS (30000000-0000-xxxx)
-- Canonical relationships used across domains
-- =============================================================================

INSERT INTO ontology_relations (id, relation_type, source_type_id, target_type_id, cardinality, semantics, extraction_hints) VALUES

('30000000-0000-0001-0000-000000000001', 'LOCATED_AT', 
 '10000000-0000-0000-0000-000000000001', '20000000-0000-0001-0000-000000000001',
 'MANY_TO_ONE',
 'Asset is located at a facility',
 '["located at", "at", "in", "housed at", "based at", "situated at"]'),

('30000000-0000-0001-0000-000000000002', 'PART_OF', 
 '20000000-0000-0001-0000-000000000001', '20000000-0000-0001-0000-000000000001',
 'MANY_TO_ONE',
 'Facility is part of a larger facility or complex',
 '["part of", "within", "belongs to", "section of", "unit of"]'),

('30000000-0000-0001-0000-000000000003', 'OPERATED_BY', 
 '20000000-0000-0001-0000-000000000001', '10000000-0000-0000-0000-000000000005',
 'MANY_TO_ONE',
 'Facility is operated by an organization',
 '["operated by", "managed by", "run by", "owned by"]'),

('30000000-0000-0002-0000-000000000001', 'PRODUCES', 
 '20000000-0000-0001-0000-000000000002', '20000000-0000-0002-0000-000000000001',
 'MANY_TO_MANY',
 'Production facility produces goods',
 '["produces", "manufactures", "generates", "outputs", "makes"]'),

('30000000-0000-0002-0000-000000000002', 'CONSUMES', 
 '20000000-0000-0001-0000-000000000001', '20000000-0000-0002-0000-000000000001',
 'MANY_TO_MANY',
 'Facility consumes goods as inputs',
 '["consumes", "uses", "requires", "inputs", "takes"]'),

('30000000-0000-0003-0000-000000000001', 'ORIGINATES_FROM', 
 '20000000-0000-0003-0000-000000000001', '10000000-0000-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Shipment originates from a location',
 '["from", "originates from", "shipped from", "departed from", "origin"]'),

('30000000-0000-0003-0000-000000000002', 'DESTINED_FOR', 
 '20000000-0000-0003-0000-000000000001', '10000000-0000-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Shipment is destined for a location',
 '["to", "destined for", "shipped to", "arriving at", "destination"]'),

('30000000-0000-0003-0000-000000000003', 'CONTAINS_CARGO', 
 '20000000-0000-0003-0000-000000000001', '20000000-0000-0002-0000-000000000001',
 'MANY_TO_MANY',
 'Shipment contains goods',
 '["contains", "carrying", "loaded with", "cargo", "freight"]'),

('30000000-0000-0003-0000-000000000004', 'TRANSPORTED_BY', 
 '20000000-0000-0003-0000-000000000001', '20000000-0000-0003-0000-000000000003',
 'MANY_TO_ONE',
 'Shipment is transported by a vehicle',
 '["transported by", "carried by", "on board", "via", "by vessel"]'),

('30000000-0000-0004-0000-000000000001', 'PERFORMS', 
 '20000000-0000-0004-0000-000000000001', '00000000-0000-0000-0000-000000000002',
 'MANY_TO_MANY',
 'Team performs an event or activity',
 '["performs", "conducts", "executes", "carries out", "completed by"]'),

('30000000-0000-0004-0000-000000000002', 'RESPONSIBLE_FOR', 
 '20000000-0000-0004-0000-000000000001', '10000000-0000-0000-0000-000000000001',
 'MANY_TO_MANY',
 'Team is responsible for an asset',
 '["responsible for", "manages", "oversees", "maintains", "owns"]'),

('30000000-0000-0004-0000-000000000003', 'MEMBER_OF', 
 '10000000-0000-0000-0000-000000000004', '20000000-0000-0004-0000-000000000001',
 'MANY_TO_MANY',
 'Person is a member of an operational team',
 '["member of", "works on", "assigned to", "part of", "belongs to"]'),

('30000000-0000-0005-0000-000000000001', 'DOCUMENTS', 
 '20000000-0000-0005-0000-000000000001', '00000000-0000-0000-0000-000000000002',
 'MANY_TO_ONE',
 'Document documents an event',
 '["documents", "records", "describes", "reports on", "covers"]'),

('30000000-0000-0005-0000-000000000002', 'APPLIES_TO', 
 '20000000-0000-0005-0000-000000000001', '10000000-0000-0000-0000-000000000001',
 'MANY_TO_MANY',
 'Document applies to an asset',
 '["applies to", "covers", "for", "regarding", "concerning"]'),

('30000000-0000-0006-0000-000000000001', 'CONNECTS', 
 '20000000-0000-0006-0000-000000000001', '20000000-0000-0001-0000-000000000001',
 'MANY_TO_MANY',
 'Linear asset connects facilities',
 '["connects", "links", "joins", "between", "from...to"]');

-- =============================================================================
-- End of Shared Ontology
-- =============================================================================
