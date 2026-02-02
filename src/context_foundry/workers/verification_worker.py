"""
Evidence Layer Phase 2: LLM Verification Worker

Verifies facts against their supporting evidence using LLM.
Queries unverified facts from evidence_records, calls LLM to verify,
and stores verdicts in fact_verifications table.
"""
import os
import uuid
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..models.schema import (
    get_session,
    Entity,
    Relationship,
    EvidenceRecord,
    FactVerification,
    FactType,
    VerificationStatus,
    LifecycleState,
)
from ..utils.logger import logger


@dataclass
class VerificationConfig:
    """Configuration for the verification worker."""
    batch_size: int = 20
    max_facts_per_run: int = 100
    max_tokens_per_run: int = 50000
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    confidence_threshold: float = 0.7


@dataclass
class VerificationResult:
    """Result of a single fact verification."""
    fact_id: uuid.UUID
    fact_type: FactType
    status: VerificationStatus
    reason: str
    confidence: float


class VerificationWorker:
    """
    LLM-based verification worker for the Evidence Layer.
    
    Verifies facts against their supporting evidence by:
    1. Querying unverified facts from evidence_records
    2. Building verification prompts for each fact
    3. Calling LLM to verify evidence supports the fact
    4. Storing verdicts in fact_verifications table
    5. Updating fact's verified and evidence_verification_status columns
    """
    
    def __init__(
        self,
        session: Optional[Session] = None,
        tenant_id: Optional[str] = None,
        config: Optional[VerificationConfig] = None
    ):
        self.session = session or get_session(use_rls_role=False)
        self.tenant_id = tenant_id
        self.config = config or VerificationConfig()
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for verification worker")
        
        base_url = os.environ.get("OPENAI_BASE_URL")
        
        if base_url:
            self.llm_client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.llm_client = OpenAI(api_key=api_key)
        
        self.tokens_used = 0
        self.facts_processed = 0
    
    def run(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Run verification on unverified facts.
        
        Args:
            limit: Maximum number of facts to verify (overrides config.max_facts_per_run)
        
        Returns:
            Dictionary with verification statistics
        """
        max_facts = limit or self.config.max_facts_per_run
        
        logger.info(f"[VerificationWorker] Starting verification run (max_facts={max_facts}, batch_size={self.config.batch_size})")
        
        stats = {
            "facts_processed": 0,
            "verified": 0,
            "rejected": 0,
            "needs_review": 0,
            "errors": 0,
            "tokens_used": 0,
        }
        
        unverified_facts = self._get_unverified_facts(max_facts)
        
        if not unverified_facts:
            logger.info("[VerificationWorker] No unverified facts found")
            return stats
        
        logger.info(f"[VerificationWorker] Found {len(unverified_facts)} unverified facts to process")
        
        for i in range(0, len(unverified_facts), self.config.batch_size):
            batch = unverified_facts[i:i + self.config.batch_size]
            
            if self.tokens_used >= self.config.max_tokens_per_run:
                logger.warning(f"[VerificationWorker] Token limit reached ({self.tokens_used}/{self.config.max_tokens_per_run})")
                break
            
            batch_results = self._process_batch(batch)
            
            for result in batch_results:
                self._store_verdict(result)
                stats["facts_processed"] += 1
                
                if result.status == VerificationStatus.VERIFIED:
                    stats["verified"] += 1
                elif result.status == VerificationStatus.REJECTED:
                    stats["rejected"] += 1
                elif result.status == VerificationStatus.NEEDS_REVIEW:
                    stats["needs_review"] += 1
        
        try:
            self.session.commit()
            logger.info(f"[VerificationWorker] Committed {stats['facts_processed']} verification results")
        except Exception as e:
            self.session.rollback()
            logger.error(f"[VerificationWorker] Failed to commit: {e}")
            stats["errors"] += 1
        
        stats["tokens_used"] = self.tokens_used
        
        logger.info(f"[VerificationWorker] Completed: {stats}")
        return stats
    
    def _get_unverified_facts(self, limit: int) -> List[Dict[str, Any]]:
        """Get unverified facts with their evidence records."""
        query = self.session.query(EvidenceRecord)
        
        if self.tenant_id:
            tenant_uuid = uuid.UUID(self.tenant_id) if isinstance(self.tenant_id, str) else self.tenant_id
            query = query.filter(EvidenceRecord.tenant_id == tenant_uuid)
        
        already_verified_subq = select(FactVerification.fact_id).where(
            FactVerification.verification_status != VerificationStatus.UNVERIFIED
        ).scalar_subquery()
        
        query = query.filter(~EvidenceRecord.fact_id.in_(already_verified_subq))
        
        evidence_records = query.limit(limit).all()
        
        facts = []
        for record in evidence_records:
            fact_info = self._get_fact_info(record.fact_type, record.fact_id)
            if fact_info:
                facts.append({
                    "evidence_record": record,
                    "fact_info": fact_info,
                })
        
        return facts
    
    def _get_fact_info(self, fact_type: FactType, fact_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get fact description based on type."""
        if fact_type == FactType.ENTITY:
            entity = self.session.query(Entity).filter(Entity.id == fact_id).first()
            if entity:
                return {
                    "type": "entity",
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "description": f"Entity '{entity.name}' of type {entity.entity_type}",
                    "model": entity,
                }
        elif fact_type == FactType.RELATIONSHIP:
            rel = self.session.query(Relationship).filter(Relationship.id == fact_id).first()
            if rel:
                source = self.session.query(Entity).filter(Entity.id == rel.source_id).first()
                target = self.session.query(Entity).filter(Entity.id == rel.target_id).first()
                source_name = source.name if source else "Unknown"
                target_name = target.name if target else "Unknown"
                return {
                    "type": "relationship",
                    "source": source_name,
                    "target": target_name,
                    "relationship_type": rel.relationship_type,
                    "description": f"Relationship: {source_name} --[{rel.relationship_type}]--> {target_name}",
                    "model": rel,
                }
        return None
    
    def _process_batch(self, batch: List[Dict[str, Any]]) -> List[VerificationResult]:
        """Process a batch of facts for verification."""
        results = []
        
        for fact in batch:
            try:
                result = self._verify_single_fact(fact)
                results.append(result)
            except Exception as e:
                logger.error(f"[VerificationWorker] Error verifying fact {fact['evidence_record'].fact_id}: {e}")
                results.append(VerificationResult(
                    fact_id=fact["evidence_record"].fact_id,
                    fact_type=fact["evidence_record"].fact_type,
                    status=VerificationStatus.NEEDS_REVIEW,
                    reason=f"Verification error: {str(e)}",
                    confidence=0.0
                ))
        
        return results
    
    def _verify_single_fact(self, fact: Dict[str, Any]) -> VerificationResult:
        """Verify a single fact against its evidence using LLM."""
        evidence_record = fact["evidence_record"]
        fact_info = fact["fact_info"]
        
        prompt = self._build_verification_prompt(
            evidence_text=evidence_record.evidence_text,
            fact_description=fact_info["description"]
        )
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=150
            )
            
            if response.usage:
                self.tokens_used += response.usage.total_tokens
            
            content = response.choices[0].message.content.strip()
            
            return self._parse_verification_response(
                content,
                evidence_record.fact_id,
                evidence_record.fact_type
            )
            
        except Exception as e:
            logger.error(f"[VerificationWorker] LLM call failed: {e}")
            raise
    
    def _build_verification_prompt(self, evidence_text: str, fact_description: str) -> str:
        """Build the verification prompt for the LLM."""
        return f"""Given the evidence: "{evidence_text}"

Does it support this fact: "{fact_description}"?

Respond in exactly this format:
Answer: yes/no/uncertain
Explanation: <brief reason in one sentence>

Rules:
- Answer "yes" if the evidence clearly supports the fact
- Answer "no" if the evidence contradicts or does not mention the fact
- Answer "uncertain" if the evidence is ambiguous or incomplete"""
    
    def _parse_verification_response(
        self,
        content: str,
        fact_id: uuid.UUID,
        fact_type: FactType
    ) -> VerificationResult:
        """Parse LLM response into verification result."""
        content_lower = content.lower()
        
        explanation = ""
        if "explanation:" in content_lower:
            explanation = content.split("Explanation:", 1)[-1].strip()
            if not explanation:
                explanation = content.split("explanation:", 1)[-1].strip()
        
        if "answer: yes" in content_lower or content_lower.startswith("yes"):
            return VerificationResult(
                fact_id=fact_id,
                fact_type=fact_type,
                status=VerificationStatus.VERIFIED,
                reason=explanation or "Evidence supports the fact",
                confidence=0.9
            )
        elif "answer: no" in content_lower or content_lower.startswith("no"):
            return VerificationResult(
                fact_id=fact_id,
                fact_type=fact_type,
                status=VerificationStatus.REJECTED,
                reason=explanation or "Evidence does not support the fact",
                confidence=0.9
            )
        else:
            return VerificationResult(
                fact_id=fact_id,
                fact_type=fact_type,
                status=VerificationStatus.NEEDS_REVIEW,
                reason=explanation or "Verification uncertain, needs human review",
                confidence=0.5
            )
    
    def _store_verdict(self, result: VerificationResult) -> None:
        """Store verification verdict and update fact status."""
        tenant_uuid = uuid.UUID(self.tenant_id) if self.tenant_id else None
        
        existing = self.session.query(FactVerification).filter(
            and_(
                FactVerification.fact_id == result.fact_id,
                FactVerification.fact_type == result.fact_type
            )
        ).first()
        
        if existing:
            existing.verification_status = result.status
            existing.verification_reason = result.reason
            existing.verifier_model = self.config.model
            existing.confidence = result.confidence
            existing.created_at = datetime.utcnow()
        else:
            verification = FactVerification(
                id=uuid.uuid4(),
                tenant_id=tenant_uuid,
                fact_type=result.fact_type,
                fact_id=result.fact_id,
                verification_status=result.status,
                verification_reason=result.reason,
                verifier_model=self.config.model,
                confidence=result.confidence,
            )
            self.session.add(verification)
        
        self._update_fact_status(result)
    
    def _update_fact_status(self, result: VerificationResult) -> None:
        """Update the verified and evidence_verification_status on the fact."""
        if result.fact_type == FactType.ENTITY:
            entity = self.session.query(Entity).filter(Entity.id == result.fact_id).first()
            if entity:
                entity.verified = (result.status == VerificationStatus.VERIFIED)
                entity.evidence_verification_status = result.status
                logger.debug(f"[VerificationWorker] Updated entity {entity.name}: verified={entity.verified}")
        
        elif result.fact_type == FactType.RELATIONSHIP:
            rel = self.session.query(Relationship).filter(Relationship.id == result.fact_id).first()
            if rel:
                rel.verified = (result.status == VerificationStatus.VERIFIED)
                rel.evidence_verification_status = result.status
                logger.debug(f"[VerificationWorker] Updated relationship {result.fact_id}: verified={rel.verified}")


def main():
    """CLI entry point for verification worker."""
    parser = argparse.ArgumentParser(description="Run LLM verification on unverified facts")
    parser.add_argument("--tenant-id", type=str, help="Tenant ID to filter facts")
    parser.add_argument("--limit", type=int, default=10, help="Maximum facts to verify (default: 10)")
    parser.add_argument("--batch-size", type=int, default=20, help="Batch size for processing (default: 20)")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="LLM model to use (default: gpt-4o-mini)")
    
    args = parser.parse_args()
    
    config = VerificationConfig(
        batch_size=args.batch_size,
        max_facts_per_run=args.limit,
        model=args.model,
    )
    
    worker = VerificationWorker(
        tenant_id=args.tenant_id,
        config=config
    )
    
    stats = worker.run(limit=args.limit)
    
    print("\n=== Verification Results ===")
    print(f"Facts processed: {stats['facts_processed']}")
    print(f"Verified: {stats['verified']}")
    print(f"Rejected: {stats['rejected']}")
    print(f"Needs review: {stats['needs_review']}")
    print(f"Errors: {stats['errors']}")
    print(f"Tokens used: {stats['tokens_used']}")


if __name__ == "__main__":
    main()
