#!/usr/bin/env python3
"""
Temporal Test Data Synthesis Script

Creates backdated entities and relationships for testing the timeline slider feature.
Generates data spanning January 2025 through December 2025 with:
- Entities created at different time points
- Some entities with version history (superseded_by chains)
- Relationships that evolved over time
"""

import os
import sys
from datetime import datetime
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.context_foundry.models.schema import Entity, Relationship, LifecycleState

DATABASE_URL = os.environ.get('DATABASE_URL')

def create_temporal_data():
    """Create entities and relationships with varied temporal data."""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("=" * 60)
        print("TEMPORAL TEST DATA SYNTHESIS")
        print("=" * 60)
        
        # Define time points throughout 2025
        time_points = {
            'jan': datetime(2025, 1, 15, 10, 0, 0),
            'mar': datetime(2025, 3, 20, 14, 30, 0),
            'jun': datetime(2025, 6, 10, 9, 15, 0),
            'sep': datetime(2025, 9, 5, 16, 45, 0),
            'nov': datetime(2025, 11, 1, 11, 0, 0),
        }
        
        created_entities = {}
        
        # ============================================================
        # JANUARY 2025 - Initial Infrastructure Setup
        # ============================================================
        print("\n[JAN 2025] Creating initial infrastructure...")
        
        # Core Database Server
        db_server = Entity(
            id=uuid4(),
            name="Primary Database Cluster",
            entity_type="DATABASE",
            description="Main PostgreSQL cluster serving all production services",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.95,
            properties={"vendor": "PostgreSQL", "version": "15.2", "replicas": 3},
            valid_from=time_points['jan'],
            valid_to=None,
            extraction_method="temporal_synthesis"
        )
        session.add(db_server)
        created_entities['db_server'] = db_server
        
        # Platform Team
        platform_team = Entity(
            id=uuid4(),
            name="Platform Engineering Team",
            entity_type="TEAM",
            description="Core infrastructure and platform team",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.92,
            properties={"size": 8, "lead": "Sarah Chen"},
            valid_from=time_points['jan'],
            valid_to=None,
            extraction_method="temporal_synthesis"
        )
        session.add(platform_team)
        created_entities['platform_team'] = platform_team
        
        # ============================================================
        # MARCH 2025 - New Services Launch
        # ============================================================
        print("[MAR 2025] Launching new services...")
        
        # User Service
        user_service = Entity(
            id=uuid4(),
            name="User Authentication Service",
            entity_type="SERVICE",
            description="Handles user authentication, authorization, and session management",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.90,
            properties={"language": "Go", "framework": "Gin", "port": 8080},
            valid_from=time_points['mar'],
            valid_to=None,
            extraction_method="temporal_synthesis"
        )
        session.add(user_service)
        created_entities['user_service'] = user_service
        
        # API Gateway
        api_gateway = Entity(
            id=uuid4(),
            name="API Gateway",
            entity_type="COMPONENT",
            description="Central API gateway for routing and rate limiting",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.88,
            properties={"type": "Kong", "version": "3.4"},
            valid_from=time_points['mar'],
            valid_to=None,
            extraction_method="temporal_synthesis"
        )
        session.add(api_gateway)
        created_entities['api_gateway'] = api_gateway
        
        # ============================================================
        # JUNE 2025 - Expansion Phase
        # ============================================================
        print("[JUN 2025] Expanding infrastructure...")
        
        # Order Service
        order_service = Entity(
            id=uuid4(),
            name="Order Processing Service",
            entity_type="SERVICE",
            description="Processes customer orders and manages order lifecycle",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.85,
            properties={"language": "Java", "framework": "Spring Boot", "port": 8081},
            valid_from=time_points['jun'],
            valid_to=None,
            extraction_method="temporal_synthesis"
        )
        session.add(order_service)
        created_entities['order_service'] = order_service
        
        # Cache Layer
        cache_layer = Entity(
            id=uuid4(),
            name="Redis Cache Cluster",
            entity_type="COMPONENT",
            description="Distributed caching layer for session and data caching",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.87,
            properties={"vendor": "Redis", "version": "7.2", "nodes": 6},
            valid_from=time_points['jun'],
            valid_to=None,
            extraction_method="temporal_synthesis"
        )
        session.add(cache_layer)
        created_entities['cache_layer'] = cache_layer
        
        # DevOps Team
        devops_team = Entity(
            id=uuid4(),
            name="DevOps Team",
            entity_type="TEAM",
            description="Deployment automation and CI/CD team",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.91,
            properties={"size": 5, "lead": "Mike Johnson"},
            valid_from=time_points['jun'],
            valid_to=None,
            extraction_method="temporal_synthesis"
        )
        session.add(devops_team)
        created_entities['devops_team'] = devops_team
        
        # ============================================================
        # SEPTEMBER 2025 - Major Upgrade (Version History Demo)
        # ============================================================
        print("[SEP 2025] Major upgrade with version history...")
        
        # Create the OLD version of Notification Service (superseded)
        old_notification_id = uuid4()
        old_notification = Entity(
            id=old_notification_id,
            name="Notification Service v1",
            entity_type="SERVICE",
            description="Legacy notification service using email only",
            lifecycle_state=LifecycleState.ARCHIVED,
            confidence=0.75,
            properties={"language": "Python", "version": "1.0", "channels": ["email"]},
            valid_from=time_points['mar'],
            valid_to=time_points['sep'],
            change_reason="Superseded by v2 with multi-channel support",
            extraction_method="temporal_synthesis"
        )
        session.add(old_notification)
        
        # Create the NEW version of Notification Service
        new_notification_id = uuid4()
        new_notification = Entity(
            id=new_notification_id,
            name="Notification Service v2",
            entity_type="SERVICE",
            description="Multi-channel notification service with email, SMS, and push",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.93,
            properties={"language": "Python", "version": "2.0", "channels": ["email", "sms", "push"]},
            valid_from=time_points['sep'],
            valid_to=None,
            change_reason="Upgraded from v1 with multi-channel support",
            extraction_method="temporal_synthesis"
        )
        session.add(new_notification)
        created_entities['notification_service'] = new_notification
        
        # Link the supersession
        old_notification.superseded_by = new_notification_id
        
        # Incident from September
        sept_incident = Entity(
            id=uuid4(),
            name="INC-2025-SEP-001: Cache Failover Event",
            entity_type="INCIDENT",
            description="Redis primary node failure triggered automatic failover. 2-minute service degradation.",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.95,
            properties={"severity": "P2", "duration_minutes": 2, "affected_users": 1500, "resolved": True},
            valid_from=datetime(2025, 9, 12, 14, 30, 0),
            valid_to=None,
            extraction_method="temporal_synthesis"
        )
        session.add(sept_incident)
        created_entities['sept_incident'] = sept_incident
        
        # ============================================================
        # NOVEMBER 2025 - Recent Changes
        # ============================================================
        print("[NOV 2025] Recent infrastructure changes...")
        
        # Analytics Service
        analytics_service = Entity(
            id=uuid4(),
            name="Analytics Pipeline",
            entity_type="SERVICE",
            description="Real-time analytics and reporting service",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.82,
            properties={"language": "Scala", "framework": "Apache Flink", "port": 8085},
            valid_from=time_points['nov'],
            valid_to=None,
            extraction_method="temporal_synthesis"
        )
        session.add(analytics_service)
        created_entities['analytics_service'] = analytics_service
        
        # New Team Member (Person)
        new_engineer = Entity(
            id=uuid4(),
            name="Alex Rivera",
            entity_type="PERSON",
            description="Senior Backend Engineer, joined November 2025",
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.90,
            properties={"role": "Senior Backend Engineer", "start_date": "2025-11-01"},
            valid_from=datetime(2025, 11, 15, 9, 0, 0),
            valid_to=None,
            extraction_method="temporal_synthesis"
        )
        session.add(new_engineer)
        created_entities['new_engineer'] = new_engineer
        
        session.flush()
        
        # ============================================================
        # RELATIONSHIPS (with temporal awareness)
        # ============================================================
        print("\nCreating relationships...")
        
        relationships = [
            # January relationships
            {
                'source': created_entities['platform_team'].id,
                'target': created_entities['db_server'].id,
                'type': 'OWNS',
                'valid_from': time_points['jan'],
                'desc': 'Platform team owns the database cluster'
            },
            # March relationships
            {
                'source': created_entities['user_service'].id,
                'target': created_entities['db_server'].id,
                'type': 'DEPENDS_ON',
                'valid_from': time_points['mar'],
                'desc': 'User service depends on database'
            },
            {
                'source': created_entities['api_gateway'].id,
                'target': created_entities['user_service'].id,
                'type': 'ROUTES_TO',
                'valid_from': time_points['mar'],
                'desc': 'API gateway routes to user service'
            },
            # June relationships
            {
                'source': created_entities['order_service'].id,
                'target': created_entities['db_server'].id,
                'type': 'DEPENDS_ON',
                'valid_from': time_points['jun'],
                'desc': 'Order service depends on database'
            },
            {
                'source': created_entities['order_service'].id,
                'target': created_entities['cache_layer'].id,
                'type': 'DEPENDS_ON',
                'valid_from': time_points['jun'],
                'desc': 'Order service uses cache'
            },
            {
                'source': created_entities['user_service'].id,
                'target': created_entities['cache_layer'].id,
                'type': 'DEPENDS_ON',
                'valid_from': time_points['jun'],
                'desc': 'User service uses cache for sessions'
            },
            {
                'source': created_entities['devops_team'].id,
                'target': created_entities['api_gateway'].id,
                'type': 'OWNS',
                'valid_from': time_points['jun'],
                'desc': 'DevOps owns the API gateway'
            },
            # September relationships
            {
                'source': created_entities['notification_service'].id,
                'target': created_entities['db_server'].id,
                'type': 'DEPENDS_ON',
                'valid_from': time_points['sep'],
                'desc': 'Notification service v2 depends on database'
            },
            {
                'source': created_entities['sept_incident'].id,
                'target': created_entities['cache_layer'].id,
                'type': 'AFFECTS',
                'valid_from': datetime(2025, 9, 12, 14, 30, 0),
                'desc': 'Cache incident affected the cache layer'
            },
            # November relationships
            {
                'source': created_entities['analytics_service'].id,
                'target': created_entities['db_server'].id,
                'type': 'DEPENDS_ON',
                'valid_from': time_points['nov'],
                'desc': 'Analytics reads from database'
            },
            {
                'source': created_entities['new_engineer'].id,
                'target': created_entities['devops_team'].id,
                'type': 'MEMBER_OF',
                'valid_from': datetime(2025, 11, 15, 9, 0, 0),
                'desc': 'Alex joined DevOps team'
            },
        ]
        
        for rel in relationships:
            r = Relationship(
                id=uuid4(),
                source_id=rel['source'],
                target_id=rel['target'],
                relationship_type=rel['type'],
                description=rel['desc'],
                lifecycle_state=LifecycleState.TRUSTED,
                confidence=0.88,
                valid_from=rel['valid_from'],
                valid_to=None
            )
            session.add(r)
        
        session.commit()
        
        print("\n" + "=" * 60)
        print("SYNTHESIS COMPLETE")
        print("=" * 60)
        print(f"Created {len(created_entities)} entities across 5 time periods")
        print(f"Created {len(relationships)} relationships")
        print("\nTime periods covered:")
        for period, dt in time_points.items():
            print(f"  - {period.upper()}: {dt.strftime('%B %d, %Y')}")
        print("\nVersion history created:")
        print("  - Notification Service: v1 (Mar) -> v2 (Sep)")
        print("\nYou can now use the timeline slider to explore!")
        print("=" * 60)
        
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    create_temporal_data()
