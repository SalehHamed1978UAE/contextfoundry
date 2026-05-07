#!/usr/bin/env bash
# Re-extract ALL remaining failed docs in one continuous run.
set -e
cd /home/runner/workspace
exec python -u scripts/_batch_reextract_failed.py --count 100 2>&1
