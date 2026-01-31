-- =============================================================================
-- Context Foundry: Asset-Intensive Infrastructure Operator Domain Template
-- =============================================================================
-- Archetype: INFRA (ID: 01)
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: Claude
-- Date: 2025-12-06
-- RFC Version: 2.0 (Dual-System Architecture)
-- Companies Served: TAQA, ENEC, EWEC, AD Ports Group, Abu Dhabi Airports, 
--                   Etihad Rail, Tadweer Group
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
-- UtilityProduct: 20000000-0000-0002-0000-000000000004
-- Shipment: 20000000-0000-0003-0000-000000000001
-- TransportVehicle: 20000000-0000-0003-0000-000000000003
-- OperationalTeam: 20000000-0000-0004-0000-000000000001
-- MaintenanceTeam: 20000000-0000-0004-0000-000000000002
-- OperationsTeam: 20000000-0000-0004-0000-000000000003
-- OperationalDocument: 20000000-0000-0005-0000-000000000001
-- IncidentReport: 20000000-0000-0005-0000-000000000003
-- MaintenanceLog: 20000000-0000-0005-0000-000000000004
-- RegulatoryFiling: 20000000-0000-0005-0000-000000000005
-- LinearAsset: 20000000-0000-0006-0000-000000000001

-- =============================================================================
-- ABSTRACT TYPES (intermediate hierarchy for this domain)
-- UUID Pattern: 20000000-0001-0001-0000-00000000000X (abstract)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

