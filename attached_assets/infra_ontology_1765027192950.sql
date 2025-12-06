-- =============================================================================
-- Context Foundry: Asset-Intensive Infrastructure Operator Domain Template
-- =============================================================================
-- Archetype: INFRA (ID: 01)
-- Author: Claude
-- Date: 2025-12-06
-- Companies Served: TAQA, ENEC, EWEC, AD Ports Group, Abu Dhabi Airports, 
--                   Etihad Rail, Tadweer Group
-- =============================================================================

-- =============================================================================
-- ENTITY TYPES (Layer 2)
-- UUID Pattern: 20000000-0001-0000-0000-00000000000X
-- =============================================================================

INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, extraction_hints) VALUES

-- -----------------------------------------------------------------------------
-- Power & Energy Assets
-- -----------------------------------------------------------------------------
('20000000-0001-0000-0000-000000000001', 'PowerPlant', 2, 'Power Plant', 
 'Electricity generation facility including gas, solar, nuclear, and waste-to-energy plants',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"plant_type": {"type": "string", "enum": ["gas", "solar", "nuclear", "wind", "hydro", "waste_to_energy", "combined_cycle"]}, "capacity_mw": {"type": "number"}, "commissioning_date": {"type": "string", "format": "date"}, "operator": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "decommissioned", "maintenance"]}}}',
 '["power plant", "power station", "generating station", "generation facility", "MW capacity", "megawatt", "electricity generation", "Taweelah", "Shuweihat", "Fujairah F2", "Barakah", "Noor Abu Dhabi"]'),

('20000000-0001-0000-0000-000000000002', 'DesalinationPlant', 2, 'Desalination Plant',
 'Water desalination facility producing potable water from seawater',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"technology": {"type": "string", "enum": ["reverse_osmosis", "multi_stage_flash", "multi_effect_distillation", "hybrid"]}, "capacity_migd": {"type": "number"}, "commissioning_date": {"type": "string", "format": "date"}, "operator": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "decommissioned", "maintenance"]}}}',
 '["desalination plant", "desalination facility", "water plant", "RO plant", "reverse osmosis", "MIGD", "million gallons", "potable water", "seawater treatment", "Taweelah RO", "GS Inima"]'),

('20000000-0001-0000-0000-000000000003', 'NuclearReactor', 2, 'Nuclear Reactor',
 'Nuclear reactor unit within a nuclear power plant',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"reactor_type": {"type": "string", "enum": ["APR-1400", "PWR", "BWR", "other"]}, "capacity_mw": {"type": "number"}, "unit_number": {"type": "integer"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "refueling", "maintenance", "decommissioned"]}, "license_number": {"type": "string"}}}',
 '["reactor", "nuclear unit", "Unit 1", "Unit 2", "Unit 3", "Unit 4", "APR-1400", "Barakah", "nuclear reactor", "reactor unit"]'),

('20000000-0001-0000-0000-000000000004', 'Substation', 2, 'Substation',
 'Electrical substation for voltage transformation and power distribution',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"voltage_kv": {"type": "number"}, "substation_type": {"type": "string", "enum": ["transmission", "distribution", "switching", "converter"]}, "capacity_mva": {"type": "number"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "maintenance"]}}}',
 '["substation", "electrical substation", "kV", "kilovolt", "transformer station", "switching station", "grid connection", "transmission substation"]'),

('20000000-0001-0000-0000-000000000005', 'TransmissionLine', 2, 'Transmission Line',
 'High-voltage power transmission infrastructure',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"voltage_kv": {"type": "number"}, "length_km": {"type": "number"}, "circuit_type": {"type": "string", "enum": ["single", "double", "multi"]}, "conductor_type": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "maintenance"]}}}',
 '["transmission line", "power line", "overhead line", "cable", "kV line", "circuit", "grid infrastructure", "interconnection"]'),

('20000000-0001-0000-0000-000000000006', 'Pipeline', 2, 'Pipeline',
 'Water, gas, or waste pipeline infrastructure',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"pipeline_type": {"type": "string", "enum": ["water", "gas", "oil", "sewage", "brine"]}, "diameter_inches": {"type": "number"}, "length_km": {"type": "number"}, "material": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "maintenance"]}}}',
 '["pipeline", "water main", "transmission main", "gas pipeline", "sewage line", "brine outfall", "trunk main"]'),

