"""
Relationship Extraction (RE) Agent for Context Foundry.

Discovers relationships between existing TRUSTED entities using existing documents.
Solves the "Bag-of-Nouns" problem: 79.8% of entities are isolated with no relationships.

Key Properties:
- Domain-agnostic (IT, Healthcare, Finance, etc.)
- Extracts relationships ONLY between already-defined TRUSTED entities
- Writes relationships to proposed_relationships staging table
- Enforces strict grounding — no speculation, no new entities
- Integrates with Gardener for lifecycle management

Safety Constraints:
1. No new entities - only relationships between existing TRUSTED entities
2. Evidence required - every relationship needs an evidence_span
3. Type pair validation - relationships must respect ontology constraints
4. Lexical evidence detection - increases confidence when explicit patterns found
5. Confidence thresholds - auto-approve/pending/reject based on score
6. Never direct to TRUSTED - all go to proposed_relationships first
7. Dedupe before insert - no duplicate relationships
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import text
from openai import OpenAI

from ..models.schema import (
    get_session, Entity, Relationship, Document, DocumentChunk, EntityMention,
    InferenceRun, InferenceRunChunk, ProposedRelationship, OntologyRelationshipType,
    LifecycleState, InferenceRunStatus, ProposedRelationshipStatus, InferenceMethod
)

try:
    from replit.ai.config import AI_INTEGRATIONS_OPENAI_API_KEY, AI_INTEGRATIONS_OPENAI_BASE_URL
except ImportError:
    import os
    AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    AI_INTEGRATIONS_OPENAI_BASE_URL = None

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1.1"  # Added specificity guidance to prefer rich types over RELATED_TO


@dataclass
class ValidationResult:
    """Result of validating a proposed relationship."""
    is_valid: bool
    reason: Optional[str] = None
    proposal: Optional[ProposedRelationship] = None


@dataclass
class CandidateEntity:
    """Entity candidate for relationship extraction."""
    id: UUID
    code: str
    name: str
    entity_type: str
    mention_text: str


class RelationshipInferenceAgent:
    """
    Agent that discovers relationships between existing TRUSTED entities
    by analyzing document chunks.
    """
    
    SYSTEM_PROMPT = """You are the Relationship Extraction Agent for Context Foundry, an enterprise knowledge graph.

Your task is to identify relationships between KNOWN ENTITIES based on document evidence.

CRITICAL RULES — VIOLATIONS ARE UNACCEPTABLE:
1. You may ONLY identify relationships between entities in ENTITY_LIST
2. You may ONLY use relationship types in ALLOWED_RELATIONSHIPS
3. You may NOT invent, suggest, or hallucinate new entities
4. You may NOT invent new relationship types
5. Every relationship MUST have an exact quote from the document as evidence
6. If no clear relationship exists, return an empty list — DO NOT GUESS
7. Confidence scores must reflect actual certainty (0.0-1.0)

RELATIONSHIP TYPE SELECTION — SPECIFICITY IS MANDATORY:
- ALWAYS prefer the MOST SPECIFIC relationship type that fits the evidence
- RELATED_TO is a LAST RESORT — only use when NO other type applies
- Look for action verbs that indicate specific relationships:
  * "leads", "manages", "oversees", "directs", "heads" → MANAGES
  * "owns", "acquired", "purchased" → OWNS
  * "depends on", "requires", "needs", "uses" → DEPENDS_ON
  * "works at", "employed by", "joined" → WORKS_AT
  * "reports to", "supervised by" → REPORTS_TO
  * "part of", "belongs to", "within" → PART_OF or MEMBER_OF
  * "located in", "based in", "headquartered" → LOCATED_IN
  * "implements", "follows", "adopts" → IMPLEMENTS
  * "enables", "supports", "facilitates" → ENABLES
  * "calls", "invokes", "routes to" → ROUTES_TO or CALLS
