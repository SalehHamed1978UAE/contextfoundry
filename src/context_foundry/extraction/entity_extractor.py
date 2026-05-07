"""
Entity Extractor for Context Foundry - Multi-Domain Knowledge Extraction System.

Context Foundry is domain-agnostic and supports ANY industry or sector:
- Venture Capital & Private Equity (funds, portfolio companies, deals, board members)
- Healthcare (providers, patients, treatments, clinical trials)
- Legal (contracts, parties, cases, compliance)
- Human Resources (employees, compensation, org structure)
- Finance & Banking (transactions, accounts, regulations)
- Technology & IT Operations (services, infrastructure, incidents)
- Real Estate (properties, leases, tenants)
- And any other domain with documents containing entities and relationships

Uses LLM-powered NER to extract entities based on active schema configuration.
Uses Replit AI Integrations for OpenAI access (no API key required, billed to credits).
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import hashlib

from openai import OpenAI

logger = logging.getLogger(__name__)

from ..config.domain_schema import get_schema_loader, DomainSchemaLoader
from ..ontology_foundry.schema_service import OntologySchemaService, get_ontology_schema_service
from .entity_hygiene import is_valid_entity_name as hygiene_is_valid_entity_name
from .document_classifier import classify_with_fallback


# Issue 1 Fix: Metadata entities that should never be extracted as real entities
# These are document metadata fields, placeholders, or generic role references
METADATA_BLACKLIST = {
    # Document metadata fields that should never be entities
    'document owner',
    'document author',
    'author',
    'owner',
    'created by',
    'modified by',
    'last modified by',
    'file owner',
    'prepared by',
    'reviewed by',
    'approved by',
    # Generic role placeholders
    'direct reports',
    'incident commander',
    'tbd',
    'to be determined',
    'n/a',
    'not applicable',
    'unknown',
    'undefined',
    'placeholder',
    'your name',
    'your name here',
    'insert name',
    '[name]',
    '[title]',
    '[role]',
}


def load_few_shot_examples(domain: str = "core") -> list:
    """Load few-shot examples for the specified domain."""
    examples_dir = Path(__file__).parent.parent.parent.parent / "brain" / "examples"
    
    domain_file = examples_dir / f"{domain}_examples.json"
    core_file = examples_dir / "core_examples.json"
    
    file_to_load = domain_file if domain_file.exists() else core_file
    
    if not file_to_load.exists():
        return []
    
    try:
        with open(file_to_load, 'r') as f:
            data = json.load(f)
            return data.get('examples', [])
    except Exception:
        return []


def format_few_shot_examples(examples: list) -> str:
    """Format few-shot examples for inclusion in prompt."""
    if not examples:
        return "No examples available."
    
    formatted = []
    for i, ex in enumerate(examples, 1):
        input_text = ex.get('input', '')
        output = ex.get('output', [])
        
        output_str = "\n".join([
            f"  - \"{e['name']}\" -> {e['type']} ({e.get('reasoning', '')})"
            for e in output
        ])
        
        formatted.append(f"Example {i}:\nInput: \"{input_text}\"\nOutput:\n{output_str}")
    
    return "\n\n".join(formatted)

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

CORE_FOUNDATION_TYPES = {
    "PERSON": {
        "description": "A human individual with a proper name (first + last name). NOT job titles alone.",
        "required_fields": ["canonical_name"],
        "optional_fields": ["role", "title", "department", "organization", "email"],
        "role_extraction_rules": [
            "Only extract 'role' if EXPLICITLY stated: 'X is the Y', 'X, Y', 'Y: X'",
            "Use FORMAL titles only: CEO, CFO, Chief Engineer, VP, Director, President",
            "Do NOT use departments/teams as roles (Engineering, Aerospace Division)",
            "Do NOT infer roles from project associations (Falcon X Lead → wrong)",
            "If role not explicitly stated, OMIT the role property entirely"
        ]
    },
    "ORGANIZATION": {
        "description": "A company, team, department, institution, or any organized group",
        "required_fields": ["canonical_name"],
        "optional_fields": ["org_type", "industry", "location", "parent_org"]
    },
    "DOCUMENT": {
        "description": "A document, report, file, policy, or written artifact",
        "required_fields": ["canonical_name"],
        "optional_fields": ["document_type", "author", "date", "version"]
    },
    "LOCATION": {
        "description": "A physical or logical place - city, region, address, or venue",
        "required_fields": ["canonical_name"],
        "optional_fields": ["location_type", "address", "parent_location"]
    },
    "EVENT": {
        "description": "An occurrence, meeting, incident, milestone, or happening",
        "required_fields": ["canonical_name"],
        "optional_fields": ["event_type", "date", "duration", "participants"]
    },
    "CONCEPT": {
        "description": "An abstract idea, topic, theme, principle, or methodology",
        "required_fields": ["canonical_name"],
        "optional_fields": ["category", "related_concepts", "definition"]
    },
    "PROCESS": {
        "description": "A workflow, procedure, method, or sequence of steps",
        "required_fields": ["canonical_name"],
        "optional_fields": ["process_type", "steps", "owner", "status"]
    },
    "DATE": {
        "description": "A specific date, time period, deadline, or temporal reference",
        "required_fields": ["canonical_name"],
        "optional_fields": ["date_value", "date_type", "timezone"]
    }
}


@dataclass
class ExtractedEntity:
    """Represents an entity extracted from text."""
    id: str
    entity_type: str
    canonical_name: str
    properties: Dict
    source_span: str
    source_document_id: str
    source_chunk_id: str
    source_sentence_idx: int
    confidence: float
    tenant_id: Optional[str] = None
    extracted_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "canonical_name": self.canonical_name,
            "properties": self.properties,
            "source_span": self.source_span,
            "source_document_id": self.source_document_id,
            "source_chunk_id": self.source_chunk_id,
            "source_sentence_idx": self.source_sentence_idx,
            "confidence": self.confidence,
            "tenant_id": self.tenant_id,
            "extracted_at": self.extracted_at.isoformat(),
        }


class EntityExtractor:
    """
    LLM-powered entity extractor that works with any domain schema.

    Loads entity types dynamically from the active domain schema configuration.

    Phase 3 Enhancement: When use_ontology_schema=True, generates extraction prompts
    from ACTIVE ontology types in the database, enabling schema-constrained extraction.
    """

    def __init__(
        self,
        model: str = "gpt-4o",  # Using GPT-4o for better entity extraction (4o-mini has ~21% omission rate)
        temperature: float = 0.0,  # Deterministic for consistent extraction
        max_retries: int = 3,
        schema_loader: Optional[DomainSchemaLoader] = None,
        use_ontology_schema: bool = True,  # Phase 3: Use ontology-constrained extraction
    ):
        """
        Initialize the entity extractor.

        Args:
            model: OpenAI model to use
            temperature: Temperature for generation (0.0 = deterministic)
            max_retries: Maximum retries on API errors
            schema_loader: Optional schema loader instance (uses singleton if not provided)
            use_ontology_schema: If True, generate prompts from ACTIVE ontology types (Phase 3)
        """
        self.client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL,
        )
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self._schema_loader = schema_loader
        self.use_ontology_schema = use_ontology_schema
        self._ontology_service: Optional[OntologySchemaService] = None
    
    @property
    def schema_loader(self) -> DomainSchemaLoader:
        """Get schema loader (lazy initialization)."""
        if self._schema_loader is None:
            self._schema_loader = get_schema_loader()
        return self._schema_loader

    @property
    def ontology_service(self) -> Optional[OntologySchemaService]:
        """Get OntologySchemaService (lazy initialization, Phase 3)."""
        if self._ontology_service is None and self.use_ontology_schema:
            try:
                self._ontology_service = get_ontology_schema_service()
                if not self._ontology_service._loaded:
                    from ..models.schema import get_session
                    session = get_session()
                    self._ontology_service.load(session)
                logger.info(f"[OntologyExtraction] Loaded {len(self._ontology_service.entity_types)} entity types from ontology")
            except Exception as e:
                logger.warning(f"[OntologyExtraction] Could not load ontology schema: {e}")
                self._ontology_service = None
        return self._ontology_service

    def get_valid_entity_types(self) -> Set[str]:
        """Get set of valid entity type names from schema."""
        # Phase 3: Prefer ontology types if available
        if self.use_ontology_schema and self.ontology_service:
            return self.ontology_service.get_valid_entity_types()
        return self.schema_loader.get_valid_entity_types()

    def _build_ontology_constrained_prompt(self, text: str) -> str:
        """
        Build extraction prompt constrained to ACTIVE ontology types (Phase 3).

        This generates the prompt dynamically from ontology.types table,
        ensuring extraction only produces types that exist in the ontology.
        """
        if not self.ontology_service:
            logger.warning("[OntologyExtraction] No ontology service, falling back to default prompt")
            return self._build_entity_extraction_prompt(text)

        # Get entity type list and descriptions from ontology
        entity_type_section = self.ontology_service.build_entity_extraction_prompt()

        valid_types = sorted(self.ontology_service.get_valid_entity_types())
        valid_types_str = ", ".join(valid_types)

        prompt = f"""Extract ALL entities from this text using ONLY the following ontology types.

