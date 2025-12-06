-- =============================================================================
-- Context Foundry: Aviation & Mobility Services Domain Template
-- =============================================================================
-- Archetype: AVIATION (ID: 05)
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: Integration Pass (from ChatGPT docs)
-- Date: 2025-12-06
-- RFC Version: 2.0 (Dual-System Architecture)
-- Companies Served: Etihad Airways, Wizz Air (Abu Dhabi), Q Mobility
-- =============================================================================

-- =============================================================================
-- SHARED TYPE REFERENCES (from shared_ontology.sql - DO NOT REDEFINE)
-- =============================================================================
-- Facility: 20000000-0000-0001-0000-000000000001
-- TransportFacility: 20000000-0000-0001-0000-000000000005
-- TransportVehicle: 20000000-0000-0003-0000-000000000003
-- OperationalTeam: 20000000-0000-0004-0000-000000000001
-- MaintenanceTeam: 20000000-0000-0004-0000-000000000002
-- OperationsTeam: 20000000-0000-0004-0000-000000000003
-- OperationalDocument: 20000000-0000-0005-0000-000000000001
-- MaintenanceLog: 20000000-0000-0005-0000-000000000004

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
('20000000-0005-0000-0000-000000000001', 'AviationEvent', 2, 'Aviation Event',
 'Abstract parent for aviation operational events.',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"start_time": {"type": "string", "format": "date-time"}, "end_time": {"type": "string", "format": "date-time"}, "status": {"type": "string", "enum": ["scheduled", "in_progress", "completed", "cancelled", "delayed"]}}}',
 '["event", "operation", "activity", "flight operation"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000002', 'AviationFacility', 2, 'Aviation Facility',
 'Abstract parent for aviation-related facilities.',
 '20000000-0000-0001-0000-000000000005',
 '{"type": "object", "properties": {"facility_code": {"type": "string"}, "operational_hours": {"type": "string"}}}',
 '["aviation facility", "airport facility", "terminal"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000003', 'CrewMember', 2, 'Crew Member',
 'Abstract parent for flight crew personnel.',
 '10000000-0000-0000-0000-000000000004',
 '{"type": "object", "properties": {"employee_id": {"type": "string"}, "crew_role": {"type": "string"}, "license_number": {"type": "string"}}}',
 '["crew", "crew member", "flight crew", "aircrew"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Facility Types
