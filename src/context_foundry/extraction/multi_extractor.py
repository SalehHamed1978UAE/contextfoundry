"""
Multi-Model Extraction Pipeline for Context Foundry

This module orchestrates redundant extraction passes using multiple LLMs,
enabling consensus-based entity and relationship extraction.

Phase 1 Implementation:
- GPT-4o-mini (primary)
- Claude Sonnet 4 (secondary)

Guardrail: Extraction outputs are stored as raw data; no KG writes yet.
"""

import json
import os
import hashlib
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from ..ontology.schema import (
    EntityType,
    RelationshipType,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionOutput,
)
from ..ontology.validator import OntologyValidator, normalize_entity_type, normalize_relationship_type


EXTRACTION_SYSTEM_PROMPT = """You are a knowledge extraction system. Your task is to extract structured entities and relationships from the provided document.

## Entity Types (use EXACTLY these type names):
- PERSON: People mentioned (name, title, role, department)
- ORGANIZATION: Companies, corporations, groups (name, type, industry)
- BUSINESS_UNIT: Divisions, departments, teams within an organization (name, focus areas)
- PROJECT: Initiatives, programs, campaigns (name, budget, timeline, status)
- PRODUCT: Physical or digital products (name, description, category)
- SERVICE: Services offered (name, description)
- CUSTOMER: Customer organizations (name, industry, region)
- SUPPLIER: Vendor/supplier organizations (name, capability, risk level)
- PARTNER: Partner organizations (name, partnership type)
- FINANCIAL_METRIC: Financial figures (metric name, value, period, type: CURRENCY/PERCENTAGE/COUNT)
- LOCATION: Places, cities, regions (name, city, country)
- FACILITY: Physical facilities, plants, offices (name, location, type)
- POLICY: Policies, regulations, guidelines (name, policy ID, category)
- TECHNOLOGY: Technologies, platforms, tools (name, description)

## Relationship Types (use EXACTLY these type names):
- OWNS: Entity owns another entity (Org→Project, BU→Project)
- LEADS: Person leads an organization/project (Person→Org/BU/Project)
- MANAGES: Person manages a team/project (Person→BU/Project)
- WORKS_FOR: Person is employed by organization (Person→Organization/Business Unit)
- WORKS_AT: Person works at a location/facility (Person→Organization/Location/Facility)
- REPORTS_TO: Person reports to another person (Person→Person)
- CUSTOMER_OF: Entity buys from / is customer of organization (Customer/Org→Organization)
- SUPPLIER_OF: Entity supplies/provides/vendors to another organization (Supplier/Org→Organization)
- PARTNER_OF: Organizations are partners (Organization→Organization)
- FUNDED_BY: Project is funded by organization (Project→Organization)
- LOCATED_AT: Entity is located at a place (Org/Facility→Location)
- FOCUSES_ON: Business unit focuses on domain (BU→Concept)
- PRODUCES: Entity produces a product (Org/BU→Product)
- USES: Entity uses technology (Project/Org→Technology)
- PART_OF: Entity is part of another (BU→Organization, Person→BU)
- HOLDS_POSITION: Person holds a specific role (Person→Organization with role property)

## Output Format (JSON):
{
  "entities": [
    {
      "name": "Sarah Chen",
      "entity_type": "PERSON",
      "properties": {"title": "CEO", "role": "Chief Executive Officer"},
      "confidence": 0.95,
      "source_excerpt": "Sarah Chen, CEO of Manus Orion Group"
    }
  ],
  "relationships": [
    {
      "source_entity": "Sarah Chen",
      "source_type": "PERSON",
      "relationship_type": "LEADS",
      "target_entity": "Manus Orion Group",
      "target_type": "ORGANIZATION",
      "confidence": 0.9,
      "evidence": "Sarah Chen leads the executive team"
    }
  ]
}

## Guidelines:
1. Extract ALL entities and relationships mentioned in the document
2. Use exact entity type names from the list above
3. Include source excerpts/evidence for traceability
4. Assign confidence scores (0.0-1.0) based on explicitness
5. For financial values, include the metric name, value, and period
6. For people, always try to capture their role/title
7. Create HOLDS_POSITION relationships for executive roles
8. Be thorough, but do not invent unsupported relationships

## Critical Guardrails (must follow):
1. Co-occurrence is NOT employment:
   - If a person and organization are merely mentioned together in meetings/reports/projects, do NOT create WORKS_FOR/WORKS_AT.
   - Only create employment relationships when text explicitly indicates employment/title at organization.
2. Prioritize supply-chain/commercial relationships:
   - Use SUPPLIER_OF/CUSTOMER_OF for supplier, vendor, procurement, buying, delivering, or customer statements.
3. Validate entity typing:
   - Major companies and company-like names are ORGANIZATION, not PERSON.
   - Do not assign PERSON to entities like "Boeing", "Siemens", "Lockheed Martin", "Nexus Industries".
4. Example patterns:
   - "Boeing representatives met with Nexus Industries" -> NO WORKS_FOR
   - "Nexus Industries is a customer of Boeing" -> CUSTOMER_OF
   - "Siemens supplies turbine components to Nexus Industries" -> SUPPLIER_OF
   - "Michael Chang serves as CFO of Nexus Industries" -> HOLDS_POSITION + WORKS_FOR
"""


