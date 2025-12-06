-- Migration 009: Message Bus for Agent Coordination
-- RFC v2 §12 - Event-Driven Agent Communication
--
-- The message bus enables loose coupling between governance agents:
-- - Ontology Foundry agents publish type lifecycle events
-- - Context Foundry agents publish extraction/validation events
-- - OrphanDetector publishes feedback events to Ontology Foundry
--
-- Message Types:
-- - TYPE_PROPOSED: New type submitted for validation
-- - TYPE_APPROVED: Type passed validation and approval
-- - TYPE_ACTIVATED: Type now available for extraction
-- - TYPE_DEPRECATED: Type marked for removal
-- - EXTRACTION_COMPLETE: Document extraction finished
-- - ENTITY_PROMOTED: Entity promoted to TRUSTED
-- - ORPHAN_PATTERN_DETECTED: Unmatched extraction pattern found
-- - APPROVAL_REQUIRED: Human review needed
-- - APPROVAL_COMPLETE: Human review decision made

-- Event type enum
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'event_type') THEN
        CREATE TYPE event_type AS ENUM (
            'TYPE_PROPOSED',
            'TYPE_VALIDATING',
            'TYPE_APPROVED',
            'TYPE_ACTIVATED',
            'TYPE_DEPRECATED',
            'TYPE_REJECTED',
            'EXTRACTION_COMPLETE',
            'ENTITY_STAGED',
            'ENTITY_PROMOTED',
            'ENTITY_ARCHIVED',
            'RELATIONSHIP_PROMOTED',
            'ORPHAN_PATTERN_DETECTED',
            'APPROVAL_REQUIRED',
            'APPROVAL_COMPLETE',
            'CONFLICT_DETECTED',
            'CONFLICT_RESOLVED'
        );
    END IF;
END $$;

-- Processing status enum
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'processing_status') THEN
        CREATE TYPE processing_status AS ENUM (
            'PENDING',
            'PROCESSING',
            'COMPLETED',
            'FAILED',
            'DEAD_LETTER'
        );
    END IF;
END $$;

-- Main message queue table
CREATE TABLE IF NOT EXISTS shared.message_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Event metadata
    event_type event_type NOT NULL,
    source_agent VARCHAR(100) NOT NULL,
    target_agent VARCHAR(100),  -- NULL = broadcast to all subscribers
    
    -- Event payload
    payload JSONB NOT NULL DEFAULT '{}',
    
    -- Correlation for request/response patterns
    correlation_id UUID,
    causation_id UUID,  -- ID of event that caused this one
    
    -- Processing state
    status processing_status NOT NULL DEFAULT 'PENDING',
    retry_count INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,
    error_message TEXT,
    
    -- Timing
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    scheduled_for TIMESTAMP,  -- For delayed processing
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Dead letter tracking
    dead_lettered_at TIMESTAMP,
    dead_letter_reason TEXT
);

-- Event subscriptions table
CREATE TABLE IF NOT EXISTS shared.event_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    subscriber_agent VARCHAR(100) NOT NULL,
    event_type event_type NOT NULL,
    
    -- Subscription filter (optional)
    filter_expression JSONB,  -- JSONPath filter on payload
    
    -- Subscription state
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    CONSTRAINT unique_subscription UNIQUE (subscriber_agent, event_type)
);

-- Processed events log (for exactly-once semantics)
CREATE TABLE IF NOT EXISTS shared.processed_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    message_id UUID NOT NULL REFERENCES shared.message_queue(id),
    subscriber_agent VARCHAR(100) NOT NULL,
    
    processed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    result_status VARCHAR(50),
    result_payload JSONB,
    
    CONSTRAINT unique_processing UNIQUE (message_id, subscriber_agent)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_message_queue_status ON shared.message_queue(status);
CREATE INDEX IF NOT EXISTS idx_message_queue_event_type ON shared.message_queue(event_type);
CREATE INDEX IF NOT EXISTS idx_message_queue_target ON shared.message_queue(target_agent) WHERE target_agent IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_message_queue_scheduled ON shared.message_queue(scheduled_for) WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_message_queue_correlation ON shared.message_queue(correlation_id) WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_event_subscriptions_active ON shared.event_subscriptions(event_type) WHERE is_active = TRUE;

-- Function to get pending messages for an agent
CREATE OR REPLACE FUNCTION shared.get_pending_messages(
    p_agent_name VARCHAR(100),
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    message_id UUID,
    event_type event_type,
    source_agent VARCHAR(100),
    payload JSONB,
    correlation_id UUID,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        mq.id,
        mq.event_type,
        mq.source_agent,
        mq.payload,
        mq.correlation_id,
        mq.created_at
    FROM shared.message_queue mq
    INNER JOIN shared.event_subscriptions es 
        ON es.event_type = mq.event_type
        AND es.subscriber_agent = p_agent_name
        AND es.is_active = TRUE
    LEFT JOIN shared.processed_events pe 
        ON pe.message_id = mq.id 
        AND pe.subscriber_agent = p_agent_name
    WHERE mq.status = 'PENDING'
      AND pe.id IS NULL
      AND (mq.target_agent IS NULL OR mq.target_agent = p_agent_name)
      AND (mq.scheduled_for IS NULL OR mq.scheduled_for <= NOW())
    ORDER BY mq.created_at ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to acknowledge message processing
CREATE OR REPLACE FUNCTION shared.ack_message(
    p_message_id UUID,
    p_agent_name VARCHAR(100),
    p_status VARCHAR(50) DEFAULT 'SUCCESS',
    p_result JSONB DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    INSERT INTO shared.processed_events (message_id, subscriber_agent, result_status, result_payload)
    VALUES (p_message_id, p_agent_name, p_status, p_result)
    ON CONFLICT (message_id, subscriber_agent) DO UPDATE
    SET processed_at = NOW(), result_status = p_status, result_payload = p_result;
    
    -- Check if all subscribers have processed this message
    IF NOT EXISTS (
        SELECT 1 
        FROM shared.event_subscriptions es
        LEFT JOIN shared.processed_events pe 
            ON pe.message_id = p_message_id 
            AND pe.subscriber_agent = es.subscriber_agent
        WHERE es.event_type = (SELECT event_type FROM shared.message_queue WHERE id = p_message_id)
          AND es.is_active = TRUE
          AND pe.id IS NULL
    ) THEN
        UPDATE shared.message_queue SET status = 'COMPLETED', completed_at = NOW()
        WHERE id = p_message_id;
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Seed default subscriptions for governance agents
INSERT INTO shared.event_subscriptions (subscriber_agent, event_type) VALUES
    ('TypeValidator', 'TYPE_PROPOSED'),
    ('HierarchyEnforcer', 'TYPE_PROPOSED'),
    ('CollisionDetector', 'TYPE_PROPOSED'),
    ('ApprovalManager', 'TYPE_VALIDATING'),
    ('OrphanDetector', 'EXTRACTION_COMPLETE'),
    ('OrphanDetector', 'ENTITY_STAGED'),
    ('Gardener', 'ENTITY_STAGED'),
    ('Gardener', 'CONFLICT_DETECTED'),
    ('IdentityResolver', 'ENTITY_STAGED')
ON CONFLICT (subscriber_agent, event_type) DO NOTHING;

COMMENT ON TABLE shared.message_queue IS 'Event-driven message bus for agent coordination';
COMMENT ON TABLE shared.event_subscriptions IS 'Agent subscriptions to event types';
COMMENT ON TABLE shared.processed_events IS 'Tracking for exactly-once processing semantics';
