# LEARNING FLOW — COMPLETE IMPLEMENTATION SPEC

## Overview

Learning Flow is Context Foundry's adaptive system that learns from user interactions to improve extraction quality over time. When users ask questions and the system can't answer (or answers incorrectly), Learning Flow captures that feedback and uses it to enhance future extractions.

**Core Principle:** "Organizational object permanence for AI" — the system refuses to hallucinate, admits uncertainty, and learns from gaps.

---

## The Problem Learning Flow Solves

### Current State
1. User uploads documents → Extraction runs once → Done
2. If extraction misses an entity (like CloudAI), it stays missed
3. User asks question → No answer → User frustrated
4. No feedback loop to improve

### With Learning Flow
1. User uploads documents → Extraction runs → Initial KG created
2. User asks question → System can't answer → Gap detected
3. System records the gap → Re-examines source documents
4. Targeted extraction fills the gap → KG improved
5. Next time user asks → Answer available

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LEARNING FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────┐  │
│  │  Query   │────▶│  Gap         │────▶│  Learning    │────▶│ Targeted  │  │
│  │  Engine  │     │  Detector    │     │  Queue       │     │ Extractor │  │
│  └──────────┘     └──────────────┘     └──────────────┘     └───────────┘  │
│       │                  │                    │                    │        │
│       │                  │                    │                    │        │
│       ▼                  ▼                    ▼                    ▼        │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────┐  │
│  │ Knowledge│◀────│  Feedback    │     │  Priority    │     │ Knowledge │  │
│  │  Graph   │     │  Store       │     │  Scorer      │     │   Graph   │  │
│  └──────────┘     └──────────────┘     └──────────────┘     └───────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Gap Detector
Identifies when the system can't answer a query or has low confidence.

### 2. Feedback Store
Records query gaps, user corrections, and learning opportunities.

### 3. Learning Queue
Prioritizes which gaps to address based on frequency and impact.

### 4. Targeted Extractor
Re-examines source documents with specific focus on filling identified gaps.

### 5. Priority Scorer
Ranks learning opportunities by importance.

---

## PHASE 1: DATABASE SCHEMA

Create migration: `migrations/018_learning_flow.sql`

```sql
-- =============================================================================
-- Migration 018: Learning Flow
-- =============================================================================
-- Purpose: Track query gaps, user feedback, and learning opportunities
-- Date: 2026-01-13
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Query Gaps: Questions the system couldn't answer well
-- -----------------------------------------------------------------------------
CREATE TABLE query_gaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES vaults(id) ON DELETE CASCADE,
    
    -- The query that revealed the gap
    query_text TEXT NOT NULL,
    query_type VARCHAR(50),  -- 'entity', 'relationship', 'attribute', 'general'
    
    -- What the user was looking for
    expected_entity_type VARCHAR(100),
    expected_entity_name VARCHAR(500),
    expected_relationship_type VARCHAR(100),
    
    -- System's response
    system_response TEXT,
    confidence_score FLOAT,
    
    -- Gap classification
    gap_type VARCHAR(50) NOT NULL,  -- 'missing_entity', 'missing_relationship', 'wrong_answer', 'low_confidence', 'no_answer'
    
    -- Resolution status
    status VARCHAR(20) DEFAULT 'OPEN',  -- 'OPEN', 'QUEUED', 'PROCESSING', 'RESOLVED', 'IGNORED'
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    user_id VARCHAR(100),  -- Optional: track which user encountered the gap
    session_id VARCHAR(100)
);

CREATE INDEX idx_query_gaps_tenant_status ON query_gaps(tenant_id, status);
CREATE INDEX idx_query_gaps_type ON query_gaps(gap_type, status);
CREATE INDEX idx_query_gaps_created ON query_gaps(created_at DESC);

-- -----------------------------------------------------------------------------
-- User Feedback: Explicit corrections from users
-- -----------------------------------------------------------------------------
CREATE TABLE user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES vaults(id) ON DELETE CASCADE,
    
    -- Reference to what's being corrected
    query_gap_id UUID REFERENCES query_gaps(id) ON DELETE SET NULL,
    entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
    relationship_id UUID REFERENCES relationships(id) ON DELETE SET NULL,
    
    -- The feedback
    feedback_type VARCHAR(50) NOT NULL,  -- 'correction', 'confirmation', 'rejection', 'addition'
    
    -- Correction details
    original_value TEXT,
    corrected_value TEXT,
    correction_field VARCHAR(100),  -- 'name', 'type', 'relationship', 'attribute'
    
    -- Context
    feedback_text TEXT,  -- User's explanation
    confidence FLOAT DEFAULT 1.0,  -- How confident is this feedback
    
    -- Status
    status VARCHAR(20) DEFAULT 'PENDING',  -- 'PENDING', 'APPLIED', 'REJECTED', 'REVIEWING'
    applied_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    user_id VARCHAR(100)
);

CREATE INDEX idx_user_feedback_tenant ON user_feedback(tenant_id, status);
CREATE INDEX idx_user_feedback_entity ON user_feedback(entity_id);

-- -----------------------------------------------------------------------------
-- Learning Queue: Prioritized list of extraction tasks
-- -----------------------------------------------------------------------------
CREATE TABLE learning_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES vaults(id) ON DELETE CASCADE,
    
    -- What to learn
    task_type VARCHAR(50) NOT NULL,  -- 'extract_entity', 'extract_relationship', 'verify_entity', 'expand_context'
    
    -- Target information
    target_entity_type VARCHAR(100),
    target_entity_name VARCHAR(500),
    target_relationship_type VARCHAR(100),
    search_terms TEXT[],  -- Keywords to look for in documents
    
    -- Source documents to re-examine
    document_ids UUID[],
    chunk_ids UUID[],
    
    -- Priority and scheduling
    priority INTEGER DEFAULT 50,  -- 0-100, higher = more important
    priority_reason TEXT,
    
    -- Frequency tracking (same gap reported multiple times = higher priority)
    occurrence_count INTEGER DEFAULT 1,
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    
    -- Related gaps
    query_gap_ids UUID[],
    
    -- Processing status
    status VARCHAR(20) DEFAULT 'PENDING',  -- 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    
    -- Results
    entities_found INTEGER DEFAULT 0,
    relationships_found INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_learning_queue_tenant_status ON learning_queue(tenant_id, status);
CREATE INDEX idx_learning_queue_priority ON learning_queue(priority DESC, created_at ASC) WHERE status = 'PENDING';

-- -----------------------------------------------------------------------------
-- Learning Results: What was learned from each task
-- -----------------------------------------------------------------------------
CREATE TABLE learning_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learning_task_id UUID NOT NULL REFERENCES learning_queue(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    
    -- What was found
    result_type VARCHAR(50) NOT NULL,  -- 'new_entity', 'new_relationship', 'updated_entity', 'no_change'
    
    -- Entity details (if applicable)
    entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
    entity_name VARCHAR(500),
    entity_type VARCHAR(100),
    
    -- Relationship details (if applicable)
    relationship_id UUID REFERENCES relationships(id) ON DELETE SET NULL,
    source_entity_name VARCHAR(500),
    relationship_type VARCHAR(100),
    target_entity_name VARCHAR(500),
    
    -- Source information
    source_chunk_id UUID,
    source_text TEXT,
    confidence FLOAT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_learning_results_task ON learning_results(learning_task_id);
CREATE INDEX idx_learning_results_entity ON learning_results(entity_id);

-- -----------------------------------------------------------------------------
-- Learning Patterns: Patterns discovered that improve extraction
-- -----------------------------------------------------------------------------
CREATE TABLE learning_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES vaults(id) ON DELETE CASCADE,  -- NULL = global pattern
    
    -- Pattern definition
    pattern_type VARCHAR(50) NOT NULL,  -- 'entity_pattern', 'relationship_pattern', 'section_pattern'
    pattern_name VARCHAR(200),
    pattern_regex TEXT,
    pattern_context TEXT,  -- e.g., "Found in BREAKOUT COMPANIES sections"
    
    -- What this pattern extracts
    extracts_entity_type VARCHAR(100),
    extracts_relationship_type VARCHAR(100),
    
    -- Performance metrics
    times_matched INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    accuracy FLOAT GENERATED ALWAYS AS (
        CASE WHEN times_matched > 0 
             THEN times_correct::FLOAT / times_matched 
             ELSE 0 
        END
    ) STORED,
    
    -- Status
    status VARCHAR(20) DEFAULT 'ACTIVE',  -- 'ACTIVE', 'TESTING', 'DISABLED'
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_learning_patterns_tenant ON learning_patterns(tenant_id, status);
CREATE INDEX idx_learning_patterns_type ON learning_patterns(pattern_type, status);

-- -----------------------------------------------------------------------------
-- View: Learning Dashboard Summary
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW learning_dashboard AS
SELECT 
    v.id as tenant_id,
    v.name as vault_name,
    
    -- Gap counts
    COUNT(DISTINCT qg.id) FILTER (WHERE qg.status = 'OPEN') as open_gaps,
    COUNT(DISTINCT qg.id) FILTER (WHERE qg.status = 'RESOLVED') as resolved_gaps,
    
    -- Feedback counts
    COUNT(DISTINCT uf.id) FILTER (WHERE uf.status = 'PENDING') as pending_feedback,
    COUNT(DISTINCT uf.id) FILTER (WHERE uf.status = 'APPLIED') as applied_feedback,
    
    -- Queue counts
    COUNT(DISTINCT lq.id) FILTER (WHERE lq.status = 'PENDING') as queued_tasks,
    COUNT(DISTINCT lq.id) FILTER (WHERE lq.status = 'COMPLETED') as completed_tasks,
    
    -- Learning metrics
    COALESCE(SUM(lr.entities_found), 0) as total_entities_learned,
    COALESCE(SUM(lr.relationships_found), 0) as total_relationships_learned
    
FROM vaults v
LEFT JOIN query_gaps qg ON qg.tenant_id = v.id
LEFT JOIN user_feedback uf ON uf.tenant_id = v.id
LEFT JOIN learning_queue lq ON lq.tenant_id = v.id
LEFT JOIN learning_results lr ON lr.tenant_id = v.id
GROUP BY v.id, v.name;

-- =============================================================================
-- End Migration 018
-- =============================================================================
```