## VALID ENTITY TYPES (from ontology schema)

{entity_type_section}

## RULES

1. ONLY use entity types listed above - do not invent new types
2. If an entity doesn't fit any type, use the closest match or skip it
3. Extract ALL entities exhaustively - a short list is a failed extraction
4. For PERSON entities, only use 'role' if explicitly stated with formal title

## OUTPUT FORMAT

Return valid JSON array only (no markdown):
[{{"entity_type": "TYPE", "canonical_name": "exact text", "confidence": 0.9, "properties": {{}}}}]

Valid types: {valid_types_str}

## TEXT TO EXTRACT

{text}"""

        return prompt

    def validate_against_ontology(self, entities: List['ExtractedEntity']) -> Dict:
        """
        Validate extracted entities against ACTIVE ontology types (Phase 3).

        Returns:
            Dict with 'valid', 'invalid', and 'warnings' lists
        """
        result = {
            'valid': [],
            'invalid': [],
            'warnings': [],
            'type_distribution': {},
        }

        if not self.ontology_service:
            # No ontology loaded, all entities pass
            result['valid'] = entities
            result['warnings'].append("No ontology schema loaded - all types accepted")
            return result

        valid_types = self.ontology_service.get_valid_entity_types()

        for entity in entities:
            entity_type = entity.entity_type.upper()
            result['type_distribution'][entity_type] = result['type_distribution'].get(entity_type, 0) + 1

            if entity_type in valid_types:
                result['valid'].append(entity)
            elif entity_type in self.type_mappings:
                # Type can be mapped to a valid type
                mapped_type = self.type_mappings[entity_type]
                if mapped_type.upper() in valid_types:
                    result['valid'].append(entity)
                    result['warnings'].append(f"Type '{entity_type}' mapped to '{mapped_type}'")
                else:
                    result['invalid'].append(entity)
                    result['warnings'].append(f"Type '{entity_type}' mapped to '{mapped_type}' which is not in ontology")
            else:
                result['invalid'].append(entity)
                result['warnings'].append(f"Entity '{entity.canonical_name}' has unknown type '{entity_type}'")

        logger.info(f"[OntologyValidation] {len(result['valid'])} valid, {len(result['invalid'])} invalid entities")
        return result
    
    def _append_document_context_rules(self, prompt: str, document_context: Optional[Dict]) -> str:
        """P1.4: Append document-type-specific extraction rules to a prompt."""
        if not document_context:
            return prompt
        doc_type = (document_context.get("doc_type") or "").lower()
        if "customer" in doc_type:
            prompt += """

DOCUMENT CONTEXT: CUSTOMER PROFILE
This document describes a CUSTOMER organization. Critical rules:
1. The organization NAMED in the document title/filename is the CUSTOMER.
2. When extracting SUPPLIES relationships, the customer is the TARGET.
3. Do NOT extract program/product names as targets — extract the CUSTOMER ORG.
4. Example: "Boeing sources materials from Hexcel" → SUPPLIES(Hexcel, Boeing), CUSTOMER_OF(Boeing, Hexcel)
"""
        elif "supplier" in doc_type:
            prompt += """

