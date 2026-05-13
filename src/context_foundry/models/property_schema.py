"""SQLAlchemy model for the property_facts table (Stage 3A).

Follows the Entity pattern from schema.py. Represents a single typed
attribute fact (revenue, budget, capacity, qubits, etc.) materialized
from an entity's properties JSON.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .schema import Base


class PropertyFact(Base):
    """A single typed attribute fact materialized from entity.properties."""

    __tablename__ = "property_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    entity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_name = Column(String(255), nullable=False)
    entity_type = Column(String(100), nullable=False)
    lifecycle_state = Column(String(20), nullable=False, default="STAGING")

    # Attribute data
    attribute_name = Column(String(255), nullable=False)
    attribute_value = Column(Text, nullable=False)
    numeric_value = Column(Float, nullable=True)
    unit = Column(String(100), nullable=True)
    value_type = Column(String(50), nullable=True)

    # Temporal qualifiers
    period = Column(String(50), nullable=True)
    fiscal_year = Column(String(10), nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)

    # Provenance
    source_document_id = Column(String(255), nullable=True)
    source_entity_properties = Column(JSONB, nullable=True)
    confidence = Column(Float, default=0.8)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id) if self.id else None,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "lifecycle_state": self.lifecycle_state,
            "attribute_name": self.attribute_name,
            "attribute_value": self.attribute_value,
            "numeric_value": self.numeric_value,
            "unit": self.unit,
            "value_type": self.value_type,
            "period": self.period,
            "fiscal_year": self.fiscal_year,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "source_document_id": self.source_document_id,
            "confidence": self.confidence,
        }
