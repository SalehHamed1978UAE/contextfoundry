"""
Targeted Extractor

Re-examines source documents to fill specific knowledge gaps.
Uses focused extraction prompts to find missing entities/relationships.
"""

import json
import logging
import re
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4

from sqlalchemy import text

logger = logging.getLogger(__name__)


class TargetedExtractor:
    """Performs targeted extraction to fill knowledge gaps"""
    
    def __init__(self, db_session, llm_client=None):
        self.db = db_session
        self.llm = llm_client
    
    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a learning task by performing targeted extraction.
        
        Returns results summary.
        """
        
        task_id = task['id']
        tenant_id = task['tenant_id']
        
        logger.info(f"Processing learning task {task_id}")
        
        chunks = self._get_relevant_chunks(
            tenant_id=tenant_id,
            search_terms=task.get('search_terms', []),
            document_ids=task.get('document_ids'),
            chunk_ids=task.get('chunk_ids')
        )
        
        if not chunks:
            logger.warning(f"No relevant chunks found for task {task_id}")
            return {"entities_found": 0, "relationships_found": 0, "chunks_searched": 0}
        
        logger.info(f"Found {len(chunks)} relevant chunks to search")
        
        all_entities = []
        all_relationships = []
        
        for chunk in chunks:
            entities, relationships = self._extract_from_chunk(
                chunk=chunk,
                target_entity_name=task.get('target_entity_name'),
                target_entity_type=task.get('target_entity_type'),
                target_relationship_type=task.get('target_relationship_type'),
                search_terms=task.get('search_terms', [])
            )
            
            all_entities.extend(entities)
            all_relationships.extend(relationships)
        
        for entity in all_entities:
            self._store_entity_result(task_id, tenant_id, entity)
        
        for rel in all_relationships:
            self._store_relationship_result(task_id, tenant_id, rel)
        
        entities_added = self._add_entities_to_kg(tenant_id, all_entities)
        relationships_added = self._add_relationships_to_kg(tenant_id, all_relationships)
        
        return {
            "entities_found": len(all_entities),
            "relationships_found": len(all_relationships),
            "entities_added": entities_added,
            "relationships_added": relationships_added,
            "chunks_searched": len(chunks)
        }
    
    def _get_relevant_chunks(
        self,
        tenant_id: UUID,
        search_terms: List[str],
        document_ids: Optional[List[UUID]] = None,
        chunk_ids: Optional[List[UUID]] = None
    ) -> List[Dict[str, Any]]:
        """Get chunks relevant to the search terms"""
        
        if chunk_ids:
            result = self.db.execute(text("""
                SELECT c.id, c.content, c.document_id, d.name as document_name
                FROM document_chunks c
                JOIN platform.documents d ON c.document_id = d.id
                WHERE c.id = ANY(:chunk_ids)
            """), {"chunk_ids": chunk_ids})
            return [dict(r._mapping) for r in result.fetchall()]
        
        if search_terms:
            query = """
                SELECT c.id, c.content, c.document_id, d.name as document_name
                FROM document_chunks c
                JOIN platform.documents d ON c.document_id = d.id
                WHERE d.tenant_id = :tenant_id
            """
            
            params = {"tenant_id": tenant_id}
            
            if document_ids:
                query += " AND c.document_id = ANY(:doc_ids)"
                params["doc_ids"] = document_ids
            
            term_conditions = []
            for i, term in enumerate(search_terms[:5]):
                param_name = f"term_{i}"
                term_conditions.append(f"c.content ILIKE :{param_name}")
                params[param_name] = f"%{term}%"
            
            if term_conditions:
                query += f" AND ({' OR '.join(term_conditions)})"
            
            query += " LIMIT 20"
            
            result = self.db.execute(text(query), params)
            return [dict(r._mapping) for r in result.fetchall()]
        
        result = self.db.execute(text("""
            SELECT c.id, c.content, c.document_id, d.name as document_name
            FROM document_chunks c
            JOIN platform.documents d ON c.document_id = d.id
            WHERE d.tenant_id = :tenant_id
            LIMIT 50
        """), {"tenant_id": tenant_id})
        
        return [dict(r._mapping) for r in result.fetchall()]
    
    def _extract_from_chunk(
        self,
        chunk: Dict[str, Any],
        target_entity_name: Optional[str],
        target_entity_type: Optional[str],
        target_relationship_type: Optional[str],
        search_terms: List[str]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Perform targeted extraction from a single chunk.
        
        Uses a focused prompt to find specific entities/relationships.
        """
        
        entities = []
        relationships = []
        
        content = chunk['content']
        
        pattern_entities = self._pattern_extract(
            content, 
            target_entity_name, 
            target_entity_type,
            search_terms
        )
        entities.extend(pattern_entities)
        
        if self.llm and len(pattern_entities) == 0:
            llm_entities, llm_relationships = self._llm_extract(
                content,
                target_entity_name,
                target_entity_type,
                target_relationship_type,
                search_terms
            )
            entities.extend(llm_entities)
            relationships.extend(llm_relationships)
        
        for entity in entities:
            entity['source_chunk_id'] = chunk['id']
            entity['source_document_id'] = chunk['document_id']
        
        for rel in relationships:
            rel['source_chunk_id'] = chunk['id']
        
        return entities, relationships
    
    def _pattern_extract(
        self,
        content: str,
        target_entity_name: Optional[str],
        target_entity_type: Optional[str],
        search_terms: List[str]
    ) -> List[Dict]:
        """Pattern-based extraction for common formats"""
        
        entities = []
        
        if target_entity_name:
            pattern = re.compile(re.escape(target_entity_name), re.IGNORECASE)
            matches = pattern.finditer(content)
            
            for match in matches:
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 100)
                context = content[start:end]
                
                entities.append({
                    'name': match.group(),
                    'entity_type': target_entity_type or 'UNKNOWN',
                    'confidence': 0.8,
                    'source_text': context,
                    'extraction_method': 'pattern'
                })
        
        cohort_pattern = r'([A-Z][A-Za-z0-9]+)\s*\(Cohort\s+\d+\)'
        for match in re.finditer(cohort_pattern, content):
            entities.append({
                'name': match.group(1),
                'entity_type': 'PORTFOLIO_COMPANY',
                'confidence': 0.9,
                'source_text': match.group(0),
                'extraction_method': 'pattern'
            })
        
        title_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–—]\s*(CEO|CTO|CFO|COO|CMO|CIO|President|Director|Partner|Manager|VP)'
        for match in re.finditer(title_pattern, content):
            entities.append({
                'name': match.group(1),
                'entity_type': 'PERSON',
                'confidence': 0.85,
                'source_text': match.group(0),
                'extraction_method': 'pattern',
                'attributes': {'title': match.group(2)}
            })
        
        company_pattern = r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:Inc|LLC|Corp|Ltd|Company|Technologies|Solutions)\.?'
        for match in re.finditer(company_pattern, content):
            entities.append({
                'name': match.group(0).rstrip('.'),
                'entity_type': 'ORGANIZATION',
                'confidence': 0.75,
                'source_text': match.group(0),
                'extraction_method': 'pattern'
            })
        
        return entities
    
    def _llm_extract(
        self,
        content: str,
        target_entity_name: Optional[str],
        target_entity_type: Optional[str],
        target_relationship_type: Optional[str],
        search_terms: List[str]
    ) -> Tuple[List[Dict], List[Dict]]:
        """LLM-based targeted extraction"""
        
        prompt = self._build_extraction_prompt(
            content,
            target_entity_name,
            target_entity_type,
            target_relationship_type,
            search_terms
        )
        
        try:
            response = self.llm.complete(prompt)
            return self._parse_llm_response(response)
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return [], []
    
    def _build_extraction_prompt(
        self,
        content: str,
        target_entity_name: Optional[str],
        target_entity_type: Optional[str],
        target_relationship_type: Optional[str],
        search_terms: List[str]
    ) -> str:
        """Build a focused extraction prompt"""
        
        prompt = f"""You are an expert entity extractor. Your task is to find specific information in the following text.

TEXT:
{content[:3000]}

"""
        
        if target_entity_name:
            prompt += f"""
SPECIFIC TARGET: Find any mention of "{target_entity_name}" and extract:
- Full name/title
- Type (person, organization, etc.)
- Any attributes mentioned
- Any relationships to other entities
"""
        
        if target_entity_type:
            prompt += f"""
ENTITY TYPE FOCUS: Look specifically for {target_entity_type} entities.
"""
        
        if search_terms:
            prompt += f"""
SEARCH TERMS: Pay special attention to these terms: {', '.join(search_terms)}
"""
        
        prompt += """
OUTPUT FORMAT (JSON):
{
  "entities": [
    {"name": "...", "type": "...", "confidence": 0.0-1.0, "context": "..."}
  ],
  "relationships": [
    {"source": "...", "relationship": "...", "target": "...", "confidence": 0.0-1.0}
  ]
}

If nothing is found, return empty arrays.
"""
        
        return prompt
    
    def _parse_llm_response(self, response: str) -> Tuple[List[Dict], List[Dict]]:
        """Parse LLM response into entities and relationships"""
        
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                entities = data.get('entities', [])
                relationships = data.get('relationships', [])
                
                for e in entities:
                    e['extraction_method'] = 'llm'
                for r in relationships:
                    r['extraction_method'] = 'llm'
                
                return entities, relationships
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
        
        return [], []
    
    def _store_entity_result(
        self, 
        task_id: UUID, 
        tenant_id: UUID, 
        entity: Dict
    ) -> None:
        """Store entity result for tracking"""
        
        self.db.execute(text("""
            INSERT INTO learning_results (
                learning_task_id, tenant_id, result_type,
                entity_name, entity_type, source_chunk_id,
                source_text, confidence
            ) VALUES (
                :task_id, :tenant_id, 'new_entity',
                :name, :type, :chunk_id,
                :source, :confidence
            )
        """), {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "name": entity['name'],
            "type": entity.get('entity_type', 'UNKNOWN'),
            "chunk_id": entity.get('source_chunk_id'),
            "source": entity.get('source_text', '')[:500],
            "confidence": entity.get('confidence', 0.5)
        })
    
    def _store_relationship_result(
        self, 
        task_id: UUID, 
        tenant_id: UUID, 
        rel: Dict
    ) -> None:
        """Store relationship result for tracking"""
        
        self.db.execute(text("""
            INSERT INTO learning_results (
                learning_task_id, tenant_id, result_type,
                source_entity_name, relationship_type, target_entity_name,
                source_chunk_id, confidence
            ) VALUES (
                :task_id, :tenant_id, 'new_relationship',
                :source, :rel_type, :target,
                :chunk_id, :confidence
            )
        """), {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "source": rel.get('source', ''),
            "rel_type": rel.get('relationship', ''),
            "target": rel.get('target', ''),
            "chunk_id": rel.get('source_chunk_id'),
            "confidence": rel.get('confidence', 0.5)
        })
    
    def _add_entities_to_kg(
        self, 
        tenant_id: UUID, 
        entities: List[Dict]
    ) -> int:
        """Add discovered entities to the knowledge graph"""
        
        added = 0
        
        for entity in entities:
            existing = self.db.execute(text("""
                SELECT id FROM entities 
                WHERE tenant_id = :tenant_id 
                  AND UPPER(name) = UPPER(:name)
                LIMIT 1
            """), {
                "tenant_id": tenant_id,
                "name": entity['name']
            }).fetchone()
            
            if not existing:
                self.db.execute(text("""
                    INSERT INTO entities (id, tenant_id, name, entity_type, confidence, source)
                    VALUES (:id, :tenant_id, :name, :type, :confidence, 'learning_flow')
                """), {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "name": entity['name'],
                    "type": entity.get('entity_type', 'UNKNOWN'),
                    "confidence": entity.get('confidence', 0.5)
                })
                added += 1
        
        self.db.commit()
        return added
    
    def _add_relationships_to_kg(
        self, 
        tenant_id: UUID, 
        relationships: List[Dict]
    ) -> int:
        """Add discovered relationships to the knowledge graph"""
        
        added = 0
        
        for rel in relationships:
            source = self.db.execute(text("""
                SELECT id FROM entities 
                WHERE tenant_id = :tenant_id AND UPPER(name) = UPPER(:name)
                LIMIT 1
            """), {"tenant_id": tenant_id, "name": rel.get('source', '')}).fetchone()
            
            target = self.db.execute(text("""
                SELECT id FROM entities 
                WHERE tenant_id = :tenant_id AND UPPER(name) = UPPER(:name)
                LIMIT 1
            """), {"tenant_id": tenant_id, "name": rel.get('target', '')}).fetchone()
            
            if source and target:
                existing = self.db.execute(text("""
                    SELECT id FROM relationships
                    WHERE source_id = :source AND target_id = :target
                      AND relationship_type = :rel_type
                    LIMIT 1
                """), {
                    "source": source.id,
                    "target": target.id,
                    "rel_type": rel.get('relationship', 'RELATED_TO')
                }).fetchone()
                
                if not existing:
                    self.db.execute(text("""
                        INSERT INTO relationships (
                            id, tenant_id, source_id, target_id, 
                            relationship_type, confidence
                        ) VALUES (
                            :id, :tenant_id, :source, :target, 
                            :rel_type, :confidence
                        )
                    """), {
                        "id": uuid4(),
                        "tenant_id": tenant_id,
                        "source": source.id,
                        "target": target.id,
                        "rel_type": rel.get('relationship', 'RELATED_TO'),
                        "confidence": rel.get('confidence', 0.5)
                    })
                    added += 1
        
        self.db.commit()
        return added


def get_targeted_extractor(db_session, llm_client=None) -> TargetedExtractor:
    """Get targeted extractor with provided session"""
    return TargetedExtractor(db_session, llm_client)
