# Learning Flow Integration Spec
**Date:** 2026-01-13
**Status:** Ready for Implementation

---

## Problem Statement

Learning Flow components exist but are not connected to the query pipeline:
- `gap_detector.py` ✅ exists
- `queue_manager.py` ✅ exists
- `targeted_extractor.py` ✅ exists
- `orchestrator.py` ✅ exists
- **Learning tables are empty** (0 gaps, 0 queue items)

**Root Cause:** No integration point between query execution and gap detection.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         QUERY PIPELINE                               │
│                                                                      │
│  User Query ──► Retrieval ──► Reasoning ──► Response                │
│                                    │                                 │
│                                    ▼                                 │
│                         ┌──────────────────┐                        │
│                         │ Response Analyzer │ ◄── NEW COMPONENT     │
│                         └────────┬─────────┘                        │
│                                  │                                   │
│                    ┌─────────────┼─────────────┐                    │
│                    ▼             ▼             ▼                    │
│              Low Confidence  Missing Info  Entity Gap               │
│                    │             │             │                    │
│                    └─────────────┼─────────────┘                    │
│                                  ▼                                   │
└──────────────────────────────────┼──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        LEARNING FLOW                                 │
│                                                                      │
│  ┌──────────────┐    ┌───────────────┐    ┌────────────────────┐   │
│  │ Gap Detector │───►│ Queue Manager │───►│ Targeted Extractor │   │
│  └──────────────┘    └───────────────┘    └────────────────────┘   │
│                                                      │               │
│                                                      ▼               │
│                                           ┌──────────────────┐      │
│                                           │ Knowledge Graph  │      │
│                                           │    Updated       │      │
│                                           └──────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Integration Points

### 1. Response Analyzer (NEW)

Create a new component that analyzes query responses for gaps.

**File:** `src/context_foundry/learning/response_analyzer.py`

