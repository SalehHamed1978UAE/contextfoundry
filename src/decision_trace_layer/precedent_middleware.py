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
- 300ms timeout on precedent search
- No-block on timeout/error: proceed with decision, log status
- Single orchestration hook for all decision points
"""

import os
import time
import logging
import functools
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)


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
    
    def __post_init__(self):
        if self.latency_samples is None:
            self.latency_samples = []
    
    def record_latency(self, latency_ms: float):
        """Record a latency sample for percentile calculation"""
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
    def p95_latency_ms(self) -> float:
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def citation_rate(self) -> float:
        return self.cited_precedents / max(self.total_calls, 1) * 100
    
    @property
    def deviation_rate(self) -> float:
        return self.deviations / max(self.total_calls, 1) * 100


class PrecedentMiddleware:
    """
    Middleware that enforces "retrieve before decide" pattern.
    
    GUARDRAILS:
    - 300ms timeout on precedent search (configurable)
    - No-block on failure: proceed with decision, log status
    """
    
    STRONG_PRECEDENT_THRESHOLD = 0.7
    MIN_PRECEDENTS_TO_FETCH = 5
    PRECEDENT_TIMEOUT_SECONDS = 0.3  # 300ms
    
    _executor = ThreadPoolExecutor(max_workers=4)
    _metrics = PrecedentLookupMetrics()
    
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
    
    def _do_precedent_search(
        self,
        situation: str,
        decision_type: Optional[str],
        entity_ids: Optional[List[str]],
        limit: int
    ) -> List[Precedent]:
        """Internal method that performs the actual HTTP call"""
        response = requests.post(
            f"{self.base_url}/api/v1/dtl/precedents/search",
            headers={
                "X-CF-API-Key": self.api_key,
                "Content-Type": "application/json"
            },
            json={
                "query": situation,
                "decision_type": decision_type,
                "entity_ids": entity_ids,
                "limit": limit
            },
            timeout=self.timeout_seconds
        )
        
        if response.status_code != 200:
            logger.warning(f"[PrecedentMiddleware] Search failed: {response.status_code}")
            return []
        
        data = response.json()
        
        precedents = []
        for p in data:
            precedents.append(Precedent(
                decision_id=p.get("decision_id") or p.get("id"),
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
        
        GUARDRAIL: 300ms timeout, no-block on failure
        """
        self._metrics.total_calls += 1
        start_time = time.time()
        
        try:
            future = self._executor.submit(
                self._do_precedent_search,
                situation, decision_type, entity_ids, limit
            )
            
            precedents = future.result(timeout=self.timeout_seconds)
            latency_ms = (time.time() - start_time) * 1000
            
            self._metrics.successful_calls += 1
            self._metrics.total_latency_ms += latency_ms
            self._metrics.record_latency(latency_ms)
            
            return precedents, "success", latency_ms
            
        except FuturesTimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.timeout_calls += 1
            self._metrics.record_latency(latency_ms)
            future.cancel()
            logger.warning(f"[PrecedentMiddleware] Timeout after {latency_ms:.0f}ms, proceeding without precedents")
            return [], "skipped_timeout", latency_ms
            
        except requests.exceptions.Timeout:
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.timeout_calls += 1
            self._metrics.record_latency(latency_ms)
            logger.warning(f"[PrecedentMiddleware] Request timeout after {latency_ms:.0f}ms")
            return [], "skipped_timeout", latency_ms
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.error_calls += 1
            self._metrics.record_latency(latency_ms)
            logger.error(f"[PrecedentMiddleware] Error retrieving precedents: {e}")
            return [], "skipped_error", latency_ms
    
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