---

## PHASE 2: GAP DETECTOR

Create file: `src/context_foundry/learning/gap_detector.py`

```python
"""
Gap Detector

Identifies when the system can't answer a query well and records the gap
for future learning.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import text

logger = logging.getLogger(__name__)


class GapType(str, Enum):
    MISSING_ENTITY = "missing_entity"
    MISSING_RELATIONSHIP = "missing_relationship"
    WRONG_ANSWER = "wrong_answer"
    LOW_CONFIDENCE = "low_confidence"
    NO_ANSWER = "no_answer"


class QueryType(str, Enum):
    ENTITY = "entity"  # "Who is the CEO?"
    RELATIONSHIP = "relationship"  # "Who reports to Sarah?"
    ATTRIBUTE = "attribute"  # "What is the CEO's salary?"
    GENERAL = "general"  # "Tell me about CloudAI"


class GapDetector:
    """Detects and records query gaps for learning"""
    
    # Confidence thresholds
    LOW_CONFIDENCE_THRESHOLD = 0.6
    NO_ANSWER_PATTERNS = [
        "i don't have",
        "no information",
        "not found",
        "cannot find",
        "don't see",
        "not mentioned",
        "no data",
        "unable to find",
        "not in the knowledge graph"
    ]
    
    def __init__(self, db_session):
        self.db = db_session
    
    def analyze_response(
        self,
        tenant_id: UUID,
        query_text: str,
        response_text: str,
        confidence: float,
        entities_used: List[str] = None,
        relationships_used: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a query response to detect gaps.
        
        Returns gap info if a gap is detected, None otherwise.
        """
        
        gap_type = None
        
        # Check for no answer
        if self._is_no_answer(response_text):
            gap_type = GapType.NO_ANSWER
        
        # Check for low confidence
        elif confidence < self.LOW_CONFIDENCE_THRESHOLD:
            gap_type = GapType.LOW_CONFIDENCE
        
        # If no gap detected, return None
        if not gap_type:
            return None
        
        # Classify the query
        query_type = self._classify_query(query_text)
        
        # Extract what was being looked for
        expected = self._extract_expected(query_text, query_type)
        
        # Record the gap
        gap_id = self._record_gap(
            tenant_id=tenant_id,
            query_text=query_text,
            query_type=query_type,
            gap_type=gap_type,
            response_text=response_text,
            confidence=confidence,
            expected=expected
        )
        
        logger.info(f"Gap detected: {gap_type.value} for query '{query_text[:50]}...'")
        
        return {
            "gap_id": str(gap_id),
            "gap_type": gap_type.value,
            "query_type": query_type.value,
            "expected": expected
        }
    
    def record_user_correction(
        self,
        tenant_id: UUID,
        query_gap_id: Optional[UUID],
        original_value: str,
        corrected_value: str,
        correction_field: str,
        feedback_text: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        relationship_id: Optional[UUID] = None
    ) -> UUID:
        """Record explicit user feedback/correction"""
        
        feedback_id = uuid4()
        
        self.db.execute(text("""
            INSERT INTO user_feedback (
                id, tenant_id, query_gap_id, entity_id, relationship_id,
                feedback_type, original_value, corrected_value, 
                correction_field, feedback_text
            ) VALUES (
                :id, :tenant_id, :gap_id, :entity_id, :rel_id,
                'correction', :original, :corrected, :field, :text
            )
        """), {
            "id": feedback_id,
            "tenant_id": tenant_id,
            "gap_id": query_gap_id,
            "entity_id": entity_id,
            "rel_id": relationship_id,
            "original": original_value,
            "corrected": corrected_value,
            "field": correction_field,
            "text": feedback_text
        })
        self.db.commit()
        
        logger.info(f"User correction recorded: {correction_field} '{original_value}' -> '{corrected_value}'")
        
        return feedback_id
    
    def _is_no_answer(self, response_text: str) -> bool:
        """Check if response indicates no answer was found"""
        response_lower = response_text.lower()
        return any(pattern in response_lower for pattern in self.NO_ANSWER_PATTERNS)
    
    def _classify_query(self, query_text: str) -> QueryType:
        """Classify the type of query"""
        query_lower = query_text.lower()
        
        # Entity queries
        if any(p in query_lower for p in ["who is", "what is", "tell me about"]):
            if "who" in query_lower:
                return QueryType.ENTITY
            return QueryType.GENERAL
        
        # Relationship queries
        if any(p in query_lower for p in ["reports to", "works for", "manages", "leads"]):
            return QueryType.RELATIONSHIP
        
        # Attribute queries
        if any(p in query_lower for p in ["salary", "compensation", "how much", "what is the"]):
            return QueryType.ATTRIBUTE
        
        return QueryType.GENERAL
    
    def _extract_expected(self, query_text: str, query_type: QueryType) -> Dict[str, Any]:
        """Extract what the user was likely looking for"""
        expected = {}
        query_lower = query_text.lower()
        
        # Extract role/title being asked about
        roles = ["ceo", "cto", "cfo", "coo", "cmo", "cio", "president", "director", 
                 "manager", "partner", "vp", "chief"]
        for role in roles:
            if role in query_lower:
                expected["entity_type"] = "PERSON"
                expected["role"] = role.upper()
                break
        
        # Extract entity name if mentioned
        # Simple heuristic: capitalized words that aren't common words
        import re
        capitalized = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query_text)
        common_words = {"Who", "What", "Tell", "About", "The", "Is", "Are", "Does"}
        names = [w for w in capitalized if w not in common_words]
        if names:
            expected["entity_name"] = names[0]
        
        return expected
    
    def _record_gap(
        self,
        tenant_id: UUID,
        query_text: str,
        query_type: QueryType,
        gap_type: GapType,
        response_text: str,
        confidence: float,
        expected: Dict[str, Any]
    ) -> UUID:
        """Record a gap in the database"""
        
        gap_id = uuid4()
        
        self.db.execute(text("""
            INSERT INTO query_gaps (
                id, tenant_id, query_text, query_type, gap_type,
                system_response, confidence_score,
                expected_entity_type, expected_entity_name
            ) VALUES (
                :id, :tenant_id, :query, :query_type, :gap_type,
                :response, :confidence,
                :entity_type, :entity_name
            )
        """), {
            "id": gap_id,
            "tenant_id": tenant_id,
            "query": query_text,
            "query_type": query_type.value,
            "gap_type": gap_type.value,
            "response": response_text[:2000],  # Truncate long responses
            "confidence": confidence,
            "entity_type": expected.get("entity_type"),
            "entity_name": expected.get("entity_name")
        })
        self.db.commit()
        
        return gap_id
    
    def get_open_gaps(self, tenant_id: UUID, limit: int = 20) -> List[Dict[str, Any]]:
        """Get open gaps for a tenant"""
        
        result = self.db.execute(text("""
            SELECT * FROM query_gaps
            WHERE tenant_id = :tenant_id AND status = 'OPEN'
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"tenant_id": tenant_id, "limit": limit})
        
        return [dict(r._mapping) for r in result.fetchall()]


def get_gap_detector(db_session) -> GapDetector:
    """Get gap detector with provided session"""
    return GapDetector(db_session)
```

