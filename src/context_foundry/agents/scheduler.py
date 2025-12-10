"""
Gardener Scheduler for Context Foundry.

Runs the Gardener agent on a configurable schedule (default: 5-minute cycles).
Uses threading for background execution without blocking the main application.
"""
import threading
import time
from datetime import datetime
from typing import Callable, Optional, List
from dataclasses import dataclass, field

from sqlalchemy import text

from .gardener import Gardener, GardenerConfig, GardenerCycleResult
from .identity_resolver import IdentityResolver, IdentityResolutionConfig, IdentityResolutionResult
from ..models.schema import get_session


@dataclass
class SchedulerConfig:
    """Configuration for the Gardener scheduler."""
    cycle_interval_seconds: int = 300
    run_identity_resolution: bool = True
    gardener_config: Optional[GardenerConfig] = None
    identity_config: Optional[IdentityResolutionConfig] = None
    max_history: int = 100


@dataclass
class ScheduledCycleResult:
    """Combined result of a scheduled cycle."""
    cycle_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    gardener_result: Optional[GardenerCycleResult] = None
    identity_result: Optional[IdentityResolutionResult] = None
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "cycle_number": self.cycle_number,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "gardener_result": self.gardener_result.to_dict() if self.gardener_result else None,
            "identity_result": self.identity_result.to_dict() if self.identity_result else None,
            "success": self.success,
            "error": self.error,
        }


