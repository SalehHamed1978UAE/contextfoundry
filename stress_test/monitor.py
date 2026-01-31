#!/usr/bin/env python3
"""
Stress Test Monitor
Automatically monitors the stress test process, detects failures, and restarts.
"""

import subprocess
import time
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

RESULTS_DIR = Path("/home/runner/workspace/overnight_results")
LOG_FILE = RESULTS_DIR / "stress_test.log"
MONITOR_LOG = RESULTS_DIR / "monitor.log"
CHECK_INTERVAL = 60  # seconds
MAX_STALL_TIME = 300  # 5 minutes without progress = stalled
MAX_RESTARTS = 10


def log(msg: str):
    """Log to both console and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(MONITOR_LOG, "a") as f:
        f.write(line + "\n")


def get_stress_test_pid() -> int | None:
    """Get PID of running stress test process."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "run_stress_test.py"],
            capture_output=True,
            text=True
        )
        pids = result.stdout.strip().split("\n")
        pids = [int(p) for p in pids if p.strip()]
        return pids[0] if pids else None
    except:
        return None


def get_log_size() -> int:
    """Get current log file size."""
    try:
        return LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
    except:
        return 0


def get_last_log_lines(n: int = 5) -> list[str]:
    """Get last N lines from log file."""
    try:
        if not LOG_FILE.exists():
            return []
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
            return lines[-n:] if len(lines) >= n else lines
    except:
        return []


def check_for_errors() -> str | None:
    """Check log for error patterns."""
    error_patterns = [
        "Traceback",
        "Error:",
        "Exception:",
        "FATAL",
        "Connection refused",
        "Authentication failed"
    ]
    try:
        lines = get_last_log_lines(50)
        for line in lines:
            for pattern in error_patterns:
                if pattern in line:
                    return line.strip()
    except:
        pass
    return None


def start_stress_test() -> bool:
    """Start the stress test process."""
    log("Starting stress test...")
    try:
        subprocess.run(
            ["bash", "-c", 
             "cd /home/runner/workspace && "
             "nohup python3 -u stress_test/run_stress_test.py --mode overnight "
             "</dev/null >> overnight_results/stress_test.log 2>&1 &"],
            check=True
        )
        time.sleep(3)
        pid = get_stress_test_pid()
        if pid:
            log(f"Stress test started with PID {pid}")
            return True
        else:
            log("Failed to start stress test - no PID found")
            return False
    except Exception as e:
        log(f"Failed to start stress test: {e}")
        return False


def get_progress_stats() -> dict:
    """Get current progress from log."""
    stats = {
        "docs_ingested": 0,
        "queries_executed": 0,
        "last_activity": None
    }
    try:
        lines = get_last_log_lines(100)
        for line in reversed(lines):
            if "Ingested:" in line and stats["docs_ingested"] == 0:
                pass  # Could parse doc count
            if "queries" in line.lower() and stats["queries_executed"] == 0:
                pass  # Could parse query count
            if "[INFO]" in line and not stats["last_activity"]:
                stats["last_activity"] = datetime.now()
    except:
        pass
    return stats


def main():
    log("=" * 60)
    log("STRESS TEST MONITOR STARTING")
    log("=" * 60)
    
    restart_count = 0
    last_log_size = 0
    last_progress_time = datetime.now()
    
    while True:
        try:
            pid = get_stress_test_pid()
            current_log_size = get_log_size()
            
            if not pid:
                log("Stress test not running!")
                
                if restart_count >= MAX_RESTARTS:
                    log(f"Max restarts ({MAX_RESTARTS}) reached. Stopping monitor.")
                    break
                
                error = check_for_errors()
                if error:
                    log(f"Last error: {error}")
                
                if start_stress_test():
                    restart_count += 1
                    log(f"Restart #{restart_count} successful")
                    last_progress_time = datetime.now()
                else:
                    log("Restart failed, waiting before retry...")
                    time.sleep(30)
            else:
                if current_log_size > last_log_size:
                    last_progress_time = datetime.now()
                    last_log_size = current_log_size
                else:
                    stall_duration = (datetime.now() - last_progress_time).total_seconds()
                    if stall_duration > MAX_STALL_TIME:
                        log(f"Stress test stalled for {stall_duration:.0f}s - killing and restarting")
                        try:
                            subprocess.run(["kill", str(pid)])
                            time.sleep(2)
                        except:
                            pass
                        continue
                
                last_lines = get_last_log_lines(3)
                if last_lines:
                    log(f"PID {pid} running | Log: {current_log_size} bytes | Last: {last_lines[-1].strip()[:60]}...")
                else:
                    log(f"PID {pid} running | Log: {current_log_size} bytes")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            log("Monitor stopped by user")
            break
        except Exception as e:
            log(f"Monitor error: {e}")
            time.sleep(10)
    
    log("Monitor exiting")


if __name__ == "__main__":
    main()
