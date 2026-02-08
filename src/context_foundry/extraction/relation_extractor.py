"""
Relation Extractor for Context Foundry - Multi-Domain Knowledge Extraction System.

Context Foundry is domain-agnostic and supports ANY industry or sector:
- Venture Capital & Private Equity (INVESTED_IN, BOARD_MEMBER_OF, HAS_PORTFOLIO_COMPANY)
- Healthcare (TREATS, PRESCRIBED_BY, ADMITTED_TO)
- Legal (PARTY_TO, GOVERNED_BY, SUPERSEDES)
- Human Resources (WORKS_AT, REPORTS_TO, HAS_COMPENSATION)
- Finance & Banking (HOLDS_ACCOUNT, TRANSACTED_WITH, REGULATED_BY)
- Technology & IT Operations (DEPENDS_ON, DEPLOYED_TO, MONITORS)
- Real Estate (LEASED_BY, LOCATED_IN, MANAGED_BY)
- And any other domain with entities and relationships

Uses LLM-powered relation extraction with confidence scoring based on active schema.
Uses Replit AI Integrations for OpenAI access (no API key required, billed to credits).
"""
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import logging

from openai import OpenAI

from ..config.domain_schema import get_schema_loader, DomainSchemaLoader

logger = logging.getLogger(__name__)

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")

# Canonical supplier relationship type mappings
CANONICAL_SUPPLIER_TYPES = {
    'SUPPLIES_TO': 'SUPPLIES_TO',
    'SUPPLIES': 'SUPPLIES_TO',
    'PROVIDES_TO': 'SUPPLIES_TO',
    'DELIVERS_TO': 'SUPPLIES_TO',
    'VENDOR_FOR': 'SUPPLIES_TO',
    'VENDOR_OF': 'SUPPLIES_TO',
    'SUPPLIER_OF': 'SUPPLIES_TO',
    'SUPPLIER_FOR': 'SUPPLIES_TO',
    'CONTRACTED_TO_SUPPLY': 'SUPPLIES_TO',
}
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

EMPLOYMENT_POSITIVE_PATTERN = re.compile(
    r"\b(works?\s+(at|for)|employee|employed|serves as|is (the )?(ceo|cfo|cto|coo|president|director|manager|officer)|appointed|joined)\b",
    re.IGNORECASE,
)
EMPLOYMENT_NEGATIVE_PATTERN = re.compile(
    r"\b(met with|meeting|discussed|collaborat|project with|representative|committee|steering|report)\b",
    re.IGNORECASE,
)
ORG_HINT_PATTERN = re.compile(
    r"\b(inc|corp|corporation|company|co|llc|ltd|plc|gmbh|ag|group|holdings|industries|systems|technologies|healthineers)\b",
    re.IGNORECASE,
)


@dataclass
class ExtractedRelation:
    """Represents a relationship extracted from text."""
    id: str
    relation_type: str
    source_name: str
    target_name: str
    source_span: str
    source_document_id: str
    source_chunk_id: str
    confidence: float
    properties: Dict = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "relation_type": self.relation_type,
            "source_name": self.source_name,
            "target_name": self.target_name,
            "source_span": self.source_span,
            "source_document_id": self.source_document_id,
            "source_chunk_id": self.source_chunk_id,
            "confidence": self.confidence,
            "properties": self.properties,
            "extracted_at": self.extracted_at.isoformat(),
        }


class RelationExtractor:
    """
    LLM-powered relation extractor that works with any domain schema.
    
    Loads relationship types dynamically from the active domain schema configuration.
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,  # Deterministic for consistent extraction
        max_retries: int = 3,
        schema_loader: Optional[DomainSchemaLoader] = None,
    ):
        """
        Initialize the relation extractor.
        
        Args:
            model: OpenAI model to use
            temperature: Temperature for generation (0.0 = deterministic)
            max_retries: Maximum retries on API errors
            schema_loader: Optional schema loader instance (uses singleton if not provided)
        """
        self.client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL,
        )
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self._schema_loader = schema_loader
    
    @property
    def schema_loader(self) -> DomainSchemaLoader:
        """Get schema loader (lazy initialization)."""
        if self._schema_loader is None:
            self._schema_loader = get_schema_loader()
        return self._schema_loader
    
    def get_valid_relation_types(self) -> Set[str]:
        """Get set of valid relationship type names from schema."""
        return self.schema_loader.get_valid_relationship_types()
    
    def _build_relation_extraction_prompt(self, text: str, entities_str: str) -> str:
        """Build relation extraction prompt with anti-contamination guardrails."""
        
        prompt = f"""Extract all relationships between the entities in this text.