-- -----------------------------------------------------------------------------
-- Maritime & Port Assets
-- -----------------------------------------------------------------------------
('20000000-0001-0000-0000-000000000007', 'Port', 2, 'Port',
 'Maritime port facility for cargo and vessel operations',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"port_type": {"type": "string", "enum": ["container", "bulk", "general_cargo", "cruise", "mixed"]}, "annual_capacity_teu": {"type": "number"}, "berths_count": {"type": "integer"}, "status": {"type": "string", "enum": ["operational", "under_expansion", "planned"]}}}',
 '["port", "seaport", "maritime port", "Khalifa Port", "Zayed Port", "Fujairah Port", "port facility", "port operations"]'),

('20000000-0001-0000-0000-000000000008', 'Terminal', 2, 'Terminal',
 'Port terminal or airport terminal facility',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"terminal_type": {"type": "string", "enum": ["container", "bulk", "passenger", "cargo", "cruise", "airport"]}, "capacity": {"type": "number"}, "operator": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "maintenance"]}}}',
 '["terminal", "container terminal", "cargo terminal", "passenger terminal", "Terminal A", "cruise terminal", "bulk terminal"]'),

('20000000-0001-0000-0000-000000000009', 'Berth', 2, 'Berth',
 'Ship docking position at a port',
 '10000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"berth_number": {"type": "string"}, "length_meters": {"type": "number"}, "depth_meters": {"type": "number"}, "max_vessel_size": {"type": "string"}, "status": {"type": "string", "enum": ["available", "occupied", "reserved", "maintenance"]}}}',
 '["berth", "quay", "wharf", "berth number", "alongside", "docking position", "mooring"]'),

('20000000-0001-0000-0000-00000000000A', 'Vessel', 2, 'Vessel',
 'Ship or maritime vessel',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"vessel_type": {"type": "string", "enum": ["container", "bulk_carrier", "tanker", "cruise", "roro", "general_cargo", "tug", "offshore"]}, "imo_number": {"type": "string"}, "mmsi": {"type": "string"}, "flag": {"type": "string"}, "dwt": {"type": "number"}, "teu_capacity": {"type": "integer"}}}',
 '["vessel", "ship", "MV", "MT", "container ship", "bulk carrier", "tanker", "IMO", "MMSI", "flag state", "shipping line"]'),

('20000000-0001-0000-0000-00000000000B', 'Crane', 2, 'Crane',
 'Port crane or heavy lifting equipment',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"crane_type": {"type": "string", "enum": ["STS", "RTG", "RMG", "mobile", "floating"]}, "capacity_tons": {"type": "number"}, "outreach_meters": {"type": "number"}, "manufacturer": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "maintenance", "standby"]}}}',
 '["crane", "STS crane", "gantry crane", "RTG", "quay crane", "ship-to-shore", "container crane", "lifting equipment"]'),

-- -----------------------------------------------------------------------------
-- Aviation Assets
-- -----------------------------------------------------------------------------
('20000000-0001-0000-0000-00000000000C', 'Airport', 2, 'Airport',
 'Aviation facility with runways and terminals',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"icao_code": {"type": "string"}, "iata_code": {"type": "string"}, "airport_type": {"type": "string", "enum": ["international", "domestic", "executive", "military"]}, "annual_capacity_pax": {"type": "number"}, "runways_count": {"type": "integer"}}}',
 '["airport", "Zayed International Airport", "Al Ain Airport", "Al Bateen", "AUH", "aviation facility", "airfield"]'),

('20000000-0001-0000-0000-00000000000D', 'Runway', 2, 'Runway',
 'Airport runway for aircraft operations',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"runway_designation": {"type": "string"}, "length_meters": {"type": "number"}, "width_meters": {"type": "number"}, "surface_type": {"type": "string"}, "ils_category": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "maintenance", "closed"]}}}',
 '["runway", "RWY", "runway designation", "threshold", "ILS", "approach", "takeoff", "landing"]'),

-- -----------------------------------------------------------------------------
-- Rail Assets
-- -----------------------------------------------------------------------------
('20000000-0001-0000-0000-00000000000E', 'RailwayLine', 2, 'Railway Line',
 'Rail track segment or route',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"line_name": {"type": "string"}, "length_km": {"type": "number"}, "track_type": {"type": "string", "enum": ["single", "double", "multi"]}, "electrification": {"type": "string", "enum": ["none", "overhead", "third_rail"]}, "max_speed_kmh": {"type": "integer"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned"]}}}',
 '["railway line", "rail line", "track", "route", "Etihad Rail", "rail network", "corridor", "section"]'),

('20000000-0001-0000-0000-00000000000F', 'Station', 2, 'Station',
 'Rail or transit station',
 '10000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"station_type": {"type": "string", "enum": ["passenger", "freight", "intermodal", "depot"]}, "platforms_count": {"type": "integer"}, "annual_capacity": {"type": "number"}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned"]}}}',
 '["station", "railway station", "terminal station", "freight terminal", "intermodal", "depot", "rail yard"]'),

('20000000-0001-0000-0000-000000000010', 'Locomotive', 2, 'Locomotive',
 'Rail engine for freight or passenger service',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"loco_type": {"type": "string", "enum": ["diesel", "electric", "hybrid"]}, "model": {"type": "string"}, "power_kw": {"type": "number"}, "manufacturer": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "maintenance", "standby", "retired"]}}}',
 '["locomotive", "engine", "loco", "diesel locomotive", "train engine", "traction"]'),