---

## PHASE 3: LEARNING QUEUE MANAGER

Create file: `src/context_foundry/learning/queue_manager.py`

```python
"""
Learning Queue Manager

Manages the queue of learning tasks, prioritizes them, and tracks progress.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import text

logger = logging.getLogger(__name__)


class LearningQueueManager:
    """Manages the learning task queue"""
    
    # Priority weights
    FREQUENCY_WEIGHT = 2.0  # How much to boost priority per occurrence
    RECENCY_WEIGHT = 1.5   # Boost for recently reported gaps
    USER_FEEDBACK_WEIGHT = 3.0  # Boost when user explicitly corrected
    
    def __init__(self, db_session):
        self.db = db_session
    
    def queue_from_gap(self, gap_id: UUID) -> Optional[UUID]:
        """
        Create a learning task from a query gap.
        
        If a similar task already exists, increment its occurrence count
        and boost its priority instead of creating a duplicate.
        """
        
        # Get the gap details
        gap = self.db.execute(text("""
            SELECT * FROM query_gaps WHERE id = :gap_id
        """), {"gap_id": gap_id}).fetchone()
        
        if not gap:
            logger.warning(f"Gap {gap_id} not found")
            return None
        
        gap = dict(gap._mapping)
        
        # Check for existing similar task
        existing = self._find_similar_task(
            tenant_id=gap['tenant_id'],
            entity_name=gap.get('expected_entity_name'),
            entity_type=gap.get('expected_entity_type')
        )
        
        if existing:
            # Increment occurrence count and boost priority
            self._increment_task(existing['id'], gap_id)
            return existing['id']
        
        # Create new task
        task_id = self._create_task(gap)
        
        # Update gap status
        self.db.execute(text("""
            UPDATE query_gaps SET status = 'QUEUED' WHERE id = :gap_id
        """), {"gap_id": gap_id})
        self.db.commit()
        
        return task_id
    
    def queue_from_feedback(self, feedback_id: UUID) -> UUID:
        """Create a high-priority learning task from user feedback"""
        
        # Get feedback details
        feedback = self.db.execute(text("""
            SELECT * FROM user_feedback WHERE id = :feedback_id
        """), {"feedback_id": feedback_id}).fetchone()
        
        if not feedback:
            raise ValueError(f"Feedback {feedback_id} not found")
        
        feedback = dict(feedback._mapping)
        
        # Create high-priority task
        task_id = uuid4()
        base_priority = 80  # High base priority for user feedback
        
        self.db.execute(text("""
            INSERT INTO learning_queue (
                id, tenant_id, task_type, target_entity_name,
                search_terms, priority, priority_reason, query_gap_ids
            ) VALUES (
                :id, :tenant_id, 'verify_entity', :entity_name,
                :search_terms, :priority, :reason, :gap_ids
            )
        """), {
            "id": task_id,
            "tenant_id": feedback['tenant_id'],
            "entity_name": feedback['corrected_value'],
            "search_terms": [feedback['corrected_value']],
            "priority": base_priority,
            "reason": "User feedback correction",
            "gap_ids": [feedback['query_gap_id']] if feedback['query_gap_id'] else []
        })
        self.db.commit()
        
        logger.info(f"Created high-priority learning task {task_id} from user feedback")
        
        return task_id
    
    def get_next_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the next highest-priority tasks to process"""
        
        result = self.db.execute(text("""
            SELECT * FROM learning_queue
            WHERE status = 'PENDING'
            ORDER BY priority DESC, created_at ASC
            LIMIT :limit
        """), {"limit": limit})
        
        return [dict(r._mapping) for r in result.fetchall()]
    
    def start_task(self, task_id: UUID) -> None:
        """Mark a task as processing"""
        
        self.db.execute(text("""
            UPDATE learning_queue 
            SET status = 'PROCESSING', started_at = NOW()
            WHERE id = :task_id
        """), {"task_id": task_id})
        self.db.commit()
    
    def complete_task(
        self, 
        task_id: UUID, 
        entities_found: int = 0,
        relationships_found: int = 0
    ) -> None:
        """Mark a task as completed"""
        
        self.db.execute(text("""
            UPDATE learning_queue 
            SET status = 'COMPLETED', 
                completed_at = NOW(),
                entities_found = :entities,
                relationships_found = :relationships
            WHERE id = :task_id
        """), {
            "task_id": task_id,
            "entities": entities_found,
            "relationships": relationships_found
        })
        
        # Also resolve any associated gaps
        self.db.execute(text("""
            UPDATE query_gaps 
            SET status = 'RESOLVED', resolved_at = NOW()
            WHERE id = ANY(
                SELECT unnest(query_gap_ids) FROM learning_queue WHERE id = :task_id
            )
        """), {"task_id": task_id})
        
        self.db.commit()
        
        logger.info(f"Completed learning task {task_id}: {entities_found} entities, {relationships_found} relationships")
    
    def fail_task(self, task_id: UUID, error_message: str) -> None:
        """Mark a task as failed"""
        
        self.db.execute(text("""
            UPDATE learning_queue 
            SET status = 'FAILED', 
                completed_at = NOW(),
                error_message = :error
            WHERE id = :task_id
        """), {"task_id": task_id, "error": error_message[:1000]})
        self.db.commit()
        
        logger.error(f"Learning task {task_id} failed: {error_message}")
    
    def _find_similar_task(
        self, 
        tenant_id: UUID, 
        entity_name: Optional[str],
        entity_type: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Find an existing similar task"""
        
        if not entity_name:
            return None
        
        result = self.db.execute(text("""
            SELECT * FROM learning_queue
            WHERE tenant_id = :tenant_id
              AND status IN ('PENDING', 'PROCESSING')
              AND (
                  target_entity_name ILIKE :name
                  OR :name = ANY(search_terms)
              )
            LIMIT 1
        """), {
            "tenant_id": tenant_id,
            "name": f"%{entity_name}%"
        }).fetchone()
        
        return dict(result._mapping) if result else None
    
    def _increment_task(self, task_id: UUID, gap_id: UUID) -> None:
        """Increment occurrence count and boost priority"""
        
        self.db.execute(text("""
            UPDATE learning_queue 
            SET occurrence_count = occurrence_count + 1,
                last_seen_at = NOW(),
                priority = LEAST(100, priority + :boost),
                query_gap_ids = array_append(query_gap_ids, :gap_id)
            WHERE id = :task_id
        """), {
            "task_id": task_id,
            "boost": self.FREQUENCY_WEIGHT * 5,  # 10 point boost per occurrence
            "gap_id": gap_id
        })
        
        # Update gap status
        self.db.execute(text("""
            UPDATE query_gaps SET status = 'QUEUED' WHERE id = :gap_id
        """), {"gap_id": gap_id})
        
        self.db.commit()
        
        logger.info(f"Incremented task {task_id} occurrence, gap {gap_id} queued")
    
    def _create_task(self, gap: Dict[str, Any]) -> UUID:
        """Create a new learning task from a gap"""
        
        task_id = uuid4()
        
        # Determine task type and search terms
        task_type = "extract_entity"
        search_terms = []
        
        if gap.get('expected_entity_name'):
            search_terms.append(gap['expected_entity_name'])
        
        if gap.get('expected_entity_type'):
            search_terms.append(gap['expected_entity_type'])
        
        # Extract key terms from the query
        query_terms = self._extract_search_terms(gap['query_text'])
        search_terms.extend(query_terms)
        
        # Calculate initial priority
        priority = self._calculate_priority(gap)
        
        self.db.execute(text("""
            INSERT INTO learning_queue (
                id, tenant_id, task_type, 
                target_entity_type, target_entity_name, search_terms,
                priority, priority_reason, query_gap_ids
            ) VALUES (
                :id, :tenant_id, :task_type,
                :entity_type, :entity_name, :search_terms,
                :priority, :reason, :gap_ids
            )
        """), {
            "id": task_id,
            "tenant_id": gap['tenant_id'],
            "task_type": task_type,
            "entity_type": gap.get('expected_entity_type'),
            "entity_name": gap.get('expected_entity_name'),
            "search_terms": list(set(search_terms)),  # Deduplicate
            "priority": priority,
            "reason": f"Gap type: {gap['gap_type']}",
            "gap_ids": [gap['id']]
        })
        self.db.commit()
        
        logger.info(f"Created learning task {task_id} with priority {priority}")
        
        return task_id
    
    def _extract_search_terms(self, query_text: str) -> List[str]:
        """Extract search terms from query text"""
        import re
        
        # Remove common words
        stop_words = {
            "who", "what", "where", "when", "how", "is", "are", "the", 
            "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
            "tell", "me", "about", "does", "do", "can", "could", "would"
        }
        
        # Extract words
        words = re.findall(r'\b\w+\b', query_text.lower())
        
        # Filter and return
        return [w for w in words if w not in stop_words and len(w) > 2]
    
    def _calculate_priority(self, gap: Dict[str, Any]) -> int:
        """Calculate initial priority for a gap"""
        
        base_priority = 50
        
        # Boost for certain gap types
        if gap['gap_type'] == 'no_answer':
            base_priority += 10
        elif gap['gap_type'] == 'wrong_answer':
            base_priority += 20  # Higher priority for wrong answers
        
        # Boost for low confidence (user saw an uncertain answer)
        if gap.get('confidence_score') and gap['confidence_score'] < 0.5:
            base_priority += 10
        
        return min(100, base_priority)


def get_queue_manager(db_session) -> LearningQueueManager:
    """Get queue manager with provided session"""
    return LearningQueueManager(db_session)
```