Use relationship types that best describe each connection.
Both source and target must be from the known entities list.

CRITICAL RULES:
1. Co-occurrence is NOT employment:
   - If a person and organization are only mentioned together in a meeting/report/project context, DO NOT create WORKS_AT/WORKS_FOR.
   - Only create WORKS_AT/WORKS_FOR when employment is explicit ("works at", "employee of", "serves as CFO of", etc.).
2. Prioritize supply-chain/commercial relationships:
   - For supplier/vendor/customer/procurement language, extract supply-chain types (SUPPLIES_TO, SUPPLIER_OF, CUSTOMER_OF, PROCURES_FROM, VENDOR_OF).
3. Validate entity typing in relationships:
   - If a major company-like name appears as PERSON, do not create relationship from that bad typing.

KNOWN ENTITIES:
{entities_str}

Return JSON array only (no markdown):
[{{"source_name": "...", "relation_type": "...", "target_name": "...", "source_span": "...", "confidence": 0.9}}]

TEXT:
{text}"""
        return prompt
    
    def _build_system_prompt(self) -> str:
        """Build dynamic system prompt from active schema."""
        schema = self.schema_loader.schema
        return f"You are an expert at extracting relationships between {schema.domain} entities. Respond only with valid JSON."
    
    def _generate_relation_id(
        self, 
        relation_type: str, 
        source_name: str, 
        target_name: str
    ) -> str:
        """Generate deterministic relation ID."""
        combined = f"{relation_type}:{source_name.lower()}:{target_name.lower()}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _format_entities_for_prompt(self, entities: List[Dict]) -> str:
        """Format entity list for the prompt."""
        lines = []
        for entity in entities:
            entity_type = entity.get("entity_type", "UNKNOWN")
            name = entity.get("canonical_name", entity.get("name", "Unknown"))
            lines.append(f"- {entity_type}: {name}")
        return "\n".join(lines)
    
    def _parse_llm_response(self, response_text: str) -> List[Dict]:
        """Parse LLM response into structured relations."""
        text = response_text.strip()
        if text.startswith("```"):
            text = re.sub(r"```json?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        
        try:
            relations = json.loads(text)
            if isinstance(relations, list):
                return relations
            return []
        except json.JSONDecodeError:
            try:
                match = re.search(r'\[.*\]', text, re.DOTALL)
                if match:
                    return json.loads(match.group())
            except:
                pass
            return []
    
    def _strip_type_prefix(self, name: str) -> str:
        """Remove entity type prefix like 'DOCUMENT: ' from a name."""
        prefixes = ['PERSON:', 'ORGANIZATION:', 'DOCUMENT:', 'LOCATION:', 
                    'EVENT:', 'CONCEPT:', 'PROCESS:', 'DATE:',
                    'SERVICE:', 'COMPONENT:', 'TEAM:', 'DATABASE:', 'INCIDENT:']
        name = name.strip()
        for prefix in prefixes:
            if name.upper().startswith(prefix):
                return name[len(prefix):].strip()
        return name
    
    def _fuzzy_match(self, name: str, entity_names_lower: set) -> bool:
        """Check if name matches any entity (exact or as substring)."""
        name_lower = name.lower().strip()
        if name_lower in entity_names_lower:
            return True
        for entity_name in entity_names_lower:
            if name_lower in entity_name or entity_name in name_lower:
                return True
        return False

    def _looks_like_organization_name(self, name: str) -> bool:
        """Heuristic check for organization-like names."""
        return bool(ORG_HINT_PATTERN.search(name or ""))

    def _has_employment_signal(self, relation: Dict) -> bool:
        """Require explicit employment evidence to avoid co-occurrence contamination."""
        evidence = (relation.get("source_span") or relation.get("evidence") or "").strip()
        if not evidence:
            return float(relation.get("confidence", 0.0)) >= 0.85
        if EMPLOYMENT_NEGATIVE_PATTERN.search(evidence):
            return False
        return bool(EMPLOYMENT_POSITIVE_PATTERN.search(evidence))
    
    def _validate_relation(self, relation: Dict, entity_names: set, entities: List[Dict] = None) -> bool:
        """Validate extracted relation has required fields and valid references.

        Note: We allow any relationship type (not just schema-defined ones) to support
        domain-agnostic extraction where the LLM creates appropriate types.

        Args:
            relation: The extracted relation to validate
            entity_names: Set of known entity names
            entities: Full entity list with types (optional, for type validation)
        """
        required = ["relation_type", "source_name", "target_name"]
        for fld in required:
            if fld not in relation:
                return False

        source_name = self._strip_type_prefix(relation["source_name"])
        target_name = self._strip_type_prefix(relation["target_name"])
        entity_names_lower = {n.lower() for n in entity_names}

        source_found = self._fuzzy_match(source_name, entity_names_lower)
        target_found = self._fuzzy_match(target_name, entity_names_lower)

        if not (source_found and target_found):
            return False

        # Entity type validation: Check for known bad patterns
        if entities:
            entity_map = {}
            for entity in entities:
                name = entity.get("canonical_name", entity.get("name", "")).lower()
                entity_type = entity.get("entity_type", "UNKNOWN")
                entity_map[name] = entity_type

            # Check if source/target entity types are appropriate for the relationship
            rel_type = relation["relation_type"]
            source_type = entity_map.get(source_name.lower(), "UNKNOWN")
            target_type = entity_map.get(target_name.lower(), "UNKNOWN")

            # Known company names that should NEVER be PERSON
            known_organizations = ["boeing", "siemens", "nexus industries", "nel hydrogen",
                                  "airbus", "lockheed", "raytheon", "northrop grumman"]

            # Validate: Major companies should be ORGANIZATION, not PERSON
            for org_name in known_organizations:
                if org_name in source_name.lower() and source_type == "PERSON":
                    logger.warning(f"[TypeValidation] Rejecting: {source_name} typed as PERSON (should be ORGANIZATION)")
                    return False
                if org_name in target_name.lower() and target_type == "PERSON":
                    logger.warning(f"[TypeValidation] Rejecting: {target_name} typed as PERSON (should be ORGANIZATION)")
                    return False

            if self._looks_like_organization_name(source_name) and source_type == "PERSON":
                logger.debug(f"[TypeValidation] Rejecting relation with org-like source typed PERSON: {source_name}")
                return False
            if self._looks_like_organization_name(target_name) and target_type == "PERSON":
                logger.debug(f"[TypeValidation] Rejecting relation with org-like target typed PERSON: {target_name}")
                return False

            # Validate WORKS_AT: source must be PERSON, target must be ORGANIZATION
            rel_type_upper = rel_type.upper()
            if rel_type_upper in {"WORKS_AT", "WORKS_FOR", "EMPLOYED_BY"}:
                if not self._has_employment_signal(relation):
                    logger.debug(f"[Guardrail] Rejecting employment relation without explicit evidence: {source_name} -> {target_name}")
                    return False
                if source_type != "PERSON" or target_type not in {"ORGANIZATION", "BUSINESS_UNIT", "FACILITY", "LOCATION"}:
                    logger.debug(f"[TypeValidation] Rejecting {rel_type_upper}: {source_name}({source_type}) → {target_name}({target_type})")
                    return False

            # Validate supply-chain relationships: both must be ORGANIZATION
            supply_chain_types = ["SUPPLIES", "CUSTOMER_OF", "PROCURES_FROM", "VENDOR_OF", "SUPPLIES_TO"]
            if rel_type_upper in supply_chain_types:
                allowed_source_types = {"ORGANIZATION", "SUPPLIER", "CUSTOMER", "PARTNER"}
                allowed_target_types = {"ORGANIZATION", "SUPPLIER", "CUSTOMER", "PARTNER"}
                if source_type not in allowed_source_types or target_type not in allowed_target_types:
                    logger.debug(f"[TypeValidation] Rejecting {rel_type_upper}: {source_name}({source_type}) → {target_name}({target_type})")
                    return False

        return True
    
    def _normalize_relation(self, relation: Dict) -> Dict:
        """Normalize relation fields with open capture canonical mapping."""
        from .canonical_mapper import get_canonical_mapper
        
        relation["source_name"] = self._strip_type_prefix(relation["source_name"])
        relation["target_name"] = self._strip_type_prefix(relation["target_name"])
        
        raw_type = relation["relation_type"]
        relation["raw_relationship_type"] = raw_type
        
        mapper = get_canonical_mapper()
        canonical_type, is_mapped = mapper.map_relationship_type(raw_type)
        relation["relation_type"] = canonical_type
        relation["is_mapped"] = is_mapped
        
        if not is_mapped:
            logger.debug(f"[OpenCapture] Unmapped relationship type: '{raw_type}' → '{canonical_type}'")
        
        if "confidence" not in relation:
            relation["confidence"] = 0.75
        else:
            relation["confidence"] = min(1.0, max(0.0, float(relation["confidence"])))
        
        if "source_span" not in relation:
            relation["source_span"] = f"{relation['source_name']} {relation['relation_type']} {relation['target_name']}"
        
        return relation
    
    def extract_from_text(
        self,
        text: str,
        entities: List[Dict],
        document_id: str,
        chunk_id: str = "",
        document_type: str = None,
    ) -> List[ExtractedRelation]:
        """
        Extract relations from text using LLM.
        
        Args:
            text: Text to extract relations from
            entities: List of known entities (with 'canonical_name' and 'entity_type')
            document_id: ID of the source document
            chunk_id: ID of the source chunk
            document_type: Type of document (resume, incident_report, etc.)
            
        Returns:
            List of ExtractedRelation objects
        """
        if not text.strip() or not entities:
            print(f"[RelationExtractor] Skipping: text={bool(text.strip())}, entities={len(entities) if entities else 0}")
            return []
        
        print(f"[RelationExtractor] Extracting relations from {len(entities)} entities")
        
        entity_names = {
            e.get("canonical_name", e.get("name", "")) 
            for e in entities 
            if e.get("canonical_name") or e.get("name")
        }
        
        entities_str = self._format_entities_for_prompt(entities)
        prompt = self._build_relation_extraction_prompt(text, entities_str)
        system_prompt = self._build_system_prompt()
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=2000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_relations = self._parse_llm_response(response_text)
                
                print(f"[RelationExtractor] LLM returned {len(raw_relations)} raw relations")
                for raw in raw_relations:
                    print(f"[RelationExtractor] Raw: {raw.get('source_name', '?')} -{raw.get('relation_type', '?')}-> {raw.get('target_name', '?')}")
                
                relations = []
                valid_types = self.get_valid_relation_types()
                for raw in raw_relations:
                    if not self._validate_relation(raw, entity_names, entities):
                        rel_type = raw.get("relation_type", "UNKNOWN").upper()
                        source = raw.get("source_name", "?")
                        target = raw.get("target_name", "?")
                        source_found = source.lower() in {n.lower() for n in entity_names}
                        target_found = target.lower() in {n.lower() for n in entity_names}
                        type_valid = rel_type in valid_types
                        print(f"[RelationExtractor] Skipped: {source} -{rel_type}-> {target} (type_valid={type_valid}, source_found={source_found}, target_found={target_found})")
                        continue
                    
                    normalized = self._normalize_relation(raw)
                    
                    relation = ExtractedRelation(
                        id=self._generate_relation_id(
                            normalized["relation_type"],
                            normalized["source_name"],
                            normalized["target_name"]
                        ),
                        relation_type=normalized["relation_type"],
                        source_name=normalized["source_name"],
                        target_name=normalized["target_name"],
                        source_span=normalized["source_span"],
                        source_document_id=document_id,
                        source_chunk_id=chunk_id,
                        confidence=normalized["confidence"],
                    )
                    relations.append(relation)
                
                return relations
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Relation extraction failed after {self.max_retries} attempts: {e}")
                    return []
        
        return []
    
    def extract_from_chunks(
        self,
        chunks: List[Dict],
        entities: List[Dict],
        document_id: str,
    ) -> List[ExtractedRelation]:
        """
        Extract relations from multiple chunks.
        
        Args:
            chunks: List of chunk dictionaries with 'content' and 'chunk_id'
            entities: List of known entities
            document_id: ID of the source document
            
        Returns:
            List of ExtractedRelation objects
        """
        all_relations = []
        
        for chunk in chunks:
            content = chunk.get("content", "")
            chunk_id = chunk.get("chunk_id", "")
            
            relations = self.extract_from_text(
                text=content,
                entities=entities,
                document_id=document_id,
                chunk_id=chunk_id,
            )
            all_relations.extend(relations)
        
        return self._deduplicate_relations(all_relations)
    
    def _deduplicate_relations(
        self,
        relations: List[ExtractedRelation]
    ) -> List[ExtractedRelation]:
        """Deduplicate relations, keeping highest confidence."""
        relation_map = {}
        
        for relation in relations:
            key = (
                relation.relation_type,
                relation.source_name.lower(),
                relation.target_name.lower()
            )
            
            if key not in relation_map:
                relation_map[key] = relation
            elif relation.confidence > relation_map[key].confidence:
                relation_map[key] = relation
        
        return list(relation_map.values())
    
    def extract_with_ontology(
        self,
        text: str,
        entities: List[Dict],
        document_id: str,
        document_type: str,
        relationship_types: List[Dict],
        chunk_id: str = "",
    ) -> List[ExtractedRelation]:
        """
        Extract relations using ontology-guided prompt.
        
        Args:
            text: Text to extract relations from
            entities: List of known entities
            document_id: Document ID
            document_type: Type of document (resume, incident_report, etc.)
            relationship_types: List of relationship type definitions with name/definition
            chunk_id: Chunk ID
            
        Returns:
            List of ExtractedRelation objects
        """
        if not text.strip() or not entities:
            return []
        
        entity_names = {
            e.get("canonical_name", e.get("name", ""))
            for e in entities
            if e.get("canonical_name") or e.get("name")
        }
        
        entities_str = self._format_entities_for_prompt(entities)
        
        rel_descriptions = []
        for rt in relationship_types:
            name = rt.get("name", "UNKNOWN")
            definition = rt.get("definition", f"{name} relationship")
            source_types = rt.get("source_types", [])
            target_types = rt.get("target_types", [])
            
            sources = ", ".join(source_types) if source_types else "any"
            targets = ", ".join(target_types) if target_types else "any"
            rel_descriptions.append(f"- {name}: {definition} (from {sources} to {targets})")
        
        rel_list = "\n".join(rel_descriptions) if rel_descriptions else "No predefined types - extract what you find"
        
        prompt = f"""You are an expert at extracting relationships between entities from {document_type} documents.

