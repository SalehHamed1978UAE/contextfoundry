-- =============================================================================
-- Context Foundry: Supply Chain Ontology
-- =============================================================================
-- Purpose: Defines types for agricultural supply chain, commodity trading,
--          food security, and logistics operations
-- Domain: SUPPLY (0002)
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: Claude (Reconstructed)
-- Date: 2025-12-06
-- RFC Version: 2.0 (Dual-System Architecture)
-- =============================================================================

-- =============================================================================
-- SUPPLY CHAIN FACILITY TYPES
-- UUID Pattern: 20000000-0002-0000-0000-00000000XXXX
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0002-0000-0000-000000000001', 'Farm', 2, 'Farm',
 'Agricultural land used for growing crops or raising livestock',
 '20000000-0000-0001-0000-000000000002',
 '{"type": "object", "properties": {"farm_name": {"type": "string"}, "farm_type": {"type": "string", "enum": ["crop", "livestock", "mixed", "aquaculture", "orchard", "vineyard"]}, "area_hectares": {"type": "number"}, "main_crops": {"type": "array", "items": {"type": "string"}}, "certification": {"type": "array", "items": {"type": "string"}}, "irrigation_type": {"type": "string"}}}',
 '["farm", "agricultural land", "farmland", "estate", "ranch", "plantation", "orchard", "vineyard"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000002', 'Warehouse', 2, 'Warehouse',
 'Storage facility for goods and materials in the supply chain',
 '20000000-0000-0001-0000-000000000004',
 '{"type": "object", "properties": {"warehouse_code": {"type": "string"}, "storage_capacity_sqm": {"type": "number"}, "pallet_positions": {"type": "integer"}, "warehouse_type": {"type": "string", "enum": ["dry", "bonded", "hazmat", "general"]}, "wms_system": {"type": "string"}}}',
 '["warehouse", "distribution center", "DC", "storage facility", "depot"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000003', 'ColdStorage', 2, 'Cold Storage',
 'Temperature-controlled storage facility for perishable goods',
 '20000000-0000-0001-0000-000000000004',
 '{"type": "object", "properties": {"temperature_range_min": {"type": "number"}, "temperature_range_max": {"type": "number"}, "cold_rooms_count": {"type": "integer"}, "capacity_pallets": {"type": "integer"}, "certifications": {"type": "array", "items": {"type": "string"}}}}',
 '["cold storage", "refrigerated warehouse", "freezer", "chiller", "reefer facility", "cold chain"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000004', 'Silo', 2, 'Silo',
 'Storage structure for bulk materials like grain, cement, or other commodities',
 '20000000-0000-0001-0000-000000000004',
 '{"type": "object", "properties": {"silo_type": {"type": "string", "enum": ["grain", "cement", "feed", "industrial"]}, "capacity_tons": {"type": "number"}, "height_meters": {"type": "number"}, "diameter_meters": {"type": "number"}, "aeration_system": {"type": "boolean"}}}',
 '["silo", "grain elevator", "bulk storage", "bin", "storage tower"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000005', 'PackingHouse', 2, 'Packing House',
 'Facility for sorting, grading, and packing agricultural products',
 '20000000-0000-0001-0000-000000000003',
 '{"type": "object", "properties": {"throughput_tons_per_hour": {"type": "number"}, "grading_lines": {"type": "integer"}, "cold_chain_maintained": {"type": "boolean"}, "certifications": {"type": "array", "items": {"type": "string"}}}}',
 '["packing house", "packhouse", "grading facility", "sorting center", "processing plant"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000006', 'SupplyPort', 2, 'Supply Port',
 'Maritime port facility for supply chain cargo and commodity operations',
 '20000000-0000-0001-0000-000000000005',
 '{"type": "object", "properties": {"port_code": {"type": "string"}, "annual_throughput_teu": {"type": "number"}, "bulk_handling_capacity": {"type": "number"}, "reefer_plugs": {"type": "integer"}, "customs_bonded": {"type": "boolean"}}}',
 '["port", "seaport", "maritime terminal", "harbor", "shipping port", "container port"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- TRANSPORT ASSET TYPES
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0002-0000-0000-000000000007', 'CargoVessel', 2, 'Cargo Vessel',
 'Ship used for transporting cargo in supply chain operations',
 '20000000-0000-0003-0000-000000000005',
 '{"type": "object", "properties": {"vessel_name": {"type": "string"}, "imo_number": {"type": "string"}, "vessel_type": {"type": "string", "enum": ["bulk_carrier", "container_ship", "reefer", "tanker", "general_cargo"]}, "dwt": {"type": "number"}, "teu_capacity": {"type": "integer"}, "flag": {"type": "string"}}}',
 '["vessel", "ship", "cargo ship", "MV", "bulk carrier", "container vessel", "reefer ship"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000008', 'FreightTruck', 2, 'Freight Truck',
 'Truck used for road freight transport in supply chain',
 '20000000-0000-0003-0000-000000000006',
 '{"type": "object", "properties": {"truck_type": {"type": "string", "enum": ["flatbed", "refrigerated", "dry_van", "tanker"]}, "capacity_tons": {"type": "number"}, "license_plate": {"type": "string"}, "temperature_controlled": {"type": "boolean"}}}',
 '["truck", "lorry", "trailer", "reefer truck", "flatbed", "semi-trailer"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- SUPPLY CHAIN EVENT TYPES
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0002-0000-0000-000000000009', 'Harvest', 2, 'Harvest',
 'Event of harvesting crops from a farm or production facility',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"harvest_date": {"type": "string", "format": "date"}, "quantity_harvested": {"type": "number"}, "unit": {"type": "string"}, "quality_grade": {"type": "string"}, "weather_conditions": {"type": "string"}}}',
 '["harvest", "harvesting", "crop harvest", "picking", "collection", "yield"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-00000000000A', 'CommodityTrade', 2, 'Commodity Trade',
 'Commercial trade transaction for buying or selling commodities',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"trade_date": {"type": "string", "format": "date"}, "trade_type": {"type": "string", "enum": ["purchase", "sale", "swap"]}, "quantity": {"type": "number"}, "unit": {"type": "string"}, "price_per_unit": {"type": "number"}, "currency": {"type": "string"}, "incoterms": {"type": "string"}}}',
 '["trade", "transaction", "deal", "purchase", "sale", "contract", "agreement"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-00000000000B', 'QualityInspection', 2, 'Quality Inspection',
 'Inspection event to verify quality standards of commodities or products',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"inspection_date": {"type": "string", "format": "date"}, "inspection_type": {"type": "string"}, "inspector": {"type": "string"}, "pass_fail": {"type": "boolean"}, "findings": {"type": "string"}}}',
 '["inspection", "audit", "check", "examination", "survey", "assessment"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- SUPPLY CHAIN ORGANIZATION TYPES
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0002-0000-0000-00000000000C', 'Producer', 2, 'Producer',
 'Organization that produces agricultural goods or commodities',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"producer_type": {"type": "string", "enum": ["farm", "cooperative", "plantation", "ranch"]}, "main_products": {"type": "array", "items": {"type": "string"}}, "certifications": {"type": "array", "items": {"type": "string"}}, "annual_output": {"type": "number"}}}',
 '["producer", "grower", "farmer", "manufacturer", "supplier", "vendor"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-00000000000D', 'Carrier', 2, 'Carrier',
 'Organization providing transport and logistics services',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"carrier_type": {"type": "string", "enum": ["shipping_line", "trucking", "rail", "air_cargo", "multimodal"]}, "fleet_size": {"type": "integer"}, "service_routes": {"type": "array", "items": {"type": "string"}}, "licenses": {"type": "array", "items": {"type": "string"}}}}',
 '["carrier", "shipper", "freight forwarder", "logistics provider", "transporter", "shipping company"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-00000000000E', 'Trader', 2, 'Trader',
 'Organization engaged in commodity trading and merchandising',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"trading_commodities": {"type": "array", "items": {"type": "string"}}, "trading_regions": {"type": "array", "items": {"type": "string"}}, "annual_volume": {"type": "number"}, "trade_licenses": {"type": "array", "items": {"type": "string"}}}}',
 '["trader", "trading company", "merchant", "broker", "dealer"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- SUPPLY CHAIN DOCUMENT TYPES
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('20000000-0002-0000-0000-00000000000F', 'BillOfLading', 2, 'Bill of Lading',
 'Shipping document serving as receipt and contract of carriage',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"bl_number": {"type": "string"}, "shipper": {"type": "string"}, "consignee": {"type": "string"}, "notify_party": {"type": "string"}, "vessel_name": {"type": "string"}, "port_of_loading": {"type": "string"}, "port_of_discharge": {"type": "string"}, "description_of_goods": {"type": "string"}}}',
 '["bill of lading", "B/L", "BOL", "shipping document", "cargo receipt"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000010', 'QualityCertificate', 2, 'Quality Certificate',
 'Certificate attesting to quality standards of commodities',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"certificate_number": {"type": "string"}, "issuing_body": {"type": "string"}, "issue_date": {"type": "string", "format": "date"}, "expiry_date": {"type": "string", "format": "date"}, "quality_parameters": {"type": "object"}, "grade": {"type": "string"}}}',
 '["quality certificate", "certificate of quality", "COQ", "grade certificate", "analysis certificate"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000011', 'InspectionReport', 2, 'Inspection Report',
 'Report documenting findings from quality or quantity inspections',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"report_number": {"type": "string"}, "inspection_date": {"type": "string", "format": "date"}, "inspector_name": {"type": "string"}, "inspection_company": {"type": "string"}, "findings": {"type": "string"}, "recommendations": {"type": "string"}}}',
 '["inspection report", "survey report", "inspection certificate", "findings report"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000012', 'PhytosanitaryCertificate', 2, 'Phytosanitary Certificate',
 'Plant health certificate required for agricultural exports',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"certificate_number": {"type": "string"}, "exporting_country": {"type": "string"}, "importing_country": {"type": "string"}, "product_description": {"type": "string"}, "treatment_details": {"type": "string"}, "issue_date": {"type": "string", "format": "date"}}}',
 '["phytosanitary certificate", "plant health certificate", "phyto certificate", "SPS certificate"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0002-0000-0000-000000000013', 'TradeConfirmation', 2, 'Trade Confirmation',
 'Document confirming terms of a commodity trade agreement',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"confirmation_number": {"type": "string"}, "trade_date": {"type": "string", "format": "date"}, "buyer": {"type": "string"}, "seller": {"type": "string"}, "commodity": {"type": "string"}, "quantity": {"type": "number"}, "price": {"type": "number"}, "delivery_terms": {"type": "string"}}}',
 '["trade confirmation", "contract confirmation", "deal confirmation", "purchase confirmation"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- SUPPLY CHAIN RELATIONSHIPS
