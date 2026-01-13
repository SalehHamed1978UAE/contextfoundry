"""
Circuit Breaker for Extraction Retries

Prevents runaway retries during systemic failures (e.g., LLM API down).
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
        self.state = CircuitState.CLOSED
        self.opened_at: Optional[datetime] = None
    
    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit"""
        
        if self.state == CircuitState.OPEN:
            return
        
        result = self.db.execute(text("""
            SELECT COUNT(*) as count FROM extraction_jobs
            WHERE status IN ('FAILED', 'TIMEOUT')
              AND completed_at > NOW() - INTERVAL :window
        """), {"window": f"{self.window_minutes} minutes"}).fetchone()
        
        recent_failures = result.count if result else 0
        
        if recent_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = datetime.utcnow()
            logger.error(
                f"[CircuitBreaker] OPEN: {recent_failures} failures in {self.window_minutes} min. "
                f"Retries blocked for {self.cooldown_minutes} min."
            )
    
    def record_success(self) -> None:
        """Record a success, potentially closing the circuit"""
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.opened_at = None
            logger.info("[CircuitBreaker] CLOSED: system recovered")
    
    def can_retry(self) -> bool:
        """Check if retries are allowed"""
        
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self.opened_at and datetime.utcnow() > self.opened_at + timedelta(minutes=self.cooldown_minutes):
                self.state = CircuitState.HALF_OPEN
                logger.info("[CircuitBreaker] HALF_OPEN: allowing test retry")
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def get_status(self) -> dict:
        """Get current circuit breaker status"""
        return {
            "state": self.state.value,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "cooldown_remaining": self._cooldown_remaining(),
            "failure_threshold": self.failure_threshold,
            "window_minutes": self.window_minutes,
            "cooldown_minutes": self.cooldown_minutes
        }
    
    def _cooldown_remaining(self) -> Optional[int]:
        """Seconds remaining in cooldown, or None if not in cooldown"""
        if self.state != CircuitState.OPEN or not self.opened_at:
            return None
        
        cooldown_end = self.opened_at + timedelta(minutes=self.cooldown_minutes)
        remaining = (cooldown_end - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    
    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state"""
        self.state = CircuitState.CLOSED
        self.opened_at = None
        logger.info("[CircuitBreaker] Manually reset to CLOSED")


def get_circuit_breaker(db_session) -> ExtractionCircuitBreaker:
    """Get circuit breaker with provided session"""
    return ExtractionCircuitBreaker(db_session)