Given the following text and the list of known entities, extract all relationships.

RECOMMENDED RELATIONSHIP TYPES for {document_type.upper()} documents:
{rel_list}

Use these types when they fit. If you find a relationship not covered by these types,
create a descriptive relationship type in UPPERCASE_UNDERSCORE format.

KNOWN ENTITIES:
{entities_str}

For each relationship, provide:
1. relation_type: A relationship type (preferably from the recommended list)
2. source_name: The name of the source entity (must be from KNOWN ENTITIES)
3. target_name: The name of the target entity (must be from KNOWN ENTITIES)
4. source_span: The exact text that indicates this relationship
5. confidence: Your confidence in this extraction (0.0 to 1.0)

CRITICAL EXTRACTION RULES:

1. CO-OCCURRENCE IS NOT EMPLOYMENT
   ❌ WRONG: If a person is mentioned in a meeting, report, or project involving an organization → DO NOT create WORKS_AT
   ❌ WRONG: If a person and organization appear in the same sentence → DO NOT assume WORKS_AT
   ✅ CORRECT: Only create WORKS_AT when the text explicitly states employment (e.g., "John works at Acme", "Sarah is an employee of Corp")

   Examples:
   - "Boeing representatives met with Nexus Industries" → NO WORKS_AT relationship (just a meeting)
   - "Jennifer Walsh discussed the project with Siemens" → NO WORKS_AT (just collaboration)
   - "Michael Chang serves as CFO of Nexus Industries" → YES, create HOLDS_POSITION + WORKS_AT