-- Energy Production Abstract Types
('20000000-0001-0001-0000-000000000001', 'UtilityPlant', 2, 'Utility Plant',
 'Facility that produces utilities (power, water). Abstract parent for power plants, desalination plants.',
 '20000000-0000-0001-0000-000000000002',
 '{"type": "object", "properties": {"plant_id": {"type": "string"}, "commissioned_date": {"type": "string", "format": "date"}, "operator": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "decommissioned", "maintenance"]}}}',
 '["plant", "utility plant", "generation facility", "production facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Transport Infrastructure Abstract Types
('20000000-0001-0001-0000-000000000002', 'TransportHub', 2, 'Transport Hub',
 'Major transport facility serving as origin/destination for movement. Abstract parent for ports, airports, stations.',
 '20000000-0000-0001-0000-000000000005',
 '{"type": "object", "properties": {"hub_code": {"type": "string"}, "annual_throughput": {"type": "number"}, "throughput_unit": {"type": "string"}}}',
 '["hub", "terminal", "port", "airport", "station", "interchange"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Grid Infrastructure Abstract Types
('20000000-0001-0001-0000-000000000003', 'GridInfrastructure', 2, 'Grid Infrastructure',
 'Infrastructure for transmission and distribution of utilities. Abstract parent for substations, control centers.',
 '20000000-0000-0001-0000-000000000001',
 '{"type": "object", "properties": {"grid_zone": {"type": "string"}, "voltage_level": {"type": "string"}}}',
 '["grid", "network", "transmission", "distribution", "substation"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Mobile Asset Abstract Types
('20000000-0001-0001-0000-000000000004', 'InfrastructureVehicle', 2, 'Infrastructure Vehicle',
 'Vehicle operating within infrastructure networks. Abstract parent for vessels, locomotives, aircraft.',
 '20000000-0000-0003-0000-000000000003',
 '{"type": "object", "properties": {"registration": {"type": "string"}, "operator": {"type": "string"}, "status": {"type": "string", "enum": ["active", "maintenance", "retired"]}}}',
 '["vessel", "ship", "locomotive", "train", "aircraft"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Infrastructure Component Abstract Types
('20000000-0001-0001-0000-000000000005', 'InfrastructureComponent', 2, 'Infrastructure Component',
 'Discrete component within a larger facility. Abstract parent for reactors, berths, runways, cranes.',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"component_id": {"type": "string"}, "parent_facility": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "maintenance", "standby", "decommissioned"]}}}',
 '["unit", "berth", "runway", "crane", "reactor", "bay", "gate"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Waste Management Abstract Types
('20000000-0001-0001-0000-000000000006', 'WasteManagementFacility', 2, 'Waste Management Facility',
 'Facility for waste collection, processing, or disposal. Abstract parent for landfills, MRFs, WtE plants.',
 '20000000-0000-0001-0000-000000000003',
 '{"type": "object", "properties": {"waste_types_accepted": {"type": "array", "items": {"type": "string"}}, "permit_number": {"type": "string"}}}',
 '["waste facility", "landfill", "recycling", "MRF", "waste-to-energy", "transfer station"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- CONCRETE TYPES - Power & Water
-- UUID Pattern: 20000000-0001-0002-0000-00000000000X (power/water)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0001-0002-0000-000000000001', 'PowerPlant', 2, 'Power Plant',
 'Electricity generation facility including gas, solar, nuclear, and combined cycle plants.',
 '20000000-0001-0001-0000-000000000001',
 '{"type": "object", "properties": {"plant_type": {"type": "string", "enum": ["gas", "solar", "nuclear", "wind", "hydro", "waste_to_energy", "combined_cycle"]}, "capacity_mw": {"type": "number"}, "fuel_type": {"type": "string"}}}',
 '["power plant", "power station", "generating station", "MW capacity", "megawatt", "Taweelah", "Shuweihat", "Fujairah F2", "Barakah", "Noor Abu Dhabi"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0002-0000-000000000002', 'DesalinationPlant', 2, 'Desalination Plant',
 'Water desalination facility producing potable water from seawater.',
 '20000000-0001-0001-0000-000000000001',
 '{"type": "object", "properties": {"technology": {"type": "string", "enum": ["reverse_osmosis", "multi_stage_flash", "multi_effect_distillation", "hybrid"]}, "capacity_migd": {"type": "number"}}}',
 '["desalination plant", "desalination facility", "water plant", "RO plant", "reverse osmosis", "MIGD", "million gallons", "Taweelah RO", "GS Inima"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0002-0000-000000000003', 'NuclearReactor', 2, 'Nuclear Reactor',
 'Nuclear reactor unit within a nuclear power plant.',
 '20000000-0001-0001-0000-000000000005',
 '{"type": "object", "properties": {"reactor_type": {"type": "string", "enum": ["APR-1400", "PWR", "BWR", "other"]}, "capacity_mw": {"type": "number"}, "unit_number": {"type": "integer"}, "license_number": {"type": "string"}}}',
 '["reactor", "nuclear unit", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "APR-1400", "Barakah"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0002-0000-000000000004', 'Substation', 2, 'Substation',
 'Electrical substation for voltage transformation and power distribution.',
 '20000000-0001-0001-0000-000000000003',
 '{"type": "object", "properties": {"voltage_kv": {"type": "number"}, "substation_type": {"type": "string", "enum": ["transmission", "distribution", "switching", "converter"]}, "capacity_mva": {"type": "number"}}}',
 '["substation", "electrical substation", "kV", "kilovolt", "transformer station", "switching station"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0002-0000-000000000005', 'ControlCenter', 2, 'Control Center',
 'Operations or network control center for grid management.',
 '20000000-0001-0001-0000-000000000003',
 '{"type": "object", "properties": {"center_type": {"type": "string", "enum": ["grid", "network", "dispatch", "SCADA"]}, "systems_monitored": {"type": "array", "items": {"type": "string"}}}}',
 '["control center", "operations center", "OCC", "network control", "dispatch center", "SCADA", "control room", "load dispatch"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- CONCRETE TYPES - Linear Assets
-- UUID Pattern: 20000000-0001-0003-0000-00000000000X (linear)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0001-0003-0000-000000000001', 'TransmissionLine', 2, 'Transmission Line',
 'High-voltage power transmission infrastructure.',
 '20000000-0000-0006-0000-000000000001',
 '{"type": "object", "properties": {"voltage_kv": {"type": "number"}, "circuit_type": {"type": "string", "enum": ["single", "double", "multi"]}, "conductor_type": {"type": "string"}}}',
 '["transmission line", "power line", "overhead line", "kV line", "circuit", "grid infrastructure", "interconnection"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0003-0000-000000000002', 'Pipeline', 2, 'Pipeline',
 'Water, gas, or waste pipeline infrastructure.',
 '20000000-0000-0006-0000-000000000001',
 '{"type": "object", "properties": {"pipeline_type": {"type": "string", "enum": ["water", "gas", "oil", "sewage", "brine"]}, "diameter_inches": {"type": "number"}, "material": {"type": "string"}}}',
 '["pipeline", "water main", "transmission main", "gas pipeline", "sewage line", "brine outfall", "trunk main"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0003-0000-000000000003', 'RailwayLine', 2, 'Railway Line',
 'Rail track segment or route.',
 '20000000-0000-0006-0000-000000000001',
 '{"type": "object", "properties": {"line_name": {"type": "string"}, "track_type": {"type": "string", "enum": ["single", "double", "multi"]}, "electrification": {"type": "string", "enum": ["none", "overhead", "third_rail"]}, "max_speed_kmh": {"type": "integer"}}}',
 '["railway line", "rail line", "track", "route", "Etihad Rail", "rail network", "corridor", "section"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- CONCRETE TYPES - Maritime
-- UUID Pattern: 20000000-0001-0004-0000-00000000000X (maritime)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

-- Port type moved to shared ontology (00_shared_ontology.sql)

('20000000-0001-0004-0000-000000000002', 'Terminal', 2, 'Terminal',
 'Port terminal for specific cargo or passenger operations.',
 '20000000-0001-0001-0000-000000000005',
 '{"type": "object", "properties": {"terminal_type": {"type": "string", "enum": ["container", "bulk", "passenger", "cargo", "cruise"]}, "capacity": {"type": "number"}, "operator": {"type": "string"}}}',
 '["terminal", "container terminal", "cargo terminal", "passenger terminal", "cruise terminal", "bulk terminal"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0004-0000-000000000003', 'Berth', 2, 'Berth',
 'Ship docking position at a port terminal.',
 '20000000-0001-0001-0000-000000000005',
 '{"type": "object", "properties": {"berth_number": {"type": "string"}, "length_meters": {"type": "number"}, "depth_meters": {"type": "number"}, "max_vessel_size": {"type": "string"}}}',
 '["berth", "quay", "wharf", "berth number", "alongside", "docking position", "mooring"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Vessel type moved to shared ontology (00_shared_ontology.sql)

('20000000-0001-0004-0000-000000000005', 'Crane', 2, 'Crane',
 'Port crane for cargo handling.',
 '20000000-0001-0001-0000-000000000005',
 '{"type": "object", "properties": {"crane_type": {"type": "string", "enum": ["STS", "RTG", "RMG", "mobile", "floating"]}, "capacity_tons": {"type": "number"}, "outreach_meters": {"type": "number"}, "manufacturer": {"type": "string"}}}',
 '["crane", "STS crane", "gantry crane", "RTG", "quay crane", "ship-to-shore", "container crane"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- CONCRETE TYPES - Aviation
-- UUID Pattern: 20000000-0001-0005-0000-00000000000X (aviation)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0001-0005-0000-000000000001', 'Airport', 2, 'Airport',
 'Aviation facility with runways and terminals.',
 '20000000-0001-0001-0000-000000000002',
 '{"type": "object", "properties": {"icao_code": {"type": "string"}, "iata_code": {"type": "string"}, "airport_type": {"type": "string", "enum": ["international", "domestic", "executive", "military"]}, "annual_capacity_pax": {"type": "number"}}}',
 '["airport", "Zayed International Airport", "Al Ain Airport", "Al Bateen", "AUH", "aviation facility", "airfield"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0005-0000-000000000002', 'Runway', 2, 'Runway',
 'Airport runway for aircraft operations.',
 '20000000-0001-0001-0000-000000000005',
 '{"type": "object", "properties": {"runway_designation": {"type": "string"}, "length_meters": {"type": "number"}, "width_meters": {"type": "number"}, "surface_type": {"type": "string"}, "ils_category": {"type": "string"}}}',
 '["runway", "RWY", "runway designation", "threshold", "ILS", "approach", "takeoff", "landing"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- CONCRETE TYPES - Rail
-- UUID Pattern: 20000000-0001-0006-0000-00000000000X (rail)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0001-0006-0000-000000000001', 'RailStation', 2, 'Rail Station',
 'Rail or transit station.',
 '20000000-0001-0001-0000-000000000002',
 '{"type": "object", "properties": {"station_type": {"type": "string", "enum": ["passenger", "freight", "intermodal", "depot"]}, "platforms_count": {"type": "integer"}, "annual_capacity": {"type": "number"}}}',
 '["station", "railway station", "terminal station", "freight terminal", "intermodal", "depot", "rail yard"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0006-0000-000000000002', 'Locomotive', 2, 'Locomotive',
 'Rail engine for freight or passenger service.',
 '20000000-0001-0001-0000-000000000004',
 '{"type": "object", "properties": {"loco_type": {"type": "string", "enum": ["diesel", "electric", "hybrid"]}, "model": {"type": "string"}, "power_kw": {"type": "number"}, "manufacturer": {"type": "string"}}}',
 '["locomotive", "engine", "loco", "diesel locomotive", "train engine", "traction"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0006-0000-000000000003', 'Wagon', 2, 'Wagon',
 'Rail freight car.',
 '20000000-0001-0001-0000-000000000005',
 '{"type": "object", "properties": {"wagon_type": {"type": "string", "enum": ["hopper", "tank", "flatbed", "container", "boxcar"]}, "capacity_tons": {"type": "number"}, "wagon_number": {"type": "string"}}}',
 '["wagon", "freight car", "railcar", "hopper", "tank car", "rolling stock"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0006-0000-000000000004', 'MaintenanceDepot', 2, 'Maintenance Depot',
 'Facility for rail or infrastructure equipment maintenance.',
 '20000000-0000-0001-0000-000000000004',
 '{"type": "object", "properties": {"depot_type": {"type": "string", "enum": ["rail", "aviation", "marine", "vehicle", "equipment"]}, "capacity_units": {"type": "integer"}, "services_offered": {"type": "array", "items": {"type": "string"}}}}',
 '["depot", "maintenance depot", "workshop", "maintenance facility", "repair facility", "service center", "MRO facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- CONCRETE TYPES - Waste Management
-- UUID Pattern: 20000000-0001-0007-0000-00000000000X (waste)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0001-0007-0000-000000000001', 'WasteProcessingPlant', 2, 'Waste Processing Plant',
 'Facility for waste treatment, recycling, or energy recovery.',
 '20000000-0001-0001-0000-000000000006',
 '{"type": "object", "properties": {"facility_type": {"type": "string", "enum": ["landfill", "incinerator", "MRF", "composting", "WtE", "transfer_station"]}, "capacity_tons_year": {"type": "number"}}}',
 '["waste facility", "landfill", "incinerator", "MRF", "material recovery", "waste-to-energy", "recycling facility", "Tadweer", "transfer station"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0007-0000-000000000002', 'WasteStream', 2, 'Waste Stream',
 'Category of waste material processed by facilities.',
 '20000000-0000-0002-0000-000000000001',
 '{"type": "object", "properties": {"waste_type": {"type": "string", "enum": ["municipal_solid", "industrial", "hazardous", "construction_demolition", "green", "medical", "electronic"]}, "source_sector": {"type": "string"}, "volume_tons": {"type": "number"}}}',
 '["waste stream", "waste type", "municipal solid waste", "MSW", "industrial waste", "hazardous waste", "construction waste", "C&D waste", "green waste"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- EVENT TYPES
-- UUID Pattern: 20000000-0001-0008-0000-00000000000X (events)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0001-0008-0000-000000000001', 'OutageEvent', 2, 'Outage Event',
 'Unplanned or planned service interruption affecting infrastructure.',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"outage_type": {"type": "string", "enum": ["planned", "unplanned", "emergency", "forced"]}, "cause": {"type": "string"}, "start_time": {"type": "string", "format": "date-time"}, "end_time": {"type": "string", "format": "date-time"}, "affected_capacity_mw": {"type": "number"}, "customers_affected": {"type": "integer"}}}',
 '["outage", "interruption", "trip", "shutdown", "forced outage", "unplanned outage", "service disruption", "blackout", "load shedding"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0008-0000-000000000002', 'MaintenanceEvent', 2, 'Maintenance Event',
 'Scheduled or unscheduled maintenance activity on an asset.',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"maintenance_type": {"type": "string", "enum": ["preventive", "corrective", "predictive", "overhaul", "inspection"]}, "scheduled_start": {"type": "string", "format": "date-time"}, "scheduled_end": {"type": "string", "format": "date-time"}, "actual_start": {"type": "string", "format": "date-time"}, "actual_end": {"type": "string", "format": "date-time"}, "work_order_number": {"type": "string"}}}',
 '["maintenance", "overhaul", "inspection", "preventive maintenance", "corrective maintenance", "work order", "scheduled maintenance", "turnaround"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0008-0000-000000000003', 'InspectionEvent', 2, 'Inspection Event',
 'Regulatory or safety inspection of an asset or facility.',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"inspection_type": {"type": "string", "enum": ["regulatory", "safety", "environmental", "quality", "third_party"]}, "inspector": {"type": "string"}, "inspection_date": {"type": "string", "format": "date"}, "result": {"type": "string", "enum": ["pass", "fail", "conditional", "pending"]}, "findings_count": {"type": "integer"}}}',
 '["inspection", "audit", "survey", "regulatory inspection", "safety inspection", "FANR inspection", "compliance audit", "third-party inspection"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0008-0000-000000000004', 'VesselCallEvent', 2, 'Vessel Call Event',
 'Ship arrival and departure at a port berth.',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"eta": {"type": "string", "format": "date-time"}, "ata": {"type": "string", "format": "date-time"}, "etd": {"type": "string", "format": "date-time"}, "atd": {"type": "string", "format": "date-time"}, "cargo_type": {"type": "string"}, "cargo_volume_tons": {"type": "number"}, "containers_loaded": {"type": "integer"}, "containers_discharged": {"type": "integer"}}}',
 '["vessel call", "port call", "arrival", "departure", "ETA", "ETD", "berthing", "sailing", "ship arrival"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0008-0000-000000000005', 'GenerationEvent', 2, 'Generation Event',
 'Power or water generation/production period.',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"period_start": {"type": "string", "format": "date-time"}, "period_end": {"type": "string", "format": "date-time"}, "output_mwh": {"type": "number"}, "output_migd": {"type": "number"}, "availability_pct": {"type": "number"}, "capacity_factor_pct": {"type": "number"}}}',
 '["generation", "production", "output", "MWh", "generation period", "daily generation", "monthly output"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- RECORD TYPES
