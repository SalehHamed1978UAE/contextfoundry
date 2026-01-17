# Context Foundry - Cognitive Operating System for the Enterprise

## Overview
Context Foundry is a Cognitive Operating System for the Enterprise designed to provide AI systems with a coherent, evolving understanding of organizational reality. Its core purpose is to build a dynamic "World Model" that compounds knowledge over time, is grounded in verifiable sources, and remains trustworthy by admitting uncertainty. The project aims to create a domain-agnostic, single substrate for all enterprise AI applications, moving beyond static knowledge representations to a system that learns and adapts, ultimately enabling AI to reason over structured truth, eliminate hallucination, and provide reliable, context-aware answers.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture
Context Foundry is built around a **Tri-Memory System** consisting of Semantic Memory (knowledge graph), Episodic Memory (event timelines), and Symbolic Memory (rules, constraints). Facts within the system follow a **Fact Lifecycle** (STAGING, TRUSTED, ARCHIVED) and include `_layer`, `_confidence`, `_sources`, and `_lifecycle` metadata.

A core principle is **Context-Attached Knowledge**, where relationships are enriched with metadata like temporal validity and provenance. The system assembles a **Context Bundle** for AI applications, packaging focal entities, relationships, rules, and a confidence summary.

Key agents include:
- **GraphBuilderAgent**: Extracts entities and relationships.
- **RetrievalAgent**: Assembles the Context Bundle.
- **ReasoningAgent**: Utilizes LLMs over the Context Bundle.
- **ValidationAgent**: Applies symbolic rules.
- **GardenerAgent**: Maintains knowledge graph quality.
- **QueryTimeSemanticAgent**: Orchestrates retrieval and reasoning.

The **Query Flow** involves parsing, entity resolution, context bundle retrieval, LLM reasoning, symbolic validation, and response generation with confidence and provenance.

Architectural features include:
- **Tenant Context and RLS**: Enhanced `TenantSession` for Row-Level Security.
- **Query Pipeline**: Features `QueryClassifier`, `RoleResolver` (3-stage with fuzzy matching and document search), and `RetrievalRouter` (GRAPH_ONLY, DOCS_ONLY, HYBRID strategies with fallback).
- **Implicit Role Extraction**: `GraphBuilder` automatically creates `HOLDS_POSITION` relationships.
- **QA Verifier**: Two-layer verification (structural rules + LLM semantic check) for answer quality.
- **Dynamic Confidence Scoring**: Computed scores based on answer quality and evidence.
- **Source Attribution**: Extracts and displays sources from various tools.
- **Deterministic Document Fallback**: Automatic document search when KG lacks data.
- **Context Injection**: Passes `vault_context` for target entity resolution.
- **Extraction Hardening**: Post-processor (`ExtractionPostProcessor`) uses regex patterns to catch missed relationships (e.g., HOLDS_POSITION, HAS_COMPENSATION) after LLM extraction.
- **Role→Attribute/Relationship Query Chaining**: Query pipeline rewrites role-based queries (e.g., "CEO's salary") into person-specific queries, handling single and multi-matches with context prioritization.
- **Ambiguity Detection & Disambiguation**: Generalized pattern for handling multiple entity matches using `AmbiguityResult` and a `DisambiguationReasoner` (LLM-based) to determine the best match or request user clarification.
- **Extraction Job Tracking System**: Monitors extraction jobs with automatic timeout detection, retry logic (circuit breaker), and verification. It uses `ExtractionJobTracker`, `ExtractionCircuitBreaker`, and `ExtractionMonitor` to manage job lifecycle, retries, and health.
- **Ontology Foundry (Phase 1)**: A learning system that identifies unknown relationship/entity types as candidates, stores them in a `CandidateStore` with evidence and confidence, and routes them for potential future approval, preventing ingestion of unapproved types into the main KG.
- **Learning Flow**: An adaptive learning system that detects query gaps (`GapDetector`), prioritizes learning tasks (`LearningQueueManager`), and performs targeted extraction (`TargetedExtractor`) to improve knowledge graph quality, learning from query failures and user feedback.

## External Dependencies
- **Database:** PostgreSQL (with pgvector)
- **LLM:** OpenAI `gpt-4o-mini`
- **Vision LLM:** Anthropic Claude Sonnet 4
- **Vector Embeddings:** `text-embedding-3-small`
- **Web Framework:** Flask
- **Deployment:** Gunicorn
- **Authentication:** Magic Link, API Keys, JWT Sessions, Google OAuth