2. PRIORITIZE SUPPLY-CHAIN RELATIONSHIPS
   When organizations interact commercially (buying, selling, supplying, procurement), use supply-chain relationship types:
   - SUPPLIES: "Siemens supplies turbine components to Nexus Industries"
   - CUSTOMER_OF: "Nexus Industries is a customer of Boeing"
   - PROCURES_FROM: "The company procures materials from Vendor Corp"
   - VENDOR_OF: "Supplier Inc. is a vendor of parts to Manufacturing Co"

   ✅ Look for: supplier, vendor, customer, purchases from, procures, provides to, delivers to, supplies
   ❌ Don't miss commercial relationships just because they lack HR context

3. VALIDATE ENTITY TYPES
   - Major companies (Boeing, Siemens, Nexus Industries, etc.) must be ORGANIZATION, never PERSON
   - If entity type seems wrong, skip that relationship rather than create incorrect data
   - People are PERSON, companies are ORGANIZATION - never mix these up

4. SUPPLIER PROFILE DIRECTIONALITY
   Supplier profiles describe relationships FROM the supplier's perspective. Extract these as supply-chain edges:

   ✅ CORRECT patterns:
   - "Supplier Name: X" in organizational context → SUPPLIES(source=X, target=org/project)
   - "X supplies to Y" → SUPPLIES(source=X, target=Y)
   - "Y procures from X" → SUPPLIES(source=X, target=Y) [same direction as "X supplies to Y"]
   - "Strategic Supplier: X" for project/org Y → SUPPLIES(source=X, target=Y)
   - Table with "Supplier Name | Contract Value" → SUPPLIES from supplier to customer

   Examples:
   - Document titled "Nel Hydrogen - Supplier Profile" with "Components: PEM Electrolyzers" for Nexus
     → SUPPLIES(source="Nel Hydrogen", target="Nexus Industries")
   - "First Solar - Supplier Type: Strategic Solar Component Provider"
     → SUPPLIES(source="First Solar", target="Nexus Industries")
   - "Nexus Industries procures solar panels from First Solar"
     → SUPPLIES(source="First Solar", target="Nexus Industries") [NOT procures_from]

   ❌ DON'T create generic OWNS/MEMBER_OF when supplier profile context is clear
   ❌ DON'T reverse the direction: supplier is source, customer is target