('20000000-0005-0000-0000-000000000004', 'AviationAirport', 2, 'AviationAirport',
 'Aviation facility for aircraft operations and passenger services.',
 '20000000-0005-0000-0000-000000000002',
 '{"type": "object", "properties": {"iata_code": {"type": "string"}, "icao_code": {"type": "string"}, "airport_type": {"type": "string", "enum": ["international", "domestic", "regional", "executive"]}, "runways": {"type": "integer"}, "annual_capacity_pax": {"type": "number"}}}',
 '["airport", "Zayed International Airport", "AUH", "Al Ain Airport", "AAN", "Abu Dhabi airport"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000005', 'AirportTerminal', 2, 'AirportTerminal',
 'Passenger terminal building at an airport.',
 '20000000-0005-0000-0000-000000000002',
 '{"type": "object", "properties": {"terminal_name": {"type": "string"}, "gates_count": {"type": "integer"}, "capacity_pax_hour": {"type": "number"}}}',
 '["terminal", "Terminal 1", "Terminal A", "passenger terminal"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000006', 'Hangar', 2, 'Hangar',
 'Aircraft storage and maintenance building.',
 '20000000-0005-0000-0000-000000000002',
 '{"type": "object", "properties": {"hangar_id": {"type": "string"}, "capacity_aircraft": {"type": "integer"}, "mro_certified": {"type": "boolean"}}}',
 '["hangar", "aircraft hangar", "maintenance hangar", "MRO hangar"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000007', 'Gate', 2, 'Gate',
 'Boarding gate at an airport terminal.',
 '20000000-0005-0000-0000-000000000002',
 '{"type": "object", "properties": {"gate_number": {"type": "string"}, "gate_type": {"type": "string", "enum": ["contact", "remote", "bus"]}, "status": {"type": "string", "enum": ["open", "closed", "boarding"]}}}',
 '["gate", "boarding gate", "Gate A1", "departure gate"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Vehicle Types
('20000000-0005-0000-0000-000000000008', 'Aircraft', 2, 'Aircraft',
 'Fixed-wing or rotary aircraft for air transport.',
 '20000000-0000-0003-0000-000000000003',
 '{"type": "object", "properties": {"registration": {"type": "string"}, "aircraft_type": {"type": "string"}, "manufacturer": {"type": "string"}, "model": {"type": "string"}, "seat_capacity": {"type": "integer"}, "range_km": {"type": "number"}, "status": {"type": "string", "enum": ["active", "maintenance", "grounded", "retired"]}}}',
 '["aircraft", "airplane", "plane", "A380", "B787", "A350", "registration", "tail number", "tail #", "reg.", "aircraft ID", "A6-"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000009', 'GroundVehicle', 2, 'Ground Vehicle',
 'Ground service vehicle at airport or mobility service.',
 '20000000-0000-0003-0000-000000000003',
 '{"type": "object", "properties": {"vehicle_id": {"type": "string"}, "vehicle_type": {"type": "string", "enum": ["tug", "fuel_truck", "catering", "bus", "taxi", "car"]}, "license_plate": {"type": "string"}}}',
 '["ground vehicle", "GSE", "tug", "fuel truck", "airport bus", "taxi"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Agent Types
('20000000-0005-0000-0000-00000000000A', 'Pilot', 2, 'Pilot',
 'Flight deck crew member certified to operate aircraft.',
 '20000000-0005-0000-0000-000000000003',
 '{"type": "object", "properties": {"license_type": {"type": "string", "enum": ["ATPL", "CPL", "PPL"]}, "type_ratings": {"type": "array", "items": {"type": "string"}}, "flight_hours": {"type": "number"}}}',
 '["pilot", "captain", "first officer", "commander", "PIC"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-00000000000B', 'CabinCrew', 2, 'Cabin Crew',
 'Flight attendant responsible for passenger safety and service.',
 '20000000-0005-0000-0000-000000000003',
 '{"type": "object", "properties": {"cabin_position": {"type": "string", "enum": ["purser", "senior", "standard"]}, "languages": {"type": "array", "items": {"type": "string"}}}}',
 '["cabin crew", "flight attendant", "purser", "steward", "stewardess"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-00000000000C', 'FlightCrew', 2, 'Flight Crew',
 'Team assigned to operate a specific flight.',
 '20000000-0000-0004-0000-000000000003',
 '{"type": "object", "properties": {"crew_complement": {"type": "integer"}, "duty_start": {"type": "string", "format": "date-time"}, "duty_end": {"type": "string", "format": "date-time"}}}',
 '["flight crew", "crew", "operating crew", "cockpit crew", "cabin crew"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-00000000000D', 'GroundCrew', 2, 'Ground Crew',
 'Team handling ground operations at airport.',
 '20000000-0000-0004-0000-000000000003',
 '{"type": "object", "properties": {"shift": {"type": "string"}, "station": {"type": "string"}, "responsibilities": {"type": "array", "items": {"type": "string"}}}}',
 '["ground crew", "ramp agents", "ground handlers", "GSE operators"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Event Types
('20000000-0005-0000-0000-00000000000E', 'Flight', 2, 'Flight',
 'Scheduled or charter flight operation.',
 '20000000-0005-0000-0000-000000000001',
 '{"type": "object", "properties": {"flight_number": {"type": "string"}, "origin": {"type": "string"}, "destination": {"type": "string"}, "scheduled_departure": {"type": "string", "format": "date-time"}, "scheduled_arrival": {"type": "string", "format": "date-time"}, "actual_departure": {"type": "string", "format": "date-time"}, "actual_arrival": {"type": "string", "format": "date-time"}, "flight_status": {"type": "string", "enum": ["scheduled", "boarding", "departed", "in_flight", "landed", "cancelled", "delayed"]}}}',
 '["flight", "EY", "WY", "flight number", "departure", "arrival", "route"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-00000000000F', 'MaintenanceCheck', 2, 'Maintenance Check',
 'Scheduled or unscheduled aircraft maintenance event.',
 '20000000-0005-0000-0000-000000000001',
 '{"type": "object", "properties": {"check_type": {"type": "string", "enum": ["A_check", "B_check", "C_check", "D_check", "line", "AOG"]}, "work_order": {"type": "string"}, "findings": {"type": "string"}}}',
 '["maintenance check", "A check", "C check", "heavy maintenance", "line maintenance", "AOG"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000010', 'TurnaroundEvent', 2, 'Turnaround Event',
 'Ground handling activities between flight arrival and departure.',
 '20000000-0005-0000-0000-000000000001',
 '{"type": "object", "properties": {"turnaround_time_min": {"type": "integer"}, "activities": {"type": "array", "items": {"type": "string"}}, "delays": {"type": "string"}}}',
 '["turnaround", "ground handling", "aircraft turnaround", "quick turn", "block time", "turn time", "TAT"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000011', 'PassengerBooking', 2, 'Passenger Booking',
 'Flight reservation and booking event.',
 '20000000-0005-0000-0000-000000000001',
 '{"type": "object", "properties": {"pnr": {"type": "string"}, "booking_date": {"type": "string", "format": "date"}, "fare_class": {"type": "string"}, "passengers": {"type": "integer"}, "total_fare": {"type": "number"}}}',
 '["booking", "reservation", "PNR", "ticket", "fare"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Record Types
('20000000-0005-0000-0000-000000000012', 'FlightPlan', 2, 'Flight Plan',
 'Operational flight plan document.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"plan_id": {"type": "string"}, "route": {"type": "string"}, "fuel_required_kg": {"type": "number"}, "flight_level": {"type": "integer"}, "alternate_airport": {"type": "string"}}}',
 '["flight plan", "OFP", "route", "fuel plan", "dispatch"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000013', 'AircraftLog', 2, 'Aircraft Log',
 'Technical log recording aircraft status and defects.',
 '20000000-0000-0005-0000-000000000004',
 '{"type": "object", "properties": {"log_date": {"type": "string", "format": "date"}, "flight_hours": {"type": "number"}, "cycles": {"type": "integer"}, "defects": {"type": "string"}, "deferred_items": {"type": "string"}}}',
 '["tech log", "aircraft log", "journey log", "defect log", "MEL"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000014', 'SafetyReport', 2, 'Safety Report',
 'Aviation safety occurrence or incident report.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"report_type": {"type": "string", "enum": ["ASR", "MOR", "incident", "accident"]}, "severity": {"type": "string", "enum": ["minor", "significant", "serious", "accident"]}, "occurrence_date": {"type": "string", "format": "date"}}}',
 '["safety report", "ASR", "occurrence", "incident report", "MOR", "occurrence report"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Additional Entity Types (from QA review)
('20000000-0005-0000-0000-000000000015', 'Passenger', 2, 'Passenger',
 'Individual traveling on a flight.',
 '10000000-0000-0000-0000-000000000004',
 '{"type": "object", "properties": {"passenger_id": {"type": "string"}, "ticket_number": {"type": "string"}, "frequent_flyer_id": {"type": "string"}, "seat_number": {"type": "string"}, "passenger_type": {"type": "string", "enum": ["adult", "child", "infant", "unaccompanied_minor"]}}}',
 '["passenger", "traveler", "pax", "guest", "flyer", "ticket holder"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000016', 'Route', 2, 'Route',
 'Standard flight route or air corridor.',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"route_code": {"type": "string"}, "origin_code": {"type": "string"}, "destination_code": {"type": "string"}, "waypoints": {"type": "array", "items": {"type": "string"}}, "distance_nm": {"type": "number"}, "flight_time_min": {"type": "integer"}}}',
 '["route", "air route", "flight path", "corridor", "AUH-JED", "city pair", "sector"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000017', 'Baggage', 2, 'Baggage',
 'Passenger baggage or cargo item.',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"bag_tag": {"type": "string"}, "weight_kg": {"type": "number"}, "baggage_type": {"type": "string", "enum": ["checked", "cabin", "oversized", "special"]}, "status": {"type": "string", "enum": ["checked_in", "loaded", "in_transit", "arrived", "claimed", "delayed", "lost"]}}}',
 '["baggage", "bag", "luggage", "bag tag", "checked bag", "lost luggage", "baggage claim"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000018', 'AirportRunway', 2, 'Airport Runway',
 'Aircraft runway at an airport for takeoff and landing operations.',
 '20000000-0005-0000-0000-000000000002',
 '{"type": "object", "properties": {"runway_id": {"type": "string"}, "length_m": {"type": "number"}, "width_m": {"type": "number"}, "surface": {"type": "string", "enum": ["asphalt", "concrete", "grass"]}, "ils_category": {"type": "string", "enum": ["CAT_I", "CAT_II", "CAT_IIIA", "CAT_IIIB", "none"]}, "status": {"type": "string", "enum": ["open", "closed", "maintenance"]}}}',
 '["runway", "RWY", "threshold", "touchdown zone", "ILS", "runway designation", "13L", "31R"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-000000000019', 'Airline', 2, 'Airline',
 'Air carrier organization operating flights.',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"iata_code": {"type": "string"}, "icao_code": {"type": "string"}, "airline_name": {"type": "string"}, "hub_airports": {"type": "array", "items": {"type": "string"}}, "fleet_size": {"type": "integer"}}}',
 '["airline", "carrier", "Etihad", "EY", "Wizz Air", "WY", "Emirates", "EK", "air carrier", "operator"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-00000000001A', 'Delay', 2, 'Delay',
 'Flight delay event with cause and duration.',
 '20000000-0005-0000-0000-000000000001',
 '{"type": "object", "properties": {"delay_code": {"type": "string"}, "delay_reason": {"type": "string", "enum": ["weather", "technical", "crew", "ATC", "security", "passenger", "operational", "connecting"]}, "delay_minutes": {"type": "integer"}, "responsible_party": {"type": "string"}}}',
 '["delay", "delayed", "late departure", "late arrival", "delay code", "IATA delay code"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('20000000-0005-0000-0000-00000000001B', 'FlightManifest', 2, 'Flight Manifest',
 'Passenger and cargo manifest for a flight.',
 '20000000-0000-0005-0000-000000000001',
 '{"type": "object", "properties": {"manifest_id": {"type": "string"}, "passenger_count": {"type": "integer"}, "cargo_weight_kg": {"type": "number"}, "special_passengers": {"type": "string"}, "generated_time": {"type": "string", "format": "date-time"}}}',
 '["manifest", "passenger manifest", "load sheet", "passenger list", "cargo manifest"]',
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

