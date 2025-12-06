-- =============================================================================
-- Context Foundry: Global Supply Chain & Trading Platform Domain Template
-- =============================================================================
-- Archetype: SUPPLY (ID: 02)
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: Manus AI (Gemini)
-- Date: 2025-12-06
-- RFC Version: 2.0 (Dual-System Architecture)
-- Companies Served: Louis Dreyfus Company (LDC), Al Dahra, Unifrutti, Aramex, Silal
-- =============================================================================

-- =============================================================================
-- SHARED TYPE REFERENCES (from shared_ontology.sql - DO NOT REDEFINE)
-- =============================================================================
-- Facility: 20000000-0000-0001-0000-000000000001
-- ProductionFacility: 20000000-0000-0001-0000-000000000002
-- ProcessingFacility: 20000000-0000-0001-0000-000000000003
-- StorageFacility: 20000000-0000-0001-0000-000000000004
-- TransportFacility: 20000000-0000-0001-0000-000000000005
-- Good: 20000000-0000-0002-0000-000000000001
-- Commodity: 20000000-0000-0002-0000-000000000002
-- FinishedProduct: 20000000-0000-0002-0000-000000000003
-- Shipment: 20000000-0000-0003-0000-000000000001
-- Container: 20000000-0000-0003-0000-000000000002
-- TransportVehicle: 20000000-0000-0003-0000-000000000003
-- OperationalTeam: 20000000-0000-0004-0000-000000000001
-- OperationalDocument: 20000000-0000-0005-0000-000000000001
-- =============================================================================

-- =============================================================================
-- CONCRETE FACILITY TYPES (extend shared hierarchy)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