---

## PHASE 4: TARGETED EXTRACTOR

Create file: `src/context_foundry/learning/targeted_extractor.py`

```python
"""
Targeted Extractor

Re-examines source documents to fill specific knowledge gaps.
Uses focused extraction prompts to find missing entities/relationships.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import text

logger = logging.getLogger(__name__)


class TargetedExtractor:
    """Performs targeted extraction to fill knowledge gaps"""
    
    def __init__(self, db_session, llm_client=None):
        self.db = db_session
        self.llm = llm_client
    
    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a learning task by performing targeted extraction.
        
        Returns results summary.
        """
        
        task_id = task['id']
        tenant_id = task['tenant_id']
        
        logger.info(f"Processing learning task {task_id}")
        
        # Get chunks to search
        chunks = self._get_relevant_chunks(
            tenant_id=tenant_id,
            search_terms=task.get('search_terms', []),
            document_ids=task.get('document_ids'),
            chunk_ids=task.get('chunk_ids')
        )
        
        if not chunks:
            logger.warning(f"No relevant chunks found for task {task_id}")
            return {"entities_found": 0, "relationships_found": 0, "chunks_searched": 0}
        
        logger.info(f"Found {len(chunks)} relevant chunks to search")
        
        # Perform targeted extraction on each chunk
        all_entities = []
        all_relationships = []
        
        for chunk in chunks:
            entities, relationships = self._extract_from_chunk(
                chunk=chunk,
                target_entity_name=task.get('target_entity_name'),
                target_entity_type=task.get('target_entity_type'),
                target_relationship_type=task.get('target_relationship_type'),
                search_terms=task.get('search_terms', [])
            )
            
            all_entities.extend(entities)
            all_relationships.extend(relationships)
        
        # Store results
        for entity in all_entities:
            self._store_entity_result(task_id, tenant_id, entity)
        
        for rel in all_relationships:
            self._store_relationship_result(task_id, tenant_id, rel)
        
        # Add to knowledge graph
        entities_added = self._add_entities_to_kg(tenant_id, all_entities)
        relationships_added = self._add_relationships_to_kg(tenant_id, all_relationships)
        
        return {
            "entities_found": len(all_entities),
            "relationships_found": len(all_relationships),
            "entities_added": entities_added,
            "relationships_added": relationships_added,
            "chunks_searched": len(chunks)
        }
    
    def _get_relevant_chunks(
        self,
        tenant_id: UUID,
        search_terms: List[str],
        document_ids: Optional[List[UUID]] = None,
        chunk_ids: Optional[List[UUID]] = None
    ) -> List[Dict[str, Any]]:
        """Get chunks relevant to the search terms"""
        
        # If specific chunks are specified, use those
        if chunk_ids:
            result = self.db.execute(text("""
                SELECT c.id, c.content, c.document_id, d.name as document_name
                FROM document_chunks c
                JOIN platform.documents d ON c.document_id = d.id
                WHERE c.id = ANY(:chunk_ids)
            """), {"chunk_ids": chunk_ids})
            return [dict(r._mapping) for r in result.fetchall()]
        
        # Build search query
        if search_terms:
            # Use full-text search or ILIKE
            search_pattern = '%' + '%'.join(search_terms) + '%'
            
            query = """
                SELECT c.id, c.content, c.document_id, d.name as document_name
                FROM document_chunks c
                JOIN platform.documents d ON c.document_id = d.id
                WHERE d.tenant_id = :tenant_id
            """
            
            params = {"tenant_id": tenant_id}
            
            if document_ids:
                query += " AND c.document_id = ANY(:doc_ids)"
                params["doc_ids"] = document_ids
            
            # Search for any of the terms
            term_conditions = []
            for i, term in enumerate(search_terms[:5]):  # Limit to 5 terms
                param_name = f"term_{i}"
                term_conditions.append(f"c.content ILIKE :{param_name}")
                params[param_name] = f"%{term}%"
            
            if term_conditions:
                query += f" AND ({' OR '.join(term_conditions)})"
            
            query += " LIMIT 20"
            
            result = self.db.execute(text(query), params)
            return [dict(r._mapping) for r in result.fetchall()]
        
        # Fallback: get all chunks for tenant
        result = self.db.execute(text("""
            SELECT c.id, c.content, c.document_id, d.name as document_name
            FROM document_chunks c
            JOIN platform.documents d ON c.document_id = d.id
            WHERE d.tenant_id = :tenant_id
            LIMIT 50
        """), {"tenant_id": tenant_id})
        
        return [dict(r._mapping) for r in result.fetchall()]
    
    def _extract_from_chunk(
        self,
        chunk: Dict[str, Any],
        target_entity_name: Optional[str],
        target_entity_type: Optional[str],
        target_relationship_type: Optional[str],
        search_terms: List[str]
    ) -> tuple[List[Dict], List[Dict]]:
        """
        Perform targeted extraction from a single chunk.
        
        Uses a focused prompt to find specific entities/relationships.
        """
        
        entities = []
        relationships = []
        
        content = chunk['content']
        
        # First, try pattern-based extraction (fast)
        pattern_entities = self._pattern_extract(
            content, 
            target_entity_name, 
            target_entity_type,
            search_terms
        )
        entities.extend(pattern_entities)
        
        # If we have an LLM and didn't find much with patterns, use LLM
        if self.llm and len(pattern_entities) == 0:
            llm_entities, llm_relationships = self._llm_extract(
                content,
                target_entity_name,
                target_entity_type,
                target_relationship_type,
                search_terms
            )
            entities.extend(llm_entities)
            relationships.extend(llm_relationships)
        
        # Add source information
        for entity in entities:
            entity['source_chunk_id'] = chunk['id']
            entity['source_document_id'] = chunk['document_id']
        
        for rel in relationships:
            rel['source_chunk_id'] = chunk['id']
        
        return entities, relationships
    
    def _pattern_extract(
        self,
        content: str,
        target_entity_name: Optional[str],
        target_entity_type: Optional[str],
        search_terms: List[str]
    ) -> List[Dict]:
        """Pattern-based extraction for common formats"""
        
        import re
        entities = []
        
        # If looking for a specific entity, check if it's mentioned
        if target_entity_name:
            # Case-insensitive search
            pattern = re.compile(re.escape(target_entity_name), re.IGNORECASE)
            matches = pattern.finditer(content)
            
            for match in matches:
                # Get context around the match
                start = max(0, match.start() - 100)
                end = min(len(content), match.end() + 100)
                context = content[start:end]
                
                entities.append({
                    'name': match.group(),
                    'entity_type': target_entity_type or 'UNKNOWN',
                    'confidence': 0.8,
                    'source_text': context,
                    'extraction_method': 'pattern'
                })
        
        # Portfolio company pattern: "COMPANY_NAME (Cohort N)"
        cohort_pattern = r'([A-Z][A-Za-z0-9]+)\s*\(Cohort\s+\d+\)'
        for match in re.finditer(cohort_pattern, content):
            entities.append({
                'name': match.group(1),
                'entity_type': 'PORTFOLIO_COMPANY',
                'confidence': 0.9,
                'source_text': match.group(0),
                'extraction_method': 'pattern'
            })
        
        # Person with title pattern: "Name - Title"
        title_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–—]\s*(CEO|CTO|CFO|COO|President|Director|Partner|Manager)'
        for match in re.finditer(title_pattern, content):
            entities.append({
                'name': match.group(1),
                'entity_type': 'PERSON',
                'confidence': 0.85,
                'source_text': match.group(0),
                'extraction_method': 'pattern',
                'attributes': {'title': match.group(2)}
            })
        
        return entities
    
    def _llm_extract(
        self,
        content: str,
        target_entity_name: Optional[str],
        target_entity_type: Optional[str],
        target_relationship_type: Optional[str],
        search_terms: List[str]
    ) -> tuple[List[Dict], List[Dict]]:
        """LLM-based targeted extraction"""
        
        # Build focused prompt
        prompt = self._build_extraction_prompt(
            content,
            target_entity_name,
            target_entity_type,
            target_relationship_type,
            search_terms
        )
        
        # Call LLM
        try:
            response = self.llm.complete(prompt)
            return self._parse_llm_response(response)
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return [], []
    
    def _build_extraction_prompt(
        self,
        content: str,
        target_entity_name: Optional[str],
        target_entity_type: Optional[str],
        target_relationship_type: Optional[str],
        search_terms: List[str]
    ) -> str:
        """Build a focused extraction prompt"""
        
        prompt = f"""You are an expert entity extractor. Your task is to find specific information in the following text.

TEXT:
{content[:3000]}

"""
        
        if target_entity_name:
            prompt += f"""
SPECIFIC TARGET: Find any mention of "{target_entity_name}" and extract:
- Full name/title
- Type (person, organization, etc.)
- Any attributes mentioned
- Any relationships to other entities
"""
        
        if target_entity_type:
            prompt += f"""
ENTITY TYPE FOCUS: Look specifically for {target_entity_type} entities.
"""
        
        if search_terms:
            prompt += f"""
SEARCH TERMS: Pay special attention to these terms: {', '.join(search_terms)}
"""
        
        prompt += """
OUTPUT FORMAT (JSON):
{
  "entities": [
    {"name": "...", "type": "...", "confidence": 0.0-1.0, "context": "..."}
  ],
  "relationships": [
    {"source": "...", "relationship": "...", "target": "...", "confidence": 0.0-1.0}
  ]
}

If nothing is found, return empty arrays.
"""
        
        return prompt
    
    def _parse_llm_response(self, response: str) -> tuple[List[Dict], List[Dict]]:
        """Parse LLM response into entities and relationships"""
        
        import json
        
        try:
            # Extract JSON from response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                entities = data.get('entities', [])
                relationships = data.get('relationships', [])
                
                # Mark as LLM-extracted
                for e in entities:
                    e['extraction_method'] = 'llm'
                for r in relationships:
                    r['extraction_method'] = 'llm'
                
                return entities, relationships
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
        
        return [], []
    
    def _store_entity_result(
        self, 
        task_id: UUID, 
        tenant_id: UUID, 
        entity: Dict
    ) -> None:
        """Store entity result for tracking"""
        
        self.db.execute(text("""
            INSERT INTO learning_results (
                learning_task_id, tenant_id, result_type,
                entity_name, entity_type, source_chunk_id,
                source_text, confidence
            ) VALUES (
                :task_id, :tenant_id, 'new_entity',
                :name, :type, :chunk_id,
                :source, :confidence
            )
        """), {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "name": entity['name'],
            "type": entity.get('entity_type', 'UNKNOWN'),
            "chunk_id": entity.get('source_chunk_id'),
            "source": entity.get('source_text', '')[:500],
            "confidence": entity.get('confidence', 0.5)
        })
    
    def _store_relationship_result(
        self, 
        task_id: UUID, 
        tenant_id: UUID, 
        rel: Dict
    ) -> None:
        """Store relationship result for tracking"""
        
        self.db.execute(text("""
            INSERT INTO learning_results (
                learning_task_id, tenant_id, result_type,
                source_entity_name, relationship_type, target_entity_name,
                source_chunk_id, confidence
            ) VALUES (
                :task_id, :tenant_id, 'new_relationship',
                :source, :rel_type, :target,
                :chunk_id, :confidence
            )
        """), {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "source": rel.get('source', ''),
            "rel_type": rel.get('relationship', ''),
            "target": rel.get('target', ''),
            "chunk_id": rel.get('source_chunk_id'),
            "confidence": rel.get('confidence', 0.5)
        })
    
    def _add_entities_to_kg(
        self, 
        tenant_id: UUID, 
        entities: List[Dict]
    ) -> int:
        """Add discovered entities to the knowledge graph"""
        
        added = 0
        
        for entity in entities:
            # Check if entity already exists
            existing = self.db.execute(text("""
                SELECT id FROM entities 
                WHERE tenant_id = :tenant_id 
                  AND UPPER(name) = UPPER(:name)
                LIMIT 1
            """), {
                "tenant_id": tenant_id,
                "name": entity['name']
            }).fetchone()
            
            if not existing:
                # Add new entity
                self.db.execute(text("""
                    INSERT INTO entities (id, tenant_id, name, entity_type, confidence, source)
                    VALUES (:id, :tenant_id, :name, :type, :confidence, 'learning_flow')
                """), {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "name": entity['name'],
                    "type": entity.get('entity_type', 'UNKNOWN'),
                    "confidence": entity.get('confidence', 0.5)
                })
                added += 1
        
        self.db.commit()
        return added
    
    def _add_relationships_to_kg(
        self, 
        tenant_id: UUID, 
        relationships: List[Dict]
    ) -> int:
        """Add discovered relationships to the knowledge graph"""
        
        added = 0
        
        for rel in relationships:
            # Find source and target entities
            source = self.db.execute(text("""
                SELECT id FROM entities 
                WHERE tenant_id = :tenant_id AND UPPER(name) = UPPER(:name)
                LIMIT 1
            """), {"tenant_id": tenant_id, "name": rel.get('source', '')}).fetchone()
            
            target = self.db.execute(text("""
                SELECT id FROM entities 
                WHERE tenant_id = :tenant_id AND UPPER(name) = UPPER(:name)
                LIMIT 1
            """), {"tenant_id": tenant_id, "name": rel.get('target', '')}).fetchone()
            
            if source and target:
                # Check if relationship exists
                existing = self.db.execute(text("""
                    SELECT id FROM relationships
                    WHERE source_id = :source AND target_id = :target
                      AND relationship_type = :rel_type
                    LIMIT 1
                """), {
                    "source": source.id,
                    "target": target.id,
                    "rel_type": rel.get('relationship', 'RELATED_TO')
                }).fetchone()
                
                if not existing:
                    self.db.execute(text("""
                        INSERT INTO relationships (
                            id, tenant_id, source_id, target_id, 
                            relationship_type, confidence
                        ) VALUES (
                            :id, :tenant_id, :source, :target, 
                            :rel_type, :confidence
                        )
                    """), {
                        "id": uuid4(),
                        "tenant_id": tenant_id,
                        "source": source.id,
                        "target": target.id,
                        "rel_type": rel.get('relationship', 'RELATED_TO'),
                        "confidence": rel.get('confidence', 0.5)
                    })
                    added += 1
        
        self.db.commit()
        return added


def get_targeted_extractor(db_session, llm_client=None) -> TargetedExtractor:
    """Get targeted extractor with provided session"""
    return TargetedExtractor(db_session, llm_client)
```