@dataclass
class DocumentInfo:
    """Information about a document to be extracted."""
    document_id: str
    path: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_file(file_path: str) -> "DocumentInfo":
        """Create DocumentInfo from a file path."""
        path = Path(file_path)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        doc_id = hashlib.md5(file_path.encode()).hexdigest()[:12]
        
        return DocumentInfo(
            document_id=doc_id,
            path=str(path),
            content=content,
            metadata={
                "filename": path.name,
                "extension": path.suffix,
                "size_bytes": len(content),
            }
        )


class BaseExtractor(ABC):
    """Abstract base class for LLM-based extractors."""
    
    def __init__(self, model_name: str, validator: Optional[OntologyValidator] = None):
        self.model_name = model_name
        self.validator = validator or OntologyValidator(strict=False)
    
    @abstractmethod
    def extract(self, document: DocumentInfo) -> ExtractionOutput:
        """Extract entities and relationships from a document."""
        pass
    
    def _attempt_partial_parse(self, response_text: str) -> Tuple[List[ExtractedEntity], List[ExtractedRelationship]]:
        """Attempt to parse partial/incomplete JSON responses."""
        import re
        
        entities = []
        relationships = []
        
        entity_pattern = r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"entity_type"\s*:\s*"([^"]+)"[^}]*\}'
        for match in re.finditer(entity_pattern, response_text, re.DOTALL):
            name = match.group(1)
            entity_type_str = match.group(2)
            
            normalized_type = normalize_entity_type(entity_type_str)
            if normalized_type is None:
                normalized_type = EntityType.CONCEPT
            
            entities.append(ExtractedEntity(
                name=name,
                entity_type=normalized_type,
                properties={},
                confidence=0.5,
                source_document="",
                source_excerpt="",
                aliases=[],
            ))
        
        rel_pattern = r'\{\s*"source_entity"\s*:\s*"([^"]+)"[^}]*"relationship_type"\s*:\s*"([^"]+)"[^}]*"target_entity"\s*:\s*"([^"]+)"'
        for match in re.finditer(rel_pattern, response_text, re.DOTALL):
            source = match.group(1)
            rel_type_str = match.group(2)
            target = match.group(3)
            
            normalized_rel = normalize_relationship_type(rel_type_str)
            if normalized_rel is None:
                normalized_rel = RelationshipType.RELATED_TO
            
            relationships.append(ExtractedRelationship(
                source_entity=source,
                source_type=EntityType.CONCEPT,
                relationship_type=normalized_rel,
                target_entity=target,
                target_type=EntityType.CONCEPT,
                properties={},
                confidence=0.5,
                source_document="",
                evidence="",
            ))
        
        return entities, relationships

    _ORG_HINT_PATTERN = re.compile(
        r"\b(inc|corp|corporation|company|co|llc|ltd|plc|gmbh|ag|group|holdings|industries|systems|technologies|healthineers)\b",
        re.IGNORECASE,
    )
    _EMPLOYMENT_POSITIVE_PATTERN = re.compile(
        r"\b(works?\s+(at|for)|employee|employed|serves as|is (the )?(ceo|cfo|cto|coo|president|director|manager|officer)|appointed|joined)\b",
        re.IGNORECASE,
    )
    _EMPLOYMENT_NEGATIVE_PATTERN = re.compile(
        r"\b(met with|meeting|discussed|collaborat|project with|representative|committee|steering|report)\b",
        re.IGNORECASE,
    )

    def _looks_like_organization(self, name: str) -> bool:
        """Heuristic check for company/organization-like names."""
        normalized = name.strip().lower()
        if not normalized:
            return False
        return bool(self._ORG_HINT_PATTERN.search(normalized))

    def _coerce_entity_type(self, name: str, entity_type: EntityType) -> EntityType:
        """Apply guardrail corrections for common entity typing mistakes."""
        if entity_type == EntityType.PERSON and self._looks_like_organization(name):
            return EntityType.ORGANIZATION
        return entity_type

    def _has_employment_signal(self, evidence: str) -> bool:
        """Require explicit employment evidence for WORKS_* relationships."""
        text = (evidence or "").strip()
        if not text:
            return False
        if self._EMPLOYMENT_NEGATIVE_PATTERN.search(text):
            return False
        return bool(self._EMPLOYMENT_POSITIVE_PATTERN.search(text))
    
    def _build_prompt(self, document: DocumentInfo) -> str:
        """Build the extraction prompt for a document."""
        max_content_chars = 15000
        content = document.content
        if len(content) > max_content_chars:
            content = content[:max_content_chars] + "\n\n[Document truncated for extraction...]"
        
        return f"""## Document: {document.metadata.get('filename', document.document_id)}

{content}

---

Extract all entities and relationships from the document above. Return valid JSON only."""
    
    def _parse_response(self, response_text: str, document: DocumentInfo) -> ExtractionOutput:
        """Parse LLM response into ExtractionOutput."""
        entities = []
        relationships = []
        used_partial_parse = False
        entity_type_coercions = 0
        filtered_relationships = 0
        
        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            data = json.loads(response_text)
            entity_type_map: Dict[str, EntityType] = {}
            
            for e in data.get("entities", []):
                entity_type_str = e.get("entity_type", "")
                normalized_type = normalize_entity_type(entity_type_str)
                
                if normalized_type is None:
                    normalized_type = EntityType.CONCEPT

                coerced_type = self._coerce_entity_type(e.get("name", ""), normalized_type)
                if coerced_type != normalized_type:
                    entity_type_coercions += 1
                normalized_type = coerced_type
                entity_type_map[e.get("name", "").lower().strip()] = normalized_type
                
                entities.append(ExtractedEntity(
                    name=e.get("name", ""),
                    entity_type=normalized_type,
                    properties=e.get("properties", {}),
                    confidence=float(e.get("confidence", 0.5)),
                    source_document=document.path,
                    source_excerpt=e.get("source_excerpt", ""),
                    aliases=e.get("aliases", []),
                ))
            
            for r in data.get("relationships", []):
                rel_type_str = r.get("relationship_type", "")
                normalized_rel = normalize_relationship_type(rel_type_str)
                
                if normalized_rel is None:
                    normalized_rel = RelationshipType.RELATED_TO
                
                source_type_str = r.get("source_type", "CONCEPT")
                target_type_str = r.get("target_type", "CONCEPT")
                
                source_type = normalize_entity_type(source_type_str) or EntityType.CONCEPT
                target_type = normalize_entity_type(target_type_str) or EntityType.CONCEPT

                source_name = r.get("source_entity", "")
                target_name = r.get("target_entity", "")

                source_type = entity_type_map.get(source_name.lower().strip(), source_type)
                target_type = entity_type_map.get(target_name.lower().strip(), target_type)

                # Co-occurrence guardrail: require explicit employment language.
                if normalized_rel in {RelationshipType.WORKS_FOR, RelationshipType.WORKS_AT}:
                    evidence = r.get("evidence", "")
                    if not self._has_employment_signal(evidence):
                        filtered_relationships += 1
                        continue

                # Type validation guardrails for high-risk relationship classes.
                if normalized_rel == RelationshipType.WORKS_FOR:
                    if source_type != EntityType.PERSON:
                        filtered_relationships += 1
                        continue
                    if target_type not in {EntityType.ORGANIZATION, EntityType.BUSINESS_UNIT}:
                        filtered_relationships += 1
                        continue

                if normalized_rel in {RelationshipType.CUSTOMER_OF, RelationshipType.SUPPLIER_OF}:
                    if source_type == EntityType.PERSON or target_type == EntityType.PERSON:
                        filtered_relationships += 1
                        continue
                
                relationships.append(ExtractedRelationship(
                    source_entity=source_name,
                    source_type=source_type,
                    relationship_type=normalized_rel,
                    target_entity=target_name,
                    target_type=target_type,
                    properties=r.get("properties", {}),
                    confidence=float(r.get("confidence", 0.5)),
                    source_document=document.path,
                    evidence=r.get("evidence", ""),
                ))
                
        except json.JSONDecodeError as e:
            print(f"[MultiExtractor] JSON parse error: {e}")
            entities, relationships = self._attempt_partial_parse(response_text)
            used_partial_parse = True
            print(f"[MultiExtractor] Partial parse recovered: {len(entities)} entities, {len(relationships)} relationships")
        except Exception as e:
            print(f"[MultiExtractor] Parse error: {e}")
        
        return ExtractionOutput(
            document_id=document.document_id,
            document_path=document.path,
            model_name=self.model_name,
            extracted_at=datetime.utcnow(),
            entities=entities,
            relationships=relationships,
            metadata={
                "filename": document.metadata.get("filename", ""),
                "raw_entity_count": len(entities),
                "raw_relationship_count": len(relationships),
                "used_partial_parse": used_partial_parse,
                "truncated": len(document.content) > 15000,
                "entity_type_coercions": entity_type_coercions,
                "filtered_relationships": filtered_relationships,
            }
        )