('20000000-0001-0000-0000-000000000011', 'Wagon', 2, 'Wagon',
 'Rail freight car or passenger coach',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"wagon_type": {"type": "string", "enum": ["hopper", "tank", "flatbed", "container", "boxcar", "coach"]}, "capacity_tons": {"type": "number"}, "manufacturer": {"type": "string"}, "status": {"type": "string", "enum": ["operational", "maintenance", "standby", "retired"]}}}',
 '["wagon", "freight car", "railcar", "hopper", "tank car", "coach", "rolling stock"]'),

-- -----------------------------------------------------------------------------
-- Waste Management Assets
-- -----------------------------------------------------------------------------
('20000000-0001-0000-0000-000000000012', 'WasteProcessingFacility', 2, 'Waste Processing Facility',
 'Facility for waste treatment, recycling, or disposal',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"facility_type": {"type": "string", "enum": ["landfill", "incinerator", "MRF", "composting", "WtE", "transfer_station"]}, "capacity_tons_year": {"type": "number"}, "waste_types_accepted": {"type": "array", "items": {"type": "string"}}, "status": {"type": "string", "enum": ["operational", "under_construction", "planned", "closed"]}}}',
 '["waste facility", "landfill", "incinerator", "MRF", "material recovery", "waste-to-energy", "recycling facility", "Tadweer", "transfer station"]'),

-- -----------------------------------------------------------------------------
-- Events
-- -----------------------------------------------------------------------------
('20000000-0001-0000-0000-000000000013', 'Outage', 2, 'Outage',
 'Unplanned service interruption affecting infrastructure',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"outage_type": {"type": "string", "enum": ["planned", "unplanned", "emergency", "forced"]}, "cause": {"type": "string"}, "start_time": {"type": "string", "format": "date-time"}, "end_time": {"type": "string", "format": "date-time"}, "affected_capacity_mw": {"type": "number"}, "customers_affected": {"type": "integer"}}}',
 '["outage", "interruption", "trip", "shutdown", "forced outage", "unplanned outage", "service disruption", "blackout", "load shedding"]'),

('20000000-0001-0000-0000-000000000014', 'MaintenanceEvent', 2, 'Maintenance Event',
 'Scheduled or unscheduled maintenance activity',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"maintenance_type": {"type": "string", "enum": ["preventive", "corrective", "predictive", "overhaul", "inspection"]}, "scheduled_start": {"type": "string", "format": "date-time"}, "scheduled_end": {"type": "string", "format": "date-time"}, "actual_start": {"type": "string", "format": "date-time"}, "actual_end": {"type": "string", "format": "date-time"}, "work_order_number": {"type": "string"}}}',
 '["maintenance", "overhaul", "inspection", "preventive maintenance", "corrective maintenance", "work order", "scheduled maintenance", "turnaround"]'),

('20000000-0001-0000-0000-000000000015', 'Inspection', 2, 'Inspection',
 'Regulatory or safety inspection event',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"inspection_type": {"type": "string", "enum": ["regulatory", "safety", "environmental", "quality", "third_party"]}, "inspector": {"type": "string"}, "inspection_date": {"type": "string", "format": "date"}, "result": {"type": "string", "enum": ["pass", "fail", "conditional", "pending"]}, "findings_count": {"type": "integer"}}}',
 '["inspection", "audit", "survey", "regulatory inspection", "safety inspection", "FANR inspection", "compliance audit", "third-party inspection"]'),

('20000000-0001-0000-0000-000000000016', 'VesselCall', 2, 'Vessel Call',
 'Ship arrival and departure at port',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"eta": {"type": "string", "format": "date-time"}, "ata": {"type": "string", "format": "date-time"}, "etd": {"type": "string", "format": "date-time"}, "atd": {"type": "string", "format": "date-time"}, "cargo_type": {"type": "string"}, "cargo_volume": {"type": "number"}}}',
 '["vessel call", "port call", "arrival", "departure", "ETA", "ETD", "berthing", "sailing", "ship arrival"]'),

