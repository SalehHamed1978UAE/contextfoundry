#!/usr/bin/env python3
"""
Seed test fixtures for inference rule validation.

Creates 3 test patterns:
1. Transitive Chain: Frontend App → Auth Gateway → User Database
2. Co-occurrence: Payment Processor + Fraud Detection in 3 shared documents
3. Shared Dependency: Mobile App + Web App → Core API

Run: python scripts/seed_inference_fixtures.py
"""

import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.context_foundry.models.schema import Entity, Relationship, Document, LifecycleState, ValidationStatus
from src.context_foundry.memory.episodic import openai_embedding

DATABASE_URL = os.environ.get('DATABASE_URL')

FIXTURE_ENTITY_IDS = {
    'frontend_app': uuid.UUID('96f8b46b-e5a5-41ad-9579-11b67f7cf768'),
    'auth_gateway': uuid.UUID('b8d3c1f2-9a5e-4b7c-8d6f-1e2a3b4c5d6e'),
    'user_database': uuid.UUID('c9e4d2a3-0b6f-5c8d-9e7a-2f3b4c5d6e7f'),
    'payment_processor': uuid.UUID('ceaeb85e-b1ec-4930-b18f-953188ffecb7'),
    'fraud_detection': uuid.UUID('df9fc96f-c2fd-5a41-c29a-064299aafd8c'),
    'mobile_app': uuid.UUID('9e73a762-e1b9-4938-9d6a-a8aa516541a3'),
    'web_app': uuid.UUID('ae84b873-f2ca-5a49-ae7b-b9bb627652b4'),
    'core_api': uuid.UUID('be95c984-03db-6b5a-bf8c-cacc73863c15')
}

def get_session():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()

def entity_exists(session, entity_id):
    """Check if entity already exists."""
    return session.query(Entity).filter(Entity.id == entity_id).first() is not None

def seed_transitive_chain(session):
    """
    Fixture 1: Transitive Dependency Rule
    
    Frontend App → DEPENDS_ON → Auth Gateway → DEPENDS_ON → User Database
    
    User Database has no outgoing edges (is a frontier node).
    When expanding Frontend App and hitting User Database as frontier,
    the transitive rule should infer: Frontend App LIKELY_DEPENDS_ON User Database
    """
    print("\n=== Seeding Fixture 1: Transitive Chain ===")
    
    frontend_id = FIXTURE_ENTITY_IDS['frontend_app']
    auth_id = FIXTURE_ENTITY_IDS['auth_gateway']
    userdb_id = FIXTURE_ENTITY_IDS['user_database']
    
    if entity_exists(session, frontend_id):
        print("  Skipping - entities already exist")
        print(f"  Frontend App: {frontend_id}")
        print(f"  Auth Gateway: {auth_id}")
        print(f"  User Database: {userdb_id}")
        return frontend_id, auth_id, userdb_id
    
    frontend = Entity(
        id=frontend_id,
        name="Frontend App",
        entity_type="SERVICE",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="Main web frontend application",
        confidence=0.95,
        source_document_id="fixture-transitive-001",
        extracted_at=datetime.utcnow(),
        valid_from=datetime.utcnow()
    )
    
    auth = Entity(
        id=auth_id,
        name="Auth Gateway",
        entity_type="SERVICE",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="Authentication gateway service",
        confidence=0.95,
        source_document_id="fixture-transitive-001",
        extracted_at=datetime.utcnow(),
        valid_from=datetime.utcnow()
    )
    
    userdb = Entity(
        id=userdb_id,
        name="User Database",
        entity_type="DATABASE",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="User credentials and profile database",
        confidence=0.95,
        source_document_id="fixture-transitive-001",
        extracted_at=datetime.utcnow(),
        valid_from=datetime.utcnow()
    )
    
    session.add_all([frontend, auth, userdb])
    session.flush()
    
    rel1 = Relationship(
        id=uuid.uuid4(),
        source_id=frontend_id,
        target_id=auth_id,
        relationship_type="DEPENDS_ON",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="Frontend depends on Auth Gateway for user authentication",
        confidence=0.9,
        source_document_id="fixture-transitive-001",
        valid_from=datetime.utcnow()
    )
    
    rel2 = Relationship(
        id=uuid.uuid4(),
        source_id=auth_id,
        target_id=userdb_id,
        relationship_type="DEPENDS_ON",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="Auth Gateway depends on User Database for credential lookup",
        confidence=0.9,
        source_document_id="fixture-transitive-001",
        valid_from=datetime.utcnow()
    )
    
    session.add_all([rel1, rel2])
    session.commit()
    
    print(f"  Created: Frontend App ({frontend_id})")
    print(f"  Created: Auth Gateway ({auth_id})")
    print(f"  Created: User Database ({userdb_id})")
    print(f"  Created: Frontend App → DEPENDS_ON → Auth Gateway")
    print(f"  Created: Auth Gateway → DEPENDS_ON → User Database")
    
    return {
        'frontend_id': str(frontend_id),
        'auth_id': str(auth_id),
        'userdb_id': str(userdb_id)
    }