class GPT4oMiniExtractor(BaseExtractor):
    """Extractor using OpenAI GPT-4o-mini."""
    
    def __init__(self, validator: Optional[OntologyValidator] = None):
        super().__init__("gpt-4o-mini", validator)
        self.client = None
    
    def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self.client is None:
            from openai import OpenAI
            self.client = OpenAI()
        return self.client
    
    def extract(self, document: DocumentInfo) -> ExtractionOutput:
        """Extract using GPT-4o-mini."""
        client = self._get_client()
        
        prompt = self._build_prompt(document)
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=8000,
            )
            
            response_text = response.choices[0].message.content or ""
            return self._parse_response(response_text, document)
            
        except Exception as e:
            print(f"[GPT4oMiniExtractor] Error: {e}")
            return ExtractionOutput(
                document_id=document.document_id,
                document_path=document.path,
                model_name=self.model_name,
                extracted_at=datetime.utcnow(),
                entities=[],
                relationships=[],
                metadata={"error": str(e)}
            )


class ClaudeSonnetExtractor(BaseExtractor):
    """Extractor using Anthropic Claude Sonnet."""
    
    def __init__(self, validator: Optional[OntologyValidator] = None):
        super().__init__("claude-sonnet-4-20250514", validator)
        self.client = None
    
    def _get_client(self):
        """Lazy initialization of Anthropic client."""
        if self.client is None:
            import anthropic
            self.client = anthropic.Anthropic()
        return self.client
    
    def extract(self, document: DocumentInfo) -> ExtractionOutput:
        """Extract using Claude Sonnet."""
        client = self._get_client()
        
        prompt = self._build_prompt(document)
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8000,
                system=EXTRACTION_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, 'text'):
                        response_text = block.text
                        break
            return self._parse_response(response_text, document)
            
        except Exception as e:
            print(f"[ClaudeSonnetExtractor] Error: {e}")
            return ExtractionOutput(
                document_id=document.document_id,
                document_path=document.path,
                model_name=self.model_name,
                extracted_at=datetime.utcnow(),
                entities=[],
                relationships=[],
                metadata={"error": str(e)}
            )


