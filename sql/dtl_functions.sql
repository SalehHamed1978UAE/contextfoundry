/* ============================================================================
   Context Foundry — Decision Trace Layer (DTL) v1.0 
   Precedent Search Functions
   ============================================================================ */

-- search_precedents — category is a ranking bonus, not a filter
-- Also adds entity overlap signal + confidence gate + optional negative-outcome filtering

DROP FUNCTION IF EXISTS search_precedents(
  TEXT, VECTOR(1536), UUID, TEXT, UUID[], FLOAT, INT, BOOLEAN, INT, INT, FLOAT, FLOAT, FLOAT, FLOAT
);

CREATE OR REPLACE FUNCTION search_precedents(
  p_query_text TEXT,
  p_query_embedding VECTOR(1536),
  p_tenant_id UUID,
  p_decision_type_hint TEXT DEFAULT NULL,
  p_required_entity_ids UUID[] DEFAULT NULL,
  p_min_overall_confidence FLOAT DEFAULT 0.0,
  p_limit INT DEFAULT 10,
  p_include_negative_outcomes BOOLEAN DEFAULT TRUE,

  -- scoring knobs
  p_rrf_k INT DEFAULT 60,
  p_recency_half_life_days INT DEFAULT 180,
  p_recency_weight FLOAT DEFAULT 0.30,
  p_outcome_weight FLOAT DEFAULT 0.15,
  p_category_bonus_weight FLOAT DEFAULT 0.05,
  p_entity_bonus_weight FLOAT DEFAULT 0.05
)
RETURNS TABLE (
  decision_id UUID,
  decision_human_id VARCHAR,
  summary TEXT,
  decision_type TEXT,
  rationale_summary TEXT,
  choice JSONB,
  decision_timestamp TIMESTAMPTZ,
  decision_maker_id UUID,
  outcome_status result_status,

  -- explainability signals
  semantic_rank INT,
  fulltext_rank INT,
  entity_rank INT,

  semantic_score FLOAT,
  fulltext_score FLOAT,
  entity_overlap_score FLOAT,
  recency_score FLOAT,
  outcome_score FLOAT,
  category_bonus FLOAT,

  rrf_score FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
  k INT := p_rrf_k;
BEGIN
  RETURN QUERY
  WITH base AS (
    SELECT
      dt.*,
      COALESCE(dcs.overall_confidence::float, 0.5) AS overall_conf
    FROM decision_traces dt
    LEFT JOIN LATERAL (
      SELECT overall_confidence
      FROM decision_confidence_scores
      WHERE decision_id = dt.id
      ORDER BY created_at DESC
      LIMIT 1
    ) dcs ON TRUE
    WHERE dt.tenant_id = p_tenant_id
      AND dt.lifecycle_state = 'enacted'
      AND COALESCE(dcs.overall_confidence::float, 0.5) >= p_min_overall_confidence
  ),

  -- Semantic candidates (vector)
  semantic_search AS (
    SELECT
      b.id,
      ROW_NUMBER() OVER (ORDER BY b.rationale_embedding <=> p_query_embedding) AS r,
      (1.0 - (b.rationale_embedding <=> p_query_embedding))::float AS s
    FROM base b
    WHERE b.rationale_embedding IS NOT NULL
    ORDER BY b.rationale_embedding <=> p_query_embedding
    LIMIT k
  ),

  -- Full-text candidates
  fulltext_search AS (
    SELECT
      b.id,
      ROW_NUMBER() OVER (
        ORDER BY ts_rank_cd(
          to_tsvector('english', COALESCE(b.decision_summary,'') || ' ' || COALESCE(b.rationale_summary,'')),
          plainto_tsquery('english', p_query_text)
        ) DESC
      ) AS r,
      ts_rank_cd(
        to_tsvector('english', COALESCE(b.decision_summary,'') || ' ' || COALESCE(b.rationale_summary,'')),
        plainto_tsquery('english', p_query_text)
      )::float AS s
    FROM base b
    WHERE to_tsvector('english', COALESCE(b.decision_summary,'') || ' ' || COALESCE(b.rationale_summary,'')) @@ plainto_tsquery('english', p_query_text)
    LIMIT k
  ),

  -- Entity overlap candidates (signal, not hard constraint)
  entity_overlap AS (
    SELECT
      del.decision_id AS id,
      COUNT(*)::float AS overlap_count
    FROM decision_entity_links del
    WHERE p_required_entity_ids IS NOT NULL
      AND del.entity_id = ANY(p_required_entity_ids)
    GROUP BY del.decision_id
  ),

  entity_search AS (
    SELECT
      eo.id,
      ROW_NUMBER() OVER (ORDER BY eo.overlap_count DESC) AS r,
      (eo.overlap_count / NULLIF(array_length(p_required_entity_ids, 1), 0))::float AS s
    FROM entity_overlap eo
    ORDER BY eo.overlap_count DESC
    LIMIT k
  ),

  -- Combine ranks with Reciprocal Rank Fusion
  rrf_combined AS (
    SELECT id, 0.40 / (k + r) AS score, r AS sem_rank, NULL::INT AS ft_rank, NULL::INT AS ent_rank
    FROM semantic_search
    UNION ALL
    SELECT id, 0.35 / (k + r) AS score, NULL::INT, r, NULL::INT
    FROM fulltext_search
    UNION ALL
    SELECT id, 0.25 / (k + r) AS score, NULL::INT, NULL::INT, r
    FROM entity_search
  ),

  rrf_aggregated AS (
    SELECT
      id,
      SUM(score)::float AS base_rrf_score,
      MIN(sem_rank) AS semantic_rank,
      MIN(ft_rank) AS fulltext_rank,
      MIN(ent_rank) AS entity_rank
    FROM rrf_combined
    GROUP BY id
  ),

  joined AS (
    SELECT
      b.id AS decision_id,
      b.decision_id AS decision_human_id,
      b.decision_summary AS summary,
      b.decision_type,
      b.rationale_summary,
      b.decision_choice AS choice,
      b.decision_timestamp,
      b.decision_maker_id,

      ra.semantic_rank,
      ra.fulltext_rank,
      ra.entity_rank,

      COALESCE(ss.s, 0.0)::float AS semantic_score,
      COALESCE(fs.s, 0.0)::float AS fulltext_score,
      COALESCE(es.s, 0.0)::float AS entity_overlap_score,

      -- Recency score (exp decay, 0..1)
      (EXP(
        -0.693 * EXTRACT(EPOCH FROM (NOW() - b.decision_timestamp)) / 86400.0 / p_recency_half_life_days
      ))::float AS recency_score,

      -- Outcome score (from most recent result)
      COALESCE(dr.outcome_status, 'unknown'::result_status) AS outcome_status,
      CASE COALESCE(dr.outcome_status, 'unknown'::result_status)
        WHEN 'positive' THEN 1.0
        WHEN 'neutral'  THEN 0.5
        WHEN 'negative' THEN 0.1
        ELSE 0.5
      END::float AS outcome_score,

      -- Category match bonus (NO FILTER - just ranking boost)
      CASE
        WHEN p_decision_type_hint IS NOT NULL AND b.decision_type = p_decision_type_hint THEN 1.0
        ELSE 0.0
      END::float AS category_bonus,

      ra.base_rrf_score
    FROM rrf_aggregated ra
    JOIN base b ON b.id = ra.id
    LEFT JOIN semantic_search ss ON ss.id = b.id
    LEFT JOIN fulltext_search fs ON fs.id = b.id
    LEFT JOIN entity_search es ON es.id = b.id

    LEFT JOIN LATERAL (
      SELECT outcome_status
      FROM decision_results
      WHERE decision_id = b.id
      ORDER BY observed_at DESC
      LIMIT 1
    ) dr ON TRUE
  )

  SELECT
    j.decision_id,
    j.decision_human_id,
    j.summary,
    j.decision_type,
    j.rationale_summary,
    j.choice,
    j.decision_timestamp,
    j.decision_maker_id,
    j.outcome_status,

    j.semantic_rank,
    j.fulltext_rank,
    j.entity_rank,

    j.semantic_score,
    j.fulltext_score,
    j.entity_overlap_score,
    j.recency_score,
    j.outcome_score,
    j.category_bonus,

    (
      j.base_rrf_score
      + p_recency_weight * j.recency_score
      + p_outcome_weight * j.outcome_score
      + p_category_bonus_weight * j.category_bonus
      + p_entity_bonus_weight * COALESCE(j.entity_overlap_score, 0.0)
    )::float AS rrf_score

  FROM joined j
  WHERE (p_include_negative_outcomes OR j.outcome_status != 'negative'::result_status)
  ORDER BY rrf_score DESC
  LIMIT p_limit;

END;
$$;

-- Stable wrapper function with fixed signature for API
-- This prevents breaking changes when the main function evolves

DROP FUNCTION IF EXISTS search_precedents_api(TEXT, VECTOR(1536), UUID, TEXT, UUID[], FLOAT, INT, BOOLEAN);

CREATE OR REPLACE FUNCTION search_precedents_api(
  p_query_text TEXT,
  p_query_embedding VECTOR(1536),
  p_tenant_id UUID,
  p_decision_type_hint TEXT DEFAULT NULL,
  p_entity_ids UUID[] DEFAULT NULL,
  p_min_confidence FLOAT DEFAULT 0.0,
  p_limit INT DEFAULT 10,
  p_include_negative_outcomes BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
  decision_id UUID,
  decision_human_id VARCHAR,
  summary TEXT,
  decision_type TEXT,
  rationale_summary TEXT,
  choice JSONB,
  decision_timestamp TIMESTAMPTZ,
  decision_maker_id UUID,
  outcome_status result_status,
  semantic_rank INT,
  fulltext_rank INT,
  entity_rank INT,
  semantic_score FLOAT,
  fulltext_score FLOAT,
  entity_overlap_score FLOAT,
  recency_score FLOAT,
  outcome_score FLOAT,
  category_bonus FLOAT,
  rrf_score FLOAT
)
LANGUAGE sql
AS $$
  SELECT * FROM search_precedents(
    p_query_text,
    p_query_embedding,
    p_tenant_id,
    p_decision_type_hint,
    p_entity_ids,
    p_min_confidence,
    p_limit,
    p_include_negative_outcomes,
    60,    -- p_rrf_k (default)
    180,   -- p_recency_half_life_days (default)
    0.30,  -- p_recency_weight (default)
    0.15,  -- p_outcome_weight (default)
    0.05,  -- p_category_bonus_weight (default)
    0.05   -- p_entity_bonus_weight (default)
  );
$$;