EXTRACTION GUIDELINES:
- Extract ALL relationships mentioned in the text
- Both source and target entities must be from the KNOWN ENTITIES list
- Use recommended relationship types when they fit the document type
- Assign lower confidence (0.5-0.7) if the relationship is implied
- Assign higher confidence (0.8-1.0) if the relationship is explicitly stated

TEXT:
{text}

Respond with ONLY valid JSON array:
[
  {{
    "relation_type": "RELATION_TYPE",
    "source_name": "Source Entity",
    "target_name": "Target Entity",
    "source_span": "exact text",
    "confidence": 0.95
  }}
]"""

        system_prompt = f"You are an expert at extracting relationships from {document_type} documents. Respond only with valid JSON."
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=8000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_relations = self._parse_llm_response(response_text)
                
                print(f"[RelationExtractor] Ontology-guided: {len(raw_relations)} raw relations for {document_type}")

                relations = []
                for raw in raw_relations:
                    if not self._validate_relation(raw, entity_names, entities):
                        continue
                    
                    normalized = self._normalize_relation(raw)
                    
                    relation = ExtractedRelation(
                        id=self._generate_relation_id(
                            normalized["relation_type"],
                            normalized["source_name"],
                            normalized["target_name"]
                        ),
                        relation_type=normalized["relation_type"],
                        source_name=normalized["source_name"],
                        target_name=normalized["target_name"],
                        source_span=normalized["source_span"],
                        source_document_id=document_id,
                        source_chunk_id=chunk_id,
                        confidence=normalized["confidence"],
                    )
                    relations.append(relation)
                
                return relations
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Ontology-guided relation extraction failed: {e}")
                    return []
        
        return []