-- -----------------------------------------------------------------------------
-- Records & Documents
-- -----------------------------------------------------------------------------
('20000000-0001-0000-0000-000000000017', 'Permit', 2, 'Permit',
 'Regulatory permit or license for operations',
 '00000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"permit_type": {"type": "string", "enum": ["operating", "construction", "environmental", "safety", "import_export"]}, "permit_number": {"type": "string"}, "issuing_authority": {"type": "string"}, "issue_date": {"type": "string", "format": "date"}, "expiry_date": {"type": "string", "format": "date"}, "status": {"type": "string", "enum": ["active", "expired", "suspended", "revoked", "pending"]}}}',
 '["permit", "license", "authorization", "NOC", "no objection certificate", "operating license", "FANR license", "environmental permit"]'),

('20000000-0001-0000-0000-000000000018', 'SafetyReport', 2, 'Safety Report',
 'Safety analysis, incident report, or safety assessment',
 '00000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"report_type": {"type": "string", "enum": ["incident", "near_miss", "safety_analysis", "risk_assessment", "investigation"]}, "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]}, "report_date": {"type": "string", "format": "date"}, "status": {"type": "string", "enum": ["open", "under_investigation", "closed", "resolved"]}}}',
 '["safety report", "incident report", "near miss", "accident report", "safety analysis", "risk assessment", "investigation report", "HSE report"]'),

('20000000-0001-0000-0000-000000000019', 'PurchaseAgreement', 2, 'Purchase Agreement',
 'Power or water purchase agreement contract',
 '00000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"agreement_type": {"type": "string", "enum": ["PPA", "PWPA", "WPA", "tolling"]}, "counterparty": {"type": "string"}, "capacity_contracted": {"type": "number"}, "term_years": {"type": "integer"}, "start_date": {"type": "string", "format": "date"}, "end_date": {"type": "string", "format": "date"}}}',
 '["PPA", "power purchase agreement", "PWPA", "water purchase agreement", "offtake agreement", "tolling agreement", "capacity contract"]'),

('20000000-0001-0000-0000-00000000001A', 'EnvironmentalAssessment', 2, 'Environmental Assessment',
 'Environmental impact assessment or environmental report',
 '00000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"assessment_type": {"type": "string", "enum": ["EIA", "EIS", "SEA", "monitoring"]}, "project_name": {"type": "string"}, "submission_date": {"type": "string", "format": "date"}, "approval_status": {"type": "string", "enum": ["approved", "pending", "rejected", "conditional"]}}}',
 '["EIA", "environmental impact assessment", "environmental study", "EIS", "environmental report", "environmental clearance", "sustainability report"]'),

-- -----------------------------------------------------------------------------
-- Locations
-- -----------------------------------------------------------------------------
('20000000-0001-0000-0000-00000000001B', 'MaintenanceDepot', 2, 'Maintenance Depot',
 'Facility for equipment maintenance and repair',
 '10000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"depot_type": {"type": "string", "enum": ["rail", "aviation", "marine", "vehicle", "equipment"]}, "capacity": {"type": "string"}, "services_offered": {"type": "array", "items": {"type": "string"}}}}',
 '["depot", "maintenance depot", "workshop", "maintenance facility", "repair facility", "service center", "MRO facility"]'),

('20000000-0001-0000-0000-00000000001C', 'ControlCenter', 2, 'Control Center',
 'Operations or network control center',
 '10000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"center_type": {"type": "string", "enum": ["grid", "network", "traffic", "port", "airport"]}, "systems_monitored": {"type": "array", "items": {"type": "string"}}}}',
 '["control center", "operations center", "OCC", "network control", "dispatch center", "SCADA", "control room", "load dispatch"]');

-- =============================================================================
-- RELATIONSHIP TYPES (Layer 2)
-- UUID Pattern: 30000000-0001-0000-0000-00000000000X
-- =============================================================================

INSERT INTO ontology_relations (id, relation_type, source_type_id, target_type_id, cardinality, semantics, extraction_hints) VALUES

('30000000-0001-0000-0000-000000000001', 'GENERATES', 
 '20000000-0001-0000-0000-000000000001', '10000000-0000-0000-0000-000000000003',
 'MANY_TO_MANY',
 'Power plant generates electricity supplied to a location or grid',
 '["generates", "produces", "supplies power to", "feeds", "MW output", "generation capacity"]'),