DOCUMENT CONTEXT: SUPPLIER PROFILE
This document describes a SUPPLIER organization. Critical rules:
1. The organization described is the SUPPLIER (source of SUPPLIES).
2. Always extract SUPPLIES(supplier, customer) relationships explicitly.
3. Also extract CUSTOMER_OF(customer, supplier) for the inverse direction.
"""
        return prompt

    def _build_entity_extraction_prompt(self, text: str, document_context: Optional[Dict] = None) -> str:
        """Build simplified entity extraction prompt optimized for completeness.

        Context Foundry is a MULTI-DOMAIN system supporting any industry:
        VC/Investment, Healthcare, Legal, HR, Finance, IT, Real Estate, etc.

        P1.4: When document_context is provided, document-type-specific rules
        (e.g. CUSTOMER PROFILE / SUPPLIER PROFILE) are appended to the prompt.
        """
        core_types = "COMPONENT, CONCEPT, SERVICE, PROCESS, PERSON, ORGANIZATION, TEAM, DATABASE, METRIC, INCIDENT, EVENT, DOCUMENT, TOOL, TIME_PERIOD, LOCATION"

        prompt = f"""Extract ALL entities from this text. Be EXHAUSTIVE - a short list is a FAILED extraction.

This is a MULTI-DOMAIN knowledge extraction system. The text may come from ANY industry:
- Venture Capital & Investment (portfolio companies, funds, deals, board members)
- Healthcare (patients, providers, treatments, facilities)
- Legal (contracts, parties, clauses, cases)
- Human Resources (employees, positions, compensation, departments)
- Finance & Banking (accounts, transactions, regulations)
- Technology & IT Operations (services, databases, incidents)
- Real Estate (properties, leases, tenants)
- And more...

Valid types: {core_types}

## ENTITY TYPE DEFINITIONS (with multi-domain examples)

COMPONENT: System parts, subsystems, modules, divisions
  - Tech: "Auth Module", "Semantic Memory", "API Gateway"
  - Business: "Investment Committee", "Due Diligence Team", "Claims Processing Unit"

CONCEPT: Abstract ideas, approaches, patterns, techniques, terms-of-art
  - Tech: "RAG", "Fine-Tuning", "Microservices Architecture"
  - VC: "Series A", "Cap Table", "Liquidation Preference", "Pro-rata Rights"
  - Legal: "Force Majeure", "Indemnification", "Non-Compete"
  - Healthcare: "HIPAA Compliance", "Clinical Trial Phase", "Standard of Care"

SERVICE: Running software services, APIs, business services
  - Tech: "OrderService", "PaymentAPI", "Auth Service"
  - Business: "Payroll Processing", "Claims Adjudication", "Portfolio Monitoring"

PROCESS: Workflows, procedures, phases, stages, lifecycles
  - Tech: "CI/CD Pipeline", "Deployment Process", "Code Review"
  - VC: "Due Diligence", "Term Sheet Negotiation", "Board Meeting Cadence"
  - HR: "Onboarding Process", "Performance Review Cycle", "Compensation Planning"

PERSON: Named individuals AND job roles/titles
  - "James Rodriguez", "Sarah Chen", "Dr. Michael Lee"
  - "CEO", "Managing Partner", "Chief Medical Officer", "General Counsel"
  - "Board Member", "Limited Partner", "Portfolio Manager"

ORGANIZATION: Companies, funds, agencies, institutions - ANY entity that acts
  - Corporations: "Apple", "Goldman Sachs", "Mayo Clinic"
  - VC/PE: "Sequoia Capital", "TechVentures Fund II", "Andreessen Horowitz"
  - Portfolio Companies: "CloudMatrix", "HealthSync", "DataPipe"
  - Government: "SEC", "FDA", "Department of Labor"

TEAM: Named teams, committees, groups within organizations
  - "Investment Committee", "Board of Directors", "Engineering Team"
  - "Compensation Committee", "Audit Committee", "Deal Team"

DATABASE: Data stores, repositories, registries, record systems
  - Tech: "PostgreSQL", "Redis Cache", "Data Warehouse"
  - Business: "Cap Table", "Portfolio Database", "Patient Registry", "Contract Repository"

METRIC: Measurements, scores, KPIs, valuations, financial figures
  - Tech: "uptime 99.9%", "latency < 100ms"
  - VC: "ARR $5M", "MRR", "Burn Rate", "Runway 18 months", "$10M valuation"
  - HR: "Compensation $250K", "Bonus 20%", "Equity 0.5%"

INCIDENT: Disruptions, issues, cases, claims - domain-specific events requiring response
  - Tech: "INC-2025-1215", "Production Outage", "Security Breach"
  - Legal: "Case #2024-CV-1234", "Arbitration Filing"
  - Healthcare: "Adverse Event", "Malpractice Claim"
  - HR: "Grievance #456", "EEOC Complaint"

EVENT: Meetings, milestones, transactions, occurrences
  - "Board Meeting Q1 2025", "Series B Close", "IPO", "Acquisition"
  - "Annual Review", "Contract Signing", "FDA Approval"

DOCUMENT: Referenced reports, agreements, filings, records
  - "Term Sheet", "Investment Agreement", "Employment Contract"
  - "10-K Filing", "Board Resolution", "NDA", "SAFE Agreement"
  - "Runbook", "Architecture Doc", "Policy Manual"

TOOL: Software, platforms, instruments
  - "Salesforce", "Carta", "DocuSign", "Bloomberg Terminal"

TIME_PERIOD: Dates, time ranges, deadlines, fiscal periods
  - "Q4 2025", "FY2024", "December 2025", "18-month runway"

LOCATION: PHYSICAL places (cities, countries, buildings, facilities)
  - "San Francisco", "New York Office", "Boston", "Building A"

## CRITICAL RULES

1. NEVER use "RELATIONSHIP" as an entity type - relationships are edges, not nodes
2. Use COMPONENT for system parts like "Semantic Memory", "Episodic Memory", "Procedural Memory"
3. Use CONCEPT for abstract ideas like "RAG", "Fine-Tuning", "World Model"
4. Use SERVICE only for actual running services (OrderService, PaymentAPI)
5. Use PROCESS for workflow stages like "Ingestion", "Perception", "Learning"
6. Extract ALL capitalized multi-word terms and named concepts
7. Be EXHAUSTIVE - do not stop until every entity is captured
8. When uncertain, INCLUDE with confidence 0.7-0.8

## SUPPLY-CHAIN ENTITY EXTRACTION (CRITICAL)