- If the text says "X manages Y", use MANAGES, not RELATED_TO
- If the text says "X depends on Y", use DEPENDS_ON, not RELATED_TO

OUTPUT REQUIREMENTS:
- Return valid JSON only
- Include evidence_span with exact quote (10-500 chars)
- Include confidence score (0.0-1.0)
- If uncertain, lower confidence or omit entirely"""

    def __init__(self, session: Optional[Session] = None, domain: str = 'IT'):
        self.session = session or get_session()
        self.domain = domain
        self._llm_client = None
        self._ontology_cache: Dict[str, OntologyRelationshipType] = {}
        logger.info(f"RelationshipInferenceAgent initialized for domain: {domain}")
    
    @property
    def llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            kwargs = {"api_key": AI_INTEGRATIONS_OPENAI_API_KEY}
            if AI_INTEGRATIONS_OPENAI_BASE_URL:
                kwargs["base_url"] = AI_INTEGRATIONS_OPENAI_BASE_URL
            self._llm_client = OpenAI(**kwargs)
        return self._llm_client
    
    def get_ontology(self, tenant_id: Optional[UUID] = None) -> List[OntologyRelationshipType]:
        """Get ontology relationship types for domain."""
        query = self.session.query(OntologyRelationshipType).filter(
            OntologyRelationshipType.domain == self.domain,
            OntologyRelationshipType.is_active == True
        )
        if tenant_id:
            query = query.filter(
                (OntologyRelationshipType.tenant_id == None) | 
                (OntologyRelationshipType.tenant_id == tenant_id)
            )
        return query.all()
    
    def validate_entities(
        self, 
        source_id: UUID, 
        target_id: UUID, 
        tenant_id: UUID
    ) -> Tuple[bool, Optional[str]]:
        """
        Constraint 1: Both entities must exist and be TRUSTED.
        """
        source = self.session.query(Entity).filter(Entity.id == source_id).first()
        target = self.session.query(Entity).filter(Entity.id == target_id).first()
        
        if not source:
            return False, f"Source entity {source_id} does not exist"
        if not target:
            return False, f"Target entity {target_id} does not exist"
        if source.lifecycle_state != LifecycleState.TRUSTED:
            return False, f"Source entity not TRUSTED (state: {source.lifecycle_state.value})"
        if target.lifecycle_state != LifecycleState.TRUSTED:
            return False, f"Target entity not TRUSTED (state: {target.lifecycle_state.value})"
        if source.tenant_id != tenant_id or target.tenant_id != tenant_id:
            return False, "Cross-tenant relationship not allowed"
        if source_id == target_id:
            return False, "Self-referential relationship not allowed"
        
        return True, None
    
    def validate_evidence(
        self, 
        evidence_span: str, 
        chunk_text: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Constraint 2: Evidence must actually exist in the chunk.
        """
        if not evidence_span:
            return False, "Evidence span is empty"
        if evidence_span not in chunk_text:
            evidence_lower = evidence_span.lower()
            chunk_lower = chunk_text.lower()
            if evidence_lower not in chunk_lower:
                return False, "Evidence span not found in chunk text"
        if len(evidence_span) < 10:
            return False, f"Evidence too short ({len(evidence_span)} chars, min 10)"
        if len(evidence_span) > 500:
            return False, f"Evidence too long ({len(evidence_span)} chars, max 500)"
        
        return True, None
    
    def validate_type_pair(
        self,
        source_type: str,
        target_type: str,
        relationship_type: str,
        ontology: List[OntologyRelationshipType]
    ) -> Tuple[bool, Optional[str], Optional[OntologyRelationshipType]]:
        """
        Constraint 3: Relationship type must be valid for this source/target pair.
        """
        ont = next((o for o in ontology if o.relationship_type == relationship_type), None)
        
        if not ont:
            return False, f"Unknown relationship type: {relationship_type}", None
        if not ont.is_active:
            return False, f"Relationship type {relationship_type} is disabled", None
        if source_type not in ont.valid_source_types:
            return False, f"{source_type} cannot be source of {relationship_type}", None
        if target_type not in ont.valid_target_types:
            return False, f"{target_type} cannot be target of {relationship_type}", None
        
        return True, None, ont
    
    def has_lexical_evidence(
        self, 
        evidence_span: str, 
        ont: OntologyRelationshipType
    ) -> bool:
        """
        Constraint 4: Check if evidence contains lexical patterns for this relationship type.
        """
        evidence_lower = evidence_span.lower()
        for pattern in ont.lexical_patterns:
            if pattern.lower() in evidence_lower:
                return True
        return False
    
    def get_disposition(
        self, 
        confidence: float, 
        has_lexical: bool, 
        ont: OntologyRelationshipType
    ) -> str:
        """
        Constraint 5: Determine what to do with this proposal based on confidence.
        """
        if confidence >= ont.auto_approve_confidence and has_lexical:
            return 'AUTO_APPROVE'
        elif confidence >= ont.min_confidence:
            return 'PENDING'
        else:
            return 'REJECT'
    
    def check_duplicate(
        self,
        source_id: UUID,
        target_id: UUID,
        relationship_type: str,
        tenant_id: UUID,
        chunk_id: UUID = None
    ) -> Tuple[bool, str]:
        """
        Constraint 7: Check if this relationship already exists.
        Returns (is_duplicate, reason).
        """
        # 1. Check existing relationships (global)
        existing = self.session.query(Relationship).filter(
            Relationship.tenant_id == tenant_id,
            Relationship.source_id == source_id,
            Relationship.target_id == target_id,
            Relationship.relationship_type == relationship_type,
            Relationship.lifecycle_state != LifecycleState.ARCHIVED
        ).first()
        
        if existing:
            return True, "RELATIONSHIP_EXISTS"
        
        # 2. Check for any pending/approved proposal (global dedup)
        global_proposal = self.session.query(ProposedRelationship).filter(
            ProposedRelationship.tenant_id == tenant_id,
            ProposedRelationship.source_entity_id == source_id,
            ProposedRelationship.target_entity_id == target_id,
            ProposedRelationship.relationship_type == relationship_type,
            ProposedRelationship.status.in_([
                ProposedRelationshipStatus.PENDING,
                ProposedRelationshipStatus.AUTO_APPROVED,
                ProposedRelationshipStatus.APPROVED
            ])
        ).first()
        
        if global_proposal:
            return True, "PROPOSAL_EXISTS_GLOBAL"
        
        # 3. Check for same chunk (unique constraint - prevents re-processing)
        if chunk_id:
            chunk_proposal = self.session.query(ProposedRelationship).filter(
                ProposedRelationship.tenant_id == tenant_id,
                ProposedRelationship.source_entity_id == source_id,
                ProposedRelationship.target_entity_id == target_id,
                ProposedRelationship.relationship_type == relationship_type,
                ProposedRelationship.source_chunk_id == chunk_id
            ).first()
            
            if chunk_proposal:
                return True, "PROPOSAL_EXISTS_CHUNK"
        
        return False, None
    
    def select_isolated_entities(
        self,
        tenant_id: UUID,
        batch_size: int = 100,
        entity_filter: Optional[Dict] = None
    ) -> List[Entity]:
        """Select isolated entities (no relationships) that have mentions, prioritized by mention count."""
        query = text("""
            SELECT e.id
            FROM entities e
            LEFT JOIN relationships r ON (e.id = r.source_id OR e.id = r.target_id)
                AND r.lifecycle_state != 'ARCHIVED'
            WHERE e.tenant_id = :tenant_id
              AND e.lifecycle_state = 'TRUSTED'
              AND r.id IS NULL
              AND EXISTS (SELECT 1 FROM entity_mentions em WHERE em.entity_id = e.id)
            ORDER BY (SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) DESC
            LIMIT :batch_size
        """)
        
        result = self.session.execute(query, {
            "tenant_id": str(tenant_id),
            "batch_size": batch_size
        })
        
        entity_ids = [row[0] for row in result.fetchall()]
        if not entity_ids:
            return []
        
        return self.session.query(Entity).filter(Entity.id.in_(entity_ids)).all()
    
    def get_chunks_for_entity(
        self, 
        entity_id: UUID, 
        tenant_id: UUID
    ) -> List[DocumentChunk]:
        """Get all document chunks mentioning this entity."""
        # Use subquery to get distinct chunk IDs (avoids JSON comparison issue)
        chunk_ids_subq = self.session.query(EntityMention.chunk_id).filter(
            EntityMention.entity_id == entity_id
        ).distinct().subquery()
        
        return self.session.query(DocumentChunk).filter(
            DocumentChunk.id.in_(chunk_ids_subq),
            DocumentChunk.tenant_id == tenant_id
        ).all()
    
    def find_candidate_entities(
        self, 
        chunk: DocumentChunk, 
        tenant_id: UUID
    ) -> List[CandidateEntity]:
        """Find all TRUSTED entities mentioned in this chunk."""
        mentions = self.session.query(EntityMention, Entity).join(
            Entity, Entity.id == EntityMention.entity_id
        ).filter(
            EntityMention.chunk_id == chunk.id,
            Entity.tenant_id == tenant_id,
            Entity.lifecycle_state == LifecycleState.TRUSTED
        ).all()
        
        candidates = []
        for idx, (mention, entity) in enumerate(mentions):
            candidates.append(CandidateEntity(
                id=entity.id,
                code=f"E{idx+1}",
                name=entity.name,
                entity_type=entity.entity_type,
                mention_text=mention.mention_text
            ))
        
        return candidates
    
    def build_extraction_prompt(
        self,
        chunk: DocumentChunk,
        candidates: List[CandidateEntity],
        ontology: List[OntologyRelationshipType],
        tenant_id: UUID
    ) -> str:
        """Build the user prompt for LLM extraction."""
        entity_list = "\n".join([
            f"- {c.code}: \"{c.name}\" (type: {c.entity_type})"
            for c in candidates
        ])
        
        rel_list = "\n".join([
            f"- {o.relationship_type}: {o.definition}\n  Valid: {o.valid_source_types} → {o.valid_target_types}"
            for o in ontology
        ])
        
        return f"""DOMAIN: {self.domain}
TENANT: {tenant_id}

ENTITY_LIST (you may ONLY use these — match by entity_code):
{entity_list}

ALLOWED_RELATIONSHIPS (you may ONLY use these types, listed from MOST SPECIFIC to LEAST SPECIFIC):
{rel_list}

⚠️ RELATED_TO is the LAST entry because it is a FALLBACK — only use it when NO specific type applies.

DOCUMENT CHUNK:
\"\"\"
{chunk.text}
\"\"\"

TASK:
Extract all EXPLICIT relationships between the entities above that are stated in this text.
Do not infer relationships that are not clearly expressed.

IMPORTANT: Choose the MOST SPECIFIC relationship type. Examples:
- "Emily Rodriguez leads the QA Department" → MANAGES (not RELATED_TO)
- "Mark Thompson oversees automated processes" → MANAGES (not RELATED_TO)
- "Payment Gateway depends on Redis Cache" → DEPENDS_ON (not RELATED_TO)
- "John works at Acme Corp" → WORKS_AT (not RELATED_TO)

OUTPUT FORMAT (JSON):
{{
  "relationships": [
    {{
      "source_entity_code": "E1",
      "target_entity_code": "E3",
      "relationship_type": "DEPENDS_ON",
      "confidence": 0.85,
      "evidence_span": "exact quote from document text"
    }}
  ]
}}

If no relationships can be identified with evidence, return:
{{"relationships": []}}"""

    def call_llm(self, user_prompt: str) -> Tuple[List[Dict], int]:
        """Call LLM and parse response."""
        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            tokens_used = response.usage.total_tokens if response.usage else 0
            content = response.choices[0].message.content
            
            try:
                parsed = json.loads(content)
                relationships = parsed.get("relationships", [])
                return relationships, tokens_used
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM response as JSON: {content[:200]}")
                return [], tokens_used
                
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return [], 0
    
    def validate_proposal(
        self,
        raw: Dict,
        chunk: DocumentChunk,
        candidates: List[CandidateEntity],
        ontology: List[OntologyRelationshipType],
        run: InferenceRun
    ) -> ValidationResult:
        """Validate a single proposed relationship against all constraints."""
        source = next((c for c in candidates if c.code == raw.get('source_entity_code')), None)
        target = next((c for c in candidates if c.code == raw.get('target_entity_code')), None)
        
        if not source or not target:
            return ValidationResult(False, "Entity code not in candidate list")
        
        valid, msg = self.validate_entities(source.id, target.id, run.tenant_id)
        if not valid:
            return ValidationResult(False, msg)
        
        evidence_span = raw.get('evidence_span', '')
        valid, msg = self.validate_evidence(evidence_span, chunk.text)
        if not valid:
            return ValidationResult(False, msg)
        
        relationship_type = raw.get('relationship_type', '')
        valid, msg, rel_ont = self.validate_type_pair(
            source.entity_type, target.entity_type, relationship_type, ontology
        )
        
        # Direction-flip: If original direction fails, try swapping source/target
        direction_flipped = False
        if not valid:
            valid_flipped, msg_flipped, rel_ont_flipped = self.validate_type_pair(
                target.entity_type, source.entity_type, relationship_type, ontology
            )
            if valid_flipped:
                # Swap source and target
                source, target = target, source
                rel_ont = rel_ont_flipped
                direction_flipped = True
                logger.debug(f"Direction flipped for {relationship_type}: {source.name} -> {target.name}")
            else:
                return ValidationResult(False, msg)
        
        has_lexical = self.has_lexical_evidence(evidence_span, rel_ont)
        
        confidence = float(raw.get('confidence', 0.5))
        disposition = self.get_disposition(confidence, has_lexical, rel_ont)
        if disposition == 'REJECT':
            return ValidationResult(False, f"Confidence {confidence} below threshold {rel_ont.min_confidence}")
        
        is_dup, dup_reason = self.check_duplicate(source.id, target.id, relationship_type, run.tenant_id, chunk.id)
        if is_dup:
            return ValidationResult(False, f"Duplicate: {dup_reason}")
        
        status = (ProposedRelationshipStatus.AUTO_APPROVED 
                  if disposition == 'AUTO_APPROVE' 
                  else ProposedRelationshipStatus.PENDING)
        
        proposal = ProposedRelationship(
            tenant_id=run.tenant_id,
            source_entity_id=source.id,
            target_entity_id=target.id,
            relationship_type=relationship_type,
            confidence=confidence,
            inference_run_id=run.id,
            source_document_id=chunk.document_id,
            source_chunk_id=chunk.id,
            evidence_span=evidence_span,
            inference_method=InferenceMethod.LLM_EXTRACTION,
            has_lexical_evidence=has_lexical,
            status=status
        )
        
        return ValidationResult(True, None, proposal)
    
    def process_chunk(
        self,
        entity: Entity,
        chunk: DocumentChunk,
        run: InferenceRun,
        ontology: List[OntologyRelationshipType]
    ) -> int:
        """Process a single chunk for relationship extraction."""
        candidates = self.find_candidate_entities(chunk, run.tenant_id)
        
        if len(candidates) < 2:
            chunk_record = InferenceRunChunk(
                run_id=run.id,
                chunk_id=chunk.id,
                entity_id=entity.id,
                status='NO_CANDIDATES',
                relationships_found=0
            )
            self.session.add(chunk_record)
            return 0
        
        prompt = self.build_extraction_prompt(chunk, candidates, ontology, run.tenant_id)
        
        raw_relationships, tokens_used = self.call_llm(prompt)
        run.llm_tokens_used += tokens_used
        run.estimated_cost_usd += tokens_used * 0.00000015  # gpt-4o-mini pricing
        
        validated_count = 0
        for raw in raw_relationships:
            result = self.validate_proposal(raw, chunk, candidates, ontology, run)
            if result.is_valid and result.proposal:
                self.session.add(result.proposal)
                run.relationships_proposed += 1
                validated_count += 1
                if result.proposal.status == ProposedRelationshipStatus.AUTO_APPROVED:
                    run.relationships_approved += 1
            else:
                logger.debug(f"Rejected proposal: {result.reason}")
        
        chunk_record = InferenceRunChunk(
            run_id=run.id,
            chunk_id=chunk.id,
            entity_id=entity.id,
            status='COMPLETED',
            relationships_found=validated_count
        )
        self.session.add(chunk_record)
        run.chunks_analyzed += 1
        
        return validated_count
    
    def already_processed(
        self, 
        run_id: UUID, 
        chunk_id: UUID, 
        entity_id: UUID
    ) -> bool:
        """Idempotency check - has this chunk been processed for this entity in this run?"""
        existing = self.session.query(InferenceRunChunk).filter(
            InferenceRunChunk.run_id == run_id,
            InferenceRunChunk.chunk_id == chunk_id,
            InferenceRunChunk.entity_id == entity_id
        ).first()
        return existing is not None
    
    def process_entity(
        self,
        entity: Entity,
        run: InferenceRun,
        ontology: List[OntologyRelationshipType]
    ) -> int:
        """Process a single entity: find its chunks, extract relationships."""
        chunks = self.get_chunks_for_entity(entity.id, run.tenant_id)
        
        total_found = 0
        for chunk in chunks:
            if self.already_processed(run.id, chunk.id, entity.id):
                continue
            
            try:
                found = self.process_chunk(entity, chunk, run, ontology)
                total_found += found
            except Exception as e:
                logger.error(f"Failed to process chunk {chunk.id}: {e}")
                error_record = InferenceRunChunk(
                    run_id=run.id,
                    chunk_id=chunk.id,
                    entity_id=entity.id,
                    status='FAILED',
                    error_message=str(e)
                )
                self.session.add(error_record)
        
        return total_found
    
    def start_run(
        self,
        tenant_id: UUID,
        batch_size: int = 100,
        entity_filter: Optional[Dict] = None
    ) -> InferenceRun:
        """Create and start a new inference run."""
        run = InferenceRun(
            tenant_id=tenant_id,
            batch_size=batch_size,
            entity_filter=entity_filter,
            prompt_version=PROMPT_VERSION,
            domain=self.domain,
            status=InferenceRunStatus.RUNNING
        )
        self.session.add(run)
        self.session.commit()
        
        logger.info(f"Started inference run {run.id} for tenant {tenant_id}")
        return run
    
    def run_inference(
        self,
        tenant_id: UUID,
        batch_size: int = 100,
        entity_filter: Optional[Dict] = None
    ) -> InferenceRun:
        """Main entry point: run relationship inference on isolated entities."""
        run = self.start_run(tenant_id, batch_size, entity_filter)
        
        try:
            ontology = self.get_ontology(tenant_id)
            if not ontology:
                raise ValueError(f"No ontology found for domain {self.domain}")
            
            entities = self.select_isolated_entities(tenant_id, batch_size, entity_filter)
            logger.info(f"Selected {len(entities)} isolated entities for processing")
            
            for entity in entities:
                self.process_entity(entity, run, ontology)
                run.entities_processed += 1
                
                if run.entities_processed % 10 == 0:
                    self.session.commit()
                    logger.info(f"Progress: {run.entities_processed}/{len(entities)} entities, "
                               f"{run.relationships_proposed} proposed, "
                               f"{run.relationships_approved} auto-approved")
            
            run.status = InferenceRunStatus.COMPLETED
            run.completed_at = datetime.utcnow()
            
        except Exception as e:
            run.status = InferenceRunStatus.FAILED
            run.error_message = str(e)
            logger.error(f"Inference run {run.id} failed: {e}")
        
        self.session.commit()
        logger.info(f"Completed inference run {run.id}: {run.relationships_proposed} proposed, "
                   f"{run.relationships_approved} auto-approved, "
                   f"${run.estimated_cost_usd:.4f} estimated cost")
        
        return run
    
    def get_pending_proposals(
        self,
        tenant_id: UUID,
        run_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[ProposedRelationship]:
        """Get pending proposals for review."""
        query = self.session.query(ProposedRelationship).filter(
            ProposedRelationship.tenant_id == tenant_id,
            ProposedRelationship.status == ProposedRelationshipStatus.PENDING
        )
        if run_id:
            query = query.filter(ProposedRelationship.inference_run_id == run_id)
        
        return query.order_by(ProposedRelationship.confidence.desc()).limit(limit).all()
    
    def approve_proposal(
        self,
        proposal_id: UUID,
        approved_by: str
    ) -> Optional[UUID]:
        """
        Approve a proposal and create relationship in STAGING.
        Constraint 6: Never direct to TRUSTED - goes to STAGING, Gardener promotes.
        """
        proposal = self.session.query(ProposedRelationship).filter(
            ProposedRelationship.id == proposal_id
        ).first()
        
        if not proposal:
            return None
        
        if proposal.status not in [ProposedRelationshipStatus.PENDING, ProposedRelationshipStatus.AUTO_APPROVED]:
            logger.warning(f"Cannot approve proposal {proposal_id} with status {proposal.status}")
            return None
        
        relationship = Relationship(
            tenant_id=proposal.tenant_id,
            source_id=proposal.source_entity_id,
            target_id=proposal.target_entity_id,
            relationship_type=proposal.relationship_type,
            confidence=proposal.confidence,
            lifecycle_state=LifecycleState.STAGING,
            properties={
                'source': 'inference_agent',
                'run_id': str(proposal.inference_run_id),
                'document_id': str(proposal.source_document_id),
                'chunk_id': str(proposal.source_chunk_id) if proposal.source_chunk_id else None,
                'evidence': proposal.evidence_span,
                'method': proposal.inference_method.value,
                'has_lexical_evidence': proposal.has_lexical_evidence,
                'corroboration_count': proposal.corroboration_count,
                'approved_by': approved_by,
                'approved_at': datetime.utcnow().isoformat()
            },
            source_sentence=proposal.evidence_span
        )
        self.session.add(relationship)
        
        proposal.status = ProposedRelationshipStatus.APPROVED
        proposal.reviewed_by = approved_by
        proposal.reviewed_at = datetime.utcnow()
        
        run = self.session.query(InferenceRun).filter(
            InferenceRun.id == proposal.inference_run_id
        ).first()
        if run:
            run.relationships_approved += 1
        
        self.session.commit()
        
        logger.info(f"Approved proposal {proposal_id} -> relationship {relationship.id}")
        return relationship.id
    
    def reject_proposal(
        self,
        proposal_id: UUID,
        rejected_by: str,
        reason: str
    ) -> bool:
        """Reject a proposal."""
        proposal = self.session.query(ProposedRelationship).filter(
            ProposedRelationship.id == proposal_id
        ).first()
        
        if not proposal:
            return False
        
        proposal.status = ProposedRelationshipStatus.REJECTED
        proposal.reviewed_by = rejected_by
        proposal.reviewed_at = datetime.utcnow()
        proposal.rejection_reason = reason
        
        run = self.session.query(InferenceRun).filter(
            InferenceRun.id == proposal.inference_run_id
        ).first()
        if run:
            run.relationships_rejected += 1
        
        self.session.commit()
        
        logger.info(f"Rejected proposal {proposal_id}: {reason}")
        return True
    
    def bulk_approve(
        self,
        tenant_id: UUID,
        min_confidence: float = 0.90,
        require_lexical: bool = True,
        approved_by: str = "system",
        run_id: Optional[UUID] = None
    ) -> List[UUID]:
        """Bulk approve proposals meeting criteria."""
        query = self.session.query(ProposedRelationship).filter(
            ProposedRelationship.tenant_id == tenant_id,
            ProposedRelationship.status == ProposedRelationshipStatus.PENDING,
            ProposedRelationship.confidence >= min_confidence
        )
        
        if require_lexical:
            query = query.filter(ProposedRelationship.has_lexical_evidence == True)
        if run_id:
            query = query.filter(ProposedRelationship.inference_run_id == run_id)
        
        proposals = query.all()
        approved_ids = []
        
        for proposal in proposals:
            rel_id = self.approve_proposal(proposal.id, approved_by)
            if rel_id:
                approved_ids.append(rel_id)
        
        logger.info(f"Bulk approved {len(approved_ids)} proposals")
        return approved_ids
    
    def rollback_run(
        self,
        run_id: UUID,
        reason: str,
        executed_by: str,
        delete_proposals: bool = True
    ) -> Dict:
        """Rollback an inference run, deleting created relationships and proposals."""
        run = self.session.query(InferenceRun).filter(InferenceRun.id == run_id).first()
        if not run:
            return {"error": "Run not found"}
        
        relationships_deleted = self.session.query(Relationship).filter(
            Relationship.properties['run_id'].astext == str(run_id)
        ).delete(synchronize_session='fetch')
        
        proposals_deleted = 0
        if delete_proposals:
            proposals_deleted = self.session.query(ProposedRelationship).filter(
                ProposedRelationship.inference_run_id == run_id
            ).delete(synchronize_session='fetch')
        
        run.status = InferenceRunStatus.ROLLED_BACK
        run.rollback_executed = True
        run.rollback_at = datetime.utcnow()
        run.rollback_reason = reason
        
        self.session.commit()
        
        logger.info(f"Rolled back run {run_id}: {relationships_deleted} relationships, "
                   f"{proposals_deleted} proposals deleted")
        
        return {
            "run_id": str(run_id),
            "status": "ROLLED_BACK",
            "relationships_deleted": relationships_deleted,
            "proposals_deleted": proposals_deleted
        }
    
    def get_metrics(self, tenant_id: UUID) -> Dict:
        """Get relationship density and inference metrics."""
        total_entities = self.session.query(Entity).filter(
            Entity.tenant_id == tenant_id,
            Entity.lifecycle_state == LifecycleState.TRUSTED
        ).count()
        
        total_relationships = self.session.query(Relationship).filter(
            Relationship.tenant_id == tenant_id,
            Relationship.lifecycle_state == LifecycleState.TRUSTED
        ).count()
        
        isolated = self.session.execute(text("""
            SELECT COUNT(*) FROM entities e
            LEFT JOIN relationships r ON (e.id = r.source_id OR e.id = r.target_id)
                AND r.lifecycle_state = 'TRUSTED'
            WHERE e.tenant_id = :tenant_id
              AND e.lifecycle_state = 'TRUSTED'
              AND r.id IS NULL
        """), {"tenant_id": str(tenant_id)}).scalar()
        
        pending = self.session.query(ProposedRelationship).filter(
            ProposedRelationship.tenant_id == tenant_id,
            ProposedRelationship.status == ProposedRelationshipStatus.PENDING
        ).count()
        
        density = total_relationships / total_entities if total_entities > 0 else 0
        
        return {
            "relationship_density": round(density, 3),
            "total_entities": total_entities,
            "total_relationships": total_relationships,
            "isolated_entities": isolated,
            "isolated_percent": round(isolated / total_entities * 100, 1) if total_entities > 0 else 0,
            "pending_proposals": pending
        }
