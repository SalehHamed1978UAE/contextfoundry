"""
Circuit Breaker for Extraction Retries

Prevents runaway retries during systemic failures (e.g., LLM API down).
State is persisted in the database for cross-request consistency.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ExtractionCircuitBreaker:
    """
    Circuit breaker to prevent runaway retries.
    
    State is persisted in the database (extraction_circuit_breaker table)
    to share state across all API requests and scheduler runs.
    
    Opens after `failure_threshold` failures in `window_minutes`.
    Stays open for `cooldown_minutes` before allowing test retry.
    """
    
    def __init__(
        self, 
        db_session,
        failure_threshold: int = 10,
        window_minutes: int = 5,
        cooldown_minutes: int = 15
    ):
        self.db = db_session
        self.failure_threshold = failure_threshold
        self.window_minutes = window_minutes
        self.cooldown_minutes = cooldown_minutes
    
    def _get_state(self) -> dict:
        """Get current circuit breaker state from database."""
        result = self.db.execute(text("""
            SELECT state, opened_at, failure_count, last_failure_at, updated_at
            FROM extraction_circuit_breaker
            WHERE id = 1
        """)).fetchone()
        
        if not result:
            return {
                "state": CircuitState.CLOSED.value,
                "opened_at": None,
                "failure_count": 0,
                "last_failure_at": None
            }
        
        return {
            "state": result.state,
            "opened_at": result.opened_at,
            "failure_count": result.failure_count,
            "last_failure_at": result.last_failure_at
        }
    
    def _update_state(self, state: str, opened_at: Optional[datetime] = None, 
                      failure_count: Optional[int] = None) -> None:
        """Update circuit breaker state in database."""
        self.db.execute(text("""
            UPDATE extraction_circuit_breaker 
            SET state = :state,
                opened_at = COALESCE(:opened_at, opened_at),
                failure_count = COALESCE(:failure_count, failure_count),
                updated_at = NOW()
            WHERE id = 1
        """), {
            "state": state,
            "opened_at": opened_at,
            "failure_count": failure_count
        })
        self.db.commit()
    
    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        
        current = self._get_state()
        
        if current["state"] == CircuitState.OPEN.value:
            return
        
        result = self.db.execute(text("""
            SELECT COUNT(*) as count FROM extraction_jobs
            WHERE status IN ('FAILED', 'TIMEOUT')
              AND completed_at > NOW() - INTERVAL :window
        """), {"window": f"{self.window_minutes} minutes"}).fetchone()
        
        recent_failures = result.count if result else 0
        
        self.db.execute(text("""
            UPDATE extraction_circuit_breaker 
            SET failure_count = :count,
                last_failure_at = NOW(),
                updated_at = NOW()
            WHERE id = 1
        """), {"count": recent_failures})
        self.db.commit()
        
        if recent_failures >= self.failure_threshold:
            self._update_state(
                state=CircuitState.OPEN.value,
                opened_at=datetime.utcnow(),
                failure_count=recent_failures
            )
            logger.error(
                f"[CircuitBreaker] OPEN: {recent_failures} failures in {self.window_minutes} min. "
                f"Retries blocked for {self.cooldown_minutes} min."
            )
    
    def record_success(self) -> None:
        """Record a success, potentially closing the circuit."""
        
        current = self._get_state()
        
        if current["state"] == CircuitState.HALF_OPEN.value:
            self._update_state(
                state=CircuitState.CLOSED.value,
                opened_at=None,
                failure_count=0
            )
            logger.info("[CircuitBreaker] CLOSED: system recovered")
    
    def can_retry(self) -> bool:
        """Check if retries are allowed."""
        
        current = self._get_state()
        state = current["state"]
        opened_at = current["opened_at"]
        
        if state == CircuitState.CLOSED.value:
            return True
        
        if state == CircuitState.OPEN.value:
            if opened_at and datetime.utcnow() > opened_at + timedelta(minutes=self.cooldown_minutes):
                self._update_state(state=CircuitState.HALF_OPEN.value)
                logger.info("[CircuitBreaker] HALF_OPEN: allowing test retry")
                return True
            return False
        
        if state == CircuitState.HALF_OPEN.value:
            return True
        
        return False
    
    @property
    def state(self) -> CircuitState:
        """Get current state as enum."""
        current = self._get_state()
        return CircuitState(current["state"])
    
    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        current = self._get_state()
        
        cooldown_remaining = None
        if current["state"] == CircuitState.OPEN.value and current["opened_at"]:
            cooldown_end = current["opened_at"] + timedelta(minutes=self.cooldown_minutes)
            remaining = (cooldown_end - datetime.utcnow()).total_seconds()
            cooldown_remaining = max(0, int(remaining))
        
        return {
            "state": current["state"],
            "opened_at": current["opened_at"].isoformat() if current["opened_at"] else None,
            "failure_count": current["failure_count"],
            "cooldown_remaining": cooldown_remaining,
            "failure_threshold": self.failure_threshold,
            "window_minutes": self.window_minutes,
            "cooldown_minutes": self.cooldown_minutes
        }
    
    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._update_state(
            state=CircuitState.CLOSED.value,
            opened_at=None,
            failure_count=0
        )
        logger.info("[CircuitBreaker] Manually reset to CLOSED")


def get_circuit_breaker(db_session) -> ExtractionCircuitBreaker:
    """Get circuit breaker with provided session."""
    return ExtractionCircuitBreaker(db_session)