---

## PHASE 5: LEARNING FLOW ORCHESTRATOR

Create file: `src/context_foundry/learning/orchestrator.py`

```python
"""
Learning Flow Orchestrator

Coordinates the entire learning flow process:
1. Detect gaps from queries
2. Queue learning tasks
3. Process tasks with targeted extraction
4. Update knowledge graph
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID

from context_foundry.learning.gap_detector import get_gap_detector, GapDetector
from context_foundry.learning.queue_manager import get_queue_manager, LearningQueueManager
from context_foundry.learning.targeted_extractor import get_targeted_extractor, TargetedExtractor

logger = logging.getLogger(__name__)


class LearningFlowOrchestrator:
    """Orchestrates the learning flow process"""
    
    def __init__(self, db_session, llm_client=None):
        self.db = db_session
        self.gap_detector = get_gap_detector(db_session)
        self.queue_manager = get_queue_manager(db_session)
        self.extractor = get_targeted_extractor(db_session, llm_client)
    
    def on_query_response(
        self,
        tenant_id: UUID,
        query_text: str,
        response_text: str,
        confidence: float,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Hook to call after every query response.
        
        Detects gaps and queues learning tasks automatically.
        """
        
        # Detect any gaps
        gap = self.gap_detector.analyze_response(
            tenant_id=tenant_id,
            query_text=query_text,
            response_text=response_text,
            confidence=confidence,
            **kwargs
        )
        
        if gap:
            # Queue learning task
            task_id = self.queue_manager.queue_from_gap(UUID(gap['gap_id']))
            gap['task_id'] = str(task_id) if task_id else None
            
            logger.info(f"Gap detected and queued: {gap['gap_type']}")
        
        return gap
    
    def on_user_feedback(
        self,
        tenant_id: UUID,
        original_value: str,
        corrected_value: str,
        correction_field: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Hook to call when user provides explicit feedback.
        
        Creates high-priority learning task.
        """
        
        # Record the feedback
        feedback_id = self.gap_detector.record_user_correction(
            tenant_id=tenant_id,
            original_value=original_value,
            corrected_value=corrected_value,
            correction_field=correction_field,
            **kwargs
        )
        
        # Queue high-priority learning task
        task_id = self.queue_manager.queue_from_feedback(feedback_id)
        
        return {
            "feedback_id": str(feedback_id),
            "task_id": str(task_id),
            "status": "queued"
        }
    
    def process_learning_queue(self, limit: int = 5) -> Dict[str, Any]:
        """
        Process pending learning tasks.
        
        Call this periodically (e.g., every minute) or on-demand.
        """
        
        tasks = self.queue_manager.get_next_tasks(limit=limit)
        
        if not tasks:
            return {"processed": 0, "message": "No pending tasks"}
        
        results = []
        
        for task in tasks:
            task_id = task['id']
            
            try:
                # Mark as processing
                self.queue_manager.start_task(task_id)
                
                # Process the task
                result = self.extractor.process_task(task)
                
                # Mark as complete
                self.queue_manager.complete_task(
                    task_id,
                    entities_found=result.get('entities_found', 0),
                    relationships_found=result.get('relationships_found', 0)
                )
                
                results.append({
                    "task_id": str(task_id),
                    "status": "completed",
                    **result
                })
                
            except Exception as e:
                logger.error(f"Failed to process task {task_id}: {e}")
                self.queue_manager.fail_task(task_id, str(e))
                results.append({
                    "task_id": str(task_id),
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "processed": len(results),
            "results": results
        }
    
    def get_learning_status(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get learning flow status for a tenant"""
        
        from sqlalchemy import text
        
        result = self.db.execute(text("""
            SELECT * FROM learning_dashboard WHERE tenant_id = :tenant_id
        """), {"tenant_id": tenant_id}).fetchone()
        
        if result:
            return dict(result._mapping)
        
        return {
            "tenant_id": str(tenant_id),
            "open_gaps": 0,
            "queued_tasks": 0,
            "completed_tasks": 0
        }
    
    def trigger_learning(self, tenant_id: UUID) -> Dict[str, Any]:
        """
        Manually trigger learning for a tenant.
        
        Useful for batch processing or admin actions.
        """
        
        # Get open gaps
        gaps = self.gap_detector.get_open_gaps(tenant_id)
        
        # Queue any that aren't already queued
        queued = 0
        for gap in gaps:
            if gap['status'] == 'OPEN':
                self.queue_manager.queue_from_gap(gap['id'])
                queued += 1
        
        # Process the queue
        process_result = self.process_learning_queue(limit=10)
        
        return {
            "gaps_queued": queued,
            "tasks_processed": process_result['processed'],
            "results": process_result.get('results', [])
        }


def get_orchestrator(db_session, llm_client=None) -> LearningFlowOrchestrator:
    """Get orchestrator with provided session"""
    return LearningFlowOrchestrator(db_session, llm_client)
```