('30000000-0001-0000-0000-000000000002', 'SUPPLIES_WATER', 
 '20000000-0001-0000-0000-000000000002', '10000000-0000-0000-0000-000000000003',
 'MANY_TO_MANY',
 'Desalination plant supplies water to a location or network',
 '["supplies water", "provides water", "water supply", "MIGD", "potable water to"]'),

('30000000-0001-0000-0000-000000000003', 'CONNECTS_TO', 
 '20000000-0001-0000-0000-000000000004', '20000000-0001-0000-0000-000000000005',
 'MANY_TO_MANY',
 'Substation connects to transmission line in grid topology',
 '["connects to", "linked to", "interconnected", "feeds", "receives from", "grid connection"]'),

('30000000-0001-0000-0000-000000000004', 'DOCKS_AT', 
 '20000000-0001-0000-0000-00000000000A', '20000000-0001-0000-0000-000000000009',
 'MANY_TO_ONE',
 'Vessel docks at berth during port call',
 '["docks at", "berths at", "alongside", "moored at", "berthed", "at berth"]'),

('30000000-0001-0000-0000-000000000005', 'OPERATES_AT', 
 '20000000-0001-0000-0000-000000000008', '20000000-0001-0000-0000-000000000007',
 'MANY_TO_ONE',
 'Terminal operates at a port',
 '["operates at", "located at", "within", "part of", "serves"]'),

('30000000-0001-0000-0000-000000000006', 'TRAVERSES', 
 '20000000-0001-0000-0000-000000000010', '20000000-0001-0000-0000-00000000000E',
 'MANY_TO_MANY',
 'Locomotive traverses railway line segment',
 '["traverses", "runs on", "operates on", "travels", "route", "section"]'),

('30000000-0001-0000-0000-000000000007', 'SERVES', 
 '20000000-0001-0000-0000-00000000000F', '10000000-0000-0000-0000-000000000003',
 'MANY_TO_MANY',
 'Station serves a location or region',
 '["serves", "connects", "provides access to", "located in", "covers"]'),

('30000000-0001-0000-0000-000000000008', 'MAINTAINED_BY', 
 '10000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000005',
 'MANY_TO_ONE',
 'Asset is maintained by an organization (contractor or operator)',
 '["maintained by", "serviced by", "under contract with", "maintenance provider", "O&M contractor"]'),

('30000000-0001-0000-0000-000000000009', 'LICENSED_BY', 
 '10000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000005',
 'MANY_TO_ONE',
 'Asset is licensed or regulated by a regulatory body',
 '["licensed by", "regulated by", "authorized by", "approved by", "under jurisdiction of", "FANR", "DoE"]'),

('30000000-0001-0000-0000-00000000000A', 'AFFECTS', 
 '20000000-0001-0000-0000-000000000013', '10000000-0000-0000-0000-000000000001',
 'MANY_TO_MANY',
 'Outage affects one or more assets',
 '["affects", "impacts", "disrupts", "caused outage at", "resulted in loss of"]'),

('30000000-0001-0000-0000-00000000000B', 'SCHEDULED_FOR', 
 '20000000-0001-0000-0000-000000000014', '10000000-0000-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Maintenance event is scheduled for an asset',
 '["scheduled for", "planned for", "maintenance on", "work order for", "overhaul of"]'),

('30000000-0001-0000-0000-00000000000C', 'AUTHORIZES', 
 '20000000-0001-0000-0000-000000000017', '10000000-0000-0000-0000-000000000001',
 'ONE_TO_MANY',
 'Permit authorizes operation of an asset',
 '["authorizes", "permits", "licenses", "allows operation of", "grants approval for"]'),

('30000000-0001-0000-0000-00000000000D', 'GOVERNS', 
 '20000000-0001-0000-0000-000000000019', '20000000-0001-0000-0000-000000000001',
 'ONE_TO_MANY',
 'Purchase agreement governs power plant output',
 '["governs", "covers", "applies to", "contracted capacity from", "offtake from"]'),

('30000000-0001-0000-0000-00000000000E', 'PROCESSES', 
 '20000000-0001-0000-0000-000000000012', '10000000-0000-0000-0000-000000000001',
 'MANY_TO_MANY',
 'Waste processing facility processes waste streams',
 '["processes", "treats", "handles", "receives", "disposes of", "recycles"]'),

('30000000-0001-0000-0000-00000000000F', 'INSPECTS', 
 '20000000-0001-0000-0000-000000000015', '10000000-0000-0000-0000-000000000001',
 'MANY_TO_ONE',
 'Inspection event inspects an asset',
 '["inspects", "audits", "surveys", "examines", "assesses", "reviews"]');

-- =============================================================================
-- End of Infrastructure Domain Template
-- =============================================================================