When a document profiles a CUSTOMER or SUPPLIER, the named company is the
PRIMARY ORGANIZATION entity — NOT a program, product, or contract:

CORRECT extractions:
  "Boeing sources composite materials from Hexcel"
    → ORGANIZATION: "Boeing"
    → ORGANIZATION: "Hexcel"
  "Customer Profile: Lockheed Martin (F-35 Block 4 program)"
    → ORGANIZATION: "Lockheed Martin"   (primary - the customer)
    → PROJECT: "F-35 Block 4"           (secondary - a program of theirs)
  "Nel Hydrogen supplies fuel cells to Boeing"
    → ORGANIZATION: "Nel Hydrogen"      (the supplier)
    → ORGANIZATION: "Boeing"            (the customer)

WRONG (do NOT do this):
  - Extracting "F-35 Block 4" as the primary entity from a Lockheed customer profile
  - Extracting "Boeing Programs" as ORGANIZATION when "Boeing" already exists
  - Extracting "The Boeing Company" and "Boeing" as separate entities (use the canonical short form)

CANONICAL FORM RULE:
When the same organization appears under multiple surface forms in the document
("Boeing", "The Boeing Company", "Boeing Commercial Airplanes"), extract ONE
ORGANIZATION entity using the canonical short form ("Boeing"). Do NOT emit
duplicates with type variations (COMPETITOR, CUSTOMER, ORGANIZATION).

## ROLE EXTRACTION RULES (CRITICAL FOR PERSON ENTITIES)

When extracting the 'role' property for PERSON entities:

1. ONLY use EXPLICIT role statements from the text:
   CORRECT: "Dr. Victoria Chen, CEO" → role: "CEO"
   CORRECT: "Michael Chang serves as CFO" → role: "CFO"  
   CORRECT: "Chief Engineer: Dr. Elena Rodriguez" → role: "Chief Engineer"
   
2. NEVER infer roles from context or associations:
   WRONG: "Thomas Wright leads UAV engineering" → role: "UAV Engineering Lead"
   CORRECT: "Thomas Wright leads UAV engineering" → NO role property (not explicitly titled)
   
3. DISTINGUISH formal titles from job functions:
   FORMAL TITLES (use these): CEO, CFO, COO, CTO, CISO, Chief Engineer, VP, Director, President, Division President
   JOB FUNCTIONS (avoid): Engineering Lead, Project Manager, Team Lead, Program Manager
   
4. When role is NOT explicitly stated with a formal title, OMIT the role property entirely.
   It is better to have NO role than a WRONG role.

5. Use high confidence (0.9+) only when role is explicitly stated with formal title.
   Use lower confidence (0.7-0.8) for inferred associations.

## DO NOT EXTRACT

- Raw numbers like "0.95", "2024", "100" - these are VALUES, not entities
- JSON field values from code examples (e.g., if you see "confidence": 0.95, do NOT extract "0.95")
- Timestamps like "2026-01-06T10:30:00Z"
- Percentages like "95%" or "95% confidence"
- Code block contents - only extract entities mentioned in prose text
- Short strings under 3 characters

## OUTPUT FORMAT

Return valid JSON array only (no markdown):
[{{"entity_type": "TYPE", "canonical_name": "exact text", "confidence": 0.9}}]

## TEXT TO EXTRACT