---

## PHASE 6: API ENDPOINTS

Add to your API router:

```python
from flask import Blueprint, request, jsonify
from sqlalchemy import text
from context_foundry.database import get_db_session
from context_foundry.learning.orchestrator import get_orchestrator

learning_bp = Blueprint('learning', __name__)


@learning_bp.route('/api/learning/status/<vault_id>', methods=['GET'])
def get_learning_status(vault_id):
    """Get learning flow status for a vault"""
    db = get_db_session()
    orchestrator = get_orchestrator(db)
    
    return jsonify(orchestrator.get_learning_status(vault_id))


@learning_bp.route('/api/learning/gaps/<vault_id>', methods=['GET'])
def get_gaps(vault_id):
    """Get open gaps for a vault"""
    db = get_db_session()
    orchestrator = get_orchestrator(db)
    
    gaps = orchestrator.gap_detector.get_open_gaps(vault_id)
    return jsonify(gaps)


@learning_bp.route('/api/learning/feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback/correction"""
    data = request.json
    db = get_db_session()
    orchestrator = get_orchestrator(db)
    
    result = orchestrator.on_user_feedback(
        tenant_id=data['vault_id'],
        original_value=data['original_value'],
        corrected_value=data['corrected_value'],
        correction_field=data['correction_field'],
        feedback_text=data.get('feedback_text')
    )
    
    return jsonify(result)


@learning_bp.route('/api/learning/trigger/<vault_id>', methods=['POST'])
def trigger_learning(vault_id):
    """Manually trigger learning for a vault"""
    db = get_db_session()
    orchestrator = get_orchestrator(db)
    
    result = orchestrator.trigger_learning(vault_id)
    return jsonify(result)


@learning_bp.route('/api/learning/process', methods=['POST'])
def process_queue():
    """Process pending learning tasks"""
    data = request.json or {}
    limit = data.get('limit', 5)
    
    db = get_db_session()
    orchestrator = get_orchestrator(db)
    
    result = orchestrator.process_learning_queue(limit=limit)
    return jsonify(result)


@learning_bp.route('/api/learning/dashboard', methods=['GET'])
def get_dashboard():
    """Get learning dashboard for all vaults"""
    db = get_db_session()
    
    result = db.execute(text("SELECT * FROM learning_dashboard")).fetchall()
    return jsonify([dict(r._mapping) for r in result])
```

