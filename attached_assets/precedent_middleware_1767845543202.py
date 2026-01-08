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

Usage:
    from src.decision_trace_layer.precedent_middleware import PrecedentMiddleware
    
    middleware = PrecedentMiddleware(tenant_id, decision_maker_id)
    
    # Wrap any decision function
    @middleware.with_precedents(decision_type="discount_approval")
    def approve_discount(customer_id: str, requested_discount: int) -> dict:
        # Your decision logic here
        # middleware.precedents contains relevant past decisions
        # You MUST call middleware.decide() before returning
        ...

Or use directly:
    result = middleware.decide_with_precedents(
        situation="Customer wants 25% discount due to churn risk",
        decision_type="discount_approval",
        decide_fn=lambda precedents: your_decision_logic(precedents)
    )
"""

import os
import functools
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import requests


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
    
    # Filled after decision
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


class PrecedentMiddleware:
    """
    Middleware that enforces "retrieve before decide" pattern.
    
    This is the missing piece that completes the Context Graph loop.
    """
    
    STRONG_PRECEDENT_THRESHOLD = 0.7  # Score above this = strong match
    MIN_PRECEDENTS_TO_FETCH = 5
    
    def __init__(
        self,
        tenant_id: str,
        decision_maker_id: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.tenant_id = tenant_id
        self.decision_maker_id = decision_maker_id
        self.api_key = api_key or os.environ.get("CF_API_KEY")
        self.base_url = base_url or os.environ.get("DTL_BASE_URL", "http://localhost:5000")
        
        if not self.api_key:
            raise ValueError("API key required. Set CF_API_KEY env var or pass api_key.")
        
        # Current decision context (for decorator pattern)
        self._current_context: Optional[DecisionContext] = None
    
    # =========================================================================
    # CORE: Retrieve Precedents
    # =========================================================================
    
    def retrieve_precedents(
        self,
        situation: str,
        decision_type: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[Precedent]:
        """
        RETRIEVE phase of CBR: Find relevant past decisions.
        
        Args:
            situation: Natural language description of the current situation
            decision_type: Optional type hint (e.g., "discount_approval")
            entity_ids: Optional entity IDs involved
            limit: Max precedents to return
        
        Returns:
            List of relevant precedents, sorted by score
        """
        try:
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
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"[PrecedentMiddleware] Search failed: {response.status_code}")
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
            
        except Exception as e:
            print(f"[PrecedentMiddleware] Error retrieving precedents: {e}")
            return []
    
    # =========================================================================
    # CORE: Log Decision with Citations
    # =========================================================================
    
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
        entity_ids: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        RETAIN phase of CBR: Store the decision for future reference.
        
        Args:
            summary: Brief summary of what was decided
            choice: The decision made (structured)
            rationale: Why this decision was made
            decision_type: Category of decision
            evidence: Supporting evidence
            cited_precedents: IDs of precedents that were followed
            deviated_from: ID of precedent that was NOT followed
            deviation_reason: Why the precedent was not followed
            entity_ids: Related entity IDs
        
        Returns:
            Decision ID if successful, None otherwise
        """
        # Build evidence if not provided
        if not evidence:
            evidence = [{
                "evidence_type": "agent_log",
                "excerpt": f"Agent decision: {rationale[:500]}"
            }]
        
        # Add deviation as evidence if present
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
                    # Custom fields for precedent tracking
                    "context": {
                        "cited_precedents": cited_precedents or [],
                        "deviated_from": deviated_from,
                        "deviation_reason": deviation_reason,
                        "precedent_followed": bool(cited_precedents),
                        "middleware_version": "1.0"
                    }
                },
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                return data.get("decision_id") or data.get("id")
            else:
                print(f"[PrecedentMiddleware] Log failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"[PrecedentMiddleware] Error logging decision: {e}")
            return None
    
    # =========================================================================
    # HIGH-LEVEL: Decide with Precedents
    # =========================================================================
    
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
        
        Args:
            situation: Natural language description of the situation
            decision_type: Type of decision being made
            decide_fn: Function that takes precedents and returns:
                {
                    "choice": {...},
                    "rationale": "...",
                    "followed_precedent_id": "..." or None,
                    "deviated_from_id": "..." or None,
                    "deviation_reason": "..." or None
                }
            entity_ids: Related entity IDs
            auto_log: Whether to automatically log the decision
        
        Returns:
            DecisionResult with decision details and precedent tracking
        """
        # RETRIEVE
        precedents = self.retrieve_precedents(
            situation=situation,
            decision_type=decision_type,
            entity_ids=entity_ids,
            limit=self.MIN_PRECEDENTS_TO_FETCH
        )
        
        # DECIDE (REUSE + REVISE)
        decision = decide_fn(precedents)
        
        choice = decision.get("choice", {})
        rationale = decision.get("rationale", "No rationale provided")
        followed_id = decision.get("followed_precedent_id")
        deviated_id = decision.get("deviated_from_id")
        deviation_reason = decision.get("deviation_reason")
        
        # Validate: if strong precedent exists, must follow or explain deviation
        has_strong = precedents and precedents[0].score >= self.STRONG_PRECEDENT_THRESHOLD
        if has_strong and not followed_id and not deviated_id:
            print(f"[PrecedentMiddleware] WARNING: Strong precedent exists (score={precedents[0].score:.2f}) but decision neither follows nor deviates")
        
        # RETAIN
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
                entity_ids=entity_ids
            )
        
        return DecisionResult(
            decision_id=decision_id or "not_logged",
            choice=choice,
            rationale=rationale,
            precedents_considered=len(precedents),
            precedent_followed=followed_id,
            deviated=bool(deviated_id),
            deviation_reason=deviation_reason
        )
    
    # =========================================================================
    # DECORATOR: For wrapping decision functions
    # =========================================================================
    
    def with_precedents(
        self,
        decision_type: Optional[str] = None,
        situation_builder: Optional[Callable[..., str]] = None
    ):
        """
        Decorator that injects precedent retrieval into any decision function.
        
        Usage:
            @middleware.with_precedents(decision_type="discount_approval")
            def approve_discount(self, customer_id, amount, *, precedents, context):
                # precedents: List[Precedent] - automatically injected
                # context: DecisionContext - for tracking follow/deviate
                
                if precedents and precedents[0].score > 0.7:
                    # Follow precedent
                    context.follow(precedents[0].decision_id)
                    return precedents[0].choice
                else:
                    # Make own decision
                    context.deviate(precedents[0].decision_id if precedents else None,
                                   "No strong precedent found")
                    return {"approved": True, "discount": amount}
        """
        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                # Build situation description
                if situation_builder:
                    situation = situation_builder(*args, **kwargs)
                else:
                    # Default: use function name and args
                    situation = f"{fn.__name__} with args: {args}, kwargs: {kwargs}"
                
                # Retrieve precedents
                precedents = self.retrieve_precedents(
                    situation=situation,
                    decision_type=decision_type
                )
                
                # Create context for tracking
                context = DecisionContext(
                    situation=situation,
                    decision_type=decision_type,
                    precedents=precedents,
                    top_precedent=precedents[0] if precedents else None,
                    has_strong_precedent=bool(precedents and precedents[0].score >= self.STRONG_PRECEDENT_THRESHOLD)
                )
                
                # Store for access within function
                self._current_context = context
                
                # Inject precedents and context
                kwargs["precedents"] = precedents
                kwargs["context"] = context
                
                # Call the actual function
                result = fn(*args, **kwargs)
                
                # Auto-log if context was populated
                if context.choice is not None:
                    self.log_decision(
                        summary=f"{decision_type}: {str(context.choice)[:100]}",
                        choice=context.choice,
                        rationale=context.rationale or "No rationale",
                        decision_type=decision_type,
                        cited_precedents=[context.followed_precedent] if context.followed_precedent else [],
                        deviated_from=context.deviated_from,
                        deviation_reason=context.deviation_reason
                    )
                
                self._current_context = None
                return result
            
            return wrapper
        return decorator
    
    # =========================================================================
    # CONTEXT HELPERS: For use within decorated functions
    # =========================================================================
    
    def follow(self, precedent_id: str, choice: Dict, rationale: str):
        """Mark that we're following a precedent"""
        if self._current_context:
            self._current_context.followed_precedent = precedent_id
            self._current_context.choice = choice
            self._current_context.rationale = rationale
    
    def deviate(self, precedent_id: Optional[str], reason: str, choice: Dict, rationale: str):
        """Mark that we're deviating from a precedent (or making novel decision)"""
        if self._current_context:
            self._current_context.deviated_from = precedent_id
            self._current_context.deviation_reason = reason
            self._current_context.choice = choice
            self._current_context.rationale = rationale


# =============================================================================
# CONVENIENCE: Quick decision with precedent check
# =============================================================================

def decide_with_context(
    tenant_id: str,
    decision_maker_id: str,
    situation: str,
    decision_type: str,
    default_decision: Callable[[], Dict[str, Any]],
    adapt_from_precedent: Optional[Callable[[Precedent], Dict[str, Any]]] = None,
    api_key: Optional[str] = None
) -> DecisionResult:
    """
    Convenience function for one-off decisions with precedent checking.
    
    Args:
        tenant_id: Tenant ID
        decision_maker_id: Decision maker entity ID
        situation: Description of the situation
        decision_type: Type of decision
        default_decision: Function that returns default choice if no precedent
        adapt_from_precedent: Optional function to adapt precedent to current case
        api_key: Optional API key (defaults to env var)
    
    Returns:
        DecisionResult
    
    Example:
        result = decide_with_context(
            tenant_id="...",
            decision_maker_id="...",
            situation="Customer Acme wants 30% discount, ARR $400K, churn risk high",
            decision_type="discount_approval",
            default_decision=lambda: {
                "choice": {"approved": True, "discount": 20},
                "rationale": "Applied default policy"
            },
            adapt_from_precedent=lambda p: {
                "choice": p.choice,
                "rationale": f"Following precedent: {p.summary}"
            }
        )
    """
    middleware = PrecedentMiddleware(
        tenant_id=tenant_id,
        decision_maker_id=decision_maker_id,
        api_key=api_key
    )
    
    def decide_fn(precedents: List[Precedent]) -> Dict:
        # Check for strong precedent
        if precedents and precedents[0].score >= PrecedentMiddleware.STRONG_PRECEDENT_THRESHOLD:
            top = precedents[0]
            
            if adapt_from_precedent:
                adapted = adapt_from_precedent(top)
                return {
                    "choice": adapted.get("choice", top.choice),
                    "rationale": adapted.get("rationale", f"Adapted from precedent: {top.summary}"),
                    "followed_precedent_id": top.decision_id
                }
            else:
                return {
                    "choice": top.choice,
                    "rationale": f"Following precedent: {top.summary}",
                    "followed_precedent_id": top.decision_id
                }
        else:
            # No strong precedent - use default
            default = default_decision()
            return {
                "choice": default.get("choice", {}),
                "rationale": default.get("rationale", "No strong precedent found"),
                "deviated_from_id": precedents[0].decision_id if precedents else None,
                "deviation_reason": "No strong precedent match" if precedents else "No precedents found"
            }
    
    return middleware.decide_with_precedents(
        situation=situation,
        decision_type=decision_type,
        decide_fn=decide_fn
    )


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Example: Using the convenience function
    print("Example: Discount approval with precedent checking\n")
    
    # This would be called from your agent code
    result = decide_with_context(
        tenant_id="test-tenant",
        decision_maker_id="discount-agent",
        situation="Customer Acme Corp wants 25% discount. ARR: $350K, Churn risk: High (0.78), Competitor offer in hand.",
        decision_type="discount_approval",
        default_decision=lambda: {
            "choice": {"approved": True, "discount_percent": 20},
            "rationale": "Applied standard policy: max 20% without precedent"
        },
        adapt_from_precedent=lambda p: {
            "choice": p.choice,
            "rationale": f"Following similar case: {p.summary}"
        }
    )
    
    print(f"Decision ID: {result.decision_id}")
    print(f"Choice: {result.choice}")
    print(f"Rationale: {result.rationale}")
    print(f"Precedents considered: {result.precedents_considered}")
    print(f"Followed precedent: {result.precedent_followed}")
    print(f"Deviated: {result.deviated}")
    if result.deviated:
        print(f"Deviation reason: {result.deviation_reason}")
