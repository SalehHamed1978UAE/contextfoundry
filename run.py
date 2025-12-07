#!/usr/bin/env python3
import subprocess
import sys
import os
import time
import signal
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

processes = []


def signal_handler(signum, frame):
    logger.info("Shutdown signal received, stopping services...")
    for name, proc in processes:
        if proc.poll() is None:
            logger.info(f"Stopping {name}...")
            proc.terminate()
    for name, proc in processes:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    sys.exit(0)


def main():
    global processes
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    env = os.environ.copy()
    env['BRAIN_INTERNAL_URL'] = 'http://localhost:5001'
    
    logger.info("Starting Brain service on port 5001...")
    brain_proc = subprocess.Popen(
        [sys.executable, 'brain/app.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    processes.append(('Brain', brain_proc))
    
    time.sleep(2)
    
    if brain_proc.poll() is not None:
        logger.error("Brain service failed to start!")
        output = brain_proc.stdout.read().decode() if brain_proc.stdout else ""
        logger.error(f"Output: {output}")
        sys.exit(1)
    
    logger.info("Starting Platform service on port 5000...")
    platform_proc = subprocess.Popen(
        [sys.executable, 'platform_app.py'],
        env=env,
        stdout=None,
        stderr=None
    )
    processes.append(('Platform', platform_proc))
    
    time.sleep(1)
    
    if platform_proc.poll() is not None:
        logger.error("Platform service failed to start!")
        brain_proc.terminate()
        sys.exit(1)
    
    logger.info("=" * 50)
    logger.info("Both services running:")
    logger.info("  - Brain:    http://localhost:5001 (internal API)")
    logger.info("  - Platform: http://localhost:5000 (user-facing)")
    logger.info("=" * 50)
    
    while True:
        for name, proc in processes:
            if proc.poll() is not None:
                logger.error(f"{name} service exited with code {proc.returncode}")
                signal_handler(None, None)
        time.sleep(1)


if __name__ == '__main__':
    main()