---

## PHASE 7: INTEGRATION WITH QUERY ENGINE

Update your query handler to hook into Learning Flow:

```python
# In your query handler (e.g., query_handler.py)

from context_foundry.learning.orchestrator import get_orchestrator

def handle_query(tenant_id: UUID, query_text: str, db_session) -> Dict[str, Any]:
    """Handle a user query"""
    
    # ... existing query logic ...
    response_text = "..."  # Your query response
    confidence = 0.85  # Your confidence score
    
    # Hook into Learning Flow
    orchestrator = get_orchestrator(db_session)
    gap = orchestrator.on_query_response(
        tenant_id=tenant_id,
        query_text=query_text,
        response_text=response_text,
        confidence=confidence
    )
    
    # Include gap info in response (optional)
    result = {
        "answer": response_text,
        "confidence": confidence
    }
    
    if gap:
        result["learning"] = {
            "gap_detected": True,
            "gap_type": gap['gap_type'],
            "task_queued": gap.get('task_id') is not None
        }
    
    return result
```

---

## PHASE 8: SCHEDULER INTEGRATION

Add Learning Flow processing to your scheduler:

```python
# In your scheduler (e.g., scheduler.py)

from context_foundry.learning.orchestrator import get_orchestrator

def run_learning_cycle():
    """Run a learning cycle - call this periodically"""
    
    db = get_db_session()
    orchestrator = get_orchestrator(db)
    
    result = orchestrator.process_learning_queue(limit=10)
    
    logger.info(f"Learning cycle complete: {result['processed']} tasks processed")
    
    return result

# Add to scheduler (e.g., every 5 minutes)
# scheduler.add_job(run_learning_cycle, 'interval', minutes=5)
```