class MultiModelExtractor:
    """Orchestrates extraction using multiple LLM models."""
    
    def __init__(
        self,
        output_dir: str = "extraction_outputs",
        models: Optional[List[str]] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.extractors: Dict[str, BaseExtractor] = {}
        
        if models is None:
            models = ["gpt-4o-mini", "claude-sonnet"]
        
        for model in models:
            if model == "gpt-4o-mini":
                self.extractors[model] = GPT4oMiniExtractor()
            elif model in ["claude-sonnet", "claude-sonnet-4"]:
                self.extractors["claude-sonnet"] = ClaudeSonnetExtractor()
    
    def _mark_extraction_complete(self, document_id: str, model_name: str):
        """Mark extraction complete for a specific model in the database."""
        import psycopg2
        
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            return
            
        column = 'gpt_extracted_at' if 'gpt' in model_name.lower() else 'claude_extracted_at'
        
        try:
            with psycopg2.connect(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                        UPDATE platform.documents 
                        SET {column} = NOW()
                        WHERE id = %s
                    """, (document_id,))
                conn.commit()
        except Exception as e:
            print(f"[MultiExtractor] Failed to update DB for {document_id}: {e}")

    def extract_document(
        self, 
        document: DocumentInfo,
        vault_id: str = "default",
    ) -> Dict[str, ExtractionOutput]:
        """Run extraction on a document using all configured models."""
        results = {}
        
        vault_dir = self.output_dir / vault_id
        vault_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if all model outputs already exist - skip if so
        all_exist = True
        existing_outputs = {}
        for model_name in self.extractors.keys():
            model_dir = vault_dir / model_name.replace("-", "_")
            output_path = model_dir / f"{document.document_id}.json"
            if output_path.exists():
                existing_outputs[model_name] = output_path
            else:
                all_exist = False
        
        if all_exist and existing_outputs:
            print(f"[MultiExtractor] Skipping {document.metadata.get('filename', document.document_id)} - already extracted")
            return self._load_existing_results(existing_outputs)
        
        for model_name, extractor in self.extractors.items():
            print(f"[MultiExtractor] Extracting with {model_name}: {document.metadata.get('filename', document.document_id)}")
            
            output = extractor.extract(document)
            results[model_name] = output
            
            model_dir = vault_dir / model_name.replace("-", "_")
            model_dir.mkdir(parents=True, exist_ok=True)
            
            output_path = model_dir / f"{document.document_id}.json"
            with open(output_path, 'w') as f:
                json.dump(output.model_dump(mode='json'), f, indent=2, default=str)
            
            self._mark_extraction_complete(document.document_id, model_name)
            
            print(f"[MultiExtractor] {model_name}: {len(output.entities)} entities, {len(output.relationships)} relationships")
        
        return results
    
    def _load_existing_results(self, output_paths: Dict[str, Path]) -> Dict[str, ExtractionOutput]:
        """Load previously extracted results from JSON files."""
        results = {}
        for model_name, output_path in output_paths.items():
            try:
                with open(output_path, 'r') as f:
                    data = json.load(f)
                results[model_name] = ExtractionOutput(**data)
            except Exception as e:
                print(f"[MultiExtractor] Error loading {output_path}: {e}")
        return results
    
    def extract_batch(
        self,
        documents: List[DocumentInfo],
        vault_id: str = "default",
    ) -> Dict[str, List[ExtractionOutput]]:
        """Run extraction on multiple documents."""
        all_results: Dict[str, List[ExtractionOutput]] = {
            model: [] for model in self.extractors.keys()
        }
        
        for i, doc in enumerate(documents):
            print(f"[MultiExtractor] Processing {i+1}/{len(documents)}: {doc.metadata.get('filename', doc.document_id)}")
            
            doc_results = self.extract_document(doc, vault_id)
            
            for model_name, output in doc_results.items():
                all_results[model_name].append(output)
        
        return all_results
    
    def extract_from_directory(
        self,
        directory: str,
        vault_id: str = "default",
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, List[ExtractionOutput]]:
        """Extract from all documents in a directory."""
        if extensions is None:
            extensions = [".md", ".txt", ".html", ".json"]
        
        documents = []
        dir_path = Path(directory)
        
        for ext in extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                if file_path.name.startswith("README"):
                    continue
                try:
                    doc = DocumentInfo.from_file(str(file_path))
                    documents.append(doc)
                except Exception as e:
                    print(f"[MultiExtractor] Error loading {file_path}: {e}")
        
        print(f"[MultiExtractor] Found {len(documents)} documents in {directory}")
        return self.extract_batch(documents, vault_id)
    
    def get_extraction_summary(self, vault_id: str) -> Dict[str, Any]:
        """Get summary of extractions for a vault."""
        vault_dir = self.output_dir / vault_id
        if not vault_dir.exists():
            return {"vault_id": vault_id, "error": "Vault not found"}
        
        summary = {
            "vault_id": vault_id,
            "models": {},
            "total_documents": 0,
            "total_entities": 0,
            "total_relationships": 0,
        }
        
        doc_ids = set()
        
        for model_dir in vault_dir.iterdir():
            if not model_dir.is_dir():
                continue
            
            model_name = model_dir.name
            model_stats = {
                "documents": 0,
                "entities": 0,
                "relationships": 0,
            }
            
            for output_file in model_dir.glob("*.json"):
                with open(output_file) as f:
                    data = json.load(f)
                
                model_stats["documents"] += 1
                model_stats["entities"] += len(data.get("entities", []))
                model_stats["relationships"] += len(data.get("relationships", []))
                doc_ids.add(data.get("document_id", ""))
            
            summary["models"][model_name] = model_stats
            summary["total_entities"] += model_stats["entities"]
            summary["total_relationships"] += model_stats["relationships"]
        
        summary["total_documents"] = len(doc_ids)
        
        return summary
