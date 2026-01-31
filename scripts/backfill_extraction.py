#!/usr/bin/env python3
"""
Backfill Extraction Script for Context Foundry.

Phase 2.6: Extraction Hardening - Backfill for Existing Vaults.

Usage:
    python scripts/backfill_extraction.py --tenant-id <uuid>
    python scripts/backfill_extraction.py --all-tenants
    python scripts/backfill_extraction.py --tenant-id <uuid> --dry-run
    python scripts/backfill_extraction.py --tenant-id <uuid> --fix-gaps
"""
import argparse
import os
import sys
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.context_foundry.models.schema import (
    Entity, Relationship, Document, DocumentChunk,
    LifecycleState, get_session
)
from src.context_foundry.extraction.post_processor import (
    ExtractionPostProcessor,
    get_post_processor,
)
from src.context_foundry.extraction.gap_detector import (
    ExtractionGapDetector,
    standardize_relationship_type,
    RELATIONSHIP_TYPE_MAPPINGS,
)
from src.context_foundry.utils.logger import logger


@dataclass
class BackfillResult:
    """Result of backfill operation."""
    tenant_id: str
    documents_processed: int = 0
    relationships_added: int = 0
    relationships_standardized: int = 0
    entities_added: int = 0
    gaps_detected: int = 0
    gaps_fixed: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "tenant_id": self.tenant_id,
            "documents_processed": self.documents_processed,
            "relationships_added": self.relationships_added,
            "relationships_standardized": self.relationships_standardized,
            "entities_added": self.entities_added,
            "gaps_detected": self.gaps_detected,
            "gaps_fixed": self.gaps_fixed,
            "errors": self.errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.completed_at else None
            )
        }


class ExtractionBackfiller:
    """Backfills extraction for existing documents."""

    def __init__(self, session: Session, tenant_id: Optional[str] = None, dry_run: bool = False, fix_gaps: bool = False):
        self.session = session
        self.tenant_id = tenant_id
        self.dry_run = dry_run
        self.fix_gaps = fix_gaps
        self.post_processor = get_post_processor()

    def run(self) -> BackfillResult:
        """Run backfill for the configured tenant."""
        result = BackfillResult(tenant_id=self.tenant_id or "all", started_at=datetime.utcnow())
        try:
            standardized = self._standardize_relationship_types()
            result.relationships_standardized = standardized
            documents = self._get_documents()
            logger.info(f"[Backfill] Found {len(documents)} documents to process")
            for doc in documents:
                try:
                    doc_result = self._process_document(doc)
                    result.documents_processed += 1
                    result.relationships_added += doc_result["relationships_added"]
                    result.entities_added += doc_result["entities_added"]
                except Exception as e:
                    error_msg = f"Document {doc.id} failed: {str(e)}"
                    logger.error(f"[Backfill] {error_msg}")
                    result.errors.append(error_msg)
            gap_result = self._detect_gaps()
            result.gaps_detected = len(gap_result.gaps)
            if self.fix_gaps and not self.dry_run:
                fixed = self._fix_gaps(gap_result.gaps)
                result.gaps_fixed = fixed
            if not self.dry_run:
                self.session.commit()
                logger.info("[Backfill] Changes committed to database")
            else:
                self.session.rollback()
                logger.info("[Backfill] DRY RUN - no changes committed")
        except Exception as e:
            self.session.rollback()
            result.errors.append(str(e))
            logger.error(f"[Backfill] Fatal error: {e}")
        result.completed_at = datetime.utcnow()
        return result

    def _standardize_relationship_types(self) -> int:
        """Standardize all existing relationship types."""
        standardized_count = 0
        for old_type, new_type in RELATIONSHIP_TYPE_MAPPINGS.items():
            if old_type == new_type:
                continue
            query = self.session.query(Relationship).filter(Relationship.relationship_type == old_type)
            if self.tenant_id:
                query = query.filter(Relationship.tenant_id == self.tenant_id)
            relationships = query.all()
            if relationships:
                logger.info(f"[Backfill] Found {len(relationships)} relationships with type '{old_type}' -> '{new_type}'")
                if not self.dry_run:
                    for rel in relationships:
                        rel.relationship_type = new_type
                        standardized_count += 1
                    self.session.flush()
        return standardized_count

    def _get_documents(self) -> List[Document]:
        """Get all documents for the tenant."""
        query = self.session.query(Document)
        if self.tenant_id:
            query = query.filter(Document.tenant_id == self.tenant_id)
        return query.all()

    def _process_document(self, doc: Document) -> Dict:
        """Process a single document through post-processor."""
        result = {"relationships_added": 0, "entities_added": 0}
        content = doc.content
        if not content:
            chunks = self.session.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id
            ).order_by(DocumentChunk.chunk_index).all()
            if chunks:
                content = " ".join(c.text for c in chunks)
        if not content:
            logger.debug(f"[Backfill] Document {doc.id} has no content, skipping")
            return result
        existing_entities = self._get_existing_entities(doc.id)
        existing_relationships = self._get_existing_relationships(doc.id)
        post_result = self.post_processor.process(
            document_text=content,
            existing_entities=existing_entities,
            existing_relationships=existing_relationships
        )
        if post_result.new_relationships or post_result.new_entities:
            logger.info(f"[Backfill] Document {doc.id}: found {len(post_result.new_entities)} new entities, "
                       f"{len(post_result.new_relationships)} new relationships")
        if not self.dry_run:
            for new_entity in post_result.new_entities:
                entity = Entity(
                    id=uuid.uuid4(),
                    tenant_id=doc.tenant_id,
                    name=new_entity["name"],
                    entity_type=new_entity["entity_type"],
                    lifecycle_state=LifecycleState.STAGING,
                    confidence=new_entity.get("confidence", 0.85),
                    source_document_id=str(doc.id),
                    extraction_method="backfill_post_processor",
                    extracted_at=datetime.utcnow()
                )
                self.session.add(entity)
                result["entities_added"] += 1
            self.session.flush()
            for new_rel in post_result.new_relationships:
                source_id = self._resolve_entity_id(new_rel.source_name, doc.tenant_id)
                target_id = self._resolve_entity_id(new_rel.target_name, doc.tenant_id)
                if source_id and target_id:
                    relationship = Relationship(
                        id=uuid.uuid4(),
                        tenant_id=doc.tenant_id,
                        source_id=source_id,
                        target_id=target_id,
                        relationship_type=standardize_relationship_type(new_rel.relationship_type),
                        lifecycle_state=LifecycleState.STAGING,
                        confidence=new_rel.confidence,
                        source_document_id=str(doc.id),
                        source_sentence=new_rel.source_text[:500] if new_rel.source_text else None,
                        provenance_text=f"Backfill: {new_rel.pattern_name}",
                        extracted_at=datetime.utcnow()
                    )
                    self.session.add(relationship)
                    result["relationships_added"] += 1
            self.session.flush()
        return result

    def _get_existing_entities(self, doc_id) -> List[Dict]:
        """Get existing entities for a document."""
        entities = self.session.query(Entity).filter(Entity.source_document_id == str(doc_id)).all()
        return [{"name": e.name, "entity_type": e.entity_type} for e in entities]

    def _get_existing_relationships(self, doc_id) -> List[Dict]:
        """Get existing relationships for a document."""
        relationships = self.session.query(Relationship).filter(Relationship.source_document_id == str(doc_id)).all()
        result = []
        for rel in relationships:
            source = self.session.query(Entity).filter(Entity.id == rel.source_id).first()
            target = self.session.query(Entity).filter(Entity.id == rel.target_id).first()
            if source and target:
                result.append({
                    "source_name": source.name,
                    "target_name": target.name,
                    "relationship_type": rel.relationship_type
                })
        return result

    def _resolve_entity_id(self, name: str, tenant_id) -> Optional:
        """Resolve entity name to ID."""
        from sqlalchemy import func
        entity = self.session.query(Entity).filter(
            func.lower(Entity.name) == func.lower(name),
            Entity.tenant_id == tenant_id
        ).first()
        return entity.id if entity else None

    def _detect_gaps(self):
        """Run gap detection."""
        detector = ExtractionGapDetector(session=self.session, tenant_id=self.tenant_id)
        return detector.detect_all(include_trusted=True)

    def _fix_gaps(self, gaps) -> int:
        """Attempt to fix detected gaps."""
        fixed = 0
        for gap in gaps:
            logger.info(f"[Backfill] Gap: {gap.gap_type.value} - {gap.entity_name}: {gap.description}")
        return fixed