{text}"""
        # P1.4: Append document-type-specific extraction rules when available
        prompt = self._append_document_context_rules(prompt, document_context)
        return prompt
    
    def _chunk_text(self, text: str, chunk_size: int = 2000, overlap: int = 400) -> List[str]:
        """Split text into overlapping chunks to avoid output saturation."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('. ')
                if last_period > chunk_size * 0.6:
                    end = start + last_period + 2
                    chunk = text[start:end]
            
            chunks.append(chunk)
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks
    
    def _build_system_prompt(self) -> str:
        """Build dynamic system prompt from active schema."""
        schema = self.schema_loader.schema
        return f"You are an expert entity extractor. Your goal is COMPLETENESS - extract ALL entities from {schema.domain} documents. Respond only with valid JSON."
    
    def _generate_entity_id(self, entity_type: str, canonical_name: str) -> str:
        """Generate deterministic entity ID."""
        combined = f"{entity_type}:{canonical_name.lower()}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _parse_llm_response(self, response_text: str) -> List[Dict]:
        """Parse LLM response into structured entities."""
        text = response_text.strip()
        if text.startswith("```"):
            text = re.sub(r"```json?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        
        try:
            entities = json.loads(text)
            if isinstance(entities, list):
                return entities
            return []
        except json.JSONDecodeError:
            try:
                match = re.search(r'\[.*\]', text, re.DOTALL)
                if match:
                    return json.loads(match.group())
            except:
                pass
            return []
    
    def _validate_entity(self, entity: Dict) -> bool:
        """Validate extracted entity has required fields.
        
        OPEN CAPTURE: Accept any entity type - schema validation is done downstream
        by the canonical mapper (Phase 2). This enables domain-agnostic extraction.
        """
        if "entity_type" not in entity:
            return False
        if "canonical_name" not in entity and "name" not in entity:
            return False
        
        # OPEN CAPTURE: Accept any entity type - no longer reject unknown types
        # The raw_entity_type will be preserved and mapped to canonical types later
        entity_type = entity["entity_type"].upper()
        if not entity_type or len(entity_type) < 2:
            return False
        
        name = entity.get("canonical_name") or entity.get("name", "")
        if not self._is_valid_entity_name(name):
            return False
        
        return True
    
    def _is_valid_entity_name(self, name: str) -> bool:
        """
        Validate that an entity name is meaningful and not garbage.
        
        Uses centralized entity_hygiene.is_valid_entity_name() for core validation
        (newlines, double spaces, state abbrevs, etc.) plus additional extraction-time
        checks for LLM artifacts.
        
        Rejects:
        - Entities with embedded newlines (centralized hygiene)
        - Entities with double spaces (concatenation artifacts)
        - State abbreviations and garbage tokens (centralized hygiene)
        - Pure numbers (e.g., "0.95", "2024", "100")
        - Pure punctuation
        - Very short names (< 2 chars)
        - ISO dates/timestamps
        - Percentage patterns (e.g., "95%", "95% confidence")
        - JSON-like values
        """
        if not name or len(name.strip()) < 2:
            return False
        
        # Use centralized entity hygiene for newline/concatenation checks
        if not hygiene_is_valid_entity_name(name):
            return False
        
        name_clean = name.strip()
        
        # Additional LLM extraction-specific checks
        if re.match(r'^[\d.,\-+]+$', name_clean):
            return False
        
        if re.match(r'^\d{4}(-\d{2})?(-\d{2})?(T[\d:]+)?Z?$', name_clean):
            return False
        
        if re.match(r'^\d+%', name_clean):
            return False
        
        if re.match(r'^[\d.,]+\s*(confidence|percent|%)', name_clean, re.IGNORECASE):
            return False
        
        if name_clean.startswith('"') or name_clean.startswith("'"):
            return False
        
        if re.match(r'^[_\-]+[a-z_]+$', name_clean):
            return False
        
        if re.match(r'^(true|false|null|none|undefined)$', name_clean, re.IGNORECASE):
            return False
        
        return True
    
    SPECIFIC_TYPE_PATTERNS = [
        ("TEAM", ["team", "squad"]),
        ("INCIDENT", ["inc-", "incident", "outage", "sev1", "sev2"]),
        ("SERVICE", ["service", "gateway", "api", "app", "server", "endpoint", "microservice", "portal"]),
        ("DATABASE", ["database", "db", "datastore", "store", "warehouse", "cache", "redis", "postgres", "mysql", "inventory"]),
    ]
    
    @property
    def type_mappings(self) -> Dict[str, str]:
        """Get type mappings from OntologySchemaService.
        
        Week 3 Stabilization: Consolidated from hardcoded TYPE_MAPPING to 
        database-backed mappings via OntologySchemaService.
        """
        try:
            service = get_ontology_schema_service()
            return service.type_mappings
        except Exception:
            return {
                "APPLICATION": "SERVICE",
                "API": "SERVICE",
                "PLATFORM": "SERVICE",
                "GATEWAY": "SERVICE",
                "MICROSERVICE": "SERVICE",
                "GROUP": "TEAM",
                "SQUAD": "TEAM",
                "DEPARTMENT": "TEAM",
                "DIVISION": "ORGANIZATION",  # P1.5: business divisions are organizations
                "OUTAGE": "INCIDENT",
                "ISSUE": "INCIDENT",
                "FAILURE": "INCIDENT",
                "DATASTORE": "DATABASE",
                "REPOSITORY": "DATABASE",
                "CACHE": "DATABASE",
                "TECHNOLOGY": "SERVICE",
            }
    
    def _correct_entity_type(self, entity: Dict) -> Dict:
        """Correct common entity type misclassifications.
        
        Uses a priority system:
        1. Direct mapping from OntologySchemaService type_mappings
        2. Pattern matching on entity name (e.g., "Payment Gateway" → SERVICE)
        3. LOCATION → ORGANIZATION ACT test
        
        Week 3 Stabilization: Now uses OntologySchemaService for type mappings.
        """
        entity_type = entity.get("entity_type", "").upper()
        name = entity.get("canonical_name", entity.get("name", ""))
        name_lower = name.lower()
        
        mappings = self.type_mappings
        if entity_type in mappings:
            new_type = mappings[entity_type]
            logger.info(f"[TypeCorrection] Mapping: {entity_type} → {new_type} for '{name}'")
            entity["entity_type"] = new_type
            return entity
        
        if entity_type in ("ORGANIZATION", "PROCESS", "EVENT", "CONCEPT"):
            for specific_type, patterns in self.SPECIFIC_TYPE_PATTERNS:
                if any(pattern in name_lower for pattern in patterns):
                    logger.info(f"[TypeCorrection] Pattern match: {entity_type} → {specific_type} for '{name}'")
                    entity["entity_type"] = specific_type
                    return entity
        
        if entity_type == "LOCATION":
            org_patterns = [
                "government", "ministry", "department", "agency", "committee",
                "corporation", "company", "holding", "subsidiary", "division",
                "board", "council", "authority", "office", "bureau", "institute",
                "foundation", "association", "federation", "organization", "team",
                "group", "unit", "branch", "sector", "regime", "administration"
            ]
            for pattern in org_patterns:
                if pattern in name_lower:
                    entity["entity_type"] = "ORGANIZATION"
                    break

        # === P1.5: UPWARD CORRECTION — Promote TEAM/DIVISION/GROUP to ORGANIZATION ===
        if entity_type in ("TEAM", "DIVISION", "GROUP", "UNIT", "BRANCH"):
            business_indicators = [
                "industries", "aerospace", "materials", "systems", "energy",
                "solutions", "technologies", "corporation", "company",
                "holdings", "group", "partners", "associates", "international",
                "global", "digital", "advanced", "automated", "defense",
                "space", "aviation", "marine", "automotive", "electronics",
                "communications", "networks", "robotics", "biotech",
            ]
            if any(indicator in name_lower for indicator in business_indicators):
                logger.info(f"[TypeCorrection] Upward: {entity_type} → ORGANIZATION for '{name}'")
                entity["entity_type"] = "ORGANIZATION"
                return entity

            # Promote on well-known division patterns
            division_patterns = [
                r"\b(\w+)\s+(division|group|unit|sector|segment)\b",
                r"\b(\w+)\s+(advanced\s+\w+|digital\s+\w+)\b",
            ]
            for pattern in division_patterns:
                if re.search(pattern, name_lower):
                    logger.info(f"[TypeCorrection] Pattern upward: {entity_type} → ORGANIZATION for '{name}'")
                    entity["entity_type"] = "ORGANIZATION"
                    return entity

        return entity
    
    def _normalize_entity(self, entity: Dict) -> Dict:
        """Normalize entity fields with open capture canonical mapping."""
        from .canonical_mapper import get_canonical_mapper
        
        if "name" in entity and "canonical_name" not in entity:
            entity["canonical_name"] = entity.pop("name")
        
        entity["canonical_name"] = entity["canonical_name"].strip()
        
        raw_type = entity["entity_type"]
        entity["raw_entity_type"] = raw_type
        
        mapper = get_canonical_mapper()
        canonical_type, is_mapped = mapper.map_entity_type(raw_type)
        entity["entity_type"] = canonical_type
        entity["is_mapped"] = is_mapped
        
        if not is_mapped:
            logger.debug(f"[OpenCapture] Unmapped entity type: '{raw_type}' → '{canonical_type}'")
        
        entity = self._correct_entity_type(entity)
        
        if "properties" not in entity:
            entity["properties"] = {}
        
        if "confidence" not in entity:
            entity["confidence"] = 0.75
        else:
            entity["confidence"] = min(1.0, max(0.0, float(entity["confidence"])))
        
        if "source_span" not in entity:
            entity["source_span"] = entity["canonical_name"]
        
        return entity
    
    def _build_concept_gap_check_prompt(self, text: str, already_extracted: List[str]) -> str:
        """Build prompt for second-pass concept extraction."""
        already_list = ", ".join(already_extracted[:30]) if already_extracted else "none"
        
        return f"""You already extracted these entities: {already_list}

Now find ADDITIONAL entities we MISSED. Focus on:

1. CONCEPT: Named frameworks, methodologies, standards, approaches, models, systems, architectures
   - Look for capitalized multi-word terms: "Federated Data Catalog", "Hub-and-Spoke Model"
   - Look for acronyms and their full names: "KPI", "ROI", "GDPR", "API"
   - Section titles and document headers are often CONCEPT entities

2. PERSON: Job titles and named roles: "Data Steward", "Chief Data Officer", "Executive Sponsor"

3. DOCUMENT: Referenced documents, reports, policies, guidelines

4. DATE: All time references: "Q1 2025", "Phase 1", "Year 1", "Months 1-6"

5. PROCESS: Named processes, workflows, phases, stages, approaches

Return ONLY entities NOT in the already-extracted list above.

Return valid JSON array:
[{{"entity_type": "TYPE", "canonical_name": "name", "properties": {{}}, "source_span": "context", "confidence": 0.85}}]

TEXT:
{text}"""

    def _run_extraction_pass(
        self,
        prompt: str,
        system_prompt: str,
        document_id: str,
        chunk_id: str,
        sentence_idx: int,
    ) -> List[ExtractedEntity]:
        """Run a single extraction pass and return entities."""
        for attempt in range(self.max_retries):
            try:
                print(f"[EntityExtractor] Using model: {self.model}")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=4000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_entities = self._parse_llm_response(response_text)
                
                entities = []
                for raw in raw_entities:
                    if not self._validate_entity(raw):
                        continue
                    
                    normalized = self._normalize_entity(raw)
                    
                    entity = ExtractedEntity(
                        id=self._generate_entity_id(
                            normalized["entity_type"],
                            normalized["canonical_name"]
                        ),
                        entity_type=normalized["entity_type"],
                        canonical_name=normalized["canonical_name"],
                        properties=normalized["properties"],
                        source_span=normalized["source_span"],
                        source_document_id=document_id,
                        source_chunk_id=chunk_id,
                        source_sentence_idx=sentence_idx,
                        confidence=normalized["confidence"],
                    )
                    entities.append(entity)
                
                return entities
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Extraction pass failed after {self.max_retries} attempts: {e}")
                    return []
        
        return []

    def _extract_from_single_chunk(
        self,
        text: str,
        document_id: str,
        chunk_id: str,
        sentence_idx: int,
        document_context: Optional[Dict] = None,
    ) -> List[ExtractedEntity]:
        """Extract entities from a single text chunk.

        Phase 3: Uses ontology-constrained prompt when use_ontology_schema=True.
        P1.4: Accepts optional document_context to inject document-type-specific rules.
        """
        # Phase 3: Use ontology-constrained extraction if available
        if self.use_ontology_schema and self.ontology_service:
            prompt = self._build_ontology_constrained_prompt(text)
            if document_context:
                prompt = self._append_document_context_rules(prompt, document_context)
            logger.debug("[OntologyExtraction] Using ontology-constrained prompt")
        else:
            prompt = self._build_entity_extraction_prompt(text, document_context=document_context)

        system_prompt = self._build_system_prompt()

        return self._run_extraction_pass(
            prompt, system_prompt, document_id, chunk_id, sentence_idx
        )

    def extract_from_text(
        self,
        text: str,
        document_id: str,
        chunk_id: str = "",
        sentence_idx: int = 0,
        document_context: Optional[Dict] = None,
    ) -> List[ExtractedEntity]:
        """
        Extract entities from text using chunked extraction to avoid output saturation.
        
        Long documents are split into ~2000 char chunks with overlap to ensure
        the LLM doesn't hit the "lazy list" effect (RLHF-induced output saturation).
        
        Args:
            text: Text to extract entities from
            document_id: ID of the source document
            chunk_id: ID of the source chunk
            sentence_idx: Index of the source sentence
            
        Returns:
            List of ExtractedEntity objects
        """
        if not text.strip():
            return []
        
        # Split into chunks to avoid output saturation
        chunks = self._chunk_text(text, chunk_size=2000, overlap=400)
        print(f"[EntityExtractor] Processing {len(chunks)} chunks from {len(text)} chars")
        
        all_entities = []
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            
            chunk_entities = self._extract_from_single_chunk(
                chunk, document_id, f"{chunk_id}_c{i}", sentence_idx,
                document_context=document_context,
            )
            print(f"[EntityExtractor] Chunk {i+1}/{len(chunks)}: {len(chunk_entities)} entities")
            all_entities.extend(chunk_entities)
        
        # Deduplicate across all chunks
        deduped = self._deduplicate_entities(all_entities)
        print(f"[EntityExtractor] Total: {len(all_entities)} raw, {len(deduped)} after dedup")
        return deduped
    
    def extract_from_chunks(
        self,
        chunks: List[Dict],
        document_id: str,
        batch_size: int = 5,
        document_filename: Optional[str] = None,
    ) -> List[ExtractedEntity]:
        """
        Extract entities from multiple chunks.

        Args:
            chunks: List of chunk dictionaries with 'content' and 'chunk_id'
            document_id: ID of the source document
            batch_size: Number of chunks to process at once
            document_filename: Optional filename for document classification (P1.4)

        Returns:
            List of ExtractedEntity objects
        """
        # P1.4: Classify document to inform extraction prompts
        doc_context: Dict = {}
        if document_filename:
            try:
                # Sample first chunk's text for fallback classification
                sample_text = ""
                for c in chunks[:1]:
                    sample_text = c.get("content", "")
                    break
                doc_type = classify_with_fallback(sample_text, filename=document_filename)
                doc_context["doc_type"] = doc_type or ""
                doc_context["filename"] = document_filename
                logger.info(f"[EntityExtractor] Document '{document_filename}' classified as: {doc_type}")
            except Exception as e:
                logger.warning(f"[EntityExtractor] Document classification failed: {e}")

        all_entities = []

        for chunk in chunks:
            content = chunk.get("content", "")
            chunk_id = chunk.get("chunk_id", "")
            start_sentence = chunk.get("start_sentence", 0)

            entities = self.extract_from_text(
                text=content,
                document_id=document_id,
                chunk_id=chunk_id,
                sentence_idx=start_sentence,
                document_context=doc_context if doc_context else None,
            )
            all_entities.extend(entities)

        return self._deduplicate_entities(all_entities)
    
    def _is_metadata_entity(self, entity_name: str) -> bool:
        """Check if entity name is actually document metadata or placeholder.
        
        Issue 1 Fix: Filter out "Document Owner" and similar metadata entities
        that pollute the knowledge graph and cause irrelevant query responses.
        """
        if not entity_name:
            return True
        
        name_lower = entity_name.lower().strip()
        
        # Exact match against blacklist
        if name_lower in METADATA_BLACKLIST:
            return True
        
        # Pattern match (e.g., "Document Owner (VP of Engineering)" or "Author: John")
        for blacklisted in METADATA_BLACKLIST:
            if name_lower.startswith(blacklisted):
                return True
            # Also check for patterns like "Owner: Name" or "Author - Name"
            if name_lower.startswith(f"{blacklisted}:") or name_lower.startswith(f"{blacklisted} -"):
                return True
        
        return False
    
    def _deduplicate_entities(
        self,
        entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Deduplicate entities by canonical name, keeping highest confidence.
        
        Also filters out metadata entities that should never be in the graph.
        P1.3: After per-(type,name) dedup, runs cross-type merge to collapse
        cases like Boeing(COMPETITOR) ↔ The Boeing Company(ORGANIZATION).
        """
        entity_map = {}
        
        for entity in entities:
            # Issue 1 Fix: Skip metadata entities
            if self._is_metadata_entity(entity.canonical_name):
                logger.debug(f"Filtered metadata entity: {entity.canonical_name}")
                continue
            
            key = (entity.entity_type, entity.canonical_name.lower())
            
            if key not in entity_map:
                entity_map[key] = entity
            elif entity.confidence > entity_map[key].confidence:
                entity_map[key] = entity

        deduped = sorted(entity_map.values(), key=lambda e: (e.entity_type, e.canonical_name))

        # P1.3: Apply cross-type duplicate merge (e.g. Boeing/The Boeing Company)
        try:
            from .duplicate_detector import DuplicateDetector
            cross_dd = DuplicateDetector(session=None, tenant_id=None)
            before = len(deduped)
            deduped = cross_dd.merge_cross_type_duplicates(deduped)
            removed = before - len(deduped)
            if removed > 0:
                logger.info(f"[CrossTypeDedup] Merged {removed} cross-type duplicates ({before} -> {len(deduped)})")
        except Exception as e:
            logger.warning(f"[CrossTypeDedup] Cross-type merge skipped: {e}")

        return deduped
    
    def _build_dynamic_prompt(self, text: str, entity_types: List[str]) -> str:
        """Build extraction prompt using a dynamic list of entity types."""
        entity_descriptions = []
        
        for type_name in entity_types:
            upper_name = type_name.upper()
            if upper_name in CORE_FOUNDATION_TYPES:
                config = CORE_FOUNDATION_TYPES[upper_name]
                desc = config["description"]
                entity_descriptions.append(f"- {upper_name}: {desc}")
            else:
                entity_descriptions.append(f"- {type_name}: Entity of type {type_name}")
        
        entity_list = "\n".join(entity_descriptions)
        entity_type_names = ", ".join(entity_types)
        
        prompt = f"""You are an expert at extracting entities from documents.

Given the following text, extract all entities of these types:
{entity_list}

For each entity, provide:
1. entity_type: One of {entity_type_names}
2. canonical_name: The standardized name of the entity
3. properties: Additional properties relevant to the entity type
4. source_span: The exact text span where this entity appears
5. confidence: Your confidence in this extraction (0.0 to 1.0)

IMPORTANT RULES:
- Extract ALL meaningful entities from the text
- Use the MOST SPECIFIC type that applies (prefer domain types over general types)
- Include people, organizations, concepts, processes, dates mentioned
- Use the exact text span where the entity appears
- Assign confidence based on how clearly the entity type is indicated

Return the result as a JSON array of objects.

TEXT:
{text}

Respond with ONLY valid JSON, no markdown code blocks or other text. Format:
[
  {{
    "entity_type": "ENTITY_TYPE",
    "canonical_name": "Entity Name",
    "properties": {{}},
    "source_span": "exact text",
    "confidence": 0.95
  }}
]"""
        return prompt

    def _extract_single_chunk_with_types(
        self,
        text: str,
        entity_types: List[str],
        document_id: str,
        chunk_id: str,
        sentence_idx: int,
    ) -> List[ExtractedEntity]:
        """Extract entities from a single chunk using custom types."""
        prompt = self._build_dynamic_prompt(text, entity_types)
        system_prompt = "You are an expert at extracting entities. Be EXHAUSTIVE. Respond only with valid JSON."
        
        valid_types = set(t.upper() for t in entity_types)
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=4000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_entities = self._parse_llm_response(response_text)
                
                entities = []
                
                for raw in raw_entities:
                    if "entity_type" not in raw:
                        continue
                    if "canonical_name" not in raw and "name" not in raw:
                        continue
                    
                    raw_type = raw["entity_type"].upper()
                    if raw_type not in valid_types:
                        for valid_type in valid_types:
                            if valid_type.upper() == raw_type:
                                raw["entity_type"] = valid_type
                                break
                        else:
                            continue
                    
                    normalized = self._normalize_entity(raw)
                    
                    entity = ExtractedEntity(
                        id=self._generate_entity_id(
                            normalized["entity_type"],
                            normalized["canonical_name"]
                        ),
                        entity_type=normalized["entity_type"],
                        canonical_name=normalized["canonical_name"],
                        properties=normalized["properties"],
                        source_span=normalized["source_span"],
                        source_document_id=document_id,
                        source_chunk_id=chunk_id,
                        source_sentence_idx=sentence_idx,
                        confidence=normalized["confidence"],
                    )
                    entities.append(entity)
                
                return entities
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Entity extraction failed after {self.max_retries} attempts: {e}")
                    return []
        
        return []

    def extract_with_types(
        self,
        text: str,
        entity_types: List[str],
        document_id: str,
        chunk_id: str = "",
        sentence_idx: int = 0,
    ) -> List[ExtractedEntity]:
        """
        Extract entities using custom types with chunking to avoid output saturation.
        
        Long documents are split into ~2000 char chunks to prevent the LLM from
        hitting the "lazy list" effect (RLHF-induced output saturation).
        """
        if not text.strip():
            return []
        
        # Split into chunks to avoid output saturation
        chunks = self._chunk_text(text, chunk_size=2000, overlap=400)
        print(f"[EntityExtractor] Processing {len(chunks)} chunks from {len(text)} chars")
        
        all_entities = []
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            
            chunk_entities = self._extract_single_chunk_with_types(
                chunk, entity_types, document_id, f"{chunk_id}_c{i}", sentence_idx
            )
            print(f"[EntityExtractor] Chunk {i+1}/{len(chunks)}: {len(chunk_entities)} entities")
            all_entities.extend(chunk_entities)
        
        # Deduplicate across all chunks
        deduped = self._deduplicate_entities(all_entities)
        print(f"[EntityExtractor] Total: {len(all_entities)} raw, {len(deduped)} after dedup")
        return deduped

    def _build_core_foundation_prompt(self, text: str) -> str:
        """Build extraction prompt using Core Foundation types (fallback)."""
        entity_descriptions = []
        for name, config in CORE_FOUNDATION_TYPES.items():
            desc = config["description"]
            entity_descriptions.append(f"- {name}: {desc}")
            if config.get("required_fields"):
                entity_descriptions.append(f"  Required: {', '.join(config['required_fields'])}")
            if config.get("optional_fields"):
                entity_descriptions.append(f"  Optional: {', '.join(config['optional_fields'])}")
        
        entity_list = "\n".join(entity_descriptions)
        entity_type_names = ", ".join(CORE_FOUNDATION_TYPES.keys())
        
        prompt = f"""You are an expert at extracting entities from documents.

Given the following text, extract all entities of these UNIVERSAL types:
{entity_list}

For each entity, provide:
1. entity_type: One of {entity_type_names}
2. canonical_name: The standardized name of the entity
3. properties: Additional properties (as listed above for each type)
4. source_span: The exact text span where this entity appears
5. confidence: Your confidence in this extraction (0.0 to 1.0)

IMPORTANT RULES:
- Extract ALL meaningful entities from the text
- Include people, organizations, concepts, processes, dates mentioned
- Use the exact text span where the entity appears
- Assign confidence based on how clearly the entity type is indicated

ROLE EXTRACTION RULES (CRITICAL FOR PERSON ENTITIES):
When extracting the 'role' property for PERSON entities:
1. ONLY use EXPLICIT role statements from the text:
   CORRECT: "Dr. Victoria Chen, CEO" → role: "CEO"
   CORRECT: "CEO: Dr. Victoria Chen" → role: "CEO"
   CORRECT: "Michael Chang serves as CFO" → role: "CFO"
   CORRECT: "Chief Engineer: Dr. Elena Rodriguez" → role: "Chief Engineer"
2. NEVER infer roles from context or associations:
   WRONG: "Thomas Wright leads UAV engineering" → role: "UAV Engineering Lead"
   CORRECT: "Thomas Wright leads UAV engineering" → NO role property
3. Use FORMAL TITLES only: CEO, CFO, COO, CTO, CISO, Chief Engineer, VP, Director, President
4. When role is NOT explicitly stated with a formal title, OMIT the role property.
   It is better to have NO role than a WRONG role.

Return the result as a JSON array of objects.

TEXT:
{text}

Respond with ONLY valid JSON, no markdown code blocks or other text. Format:
[
  {{
    "entity_type": "ENTITY_TYPE",
    "canonical_name": "Entity Name",
    "properties": {{}},
    "source_span": "exact text",
    "confidence": 0.95
  }}
]"""
        return prompt
    
    def extract_with_core_foundation(
        self,
        text: str,
        document_id: str,
        chunk_id: str = "",
        sentence_idx: int = 0,
    ) -> List[ExtractedEntity]:
        """
        Extract entities using Core Foundation types (fallback for domain-agnostic extraction).
        
        Args:
            text: Text to extract entities from
            document_id: ID of the source document
            chunk_id: ID of the source chunk
            sentence_idx: Index of the source sentence
            
        Returns:
            List of ExtractedEntity objects
        """
        if not text.strip():
            return []
        
        prompt = self._build_core_foundation_prompt(text)
        system_prompt = "You are an expert at extracting universal entities. Respond only with valid JSON."
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=4000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_entities = self._parse_llm_response(response_text)
                
                entities = []
                valid_types = set(CORE_FOUNDATION_TYPES.keys())
                
                for raw in raw_entities:
                    if "entity_type" not in raw:
                        continue
                    if "canonical_name" not in raw and "name" not in raw:
                        continue
                    if raw["entity_type"].upper() not in valid_types:
                        continue
                    
                    normalized = self._normalize_entity(raw)
                    
                    entity = ExtractedEntity(
                        id=self._generate_entity_id(
                            normalized["entity_type"],
                            normalized["canonical_name"]
                        ),
                        entity_type=normalized["entity_type"],
                        canonical_name=normalized["canonical_name"],
                        properties=normalized["properties"],
                        source_span=normalized["source_span"],
                        source_document_id=document_id,
                        source_chunk_id=chunk_id,
                        source_sentence_idx=sentence_idx,
                        confidence=normalized["confidence"],
                    )
                    entities.append(entity)
                
                print(f"[CoreFoundation] Extracted {len(entities)} entities using fallback types")
                return entities
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Core Foundation extraction failed after {self.max_retries} attempts: {e}")
                    return []
        
        return []