class GardenerScheduler:
    """
    Scheduler that runs Gardener and IdentityResolver on a regular schedule.
    
    Default: 5-minute cycles
    
    Usage:
        scheduler = GardenerScheduler()
        scheduler.start()  # Starts background thread
        
        # Later...
        scheduler.stop()
    """
    
    def __init__(
        self,
        config: Optional[SchedulerConfig] = None,
        on_cycle_complete: Optional[Callable[[ScheduledCycleResult], None]] = None,
    ):
        self.config = config or SchedulerConfig()
        self.on_cycle_complete = on_cycle_complete
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cycle_count = 0
        self._history: List[ScheduledCycleResult] = []
        self._lock = threading.Lock()
        
        self._last_result: Optional[ScheduledCycleResult] = None
    
    def start(self) -> None:
        """Start the scheduler in a background thread."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"[Scheduler] Started with {self.config.cycle_interval_seconds}s interval")
    
    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        print("[Scheduler] Stopped")
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running
    
    def run_now(self) -> ScheduledCycleResult:
        """Run a cycle immediately (useful for testing)."""
        return self._run_cycle()
    
    def get_last_result(self) -> Optional[ScheduledCycleResult]:
        """Get the result of the last cycle."""
        return self._last_result
    
    def get_history(self, limit: int = 10) -> List[ScheduledCycleResult]:
        """Get recent cycle history."""
        with self._lock:
            return list(self._history[-limit:])
    
    def get_stats(self) -> dict:
        """Get scheduler statistics."""
        with self._lock:
            successful = sum(1 for r in self._history if r.success)
            failed = sum(1 for r in self._history if not r.success)
            
            total_decayed = sum(
                r.gardener_result.facts_decayed 
                for r in self._history 
                if r.gardener_result
            )
            total_promoted = sum(
                r.gardener_result.facts_promoted 
                for r in self._history 
                if r.gardener_result
            )
            total_demoted = sum(
                r.gardener_result.facts_demoted 
                for r in self._history 
                if r.gardener_result
            )
            total_conflicts = sum(
                r.gardener_result.conflicts_resolved 
                for r in self._history 
                if r.gardener_result
            )
            total_merges = sum(
                r.identity_result.auto_merged 
                for r in self._history 
                if r.identity_result
            )
            
            return {
                "running": self._running,
                "cycle_count": self._cycle_count,
                "interval_seconds": self.config.cycle_interval_seconds,
                "cycles_successful": successful,
                "cycles_failed": failed,
                "total_facts_decayed": total_decayed,
                "total_facts_promoted": total_promoted,
                "total_facts_demoted": total_demoted,
                "total_conflicts_resolved": total_conflicts,
                "total_merges_performed": total_merges,
                "last_run": self._last_result.started_at.isoformat() if self._last_result else None,
            }
    
    def _run_loop(self) -> None:
        """Main loop that runs cycles on schedule."""
        while self._running:
            try:
                result = self._run_cycle()
                
                with self._lock:
                    self._history.append(result)
                    if len(self._history) > self.config.max_history:
                        self._history = self._history[-self.config.max_history:]
                
                if self.on_cycle_complete:
                    try:
                        self.on_cycle_complete(result)
                    except Exception as e:
                        print(f"[Scheduler] Callback error: {e}")
                        
            except Exception as e:
                print(f"[Scheduler] Cycle error: {e}")
            
            for _ in range(self.config.cycle_interval_seconds):
                if not self._running:
                    break
                time.sleep(1)
    
    def _run_cycle(self) -> ScheduledCycleResult:
        """Run a single cycle of Gardener + IdentityResolver."""
        self._cycle_count += 1
        
        result = ScheduledCycleResult(
            cycle_number=self._cycle_count,
            started_at=datetime.utcnow(),
        )
        
        session = None
        try:
            session = get_session()
            
            validated_count = self._fast_validate_staging(session)
            if validated_count > 0:
                print(f"[Scheduler] Fast-validated {validated_count} STAGING entities")
            
            gardener = Gardener(
                session=session,
                config=self.config.gardener_config,
            )
            result.gardener_result = gardener.run_cycle()
            
            if self.config.run_identity_resolution:
                identity = IdentityResolver(
                    session=session,
                    config=self.config.identity_config,
                )
                result.identity_result = identity.run(commit=True)
            
            result.success = True
            
        except Exception as e:
            result.success = False
            result.error = str(e)
            if session:
                session.rollback()
        finally:
            if session:
                session.close()
        
        result.completed_at = datetime.utcnow()
        self._last_result = result
        
        self._log_cycle_result(result)
        
        return result
    
    def _log_cycle_result(self, result: ScheduledCycleResult) -> None:
        """Log cycle result for monitoring."""
        if result.success:
            gardener = result.gardener_result
            identity = result.identity_result
            
            gardener_summary = ""
            if gardener:
                gardener_summary = (
                    f"decayed={gardener.facts_decayed}, "
                    f"promoted={gardener.facts_promoted}, "
                    f"demoted={gardener.facts_demoted}, "
                    f"conflicts={gardener.conflicts_resolved}"
                )
            
            identity_summary = ""
            if identity:
                identity_summary = (
                    f"candidates={identity.candidates_found}, "
                    f"merged={identity.auto_merged}, "
                    f"review={identity.flagged_for_review}"
                )
            
            print(f"[Scheduler] Cycle #{result.cycle_number} complete: "
                  f"Gardener({gardener_summary}) Identity({identity_summary})")
        else:
            print(f"[Scheduler] Cycle #{result.cycle_number} FAILED: {result.error}")
    
    def _fast_validate_staging(self, session) -> int:
        """
        Fast SQL-based validation for STAGING entities.
        
        Marks STAGING entities with high confidence as VALID so Gardener can promote them.
        This is faster than running full StagingValidator which does expensive conflict detection.
        
        Returns: Number of entities marked as VALID
        """
        result = session.execute(text("""
            UPDATE entities 
            SET validation_status = 'VALID',
                last_validated_at = NOW()
            WHERE lifecycle_state = 'STAGING'
              AND validation_status = 'PENDING'
              AND confidence >= 0.70
              AND name IS NOT NULL
        """))
        
        rel_result = session.execute(text("""
            UPDATE relationships 
            SET validation_status = 'VALID',
                last_validated_at = NOW()
            WHERE lifecycle_state = 'STAGING'
              AND (validation_status IS NULL OR validation_status = 'PENDING')
              AND confidence >= 0.70
        """))
        
        session.commit()
        return result.rowcount + rel_result.rowcount


_scheduler_instance: Optional[GardenerScheduler] = None


def get_scheduler() -> GardenerScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = GardenerScheduler()
    return _scheduler_instance


def start_scheduler(config: Optional[SchedulerConfig] = None) -> GardenerScheduler:
    """Start the global scheduler with optional config."""
    global _scheduler_instance
    if _scheduler_instance is not None:
        _scheduler_instance.stop()
    
    _scheduler_instance = GardenerScheduler(config=config)
    _scheduler_instance.start()
    return _scheduler_instance


def stop_scheduler() -> None:
    """Stop the global scheduler."""
    global _scheduler_instance
    if _scheduler_instance:
        _scheduler_instance.stop()
        _scheduler_instance = None