```python
"""
Response Analyzer - Detects gaps in query responses and triggers Learning Flow.
"""

import logging
import re
from typing import Optional, Dict, Any, List
from uuid import UUID
from dataclasses import dataclass

from src.context_foundry.learning.gap_detector import GapDetector
from src.context_foundry.learning.queue_manager import LearningQueueManager

logger = logging.getLogger(__name__)


@dataclass
class GapSignal:
    """Represents a detected gap in a query response."""
    gap_type: str  # 'low_confidence' | 'missing_info' | 'entity_not_found' | 'relationship_gap'
    query: str
    confidence: float
    missing_elements: List[str]
    source_documents: List[UUID]


class ResponseAnalyzer:
    """
    Analyzes query responses to detect knowledge gaps.
    Triggers Learning Flow when gaps are detected.
    """

    # Phrases indicating missing information
    MISSING_INFO_PATTERNS = [
        r"does not specify",
        r"no information",
        r"not mentioned",
        r"not provided",
        r"cannot find",
        r"no data available",
        r"information is not included",
        r"not included in the retrieved",
        r"could not find",
        r"unable to determine",
    ]

    # Confidence thresholds
    LOW_CONFIDENCE_THRESHOLD = 0.70
    GAP_TRIGGER_THRESHOLD = 0.60

    def __init__(
        self,
        session,
        tenant_id: UUID,
        gap_detector: Optional[GapDetector] = None,
        queue_manager: Optional[LearningQueueManager] = None
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.gap_detector = gap_detector or GapDetector(session, tenant_id)
        self.queue_manager = queue_manager or LearningQueueManager(session, tenant_id)

        # Compile regex patterns
        self._missing_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.MISSING_INFO_PATTERNS
        ]

    def analyze_response(
        self,
        query: str,
        response: str,
        confidence: float,
        retrieved_chunks: List[Dict],
        entities_used: List[Dict]
    ) -> Optional[GapSignal]:
        """
        Analyze a query response for knowledge gaps.

        Args:
            query: The original user query
            response: The generated response text
            confidence: Response confidence score (0-1)
            retrieved_chunks: List of chunks used in retrieval
            entities_used: List of entities referenced in response

        Returns:
            GapSignal if gap detected, None otherwise
        """
        gap_signals = []

        # Check 1: Low confidence
        if confidence < self.LOW_CONFIDENCE_THRESHOLD:
            gap_signals.append({
                'type': 'low_confidence',
                'severity': 1 - confidence,
                'detail': f'Response confidence {confidence:.0%} below threshold'
            })

        # Check 2: Missing information phrases
        missing_matches = self._detect_missing_info_phrases(response)
        if missing_matches:
            gap_signals.append({
                'type': 'missing_info',
                'severity': 0.8,
                'detail': f'Found {len(missing_matches)} missing info indicators',
                'matches': missing_matches
            })

        # Check 3: Entity not found patterns
        entity_gaps = self._detect_entity_gaps(query, entities_used)
        if entity_gaps:
            gap_signals.append({
                'type': 'entity_not_found',
                'severity': 0.9,
                'detail': f'Query mentions entities not in KG: {entity_gaps}',
                'missing_entities': entity_gaps
            })

        # Check 4: Relationship gaps (query asks about relationships we don't have)
        relationship_gaps = self._detect_relationship_gaps(query, response)
        if relationship_gaps:
            gap_signals.append({
                'type': 'relationship_gap',
                'severity': 0.85,
                'detail': f'Missing relationship types: {relationship_gaps}'
            })

        # If no gaps detected, return None
        if not gap_signals:
            logger.debug(f"No gaps detected for query: {query[:50]}...")
            return None

        # Aggregate gaps into signal
        max_severity = max(g['severity'] for g in gap_signals)
        gap_types = [g['type'] for g in gap_signals]

        # Get source documents from chunks
        source_docs = list(set(
            chunk.get('document_id')
            for chunk in retrieved_chunks
            if chunk.get('document_id')
        ))

        # Extract missing elements
        missing_elements = []
        for gap in gap_signals:
            if 'missing_entities' in gap:
                missing_elements.extend(gap['missing_entities'])
            if 'matches' in gap:
                missing_elements.extend(gap['matches'][:3])  # Limit

        gap_signal = GapSignal(
            gap_type=gap_types[0],  # Primary gap type
            query=query,
            confidence=confidence,
            missing_elements=missing_elements[:10],  # Limit
            source_documents=[UUID(d) for d in source_docs if d]
        )

        logger.info(
            f"Gap detected: type={gap_signal.gap_type}, "
            f"confidence={confidence:.0%}, "
            f"missing={len(gap_signal.missing_elements)} elements"
        )

        return gap_signal

    def _detect_missing_info_phrases(self, response: str) -> List[str]:
        """Find phrases indicating missing information."""
        matches = []
        for pattern in self._missing_patterns:
            if pattern.search(response):
                matches.append(pattern.pattern)
        return matches

    def _detect_entity_gaps(
        self,
        query: str,
        entities_used: List[Dict]
    ) -> List[str]:
        """Detect entities mentioned in query but not found in KG."""
        # Extract potential entity mentions from query
        # (simplified - could use NER for better results)
        query_words = set(query.split())

        # Common entity indicators
        entity_indicators = ['CEO', 'CFO', 'CTO', 'COO', 'CMO', 'CIO', 'President',
                          'Director', 'Manager', 'Partner', 'Lead', 'Head']

        # Check if query asks about a role we didn't find
        gaps = []
        for indicator in entity_indicators:
            if indicator.lower() in query.lower():
                # Check if we found an entity with this role
                found = any(
                    indicator.lower() in str(e.get('entity_type', '')).lower() or
                    indicator.lower() in str(e.get('name', '')).lower()
                    for e in entities_used
                )
                if not found:
                    gaps.append(indicator)

        return gaps

    def _detect_relationship_gaps(
        self,
        query: str,
        response: str
    ) -> List[str]:
        """Detect queries about relationships we couldn't answer."""
        relationship_queries = [
            (r'who reports to', 'REPORTS_TO'),
            (r'reports to whom', 'REPORTS_TO'),
            (r'works (at|for)', 'WORKS_AT'),
            (r'manages', 'MANAGES'),
            (r'leads', 'LEADS'),
            (r'owns', 'OWNS'),
            (r'invested in', 'INVESTED_IN'),
        ]

        gaps = []
        query_lower = query.lower()

        for pattern, rel_type in relationship_queries:
            if re.search(pattern, query_lower):
                # Check if response indicates we couldn't answer
                if any(p.search(response) for p in self._missing_patterns):
                    gaps.append(rel_type)

        return gaps

    def trigger_learning_flow(self, gap_signal: GapSignal) -> bool:
        """
        Trigger the Learning Flow for a detected gap.

        Returns:
            True if gap was queued for learning, False otherwise
        """
        try:
            # Step 1: Register gap with gap detector
            gap_id = self.gap_detector.register_gap(
                gap_type=gap_signal.gap_type,
                query=gap_signal.query,
                confidence=gap_signal.confidence,
                missing_elements=gap_signal.missing_elements
            )

            if not gap_id:
                logger.warning("Failed to register gap with gap detector")
                return False

            # Step 2: Add to learning queue with priority
            priority = self._calculate_priority(gap_signal)

            queue_item_id = self.queue_manager.add_to_queue(
                gap_id=gap_id,
                gap_type=gap_signal.gap_type,
                priority=priority,
                source_documents=gap_signal.source_documents,
                metadata={
                    'query': gap_signal.query,
                    'confidence': gap_signal.confidence,
                    'missing_elements': gap_signal.missing_elements
                }
            )

            if queue_item_id:
                logger.info(
                    f"Gap queued for learning: gap_id={gap_id}, "
                    f"queue_item={queue_item_id}, priority={priority}"
                )
                return True
            else:
                logger.warning("Failed to add gap to learning queue")
                return False

        except Exception as e:
            logger.error(f"Failed to trigger learning flow: {e}", exc_info=True)
            return False

    def _calculate_priority(self, gap_signal: GapSignal) -> int:
        """
        Calculate queue priority (1=highest, 10=lowest).

        Priority factors:
        - Gap type severity
        - Confidence level
        - Number of missing elements
        """
        base_priority = 5

        # Adjust by gap type
        type_adjustments = {
            'entity_not_found': -2,      # Higher priority
            'relationship_gap': -1,
            'missing_info': 0,
            'low_confidence': 1,          # Lower priority
        }
        base_priority += type_adjustments.get(gap_signal.gap_type, 0)

        # Adjust by confidence (lower confidence = higher priority)
        if gap_signal.confidence < 0.5:
            base_priority -= 2
        elif gap_signal.confidence < 0.7:
            base_priority -= 1

        # Clamp to valid range
        return max(1, min(10, base_priority))
```