def seed_co_occurrence(session):
    """
    Fixture 2: Co-occurrence Rule
    
    Payment Processor and Fraud Detection are mentioned together in 3 documents.
    The co-occurrence rule should infer they are POTENTIALLY_RELATES_TO each other.
    
    Note: We create entities with matching source_document_ids to trigger the rule.
    """
    print("\n=== Seeding Fixture 2: Co-occurrence ===")
    
    doc_ids = [
        "incident-payment-fraud-01",
        "runbook-payment-flow",
        "architecture-payments"
    ]
    
    payment_id = uuid.uuid4()
    fraud_id = uuid.uuid4()
    
    payment = Entity(
        id=payment_id,
        name="Payment Processor",
        entity_type="SERVICE",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="Handles payment transactions and credit card processing",
        confidence=0.95,
        source_document_id=doc_ids[0],
        extracted_at=datetime.utcnow(),
        valid_from=datetime.utcnow()
    )
    
    fraud = Entity(
        id=fraud_id,
        name="Fraud Detection",
        entity_type="SERVICE",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="ML-based fraud detection and prevention service",
        confidence=0.95,
        source_document_id=doc_ids[0],
        extracted_at=datetime.utcnow(),
        valid_from=datetime.utcnow()
    )
    
    session.add_all([payment, fraud])
    session.flush()
    
    documents = []
    doc_contents = [
        "Incident Report: Payment Fraud Alert\n\nThe Payment Processor detected unusual activity which triggered the Fraud Detection system. Both services worked together to block the suspicious transaction.",
        "Payment Flow Runbook\n\nAll transactions go through the Payment Processor which integrates with Fraud Detection for real-time risk scoring. The Fraud Detection service analyzes patterns before Payment Processor completes the transaction.",
        "Payments Architecture Overview\n\nThe Payment Processor is the core payment handling service. Fraud Detection runs as a sidecar to Payment Processor, providing ML-based fraud scoring. Both Payment Processor and Fraud Detection share the same transaction database."
    ]
    
    for i, doc_id in enumerate(doc_ids):
        doc = Document(
            id=uuid.uuid4(),
            title=doc_id.replace("-", " ").title(),
            doc_type="runbook",
            content=doc_contents[i],
            doc_metadata={
                "mentions": ["Payment Processor", "Fraud Detection"],
                "fixture": "co-occurrence"
            },
            source_document_id=doc_id
        )
        documents.append(doc)
        
        try:
            embedding = openai_embedding(doc_contents[i])
            if embedding:
                doc.embedding = embedding
        except Exception as e:
            print(f"    Warning: Could not generate embedding for {doc_id}: {e}")
    
    session.add_all(documents)
    session.commit()
    
    print(f"  Created: Payment Processor ({payment_id}) [source: {doc_ids[0]}]")
    print(f"  Created: Fraud Detection ({fraud_id}) [source: {doc_ids[0]}]")
    print(f"  Created 3 documents mentioning both services:")
    for doc_id in doc_ids:
        print(f"    - {doc_id}")
    
    return {
        'payment_id': str(payment_id),
        'fraud_id': str(fraud_id),
        'doc_ids': doc_ids
    }