-- Agricultural Production
('20000000-0002-0000-0000-000000000001', 'Farm', 2, 'Farm',
 'Agricultural production facility for crops or livestock',
 '20000000-0000-0001-0000-000000000002', -- ProductionFacility (shared)
 '{"type": "object", "properties": {"farm_size_hectares": {"type": "number"}, "crops_grown": {"type": "array", "items": {"type": "string"}}, "irrigation_type": {"type": "string"}, "organic_certified": {"type": "boolean"}, "growing_season": {"type": "string"}}}',
 '["farm", "agricultural land", "farmland", "estate", "ranch", "plantation", "orchard", "vineyard"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Storage Facilities
('20000000-0002-0000-0000-000000000002', 'Warehouse', 2, 'Warehouse',
 'General-purpose storage facility for goods and commodities',
 '20000000-0000-0001-0000-000000000004', -- StorageFacility (shared)
 '{"type": "object", "properties": {"storage_type": {"type": "string", "enum": ["ambient", "refrigerated", "frozen", "controlled_atmosphere"]}, "capacity_metric_tons": {"type": "number"}, "racking_system": {"type": "string"}, "wms_enabled": {"type": "boolean"}}}',
 '["warehouse", "distribution center", "DC", "storage facility", "depot"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000003', 'ColdStorage', 2, 'Cold Storage',
 'Temperature-controlled storage facility for perishable goods',
 '20000000-0000-0001-0000-000000000004', -- StorageFacility (shared)
 '{"type": "object", "properties": {"temperature_range_celsius": {"type": "string"}, "capacity_pallets": {"type": "integer"}, "blast_freezing_available": {"type": "boolean"}, "haccp_certified": {"type": "boolean"}}}',
 '["cold storage", "refrigerated warehouse", "freezer", "chiller", "reefer facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000004', 'Silo', 2, 'Silo',
 'Bulk storage facility for grains, seeds, or similar commodities',
 '20000000-0000-0001-0000-000000000004', -- StorageFacility (shared)
 '{"type": "object", "properties": {"capacity_metric_tons": {"type": "number"}, "silo_type": {"type": "string", "enum": ["flat_bottom", "hopper_bottom", "bunker"]}, "aeration_system": {"type": "boolean"}, "fumigation_capability": {"type": "boolean"}}}',
 '["silo", "grain elevator", "bulk storage", "bin", "storage tower"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Processing Facilities
('20000000-0002-0000-0000-000000000005', 'PackingHouse', 2, 'Packing House',
 'Facility for sorting, grading, and packing agricultural products',
 '20000000-0000-0001-0000-000000000003', -- ProcessingFacility (shared)
 '{"type": "object", "properties": {"throughput_tons_per_hour": {"type": "number"}, "grading_lines": {"type": "integer"}, "cold_chain_maintained": {"type": "boolean"}, "certifications": {"type": "array", "items": {"type": "string"}}}}',
 '["packing house", "packhouse", "grading facility", "sorting center", "processing plant"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Transport Facilities
'{"type": "object", "properties": {"port_code": {"type": "string"}, "annual_throughput_teu": {"type": "number"}, "bulk_handling_capacity": {"type": "number"}, "reefer_plugs": {"type": "integer"}, "customs_bonded": {"type": "boolean"}}}',
 '["port", "seaport", "maritime terminal", "harbor", "shipping port", "container port"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- TRANSPORT ASSET TYPES (extend shared TransportVehicle)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

'{"type": "object", "properties": {"vessel_name": {"type": "string"}, "imo_number": {"type": "string"}, "vessel_type": {"type": "string", "enum": ["bulk_carrier", "container_ship", "reefer", "tanker", "general_cargo"]}, "dwt": {"type": "number"}, "teu_capacity": {"type": "integer"}, "flag": {"type": "string"}}}',
 '["vessel", "ship", "cargo ship", "MV", "bulk carrier", "container vessel", "reefer ship"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

'{"type": "object", "properties": {"truck_type": {"type": "string", "enum": ["flatbed", "refrigerated", "dry_van", "tanker"]}, "capacity_tons": {"type": "number"}, "license_plate": {"type": "string"}, "temperature_controlled": {"type": "boolean"}}}',
 '["truck", "lorry", "trailer", "reefer truck", "flatbed", "semi-trailer"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- SUPPLY CHAIN EVENT TYPES (extend Event)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0002-0000-0000-000000000009', 'Harvest', 2, 'Harvest',
 'Event of harvesting crops from a farm or production facility',
 '00000000-0000-0000-0000-000000000002', -- Event (L0)
 '{"type": "object", "properties": {"harvest_date": {"type": "string", "format": "date"}, "quantity_harvested": {"type": "number"}, "unit": {"type": "string"}, "quality_grade": {"type": "string"}, "weather_conditions": {"type": "string"}}}',
 '["harvest", "harvesting", "crop harvest", "picking", "collection", "yield"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-00000000000A', 'CommodityTrade', 2, 'CommodityTrade',
 'Commercial trade transaction for buying or selling commodities or goods',
 '00000000-0000-0000-0000-000000000002', -- Event (L0)
 '{"type": "object", "properties": {"trade_date": {"type": "string", "format": "date"}, "trade_type": {"type": "string", "enum": ["purchase", "sale", "swap"]}, "quantity": {"type": "number"}, "unit": {"type": "string"}, "price_per_unit": {"type": "number"}, "currency": {"type": "string"}, "incoterms": {"type": "string"}}}',
 '["trade", "transaction", "deal", "purchase", "sale", "contract", "agreement"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-00000000000B', 'Inspection', 2, 'Inspection',
 'Quality or compliance inspection event for goods or facilities',
 '00000000-0000-0000-0000-000000000002', -- Event (L0)
 '{"type": "object", "properties": {"inspection_date": {"type": "string", "format": "date-time"}, "inspection_type": {"type": "string", "enum": ["quality", "phytosanitary", "customs", "safety"]}, "inspector": {"type": "string"}, "result": {"type": "string", "enum": ["pass", "fail", "conditional"]}, "findings": {"type": "string"}}}',
 '["inspection", "audit", "check", "examination", "survey", "assessment"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- SUPPLY CHAIN AGENT TYPES (extend OperationalTeam)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0002-0000-0000-00000000000C', 'Producer', 2, 'Producer',
 'Organization or team that produces commodities or goods',
 '20000000-0000-0004-0000-000000000001', -- OperationalTeam (shared)
 '{"type": "object", "properties": {"production_capacity": {"type": "string"}, "certifications": {"type": "array", "items": {"type": "string"}}, "primary_products": {"type": "array", "items": {"type": "string"}}}}',
 '["producer", "grower", "farmer", "manufacturer", "supplier", "vendor"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-00000000000D', 'Carrier', 2, 'Carrier',
 'Organization or team that transports goods',
 '20000000-0000-0004-0000-000000000001', -- OperationalTeam (shared)
 '{"type": "object", "properties": {"carrier_type": {"type": "string", "enum": ["ocean", "air", "road", "rail", "multimodal"]}, "fleet_size": {"type": "integer"}, "service_routes": {"type": "array", "items": {"type": "string"}}}}',
 '["carrier", "shipper", "freight forwarder", "logistics provider", "transporter", "haulier"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-00000000000E', 'Trader', 2, 'Trader',
 'Organization or team that buys and sells commodities or goods',
 '20000000-0000-0004-0000-000000000001', -- OperationalTeam (shared)
 '{"type": "object", "properties": {"trading_desk": {"type": "string"}, "commodities_traded": {"type": "array", "items": {"type": "string"}}, "geographic_markets": {"type": "array", "items": {"type": "string"}}}}',
 '["trader", "trading company", "merchant", "broker", "dealer"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- DOCUMENT TYPES (extend OperationalDocument)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0002-0000-0000-00000000000F', 'BillOfLading', 2, 'Bill of Lading',
 'Shipping document issued by a carrier acknowledging receipt of cargo',
 '20000000-0000-0005-0000-000000000001', -- OperationalDocument (shared)
 '{"type": "object", "properties": {"bl_number": {"type": "string"}, "shipper": {"type": "string"}, "consignee": {"type": "string"}, "vessel_name": {"type": "string"}, "port_of_loading": {"type": "string"}, "port_of_discharge": {"type": "string"}, "cargo_description": {"type": "string"}}}',
 '["bill of lading", "B/L", "BOL", "shipping document", "cargo receipt"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000010', 'QualityCertificate', 2, 'Quality Certificate',
 'Certificate attesting to the quality or grade of a commodity or product',
 '20000000-0000-0005-0000-000000000001', -- OperationalDocument (shared)
 '{"type": "object", "properties": {"certificate_number": {"type": "string"}, "commodity": {"type": "string"}, "quality_grade": {"type": "string"}, "test_results": {"type": "string"}, "issued_by": {"type": "string"}, "issue_date": {"type": "string", "format": "date"}}}',
 '["quality certificate", "certificate of quality", "COQ", "grade certificate", "analysis certificate"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000011', 'InspectionReport', 2, 'Inspection Report',
 'Report documenting the findings of an inspection',
 '20000000-0000-0005-0000-000000000001', -- OperationalDocument (shared)
 '{"type": "object", "properties": {"report_number": {"type": "string"}, "inspection_type": {"type": "string"}, "inspector_name": {"type": "string"}, "inspection_date": {"type": "string", "format": "date"}, "findings": {"type": "string"}, "pass_fail": {"type": "string"}}}',
 '["inspection report", "survey report", "inspection certificate", "findings report"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000012', 'PhytosanitaryCertificate', 2, 'Phytosanitary Certificate',
 'Certificate confirming that plants or plant products meet phytosanitary requirements',
 '20000000-0000-0005-0000-000000000001', -- OperationalDocument (shared)
 '{"type": "object", "properties": {"certificate_number": {"type": "string"}, "exporting_country": {"type": "string"}, "importing_country": {"type": "string"}, "product_description": {"type": "string"}, "treatment_applied": {"type": "string"}, "issue_date": {"type": "string", "format": "date"}}}',
 '["phytosanitary certificate", "plant health certificate", "phyto certificate", "sanitary certificate"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000013', 'CommodityConfirmation', 2, 'Trade Confirmation',
 'Document confirming the terms of a trade transaction',
 '20000000-0000-0005-0000-000000000001', -- OperationalDocument (shared)
 '{"type": "object", "properties": {"confirmation_number": {"type": "string"}, "trade_date": {"type": "string", "format": "date"}, "buyer": {"type": "string"}, "seller": {"type": "string"}, "commodity": {"type": "string"}, "quantity": {"type": "number"}, "price": {"type": "number"}, "delivery_terms": {"type": "string"}}}',
 '["trade confirmation", "contract confirmation", "deal confirmation", "purchase confirmation"]',
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

-- Harvest Relationships
('30000000-0002-0000-0000-000000000001', 'OCCURS_AT',
 '20000000-0002-0000-0000-000000000009', '20000000-0002-0000-0000-000000000001', 'MANY_TO_ONE',
 'Indicates the farm where the harvest event occurred',
 '["harvested at", "from farm", "at location", "occurred at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000002', 'YIELDS',
 '20000000-0002-0000-0000-000000000009', '20000000-0000-0002-0000-000000000002', 'ONE_TO_MANY',
 'Indicates the commodity produced by the harvest',
 '["yielded", "produced", "harvested", "resulted in"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Storage Relationships
('30000000-0002-0000-0000-000000000003', 'STORED_IN',
 '20000000-0000-0002-0000-000000000002', '20000000-0000-0001-0000-000000000004', 'MANY_TO_MANY',
 'Indicates where a commodity is stored',
 '["stored in", "kept at", "warehoused at", "held in"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Shipment Relationships
('30000000-0002-0000-0000-000000000004', 'CONTAINS',
 '20000000-0000-0003-0000-000000000001', '20000000-0000-0002-0000-000000000002', 'ONE_TO_MANY',
 'Indicates the goods contained in a shipment',
 '["contains", "carries", "transports", "includes"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000005', 'TRANSPORTED_BY',
 '20000000-0000-0003-0000-0000-000000000001', '20000000-0000-0003-0000-000000000003', 'MANY_TO_ONE',
 'Indicates the transport vehicle used for a shipment',
 '["transported by", "carried by", "shipped on", "via"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000006', 'ORIGINATES_FROM',
 '20000000-0000-0003-0000-000000000001', '20000000-0000-0001-0000-000000000001', 'MANY_TO_ONE',
 'Indicates the origin facility of a shipment',
 '["from", "originates from", "shipped from", "departure point"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000007', 'DESTINED_FOR',
 '20000000-0000-0003-0000-000000000001', '20000000-0000-0001-0000-000000000001', 'MANY_TO_ONE',
 'Indicates the destination facility of a shipment',
 '["to", "destined for", "shipped to", "destination"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Trade Relationships
('30000000-0002-0000-0000-000000000008', 'IS_SUBJECT_OF',
 '20000000-0000-0002-0000-000000000002', '20000000-0002-0000-0000-00000000000A', 'MANY_TO_MANY',
 'Indicates the commodity that is the subject of a trade',
 '["traded", "subject of trade", "commodity traded", "goods traded"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000009', 'BUYER_IN',
 '20000000-0002-0000-0000-00000000000E', '20000000-0002-0000-0000-00000000000A', 'MANY_TO_MANY',
 'Indicates the trader acting as buyer in a trade',
 '["buyer", "purchased by", "bought by", "purchasing party"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000000A', 'SELLER_IN',
 '20000000-0002-0000-0000-00000000000E', '20000000-0002-0000-0000-00000000000A', 'MANY_TO_MANY',
 'Indicates the trader acting as seller in a trade',
 '["seller", "sold by", "selling party", "vendor"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Inspection Relationships
('30000000-0002-0000-0000-00000000000B', 'INSPECTS',
 '20000000-0002-0000-0000-00000000000B', '20000000-0000-0002-0000-000000000002', 'MANY_TO_MANY',
 'Indicates the commodity inspected during an inspection event',
 '["inspects", "examines", "assesses", "checks"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000000C', 'INSPECTION_AT',
 '20000000-0002-0000-0000-00000000000B', '20000000-0000-0001-0000-000000000001', 'MANY_TO_ONE',
 'Indicates the facility where an inspection occurred',
 '["at", "conducted at", "performed at", "location"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Agent Relationships
('30000000-0002-0000-0000-00000000000D', 'OPERATES',
 '20000000-0002-0000-0000-00000000000C', '20000000-0002-0000-0000-000000000001', 'MANY_TO_MANY',
 'Indicates a producer operates a farm',
 '["operates", "manages", "runs", "owns"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000000E', 'PROVIDES_SERVICE',
 '20000000-0002-0000-0000-00000000000D', '20000000-0000-0003-0000-000000000001', 'MANY_TO_MANY',
 'Indicates a carrier provides transport service for a shipment',
 '["carrier for", "transports", "provides service", "handles shipment"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Document Relationships
('30000000-0002-0000-0000-00000000000F', 'DOCUMENTS',
 '20000000-0002-0000-0000-00000000000F', '20000000-0000-0003-0000-000000000001', 'ONE_TO_ONE',
 'Indicates a bill of lading documents a shipment',
 '["for shipment", "documents", "covers", "relates to"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000010', 'CERTIFIES',
 '20000000-0002-0000-0000-000000000010', '20000000-0000-0002-0000-000000000002', 'ONE_TO_MANY',
 'Indicates a quality certificate certifies a commodity',
 '["certifies", "attests to", "confirms quality of", "for commodity"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000011', 'REPORTS_ON',
 '20000000-0002-0000-0000-000000000011', '20000000-0002-0000-0000-00000000000B', 'ONE_TO_ONE',
 'Indicates an inspection report documents an inspection event',
 '["reports on", "documents", "records", "findings from"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Processing Relationships
('30000000-0002-0000-0000-000000000012', 'PROCESSES',
 '20000000-0002-0000-0000-000000000005', '20000000-0000-0002-0000-000000000002', 'MANY_TO_MANY',
 'Indicates a packing house processes a commodity',
 '["processes", "packs", "grades", "handles"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000013', 'LOADS_AT',
 '20000000-0000-0003-0000-000000000001', '20000000-0000-0003-0000-000000000004', 'MANY_TO_ONE',
 'Indicates a shipment is loaded at a port',
 '["loaded at", "shipped from", "port of loading", "departure port"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000014', 'DISCHARGES_AT',
 '20000000-0000-0003-0000-000000000001', '20000000-0000-0003-0000-000000000004', 'MANY_TO_ONE',
 'Indicates a shipment is discharged at a port',
 '["discharged at", "unloaded at", "port of discharge", "destination port"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),
-- Additional relationships to fix orphans
('30000000-0002-0000-0000-000000000015', 'STORED_IN_WAREHOUSE', 
 '20000000-0000-0002-0000-000000000002', '20000000-0002-0000-0000-000000000002',
 'MANY_TO_MANY',
 'Commodity is stored in a warehouse',
 '["stored in", "warehoused at", "held at", "stock at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000016', 'STORED_IN_COLD', 
 '20000000-0000-0002-0000-000000000002', '20000000-0002-0000-0000-000000000003',
 'MANY_TO_MANY',
 'Commodity is stored in cold storage',
 '["cold storage", "refrigerated", "chilled", "frozen storage"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000017', 'STORED_IN_SILO', 
 '20000000-0000-0002-0000-000000000002', '20000000-0002-0000-0000-000000000004',
 'MANY_TO_MANY',
 'Commodity is stored in a silo',
 '["silo", "grain silo", "bulk storage", "stored in silo"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000018', 'SHIPPED_BY_VESSEL', 
 '20000000-0000-0003-0000-000000000001', '20000000-0000-0003-0000-000000000005',
 'MANY_TO_ONE',
 'Shipment is transported by vessel',
 '["shipped by", "vessel", "by sea", "maritime transport", "on board"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000019', 'SHIPPED_BY_TRUCK', 
 '20000000-0000-0003-0000-000000000001', '20000000-0000-0003-0000-000000000006',
 'MANY_TO_ONE',
 'Shipment is transported by truck',
 '["trucked", "by road", "road transport", "hauled by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000001A', 'CERTIFIES_PHYTO', 
 '20000000-0002-0000-0000-000000000012', '20000000-0000-0002-0000-000000000002',
 'MANY_TO_ONE',
 'Phytosanitary certificate certifies commodity for export',
 '["certifies", "phytosanitary", "plant health", "export certificate"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000001B', 'CONFIRMS_TRADE', 
 '20000000-0002-0000-0000-000000000013', '20000000-0002-0000-0000-00000000000A',
 'MANY_TO_ONE',
 'Trade confirmation confirms a trade transaction',
 '["confirms", "confirmation for", "trade confirmed", "transaction confirmed"]',
 'ACTIVE', 1.0, '1.0.0', NOW());