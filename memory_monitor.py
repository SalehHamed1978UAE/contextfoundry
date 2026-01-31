#!/usr/bin/env python3
"""Monitor system memory during stress tests."""

import psutil
import time
import json
from datetime import datetime

def get_system_memory():
    """Get system-wide memory stats."""
    mem = psutil.virtual_memory()
    return {
        'total_gb': mem.total / (1024**3),
        'available_gb': mem.available / (1024**3),
        'used_gb': mem.used / (1024**3),
        'percent': mem.percent
    }

def get_postgres_memory():
    """Get PostgreSQL process memory."""
    pg_mem = 0
    for proc in psutil.process_iter(['name', 'memory_info']):
        try:
            if 'postgres' in proc.info['name'].lower():
                pg_mem += proc.info['memory_info'].rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pg_mem / (1024**2)  # MB

def get_python_memory():
    """Get Python process memory."""
    py_mem = 0
    for proc in psutil.process_iter(['name', 'memory_info', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info.get('cmdline') or [])
            if 'python' in cmdline and 'memory_monitor' not in cmdline:
                py_mem += proc.info['memory_info'].rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return py_mem / (1024**2)  # MB

def main():
    print("Memory Monitor - Capturing current state")
    print("=" * 50)
    
    sys_mem = get_system_memory()
    pg_mem = get_postgres_memory()
    py_mem = get_python_memory()
    
    print(f"System Memory:")
    print(f"  Total:     {sys_mem['total_gb']:.2f} GB")
    print(f"  Used:      {sys_mem['used_gb']:.2f} GB ({sys_mem['percent']:.1f}%)")
    print(f"  Available: {sys_mem['available_gb']:.2f} GB")
    print(f"\nPostgreSQL: {pg_mem:.0f} MB")
    print(f"Python:     {py_mem:.0f} MB")
    
    # Calculate headroom
    headroom = sys_mem['available_gb']
    print(f"\nMemory headroom: {headroom:.2f} GB")
    
    if headroom < 0.5:
        print("[WARNING] Low memory - may cause issues with high concurrency")
    elif headroom < 1.0:
        print("[CAUTION] Moderate memory pressure")
    else:
        print("[OK] Sufficient memory available")
    
    return {
        'timestamp': datetime.now().isoformat(),
        'system': sys_mem,
        'postgres_mb': pg_mem,
        'python_mb': py_mem,
        'headroom_gb': headroom
    }

if __name__ == "__main__":
    result = main()
    with open('scale_test_results/memory_snapshot.json', 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nSnapshot saved to scale_test_results/memory_snapshot.json")
