"""
DTL Precedent Middleware
========================

This middleware implements the "retrieve before decide" pattern that completes
the Case-Based Reasoning (CBR) loop:

    RETRIEVE → REUSE → REVISE → RETAIN

Every non-trivial agent decision should:
1. Query precedents before deciding
2. Either follow a precedent or explicitly deviate with reason
3. Log the decision with precedent citations

CRITICAL GUARDRAILS:
- No-block on timeout/error: proceed with decision, log status
- Single orchestration hook for all decision points

ARCHITECTURE (Library-First):
- Uses inline adapter for in-process precedent search (no HTTP overhead)
- All retrieval logic in src/context_foundry/dtl/core.py
"""

import os
import time
import logging
import functools
import hashlib
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from src.context_foundry.dtl import inline_search_precedents, AuthContext

logger = logging.getLogger(__name__)


EMBEDDING_CACHE: Dict[str, tuple] = {}
EMBEDDING_CACHE_TTL = 3600  # 1 hour


def get_embedding_client_side(text_input: str) -> Optional[List[float]]:
    """
    Get embedding from OpenAI text-embedding-3-small with caching.
    Client-side computation to avoid server roundtrip for embedding.
    Returns None on failure (caller should proceed without embedding).
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[PrecedentMiddleware] OPENAI_API_KEY not set, skipping client-side embedding")
        return None
    
    normalized = text_input.lower().strip()[:500]
    cache_key = hashlib.md5(normalized.encode()).hexdigest()
    
    if cache_key in EMBEDDING_CACHE:
        embedding, timestamp = EMBEDDING_CACHE[cache_key]
        if time.time() - timestamp < EMBEDDING_CACHE_TTL:
            logger.debug("[PrecedentMiddleware] Embedding cache hit")
            return embedding
        del EMBEDDING_CACHE[cache_key]
    
    try:
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={"model": "text-embedding-3-small", "input": text_input},
            timeout=5.0  # Longer timeout for embedding (not blocking decision)
        )
        response.raise_for_status()
        embedding = response.json()["data"][0]["embedding"]
        
        if len(EMBEDDING_CACHE) >= 1000:
            oldest_key = min(EMBEDDING_CACHE.keys(), key=lambda k: EMBEDDING_CACHE[k][1])
            del EMBEDDING_CACHE[oldest_key]
        
        EMBEDDING_CACHE[cache_key] = (embedding, time.time())
        return embedding
    except Exception as e:
        logger.warning(f"[PrecedentMiddleware] Client-side embedding failed: {e}")
        return None


@dataclass
class Precedent:
    """A precedent from the DTL"""
    decision_id: str
    summary: str
    choice: Dict[str, Any]
    rationale: Optional[str]
    decision_type: Optional[str]
    outcome_status: Optional[str]
    score: float
    
    @property
    def was_successful(self) -> bool:
        return self.outcome_status == "positive"


@dataclass
class DecisionContext:
    """Context for a decision being made"""
    situation: str
    decision_type: Optional[str]
    precedents: List[Precedent] = field(default_factory=list)
    top_precedent: Optional[Precedent] = None
    has_strong_precedent: bool = False
    precedent_lookup_status: str = "not_attempted"
    precedent_lookup_latency_ms: float = 0.0
    
    choice: Optional[Dict[str, Any]] = None
    rationale: Optional[str] = None
    followed_precedent: Optional[str] = None
    deviated_from: Optional[str] = None
    deviation_reason: Optional[str] = None


@dataclass
class DecisionResult:
    """Result of a decision with precedent tracking"""
    decision_id: str
    choice: Dict[str, Any]
    rationale: str
    precedents_considered: int
    precedent_followed: Optional[str]
    deviated: bool
    deviation_reason: Optional[str]
    precedent_lookup_status: str = "success"
    precedent_lookup_latency_ms: float = 0.0


@dataclass
class LookupTiming:
    """Detailed timing for a single precedent lookup"""
    t_queue_ms: float = 0.0
    t_http_ms: float = 0.0
    t_total_ms: float = 0.0
    dtl_status: str = "success"


@dataclass 
class PrecedentLookupMetrics:
    """Metrics for monitoring precedent lookup performance"""
    total_calls: int = 0
    successful_calls: int = 0
    timeout_calls: int = 0
    error_calls: int = 0
    total_latency_ms: float = 0.0
    cited_precedents: int = 0
    deviations: int = 0
    latency_samples: list = None
    http_latency_samples: list = None
    queue_latency_samples: list = None
    cache_hits: int = 0
    
    def __post_init__(self):
        if self.latency_samples is None:
            self.latency_samples = []
        if self.http_latency_samples is None:
            self.http_latency_samples = []
        if self.queue_latency_samples is None:
            self.queue_latency_samples = []
    
    def record_timing(self, timing: LookupTiming):
        """Record a complete timing sample"""
        self.latency_samples.append(timing.t_total_ms)
        self.http_latency_samples.append(timing.t_http_ms)
        self.queue_latency_samples.append(timing.t_queue_ms)
        if len(self.latency_samples) > 1000:
            self.latency_samples = self.latency_samples[-500:]
            self.http_latency_samples = self.http_latency_samples[-500:]
            self.queue_latency_samples = self.queue_latency_samples[-500:]
    
    def record_latency(self, latency_ms: float):
        """Record a latency sample for percentile calculation (legacy)"""
        self.latency_samples.append(latency_ms)
        if len(self.latency_samples) > 1000:
            self.latency_samples = self.latency_samples[-500:]
    
    @property
    def call_rate(self) -> float:
        return self.successful_calls / max(self.total_calls, 1) * 100
    
    @property
    def mean_latency_ms(self) -> float:
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)
    
    @property
    def mean_http_latency_ms(self) -> float:
        if not self.http_latency_samples:
            return 0.0
        return sum(self.http_latency_samples) / len(self.http_latency_samples)
    
    @property
    def mean_queue_latency_ms(self) -> float:
        if not self.queue_latency_samples:
            return 0.0
        return sum(self.queue_latency_samples) / len(self.queue_latency_samples)
    
    @property
    def p95_latency_ms(self) -> float:
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def p95_http_latency_ms(self) -> float:
        if not self.http_latency_samples:
            return 0.0
        sorted_samples = sorted(self.http_latency_samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def citation_rate(self) -> float:
        return self.cited_precedents / max(self.total_calls, 1) * 100
    
    @property
    def deviation_rate(self) -> float:
        return self.deviations / max(self.total_calls, 1) * 100
    
    @property
    def cache_hit_rate(self) -> float:
        return self.cache_hits / max(self.total_calls, 1) * 100


class PrecedentMiddleware:
    """
    Middleware that enforces "retrieve before decide" pattern.
    
    GUARDRAILS:
    - 600ms timeout on precedent search (configurable)
    - No-block on failure: proceed with decision, log status
    - Keep-alive HTTP session for connection reuse
    - Query caching with 5-minute TTL
    """
    
    STRONG_PRECEDENT_THRESHOLD = 0.7
    MIN_PRECEDENTS_TO_FETCH = 5
    PRECEDENT_TIMEOUT_SECONDS = 0.6  # 600ms (increased from 300ms)
    CACHE_TTL_SECONDS = 300  # 5 minutes
    
    _metrics = PrecedentLookupMetrics()
    _session: Optional[requests.Session] = None
    _cache: Dict[str, tuple] = {}  # {cache_key: (precedents, timestamp)}
    _cache_lock = None
    
    @classmethod
    def _get_session(cls) -> requests.Session:
        """Get or create shared HTTP session with keep-alive"""
        if cls._session is None:
            cls._session = requests.Session()
            cls._session.headers.update({
                "Content-Type": "application/json",
                "Connection": "keep-alive"
            })
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=20,
                max_retries=0
            )
            cls._session.mount("http://", adapter)
            cls._session.mount("https://", adapter)
        return cls._session
    
    def __init__(
        self,
        tenant_id: str,
        decision_maker_id: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = None
    ):
        self.tenant_id = tenant_id
        self.decision_maker_id = decision_maker_id
        self.api_key = api_key or os.environ.get("CF_API_KEY")
        self.base_url = base_url or os.environ.get("DTL_BASE_URL", "http://localhost:5000")
        self.timeout_seconds = timeout_seconds or self.PRECEDENT_TIMEOUT_SECONDS
        
        if not self.api_key:
            raise ValueError("API key required. Set CF_API_KEY env var or pass api_key.")
        
        self._current_context: Optional[DecisionContext] = None
    
    @classmethod
    def get_metrics(cls) -> PrecedentLookupMetrics:
        """Get accumulated metrics across all middleware instances"""
        return cls._metrics
    
    @classmethod
    def reset_metrics(cls):
        """Reset accumulated metrics"""
        cls._metrics = PrecedentLookupMetrics()
    
    def _get_cache_key(self, situation: str, decision_type: Optional[str], limit: int) -> str:
        """Generate cache key from query parameters"""
        normalized = situation.lower().strip()[:200]
        return f"{self.tenant_id}:{decision_type or 'any'}:{limit}:{hash(normalized)}"
    
    def _check_cache(self, cache_key: str) -> Optional[List[Precedent]]:
        """Check cache for valid entry"""
        if cache_key in self._cache:
            precedents, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self.CACHE_TTL_SECONDS:
                return precedents
            del self._cache[cache_key]
        return None
    
    def _store_cache(self, cache_key: str, precedents: List[Precedent]):
        """Store result in cache"""
        self._cache[cache_key] = (precedents, time.time())
        if len(self._cache) > 500:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
    
    def _parse_precedents(self, data: Any) -> List[Precedent]:
        """Parse API response into Precedent objects"""
        if isinstance(data, dict):
            data = data.get("precedents", [])
        
        precedents = []
        for p in data:
            precedents.append(Precedent(
                decision_id=p.get("decision_id") or p.get("decision_human_id") or p.get("id"),
                summary=p.get("summary") or p.get("decision_summary", ""),
                choice=p.get("choice") or p.get("decision_choice", {}),
                rationale=p.get("rationale_summary") or p.get("rationale"),
                decision_type=p.get("decision_type"),
                outcome_status=p.get("outcome_status"),
                score=p.get("rrf_score") or p.get("score", 0)
            ))
        return precedents
    
    def retrieve_precedents(
        self,
        situation: str,
        decision_type: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        limit: int = 5
    ) -> tuple[List[Precedent], str, float]:
        """
        RETRIEVE phase of CBR: Find relevant past decisions.
        
        Returns: (precedents, status, latency_ms)
        
        ARCHITECTURE: Uses inline adapter (no HTTP overhead).
        All retrieval logic in src/context_foundry/dtl/core.py
        
        Timing instrumentation:
        - t_queue_ms: Embedding computation time (cached = 0ms)
        - t_inline_ms: Inline adapter call duration (DB + formatting)
        - t_total_ms: End-to-end including cache check and embedding
        """
        self._metrics.total_calls += 1
        t_start = time.time()
        timing = LookupTiming()
        
        cache_key = self._get_cache_key(situation, decision_type, limit)
        cached = self._check_cache(cache_key)
        if cached is not None:
            t_total = (time.time() - t_start) * 1000
            timing.t_total_ms = t_total
            timing.t_http_ms = 0.0
            timing.t_queue_ms = 0.0
            timing.dtl_status = "success"
            self._metrics.successful_calls += 1
            self._metrics.cache_hits += 1
            self._metrics.record_timing(timing)
            logger.debug(f"[PrecedentMiddleware] Cache hit: {len(cached)} precedents in {t_total:.1f}ms")
            return cached, "success", t_total
        
        t_embed_start = time.time()
        embedding = get_embedding_client_side(situation)
        t_embed_ms = (time.time() - t_embed_start) * 1000
        timing.t_queue_ms = t_embed_ms
        
        try:
            ctx = AuthContext(
                tenant_id=self.tenant_id,
                user_id=self.decision_maker_id,
                role='user'
            )
            
            t_inline_start = time.time()
            result = inline_search_precedents(
                ctx=ctx,
                query_text=situation,
                query_embedding=embedding,
                decision_type_hint=decision_type,
                required_entity_ids=entity_ids,
                limit=limit
            )
            t_inline_ms = (time.time() - t_inline_start) * 1000
            t_total_ms = (time.time() - t_start) * 1000
            
            timing.t_http_ms = t_inline_ms  # Using http_ms field for inline timing
            timing.t_total_ms = t_total_ms
            
            precedents = [
                Precedent(
                    decision_id=p.decision_id,
                    summary=p.summary,
                    choice=p.choice,
                    rationale=p.rationale_summary,
                    decision_type=p.decision_type,
                    outcome_status=p.outcome_status,
                    score=p.rrf_score
                )
                for p in result.precedents
            ]
            
            self._store_cache(cache_key, precedents)
            
            timing.dtl_status = "success"
            self._metrics.successful_calls += 1
            self._metrics.total_latency_ms += t_total_ms
            self._metrics.record_timing(timing)
            
            logger.debug(f"[PrecedentMiddleware] Found {len(precedents)} precedents (t_embed={t_embed_ms:.0f}ms, t_inline={t_inline_ms:.0f}ms, t_total={t_total_ms:.0f}ms)")
            return precedents, "success", t_total_ms
            
        except Exception as e:
            t_total_ms = (time.time() - t_start) * 1000
            timing.t_total_ms = t_total_ms
            timing.dtl_status = "error"
            self._metrics.error_calls += 1
            self._metrics.record_timing(timing)
            logger.error(f"[PrecedentMiddleware] Error: {e} (t_total={t_total_ms:.0f}ms)")
            return [], "skipped_error", t_total_ms
    
    def log_decision(
        self,
        summary: str,
        choice: Dict[str, Any],
        rationale: str,
        decision_type: Optional[str] = None,
        evidence: Optional[List[Dict]] = None,
        cited_precedents: Optional[List[str]] = None,
        deviated_from: Optional[str] = None,
        deviation_reason: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        precedent_lookup_status: str = "success",
        precedent_lookup_latency_ms: float = 0.0
    ) -> Optional[str]:
        """
        RETAIN phase of CBR: Store the decision for future reference.
        """
        if cited_precedents:
            self._metrics.cited_precedents += 1
        if deviated_from:
            self._metrics.deviations += 1
            
        if not evidence:
            evidence = [{
                "evidence_type": "agent_log",
                "excerpt": f"Agent decision: {rationale[:500]}"
            }]
        
        if deviated_from and deviation_reason:
            evidence.append({
                "evidence_type": "agent_log",
                "excerpt": f"Deviated from precedent {deviated_from}: {deviation_reason}"
            })
        
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/dtl/decisions",
                headers={
                    "X-CF-API-Key": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "summary": summary,
                    "choice": choice,
                    "rationale": rationale,
                    "decision_type": decision_type,
                    "evidence": evidence,
                    "entity_ids": entity_ids or [],
                    "decision_maker_id": self.decision_maker_id,
                    "context": {
                        "cited_precedents": cited_precedents or [],
                        "deviated_from": deviated_from,
                        "deviation_reason": deviation_reason,
                        "precedent_followed": bool(cited_precedents),
                        "precedent_lookup_status": precedent_lookup_status,
                        "precedent_lookup_latency_ms": precedent_lookup_latency_ms,
                        "middleware_version": "1.1"
                    }
                },
                timeout=5.0
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return data.get("decision_id") or data.get("id")
            else:
                logger.warning(f"[PrecedentMiddleware] Log failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[PrecedentMiddleware] Error logging decision: {e}")
            return None
    
    def decide_with_precedents(
        self,
        situation: str,
        decision_type: Optional[str],
        decide_fn: Callable[[List[Precedent]], Dict[str, Any]],
        entity_ids: Optional[List[str]] = None,
        auto_log: bool = True
    ) -> DecisionResult:
        """
        Complete CBR cycle: Retrieve → Decide → Log
        
        GUARDRAIL: No-block - always proceeds even if precedent lookup fails
        """
        precedents, lookup_status, latency_ms = self.retrieve_precedents(
            situation=situation,
            decision_type=decision_type,
            entity_ids=entity_ids,
            limit=self.MIN_PRECEDENTS_TO_FETCH
        )
        
        decision = decide_fn(precedents)
        
        choice = decision.get("choice", {})
        rationale = decision.get("rationale", "No rationale provided")
        followed_id = decision.get("followed_precedent_id")
        deviated_id = decision.get("deviated_from_id")
        deviation_reason = decision.get("deviation_reason")
        
        has_strong = precedents and precedents[0].score >= self.STRONG_PRECEDENT_THRESHOLD
        if has_strong and not followed_id and not deviated_id:
            logger.warning(f"[PrecedentMiddleware] Strong precedent exists (score={precedents[0].score:.2f}) but decision neither follows nor deviates")
        
        decision_id = None
        if auto_log:
            decision_id = self.log_decision(
                summary=f"{decision_type or 'Decision'}: {str(choice)[:100]}",
                choice=choice,
                rationale=rationale,
                decision_type=decision_type,
                cited_precedents=[followed_id] if followed_id else [],
                deviated_from=deviated_id,
                deviation_reason=deviation_reason,
                entity_ids=entity_ids,
                precedent_lookup_status=lookup_status,
                precedent_lookup_latency_ms=latency_ms
            )
        
        return DecisionResult(
            decision_id=decision_id or "not_logged",
            choice=choice,
            rationale=rationale,
            precedents_considered=len(precedents),
            precedent_followed=followed_id,
            deviated=bool(deviated_id),
            deviation_reason=deviation_reason,
            precedent_lookup_status=lookup_status,
            precedent_lookup_latency_ms=latency_ms
        )
    
    def with_precedents(
        self,
        decision_type: Optional[str] = None,
        situation_builder: Optional[Callable[..., str]] = None
    ):
        """
        Decorator for wrapping decision functions with precedent lookup.
        
        GUARDRAIL: No-block - always proceeds even if lookup fails
        """
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                if situation_builder:
                    situation = situation_builder(*args, **kwargs)
                else:
                    situation = " ".join(str(a) for a in args)
                
                precedents, lookup_status, latency_ms = self.retrieve_precedents(
                    situation=situation,
                    decision_type=decision_type,
                    limit=self.MIN_PRECEDENTS_TO_FETCH
                )
                
                context = DecisionContext(
                    situation=situation,
                    decision_type=decision_type,
                    precedents=precedents,
                    top_precedent=precedents[0] if precedents else None,
                    has_strong_precedent=bool(precedents and precedents[0].score >= self.STRONG_PRECEDENT_THRESHOLD),
                    precedent_lookup_status=lookup_status,
                    precedent_lookup_latency_ms=latency_ms
                )
                
                self._current_context = context
                
                kwargs['precedents'] = precedents
                kwargs['context'] = context
                
                return fn(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def follow(
        self,
        precedent_id: str,
        choice: Dict[str, Any],
        rationale: str
    ) -> Optional[str]:
        """Log a decision that follows a precedent."""
        ctx = self._current_context
        return self.log_decision(
            summary=f"Followed precedent {precedent_id[:8]}",
            choice=choice,
            rationale=rationale,
            decision_type=ctx.decision_type if ctx else None,
            cited_precedents=[precedent_id],
            precedent_lookup_status=ctx.precedent_lookup_status if ctx else "unknown",
            precedent_lookup_latency_ms=ctx.precedent_lookup_latency_ms if ctx else 0.0
        )
    
    def deviate(
        self,
        precedent_id: Optional[str],
        reason: str,
        choice: Dict[str, Any],
        rationale: str
    ) -> Optional[str]:
        """Log a decision that deviates from a precedent."""
        ctx = self._current_context
        return self.log_decision(
            summary=f"Deviated from precedent: {reason[:50]}",
            choice=choice,
            rationale=rationale,
            decision_type=ctx.decision_type if ctx else None,
            deviated_from=precedent_id,
            deviation_reason=reason,
            precedent_lookup_status=ctx.precedent_lookup_status if ctx else "unknown",
            precedent_lookup_latency_ms=ctx.precedent_lookup_latency_ms if ctx else 0.0
        )


def decide_with_context(
    tenant_id: str,
    decision_maker_id: str,
    situation: str,
    decision_type: str,
    default_decision: Callable[[], Dict[str, Any]],
    adapt_from_precedent: Callable[[Precedent], Dict[str, Any]],
    precedent_threshold: float = 0.7,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> DecisionResult:
    """
    Convenience function for one-off decisions with precedent checking.
    
    GUARDRAIL: No-block - always returns a decision even if lookup fails
    """
    middleware = PrecedentMiddleware(
        tenant_id=tenant_id,
        decision_maker_id=decision_maker_id,
        api_key=api_key,
        base_url=base_url
    )
    
    def decide_fn(precedents: List[Precedent]) -> Dict[str, Any]:
        if precedents and precedents[0].score >= precedent_threshold:
            adapted = adapt_from_precedent(precedents[0])
            adapted["followed_precedent_id"] = precedents[0].decision_id
            return adapted
        else:
            result = default_decision()
            if precedents:
                result["deviated_from_id"] = precedents[0].decision_id
                result["deviation_reason"] = f"Score {precedents[0].score:.2f} below threshold {precedent_threshold}"
            return result
    
    return middleware.decide_with_precedents(
        situation=situation,
        decision_type=decision_type,
        decide_fn=decide_fn,
        auto_log=True
    )
