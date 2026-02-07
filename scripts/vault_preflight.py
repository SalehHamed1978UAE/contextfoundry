#!/usr/bin/env python3
"""Vault preflight command.

Use this before extraction/eval to avoid split-brain state issues.
"""

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.context_foundry.monitoring.vault_consistency import build_vault_preflight_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DB-backed vault preflight checks")
    parser.add_argument("--vault-id", required=True, help="Vault UUID")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when checks are not all passing")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(json.dumps({"ok": False, "error": "DATABASE_URL not configured"}, indent=2))
        return 2

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        report = build_vault_preflight_report(session, args.vault_id)
    finally:
        session.close()

    print(json.dumps(report, indent=2, default=str))

    if args.strict and (not report.get("ok")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