def main():
    parser = argparse.ArgumentParser(description="Backfill extraction for existing documents")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tenant-id", type=str, help="UUID of tenant/vault to process")
    group.add_argument("--all-tenants", action="store_true", help="Process all tenants")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--fix-gaps", action="store_true", help="Attempt to automatically fix detected gaps")
    args = parser.parse_args()
    session = get_session()
    if args.all_tenants:
        tenant_ids = session.execute(
            text("SELECT DISTINCT tenant_id FROM documents WHERE tenant_id IS NOT NULL")
        ).fetchall()
        results = []
        for (tenant_id,) in tenant_ids:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing tenant: {tenant_id}")
            logger.info(f"{'='*60}")
            backfiller = ExtractionBackfiller(
                session=session,
                tenant_id=str(tenant_id),
                dry_run=args.dry_run,
                fix_gaps=args.fix_gaps
            )
            result = backfiller.run()
            results.append(result)
            print(f"\nTenant {tenant_id}:")
            print(f"  Documents processed: {result.documents_processed}")
            print(f"  Relationships added: {result.relationships_added}")
            print(f"  Relationships standardized: {result.relationships_standardized}")
            print(f"  Entities added: {result.entities_added}")
            print(f"  Gaps detected: {result.gaps_detected}")
            if result.errors:
                print(f"  Errors: {len(result.errors)}")
    else:
        logger.info(f"Processing tenant: {args.tenant_id}")
        backfiller = ExtractionBackfiller(
            session=session,
            tenant_id=args.tenant_id,
            dry_run=args.dry_run,
            fix_gaps=args.fix_gaps
        )
        result = backfiller.run()
        print("\n" + "="*60)
        print("BACKFILL COMPLETE")
        print("="*60)
        print(f"Tenant: {args.tenant_id}")
        print(f"Documents processed: {result.documents_processed}")
        print(f"Relationships added: {result.relationships_added}")
        print(f"Relationships standardized: {result.relationships_standardized}")
        print(f"Entities added: {result.entities_added}")
        print(f"Gaps detected: {result.gaps_detected}")
        print(f"Duration: {(result.completed_at - result.started_at).total_seconds():.1f}s")
        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors[:10]:
                print(f"  - {error}")
            if len(result.errors) > 10:
                print(f"  ... and {len(result.errors) - 10} more")
    session.close()


if __name__ == "__main__":
    main()