---

## VERIFICATION CHECKLIST

### Phase 1: Migration
```bash
psql -f migrations/018_learning_flow.sql
```
```sql
SELECT * FROM query_gaps LIMIT 1;
SELECT * FROM learning_queue LIMIT 1;
SELECT * FROM learning_dashboard;
```

### Phase 2-5: Components
```python
# Test gap detection
from context_foundry.learning.gap_detector import get_gap_detector
detector = get_gap_detector(db_session)
gap = detector.analyze_response(
    tenant_id=vault_id,
    query_text="Who is the CTO?",
    response_text="I don't have that information",
    confidence=0.3
)
print(gap)  # Should detect a gap

# Test queue manager
from context_foundry.learning.queue_manager import get_queue_manager
manager = get_queue_manager(db_session)
task_id = manager.queue_from_gap(gap['gap_id'])
print(task_id)  # Should return task UUID

# Test orchestrator
from context_foundry.learning.orchestrator import get_orchestrator
orchestrator = get_orchestrator(db_session)
result = orchestrator.process_learning_queue(limit=1)
print(result)  # Should show processed task
```

### Phase 6: API Endpoints
```bash
# Get learning status
curl http://localhost:8000/api/learning/status/{vault_id}

# Get gaps
curl http://localhost:8000/api/learning/gaps/{vault_id}

# Submit feedback
curl -X POST http://localhost:8000/api/learning/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "vault_id": "...",
    "original_value": "Elizabeth Morrison",
    "corrected_value": "Thomas Bradley",
    "correction_field": "CFO"
  }'

# Trigger learning
curl -X POST http://localhost:8000/api/learning/trigger/{vault_id}

# Get dashboard
curl http://localhost:8000/api/learning/dashboard
```

### End-to-End Test
1. Query something that doesn't exist → Gap should be detected
2. Check learning status → Should show open gap
3. Trigger learning → Should process gap
4. Query again → Should have answer (if found in documents)

---

## REPORT BACK

After implementation, confirm:

1. Migration applied?
2. Gap detector working?
3. Queue manager working?
4. Targeted extractor working?
5. Orchestrator coordinating all components?
6. API endpoints responding?
7. Query engine integrated?
8. Scheduler integration working?
9. End-to-end flow tested?