---

### 2. Integration into Query Pipeline

**File to modify:** `src/context_foundry/agents/reasoning.py`

Find the main query execution method and add response analysis:

```python
# Add import at top of file
from src.context_foundry.learning.response_analyzer import ResponseAnalyzer

# In the query execution method (likely `execute_query` or `answer_query`):

def execute_query(self, query: str, tenant_id: UUID) -> QueryResponse:
    """Execute a query and return response."""

    # ... existing retrieval and reasoning logic ...

    response = self._generate_response(query, retrieved_chunks, entities)
    confidence = self._calculate_confidence(response, retrieved_chunks)

    # === NEW: Analyze response for gaps ===
    try:
        analyzer = ResponseAnalyzer(
            session=self.session,
            tenant_id=tenant_id
        )

        gap_signal = analyzer.analyze_response(
            query=query,
            response=response.text,
            confidence=confidence,
            retrieved_chunks=retrieved_chunks,
            entities_used=entities
        )

        if gap_signal:
            # Trigger learning flow asynchronously (don't block response)
            analyzer.trigger_learning_flow(gap_signal)

            # Optionally add gap info to response metadata
            response.metadata['gap_detected'] = True
            response.metadata['gap_type'] = gap_signal.gap_type
    except Exception as e:
        logger.warning(f"Response analysis failed (non-blocking): {e}")
    # === END NEW ===

    return response
```

---

### 3. Background Processing

The Learning Flow orchestrator should run as a background task to process the queue.

**File to modify:** `web_app.py` or create `src/context_foundry/learning/background_worker.py`

```python
import threading
import time
from src.context_foundry.learning.orchestrator import LearningOrchestrator

class LearningFlowWorker:
    """Background worker that processes the learning queue."""

    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval  # seconds
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Start the background worker."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Learning Flow background worker started")

    def stop(self):
        """Stop the background worker."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Learning Flow background worker stopped")

    def _run(self):
        """Main worker loop."""
        while not self._stop_event.is_set():
            try:
                self._process_queue()
            except Exception as e:
                logger.error(f"Learning Flow worker error: {e}", exc_info=True)

            # Wait for next check interval
            self._stop_event.wait(self.check_interval)

    def _process_queue(self):
        """Process pending items in the learning queue."""
        from src.context_foundry.models.schema import get_session

        session = get_session()
        try:
            # Get all tenants with pending queue items
            tenants = self._get_tenants_with_pending_items(session)

            for tenant_id in tenants:
                orchestrator = LearningOrchestrator(session, tenant_id)

                # Process up to 5 items per tenant per cycle
                processed = orchestrator.process_queue(max_items=5)

                if processed > 0:
                    logger.info(f"Processed {processed} learning items for tenant {tenant_id}")

            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def _get_tenants_with_pending_items(self, session) -> List[UUID]:
        """Get list of tenants with pending learning queue items."""
        from sqlalchemy import text

        result = session.execute(text("""
            SELECT DISTINCT tenant_id
            FROM learning_queue
            WHERE status = 'pending'
            ORDER BY tenant_id
        """))

        return [row[0] for row in result.fetchall()]


# Add to web_app.py startup:
learning_worker = LearningFlowWorker(check_interval=60)

@app.before_first_request
def start_background_workers():
    learning_worker.start()

@atexit.register
def stop_background_workers():
    learning_worker.stop()
```

---

### 4. API Endpoints for Monitoring

**File to modify:** `src/context_foundry/api/learning_api.py`

Add endpoints to monitor Learning Flow status:

