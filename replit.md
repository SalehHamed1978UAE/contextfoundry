# Context Foundry - Cognitive Operating System for the Enterprise

## Overview

Context Foundry is a **Cognitive Operating System for the Enterprise** designed to provide AI systems with a coherent, evolving understanding of organizational reality. It aims to solve limitations of traditional RAG, agent-based, fine-tuning, and triple KG approaches by building a dynamic "World Model" that compounds knowledge over time, is grounded in verifiable sources, and remains trustworthy by admitting uncertainty. The project's vision is to create a domain-agnostic, single substrate that serves all enterprise AI applications, moving beyond static knowledge representations to a system that learns and adapts. Key capabilities include a Tri-Memory System (Semantic, Episodic, Symbolic), a robust Fact Lifecycle (Staging, Trusted, Archived), and Context-Attached Knowledge, ensuring relationships carry rich metadata like temporal validity and provenance. The ultimate goal is to enable AI to reason over structured truth, eliminating hallucination and providing reliable, context-aware answers.

## User Preferences

- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture

Context Foundry is built around a **Tri-Memory System** comprising Semantic Memory (knowledge graph of entities, relationships, topology), Episodic Memory (event timelines, incident patterns), and Symbolic Memory (rules, constraints, safety invariants). Each fact within the system follows a **Fact Lifecycle**: STAGING (newly extracted facts), TRUSTED (validated facts used for reasoning), and ARCHIVED (superseded or stale facts). Facts include `_layer`, `_confidence`, `_sources`, and `_lifecycle` metadata.

A core architectural principle is **Context-Attached Knowledge**, where relationships are enriched with metadata such as `valid_from`, `valid_to`, `provenance_text`, `event_context`, and `qualifiers`. The system assembles a **Context Bundle** for AI applications, which is a structured package containing focal entities, relationships with their context, dependency paths, applicable rules, and a confidence summary.

The system employs several key agents:
- **GraphBuilderAgent**: Extracts entities and context-attached relationships from documents.
- **RetrievalAgent**: Assembles the Context Bundle from the tri-memory system.
- **ReasoningAgent**: Utilizes LLMs to reason over the Context Bundle.
- **ValidationAgent**: Applies symbolic rules and adjusts confidence.
- **GardenerAgent**: Maintains the quality of the knowledge graph (deduplication, promotion, pruning).
- **QueryTimeSemanticAgent**: Parses user queries, resolves entities, and orchestrates retrieval and reasoning.

The **Query Flow** involves parsing, entity resolution, context bundle retrieval, a sufficiency check, reasoning by an LLM, validation against symbolic rules, response generation (with confidence and provenance), and an asynchronous learning step to identify and address knowledge gaps.

## External Dependencies

- **Database:** PostgreSQL (with pgvector for embeddings)
- **LLM:** OpenAI `gpt-4o-mini`
- **Vision LLM:** Anthropic Claude Sonnet 4
- **Vector Embeddings:** `text-embedding-3-small`
- **Web Framework:** Flask
- **Deployment:** Gunicorn
- **Authentication:** Magic Link, API Keys, JWT Sessions, Google OAuth