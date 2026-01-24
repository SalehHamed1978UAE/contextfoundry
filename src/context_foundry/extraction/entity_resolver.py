"""
Entity Resolution & Consensus Building for Multi-Model Extraction

Phase 2 of the extraction pipeline: Merges extractions from multiple models
into a single canonical entity set with boosted confidence scores.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from datetime import datetime
import re
from collections import defaultdict

from ..ontology.schema import EntityType, RelationshipType


@dataclass
class CanonicalEntity:
    """A resolved entity after multi-model consensus."""
    canonical_name: str
    entity_type: EntityType
    properties: Dict[str, Any]
    confidence: float
    source_models: List[str]
    name_variants: List[str]
    aliases: List[str]
    source_documents: List[str]
    consensus_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CanonicalRelationship:
    """A resolved relationship after multi-model consensus."""
    source_entity: str
    source_type: EntityType
    relationship_type: RelationshipType
    target_entity: str
    target_type: EntityType
    properties: Dict[str, Any]
    confidence: float
    source_models: List[str]
    evidence: List[str]
    consensus_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusOutput:
    """Output of the entity resolution and consensus process."""
    entities: List[CanonicalEntity]
    relationships: List[CanonicalRelationship]
    metadata: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [
                {
                    "canonical_name": e.canonical_name,
                    "entity_type": e.entity_type.value if hasattr(e.entity_type, 'value') else str(e.entity_type),
                    "properties": e.properties,
                    "confidence": e.confidence,
                    "source_models": e.source_models,
                    "name_variants": e.name_variants,
                    "aliases": e.aliases,
                    "source_documents": e.source_documents,
                    "consensus_metadata": e.consensus_metadata,
                }
                for e in self.entities
            ],
            "relationships": [
                {
                    "source_entity": r.source_entity,
                    "source_type": r.source_type.value if hasattr(r.source_type, 'value') else str(r.source_type),
                    "relationship_type": r.relationship_type.value if hasattr(r.relationship_type, 'value') else str(r.relationship_type),
                    "target_entity": r.target_entity,
                    "target_type": r.target_type.value if hasattr(r.target_type, 'value') else str(r.target_type),
                    "properties": r.properties,
                    "confidence": r.confidence,
                    "source_models": r.source_models,
                    "evidence": r.evidence,
                    "consensus_metadata": r.consensus_metadata,
                }
                for r in self.relationships
            ],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class NameNormalizer:
    """Normalizes entity names for matching."""
    
    TITLE_PREFIXES = {
        'mr', 'mrs', 'ms', 'miss', 'dr', 'prof', 'professor',
        'sir', 'dame', 'lord', 'lady', 'rev', 'reverend'
    }
    
    ROLE_PREFIXES = {
        'ceo', 'cfo', 'cto', 'coo', 'cio', 'cmo', 'chro',
        'president', 'vice president', 'vp', 'svp', 'evp',
        'director', 'manager', 'head', 'chief', 'senior', 'lead',
        'founder', 'co-founder', 'partner', 'principal'
    }
    
    SUFFIXES = {
        'jr', 'sr', 'ii', 'iii', 'iv', 'v',
        'phd', 'md', 'esq', 'mba', 'cpa'
    }
    
    ORG_SUFFIXES = {
        'inc', 'llc', 'ltd', 'corp', 'corporation', 'company', 'co',
        'group', 'holdings', 'partners', 'associates', 'consulting',
        'services', 'solutions', 'technologies', 'systems'
    }
    
    @classmethod
    def normalize(cls, name: str, entity_type: Optional[EntityType] = None) -> str:
        """Normalize a name for matching."""
        if not name:
            return ""
        
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s\'-]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        if entity_type == EntityType.PERSON:
            normalized = cls._normalize_person_name(normalized)
        elif entity_type in (EntityType.ORGANIZATION, EntityType.BUSINESS_UNIT):
            normalized = cls._normalize_org_name(normalized)
        
        return normalized.strip()
    
    @classmethod
    def _normalize_person_name(cls, name: str) -> str:
        """Remove titles and role prefixes from person names."""
        words = name.split()
        filtered = []
        
        for i, word in enumerate(words):
            clean_word = word.rstrip('.')
            if clean_word in cls.TITLE_PREFIXES:
                continue
            if clean_word in cls.SUFFIXES:
                continue
            if i == 0 and clean_word in cls.ROLE_PREFIXES:
                continue
            if i == 0 and len(words) > 2:
                two_word = f"{clean_word} {words[i+1]}" if i+1 < len(words) else ""
                if two_word in cls.ROLE_PREFIXES:
                    continue
            filtered.append(word)
        
        return ' '.join(filtered)
    
    @classmethod
    def _normalize_org_name(cls, name: str) -> str:
        """Remove common org suffixes."""
        words = name.split()
        while words and words[-1].rstrip('.') in cls.ORG_SUFFIXES:
            words.pop()
        return ' '.join(words)
    
    @classmethod
    def extract_core_name(cls, name: str, entity_type: Optional[EntityType] = None) -> str:
        """Extract just the core name (e.g., last name for persons)."""
        normalized = cls.normalize(name, entity_type)
        
        if entity_type == EntityType.PERSON:
            parts = normalized.split()
            if len(parts) >= 2:
                return parts[-1]
        
        return normalized


class EntityMatcher:
    """Matches entities across model outputs to find duplicates."""
    
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.normalizer = NameNormalizer()
    
    def are_same_entity(
        self,
        name1: str,
        type1: EntityType,
        name2: str,
        type2: EntityType,
        aliases1: Optional[List[str]] = None,
        aliases2: Optional[List[str]] = None,
    ) -> Tuple[bool, float]:
        """
        Determine if two entities are the same.
        Returns (is_match, confidence_score).
        """
        aliases1 = aliases1 or []
        aliases2 = aliases2 or []
        
        if type1 != type2:
            return False, 0.0
        
        norm1 = self.normalizer.normalize(name1, type1)
        norm2 = self.normalizer.normalize(name2, type2)
        
        if norm1 == norm2:
            return True, 1.0
        
        if self._is_substring_match(norm1, norm2):
            return True, 0.95
        
        all_names1 = [norm1] + [self.normalizer.normalize(a, type1) for a in aliases1]
        all_names2 = [norm2] + [self.normalizer.normalize(a, type2) for a in aliases2]
        
        for n1 in all_names1:
            for n2 in all_names2:
                if n1 == n2:
                    return True, 0.95
        
        if type1 == EntityType.PERSON:
            if self._is_name_variant(norm1, norm2):
                return True, 0.90
        
        similarity = self._compute_similarity(norm1, norm2)
        if similarity >= self.similarity_threshold:
            return True, similarity
        
        return False, similarity
    
    def _is_substring_match(self, name1: str, name2: str) -> bool:
        """Check if one name is contained in the other."""
        if len(name1) < 3 or len(name2) < 3:
            return False
        return name1 in name2 or name2 in name1
    
    def _is_name_variant(self, name1: str, name2: str) -> bool:
        """Check if two names are variants of the same person."""
        parts1 = name1.split()
        parts2 = name2.split()
        
        if not parts1 or not parts2:
            return False
        
        if parts1[-1] == parts2[-1]:
            return True
        
        if len(parts1) >= 2 and len(parts2) >= 2:
            if parts1[0] == parts2[0] and parts1[-1] == parts2[-1]:
                return True
        
        if len(parts1) >= 2 and len(parts2) == 1:
            if parts1[-1] == parts2[0] or parts1[0] == parts2[0]:
                return True
        if len(parts2) >= 2 and len(parts1) == 1:
            if parts2[-1] == parts1[0] or parts2[0] == parts1[0]:
                return True
        
        return False
    
    def _compute_similarity(self, s1: str, s2: str) -> float:
        """Compute string similarity using Levenshtein ratio."""
        if not s1 or not s2:
            return 0.0
        
        len1, len2 = len(s1), len(s2)
        if len1 > len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1
        
        distances = range(len1 + 1)
        for i2, c2 in enumerate(s2):
            distances_ = [i2 + 1]
            for i1, c1 in enumerate(s1):
                if c1 == c2:
                    distances_.append(distances[i1])
                else:
                    distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
            distances = distances_
        
        distance = distances[-1]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len) if max_len > 0 else 1.0


class ConsensusBuilder:
    """Builds consensus from multiple model extractions."""
    
    MULTI_MODEL_BOOST = 0.15
    SINGLE_MODEL_PENALTY = 0.0
    
    def __init__(self, matcher: Optional[EntityMatcher] = None):
        self.matcher = matcher or EntityMatcher()
    
    def build_consensus(
        self,
        extractions: Dict[str, Any],
        document_path: str = "",
    ) -> ConsensusOutput:
        """
        Build consensus from multiple model extractions.
        
        Args:
            extractions: Dict mapping model_name -> ExtractionOutput (or dict)
            document_path: Path to the source document
        
        Returns:
            ConsensusOutput with merged entities and relationships
        """
        all_entities = []
        all_relationships = []
        
        for model_name, output in extractions.items():
            if hasattr(output, 'entities'):
                entities = output.entities
                relationships = output.relationships
            else:
                entities = output.get('entities', [])
                relationships = output.get('relationships', [])
            
            for e in entities:
                all_entities.append((model_name, e))
            for r in relationships:
                all_relationships.append((model_name, r))
        
        canonical_entities = self._merge_entities(all_entities)
        
        entity_name_map = self._build_name_map(canonical_entities)
        
        canonical_relationships = self._merge_relationships(
            all_relationships, entity_name_map
        )
        
        metadata = {
            "source_models": list(extractions.keys()),
            "total_input_entities": len(all_entities),
            "total_input_relationships": len(all_relationships),
            "merged_entity_count": len(canonical_entities),
            "merged_relationship_count": len(canonical_relationships),
            "document_path": document_path,
            "multi_model_entities": sum(
                1 for e in canonical_entities if len(e.source_models) > 1
            ),
            "single_model_entities": sum(
                1 for e in canonical_entities if len(e.source_models) == 1
            ),
        }
        
        return ConsensusOutput(
            entities=canonical_entities,
            relationships=canonical_relationships,
            metadata=metadata,
        )
    
    def _merge_entities(
        self,
        all_entities: List[Tuple[str, Any]],
    ) -> List[CanonicalEntity]:
        """Merge entities from multiple models."""
        clusters: List[List[Tuple[str, Any]]] = []
        
        for model_name, entity in all_entities:
            entity_name = self._get_entity_name(entity)
            entity_type = self._get_entity_type(entity)
            entity_aliases = self._get_entity_aliases(entity)
            
            matched_cluster = None
            best_match_score = 0.0
            
            for cluster in clusters:
                for _, cluster_entity in cluster:
                    cluster_name = self._get_entity_name(cluster_entity)
                    cluster_type = self._get_entity_type(cluster_entity)
                    cluster_aliases = self._get_entity_aliases(cluster_entity)
                    
                    is_match, score = self.matcher.are_same_entity(
                        entity_name, entity_type,
                        cluster_name, cluster_type,
                        entity_aliases, cluster_aliases,
                    )
                    
                    if is_match and score > best_match_score:
                        matched_cluster = cluster
                        best_match_score = score
                        break
                
                if matched_cluster:
                    break
            
            if matched_cluster:
                matched_cluster.append((model_name, entity))
            else:
                clusters.append([(model_name, entity)])
        
        canonical_entities = []
        for cluster in clusters:
            canonical = self._create_canonical_entity(cluster)
            canonical_entities.append(canonical)
        
        return canonical_entities
    
    def _create_canonical_entity(
        self,
        cluster: List[Tuple[str, Any]],
    ) -> CanonicalEntity:
        """Create a canonical entity from a cluster of matched entities."""
        source_models = list(set(model for model, _ in cluster))
        
        name_variants = []
        all_aliases = []
        all_properties = {}
        source_documents = []
        confidences = []
        
        entity_type: EntityType = EntityType.CONCEPT
        best_name = None
        best_name_score = 0
        first_entity = True
        
        for model_name, entity in cluster:
            name = self._get_entity_name(entity)
            etype = self._get_entity_type(entity)
            
            if first_entity:
                entity_type = etype
                first_entity = False
            
            if name not in name_variants:
                name_variants.append(name)
            
            name_score = len(name.split())
            if name_score > best_name_score:
                best_name = name
                best_name_score = name_score
            
            aliases = self._get_entity_aliases(entity)
            for alias in aliases:
                if alias not in all_aliases and alias != name:
                    all_aliases.append(alias)
            
            props = self._get_entity_properties(entity)
            for key, value in props.items():
                if value is not None and value != "":
                    if key not in all_properties:
                        all_properties[key] = value
                    elif isinstance(all_properties[key], list):
                        if value not in all_properties[key]:
                            all_properties[key].append(value)
                    elif all_properties[key] != value:
                        all_properties[key] = [all_properties[key], value]
            
            source_doc = self._get_source_document(entity)
            if source_doc and source_doc not in source_documents:
                source_documents.append(source_doc)
            
            conf = self._get_confidence(entity)
            confidences.append(conf)
        
        base_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        if len(source_models) > 1:
            boosted_confidence = min(1.0, base_confidence + self.MULTI_MODEL_BOOST)
        else:
            boosted_confidence = base_confidence
        
        return CanonicalEntity(
            canonical_name=best_name or name_variants[0],
            entity_type=entity_type,
            properties=all_properties,
            confidence=round(boosted_confidence, 3),
            source_models=source_models,
            name_variants=name_variants,
            aliases=all_aliases,
            source_documents=source_documents,
            consensus_metadata={
                "cluster_size": len(cluster),
                "base_confidence": round(base_confidence, 3),
                "multi_model_boost": len(source_models) > 1,
            },
        )
    
    def _merge_relationships(
        self,
        all_relationships: List[Tuple[str, Any]],
        entity_name_map: Dict[str, str],
    ) -> List[CanonicalRelationship]:
        """Merge relationships from multiple models."""
        rel_clusters: Dict[str, List[Tuple[str, Any, str, str]]] = defaultdict(list)
        
        for model_name, rel in all_relationships:
            source = self._get_rel_source(rel)
            target = self._get_rel_target(rel)
            rel_type = self._get_rel_type(rel)
            
            canonical_source = entity_name_map.get(
                NameNormalizer.normalize(source), source
            )
            canonical_target = entity_name_map.get(
                NameNormalizer.normalize(target), target
            )
            
            key = f"{canonical_source}|{rel_type}|{canonical_target}"
            rel_clusters[key].append((model_name, rel, canonical_source, canonical_target))
        
        canonical_relationships = []
        for key, cluster in rel_clusters.items():
            canonical = self._create_canonical_relationship(cluster)
            canonical_relationships.append(canonical)
        
        return canonical_relationships
    
    def _create_canonical_relationship(
        self,
        cluster: List[Tuple[str, Any, str, str]],
    ) -> CanonicalRelationship:
        """Create a canonical relationship from a cluster."""
        source_models = list(set(model for model, _, _, _ in cluster))
        
        all_evidence = []
        all_properties = {}
        confidences = []
        
        rel_type: RelationshipType = RelationshipType.RELATED_TO
        source_type: EntityType = EntityType.CONCEPT
        target_type: EntityType = EntityType.CONCEPT
        canonical_source: str = ""
        canonical_target: str = ""
        first_rel = True
        
        for model_name, rel, can_source, can_target in cluster:
            canonical_source = can_source
            canonical_target = can_target
            
            if first_rel:
                rel_type = self._get_rel_type(rel)
                source_type = self._get_rel_source_type(rel)
                target_type = self._get_rel_target_type(rel)
                first_rel = False
            
            evidence = self._get_rel_evidence(rel)
            if evidence and evidence not in all_evidence:
                all_evidence.append(evidence)
            
            props = self._get_rel_properties(rel)
            for key, value in props.items():
                if value is not None and value != "":
                    if key not in all_properties:
                        all_properties[key] = value
            
            conf = self._get_confidence(rel)
            confidences.append(conf)
        
        base_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        if len(source_models) > 1:
            boosted_confidence = min(1.0, base_confidence + self.MULTI_MODEL_BOOST)
        else:
            boosted_confidence = base_confidence
        
        return CanonicalRelationship(
            source_entity=canonical_source,
            source_type=source_type,
            relationship_type=rel_type,
            target_entity=canonical_target,
            target_type=target_type,
            properties=all_properties,
            confidence=round(boosted_confidence, 3),
            source_models=source_models,
            evidence=all_evidence,
            consensus_metadata={
                "cluster_size": len(cluster),
                "base_confidence": round(base_confidence, 3),
                "multi_model_boost": len(source_models) > 1,
            },
        )
    
    def _build_name_map(
        self,
        canonical_entities: List[CanonicalEntity],
    ) -> Dict[str, str]:
        """Build a map from normalized name variants to canonical names."""
        name_map = {}
        for entity in canonical_entities:
            for variant in entity.name_variants:
                normalized = NameNormalizer.normalize(variant, entity.entity_type)
                name_map[normalized] = entity.canonical_name
            for alias in entity.aliases:
                normalized = NameNormalizer.normalize(alias, entity.entity_type)
                name_map[normalized] = entity.canonical_name
        return name_map
    
    def _get_entity_name(self, entity: Any) -> str:
        if hasattr(entity, 'name'):
            return entity.name
        return entity.get('name', '')
    
    def _get_entity_type(self, entity: Any) -> EntityType:
        if hasattr(entity, 'entity_type'):
            return entity.entity_type
        type_str = entity.get('entity_type', 'CONCEPT')
        try:
            return EntityType(type_str)
        except ValueError:
            return EntityType.CONCEPT
    
    def _get_entity_aliases(self, entity: Any) -> List[str]:
        if hasattr(entity, 'aliases'):
            return entity.aliases or []
        return entity.get('aliases', [])
    
    def _get_entity_properties(self, entity: Any) -> Dict[str, Any]:
        if hasattr(entity, 'properties'):
            return entity.properties or {}
        return entity.get('properties', {})
    
    def _get_source_document(self, entity: Any) -> str:
        if hasattr(entity, 'source_document'):
            return entity.source_document
        return entity.get('source_document', '')
    
    def _get_confidence(self, obj: Any) -> float:
        if hasattr(obj, 'confidence'):
            return obj.confidence
        return float(obj.get('confidence', 0.5))
    
    def _get_rel_source(self, rel: Any) -> str:
        if hasattr(rel, 'source_entity'):
            return rel.source_entity
        return rel.get('source_entity', '')
    
    def _get_rel_target(self, rel: Any) -> str:
        if hasattr(rel, 'target_entity'):
            return rel.target_entity
        return rel.get('target_entity', '')
    
    def _get_rel_type(self, rel: Any) -> RelationshipType:
        if hasattr(rel, 'relationship_type'):
            return rel.relationship_type
        type_str = rel.get('relationship_type', 'RELATED_TO')
        try:
            return RelationshipType(type_str)
        except ValueError:
            return RelationshipType.RELATED_TO
    
    def _get_rel_source_type(self, rel: Any) -> EntityType:
        if hasattr(rel, 'source_type'):
            return rel.source_type
        type_str = rel.get('source_type', 'CONCEPT')
        try:
            return EntityType(type_str)
        except ValueError:
            return EntityType.CONCEPT
    
    def _get_rel_target_type(self, rel: Any) -> EntityType:
        if hasattr(rel, 'target_type'):
            return rel.target_type
        type_str = rel.get('target_type', 'CONCEPT')
        try:
            return EntityType(type_str)
        except ValueError:
            return EntityType.CONCEPT
    
    def _get_rel_evidence(self, rel: Any) -> str:
        if hasattr(rel, 'evidence'):
            return rel.evidence
        return rel.get('evidence', '')
    
    def _get_rel_properties(self, rel: Any) -> Dict[str, Any]:
        if hasattr(rel, 'properties'):
            return rel.properties or {}
        return rel.get('properties', {})


def run_consensus(
    extraction_outputs: Dict[str, Any],
    document_path: str = "",
) -> ConsensusOutput:
    """
    Run entity resolution and consensus building.
    
    Args:
        extraction_outputs: Dict mapping model_name -> ExtractionOutput
        document_path: Path to source document
    
    Returns:
        ConsensusOutput with merged entities and relationships
    """
    builder = ConsensusBuilder()
    return builder.build_consensus(extraction_outputs, document_path)