def seed_shared_dependency(session):
    """
    Fixture 3: Shared Dependency Rule
    
    Mobile App → DEPENDS_ON → Core API
    Web App → DEPENDS_ON → Core API
    
    Core API has no outgoing edges (is a frontier node).
    When expanding Mobile App and hitting Core API as frontier,
    the shared dependency rule should suggest: Mobile App POTENTIALLY_RELATED_VIA Web App
    """
    print("\n=== Seeding Fixture 3: Shared Dependency ===")
    
    mobile_id = uuid.uuid4()
    web_id = uuid.uuid4()
    core_id = uuid.uuid4()
    
    mobile = Entity(
        id=mobile_id,
        name="Mobile App",
        entity_type="SERVICE",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="iOS and Android mobile application",
        confidence=0.95,
        source_document_id="fixture-shared-001",
        extracted_at=datetime.utcnow(),
        valid_from=datetime.utcnow()
    )
    
    web = Entity(
        id=web_id,
        name="Web App",
        entity_type="SERVICE",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="Browser-based web application",
        confidence=0.95,
        source_document_id="fixture-shared-001",
        extracted_at=datetime.utcnow(),
        valid_from=datetime.utcnow()
    )
    
    core = Entity(
        id=core_id,
        name="Core API",
        entity_type="SERVICE",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="Central API gateway for all client applications",
        confidence=0.95,
        source_document_id="fixture-shared-001",
        extracted_at=datetime.utcnow(),
        valid_from=datetime.utcnow()
    )
    
    session.add_all([mobile, web, core])
    session.flush()
    
    rel1 = Relationship(
        id=uuid.uuid4(),
        source_id=mobile_id,
        target_id=core_id,
        relationship_type="DEPENDS_ON",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="Mobile App depends on Core API for backend services",
        confidence=0.9,
        source_document_id="fixture-shared-001",
        valid_from=datetime.utcnow()
    )
    
    rel2 = Relationship(
        id=uuid.uuid4(),
        source_id=web_id,
        target_id=core_id,
        relationship_type="DEPENDS_ON",
        lifecycle_state=LifecycleState.TRUSTED,
        validation_status=ValidationStatus.VALID,
        description="Web App depends on Core API for backend services",
        confidence=0.9,
        source_document_id="fixture-shared-001",
        valid_from=datetime.utcnow()
    )
    
    session.add_all([rel1, rel2])
    session.commit()
    
    print(f"  Created: Mobile App ({mobile_id})")
    print(f"  Created: Web App ({web_id})")
    print(f"  Created: Core API ({core_id})")
    print(f"  Created: Mobile App → DEPENDS_ON → Core API")
    print(f"  Created: Web App → DEPENDS_ON → Core API")
    
    return {
        'mobile_id': str(mobile_id),
        'web_id': str(web_id),
        'core_id': str(core_id)
    }

def main():
    print("=" * 60)
    print("INFERENCE RULE TEST FIXTURES")
    print("=" * 60)
    
    session = get_session()
    
    try:
        ids = {}
        
        ids['transitive'] = seed_transitive_chain(session)
        ids['co_occurrence'] = seed_co_occurrence(session)
        ids['shared'] = seed_shared_dependency(session)
        
        print("\n" + "=" * 60)
        print("FIXTURE SEEDING COMPLETE")
        print("=" * 60)
        
        print("\n=== Validation Commands ===")
        print("\nTest Transitive Rule (expand Frontend App):")
        print(f"  curl 'http://localhost:5000/api/graph/expand/{ids['transitive']['frontend_id']}?lifecycle_state=TRUSTED&include_speculative=true'")
        
        print("\nTest Co-occurrence Rule (expand Payment Processor):")
        print(f"  curl 'http://localhost:5000/api/graph/expand/{ids['co_occurrence']['payment_id']}?lifecycle_state=TRUSTED&include_speculative=true'")
        
        print("\nTest Shared Dependency Rule (expand Mobile App):")
        print(f"  curl 'http://localhost:5000/api/graph/expand/{ids['shared']['mobile_id']}?lifecycle_state=TRUSTED&include_speculative=true'")
        
        return ids
        
    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()
