"""
Canonicalization Engine for Context Foundry.

Implements semantic grounding and embedding-based clustering for predicates.
Key insight: Embed the semantic DEFINITION, not the label.
"""
import os
import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from openai import OpenAI

from ..utils.logger import logger


@dataclass
class RawTriplet:
    subject: str
    subject_type: str
    predicate: str
    object: str
    object_type: str
    confidence: float = 0.8
    context: str = ""
    is_new_predicate: bool = False


@dataclass
class DefinedTriplet(RawTriplet):
    predicate_definition: str = ""
    predicate_embedding: Optional[List[float]] = None


@dataclass
class CanonicalTriplet:
    subject: str
    subject_type: str
    relationship_type: str  # Canonical type
    object: str
    object_type: str
    confidence: float
    source_predicate: str
    source_context: str
    predicate_definition: str = ""


@dataclass
class CanonicalRelation:
    id: Optional[str]
    tenant_id: str
    name: str
    definition: str
    embedding: Optional[List[float]]
    source_predicates: List[str] = field(default_factory=list)
    usage_count: int = 1


# Similarity thresholds
AUTO_MERGE_THRESHOLD = 0.85
LLM_VERIFY_THRESHOLD = 0.70


class Canonicalizer:
    """
    Canonicalizes extracted predicates using semantic embeddings.
    
    Process:
    1. Define: Generate semantic definition for each unique predicate
    2. Embed: Create embedding from definition (not label)
    3. Match: Find similar canonical types using cosine similarity
    4. Merge or Create: Auto-merge at >0.85, LLM verify at 0.70-0.85, create new below
    """
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self._canonical_cache: Dict[str, CanonicalRelation] = {}
        self._embedding_cache: Dict[str, List[float]] = {}
        self.client = OpenAI(
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        )
        self.embedding_client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY")
        )
        self._load_canonical_relations()
    
    def _load_canonical_relations(self) -> None:
        """Load existing canonical relations from database."""
        try:
            results = self.session.execute(
                text("""
                    SELECT id, name, definition, embedding, source_predicates, usage_count
                    FROM ontology.canonical_relations
                    WHERE tenant_id = :tenant_id
                """),
                {"tenant_id": self.tenant_id}
            ).fetchall()
            
            for row in results:
                embedding = None
                if row.embedding:
                    if isinstance(row.embedding, str):
                        embedding = [float(x) for x in row.embedding.strip('[]').split(',')]
                    else:
                        embedding = list(row.embedding)
                
                self._canonical_cache[row.name] = CanonicalRelation(
                    id=str(row.id),
                    tenant_id=self.tenant_id,
                    name=row.name,
                    definition=row.definition,
                    embedding=embedding,
                    source_predicates=row.source_predicates or [],
                    usage_count=row.usage_count
                )
            
            logger.info(f"[Canonicalizer] Loaded {len(self._canonical_cache)} canonical relations")
            
        except Exception as e:
            logger.error(f"[Canonicalizer] Failed to load canonical relations: {e}")
    
    def define_predicates(self, triplets: List[RawTriplet]) -> List[DefinedTriplet]:
        """
        Generate semantic definitions for each unique predicate.
        
        This is the key insight from EDC research: embed the DEFINITION, not the label.
        """
        unique_predicates = set(t.predicate for t in triplets)
        definitions: Dict[str, Tuple[str, List[float]]] = {}
        
        for predicate in unique_predicates:
            example = next(t for t in triplets if t.predicate == predicate)
            
            prompt = f"""Define the relationship '{predicate}' as used in this context:
"{example.context}"

Subject type: {example.subject_type}
Object type: {example.object_type}

Provide a clear one-sentence definition of what this relationship means.
Focus on the semantic meaning, not the exact words.

Return ONLY the definition, nothing else."""

            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0
                )
                definition = response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"[Canonicalizer] Failed to define '{predicate}': {e}")
                definition = f"A relationship indicating {predicate.lower().replace('_', ' ')}"
            
            embedding = self._get_embedding(definition)
            definitions[predicate] = (definition, embedding)
        
        defined_triplets = []
        for t in triplets:
            defn, emb = definitions[t.predicate]
            defined_triplets.append(DefinedTriplet(
                subject=t.subject,
                subject_type=t.subject_type,
                predicate=t.predicate,
                object=t.object,
                object_type=t.object_type,
                confidence=t.confidence,
                context=t.context,
                is_new_predicate=t.is_new_predicate,
                predicate_definition=defn,
                predicate_embedding=emb
            ))
        
        logger.info(f"[Canonicalizer] Defined {len(unique_predicates)} unique predicates")
        return defined_triplets
    
    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text, using cache.
        
        Uses direct OpenAI API for embeddings (not the Replit proxy which
        doesn't support the embeddings endpoint).
        """
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        
        try:
            response = self.embedding_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            embedding = response.data[0].embedding
            self._embedding_cache[text] = embedding
            return embedding
        except Exception as e:
            logger.error(f"[Canonicalizer] Failed to embed: {e}")
            return [0.0] * 1536
    
    def canonicalize(self, triplets: List[DefinedTriplet]) -> List[CanonicalTriplet]:
        """
        Map predicates to canonical types or create new ones.
        
        Uses embedding similarity with thresholds:
        - >0.85: Auto-merge
        - 0.70-0.85: LLM verification
        - <0.70: Create new canonical type
        """
        results = []
        new_canonicals_created = 0
        auto_merged = 0
        llm_verified = 0
        
        for triplet in triplets:
            best_match = None
            best_similarity = 0.0
            
            if triplet.predicate_embedding:
                for canonical in self._canonical_cache.values():
                    if canonical.embedding:
                        similarity = self._cosine_similarity(
                            triplet.predicate_embedding,
                            canonical.embedding
                        )
                        if similarity > best_similarity:
                            best_similarity = similarity
                            best_match = canonical
            
            if best_similarity > AUTO_MERGE_THRESHOLD:
                canonical_type = best_match.name
                self._update_canonical(best_match, triplet.predicate)
                auto_merged += 1
                
            elif best_similarity > LLM_VERIFY_THRESHOLD:
                if self._llm_verify_merge(triplet, best_match):
                    canonical_type = best_match.name
                    self._update_canonical(best_match, triplet.predicate)
                    llm_verified += 1
                else:
                    canonical_type = self._create_canonical_type(triplet)
                    new_canonicals_created += 1
            else:
                canonical_type = self._create_canonical_type(triplet)
                new_canonicals_created += 1
            
            results.append(CanonicalTriplet(
                subject=triplet.subject,
                subject_type=self._canonicalize_entity_type(triplet.subject_type),
                relationship_type=canonical_type,
                object=triplet.object,
                object_type=self._canonicalize_entity_type(triplet.object_type),
                confidence=triplet.confidence,
                source_predicate=triplet.predicate,
                source_context=triplet.context,
                predicate_definition=triplet.predicate_definition
            ))
        
        logger.info(f"[Canonicalizer] Canonicalized {len(triplets)} triplets: "
                   f"{auto_merged} auto-merged, {llm_verified} LLM-verified, "
                   f"{new_canonicals_created} new types created")
        
        return results
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))
    
    def _llm_verify_merge(self, triplet: DefinedTriplet, canonical: CanonicalRelation) -> bool:
        """LLM verification for borderline matches."""
        prompt = f"""Can these two relationship types be considered equivalent?

Relationship A: "{triplet.predicate}"
Definition A: "{triplet.predicate_definition}"

Relationship B: "{canonical.name}"
Definition B: "{canonical.definition}"

Answer YES if they represent the same semantic relationship.
Answer NO if they are meaningfully different.

Return only YES or NO."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0
            )
            answer = response.choices[0].message.content.strip().upper()
            return answer == "YES"
        except Exception as e:
            logger.error(f"[Canonicalizer] LLM verify failed: {e}")
            return False
    
    def _update_canonical(self, canonical: CanonicalRelation, source_predicate: str) -> None:
        """Update canonical relation with new source predicate."""
        if source_predicate not in canonical.source_predicates:
            canonical.source_predicates.append(source_predicate)
            canonical.usage_count += 1
            
            try:
                self.session.execute(
                    text("""
                        UPDATE ontology.canonical_relations
                        SET source_predicates = :predicates,
                            usage_count = :usage_count,
                            updated_at = NOW()
                        WHERE id = :id
                    """),
                    {
                        "id": canonical.id,
                        "predicates": json.dumps(canonical.source_predicates),
                        "usage_count": canonical.usage_count
                    }
                )
                self.session.commit()
            except Exception as e:
                logger.error(f"[Canonicalizer] Failed to update canonical: {e}")
                self.session.rollback()
    
    def _create_canonical_type(self, triplet: DefinedTriplet) -> str:
        """Create new canonical type from predicate."""
        canonical_name = triplet.predicate.upper().replace(" ", "_").replace("-", "_")
        
        if canonical_name in self._canonical_cache:
            return canonical_name
        
        new_canonical = CanonicalRelation(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            name=canonical_name,
            definition=triplet.predicate_definition,
            embedding=triplet.predicate_embedding,
            source_predicates=[triplet.predicate],
            usage_count=1
        )
        
        try:
            embedding_str = None
            if triplet.predicate_embedding:
                embedding_str = f"[{','.join(str(x) for x in triplet.predicate_embedding)}]"
            
            if embedding_str:
                self.session.execute(
                    text("""
                        INSERT INTO ontology.canonical_relations
                        (id, tenant_id, name, definition, embedding, source_predicates, usage_count)
                        VALUES (:id, :tenant_id, :name, :definition, cast(:embedding as vector), :predicates, :usage_count)
                        ON CONFLICT (tenant_id, name) DO NOTHING
                    """),
                    {
                        "id": new_canonical.id,
                        "tenant_id": self.tenant_id,
                        "name": canonical_name,
                        "definition": triplet.predicate_definition,
                        "embedding": embedding_str,
                        "predicates": json.dumps([triplet.predicate]),
                        "usage_count": 1
                    }
                )
            else:
                self.session.execute(
                    text("""
                        INSERT INTO ontology.canonical_relations
                        (id, tenant_id, name, definition, source_predicates, usage_count)
                        VALUES (:id, :tenant_id, :name, :definition, :predicates, :usage_count)
                        ON CONFLICT (tenant_id, name) DO NOTHING
                    """),
                    {
                        "id": new_canonical.id,
                        "tenant_id": self.tenant_id,
                        "name": canonical_name,
                        "definition": triplet.predicate_definition,
                        "predicates": json.dumps([triplet.predicate]),
                        "usage_count": 1
                    }
                )
            self.session.commit()
            
            self._canonical_cache[canonical_name] = new_canonical
            logger.info(f"[Canonicalizer] Created new canonical type: {canonical_name}")
            
        except Exception as e:
            logger.error(f"[Canonicalizer] Failed to create canonical type: {e}")
            self.session.rollback()
        
        return canonical_name
    
    def _canonicalize_entity_type(self, entity_type: str) -> str:
        """Normalize entity type to canonical form."""
        return entity_type.upper().replace(" ", "_").replace("-", "_")
    
    def process_triplets(self, triplets: List[RawTriplet]) -> List[CanonicalTriplet]:
        """
        Full processing pipeline: Define → Canonicalize.
        
        Args:
            triplets: Raw extracted triplets
            
        Returns:
            Canonicalized triplets with semantic grounding
        """
        if not triplets:
            return []
        
        defined = self.define_predicates(triplets)
        
        canonical = self.canonicalize(defined)
        
        return canonical


def convert_to_raw_triplets(
    entities: List[Any],
    relations: List[Any]
) -> List[RawTriplet]:
    """
    Convert extracted entities and relations to RawTriplet format.
    
    Args:
        entities: List of ExtractedEntity objects
        relations: List of ExtractedRelation objects
        
    Returns:
        List of RawTriplet objects
    """
    entity_map = {e.canonical_name: e for e in entities}
    
    triplets = []
    for rel in relations:
        source_entity = entity_map.get(rel.source_name)
        target_entity = entity_map.get(rel.target_name)
        
        triplets.append(RawTriplet(
            subject=rel.source_name,
            subject_type=source_entity.entity_type if source_entity else "UNKNOWN",
            predicate=rel.relation_type,
            object=rel.target_name,
            object_type=target_entity.entity_type if target_entity else "UNKNOWN",
            confidence=rel.confidence,
            context=rel.source_span or "",
            is_new_predicate=False
        ))
    
    return triplets
