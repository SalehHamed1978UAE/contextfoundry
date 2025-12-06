# Context Foundry - Dual-System Cognitive Architecture

## Overview
Context Foundry implements a **dual-system cognitive architecture** for enterprise knowledge graph governance. It separates **Ontology Foundry** (schema governance) from **Context Foundry** (instance governance) to allow for different governance cadences, confidence thresholds, and agent responsibilities. This project aims to provide a robust and resilient framework for managing knowledge graphs, emphasizing structured truth delivery and a cognitive cycle approach to information processing.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture
The system is built around a dual-system architecture with distinct governance for schema and instance data.

**System Separation:**
- **Ontology Foundry (Schema Governance):** Governs types of entities and relationships, with a weekly/monthly cadence and high confidence (0.90+). It manages schema definitions, validation rules, and lifecycle states. Agents include TypeValidator, HierarchyEnforcer, and CollisionDetector.
- **Context Foundry (Knowledge Governance):** Governs specific instances of entities and relationships, with a continuous cadence (per document) and configurable confidence (0.70+). It manages entities, relationships, documents, and embeddings. Agents include Extractor, Gardener, Resolver, and QueryAgent.

**Database Schema Structure:**
- `ontology`: For schema governance (meta_ontology, types, relations, rules, versions, type_migration_map).
- `context`: For instance governance (entities, relationships, documents, embeddings, orphan_patterns).
- `shared`: For cross-system components (users, audit_log, message_queue, confidence_thresholds).

**Core Components & Features:**
- **Immutable Meta-Ontology (Layer 0):** Defines foundational types: OntologyType, OntologyRelation, ValidationRule, OntologyVersion, LifecycleState.
- **Ontology Lifecycle States:** Entities progress through states like PROPOSED, VALIDATING, CONTESTED, APPROVED, ACTIVE, DEPRECATED. Only ACTIVE types allow extraction.
- **SHACL-Inspired Validation Rules:** Six base rules enforce schema quality, naming conventions, hierarchy, and property validation.
- **Validation Agents:** RuleExecutor, TypeValidator, HierarchyEnforcer, and CollisionDetector ensure data integrity and consistency.
- **Approval Workflow:** Manages type approval with decision matrices, confidence-based routing, SLA deadlines, and auto-escalation.
- **TypeLifecycleManager:** Orchestrates validation agents and routes types to the ApprovalManager based on calculated confidence.
- **Message Bus:** A PostgreSQL-backed publish/subscribe system with exactly-once semantics for agent coordination across 16 event types, including retry logic and dead-letter queue.
- **OrphanDetector:** Identifies extraction patterns without matching active ontology types, providing a feedback loop from Context Foundry to Ontology Foundry, and supporting promotion to new PROPOSED types.
- **Context Bundle API:** Provides a public API for structured truth delivery, translating internal context bundles into Pydantic models. Supports fuzzy matching and graceful empty-state handling.
- **Schema Versioning & Deprecation:** Manages type versions, migrations, and deprecation processes with an audit trail, supporting multi-hop translation chains.
- **UI/UX:** A web interface built with `base.html` and a sidebar navigation reflecting the cognitive cycle phases (Ingest, Perceive, Memory, Reason, Express, Learn). Features include a command center reorganized by cognitive phase, a dashboard with metrics, AJAX polling for real-time updates, and agent status displays.

## External Dependencies
- **Database**: PostgreSQL (Neon for Replit)
- **LLM**: OpenAI gpt-4o-mini
- **Vector Embeddings**: pgvector with text-embedding-3-small
- **Web Framework**: Flask
- **Deployment**: Gunicorn