('30000000-0005-0000-0000-000000000001', 'AIRPORT_HAS_TERMINAL', 
 '20000000-0005-0000-0000-000000000004', '20000000-0005-0000-0000-000000000005',
 'ONE_TO_MANY',
 'Airport has terminals',
 '["has terminal", "terminal at", "terminals"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000002', 'TERMINAL_HAS_GATE', 
 '20000000-0005-0000-0000-000000000005', '20000000-0005-0000-0000-000000000007',
 'ONE_TO_MANY',
 'Terminal has gates',
 '["has gate", "gate at", "gates"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000003', 'AIRPORT_HAS_HANGAR', 
 '20000000-0005-0000-0000-000000000004', '20000000-0005-0000-0000-000000000006',
 'ONE_TO_MANY',
 'Airport has hangars',
 '["has hangar", "hangar at", "maintenance facility"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000004', 'FLIGHT_OPERATED_BY', 
 '20000000-0005-0000-0000-00000000000E', '20000000-0005-0000-0000-000000000008',
 'MANY_TO_ONE',
 'Flight is operated by an aircraft',
 '["operated by", "aircraft", "on", "using aircraft"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000005', 'FLIGHT_DEPARTS_FROM', 
 '20000000-0005-0000-0000-00000000000E', '20000000-0005-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Flight departs from airport',
 '["departs from", "from", "origin", "departure airport"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000006', 'FLIGHT_ARRIVES_AT', 
 '20000000-0005-0000-0000-00000000000E', '20000000-0005-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Flight arrives at airport',
 '["arrives at", "to", "destination", "arrival airport"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000007', 'FLIGHT_CREWED_BY', 
 '20000000-0005-0000-0000-00000000000E', '20000000-0005-0000-0000-00000000000C',
 'MANY_TO_ONE',
 'Flight is crewed by flight crew',
 '["crewed by", "crew", "operated by crew", "flight crew"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000008', 'CREW_INCLUDES_PILOT', 
 '20000000-0005-0000-0000-00000000000C', '20000000-0005-0000-0000-00000000000A',
 'ONE_TO_MANY',
 'Flight crew includes pilots',
 '["includes", "pilot", "captain", "first officer"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000009', 'CREW_INCLUDES_CABIN', 
 '20000000-0005-0000-0000-00000000000C', '20000000-0005-0000-0000-00000000000B',
 'ONE_TO_MANY',
 'Flight crew includes cabin crew',
 '["includes", "cabin crew", "flight attendant"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000000A', 'MAINTENANCE_ON', 
 '20000000-0005-0000-0000-00000000000F', '20000000-0005-0000-0000-000000000008',
 'MANY_TO_ONE',
 'Maintenance check performed on aircraft',
 '["on aircraft", "maintenance for", "check on"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000000B', 'MAINTENANCE_AT', 
 '20000000-0005-0000-0000-00000000000F', '20000000-0005-0000-0000-000000000006',
 'MANY_TO_ONE',
 'Maintenance performed at hangar',
 '["at hangar", "maintenance at", "in hangar"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000000C', 'TURNAROUND_FOR', 
 '20000000-0005-0000-0000-000000000010', '20000000-0005-0000-0000-00000000000E',
 'MANY_TO_ONE',
 'Turnaround event for a flight',
 '["turnaround for", "ground handling for", "servicing flight"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000000D', 'TURNAROUND_BY', 
 '20000000-0005-0000-0000-000000000010', '20000000-0005-0000-0000-00000000000D',
 'MANY_TO_ONE',
 'Turnaround handled by ground crew',
 '["handled by", "ground crew", "ramp agents"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000000E', 'BOOKING_FOR_FLIGHT', 
 '20000000-0005-0000-0000-000000000011', '20000000-0005-0000-0000-00000000000E',
 'MANY_TO_ONE',
 'Booking is for a flight',
 '["booking for", "reservation for", "on flight"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000000F', 'PLAN_FOR_FLIGHT', 
 '20000000-0005-0000-0000-000000000012', '20000000-0005-0000-0000-00000000000E',
 'ONE_TO_ONE',
 'Flight plan is for a flight',
 '["plan for", "OFP for", "dispatch for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000010', 'LOG_FOR_AIRCRAFT', 
 '20000000-0005-0000-0000-000000000013', '20000000-0005-0000-0000-000000000008',
 'MANY_TO_ONE',
 'Aircraft log is for an aircraft',
 '["log for", "tech log for", "aircraft log"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000011', 'REPORT_FOR_FLIGHT', 
 '20000000-0005-0000-0000-000000000014', '20000000-0005-0000-0000-00000000000E',
 'MANY_TO_ONE',
 'Safety report relates to a flight',
 '["report for", "occurrence on", "incident on flight"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000012', 'GROUND_VEHICLE_AT', 
 '20000000-0005-0000-0000-000000000009', '20000000-0005-0000-0000-000000000004',
 'MANY_TO_ONE',
 'Ground vehicle operates at airport',
 '["operates at", "based at", "stationed at"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

-- Additional Relationships (from QA review)
('30000000-0005-0000-0000-000000000013', 'BOOKING_FOR_PASSENGER', 
 '20000000-0005-0000-0000-000000000011', '20000000-0005-0000-0000-000000000015',
 'MANY_TO_MANY',
 'Booking is for passengers',
 '["booking for", "passenger booking", "booked passenger"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000014', 'PASSENGER_ON_FLIGHT', 
 '20000000-0005-0000-0000-000000000015', '20000000-0005-0000-0000-00000000000E',
 'MANY_TO_MANY',
 'Passenger is on a flight',
 '["on flight", "traveling on", "passenger on", "boarded"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000015', 'FLIGHT_USES_ROUTE', 
 '20000000-0005-0000-0000-00000000000E', '20000000-0005-0000-0000-000000000016',
 'MANY_TO_ONE',
 'Flight follows a route',
 '["route", "flight path", "via", "sector"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000016', 'BAGGAGE_FOR_PASSENGER', 
 '20000000-0005-0000-0000-000000000017', '20000000-0005-0000-0000-000000000015',
 'MANY_TO_ONE',
 'Baggage belongs to a passenger',
 '["baggage for", "belongs to", "passenger baggage"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000017', 'BAGGAGE_ON_FLIGHT', 
 '20000000-0005-0000-0000-000000000017', '20000000-0005-0000-0000-00000000000E',
 'MANY_TO_ONE',
 'Baggage is loaded on a flight',
 '["loaded on", "on flight", "baggage on"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000018', 'AIRPORT_HAS_RUNWAY', 
 '20000000-0005-0000-0000-000000000004', '20000000-0005-0000-0000-000000000018',
 'ONE_TO_MANY',
 'Airport has airport runways',
 '["has runway", "runway at", "runways"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-000000000019', 'FLIGHT_USES_RUNWAY', 
 '20000000-0005-0000-0000-00000000000E', '20000000-0005-0000-0000-000000000018',
 'MANY_TO_ONE',
 'Flight uses an airport runway for takeoff or landing',
 '["runway", "takeoff from", "landing on", "assigned runway"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000001A', 'FLIGHT_OPERATED_BY_AIRLINE', 
 '20000000-0005-0000-0000-00000000000E', '20000000-0005-0000-0000-000000000019',
 'MANY_TO_ONE',
 'Flight is operated by an airline',
 '["operated by", "airline", "carrier", "Etihad flight", "Wizz Air flight"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000001B', 'AIRCRAFT_OWNED_BY', 
 '20000000-0005-0000-0000-000000000008', '20000000-0005-0000-0000-000000000019',
 'MANY_TO_ONE',
 'Aircraft is owned or operated by an airline',
 '["owned by", "operated by", "fleet", "airline aircraft"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000001C', 'DELAY_FOR_FLIGHT', 
 '20000000-0005-0000-0000-00000000001A', '20000000-0005-0000-0000-00000000000E',
 'MANY_TO_ONE',
 'Delay event is for a flight',
 '["delay for", "flight delayed", "delayed flight"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000001D', 'MANIFEST_FOR_FLIGHT', 
 '20000000-0005-0000-0000-00000000001B', '20000000-0005-0000-0000-00000000000E',
 'ONE_TO_ONE',
 'Manifest is for a flight',
 '["manifest for", "passenger list for", "load sheet for"]',
 'ACTIVE', 1.0, '1.0.0', NOW()),

('30000000-0005-0000-0000-00000000001E', 'FLIGHT_AT_GATE', 
 '20000000-0005-0000-0000-00000000000E', '20000000-0005-0000-0000-000000000007',
 'MANY_TO_ONE',
 'Flight is assigned to a gate',
 '["at gate", "gate assignment", "boarding at gate"]',
 'ACTIVE', 1.0, '1.0.0', NOW());

-- =============================================================================
-- End of Aviation Domain Template
-- =============================================================================