-- =============================================================================

INSERT INTO ontology.relations (
    id, relation_type, source_type_id, target_type_id, 
    cardinality, semantics, extraction_hints,
    status, confidence, version, valid_from
) VALUES

('30000000-0002-0000-0000-000000000001', 'PRODUCES', 
 '20000000-0002-0000-0000-00000000000C', '20000000-0000-0002-0000-000000000002',
 'ONE_TO_MANY',
 'Producer produces commodities',
 '["produces", "grows", "manufactures", "cultivates"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000002', 'HARVESTED_AT', 
 '20000000-0002-0000-0000-000000000009', '20000000-0002-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Harvest event occurred at farm',
 '["harvested at", "from farm", "at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000003', 'STORED_AT', 
 '20000000-0000-0002-0000-000000000002', '20000000-0002-0000-0000-000000000002',
 'MANY_TO_ONE',
 'Commodity stored at warehouse',
 '["stored at", "warehoused at", "kept at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000004', 'COLD_STORED_AT', 
 '20000000-0000-0002-0000-000000000002', '20000000-0002-0000-0000-000000000003',
 'MANY_TO_ONE',
 'Perishable commodity stored at cold storage',
 '["cold stored at", "refrigerated at", "frozen at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000005', 'PACKED_AT', 
 '20000000-0000-0002-0000-000000000002', '20000000-0002-0000-0000-000000000005',
 'MANY_TO_ONE',
 'Product packed at packing house',
 '["packed at", "processed at", "graded at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000006', 'SHIPPED_FROM', 
 '20000000-0000-0003-0000-000000000001', '20000000-0002-0000-0000-000000000006',
 'MANY_TO_ONE',
 'Shipment departed from port',
 '["shipped from", "departed from", "loaded at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000007', 'SHIPPED_TO', 
 '20000000-0000-0003-0000-000000000001', '20000000-0002-0000-0000-000000000006',
 'MANY_TO_ONE',
 'Shipment arrived at port',
 '["shipped to", "arrived at", "discharged at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000008', 'TRANSPORTED_BY', 
 '20000000-0000-0003-0000-000000000001', '20000000-0002-0000-0000-000000000007',
 'MANY_TO_ONE',
 'Shipment transported by vessel',
 '["transported by", "carried by", "shipped on"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000009', 'TRUCKED_BY', 
 '20000000-0000-0003-0000-000000000001', '20000000-0002-0000-0000-000000000008',
 'MANY_TO_ONE',
 'Shipment transported by truck',
 '["trucked by", "delivered by", "hauled by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000000A', 'TRADE_BUYER', 
 '20000000-0002-0000-0000-00000000000A', '20000000-0002-0000-0000-00000000000E',
 'MANY_TO_ONE',
 'Trade has buyer (trader)',
 '["buyer", "purchased by", "bought by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000000B', 'TRADE_SELLER', 
 '20000000-0002-0000-0000-00000000000A', '20000000-0002-0000-0000-00000000000E',
 'MANY_TO_ONE',
 'Trade has seller (trader)',
 '["seller", "sold by", "supplied by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000000C', 'TRADE_COMMODITY', 
 '20000000-0002-0000-0000-00000000000A', '20000000-0000-0002-0000-000000000002',
 'MANY_TO_ONE',
 'Trade involves commodity',
 '["commodity", "product", "goods"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000000D', 'INSPECTION_OF', 
 '20000000-0002-0000-0000-00000000000B', '20000000-0000-0002-0000-000000000002',
 'MANY_TO_ONE',
 'Inspection event for commodity',
 '["inspection of", "inspected", "examined"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000000E', 'CARRIER_FOR', 
 '20000000-0002-0000-0000-00000000000D', '20000000-0000-0003-0000-000000000001',
 'ONE_TO_MANY',
 'Carrier provides transport for shipments',
 '["carrier for", "transports", "ships"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000000F', 'BOL_FOR_SHIPMENT', 
 '20000000-0002-0000-0000-00000000000F', '20000000-0000-0003-0000-000000000001',
 'ONE_TO_ONE',
 'Bill of lading for shipment',
 '["B/L for", "bill of lading for", "covers"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000010', 'CERTIFICATE_FOR', 
 '20000000-0002-0000-0000-000000000010', '20000000-0000-0002-0000-000000000002',
 'MANY_TO_ONE',
 'Quality certificate for commodity',
 '["certificate for", "certifies", "covers"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000011', 'REPORT_FOR_INSPECTION', 
 '20000000-0002-0000-0000-000000000011', '20000000-0002-0000-0000-00000000000B',
 'ONE_TO_ONE',
 'Inspection report documents inspection event',
 '["report for", "documents", "findings from"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000012', 'PHYTO_FOR_SHIPMENT', 
 '20000000-0002-0000-0000-000000000012', '20000000-0000-0003-0000-000000000001',
 'MANY_TO_ONE',
 'Phytosanitary certificate for shipment',
 '["phyto for", "plant health certificate for", "covers"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000013', 'CONFIRMS_TRADE', 
 '20000000-0002-0000-0000-000000000013', '20000000-0002-0000-0000-00000000000A',
 'ONE_TO_ONE',
 'Trade confirmation confirms trade',
 '["confirms", "confirmation of", "documents"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000014', 'FARM_OWNED_BY', 
 '20000000-0002-0000-0000-000000000001', '20000000-0002-0000-0000-00000000000C',
 'MANY_TO_ONE',
 'Farm owned by producer',
 '["owned by", "operated by", "belongs to"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000015', 'VESSEL_OPERATED_BY', 
 '20000000-0002-0000-0000-000000000007', '20000000-0002-0000-0000-00000000000D',
 'MANY_TO_ONE',
 'Cargo vessel operated by carrier',
 '["operated by", "owned by", "chartered by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000016', 'BULK_STORED_IN', 
 '20000000-0000-0002-0000-000000000002', '20000000-0002-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Commodity stored in silo',
 '["stored in", "kept in", "held in"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000017', 'HARVEST_PRODUCES', 
 '20000000-0002-0000-0000-000000000009', '20000000-0000-0002-0000-000000000002',
 'ONE_TO_MANY',
 'Harvest event produces commodities',
 '["yields", "produces", "results in"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000018', 'TRADE_DOCUMENTATION', 
 '20000000-0002-0000-0000-00000000000A', '10000000-0000-0000-0000-000000000006',
 'ONE_TO_MANY',
 'Trade has supporting documents',
 '["documented by", "supported by", "evidenced by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-000000000019', 'INSPECTION_AT_FACILITY', 
 '20000000-0002-0000-0000-00000000000B', '20000000-0000-0001-0000-000000000001',
 'MANY_TO_ONE',
 'Inspection conducted at facility',
 '["inspected at", "conducted at", "performed at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000001A', 'PRODUCER_CERTIFIED_BY', 
 '20000000-0002-0000-0000-00000000000C', '10000000-0000-0000-0000-000000000005',
 'MANY_TO_MANY',
 'Producer certified by certification body',
 '["certified by", "accredited by", "approved by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0002-0000-0000-00000000001B', 'CARRIER_LICENSED_IN', 
 '20000000-0002-0000-0000-00000000000D', '10000000-0000-0000-0000-000000000003',
 'MANY_TO_MANY',
 'Carrier licensed in location/region',
 '["licensed in", "operates in", "registered in"]',
 'ACTIVE', 1.0, '1.0.0', NOW());