```python
@learning_bp.route('/learning/status', methods=['GET'])
@require_auth
def get_learning_status():
    """Get Learning Flow status for current tenant."""
    tenant_id = g.tenant_id
    session = get_db_session()

    try:
        # Get queue stats
        queue_stats = session.execute(text("""
            SELECT
                status,
                COUNT(*) as count,
                AVG(priority) as avg_priority
            FROM learning_queue
            WHERE tenant_id = :tid
            GROUP BY status
        """), {'tid': str(tenant_id)}).fetchall()

        # Get gap stats
        gap_stats = session.execute(text("""
            SELECT
                gap_type,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence
            FROM learning_gaps
            WHERE tenant_id = :tid
            GROUP BY gap_type
        """), {'tid': str(tenant_id)}).fetchall()

        # Get recent activity
        recent = session.execute(text("""
            SELECT id, gap_type, status, created_at, processed_at
            FROM learning_queue
            WHERE tenant_id = :tid
            ORDER BY created_at DESC
            LIMIT 10
        """), {'tid': str(tenant_id)}).fetchall()

        return jsonify({
            'queue': {
                row[0]: {'count': row[1], 'avg_priority': float(row[2]) if row[2] else None}
                for row in queue_stats
            },
            'gaps': {
                row[0]: {'count': row[1], 'avg_confidence': float(row[2]) if row[2] else None}
                for row in gap_stats
            },
            'recent_activity': [
                {
                    'id': str(row[0]),
                    'gap_type': row[1],
                    'status': row[2],
                    'created_at': row[3].isoformat() if row[3] else None,
                    'processed_at': row[4].isoformat() if row[4] else None
                }
                for row in recent
            ]
        })
    finally:
        session.close()


@learning_bp.route('/learning/trigger', methods=['POST'])
@require_auth
def manual_trigger():
    """Manually trigger Learning Flow processing."""
    tenant_id = g.tenant_id
    session = get_db_session()

    try:
        orchestrator = LearningOrchestrator(session, tenant_id)
        processed = orchestrator.process_queue(max_items=10)
        session.commit()

        return jsonify({
            'success': True,
            'processed': processed
        })
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()
```

---

## Testing the Integration

### Test 1: Verify Gap Detection

```python
# Test script: test_gap_detection.py

from src.context_foundry.learning.response_analyzer import ResponseAnalyzer

def test_gap_detection():
    # Simulate a response with missing info
    response = "The retrieved information does not specify who the CFO is."
    confidence = 0.65

    analyzer = ResponseAnalyzer(session, tenant_id)
    gap = analyzer.analyze_response(
        query="Who is the CFO?",
        response=response,
        confidence=confidence,
        retrieved_chunks=[],
        entities_used=[]
    )

    assert gap is not None
    assert gap.gap_type in ['missing_info', 'low_confidence']
    print(f"Gap detected: {gap}")
```

### Test 2: End-to-End Learning Flow

```bash
# 1. Run a query that should trigger a gap
curl -X POST http://localhost:5000/api/v1/query \
  -H "X-CF-API-Key: your-key" \
  -d '{"query": "Who is the CFO of Morrison & Sterling?"}'

# 2. Check learning status
curl http://localhost:5000/api/learning/status \
  -H "X-CF-API-Key: your-key"

# Expected: Should see 1 item in queue

# 3. Wait for background worker OR manually trigger
curl -X POST http://localhost:5000/api/learning/trigger \
  -H "X-CF-API-Key: your-key"

# 4. Re-run the query - should now have better answer
curl -X POST http://localhost:5000/api/v1/query \
  -H "X-CF-API-Key: your-key" \
  -d '{"query": "Who is the CFO of Morrison & Sterling?"}'
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/context_foundry/learning/response_analyzer.py` | **CREATE** | New component for gap detection |
| `src/context_foundry/agents/reasoning.py` | **MODIFY** | Add response analysis after query |
| `src/context_foundry/learning/background_worker.py` | **CREATE** | Background queue processor |
| `src/context_foundry/api/learning_api.py` | **MODIFY** | Add monitoring endpoints |
| `web_app.py` | **MODIFY** | Start background worker on startup |

---

## Success Criteria

After implementation:

1. **Gap Detection:** Queries returning "does not specify" or low confidence trigger gap detection
2. **Queue Population:** Gaps appear in `learning_queue` table within seconds of query
3. **Background Processing:** Queue items are processed within 60 seconds
4. **Knowledge Improvement:** Re-running the same query shows improved results
5. **Monitoring:** `/api/learning/status` endpoint shows queue activity

---

## Rollout Plan

1. **Phase 1:** Deploy ResponseAnalyzer (gap detection only, no queue)
2. **Phase 2:** Enable queue population (gaps get queued)
3. **Phase 3:** Enable background worker (gaps get processed)
4. **Phase 4:** Monitor and tune thresholds

This allows gradual rollout with ability to disable at each phase.