-- UUID Pattern: 20000000-0001-0009-0000-00000000000X (records)
-- =============================================================================

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, 
    parent_type_id, properties_schema, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

('20000000-0001-0009-0000-000000000001', 'OperatingPermit', 2, 'Operating Permit',
 'Regulatory permit or license for facility operations.',
 '20000000-0000-0005-0000-000000000005',
 '{"type": "object", "properties": {"permit_type": {"type": "string", "enum": ["operating", "construction", "environmental", "safety", "nuclear"]}, "permit_number": {"type": "string"}, "issuing_authority": {"type": "string"}, "issue_date": {"type": "string", "format": "date"}, "expiry_date": {"type": "string", "format": "date"}}}',
 '["permit", "license", "authorization", "NOC", "no objection certificate", "operating license", "FANR license", "environmental permit"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0009-0000-000000000002', 'SafetyAnalysisReport', 2, 'Safety Analysis Report',
 'Safety analysis, risk assessment, or incident investigation report.',
 '20000000-0000-0005-0000-000000000003',
 '{"type": "object", "properties": {"report_type": {"type": "string", "enum": ["SAR", "PSA", "HAZOP", "risk_assessment", "investigation"]}, "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]}, "report_date": {"type": "string", "format": "date"}}}',
 '["safety report", "SAR", "safety analysis", "risk assessment", "HAZOP", "investigation report", "HSE report"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0009-0000-000000000003', 'PurchaseAgreement', 2, 'Purchase Agreement',
 'Power or water purchase agreement contract.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"agreement_type": {"type": "string", "enum": ["PPA", "PWPA", "WPA", "tolling"]}, "counterparty": {"type": "string"}, "capacity_contracted": {"type": "number"}, "term_years": {"type": "integer"}, "start_date": {"type": "string", "format": "date"}, "end_date": {"type": "string", "format": "date"}}}',
 '["PPA", "power purchase agreement", "PWPA", "water purchase agreement", "offtake agreement", "tolling agreement", "capacity contract"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0001-0009-0000-000000000004', 'EnvironmentalAssessment', 2, 'Environmental Assessment',
 'Environmental impact assessment or environmental monitoring report.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"assessment_type": {"type": "string", "enum": ["EIA", "EIS", "SEA", "monitoring"]}, "project_name": {"type": "string"}, "submission_date": {"type": "string", "format": "date"}, "approval_status": {"type": "string", "enum": ["approved", "pending", "rejected", "conditional"]}}}',
 '["EIA", "environmental impact assessment", "environmental study", "EIS", "environmental report", "environmental clearance"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- RELATIONSHIP TYPES
-- UUID Pattern: 30000000-0001-0000-0000-00000000000X
-- =============================================================================

INSERT INTO ontology.relations (
    id, relation_type, source_type_id, target_type_id, 
    cardinality, semantics, extraction_hints,
    -- RFC v2 columns
    status, confidence, version, valid_from
) VALUES

-- Facility Composition
('30000000-0001-0000-0000-000000000001', 'CONTAINS_UNIT', 
 '20000000-0001-0002-0000-000000000001', '20000000-0001-0002-0000-000000000003',
 'ONE_TO_MANY',
 'Power plant contains reactor units',
 '["contains", "houses", "includes", "Unit 1", "Unit 2", "reactor unit"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000002', 'HAS_TERMINAL', 
 '20000000-0000-0003-0000-000000000004', '20000000-0001-0004-0000-000000000002',
 'ONE_TO_MANY',
 'Port has terminals',
 '["has", "includes", "operates", "terminal"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000003', 'HAS_BERTH', 
 '20000000-0001-0004-0000-000000000002', '20000000-0001-0004-0000-000000000003',
 'ONE_TO_MANY',
 'Terminal has berths',
 '["berth", "quay", "has berth", "berths at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000004', 'HAS_RUNWAY', 
 '20000000-0001-0005-0000-000000000001', '20000000-0001-0005-0000-000000000002',
 'ONE_TO_MANY',
 'Airport has runways',
 '["runway", "RWY", "has runway", "operates runway"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000005', 'OPERATES_CRANE', 
 '20000000-0001-0004-0000-000000000002', '20000000-0001-0004-0000-000000000005',
 'ONE_TO_MANY',
 'Terminal operates cranes',
 '["operates", "crane", "STS", "gantry", "quay crane"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Grid Connectivity
('30000000-0001-0000-0000-000000000006', 'CONNECTS_SUBSTATIONS', 
 '20000000-0001-0003-0000-000000000001', '20000000-0001-0002-0000-000000000004',
 'MANY_TO_MANY',
 'Transmission line connects substations',
 '["connects", "links", "between", "from substation", "to substation"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000007', 'FEEDS_PIPELINE', 
 '20000000-0001-0002-0000-000000000002', '20000000-0001-0003-0000-000000000002',
 'ONE_TO_MANY',
 'Desalination plant feeds water into pipeline',
 '["feeds", "supplies to", "connects to", "pipeline", "transmission main"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000008', 'MONITORED_BY', 
 '20000000-0001-0001-0000-000000000003', '20000000-0001-0002-0000-000000000005',
 'MANY_TO_ONE',
 'Grid infrastructure is monitored by control center',
 '["monitored by", "controlled by", "managed by", "dispatched from", "SCADA"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Rail Operations
('30000000-0001-0000-0000-000000000009', 'TRAVERSES_LINE', 
 '20000000-0001-0006-0000-000000000002', '20000000-0001-0003-0000-000000000003',
 'MANY_TO_MANY',
 'Locomotive traverses railway line',
 '["traverses", "runs on", "operates on", "route", "section"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-00000000000A', 'PULLS_WAGON', 
 '20000000-0001-0006-0000-000000000002', '20000000-0001-0006-0000-000000000003',
 'ONE_TO_MANY',
 'Locomotive pulls wagons in train consist',
 '["pulls", "hauls", "tows", "wagon", "consist", "train formation"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-00000000000B', 'SERVES_STATION', 
 '20000000-0001-0003-0000-000000000003', '20000000-0001-0006-0000-000000000001',
 'MANY_TO_MANY',
 'Railway line serves stations',
 '["serves", "stops at", "connects", "station"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-00000000000C', 'SERVICED_AT', 
 '20000000-0001-0001-0000-000000000004', '20000000-0001-0006-0000-000000000004',
 'MANY_TO_MANY',
 'Infrastructure vehicle is serviced at maintenance depot',
 '["serviced at", "maintained at", "repaired at", "overhauled at", "depot"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Waste Management
('30000000-0001-0000-0000-00000000000D', 'PROCESSES_WASTE', 
 '20000000-0001-0007-0000-000000000001', '20000000-0001-0007-0000-000000000002',
 'MANY_TO_MANY',
 'Waste processing plant processes waste streams',
 '["processes", "treats", "handles", "receives", "disposes of", "recycles"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Event Relationships
('30000000-0001-0000-0000-00000000000E', 'OUTAGE_AFFECTS', 
 '20000000-0001-0008-0000-000000000001', '20000000-0001-0001-0000-000000000001',
 'MANY_TO_MANY',
 'Outage event affects utility plant',
 '["affects", "impacts", "disrupts", "outage at", "resulted in loss"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-00000000000F', 'MAINTENANCE_ON', 
 '20000000-0001-0008-0000-000000000002', '10000000-0000-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Maintenance event is performed on an asset',
 '["maintenance on", "work order for", "overhaul of", "repair of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000010', 'PERFORMED_BY', 
 '20000000-0001-0008-0000-000000000002', '20000000-0000-0004-0000-000000000002',
 'MANY_TO_ONE',
 'Maintenance event is performed by maintenance team',
 '["performed by", "completed by", "executed by", "carried out by"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000011', 'INSPECTION_OF', 
 '20000000-0001-0008-0000-000000000003', '10000000-0000-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Inspection event inspects an asset',
 '["inspection of", "audits", "surveys", "examines", "assesses"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000012', 'VESSEL_CALL_FOR', 
 '20000000-0001-0008-0000-000000000004', '20000000-0000-0003-0000-000000000005',
 'MANY_TO_ONE',
 'Vessel call event is for a specific vessel',
 '["for vessel", "vessel", "ship", "MV", "arrival of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000013', 'VESSEL_CALL_AT', 
 '20000000-0001-0008-0000-000000000004', '20000000-0001-0004-0000-000000000003',
 'MANY_TO_ONE',
 'Vessel call event occurs at a berth',
 '["at berth", "alongside", "docked at", "berthed at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000014', 'GENERATION_AT', 
 '20000000-0001-0008-0000-000000000005', '20000000-0001-0001-0000-000000000001',
 'MANY_TO_ONE',
 'Generation event occurs at a utility plant',
 '["at", "from", "generated by", "produced by", "output from"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000015', 'PRODUCES_UTILITY', 
 '20000000-0001-0008-0000-000000000005', '20000000-0000-0002-0000-000000000004',
 'MANY_TO_MANY',
 'Generation event produces utility product (power/water)',
 '["produces", "generates", "outputs", "MW", "MIGD"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Record Relationships
('30000000-0001-0000-0000-000000000016', 'PERMIT_FOR', 
 '20000000-0001-0009-0000-000000000001', '20000000-0001-0001-0000-000000000001',
 'MANY_TO_ONE',
 'Permit authorizes operation of a utility plant',
 '["permit for", "licenses", "authorizes", "allows operation of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000017', 'AGREEMENT_COVERS', 
 '20000000-0001-0009-0000-000000000003', '20000000-0001-0002-0000-000000000001',
 'ONE_TO_MANY',
 'Purchase agreement covers power plant output',
 '["covers", "applies to", "contracted capacity from", "offtake from"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000018', 'REPORT_DOCUMENTS', 
 '20000000-0001-0009-0000-000000000002', '20000000-0001-0008-0000-000000000001',
 'MANY_TO_ONE',
 'Safety report documents an outage or incident',
 '["documents", "reports", "describes", "investigation of"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0001-0000-0000-000000000019', 'ASSESSMENT_FOR', 
 '20000000-0001-0009-0000-000000000004', '20000000-0001-0002-0000-000000000001',
 'MANY_TO_ONE',
 'Environmental assessment is for a power plant',
 '["assessment for", "EIA for", "environmental review of"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- End of Infrastructure Domain Template
-- =============================================================================
